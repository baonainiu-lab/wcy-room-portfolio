"""Export one hierarchy and embedded night maps; daylight shares its exact UVs."""
import bpy, json, struct, hashlib
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
TEXTURES = ROOT/'public/textures/lighting-v8'


def emission_material(name, image, uv_name=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emission = nt.nodes.new('ShaderNodeEmission')
    texture = nt.nodes.new('ShaderNodeTexImage')
    texture.image = image
    if uv_name:
        uv = nt.nodes.new('ShaderNodeUVMap')
        uv.uv_map = uv_name
        nt.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    nt.links.new(texture.outputs['Color'], emission.inputs['Color'])
    nt.links.new(emission.outputs[0], out.inputs['Surface'])
    return mat


def export(textures_directory=None, output_path=None, source_path=None, prepared_path=None, geometry_revision=8, lighting_revision=8):
    textures = Path(textures_directory) if textures_directory else TEXTURES
    scene = bpy.data.scenes['WEB_DUAL_V8']
    bpy.context.window.scene = scene
    baked_materials = []
    for atlas in range(8):
        for state in ('day', 'night'):
            if not (textures/f'{state}-{atlas}.png').exists():
                raise RuntimeError(f'Missing {state} bake {atlas}')
        image = bpy.data.images.load(str(textures/f'night-{atlas}.png'), check_existing=False)
        image.colorspace_settings.name = 'sRGB'
        baked_materials.append(emission_material(f'WEB8_LIGHTMAP_{atlas}', image, 'BakeUV'))
    window = bpy.data.images.load(str(textures/'window-night.png'), check_existing=False)
    window.colorspace_settings.name = 'sRGB'
    window_material = emission_material('WEB8_WINDOW_CITY', window)
    objects = [o for o in scene.objects if o.get('web_export')]
    for obj in objects:
        if obj.type != 'MESH':
            continue
        kind = obj.get('web_kind')
        if kind == 'baked':
            obj.data.materials.clear()
            obj.data.materials.append(baked_materials[int(obj['bake_atlas'])])
            for polygon in obj.data.polygons:
                polygon.material_index = 0
            for layer in list(obj.data.uv_layers):
                if layer.name != 'BakeUV':
                    obj.data.uv_layers.remove(layer)
            obj.data.uv_layers.active = obj.data.uv_layers['BakeUV']
        elif kind == 'image':
            for index, mat in enumerate(list(obj.data.materials)):
                if mat and mat.node_tree and any(n.type == 'TEX_IMAGE' and n.image and 'window-city' in n.image.name for n in mat.node_tree.nodes):
                    obj.data.materials[index] = window_material
        elif kind == 'glass':
            name = 'WEB8_CLEAR_'+(obj.data.materials[0].name if obj.data.materials else obj.name)
            mat = bpy.data.materials.new(name)
            mat.use_nodes = True
            p = mat.node_tree.nodes.get('Principled BSDF')
            p.inputs['Base Color'].default_value = (.55, .68, .74, 1)
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            for polygon in obj.data.polygons:
                polygon.material_index = 0
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.hide_render = False
        obj.select_set(True)
    path = Path(output_path) if output_path else ROOT/'public/models/orbital-atelier-v8.glb'
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_active_scene=True, use_selection=True,
        export_extras=True, export_yup=True, export_animations=False, export_lights=False, export_cameras=False,
        export_materials='EXPORT', export_copyright='Original Blender room, architecture, textures and dual lighting. Template Andrew Woan MIT.')
    data = path.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20+length])
    offset = 20+length
    blen = struct.unpack_from('<I', data, offset)[0]
    binary = data[offset+8:offset+8+blen]
    for mat in doc['materials']:
        pbr = mat.setdefault('pbrMetallicRoughness', {})
        if mat['name'].startswith('WEB8_CLEAR_'):
            alpha = .34 if 'Smoke_Glass' in mat['name'] else .13
            pbr.clear()
            pbr.update(baseColorFactor=[.69,.81,.86,alpha], metallicFactor=0, roughnessFactor=1)
            mat['alphaMode'] = 'BLEND'
        else:
            if 'emissiveTexture' in mat:
                pbr['baseColorTexture'] = mat.pop('emissiveTexture')
            pbr.update(baseColorFactor=[1,1,1,1], metallicFactor=0, roughnessFactor=1)
        mat.pop('emissiveFactor', None)
        mat.pop('normalTexture', None)
        mat.pop('occlusionTexture', None)
        mat['extensions'] = {'KHR_materials_unlit':{}}
        mat['doubleSided'] = True
    doc['extensionsUsed'] = sorted((set(doc.get('extensionsUsed',[])) - {'KHR_materials_emissive_strength'}) | {'KHR_materials_unlit'})
    doc.pop('extensionsRequired', None)
    for item in doc.get('scenes',[]):
        item.setdefault('extras',{}).update(web_baked=True, source_revision=geometry_revision, lighting_revision=lighting_revision, bake_mode='cycles_dual_day_night_agx')
    raw = json.dumps(doc,separators=(',',':')).encode()
    raw += b' '*(-len(raw)%4)
    blob = struct.pack('<III',0x46546C67,2,28+len(raw)+len(binary))+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(binary),0x004E4942)+binary
    path.write_bytes(blob)
    report = {
        'model':str(path.relative_to(ROOT)), 'source':source_path or 'assets/blender/orbital-atelier-v8.blend',
        'prepared':prepared_path or 'assets/blender/orbital-dual-bake-v8.blend', 'lightingRevision':lighting_revision,
        'triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),
        'drawPrimitives':sum(len(m['primitives']) for m in doc['meshes']),
        'materials':[m['name'] for m in doc['materials']], 'bytes':len(blob), 'sha256':hashlib.sha256(blob).hexdigest(),
        'componentIds':[o.get('asset_id') for o in objects if o.get('asset_id')],
        'bakedStates':['day','night'], 'atlasSizes':[4096]*6+[3072,2048], 'samples':40,
        'color':'Cycles combined direct, indirect, diffuse, glossy and emission; AgX baked to sRGB, browser NoToneMapping',
    }
    (ROOT/'assets/blender'/f'dual-lighting-v{geometry_revision}-export-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
