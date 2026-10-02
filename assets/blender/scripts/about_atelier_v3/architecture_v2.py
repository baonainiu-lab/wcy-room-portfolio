"""Build an editable, connected pavilion revision from the read-only atelier.

Run in background Blender. Only collection 90 architecture is revised; core
furniture meshes, materials, IDs and transforms remain untouched.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kit as K
import web_export as W

ROOT = W.ROOT
ORIGINAL = ROOT / 'assets/blender/about-atelier-v3.blend'
OUTPUT = ROOT / 'assets/blender/about-atelier-v3-architecture-v2.blend'
REPORT = ROOT / 'assets/blender/about-atelier-v3-web/architecture-v2-build-report.json'
RENDERS = ROOT / 'renders/about-atelier-v3-architecture-v2'
PREFIXES = ('context.limestone.tile', 'context.window.pier', 'context.window.mullion',
            'context.window.horizontal', 'context.window.glazing', 'context.side.mullion',
            'context.side.glazing')


def main_signature(scene):
    objects = sorted({o for c in scene.collection.children if c.name.startswith(('01_', '02_', '03_', '04_'))
                      for o in c.all_objects}, key=lambda o: o.name)
    digest = hashlib.sha256()
    for o in objects:
        digest.update(json.dumps({'name': o.name, 'type': o.type,
            'matrix': [list(row) for row in o.matrix_world],
            'parent': o.parent.name if o.parent else None,
            'asset_id': o.get('asset_id'), 'interaction': o.get('interaction'),
            'materials': [s.material.name if s.material else None for s in o.material_slots]},
            sort_keys=True).encode())
        if o.type == 'MESH':
            digest.update(str([(tuple(v.co)) for v in o.data.vertices]).encode())
            digest.update(str([tuple(p.vertices) for p in o.data.polygons]).encode())
    return digest.hexdigest(), len(objects), sorted(o['asset_id'] for o in objects if o.get('asset_id'))


def aabb(o):
    points = [o.matrix_world @ Vector(p) for p in o.bound_box]
    return {'min': [min(p[i] for p in points) for i in range(3)],
            'max': [max(p[i] for p in points) for i in range(3)]}


def overlaps(a, b):
    return all(a['min'][i] <= b['max'][i] + 1e-5 and b['min'][i] <= a['max'][i] + 1e-5 for i in range(3))


def main():
    assert bpy.app.background
    original_hash = W.sha(ORIGINAL)
    bpy.ops.wm.open_mainfile(filepath=str(ORIGINAL))
    scene = bpy.context.scene
    before, main_objects, ids = main_signature(scene)
    assert len(ids) == 128
    collection = bpy.data.collections['90_RENDER_Atrium_Lake']
    architecture = [o for o in collection.all_objects if o.name.startswith(PREFIXES)]
    removed = sorted(o.name for o in collection.all_objects if o not in architecture)
    for o in list(collection.all_objects):
        if o not in architecture:
            bpy.data.objects.remove(o, do_unlink=True)
    navy = bpy.data.objects['context.window.mullion'].data.materials[0]
    stone = bpy.data.objects['context.window.pier'].data.materials[0]
    brass = bpy.data.materials['ATELIER_V3_SatinBrass']
    light = bpy.data.materials.new('ATELIER_ARCH_V2_WarmLinearDiffuser')
    light.use_nodes = True
    p = W.principle(light)
    p.inputs['Base Color'].default_value = K.srgb('FFE4B2')
    p.inputs['Roughness'].default_value = .38
    p.inputs['Emission Color'].default_value = K.srgb('FFDE9A')
    p.inputs['Emission Strength'].default_value = 2.5
    light['source'] = 'Original procedural architectural diffuser; no third-party image'

    def mark(o, role):
        o['architecture_export'] = True
        o['architecture_role'] = role
        o['interactive'] = False
        o['excludeFromFraming'] = True
        if 'asset_id' in o:
            del o['asset_id']
        return o

    def box(name, center, size, material, role, bevel=.008):
        ob = K.box('context.arch.' + name, center, size, material, None, bevel)
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        collection.objects.link(ob)
        return mark(ob, role)

    def resize(ob, center, size, bevel=None):
        widths = [max(v.co[i] for v in ob.data.vertices) - min(v.co[i] for v in ob.data.vertices) for i in range(3)]
        for vertex in ob.data.vertices:
            for i in range(3):
                vertex.co[i] *= size[i] / widths[i]
        ob.location = center
        if bevel is not None:
            for modifier in ob.modifiers:
                if modifier.type == 'BEVEL':
                    modifier.width = bevel
                    modifier.segments = 4
        ob.data.update()

    for ob in architecture:
        mark(ob, 'glazing' if 'glazing' in ob.name else 'floor' if 'limestone.tile' in ob.name else 'vertical' if ('pier' in ob.name or 'mullion' in ob.name) else 'rail')
    # Crop the huge render-only tile sheet to the glazed pavilion footprint.
    # Retain physical grout joints while replacing the paper-thin exposed edge
    # with a continuous stone slab, coping and recessed closed underside.
    cropped_tiles, removed_tiles = [], []
    for ob in [o for o in architecture if 'limestone.tile' in o.name]:
        source_box = aabb(ob)
        x0, x1 = max(source_box['min'][0], -5.75), min(source_box['max'][0], 7.28)
        y0, y1 = max(source_box['min'][1], -5.84), min(source_box['max'][1], 5.24)
        if x1 <= x0 or y1 <= y0:
            removed_tiles.append(ob.name)
            architecture.remove(ob)
            bpy.data.objects.remove(ob, do_unlink=True)
            continue
        resize(ob, ((x0+x1)/2, (y0+y1)/2, -.044), (x1-x0, y1-y0, .080), .002)
        cropped_tiles.append(ob.name)
    assert len(cropped_tiles) == 20
    deck = box('deck.structural.stone.slab', (.765, -.30, -.20), (13.29, 11.34, .24), stone, 'deck_slab', .014)
    # Coping segments meet edge-to-edge, avoiding coplanar corner overlaps.
    for name, center, size in [
        ('left', (-5.815, -.30, -.051), (.15, 11.36, .108)),
        ('right', (7.345, -.30, -.051), (.15, 11.36, .108)),
        ('front', (.765, -5.905, -.051), (13.01, .15, .108)),
        ('back', (.765, 5.305, -.051), (13.01, .15, .108))]:
        box('deck.coping.' + name, center, size, stone, 'deck_coping', .007)
    box('deck.recessed.closed.underside', (.765, -.30, -.388), (13.08, 11.12, .164), navy, 'deck_underside', .016)
    for name, center, size in [
        ('left', (-5.886, -.30, -.145), (.012, 11.30, .018)),
        ('right', (7.416, -.30, -.145), (.012, 11.30, .018)),
        ('front', (.765, -5.976, -.145), (13.30, .012, .018)),
        ('back', (.765, 5.376, -.145), (13.30, .012, .018))]:
        box('deck.fascia.brass.inlay.' + name, center, size, brass, 'deck_inlay', .002)
    # Corner positions close the L: left/front, left/back, right/back. This
    # removes the original unexplained pair of adjacent rear stone sticks.
    piers = sorted([o for o in architecture if 'window.pier' in o.name], key=lambda o: o.name)
    pier_centers = [(-5.52, -5.60), (-5.52, 5.00), (7.10, 5.00)]
    for ob, (x, y) in zip(piers, pier_centers):
        resize(ob, (x, y, 2.855), (.30, .34, 5.47), .015)
        box('column.base.' + ob.name, (x, y, .085), (.44, .48, .17), stone, 'base', .016)
        box('column.foot.reveal.' + ob.name, (x, y, .192), (.322, .362, .035), navy, 'joint', .003)
        box('column.cap.' + ob.name, (x, y, 5.515), (.44, .48, .19), stone, 'cap', .014)
        box('column.cap.reveal.' + ob.name, (x, y, 5.39), (.322, .362, .025), brass, 'joint', .002)

    back_mullions = sorted([o for o in architecture if 'window.mullion' in o.name], key=lambda o: o.name)
    back_x = [-5.52, -2.8, .5, 3.8, 7.1]
    for ob, x in zip(back_mullions, back_x):
        resize(ob, (x, 5.0, 2.835), (.080, .160, 5.27), .006)
        box('back.mullion.pressure.cap.' + ob.name, (x, 4.916, 2.835), (.132, .022, 5.27), navy, 'vertical', .005)
    side_mullions = sorted([o for o in architecture if 'side.mullion' in o.name], key=lambda o: o.name)
    for ob, y in zip(side_mullions, [-5.6, -2.95, -.3, 2.35, 5.0]):
        resize(ob, (-5.52, y, 2.835), (.160, .080, 5.27), .006)
        box('side.mullion.pressure.cap.' + ob.name, (-5.436, y, 2.835), (.022, .132, 5.27), navy, 'vertical', .005)
    back_glass = sorted([o for o in architecture if 'window.glazing' in o.name], key=lambda o: o.name)
    for ob, x, width in zip(back_glass, [-4.16, -1.15, 2.15, 5.45], [2.65, 3.25, 3.25, 3.25]):
        resize(ob, (x, 5.035, 2.815), (width, .014, 5.17), .001)
    for ob in [o for o in architecture if 'side.glazing' in o.name]:
        resize(ob, (-5.52, ob.location.y, 2.815), (.014, 2.59, 5.17), .001)
    for ob, z in zip(sorted([o for o in architecture if 'window.horizontal' in o.name], key=lambda o: o.name), [.20, 5.43]):
        resize(ob, (.79, 5.0, z), (12.70, .16, .10), .006)
    for label, z in [('bottom', .20), ('top', 5.43)]:
        box('side.continuous.rail.' + label, (-5.52, -.30, z), (.16, 10.66, .10), navy, 'rail', .006)

    beams = [box('back.header.stone', (.79, 5.0, 5.49), (12.94, .44, .28), stone, 'header', .018),
             box('side.header.stone', (-5.52, -.30, 5.49), (.44, 10.90, .28), stone, 'header', .018)]
    sills = [box('back.sill.stone', (.79, 5.0, .085), (12.94, .40, .17), stone, 'sill', .014),
             box('side.sill.stone', (-5.52, -.30, .085), (.40, 10.90, .17), stone, 'sill', .014)]
    box('back.soffit.shadow.reveal', (.79, 4.99, 5.342), (12.72, .32, .022), navy, 'soffit', .004)
    box('side.soffit.shadow.reveal', (-5.51, -.30, 5.342), (.32, 10.66, .022), navy, 'soffit', .004)
    box('back.header.brass.inlay', (.79, 4.774, 5.445), (12.80, .012, .016), brass, 'inlay', .002)
    box('side.header.brass.inlay', (-5.294, -.30, 5.445), (.012, 10.76, .016), brass, 'inlay', .002)
    box('back.sill.brass.reveal', (.79, 4.795, .139), (12.78, .012, .020), brass, 'inlay', .002)
    box('side.sill.brass.reveal', (-5.315, -.30, .139), (.012, 10.74, .020), brass, 'inlay', .002)
    # Flush strips live inside the header soffit; no detached lamps or props.
    for i, x in enumerate([-1.15, 2.15, 5.45]):
        box('back.linear.diffuser.%d' % i, (x, 4.97, 5.325), (2.76, .052, .014), light, 'linear_light', .003)
    for i, y in enumerate([-4.275, -1.625, 1.025, 3.675]):
        box('side.linear.diffuser.%d' % i, (-5.49, y, 5.325), (.052, 2.18, .014), light, 'linear_light', .003)
    # A flush floor inlay describes the open front/right boundary without
    # adding barriers in either the hero view or the camera travel corridor.
    for name, center, size in [
        ('floor.border.back', (.79, 4.71, .004), (12.94, .026, .014)),
        ('floor.border.side', (-5.23, -.30, .004), (.026, 10.90, .014)),
        ('floor.border.front', (.92, -5.75, .004), (12.68, .026, .014)),
        ('floor.border.right', (7.26, -.39, .004), (.026, 10.72, .014))]:
        box(name, center, size, brass, 'floor_inlay', .0015)

    bpy.context.view_layer.update()
    selected = [o for o in collection.all_objects if o.get('architecture_export')]
    verticals = [o for o in selected if o.get('architecture_role') == 'vertical']
    top_connectors = [o for o in selected if o.get('architecture_role') in {'header', 'cap'}]
    bottom_connectors = [o for o in selected if o.get('architecture_role') in {'base', 'sill', 'rail'} and aabb(o)['min'][2] < .25]
    closed = []
    for ob in verticals:
        bounds = aabb(ob)
        lower, upper = [dict(bounds), dict(bounds)]
        lower['max'] = [*bounds['max'][:2], bounds['min'][2] + .02]
        upper['min'] = [*bounds['min'][:2], bounds['max'][2] - .02]
        low = [o.name for o in bottom_connectors if overlaps(lower, aabb(o))]
        high = [o.name for o in top_connectors if overlaps(upper, aabb(o))]
        assert low and high, (ob.name, low, high, bounds)
        closed.append({'vertical': ob.name, 'bottomConnections': low, 'topConnections': high})
    assert overlaps(aabb(beams[0]), aabb(beams[1]))
    assert overlaps(aabb(sills[0]), aabb(sills[1]))
    after, _, after_ids = main_signature(scene)
    assert after == before and after_ids == ids
    assert W.sha(ORIGINAL) == original_hash
    scene['architecture_revision'] = 'V2 connected pavilion'
    scene['architecture_original_source'] = W.rel(ORIGINAL)
    scene['architecture_original_sha256'] = original_hash
    scene['architecture_main_signature'] = before
    scene['architecture_removed_decor'] = json.dumps(removed)
    scene['architecture_geometry_notes'] = '5.63m continuous L header, capped supports, full bottom rails, eight refitted panes, inset warm linear soffit lamps; 13.31 x 11.36m cropped stone deck with thick fascia, coping and recessed closed underside; front/right open'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    assert W.sha(ORIGINAL) == original_hash
    counts = {}
    for ob in selected:
        role = ob['architecture_role']
        counts[role] = counts.get(role, 0) + 1
    report = {'complete': True, 'original': W.rel(ORIGINAL), 'originalSha256': original_hash,
        'originalUnchanged': True, 'derivative': W.rel(OUTPUT), 'derivativeSha256': W.sha(OUTPUT),
        'mainGeometryHierarchyTransformsSignatureBefore': before,
        'mainGeometryHierarchyTransformsSignatureAfter': after, 'mainObjects': main_objects,
        'mainAssetCount': len(ids), 'mainAssetIdsUnchanged': True,
        'architectureSourceNodes': len(selected), 'architectureRoles': counts,
        'glassPanes': 8, 'maxStructureHeight': max(aabb(o)['max'][2] for o in selected),
        'originalMainMaxHeight': 4.146907329559326,
        'removedDecorCount': len(removed), 'removedDecorNodes': removed,
        'floorTilesRetainedAndCropped': cropped_tiles, 'oversizedFloorTilesRemoved': removed_tiles,
        'deckEnvelopeBlender': {'min': [-5.89, -5.98, -.47], 'max': [7.42, 5.38, .003]},
        'deckSurfaceToUndersideThicknessMetres': .466,
        'deckHasClosedStructuralBoxAndRecessedUnderside': True,
        'verticalConnections': closed, 'headerCornerConnected': True, 'sillCornerConnected': True,
        'frontAndRightCameraAccessOpen': True, 'newThirdPartyTextures': [],
        'design': scene['architecture_geometry_notes']}
    W.write_json(REPORT, report)
    print('ATELIER_ARCH_V2_BUILT', json.dumps({k: report[k] for k in
        ('derivative', 'architectureSourceNodes', 'architectureRoles', 'maxStructureHeight')}), flush=True)

    # Render the physical source revision from a wide travel-like view and the
    # existing hero camera; these are real Cycles frames, never image mockups.
    W.device(scene)
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .045
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    RENDERS.mkdir(parents=True, exist_ok=True)
    camera_data = bpy.data.cameras.new('CAM.architecture.v2.wide')
    camera = bpy.data.objects.new('CAM.architecture.v2.wide', camera_data)
    scene.collection.objects.link(camera)
    camera.location = (13.5, -18.5, 10.8)
    camera.rotation_euler = (Vector((.65, -.7, 1.65)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 38
    camera.data.clip_end = 300
    scene.camera = camera
    scene.render.filepath = str(RENDERS / 'wide.png')
    bpy.ops.render.render(write_still=True)
    scene.camera = bpy.data.objects['CAM.hero']
    scene.camera.data.dof.use_dof = False
    scene.render.filepath = str(RENDERS / 'hero.png')
    bpy.ops.render.render(write_still=True)
    print('ATELIER_ARCH_V2_RENDERS_DONE', str(RENDERS), flush=True)


if __name__ == '__main__':
    main()
