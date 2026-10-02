import bpy,math,time
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
source=bpy.data.scenes['ORBITAL_ATELIER_V2'];bpy.context.window.scene=source;dg=bpy.context.evaluated_depsgraph_get();root=source.objects['F_Crescent_Orange_Lounge']
children=list(root.children_recursive)
s=bpy.data.scenes.new('WEB_CHAIR_REBAKE');s.world=source.world;s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=32;s.cycles.max_bounces=6;s.cycles.diffuse_bounces=3;s.cycles.glossy_bounces=3;s.cycles.transmission_bounces=4;s.view_settings.view_transform='AgX';s.view_settings.exposure=.1
for o in source.objects:
 if o!=root and o not in children:s.collection.objects.link(o)
parts=[];mats={}
for old in children:
 if old.type not in {'MESH','CURVE'} or old.hide_render:continue
 mesh=bpy.data.meshes.new_from_object(old.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
 new=bpy.data.objects.new('CHAIR_HIGH_'+old.name,mesh);s.collection.objects.link(new);new.matrix_world=old.matrix_world.copy();parts.append(new)
 for i,mat in enumerate(list(mesh.materials)):
  if mat.name not in mats:
   copy=mat.copy();copy.name='CHAIR_BAKE_'+mat.name;nt=copy.node_tree
   for pnode in nt.nodes:
    if pnode.type=='BSDF_PRINCIPLED':
     for link in list(pnode.inputs['Normal'].links):nt.links.remove(link)
   uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='UVMap'
   for n in list(nt.nodes):
    if n.type=='TEX_COORD':
     for link in list(n.outputs['UV'].links):nt.links.new(uv.outputs['UV'],link.to_socket)
    if n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked:nt.links.new(uv.outputs[0],n.inputs['Vector'])
   mats[mat.name]=copy
  mesh.materials[i]=mats[mat.name]
bpy.context.window.scene=s;bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name='WEB_CHAIR_HIGH_BAKE';o.data.validate(clean_customdata=True)
uv=o.data.uv_layers.new(name='BakeUV');o.data.uv_layers.active=uv;uv.active_render=True
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(75),island_margin=.01,area_weight=.5,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
im=bpy.data.images.new('ROOM_CHAIR_REPAIRED',width=2048,height=2048,alpha=False,float_buffer=True);im.colorspace_settings.name='Linear Rec.709'
for mat in mats.values():
 n=mat.node_tree.nodes.new('ShaderNodeTexImage');n.image=im;mat.node_tree.nodes.active=n
started=time.monotonic()
bpy.ops.object.bake('INVOKE_DEFAULT',type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=32,margin_type='EXTEND',use_clear=True)
def check_is_finished():
 if bpy.app.is_job_running('OBJECT_BAKE'):return None
 return {'stage':'chair_repair_baked','seconds':time.monotonic()-started,'triangles':sum(len(p.vertices)-2 for p in o.data.polygons)}
