# -*- coding: utf-8 -*-
"""Extend walls outward/upward without moving the room interior or its assets.

CPU-only entry point: build_and_save(). Opens protected V9, edits the canonical
source and both full-quality lighting copies, then saves a new V10 file.
Collection names used by atlas preparation remain unchanged.
"""
import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE = ROOT / 'assets/blender/orbital-atelier-v9.blend'
OUTPUT = ROOT / 'assets/blender/orbital-atelier-v10.blend'
REPORT = ROOT / 'assets/blender/wall-structure-v10-report.json'
HEIGHT = .35
THICKNESS = .16
WALL_NAMES = ('A_BackWall_Graphite', 'A_LeftWallInner', 'A_SweepingTopBand',
              'A_LeftTopRail', 'A_LeftFrontRail')
WINDOW_NAMES = ('A_PanoramaTitaniumBezel', 'A_WindowRecessLight', 'A_Window_CityPanel',
                'A_WindowDisplayLedge', 'A_WindowDisplayInlay', 'A_WindowDisplayRecessGlow',
                'A_DisplayTowerBack', 'A_DisplayTowerFrame', 'A_RightSpine_Light', 'A_LeftSkirting')


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _activate(scene):
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()


def _name(obj):
    return obj.get('v8_original_object_name', obj.name)


def _find(scene, name):
    matches = [o for o in scene.objects if _name(o) == name]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one ' + name + ' in ' + scene.name)
    return matches[0]


def _collections(scene):
    pending, result = [scene.collection], []
    while pending:
        collection = pending.pop()
        if collection not in result:
            result.append(collection)
            pending.extend(collection.children)
    return result


def _make_independent(scene, obj):
    """Only replace objects shared with an old auxiliary scene, preserving it."""
    if len(obj.users_scene) > 1:
        matrix = obj.matrix_world.copy()
        clone = obj.copy()
        clone.name = 'V10__' + obj.name
        clone['v8_original_object_name'] = _name(obj)
        for collection in _collections(scene):
            if obj.name in collection.objects:
                if collection != scene.collection and collection.users > 1:
                    raise RuntimeError('Unexpected shared architecture collection: ' + collection.name)
                collection.objects.link(clone)
                collection.objects.unlink(obj)
        clone.matrix_world = matrix
        obj = clone
    if obj.data:
        # Every edited mesh is explicitly single-user before any modifier or
        # vertex change, even where the existing object already had one user.
        obj.data = obj.data.copy()
    return obj


def _bounds(scene, obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        return {'min': [min(p[k] for p in points) for k in range(3)],
                'max': [max(p[k] for p in points) for k in range(3)]}
    finally:
        evaluated.to_mesh_clear()


def _edit_vertices(obj, edit):
    matrix, inverse = obj.matrix_world.copy(), obj.matrix_world.inverted()
    for vertex in obj.data.vertices:
        world = matrix @ vertex.co
        vertex.co = inverse @ Vector(edit(world.copy()))
    obj.data.update()


def _raw_limits(obj):
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return ([min(p[k] for p in points) for k in range(3)],
            [max(p[k] for p in points) for k in range(3)])


def _assets(scene):
    _activate(scene)
    return sorted([{'asset_id': str(o['asset_id']), 'matrix': [list(row) for row in o.matrix_world]}
                   for o in scene.objects if o.get('asset_id')], key=lambda row: row['asset_id'])


def _unchanged_transforms(scene):
    _activate(scene)
    return {_name(o): [list(row) for row in o.matrix_world] for o in scene.objects
            if _name(o) not in WALL_NAMES and 'Cutaway_Roof_Flag' not in o.name}


def _support(scene, platform, material, collection):
    # One concave L footprint avoids overlapping coplanar top faces. Its inner
    # edges coincide with the existing room inner walls; interior floor is intact.
    outline = [(-5.37,-2.57), (-4.93,-2.57), (-4.93,3.31),
               (5.00,3.31), (5.00,3.80), (-5.37,3.80)]
    n = len(outline)
    vertices = [(x,y,z) for z in (-.10,.175) for x,y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n,n*2))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    data = bpy.data.meshes.new('W10_Wall_L_Footing_' + scene.name + '_Mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    data.materials.append(material)
    obj = bpy.data.objects.new('W10_Wall_L_Footing_' + scene.name, data)
    collection.objects.link(obj)
    obj.parent = platform
    obj.matrix_world = Matrix.Identity(4)
    obj['source_node'] = 'W10_Wall_L_Footing'
    obj['wall_structure_revision'] = 10
    # No asset_id: this remains part of the existing architecture.platform.
    uv = data.uv_layers.new(name='UVMap')
    for face in data.polygons:
        major = max(range(3), key=lambda k: abs(face.normal[k]))
        axes = [k for k in range(3) if k != major]
        for index in face.loop_indices:
            p = data.vertices[data.loops[index].vertex_index].co
            uv.data[index].uv = (p[axes[0]], p[axes[1]])
    bevel = obj.modifiers.new('Small rounded support edge', 'BEVEL')
    bevel.width = .025
    bevel.segments = 3
    bevel.harden_normals = True
    normal = obj.modifiers.new('Weighted support normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    return obj


def _modify_scene(scene):
    _activate(scene)
    before_ids = _assets(scene)
    unchanged = _unchanged_transforms(scene)
    before_windows = {name: _bounds(scene, _find(scene, name)) for name in WINDOW_NAMES}
    changes = {}
    objects = {}
    for name in WALL_NAMES:
        original = _find(scene, name)
        changes[name] = {'before': _bounds(scene, original)}
        objects[name] = _make_independent(scene, original)
    scene.view_layers[0].update()

    left = objects['A_LeftWallInner']
    solidify = next(m for m in left.modifiers if m.type == 'SOLIDIFY')
    if abs(solidify.offset + 1) > 1e-6:
        raise RuntimeError('Left wall must thicken outward with Solidify offset -1.')
    solidify.thickness = .38

    def left_wall(p):
        if p.y > 3.30:
            p.y = 3.74
        if p.z > .19:
            p.z += HEIGHT
        return p

    _edit_vertices(left, left_wall)

    def back_wall(p):
        if p.y > 3.50:
            p.y += THICKNESS
        if p.z > .19:
            p.z += HEIGHT
        return p

    _edit_vertices(objects['A_BackWall_Graphite'], back_wall)
    back = objects['A_SweepingTopBand']
    low, high = _raw_limits(back)
    front_y, rear_y = low[1], high[1]

    def back_cap(p):
        p.y = front_y + (p.y-front_y)/(rear_y-front_y)*(3.78-front_y)
        p.z += HEIGHT
        return p

    _edit_vertices(back, back_cap)
    top = objects['A_LeftTopRail']
    low, high = _raw_limits(top)
    outer_x, inner_x, rear_y = low[0], high[0], high[1]

    def left_cap(p):
        p.x = inner_x + (p.x-inner_x)/(outer_x-inner_x)*(-5.35-inner_x)
        if p.y > 2.60:
            p.y = 2.60 + (p.y-2.60)/(rear_y-2.60)*(3.78-2.60)
        p.z += HEIGHT
        return p

    _edit_vertices(top, left_cap)
    front = objects['A_LeftFrontRail']
    low, high = _raw_limits(front)
    outer_x, inner_x, bottom_z, top_z = low[0], high[0], low[2], high[2]

    def left_front(p):
        p.x = inner_x + (p.x-inner_x)/(outer_x-inner_x)*(-5.35-inner_x)
        p.z = bottom_z + (p.z-bottom_z)/(top_z-bottom_z)*(top_z+HEIGHT-bottom_z)
        return p

    _edit_vertices(front, left_front)

    # Isolate the shared canonical platform root and its three unchanged floor
    # pieces before adding a child, preserving archived source-parent hierarchies.
    platform_old = next(o for o in scene.objects if o.get('asset_id') == 'architecture.platform')
    children = [o for o in platform_old.children if o.name in scene.objects]
    platform = _make_independent(scene, platform_old)
    if platform != platform_old:
        for original in children:
            matrix = original.matrix_world.copy()
            child = _make_independent(scene, original)
            child.parent = platform
            child.matrix_world = matrix
    scene.view_layers[0].update()
    plinth = _find(scene, 'A_SilverPlinth')
    material = plinth.data.materials[0]
    # Use the existing unchanged collection name, essential for atlas routing.
    scene_collections = _collections(scene)
    collection = next(c for c in platform.users_collection if c in scene_collections)
    support = _support(scene, platform, material, collection)

    roof_report = None
    for obj in scene.objects:
        if 'Cutaway_Roof_Flag' not in obj.name:
            continue
        roof = _make_independent(scene, obj)
        roof.location.z = 5.21
        # Widen only outward, keeping the cutaway front/right edges unchanged.
        points = [roof.matrix_world @ v.co for v in roof.data.vertices]
        old_min_x = min(p.x for p in points)
        old_max_y = max(p.y for p in points)

        def roof_outward(p):
            if abs(p.x-old_min_x) < .001:
                p.x = -5.38
            if abs(p.y-old_max_y) < .001:
                p.y = 3.81
            return p

        _edit_vertices(roof, roof_outward)
        roof_report = {'name': roof.name, 'center_z': 5.21}
    scene.view_layers[0].update()
    for name, obj in objects.items():
        changes[name]['after'] = _bounds(scene, obj)
        changes[name]['object'] = obj.name
    after_windows = {name: _bounds(scene, _find(scene, name)) for name in WINDOW_NAMES}
    if after_windows != before_windows:
        raise RuntimeError('Window, shelves, or interior trim bounds changed.')
    if _assets(scene) != before_ids:
        raise RuntimeError('Asset IDs or asset world transforms changed in ' + scene.name)
    after_transforms = _unchanged_transforms(scene)
    if any(after_transforms.get(name) != matrix for name, matrix in unchanged.items()):
        raise RuntimeError('An unedited object/furniture transform changed in ' + scene.name)
    # Explicit room-side anchor checks on the untouched inner vertices.
    if any(abs(v.co.x + 4.93) > 1e-5 for v in left.data.vertices):
        raise RuntimeError('Left inner surface moved.')
    front_layer = min(v.co.y for v in objects['A_BackWall_Graphite'].data.vertices)
    if abs(front_layer-3.31) > 1e-5:
        raise RuntimeError('Back inner surface moved.')
    scene['wall_structure_revision'] = 10
    scene['wall_outward_extension_m'] = THICKNESS
    scene['wall_height_extension_m'] = HEIGHT
    return {'scene': scene.name, 'changes': changes,
            'asset_count_before': len(before_ids), 'asset_count_after': len(_assets(scene)),
            'all_asset_ids_and_world_transforms_unchanged': True,
            'all_unedited_object_transforms_unchanged': True,
            'window_shelf_and_interior_trim_bounds_unchanged': True,
            'left_inner_x': -4.93, 'back_inner_y': 3.31,
            'left_wall_thickness': .38, 'back_wall_thickness': .43,
            'new_footing': {'name': support.name, 'parent_asset_id': platform['asset_id'],
                            'bounds': _bounds(scene, support), 'new_interaction_ids': 0},
            'day_roof': roof_report,
            'atlas_collection_names_preserved': True}


def build_and_save():
    before = _sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    report = {'source': str(SOURCE), 'output': str(OUTPUT),
              'height_added_m': HEIGHT, 'outward_wall_thickness_added_m': THICKNESS,
              'source_sha256_before': before, 'scenes': {}}
    for name in ('ORBITAL_ATELIER_V2', 'ORIGINAL_DAY_V9', 'ORIGINAL_NIGHT_V8'):
        scene = bpy.data.scenes[name]
        state_report = _modify_scene(scene)
        if name == 'ORIGINAL_DAY_V9':
            scene.name = 'ORIGINAL_DAY_V10'
            if scene.get('day_sunlight_v9_report'):
                daylight = json.loads(scene['day_sunlight_v9_report'])
                daylight['scene'] = scene.name
                daylight['cutaway_roof_height_v10'] = 5.21
                scene['day_sunlight_v9_report'] = json.dumps(daylight)
        elif name == 'ORIGINAL_NIGHT_V8':
            scene.name = 'ORIGINAL_NIGHT_V10'
        state_report['scene'] = scene.name
        report['scenes'][scene.name] = state_report
    _activate(bpy.data.scenes['ORIGINAL_DAY_V10'])
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=True, check_existing=False)
    after = _sha(SOURCE)
    if after != before:
        raise RuntimeError('Protected V9 file changed.')
    report.update(source_sha256_after=after, source_file_unchanged=True,
                  bytes=OUTPUT.stat().st_size, sha256=_sha(OUTPUT),
                  active_scene='ORIGINAL_DAY_V10', renders_executed=0)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report
