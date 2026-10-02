# -*- coding: utf-8 -*-
"""Save the verified V9 daylight in a new editable full-quality .blend.

Call save_day_source_v9() in a separate Blender process. No rendering/GPU work.
Only ORIGINAL_DAY_V8 receives the daylight rig and is renamed ORIGINAL_DAY_V9.
All original and accepted night scenes remain unchanged; V8 on disk is protected.
"""
import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE = ROOT / 'assets/blender/orbital-atelier-v8.blend'
DESTINATION = ROOT / 'assets/blender/orbital-atelier-v9.blend'
REPORT = ROOT / 'assets/blender/day-source-v9-report.json'


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _value(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, bpy.types.ID):
        return {'id_type': value.bl_rna.identifier, 'name': value.name}
    try:
        return [_value(v) for v in value]
    except TypeError:
        return str(value)


def _node_tree(tree):
    if tree is None:
        return None
    nodes = []
    for node in sorted(tree.nodes, key=lambda n: n.name):
        record = {'name': node.name, 'type': node.type, 'mute': node.mute,
                  'inputs': {s.identifier: _value(s.default_value)
                             for s in node.inputs if hasattr(s, 'default_value')}}
        for attribute in ('operation', 'blend_type', 'distribution', 'subsurface_method',
                          'interpolation', 'projection', 'extension', 'uv_map',
                          'sky_type', 'sun_elevation', 'sun_rotation', 'sun_disc',
                          'air_density', 'dust_density', 'aerosol_density', 'ozone_density'):
            if hasattr(node, attribute):
                record[attribute] = _value(getattr(node, attribute))
        image = getattr(node, 'image', None)
        if image:
            record['image'] = {'name': image.name, 'filepath': image.filepath,
                               'size': list(image.size), 'colorspace': image.colorspace_settings.name}
        if hasattr(node, 'color_ramp'):
            record['ramp'] = [[e.position, list(e.color)] for e in node.color_ramp.elements]
        nodes.append(record)
    links = sorted((l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier)
                   for l in tree.links)
    return {'nodes': nodes, 'links': links}


def _activate(scene):
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()


def _snapshot(scene):
    _activate(scene)
    rows = []
    materials = {}
    for obj in sorted(scene.objects, key=lambda o: o.name):
        row = {'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
               'matrix_world': [list(v) for v in obj.matrix_world],
               'asset_id': obj.get('asset_id'), 'hide_render': obj.hide_render,
               'data': obj.data.name if obj.data else None}
        if obj.type == 'LIGHT':
            light = obj.data
            row['light'] = {'type': light.type, 'energy': light.energy, 'color': list(light.color)}
            for attribute in ('size', 'size_y', 'angle', 'shape', 'shadow_soft_size'):
                if hasattr(light, attribute):
                    row['light'][attribute] = _value(getattr(light, attribute))
            row['light']['node_tree'] = _node_tree(light.node_tree)
        if obj.type == 'MESH':
            row['geometry'] = [len(obj.data.vertices), len(obj.data.edges), len(obj.data.polygons)]
        if obj.type == 'CAMERA':
            row['camera'] = [obj.data.type, obj.data.lens, obj.data.ortho_scale,
                             obj.data.clip_start, obj.data.clip_end]
        if hasattr(obj, 'material_slots'):
            row['materials'] = [slot.material.name if slot.material else None for slot in obj.material_slots]
            for slot in obj.material_slots:
                if slot.material and slot.material.name not in materials:
                    m = slot.material
                    materials[m.name] = {'diffuse_color': list(m.diffuse_color),
                                         'use_nodes': m.use_nodes, 'node_tree': _node_tree(m.node_tree)}
        rows.append(row)
    record = {'scene': scene.name, 'objects': rows, 'materials': materials,
              'world': {'name': scene.world.name, 'tree': _node_tree(scene.world.node_tree)} if scene.world else None,
              'camera': scene.camera.name if scene.camera else None,
              'view': [scene.view_settings.view_transform, scene.view_settings.look,
                       scene.view_settings.exposure, scene.view_settings.gamma]}
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return {'sha256': hashlib.sha256(raw).hexdigest(),
            'object_count': len(rows), 'material_count': len(materials),
            'light_count': sum(o.type == 'LIGHT' for o in scene.objects)}


def _assets(scene):
    _activate(scene)
    return sorted([{'id': str(o['asset_id']), 'object': o.name,
                    'matrix_world': [list(v) for v in o.matrix_world]}
                   for o in scene.objects if o.get('asset_id')], key=lambda row: (row['id'], row['object']))


def _geometry_transforms(scene):
    _activate(scene)
    return {o.name: [list(v) for v in o.matrix_world]
            for o in scene.objects if o.type != 'LIGHT'}


def save_day_source_v9():
    before_file = _digest(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    day = bpy.data.scenes['ORIGINAL_DAY_V8']
    night = bpy.data.scenes['ORIGINAL_NIGHT_V8']
    source = bpy.data.scenes['ORBITAL_ATELIER_V2']
    original_scene_names = set(bpy.data.scenes.keys())
    night_before = _snapshot(night)
    source_before = _snapshot(source)
    day_assets = _assets(day)
    night_assets = _assets(night)
    source_assets = _assets(source)
    day_geometry = _geometry_transforms(day)

    path = ROOT / 'assets/blender/scripts/day_sunlight_v9.py'
    scope = {'__name__': 'editable_day_sunlight_v9'}
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), scope)
    _activate(day)
    daylight = scope['apply_day_sunlight'](day)
    day.name = 'ORIGINAL_DAY_V9'
    daylight['scene'] = day.name
    day['day_sunlight_v9_report'] = json.dumps(daylight)
    day['lighting_source_revision'] = 9

    if _assets(day) != day_assets:
        raise RuntimeError('Day asset IDs or world transforms changed.')
    if _assets(night) != night_assets or _assets(source) != source_assets:
        raise RuntimeError('Protected night/source asset IDs or transforms changed.')
    after_geometry = _geometry_transforms(day)
    if any(after_geometry.get(name) != matrix for name, matrix in day_geometry.items()):
        raise RuntimeError('An existing full-quality day object/camera transform changed.')
    night_after = _snapshot(night)
    source_after = _snapshot(source)
    if night_after != night_before:
        raise RuntimeError('Accepted night geometry/materials/lighting/world signature changed.')
    if source_after != source_before:
        raise RuntimeError('Original source scene signature changed.')
    required = original_scene_names - {'ORIGINAL_DAY_V8'}
    if not required.issubset(set(bpy.data.scenes.keys())):
        raise RuntimeError('An unrelated original scene was removed.')

    _activate(day)
    bpy.ops.wm.save_as_mainfile(filepath=str(DESTINATION), compress=True, check_existing=False)
    after_file = _digest(SOURCE)
    if before_file != after_file:
        raise RuntimeError('Protected V8 file changed on disk.')
    report = {
        'source': str(SOURCE), 'output': str(DESTINATION), 'bytes': DESTINATION.stat().st_size,
        'sha256': _digest(DESTINATION), 'source_sha256_before': before_file,
        'source_sha256_after': after_file, 'source_file_unchanged': True,
        'active_scene': day.name, 'night_scene': night.name,
        'daylight': daylight, 'day_asset_count': len(day_assets),
        'night_asset_count': len(night_assets), 'source_asset_count': len(source_assets),
        'all_asset_ids_and_world_transforms_unchanged': True,
        'existing_day_geometry_and_camera_transforms_unchanged': True,
        'night_before': night_before, 'night_after': night_after,
        'source_scene_before': source_before, 'source_scene_after': source_after,
        'accepted_night_scene_unchanged': True, 'original_source_scene_unchanged': True,
        'all_other_scenes_preserved': sorted(required), 'renders_executed': 0,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report
