"""Reproducible original PBR intro-only bake. Never save or mutate V15 files.
Run: Blender --background orbital-dual-bake-v15.blend --python this_file.py
Only independent intro-clean-v1 PNGs, progress, source metadata and preview are written.
"""
import bpy, json, time, hashlib, math
from pathlib import Path
from mathutils import Vector
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE=ROOT/'assets/blender/orbital-dual-bake-v15.blend'
OUT=ROOT/'public/textures/intro-clean-v1';OUT.mkdir(parents=True,exist_ok=True)
RENDERS=ROOT/'renders/intro-clean-v1';RENDERS.mkdir(parents=True,exist_ok=True)
SCRIPT=Path(__file__)
START=time.monotonic()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def rel(p):return str(Path(p).relative_to(ROOT))
protected=[SOURCE,ROOT/'assets/blender/orbital-atelier-v15.blend',ROOT/'public/models/orbital-atelier-v15.glb',ROOT/'public/models/orbital-atelier-v15-compressed.glb',ROOT/'LICENSE.md']
protected+=sorted(p for p in (ROOT/'public/textures/lighting-v15').iterdir() if p.is_file())
before={rel(p):sha(p) for p in protected}
scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene
receivers=[o for o in scene.objects if o.type=='MESH' and o.get('web_export') and o.get('bake_atlas',-1) in (0,8)]
assert len(receivers)==4,len(receivers)
receiver_ids={o.as_pointer() for o in receivers}
hidden=[]
for obj in scene.objects:
 obj.hide_render=obj.as_pointer() not in receiver_ids
 if obj.as_pointer() not in receiver_ids:hidden.append({'name':obj.name,'type':obj.type,'asset_id':obj.get('asset_id')})
 else:
  obj.hide_set(False)
  obj.visible_shadow=False
  assert obj.data.uv_layers.get('BakeUV'),obj.name
# Preserve original source PBR shaders. Only reduce architectural emissive strips
# to their daytime intensity; never perform RGB lifting or emission-only baking.
materials={m for o in receivers for m in o.data.materials if m}
material_records=[]
for mat in materials:
 assert mat.use_nodes and mat.node_tree.nodes.get('WEB8_BAKE_TARGET'),mat.name
 p=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
 assert p is not None,mat.name
 rec={'name':mat.name,'baseColor':list(p.inputs['Base Color'].default_value),'metallic':p.inputs['Metallic'].default_value,'roughness':p.inputs['Roughness'].default_value,'baseColorLinked':p.inputs['Base Color'].is_linked,'roughnessLinked':p.inputs['Roughness'].is_linked}
 emission=p.inputs.get('Emission Strength')
 if emission and not emission.is_linked:
  rec['originalEmissionStrength']=emission.default_value;emission.default_value*=.2;rec['introEmissionStrength']=emission.default_value
 material_records.append(rec)
# A broad physically lit blue-grey environment supplies clean metal reflections.
# No sun, spotlight, HDRI, or hidden furniture emitter remains in this scene.
world=bpy.data.worlds.new('INTRO_CLEAN_V1_BlueGreySoftWorld');world.use_nodes=True
world.node_tree.nodes.clear();wout=world.node_tree.nodes.new('ShaderNodeOutputWorld');bg=world.node_tree.nodes.new('ShaderNodeBackground')
bg.inputs['Color'].default_value=(.36,.44,.55,1);bg.inputs['Strength'].default_value=.8
world.node_tree.links.new(bg.outputs[0],wout.inputs['Surface']);scene.world=world
lights=[]
def area(name,loc,target,energy,size,color):
 d=bpy.data.lights.new('INTRO_CLEAN_V1_'+name,'AREA');d.shape='DISK';d.size=size;d.energy=energy;d.color=color
 o=bpy.data.objects.new(d.name,d);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
 lights.append({'name':o.name,'type':'AREA','location':list(loc),'target':list(target),'watts':energy,'diameter':size,'colorLinear':list(color)})
area('Key',(-4,-4,8),(0,0,1.2),1500,10,(.85,.92,1))
area('Fill',(6,-2,5),(0,0,1.2),650,9,(.72,.85,1))
area('Rear',(0,5,7),(0,0,1.5),1000,9,(1,.93,.84))
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.02
scene.cycles.max_bounces=6;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=2
scene.cycles.use_denoising=True
pref=bpy.context.preferences.addons['cycles'].preferences
try:
 pref.compute_device_type='METAL';pref.get_devices()
 for d in pref.devices:d.use=d.type=='METAL'
 scene.cycles.device='GPU' if any(d.type=='METAL' for d in pref.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.15;scene.view_settings.gamma=1
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8'
scene.render.bake.margin=16;scene.render.bake.margin_type='EXTEND'
assert not any(o.type=='LIGHT' and not o.hide_render and o.data.type!='AREA' for o in scene.objects)
assert [o for o in scene.objects if o.type=='MESH' and not o.hide_render]==receivers
scene_receivers=[{'name':o.name,'atlas':o.get('bake_atlas'),'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'shadowVisibility':o.visible_shadow,'uv':'BakeUV'} for o in receivers]
record={'version':1,'purpose':'Clean receiver-only daylight textures used only while the room and its furniture assemble; original finished-room day/night maps are unchanged.','sourceBlend':rel(SOURCE),'sourceBlendSha256':before[rel(SOURCE)],'authoringScript':rel(SCRIPT),'authoringScriptSha256':sha(SCRIPT),'sourceScene':scene.name,'sourceMaterials':'Original Principled PBR and original microtextures from prepared V15 .blend; no unlit GLB import, color lifting, or fabricated pixels.','geometryUVUnchanged':True,'receiverMeshes':scene_receivers,'excludedObjects':hidden,'hiddenObjectCount':len(hidden),'lighting':{'worldLinearColor':[.36,.44,.55],'worldStrength':.8,'lights':lights,'sunCount':0,'receiverShadowRays':False,'reason':'Merged static architecture atlases include hardware, so disabling receiver shadow-ray visibility prevents ghost silhouettes from any not-yet-present furniture/metal hardware; PBR normal/roughness/metallic response and soft physical reflections remain.'},'materials':material_records,'bake':{'engine':'CYCLES','device':scene.cycles.device,'samples':48,'type':'COMBINED','passes':['DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'],'marginPixels':16,'imageColorMode':'RGB','imageBitDepth':8,'viewTransform':'AgX','look':scene.view_settings.look,'exposure':scene.view_settings.exposure},'atlases':[],'protectedFilesBefore':before,'complete':False,'sourceSaved':False}
write('SOURCE.json',record)
for atlas in [0,8]:
 t=time.monotonic();write('bake-progress.json',{'phase':'baking','currentAtlas':atlas,'completed':record['atlases'],'elapsedSeconds':time.monotonic()-START})
 originals=[o for o in receivers if o.get('bake_atlas')==atlas]
 bpy.ops.object.select_all(action='DESELECT');proxies=[]
 for obj in originals:
  p=obj.copy();p.data=obj.data.copy();scene.collection.objects.link(p);mx=obj.matrix_world.copy();p.parent=None;p.matrix_world=mx;p.hide_render=False;p.hide_set(False);p.visible_shadow=False;p.select_set(True);obj.hide_render=True;proxies.append(p)
  for mat in p.data.materials:
   if mat is None:continue
   target=mat.node_tree.nodes.get('WEB8_BAKE_TARGET');assert target and target.image.name==f'WEB8_ATLAS_{atlas}';mat.node_tree.nodes.active=target
 bpy.context.view_layer.objects.active=proxies[0];bpy.ops.object.join();proxy=bpy.context.object;proxy.name=f'INTRO_CLEAN_V1_RECEIVER_PROXY_{atlas}';proxy.visible_shadow=False
 bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=16,use_clear=True)
 image=bpy.data.images[f'WEB8_ATLAS_{atlas}'];out=OUT/f'day-{atlas}.png';image.save_render(str(out),scene=scene)
 bpy.data.objects.remove(proxy,do_unlink=True)
 for obj in originals:obj.hide_render=False
 item={'atlas':atlas,'state':'day','path':rel(out),'dimensions':list(image.size),'bytes':out.stat().st_size,'sha256':sha(out),'bakeSeconds':round(time.monotonic()-t,2)}
 record['atlases'].append(item);write('SOURCE.json',record);print('INTRO_CLEAN_ATLAS_READY '+json.dumps(item),flush=True)
# Actual Cycles proof of the same receiver-only PBR setup, with no hidden props.
if scene.camera:
 scene.camera.hide_render=False;scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.film_transparent=False
 preview=RENDERS/'receiver-preview.png';scene.render.filepath=str(preview);bpy.ops.render.render(write_still=True)
 record['receiverPreview']={'path':rel(preview),'sha256':sha(preview),'bytes':preview.stat().st_size,'method':'Actual Cycles render of the receiver-only original PBR setup; not AI-generated and not an atlas repaint.'}
after={rel(p):sha(p) for p in protected};assert before==after,'A protected V15 file changed while baking'
record['protectedFilesAfter']=after;record['protectedFilesUnchanged']=True;record['complete']=True;record['seconds']=round(time.monotonic()-START,2)
write('SOURCE.json',record);write('bake-progress.json',{'phase':'complete','completed':record['atlases'],'elapsedSeconds':record['seconds']})
print('INTRO_CLEAN_COMPLETE '+json.dumps({'seconds':record['seconds'],'atlasRecords':record['atlases'],'protectedFiles':len(before),'unchanged':True}),flush=True)
