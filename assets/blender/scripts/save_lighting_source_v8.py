# -*- coding: utf-8 -*-
"""Save an editable full-quality V8 source with independent day/night scenes.

Entry point: save_lighting_source_v8(). Run in a separate Blender process.
The function opens orbital-atelier-v8-interior.blend, retains every original scene, makes
two independent PBR scene copies, configures actual lights, packs the matching
city renders, and saves only orbital-atelier-v8.blend. No GPU render is run.
"""
import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE = ROOT / 'assets/blender/orbital-atelier-v8-interior.blend'
DESTINATION = ROOT / 'assets/blender/orbital-atelier-v8.blend'
TEXTURES = ROOT / 'public/textures/lighting-v8'


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _source_signature(source):
    """Ignore increased datablock user counts caused by harmless copying."""
    rows = []
    for obj in sorted(source.objects, key=lambda o: o.name):
        row = {'name': obj.name, 'type': obj.type,
               'matrix': [list(v) for v in obj.matrix_world],
               'data': obj.data.name if obj.data else None,
               'hide_render': obj.hide_render}
        if obj.type == 'LIGHT':
            row.update(energy=obj.data.energy, color=list(obj.data.color))
        if obj.data and hasattr(obj.data, 'materials'):
            row['materials'] = [m.name if m else None for m in obj.data.materials]
        rows.append(row)
    value = {'world': source.world.name if source.world else None, 'objects': rows}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode('utf-8')).hexdigest()


def _copy_scene(source, state):
    # Freshly reopened inactive scenes can have identity matrix_world caches.
    # Evaluate before taking any source transform or camera snapshot.
    if bpy.context.window:
        bpy.context.window.scene = source
    source.view_layers[0].update()
    originals = list(source.objects)
    transforms = {obj: obj.matrix_world.copy() for obj in originals}
    scene = bpy.data.scenes.new('ORIGINAL_' + state.upper() + '_V8')
    for key in source.keys():
        if key != '_RNA_UI':
            scene[key] = source[key]
    scene['lighting_source_revision'] = 8
    scene['lighting_state'] = state
    scene['geometry_quality'] = 'original full-resolution PBR geometry, modifiers and independent asset IDs'
    scene.unit_settings.system = source.unit_settings.system
    scene.unit_settings.scale_length = source.unit_settings.scale_length
    scene.render.engine = 'CYCLES'
    for attribute in ('resolution_x', 'resolution_y', 'resolution_percentage',
                      'pixel_aspect_x', 'pixel_aspect_y', 'film_transparent'):
        setattr(scene.render, attribute, getattr(source.render, attribute))
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = str(ROOT / 'renders' / ('lighting-v8-' + state + '-source.png'))
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 6
    scene.cycles.device = source.cycles.device
    scene.world = source.world.copy() if source.world else None

    objects, materials = {}, {}
    for original in originals:
        obj = original.copy()
        if original.data:
            obj.data = original.data.copy()
        obj.name = state.upper() + '_V8__' + original.name
        obj['v8_original_object_name'] = original.name
        obj.parent = None
        obj.matrix_world = transforms[original]
        if obj.type == 'LIGHT':
            # configure_lighting classifies names by the original fixture name.
            obj['v8_original_light_name'] = original.name
            obj['v8_original_light_energy'] = original.data.energy
        if obj.data and hasattr(obj.data, 'materials'):
            for index, material in enumerate(obj.data.materials):
                if material is None:
                    continue
                if material not in materials:
                    new = material.copy()
                    new.name = state.upper() + '_V8__' + material.name
                    materials[material] = new
                obj.data.materials[index] = materials[material]
        objects[original] = obj

    # Preserve authoring collection organization, while copying containers and
    # all object/data/material datablocks. No linked source collection is edited.
    collections = {}

    def copy_collection(original):
        if original in collections:
            return collections[original]
        collection = bpy.data.collections.new(state.upper() + '_V8__' + original.name)
        collections[original] = collection
        collection.hide_render = original.hide_render
        collection.hide_viewport = original.hide_viewport
        collection.hide_select = original.hide_select
        for obj in original.objects:
            if obj in objects:
                collection.objects.link(objects[obj])
        for child in original.children:
            collection.children.link(copy_collection(child))
        return collection

    for child in source.collection.children:
        scene.collection.children.link(copy_collection(child))
    for obj in source.collection.objects:
        scene.collection.objects.link(objects[obj])
    # Containers already belong exclusively to this new scene; avoid a second
    # unnecessary collection-tree copy inside configure_lighting().
    scene['v8_lighting_collections_isolated'] = True

    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()

    def depth(obj):
        level = 0
        while obj.parent in objects:
            obj = obj.parent
            level += 1
        return level

    # Evaluate each parent depth before assigning its children's world matrix.
    for level in sorted({depth(o) for o in originals}):
        for original in originals:
            if depth(original) != level or original.parent not in objects:
                continue
            obj = objects[original]
            obj.parent = objects[original.parent]
            obj.matrix_parent_inverse = original.matrix_parent_inverse.copy()
            obj.matrix_world = transforms[original]
        scene.view_layers[0].update()

    for original, obj in objects.items():
        # Preserve potential modeled-rig references without pointing back into
        # the source scene. This does not apply or discard any modifiers.
        for owner in list(obj.constraints) + list(obj.modifiers):
            for attribute in ('object', 'target', 'mirror_object', 'offset_object', 'origin'):
                reference = getattr(owner, attribute, None)
                if isinstance(reference, bpy.types.Object) and reference in objects:
                    try:
                        setattr(owner, attribute, objects[reference])
                    except (AttributeError, TypeError):
                        pass
    for material in materials.values():
        if material.node_tree:
            for node in material.node_tree.nodes:
                reference = getattr(node, 'object', None)
                if isinstance(reference, bpy.types.Object) and reference in objects:
                    node.object = objects[reference]
    scene.camera = objects[source.camera]
    scene.view_layers[0].update()
    return scene, materials, transforms, objects


def _set_material_state(materials, state):
    window_path = TEXTURES / ('window-' + state + '.png')
    window = bpy.data.images.load(str(window_path), check_existing=False)
    window.name = 'WINDOW_' + state.upper() + '_V8_RENDER'
    window.pack()
    replaced = 0
    changed_emission = 0
    for material in materials.values():
        if not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                name = (node.image.name + ' ' + node.image.filepath).lower()
                if 'window-city' in name or 'window_city' in name:
                    node.image = window
                    replaced += 1
            # Match the website's actual PBR bake: practical emissive materials
            # dim in daytime; dedicated monitor/window image shaders retain
            # their original calibrated image emission strengths.
            if state == 'day' and node.type == 'BSDF_PRINCIPLED':
                socket = node.inputs.get('Emission Strength')
                if socket is not None and not socket.is_linked:
                    if socket.default_value > 0:
                        socket.default_value *= 0.20
                        changed_emission += 1
    if replaced == 0:
        raise RuntimeError('No original window-city image node found; refusing an unmatched lighting source.')
    return {'window_file': str(window_path), 'window_image': window.name,
            'window_image_packed': bool(window.packed_file),
            'window_nodes_replaced': replaced, 'day_fixture_emission_materials_dimmed': changed_emission}


def save_lighting_source_v8(source_path=None, output_path=None):
    """Open protected V7, create day/night editable scenes, save new V8 only."""
    source_path = Path(source_path) if source_path else SOURCE
    output_path = Path(output_path) if output_path else DESTINATION
    if source_path.resolve() == output_path.resolve():
        raise ValueError('Source and output paths must differ.')
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    for state in ('day', 'night'):
        path = TEXTURES / ('window-' + state + '.png')
        if not path.is_file():
            raise FileNotFoundError(path)
    original_sha = _sha256(source_path)
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    source = bpy.data.scenes['ORBITAL_ATELIER_V2']
    if bpy.context.window:
        bpy.context.window.scene = source
    source.view_layers[0].update()
    original_signature = _source_signature(source)
    original_scenes = set(bpy.data.scenes.keys())
    source_ids = sorted(str(o['asset_id']) for o in source.objects if o.get('asset_id'))
    scope = {'__name__': 'source_lighting_v8'}
    path = ROOT / 'assets/blender/scripts/lighting_states_v8.py'
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), scope)
    report = {'source': str(source_path), 'output': str(output_path),
              'source_sha256_before': original_sha, 'states': {}}
    new_scenes = {}
    for state in ('day', 'night'):
        scene, materials, matrices, objects = _copy_scene(source, state)
        texture_report = _set_material_state(materials, state)
        lighting_report = scope['configure_lighting'](scene, state)
        scene.view_layers[0].update()
        ids = sorted(str(o['asset_id']) for o in scene.objects if o.get('asset_id'))
        if ids != source_ids:
            raise RuntimeError('Independent asset IDs changed in ' + state + ' scene.')
        max_delta = max(abs(objects[o].matrix_world[r][c] - matrices[o][r][c])
                        for o in objects if o.type != 'LIGHT'
                        for r in range(4) for c in range(4))
        if max_delta > 0.0001:
            raise RuntimeError('Copied geometry/camera transforms differ by ' + str(max_delta))
        scene['v8_lighting_configuration'] = json.dumps(lighting_report, sort_keys=True)
        new_scenes[state] = scene
        report['states'][state] = {
            'scene': scene.name, 'objects': len(scene.objects),
            'mesh_objects': sum(o.type == 'MESH' for o in scene.objects),
            'curve_objects': sum(o.type == 'CURVE' for o in scene.objects),
            'independent_asset_id_count': len(ids), 'independent_asset_ids': ids,
            'materials': len(materials), 'camera': scene.camera.name,
            'camera_position': list(scene.camera.matrix_world.translation),
            'maximum_transform_delta': max_delta, 'texture': texture_report,
            'lighting': lighting_report,
        }
    if not original_scenes.issubset(set(bpy.data.scenes.keys())):
        raise RuntimeError('An original scene was unexpectedly removed.')
    if _source_signature(source) != original_signature:
        raise RuntimeError('Protected source scene changed in memory.')
    if bpy.context.window:
        bpy.context.window.scene = new_scenes['day']
    new_scenes['day'].view_layers[0].update()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), compress=True, check_existing=False)
    original_after = _sha256(source_path)
    if original_after != original_sha:
        raise RuntimeError('Protected V7 source file changed on disk.')
    report.update(source_sha256_after=original_after, source_file_unchanged=True,
                  source_scene_unchanged=True, original_scenes_preserved=sorted(original_scenes),
                  active_scene=new_scenes['day'].name, bytes=output_path.stat().st_size,
                  sha256=_sha256(output_path), renders_executed=0)
    return report
