"""Prepare a disposable, independently interactive V8 room for two light bakes.

Open orbital-atelier-v8-interior.blend before calling prepare(). This script only snapshots,
optimizes and unwraps geometry. It does not bake or modify the editable source
scene. The prepared .blend is the reusable input for both day and night passes.
"""
import json
import math
import time
from pathlib import Path

import bpy


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SCENE_NAME = 'WEB_DUAL_V8'
ATLAS_SPECS = (
    ('architecture', 4096),
    ('furniture', 4096),
    ('original_props', 4096),
    ('window_collectibles', 4096),
    ('interior_enrichment', 4096),
    ('exterior_dock', 4096),
    ('warm_gallery', 3072),
    ('high_resolution_lounge', 2048),
)
ADDITION_ATLASES = {
    'ENRICHMENT_V5': 4,
    'INTERIOR_WARM_V8': 4,
    'EXTERIOR_DOCK_V6': 5,
    'WARM_GALLERY_V7': 6,
}


def _properties(source, target):
    for key in source.keys():
        if key != '_RNA_UI':
            try:
                target[key] = source[key]
            except TypeError:
                pass


def _triangles(obj):
    return sum(max(0, len(face.vertices) - 2) for face in obj.data.polygons)


def _owner(obj):
    parent = obj.parent
    while parent and not parent.get('asset_id'):
        parent = parent.parent
    return parent


def _root(obj):
    while obj.parent:
        obj = obj.parent
    return obj


def _kind(obj):
    # Image artwork stays on its original UV and dedicated high-resolution map.
    # Glass stays a distinct primitive so the web exporter can use alpha blend.
    for material in obj.data.materials:
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        if any(n.type == 'EMISSION' for n in nodes) and any(n.type == 'TEX_IMAGE' for n in nodes):
            return 'image'
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                transmission = node.inputs.get('Transmission Weight')
                if transmission and transmission.default_value > 0:
                    return 'glass'
    return 'baked'


def _atlas(obj):
    for name in json.loads(obj.get('source_collections_json', '[]')):
        if name in ADDITION_ATLASES:
            return ADDITION_ATLASES[name]
    root = _root(obj)
    asset_id = root.get('asset_id', '')
    if asset_id == 'environment.warm_gallery':
        return 6
    if asset_id == 'environment.orbital_dock':
        return 5
    if asset_id.startswith('v5_'):
        return 4
    if asset_id == 'furniture.lounge':
        return 7
    if asset_id.startswith('furniture.'):
        return 1
    if root.get('source_node', '').startswith('D_'):
        return 3
    if asset_id.startswith('architecture.') or not asset_id:
        return 0
    return 2


def _triangle_budget(asset_id, atlas, kind, count):
    # V5-V7 already use purpose-built lightweight geometry. The orange lounge
    # deliberately retains its source silhouette; previous decimation cracked it.
    if atlas >= 4 or kind == 'image':
        return count
    budget = 2500
    if asset_id == 'room_static':
        budget = 18000
    elif asset_id == 'furniture.work_chair':
        budget = 8000
    elif asset_id == 'trailing_wall_plant':
        budget = 9500
    elif asset_id == 'glass_bonsai_terrarium':
        budget = 7000
    elif asset_id in {'ceramic_mobius_form', 'furniture.desk', 'furniture.coffee_table'}:
        budget = 4500
    elif asset_id.startswith(('terminal_panel', 'communicator_panel')):
        budget = 1800
    elif asset_id.startswith('furniture.'):
        budget = 3500
    elif asset_id.startswith(('small_planter_leaf', 'floor_vase_leaf')):
        budget = 180
    return min(2500, budget) if kind == 'glass' else budget


def _isolated_material(old, key, cache):
    cache_key = (key, old.name)
    if cache_key in cache:
        return cache[cache_key]
    material = old.copy()
    material.name = 'WEB8_' + key + '_' + old.name
    material['source_material'] = old.name
    cache[cache_key] = material
    if not material.use_nodes:
        return material
    tree = material.node_tree
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.name = 'WEB8_ORIGINAL_UV'
    uv.uv_map = 'UVMap'
    for node in list(tree.nodes):
        if node.type == 'TEX_COORD':
            for link in list(node.outputs['UV'].links):
                tree.links.new(uv.outputs['UV'], link.to_socket)
        elif node.type == 'TEX_IMAGE' and not node.inputs['Vector'].is_linked:
            tree.links.new(uv.outputs['UV'], node.inputs['Vector'])
        elif node.type == 'BSDF_PRINCIPLED':
            # Texture-driven micro-bump is too fine for these UV atlases and
            # creates dark seam fragments. Geometry still supplies the normals.
            for link in list(node.inputs['Normal'].links):
                tree.links.remove(link)
    return material


def prepare(output_path=None, report_path=None, source_label='assets/blender/orbital-atelier-v8-interior.blend', revision=8, precision_budgets=None, atlas_uv_transform=None):
    started = time.monotonic()
    source = bpy.data.scenes.get('ORBITAL_ATELIER_V2')
    if source is None:
        raise RuntimeError('Open orbital-atelier-v8-interior.blend: ORBITAL_ATELIER_V2 is required.')
    missing = [name for name in ADDITION_ATLASES if bpy.data.collections.get(name) is None]
    if missing:
        raise RuntimeError('The V7 source is incomplete: missing ' + ', '.join(missing))
    if bpy.data.scenes.get(SCENE_NAME):
        raise RuntimeError('WEB_DUAL_V8 already exists. Reopen the V7 source to prepare a fresh copy.')
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    scene = bpy.data.scenes.new(SCENE_NAME)
    scene.world = source.world.copy() if source.world else None
    if scene.world:
        scene.world.name = 'WEB8_WORLD'
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .055
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 4
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = .1
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = 'EXTEND'
    scene.render.bake.use_clear = True
    scene.render.resolution_x = source.render.resolution_x
    scene.render.resolution_y = source.render.resolution_y
    scene.render.resolution_percentage = source.render.resolution_percentage
    scene.render.film_transparent = source.render.film_transparent
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    try:
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'METAL'
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == 'METAL'
        scene.cycles.device = 'GPU' if any(d.type == 'METAL' for d in preferences.devices) else 'CPU'
    except Exception:
        scene.cycles.device = 'CPU'

    copies, geometry, context = {}, [], []
    # Finish every evaluated snapshot before any joins/deletions. Invalidating
    # the source depsgraph midway through that process has crashed Blender before.
    for old in list(source.objects):
        is_context = old.type in {'LIGHT', 'CAMERA'} or any(c.name == 'STUDIO_NON_EXPORT' for c in old.users_collection)
        if old.type not in {'MESH', 'CURVE', 'FONT', 'EMPTY', 'LIGHT', 'CAMERA'}:
            continue
        if old.hide_render and old.type != 'EMPTY':
            continue
        if old.type == 'EMPTY':
            new = bpy.data.objects.new('WEB8_' + old.name, None)
            new.empty_display_type = old.empty_display_type
            new.empty_display_size = old.empty_display_size
        elif old.type in {'LIGHT', 'CAMERA'}:
            new = bpy.data.objects.new('WEB8_' + old.name, old.data.copy())
        else:
            mesh = bpy.data.meshes.new_from_object(old.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
            if not len(mesh.vertices):
                bpy.data.meshes.remove(mesh)
                continue
            new = bpy.data.objects.new('WEB8_' + old.name, mesh)
            if not is_context:
                geometry.append(new)
        scene.collection.objects.link(new)
        new.matrix_world = old.matrix_world.copy()
        _properties(old, new)
        new['source_node'] = old.name
        new['source_collections_json'] = json.dumps([c.name for c in old.users_collection])
        new['web_export'] = not is_context
        if is_context:
            new['web_context'] = True
            if old.type == 'LIGHT':
                new['v8_original_light_name'] = old.name
                new['v8_original_light_energy'] = old.data.energy
            context.append(new)
        copies[old] = new

    bpy.context.window.scene = scene
    for old, new in copies.items():
        parent = old.parent
        while parent and parent not in copies:
            parent = parent.parent
        if parent:
            world = new.matrix_world.copy()
            new.parent = copies[parent]
            new.matrix_world = world
    scene.camera = copies.get(source.camera)
    bpy.context.view_layer.update()

    materials = {}
    for obj in context:
        if obj.type != 'MESH':
            continue
        for index, old in enumerate(list(obj.data.materials)):
            if old:
                obj.data.materials[index] = _isolated_material(old, 'CONTEXT', materials)

    buckets = {}
    for obj in geometry:
        owner, kind, atlas = _owner(obj), _kind(obj), _atlas(obj)
        # Keep different artwork materials separate, avoiding multi-material
        # image buckets and retaining an explicit window/screen identity.
        image_key = tuple(m.name if m else '' for m in obj.data.materials) if kind == 'image' else ()
        buckets.setdefault((owner, kind, atlas, image_key), []).append(obj)

    meshes = []
    for (owner, kind, atlas, _), parts in buckets.items():
        bpy.ops.object.select_all(action='DESELECT')
        for part in parts:
            part.hide_set(False)
            part.select_set(True)
        active = parts[0]
        bpy.context.view_layer.objects.active = active
        if len(parts) > 1:
            bpy.ops.object.join()
        world = active.matrix_world.copy()
        active.parent = owner
        active.matrix_world = world
        asset_id = owner.get('asset_id', 'room_static') if owner else 'room_static'
        active.name = 'WEB8_' + asset_id + '__' + kind + '__A' + str(atlas)
        active['owner_asset_id'] = asset_id
        active['web_kind'] = kind
        active['bake_atlas'] = atlas if kind == 'baked' else -1
        active['geometry_atlas'] = atlas
        active['web_export'] = True
        count = _triangles(active)
        budget = _triangle_budget(asset_id, atlas, kind, count)
        # A measured quality profile may protect an owner without combining its
        # independent interaction group. None means retain evaluated geometry.
        if precision_budgets and kind == 'baked' and asset_id in precision_budgets:
            override = precision_budgets[asset_id]
            budget = count if override is None else max(budget, override)
        if count > budget * 1.08:
            modifier = active.modifiers.new('Web silhouette budget', 'DECIMATE')
            modifier.ratio = budget / count
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        active.data.validate(clean_customdata=True)
        active.data.update()
        active['triangles_before'] = count
        for index, old in enumerate(list(active.data.materials)):
            if old:
                key = 'BAKE_A' + str(atlas) if kind == 'baked' else kind.upper()
                active.data.materials[index] = _isolated_material(old, key, materials)
        meshes.append(active)

    atlas_reports = []
    for atlas, (label, size) in enumerate(ATLAS_SPECS):
        group = [obj for obj in meshes if obj.get('bake_atlas') == atlas]
        if not group:
            raise RuntimeError('Atlas is unexpectedly empty: ' + label)
        for obj in group:
            # Existing source maps remain UVMap. Only the new BakeUV is active
            # for baking; texture nodes explicitly reference the source UVMap.
            previous = obj.data.uv_layers.get('BakeUV')
            if previous:
                obj.data.uv_layers.remove(previous)
            layer = obj.data.uv_layers.new(name='BakeUV')
            obj.data.uv_layers.active = layer
            layer.active_render = True
        bpy.ops.object.select_all(action='DESELECT')
        for obj in group:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = group[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(75 if atlas == 7 else 66),
            island_margin=.01 if atlas == 7 else .003,
            area_weight=.5 if atlas == 7 else .25,
            correct_aspect=True,
            scale_to_bounds=True,
        )
        bpy.ops.object.mode_set(mode='OBJECT')
        uv_refinement = atlas_uv_transform(atlas, group, size) if atlas_uv_transform else None
        image = bpy.data.images.new('WEB8_ATLAS_' + str(atlas), width=size, height=size, alpha=False, float_buffer=True)
        image.colorspace_settings.name = 'Linear Rec.709'
        atlas_materials = {m for obj in group for m in obj.data.materials if m is not None}
        for material in atlas_materials:
            material.use_nodes = True
            material['bake_atlas'] = atlas
            tree = material.node_tree
            for node in tree.nodes:
                node.select = False
            target = tree.nodes.new('ShaderNodeTexImage')
            target.name = 'WEB8_BAKE_TARGET'
            target.label = 'V8 shared UV day/night bake destination'
            target.image = image
            target.select = True
            tree.nodes.active = target
        atlas_reports.append({
            'id': atlas, 'label': label, 'resolution': size,
            'image': image.name, 'uv_layer': 'BakeUV',
            'margin': 32 if atlas == 7 else 16,
            'mesh_count': len(group), 'triangles': sum(_triangles(obj) for obj in group),
            'meshes': [obj.name for obj in group],
            'material_names': sorted(m.name for m in atlas_materials),
            'owner_ids': sorted({obj['owner_asset_id'] for obj in group}),
            'uv_refinement': uv_refinement,
        })

    export_objects = [obj for obj in scene.objects if obj.get('web_export')]
    id_objects = [obj for obj in export_objects if obj.get('asset_id')]
    ids = [obj['asset_id'] for obj in id_objects]
    if len(ids) != len(set(ids)):
        raise RuntimeError('Duplicate independently interactive asset IDs in prepared scene.')
    interior = [obj for obj in id_objects if not obj['asset_id'].startswith('environment.')]
    roots = [obj for obj in interior if not any(p.get('asset_id') for p in _parents(obj))]
    if len(interior) != 93 or len(roots) != 37:
        raise RuntimeError(f'Expected 37 interior roots / 93 IDs, got {len(roots)} / {len(interior)}.')
    scene['web_baked'] = False
    scene['dual_lighting_prepared'] = True
    scene['source_revision'] = revision
    scene['source_blend'] = source_label
    scene['bake_mode'] = 'cycles_combined_dual_lighting_agx'
    output = Path(output_path) if output_path else ROOT / 'assets/blender/orbital-dual-bake-v8.blend'
    report = {
        'source': source_label,
        'prepared': str(output.relative_to(ROOT)), 'scene': scene.name,
        'atlas_count': len(atlas_reports), 'atlases': atlas_reports,
        'mesh_count': len(meshes), 'triangles': sum(_triangles(obj) for obj in meshes),
        'precision_budgets': precision_budgets or {},
        'triangles_before': sum(obj['triangles_before'] for obj in meshes),
        'interior_root_count': len(roots), 'interior_id_count': len(interior),
        'interior_roots': [obj['asset_id'] for obj in roots],
        'asset_ids': sorted(ids),
        'exterior_ids': sorted(obj['asset_id'] for obj in id_objects if obj['asset_id'].startswith('environment.')),
        'dedicated_materials': sorted({m.name for obj in meshes if obj['web_kind'] == 'image' for m in obj.data.materials if m}),
        'glass_materials': sorted({m.name for obj in meshes if obj['web_kind'] == 'glass' for m in obj.data.materials if m}),
        'context_objects': [obj.name for obj in context],
        'seconds': round(time.monotonic() - started, 2),
        'blender_device': scene.cycles.device,
    }
    scene['preparation_manifest'] = json.dumps(report, ensure_ascii=False)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    report_path = Path(report_path) if report_path else ROOT / 'assets/blender/dual-bake-v8-preparation.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def _parents(obj):
    while obj.parent:
        obj = obj.parent
        yield obj


if __name__ == '__main__':
    result = prepare()
