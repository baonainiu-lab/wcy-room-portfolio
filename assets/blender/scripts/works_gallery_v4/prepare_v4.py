"""Replace the three rebuilt architectural owners; preserve all interior BakeUVs."""
import bpy,sys,json,math,time,hashlib
from pathlib import Path
from mathutils import Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
import prepare_gallery as p
p.ATLAS_SPECS=(('architecture',4096),('exhibits',4096),('furnishings',4096),('thin_terrace',1024))
REPORT=ROOT/'assets/blender/works-gallery-v4';SOURCE=ROOT/'assets/blender/works-gallery-v4.blend';PREPARED=ROOT/'assets/blender/works-gallery-bake-v4.blend';REPLACE={'gallery.architecture','gallery.architecture.portal','gallery.architecture.glazing'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def owner(o):
 while o:
  if o.get('asset_id'):return str(o['asset_id'])
  o=o.parent
 return None
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));source=bpy.data.scenes['WORKS_GALLERY_V4'];bpy.context.window.scene=source;dg=bpy.context.evaluated_depsgraph_get()
lib=bpy.data.scenes.new('V4_ARCHITECTURE_SNAPSHOT');roots={};source_points={key:[] for key in REPLACE}
for o in source.objects:
 if o.get('asset_id') in REPLACE:
  cp=bpy.data.objects.new('V4_SNAPSHOT_'+o.name,None);p._properties(o,cp);lib.collection.objects.link(cp);cp.matrix_world=o.matrix_world.copy();roots[o['asset_id']]=cp
for o in source.objects:
 own=owner(o)
 if own not in REPLACE or o.type not in {'MESH','CURVE','FONT'} or p._excluded(o):continue
 data=bpy.data.meshes.new_from_object(o.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
 if not len(data.polygons):bpy.data.meshes.remove(data);continue
 source_points[own].extend(tuple(o.matrix_world@v.co) for v in data.vertices)
 # Explicitly bake the evaluated object's world matrix into its mesh before the
 # cross-scene transfer: inactive-scene matrix_world getters can be stale.
 data.transform(o.matrix_world);data.update()
 cp=bpy.data.objects.new('V4_SNAPSHOT_'+o.name,data);lib.collection.objects.link(cp);cp.matrix_world=Matrix.Identity(4);p._properties(o,cp);cp['source_node']=o.name;p._reparent(cp,roots[own]);cp['web_export']=True;cp['web_context']=False
# Keep a separate original PBR copy available for the retained terrace glass too.
archglass=bpy.data.materials['GALLERY_ARCH_GLASS_PBR'];libfile=REPORT/'architecture-snapshot.blend';bpy.data.libraries.write(str(libfile),{lib,archglass},fake_user=True,compress=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-bake-v3.blend'));s=bpy.data.scenes['WEB_WORKS_GALLERY_V3'];bpy.context.window.scene=s;s.name='WEB_WORKS_GALLERY_V4';oldreport=json.loads((ROOT/'assets/blender/works-gallery-v3/preparation-report.json').read_text())
retained=[o for o in s.objects if o.type=='MESH' and o.get('web_export') and o.get('owner_asset_id') not in REPLACE];retained_hash=p._fingerprint(retained)
existing_roots={o['asset_id']:o for o in s.objects if o.get('asset_id') in REPLACE}
for o in list(s.objects):
 if o.get('web_export') and not o.get('asset_id') and owner(o) in REPLACE:bpy.data.objects.remove(o,do_unlink=True)
with bpy.data.libraries.load(str(libfile),link=False) as (a,b):b.scenes=['V4_ARCHITECTURE_SNAPSHOT'];b.materials=['GALLERY_ARCH_GLASS_PBR']
loaded=b.scenes[0];archglass=b.materials[0];parts=[]
for o in list(loaded.objects):
 if o.type=='MESH':
  own=owner(o);s.collection.objects.link(o);loaded.collection.objects.unlink(o);p._reparent(o,existing_roots[own]);parts.append(o)
for o in list(loaded.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.data.scenes.remove(loaded)
materials={};buckets={}
for o in parts:
 for part,kind in p._partition(o,s):buckets.setdefault((owner(part),kind),[]).append(part)
new=[]
for (own,kind),parts in buckets.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in parts:o.select_set(True)
 active=parts[0];bpy.context.view_layer.objects.active=active;before=sum(p._triangles(o) for o in parts);names=[o['source_node'] for o in parts]
 if len(parts)>1:bpy.ops.object.join()
 p._reparent(active,existing_roots[own]);active.name='GALLERY_WEB_'+own+'__'+kind+'__A0';active['owner_asset_id']=own;active['web_kind']=kind;active['geometry_atlas']=0;active['bake_atlas']=0 if kind=='baked' else -1;active['web_export']=True;active['web_context']=False;active['triangles_before']=before;active['merged_source_nodes']=json.dumps(names)
 p._source_uv(active)
 for i,mat in enumerate(list(active.data.materials)):active.data.materials[i]=p._material(mat,'A0_'+kind,materials)
 if kind=='glass':active['architecture_glass']=True
 assert p._triangles(active)==before;new.append(active)
# Verify the transferred geometry against actual source world vertices, not only
# hierarchy and triangle counts. This catches lost locations/rotations during join.
bpy.context.view_layer.update();transform_checks={}
for own in REPLACE:
 expected=source_points[own];actual=[tuple(o.matrix_world@v.co) for o in new if owner(o)==own for v in o.data.vertices]
 assert expected and actual
 def nearest_error(a,b):
  kd=KDTree(len(b))
  for i,v in enumerate(b):kd.insert(v,i)
  kd.balance();return max(kd.find(v)[2] for v in a)
 forward=nearest_error(expected,actual);reverse=nearest_error(actual,expected)
 assert max(forward,reverse)<.00003,(own,forward,reverse)
 transform_checks[own]={'source_vertices':len(expected),'prepared_vertices':len(actual),'max_source_to_prepared_m':forward,'max_prepared_to_source_m':reverse,'bounds_blender':{'min':[min(v[i] for v in actual) for i in range(3)],'max':[max(v[i] for v in actual) for i in range(3)]}}
(REPORT/'source-prepared-transform-verification.json').write_text(json.dumps({'complete':True,'source_sha256':sha(SOURCE),'method':'bidirectional nearest-neighbour comparison of all evaluated source and joined prepared world-space vertices; tolerance 0.00003m','owners':transform_checks},indent=2)+'\n')
# The terrace stays geometrically identical; only dielectric categorization changes.
for o in retained:
 if o.get('owner_asset_id')=='gallery.environment.terrace' and o.get('web_kind')=='glass':
  o.data.materials.clear();o.data.materials.append(p._material(archglass,'A3_glass',materials));o['architecture_glass']=True
  for poly in o.data.polygons:poly.material_index=0
assert p._fingerprint(retained)==retained_hash
# Reunwrap A0 only; all exhibit/furnishing/terrace UV coordinates retain their precision.
members=[o for o in new if o.get('web_kind')=='baked'];bpy.ops.object.select_all(action='DESELECT')
for o in members:
 for uv in list(o.data.uv_layers):
  if uv.name=='BakeUV':o.data.uv_layers.remove(uv)
 uv=o.data.uv_layers.new(name='BakeUV',do_init=False);o.data.uv_layers.active=uv;uv.active_render=True;o.select_set(True)
bpy.context.view_layer.objects.active=members[0];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.0035,area_weight=.25,correct_aspect=True,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.get(p.IMAGE_PREFIX+'0');assert tuple(image.size)==(4096,4096)
for o in members:
 for mat in o.data.materials:
  mat['bake_atlas']=0
  for n in mat.node_tree.nodes:n.select=False
  target=mat.node_tree.nodes.get(p.TARGET_NODE) or mat.node_tree.nodes.new('ShaderNodeTexImage');target.name=p.TARGET_NODE;target.image=image;target.select=True;mat.node_tree.nodes.active=target
meshes=retained+new;fp=p._fingerprint(meshes);pid=hashlib.sha256((fp+str(time.time_ns())).encode()).hexdigest();hier=p._hierarchy(o for o in s.objects if o.get('web_export'));assert hier==oldreport['asset_hierarchy'] and len(hier)==77
s['preparation_id']=pid;s['geometry_uv_sha256']=fp;s['source_blend']=str(SOURCE);s['revision']='v4_closed_architecture_solid_glazing';s['web_baked']=False
reports=[]
for i,(label,size) in enumerate(p.ATLAS_SPECS):
 ms=[o for o in meshes if o.get('web_kind')=='baked' and o.get('bake_atlas')==i]
 reports.append({'atlas':i,'label':label,'resolution':size,'image':p.IMAGE_PREFIX+str(i),'uv_layer':'BakeUV','margin':16,'mesh_count':len(ms),'triangles':sum(p._triangles(o) for o in ms),'owner_ids':sorted({o['owner_asset_id'] for o in ms})})
report=dict(oldreport,source=str(SOURCE.relative_to(ROOT)),prepared=str(PREPARED.relative_to(ROOT)),scene=s.name,preparation_id=pid,geometry_uv_sha256=fp,atlases=reports,mesh_count=len(meshes),triangles=sum(p._triangles(o) for o in meshes),asset_count=77,asset_ids=sorted(hier),asset_hierarchy=hier,glass_meshes=[o.name for o in meshes if o.get('web_kind')=='glass'],retained_interiors_geometry_uv_sha256=retained_hash,retained_interiors_owner_ids=sorted({o['owner_asset_id'] for o in retained}),rebaked_atlases=[0,1,2,3],architecture_glass_meshes=[o.name for o in meshes if o.get('architecture_glass')],original_v3_source_sha256=sha(ROOT/'assets/blender/works-gallery-v3.blend'))
report['triangles_before']=report['triangles'];report.pop('retained_atlas_map',None);report.pop('retained_preparation_id',None);s['preparation_manifest']=json.dumps(report,ensure_ascii=False);bpy.ops.object.select_all(action='DESELECT');bpy.data.libraries.write(str(PREPARED),{s},fake_user=True,compress=True);(REPORT/'preparation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'complete':True,'ids':77,'triangles':report['triangles'],'arch_glass':report['architecture_glass_meshes'],'pid':pid}))
