"""Export only the approved source atelier architecture in BACKGROUND Blender.

Run: Blender -b --python assets/blender/scripts/about_atelier_v3/architecture_export.py
The editable .blend remains read-only. Runtime framing must use the main model.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import web_export as W

ROOT = W.ROOT
SOURCE = ROOT / 'assets/blender/about-atelier-v3-architecture-v2.blend'
OUTPUT = ROOT / 'public/models/about-atelier-v3-architecture.glb'
TEXTURE = ROOT / 'public/textures/about-atelier-v3/architecture/day.png'
REPORT = ROOT / 'assets/blender/about-atelier-v3-web/architecture-export-report.json'
PREFIX_COUNTS = {
    'context.limestone.tile': 20,
    'context.window.pier': 3,
    'context.window.mullion': 5,
    'context.window.horizontal': 2,
    'context.window.glazing': 4,
    'context.side.mullion': 5,
    'context.side.glazing': 4,
}


def prefix_of(name):
    return next((p for p in PREFIX_COUNTS if name == p or name.startswith(p + '.')), None)


def bounds(objects):
    vertices = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    return {'min': [min(v[i] for v in vertices) for i in range(3)],
            'max': [max(v[i] for v in vertices) for i in range(3)]}


def main():
    assert bpy.app.background, 'Never run this script in the interactive Blender session.'
    started = time.monotonic()
    source_hash = W.sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    source = bpy.context.scene
    architecture_collection = bpy.data.collections['90_RENDER_Atrium_Lake']
    selected = [o for o in architecture_collection.all_objects if prefix_of(o.name) or o.get('architecture_export')]
    counts = {p: sum(prefix_of(o.name) == p for o in selected) for p in PREFIX_COUNTS}
    assert counts == PREFIX_COUNTS, counts
    counts['context.arch.additions'] = sum(o.name.startswith('context.arch.') for o in selected)
    assert all(o.type == 'MESH' for o in selected)
    source_nodes = sorted(o.name for o in selected)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    scene = bpy.data.scenes.new('WEB_ABOUT_ATELIER_ARCHITECTURE')
    scene.world = source.world.copy()
    scene.render.engine = 'CYCLES'
    for key in ('view_transform', 'look', 'exposure', 'gamma'):
        setattr(scene.view_settings, key, getattr(source.view_settings, key))
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.cycles.samples = 32
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .035
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 8
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 6
    root = bpy.data.objects.new('ATELIER_ARCHITECTURE', None)
    scene.collection.objects.link(root)
    root['interactive'] = False
    root['architecture'] = True
    root['excludeFromFraming'] = True
    root['source'] = W.rel(SOURCE)
    root['sourceSha256'] = source_hash
    root['architectureRevision'] = source.get('architecture_revision', 'Original architecture')

    opaque, glazing, material_cache = [], [], {}
    material_sources = {}
    for old in selected:
        mesh = bpy.data.meshes.new_from_object(old.evaluated_get(dg),
                                             preserve_all_data_layers=True, depsgraph=dg)
        W.attrs(mesh)
        mesh.transform(old.matrix_world)
        mesh.update()
        is_glass = 'glazing' in old.name
        ob = bpy.data.objects.new(('ATELIER_ARCH_GLASS_' if is_glass else 'ATELIER_ARCH_PART_') + old.name, mesh)
        scene.collection.objects.link(ob)
        ob['source_node'] = old.name
        ob['interactive'] = False
        ob['excludeFromFraming'] = True
        ob.visible_shadow = old.visible_shadow
        for i, material in enumerate(list(mesh.materials)):
            material_sources[material.name] = {
                'name': material.name,
                'kind': 'PBR glass' if is_glass else 'source procedural surface',
                'images': sorted({n.image.name for n in material.node_tree.nodes
                                  if n.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} and n.image}),
            }
            if not is_glass:
                mesh.materials[i] = W.frozen_material(material, 9, material_cache)
        (glazing if is_glass else opaque).append(ob)

    # Original furniture and lights still cast their source shadows during the
    # offline bake. These objects are never selected for architecture export.
    context_nodes = []
    excluded_decor = set(architecture_collection.all_objects) - set(selected)
    for old in source.objects:
        if old not in selected and old not in excluded_decor and old.type != 'CAMERA':
            scene.collection.objects.link(old)
            context_nodes.append(old.name)
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    original_bounds = bounds(opaque + glazing)
    floor_bounds = bounds([o for o in opaque if prefix_of(o['source_node']) == 'context.limestone.tile'])
    bpy.ops.object.select_all(action='DESELECT')
    for ob in opaque:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = opaque[0]
    bpy.ops.object.join()
    opaque = bpy.context.object
    opaque.name = 'ATELIER_ARCH_OPAQUE'
    opaque['source_nodes'] = json.dumps([n for n in source_nodes if 'glazing' not in n])
    del opaque['source_node']
    uv = opaque.data.uv_layers.new(name='BakeUV', do_init=False)
    opaque.data.uv_layers.active = uv
    uv.active_render = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.0025,
                             area_weight=.25, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    image = bpy.data.images.new('ATELIER_ARCH_DAYLIGHT', width=4096, height=4096,
                                alpha=False, float_buffer=True)
    image.colorspace_settings.name = 'Linear Rec.709'
    for material in opaque.data.materials:
        for node in material.node_tree.nodes:
            node.select = False
        node = material.node_tree.nodes.new('ShaderNodeTexImage')
        node.name = W.TARGET
        node.image = image
        node.select = True
        material.node_tree.nodes.active = node
    device = W.device(scene)
    print('ATELIER_ARCH_BAKE_START', json.dumps({'device': device, 'sourceNodes': counts,
          'boundsBlender': original_bounds, 'floorBoundsBlender': floor_bounds}), flush=True)
    bake_started = time.monotonic()
    bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'COLOR', 'DIFFUSE', 'GLOSSY', 'EMIT'},
                        uv_layer='BakeUV', margin=16, use_clear=True, use_selected_to_active=False)
    TEXTURE.parent.mkdir(parents=True, exist_ok=True)
    image.save_render(str(TEXTURE), scene=scene)
    bake_seconds = round(time.monotonic() - bake_started, 2)
    print('ATELIER_ARCH_BAKE_DONE', bake_seconds, W.sha(TEXTURE), flush=True)

    baked = bpy.data.materials.new('ATELIER_ARCH_LIGHTMAP')
    baked.use_nodes = True
    baked.node_tree.nodes.clear()
    nodes, links = baked.node_tree.nodes, baked.node_tree.links
    out, emission, texture, uv_node = (nodes.new(n) for n in
        ('ShaderNodeOutputMaterial', 'ShaderNodeEmission', 'ShaderNodeTexImage', 'ShaderNodeUVMap'))
    texture.image = bpy.data.images.load(str(TEXTURE))
    texture.image.colorspace_settings.name = 'sRGB'
    uv_node.uv_map = 'BakeUV'
    links.new(uv_node.outputs[0], texture.inputs['Vector'])
    links.new(texture.outputs['Color'], emission.inputs['Color'])
    links.new(emission.outputs[0], out.inputs[0])
    opaque.data.materials.clear()
    opaque.data.materials.append(baked)

    glass = bpy.data.materials.new('ATELIER_ARCH_GLASS')
    glass.use_nodes = True
    original_glass = W.principle(glazing[0].data.materials[0])
    pbr = W.principle(glass)
    for name in ('Base Color', 'Metallic', 'Roughness', 'Transmission Weight', 'IOR'):
        pbr.inputs[name].default_value = original_glass.inputs[name].default_value
    pbr.inputs['Roughness'].default_value = .055
    for ob in glazing:
        ob.data.materials.clear()
        ob.data.materials.append(glass)
    # Selection flags are stored per source view layer. Restrict the export
    # scene itself as well, so a source-scene selected rug cannot leak into GLB.
    for name in context_nodes:
        scene.collection.objects.unlink(bpy.data.objects[name])
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for ob in [opaque] + glazing:
        W.reparent(ob, root)
        ob.select_set(True)
        for polygon in ob.data.polygons:
            polygon.material_index = 0
        for attribute in list(ob.data.attributes):
            if attribute.name in {W.POS, W.NORMAL}:
                ob.data.attributes.remove(attribute)
        for uv in list(ob.data.uv_layers):
            if ob == opaque and uv.name == 'BakeUV':
                continue
            ob.data.uv_layers.remove(uv)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pending = OUTPUT.with_name('.about-atelier-v3-architecture.pending.glb')
    bpy.ops.export_scene.gltf(filepath=str(pending), export_format='GLB', use_selection=True, use_active_scene=True,
        export_extras=True, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_normals=True, export_texcoords=True)
    blob = pending.read_bytes()
    json_length, json_type = struct.unpack_from('<II', blob, 12)
    document = json.loads(blob[20:20 + json_length])
    remaining = blob[20 + json_length:]
    for material in document['materials']:
        if material['name'] == 'ATELIER_ARCH_LIGHTMAP':
            binding = material.get('pbrMetallicRoughness', {}).get('baseColorTexture') or material['emissiveTexture']
            material['pbrMetallicRoughness'] = {'baseColorTexture': binding,
                'baseColorFactor': [1, 1, 1, 1], 'metallicFactor': 0, 'roughnessFactor': 1}
            for key in ('emissiveTexture', 'emissiveFactor', 'normalTexture', 'occlusionTexture'):
                material.pop(key, None)
            material['extensions'] = {'KHR_materials_unlit': {}}
            material['doubleSided'] = True
        elif material['name'] == 'ATELIER_ARCH_GLASS':
            material['doubleSided'] = True
    for key in ('extensionsUsed', 'extensionsRequired'):
        if 'KHR_materials_unlit' not in document.setdefault(key, []):
            document[key].append('KHR_materials_unlit')
    document['asset']['extras'] = {'source': W.rel(SOURCE), 'sourceSha256': source_hash,
        'sourceCollection': architecture_collection.name, 'sourceNodes': source_nodes,
        'architectureRevision': source.get('architecture_revision', 'Original architecture'),
        'bake': 'Daylight Cycles COMBINED; AgX; 32 samples; 4096x4096; source furniture retained as occluders',
        'architectureOnly': True, 'assetCount': 0, 'excludeFromFraming': True}
    serialized = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode()
    serialized += b' ' * (-len(serialized) % 4)
    pending.write_bytes(struct.pack('<III', 0x46546c67, 2, 20 + len(serialized) + len(remaining)) +
                        struct.pack('<II', len(serialized), json_type) + serialized + remaining)
    assert W.sha(SOURCE) == source_hash, 'The editable source changed during export.'
    assert not any('asset_id' in n.get('extras', {}) for n in document['nodes'])
    assert len(document['nodes']) == 10
    assert len(document['meshes']) == 9
    assert {m['name'] for m in document['materials']} == {'ATELIER_ARCH_LIGHTMAP', 'ATELIER_ARCH_GLASS'}
    assert len(document['images']) == 1
    assert bounds([opaque] + glazing) == original_bounds
    pending.replace(OUTPUT)
    b = original_bounds
    gltf_bounds = {'min': [b['min'][0], b['min'][2], -b['max'][1]],
                   'max': [b['max'][0], b['max'][2], -b['min'][1]]}
    report = {'complete': True, 'source': W.rel(SOURCE), 'sourceSha256': source_hash,
        'sourceFileUnchanged': True, 'sourceCollection': architecture_collection.name,
        'architectureRevision': source.get('architecture_revision', 'Original architecture'),
        'originalSource': source.get('architecture_original_source', W.rel(W.SOURCE)),
        'originalSourceSha256': source.get('architecture_original_sha256', W.sha(W.SOURCE)),
        'mainGeometryHierarchyTransformsSignature': source.get('architecture_main_signature', ''),
        'sourceNodes': source_nodes, 'sourceNodeCounts': counts,
        'excludedExport': 'All plants, bench, rugs, furnishings, cameras, lights and landscape geometry',
        'excludedFromBakeAsWell': sorted(o.name for o in excluded_decor),
        'decorRemovedFromDerivativeSource': json.loads(source.get('architecture_removed_decor', '[]')),
        'contextObjectsRetainedForBakeOnly': sorted(context_nodes),
        'boundsBlender': original_bounds, 'floorBoundsBlender': floor_bounds, 'boundsGltf': gltf_bounds,
        'model': W.rel(OUTPUT), 'bytes': OUTPUT.stat().st_size, 'sha256': W.sha(OUTPUT),
        'nodes': len(document['nodes']), 'meshes': len(document['meshes']), 'opaqueMeshes': 1,
        'glassMeshes': 8, 'assetCount': 0, 'triangles': sum(W.triangles(o) for o in [opaque] + glazing),
        'materials': [m['name'] for m in document['materials']],
        'bake': {'type': 'COMBINED', 'samples': 32, 'device': device, 'seconds': bake_seconds,
            'resolution': [4096, 4096], 'colourTransform': scene.view_settings.view_transform,
            'path': W.rel(TEXTURE), 'sha256': W.sha(TEXTURE), 'bytes': TEXTURE.stat().st_size,
            'sourceCoordinatePreservation': 'web_export.attrs and frozen_material preserve local positions and split normals before world transforms and mesh joins'},
        'textureProvenance': {'architectureMaterials': list(material_sources.values()),
            'lighting': 'Existing source CC0 Poly Haven lake_pier_2k.hdr',
            'manifest': 'assets/textures/about-atelier-v3/landscape/manifest.json',
            'newThirdPartyTextures': [], 'fabricAddedToArchitecture': False},
        'runtimeContract': {'units': 'metres', 'sourceToGltf': '(x,y,z) -> (x,z,-y)',
            'root': 'ATELIER_ARCHITECTURE', 'parent': 'About atelier scene root beside the main model',
            'framing': 'Use original main model bounds only; exclude the entire architecture root',
            'interaction': 'Noninteractive background; contributes no asset_id and none of the 128 assets',
            'opaque': 'ATELIER_ARCH_LIGHTMAP; KHR_materials_unlit; toneMapped=false',
            'glass': 'ATELIER_ARCH_GLASS; original PBR transmission and IOR; eight separate panes; runtime optimized transparency permitted'},
        'seconds': round(time.monotonic() - started, 2)}
    W.write_json(REPORT, report)
    print('ATELIER_ARCH_EXPORT_DONE', json.dumps({k: report[k] for k in
        ('model', 'bytes', 'sha256', 'meshes', 'triangles', 'seconds')}), flush=True)


if __name__ == '__main__':
    main()
