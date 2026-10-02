"""Build a disposable, decimated bake scene. Never save over the render source."""
import bpy, math, json
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
source=bpy.data.scenes['ORBITAL_ATELIER_V2'];bpy.context.window.scene=source
dg=bpy.context.evaluated_depsgraph_get()
scene=bpy.data.scenes.new('WEB_BAKE_V4');scene.world=source.world;scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=32
scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.06
scene.cycles.max_bounces=6;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=4
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.1
scene.render.bake.margin=12;scene.render.bake.use_clear=True
copies={};geometry=[];original_materials={}
for old in source.objects:
 if old.type in {'LIGHT','CAMERA'} or any(c.name=='STUDIO_NON_EXPORT' for c in old.users_collection):
  scene.collection.objects.link(old);continue
 if old.type not in {'MESH','CURVE','EMPTY'} or old.hide_render:continue
 if old.type=='EMPTY':new=bpy.data.objects.new(old.name+'__bake',None)
 else:
  mesh=bpy.data.meshes.new_from_object(old.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
  if not len(mesh.vertices):bpy.data.meshes.remove(mesh);continue
  new=bpy.data.objects.new(old.name+'__bake',mesh);geometry.append(new)
 scene.collection.objects.link(new);new.matrix_world=old.matrix_world.copy();copies[old]=new
 for k in old.keys():
  if k!='_RNA_UI':
   try:new[k]=old[k]
   except TypeError:pass
 new['source_node']=old.name
bpy.context.window.scene=scene;bpy.context.view_layer.update()
for old,new in copies.items():
 par=old.parent
 while par and par not in copies:par=par.parent
 if par:
  mx=new.matrix_world.copy();new.parent=copies[par];new.matrix_world=mx
bpy.context.view_layer.update()

def owner_for(o):
 par=o.parent
 while par and not par.get('asset_id'):par=par.parent
 return par

def root_for(o):
 par=o
 while par.parent:par=par.parent
 return par

def type_of(o):
 for mat in o.data.materials:
  if not mat or not mat.node_tree:continue
  for n in mat.node_tree.nodes:
   if n.type=='EMISSION' and any(t.type=='TEX_IMAGE' for t in mat.node_tree.nodes):return 'image'
   if n.type=='BSDF_PRINCIPLED' and n.inputs['Transmission Weight'].default_value>0:return 'glass'
 return 'baked'

buckets={}
for o in geometry:buckets.setdefault((owner_for(o),type_of(o)),[]).append(o)
meshes=[]
for (owner,kind),parts in buckets.items():
 bpy.ops.object.select_all(action='DESELECT')
 for part in parts:part.select_set(True)
 active=parts[0];bpy.context.view_layer.objects.active=active
 if len(parts)>1:bpy.ops.object.join()
 mx=active.matrix_world.copy();active.parent=owner;active.matrix_world=mx
 asset=owner.get('asset_id') if owner else 'room_static'
 active.name=asset+'__'+kind;active['web_kind']=kind
 count=sum(len(p.vertices)-2 for p in active.data.polygons)
 budget=2500
 if asset=='room_static':budget=18000
 elif asset=='furniture.lounge':budget=12000
 elif asset=='furniture.work_chair':budget=8000
 elif asset=='trailing_wall_plant':budget=9500
 elif asset=='glass_bonsai_terrarium':budget=7000
 elif asset in {'ceramic_mobius_form','furniture.desk','furniture.coffee_table'}:budget=4500
 elif asset.startswith(('terminal_panel','communicator_panel')):budget=1800
 elif asset.startswith('furniture.'):budget=3500
 elif asset.startswith(('small_planter_leaf','floor_vase_leaf')):budget=180
 if kind=='glass':budget=min(2500,budget)
 if kind=='image':budget=count
 if count>budget*1.08:
  dec=active.modifiers.new('Web silhouette budget','DECIMATE');dec.ratio=budget/count;dec.use_collapse_triangulate=True
  bpy.ops.object.modifier_apply(modifier=dec.name)
 active.data.validate(clean_customdata=True)
 active.data.update()
 active['triangles_before']=count
 meshes.append(active)

images=[];groups=[[] for _ in range(4)]
for o in meshes:
 if o['web_kind']!='baked':continue
 root=root_for(o);rid=root.get('asset_id','')
 if rid.startswith('furniture.'):atlas=1
 elif rid.startswith('architecture.') or not rid:atlas=0
 elif root.get('source_node','').startswith('D_'):atlas=3
 else:atlas=2
 o['bake_atlas']=atlas;groups[atlas].append(o)
 # Make every source texture explicitly read UVMap, independent of active BakeUV.
 for i,old in enumerate(list(o.data.materials)):
  if old is None:continue
  key=(atlas,old.name)
  if key not in original_materials:
   mat=old.copy();mat.name=f'BAKE{atlas}_'+old.name
   nt=mat.node_tree;uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='UVMap'
   for n in list(nt.nodes):
    if n.type=='TEX_COORD':
     for link in list(n.outputs['UV'].links):nt.links.new(uv.outputs['UV'],link.to_socket)
    if n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked:nt.links.new(uv.outputs['UV'],n.inputs['Vector'])
   original_materials[key]=mat
  o.data.materials[i]=original_materials[key]
 uv=o.data.uv_layers.new(name='BakeUV');o.data.uv_layers.active=uv;uv.active_render=True
for i,group in enumerate(groups):
 bpy.ops.object.select_all(action='DESELECT')
 for o in group:o.select_set(True)
 bpy.context.view_layer.objects.active=group[0]
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
 bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.002,area_weight=.25,correct_aspect=True,scale_to_bounds=True)
 bpy.ops.object.mode_set(mode='OBJECT')
 im=bpy.data.images.new(f'ROOM_BAKED_{i}',width=4096,height=4096,alpha=False,float_buffer=True);im.colorspace_settings.name='Linear Rec.709'
 images.append(im)
 for (atlas,name),mat in original_materials.items():
  if atlas!=i:continue
  n=mat.node_tree.nodes.new('ShaderNodeTexImage');n.name='BAKE_TARGET';n.image=im;mat.node_tree.nodes.active=n;n.select=True
scene['web_baked']=True
report={'scene':scene.name,'mesh_groups':len(meshes),'triangles_before':sum(o.get('triangles_before',0) for o in meshes),'triangles_after':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),'bake_groups':[len(g) for g in groups],'atlas_resolution':4096,'root_count':sum(o.type=='EMPTY' and not o.parent for o in scene.objects)}
(ROOT/'assets/blender/web-bake-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
result=report
