"""Bake only the V5 additions in the original room's light, preserving V4.

Run using Blender MCP's background tool with orbital-atelier-v2.blend.
Writes a new editable source and a lightweight independent GLB layer.
"""
import bpy, json, math, struct, hashlib, time
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
spec = globals().get('BAKE_SPEC', {
    'revision':5, 'script':'enrich_room_v5.py', 'collection':'ENRICHMENT_V5',
    'source':'orbital-atelier-v5.blend', 'scene':'WEB_ENRICHMENT_V5',
    'model':'orbital-enrichment-v5.glb', 'texture':'room-enrichment-v5.png',
    'record':'enrichment-v5',
})
started = time.monotonic()
source = bpy.data.scenes['ORBITAL_ATELIER_V2']
bpy.context.window.scene = source
namespace = {'__name__': 'enrichment_v5'}
exec(compile((ROOT/'assets/blender/scripts'/spec['script']).read_text(), 'enrich_room_v5.py', 'exec'), namespace)
addition_report = namespace['build'](consolidate=False)
(ROOT/'assets/blender'/(spec['record']+'-manifest.json')).write_text(json.dumps(addition_report, ensure_ascii=False, indent=2)+'\n')
collection = bpy.data.collections[spec['collection']]
if spec['revision'] == 7:
    from mathutils import Vector
    # These lights are baked in Blender; no additional realtime light passes
    # are required by the browser. The source .blend retains the real fixtures.
    lighting = bpy.data.collections.new('WARM_GALLERY_LIGHTING_V7')
    source.collection.children.link(lighting)
    for index, lamp in enumerate(addition_report.get('warm_light_sources', [])):
        target = lamp.get('target')
        is_area = lamp.get('type', 'area' if target else 'point') == 'area'
        data = bpy.data.lights.new('Gallery warm practical '+str(index), 'AREA' if is_area else 'POINT')
        shade = lamp.get('color', '#ffb368').lstrip('#')
        rgb = [int(shade[i:i+2],16)/255 for i in (0,2,4)]
        data.color = tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in rgb)
        data.energy = lamp.get('energy', 180 if target else 65)
        if is_area:
            data.shape = 'RECTANGLE'
            data.size = lamp.get('width', 1.5)
            data.size_y = lamp.get('height', 1.0)
        else:
            data.shadow_soft_size = .35
        obj = bpy.data.objects.new(data.name, data)
        lighting.objects.link(obj)
        obj.location = lamp['position']
        if is_area and target:
            obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
        elif not is_area:
            # The point represents the diffuser's outward light, not a bulb
            # buried inside its opaque metal/ceramic proxy.
            outward = Vector((-obj.location.x, -obj.location.y, -.2)).normalized()
            obj.location += outward * .23
if spec['revision'] >= 6:
    # The old photographic stage sat immediately below the room. The new berth
    # has a real lower deck and stairs, so move the stage below their foundations.
    stage = source.objects.get('STUDIO_Ground')
    if stage:
        stage.location.z = -1.08
    import bmesh
    for obj in collection.all_objects:
        if obj.type != 'MESH':
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
    bpy.context.view_layer.update()
source['enrichment_revision'] = spec['revision']
blend_path = ROOT/'assets/blender'/spec['source']
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

scene = bpy.data.scenes.new(spec['scene'])
scene.world = source.world
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
preferences = bpy.context.preferences.addons['cycles'].preferences
try:
    preferences.compute_device_type = 'METAL'
    preferences.get_devices()
    for device in preferences.devices:
        device.use = device.type == 'METAL'
    scene.cycles.device = 'GPU' if any(d.type == 'METAL' for d in preferences.devices) else 'CPU'
except Exception:
    scene.cycles.device = 'CPU'

dg = bpy.context.evaluated_depsgraph_get()
new_source = set(collection.all_objects)
copies, geometry = {}, []
for old in source.objects:
    if old not in new_source:
        scene.collection.objects.link(old)
        continue
    if old.type == 'EMPTY':
        new = bpy.data.objects.new(old.name+'__web', None)
    elif old.type in {'MESH', 'CURVE', 'FONT'}:
        mesh = bpy.data.meshes.new_from_object(old.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        new = bpy.data.objects.new(old.name+'__web', mesh)
        geometry.append(new)
    else:
        continue
    scene.collection.objects.link(new)
    new.matrix_world = old.matrix_world.copy()
    for key in old.keys():
        if key != '_RNA_UI':
            new[key] = old[key]
    copies[old] = new
bpy.context.window.scene = scene
for old, new in copies.items():
    if old.parent in copies:
        transform = new.matrix_world.copy()
        new.parent = copies[old.parent]
        new.matrix_world = transform
bpy.context.view_layer.update()

# One mesh per independently interactive component, one shared atlas.
buckets = {}
for obj in geometry:
    owner = obj.parent
    while owner and not owner.get('asset_id'):
        owner = owner.parent
    buckets.setdefault(owner, []).append(obj)
meshes = []
for owner, parts in buckets.items():
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = owner.get('asset_id', 'v5_prop')+'__baked'
    obj.data.validate(clean_customdata=True)
    obj.data.update()
    obj['web_addition'] = True
    meshes.append(obj)

atlas_size = spec.get('atlas',4096)
image = bpy.data.images.new('V5_ADDITIONS_LIGHTING', width=atlas_size, height=atlas_size, alpha=False, float_buffer=True)
image.colorspace_settings.name = 'Linear Rec.709'
material_copies = {}
for obj in meshes:
    for index, old in enumerate(list(obj.data.materials)):
        if not old:
            continue
        if old not in material_copies:
            material = old.copy()
            material.name = 'V5_BAKE_'+old.name
            material.use_nodes = True
            nt = material.node_tree
            # Independent UV coordinates prevent the atlas from changing any
            # existing material texture layout; smooth normals avoid bake seams.
            uv = nt.nodes.new('ShaderNodeUVMap')
            uv.uv_map = 'UVMap'
            for node in list(nt.nodes):
                if node.type == 'TEX_IMAGE' and not node.inputs['Vector'].is_linked:
                    nt.links.new(uv.outputs['UV'], node.inputs['Vector'])
                if node.type == 'BSDF_PRINCIPLED':
                    for link in list(node.inputs['Normal'].links):
                        nt.links.remove(link)
            target = nt.nodes.new('ShaderNodeTexImage')
            target.image = image
            target.name = 'V5_BAKE_TARGET'
            nt.nodes.active = target
            material_copies[old] = material
        obj.data.materials[index] = material_copies[old]
    layer = obj.data.uv_layers.new(name='BakeUV')
    obj.data.uv_layers.active = layer
    layer.active_render = True

bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.003, area_weight=.25, correct_aspect=True, scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT')

# A joined proxy makes Cycles bake one image pass without merging interaction IDs.
bpy.ops.object.select_all(action='DESELECT')
proxies = []
for obj in meshes:
    proxy = obj.copy()
    proxy.data = obj.data.copy()
    scene.collection.objects.link(proxy)
    transform = obj.matrix_world.copy()
    proxy.parent = None
    proxy.matrix_world = transform
    proxy.select_set(True)
    proxies.append(proxy)
    obj.hide_render = True
bpy.context.view_layer.objects.active = proxies[0]
bpy.ops.object.join()
proxy = bpy.context.object
proxy.name = 'V5_ATLAS_BAKE_PROXY'
bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'}, uv_layer='BakeUV', margin=16, use_clear=True)
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
texture_path = ROOT/'assets/textures/baked'/spec['texture']
image.save_render(str(texture_path), scene=scene)
bpy.data.objects.remove(proxy, do_unlink=True)
texture = bpy.data.images.load(str(texture_path), check_existing=False)
texture.colorspace_settings.name = 'sRGB'
texture.pack()
material = bpy.data.materials.new('WEB_BAKED_V5_ADDITIONS')
material.use_nodes = True
nt = material.node_tree
nt.nodes.clear()
output = nt.nodes.new('ShaderNodeOutputMaterial')
emission = nt.nodes.new('ShaderNodeEmission')
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = texture
nt.links.new(tex.outputs['Color'], emission.inputs['Color'])
nt.links.new(emission.outputs[0], output.inputs['Surface'])
for obj in meshes:
    obj.hide_render = False
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0
    for layer in list(obj.data.uv_layers):
        if layer.name != 'BakeUV':
            obj.data.uv_layers.remove(layer)

bpy.ops.object.select_all(action='DESELECT')
export_objects = [o for o in scene.objects if o.get('web_addition') or o in copies.values() and o.type == 'EMPTY']
for obj in export_objects:
    obj.select_set(True)
scene['web_baked'] = True
scene['source_revision'] = spec['revision']
glb = ROOT/'public/models'/spec['model']
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_active_scene=True, use_selection=True, export_extras=True, export_yup=True, export_animations=False, export_lights=False, export_cameras=False, export_materials='EXPORT', export_copyright='Original scene additions made in Blender for this portfolio. Template: Andrew Woan MIT.')
data = glb.read_bytes()
jlen = struct.unpack_from('<I', data, 12)[0]
doc = json.loads(data[20:20+jlen])
offset = 20+jlen
blen = struct.unpack_from('<I', data, offset)[0]
binary = data[offset+8:offset+8+blen]
for mat in doc.get('materials', []):
    pbr = mat.setdefault('pbrMetallicRoughness', {})
    if 'emissiveTexture' in mat:
        pbr['baseColorTexture'] = mat.pop('emissiveTexture')
    pbr.update(baseColorFactor=[1,1,1,1], metallicFactor=0, roughnessFactor=1)
    mat.pop('emissiveFactor', None)
    mat['extensions'] = {'KHR_materials_unlit': {}}
    mat['doubleSided'] = True
doc['extensionsUsed'] = ['KHR_materials_unlit']
doc.pop('extensionsRequired', None)
raw = json.dumps(doc, separators=(',', ':')).encode()
raw += b' '*(-len(raw)%4)
blob = struct.pack('<III', 0x46546C67, 2, 28+len(raw)+len(binary))+struct.pack('<II', len(raw), 0x4E4F534A)+raw+struct.pack('<II', len(binary), 0x004E4942)+binary
glb.write_bytes(blob)
report = {
    'source':str(blend_path.relative_to(ROOT)), 'model':str(glb.relative_to(ROOT)),
    'texture':str(texture_path.relative_to(ROOT)), 'atlas':atlas_size, 'samples':32,
    'triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),
    'drawCalls':sum(len(m['primitives']) for m in doc['meshes']),
    'bytes':len(blob), 'sha256':hashlib.sha256(blob).hexdigest(),
    'roots':[dict(id=o.get('asset_id'),name=o.name,location=list(o.matrix_world.translation)) for o in export_objects if o.type=='EMPTY' and not o.parent],
    'componentIds':[o.get('asset_id') for o in export_objects if o.get('asset_id')],
    'seconds':round(time.monotonic()-started,2), 'blenderDevice':scene.cycles.device,
}
(ROOT/'assets/blender'/(spec['record']+'-export-report.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
result = report
