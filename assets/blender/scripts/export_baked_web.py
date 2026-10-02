"""Export the optimized room with baked lighting and independent asset hierarchy."""
import bpy,json,struct,hashlib
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio');scene=bpy.data.scenes['WEB_BAKE_V4'];bpy.context.window.scene=scene
scene['web_baked']=True;scene['bake_mode']='cycles_combined_agx';scene['source_revision']=4
outdir=ROOT/'assets/textures/baked';outdir.mkdir(parents=True,exist_ok=True)
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8'
atlas_materials=[]
for i in range(4):
 path=outdir/f'room-night-{i}.png';bpy.data.images[f'ROOM_BAKED_{i}'].save_render(str(path),scene=scene)
 image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='sRGB';image.pack()
 mat=bpy.data.materials.new(f'WEB_BAKED_ATLAS_{i}');mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear()
 output=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image
 uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='BakeUV';nt.links.new(uv.outputs[0],tex.inputs['Vector']);nt.links.new(tex.outputs[0],em.inputs['Color']);nt.links.new(em.outputs[0],output.inputs['Surface']);atlas_materials.append(mat)
for obj in scene.objects:
 if obj.type!='MESH' or not obj.get('web_kind'):continue
 if obj['web_kind']=='baked':
  atlas=int(obj['bake_atlas']);obj.data.materials.clear();obj.data.materials.append(atlas_materials[atlas])
  for poly in obj.data.polygons:poly.material_index=0
  # Only the baked UV is needed by the viewer. Original procedural UVs remain in source .blend.
  for uv in list(obj.data.uv_layers):
   if uv.name!='BakeUV':obj.data.uv_layers.remove(uv)
  obj.data.uv_layers.active=obj.data.uv_layers['BakeUV']
 elif obj['web_kind']=='glass':
  old=obj.data.materials[0];name=old.name if old else obj.name
  mat=bpy.data.materials.new('WEB_CLEAR_'+name);mat.use_nodes=True
  p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.55,.68,.74,1);p.inputs['Metallic'].default_value=0;p.inputs['Roughness'].default_value=.3
  obj.data.materials.clear();obj.data.materials.append(mat)
  for poly in obj.data.polygons:poly.material_index=0
 # Display artworks keep their original dedicated high-resolution textures.
bpy.ops.object.select_all(action='DESELECT')
for obj in scene.objects:
 if obj.type=='EMPTY' or obj.get('web_kind'):obj.hide_set(False);obj.select_set(True)
path=ROOT/'public/models/orbital-atelier-v4.glb'
bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_active_scene=True,use_selection=True,export_apply=False,export_extras=True,export_yup=True,export_animations=False,export_lights=False,export_cameras=False,export_image_format='AUTO',export_materials='EXPORT',export_copyright='Original Blender room assets; template copyright 2025 Andrew Woan (MIT).')
# Explicit unlit materials give the same light-weight texture path as the original template.
# Convert Blender emission exports into standard KHR_materials_unlit base-color maps.
data=path.read_bytes();jlen=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+jlen]);boff=20+jlen;blen,btype=struct.unpack_from('<II',data,boff);binchunk=data[boff+8:boff+8+blen]
for mat in doc['materials']:
 name=mat['name'];pbr=mat.setdefault('pbrMetallicRoughness',{})
 if name.startswith('WEB_CLEAR_'):
  alpha=.34 if 'Smoke_Glass' in name else .13
  pbr.clear();pbr.update(baseColorFactor=[.69,.81,.86,alpha],metallicFactor=0,roughnessFactor=1);mat['alphaMode']='BLEND'
 else:
  if 'emissiveTexture' in mat:pbr['baseColorTexture']=mat.pop('emissiveTexture')
  pbr['baseColorFactor']=[1,1,1,1];pbr['metallicFactor']=0;pbr['roughnessFactor']=1
 mat.pop('emissiveFactor',None);mat.pop('normalTexture',None);mat.pop('occlusionTexture',None)
 mat['extensions']={'KHR_materials_unlit':{}};mat['doubleSided']=True
used=set(doc.get('extensionsUsed',[]));used.add('KHR_materials_unlit');used.discard('KHR_materials_emissive_strength');doc['extensionsUsed']=sorted(used)
for s in doc.get('scenes',[]):s.setdefault('extras',{}).update(web_baked=True,bake_mode='cycles_combined_agx',source_revision=4)
raw=json.dumps(doc,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4)
blob=struct.pack('<III',0x46546C67,2,12+8+len(raw)+8+len(binchunk))+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(binchunk),0x004E4942)+binchunk;path.write_bytes(blob)
report={'source':'assets/blender/orbital-atelier-v2.blend','scene':'WEB_BAKE_V4','model':'public/models/orbital-atelier-v4.glb','triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),'mesh_groups':len(doc['meshes']),'draw_primitives':sum(len(m['primitives']) for m in doc['meshes']),'materials':len(doc['materials']),'images':len(doc.get('images',[])),'logical_roots':26,'component_groups':74,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'baked':True,'atlas_resolution':4096,'samples':scene.cycles.samples,'web_shader':'KHR_materials_unlit / MeshBasicMaterial','color':'Cycles COMBINED lighting, AgX display transform baked into sRGB PNG; browser NoToneMapping'}
(ROOT/'assets/blender/web-baked-export-report.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.context.window.scene=bpy.data.scenes['ORBITAL_ATELIER_V2']
result=report
