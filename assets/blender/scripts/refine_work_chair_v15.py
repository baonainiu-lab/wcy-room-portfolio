"""Restore the authored work chair and a dedicated continuous-shell bake atlas."""
import argparse,array,bpy,hashlib,json,math,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from prepare_texture_precision_v15 import geometry
from refine_edge_atlas_v14 import metrics
from bake_geometry_fingerprint import fingerprints
from run_texture_precision_v15 import scope_from
PREP=ROOT/'assets/blender/orbital-dual-bake-v15.blend';SOURCE=ROOT/'assets/blender/orbital-atelier-v15.blend';OUT=ROOT/'public/textures/lighting-v15';BACK=ROOT/'assets/blender/v15-pre-chair'
REPORT=ROOT/'assets/blender/work-chair-v15-refinement.json'
SIZE=3072

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(r,indent=2)+'\n');t.replace(p)
def authored_fingerprint():
 s=bpy.data.scenes['ORBITAL_ATELIER_V2'];bpy.context.window.scene=s;bpy.context.view_layer.update();root=s.objects['F_Sculptural_Work_Chair'];dg=bpy.context.evaluated_depsgraph_get();records=[]
 for o in sorted(root.children_recursive,key=lambda o:o.name):
  if o.type not in ('MESH','CURVE') or o.hide_render:continue
  ev=o.evaluated_get(dg);m=ev.to_mesh();d=hashlib.sha256()
  for v in m.vertices:d.update(array.array('f',ev.matrix_world@v.co).tobytes())
  for p in m.polygons:d.update(array.array('i',p.vertices).tobytes())
  records.append({'name':o.name,'sha256':d.hexdigest(),'triangles':sum(len(p.vertices)-2 for p in m.polygons)})
  ev.to_mesh_clear()
 return records

def prepare():
 assert not REPORT.exists(),'Chair preparation already exists; refusing to repeat replacement'
 BACK.mkdir(parents=True,exist_ok=True)
 for p in (PREP,SOURCE,ROOT/'public/models/orbital-atelier-v15.glb',ROOT/'assets/blender/dual-lighting-v15-export-report.json',ROOT/'assets/blender/precision-images-v15-bind-report.json'):
  target=BACK/p.name;assert not target.exists();shutil.copy2(p,target)
 bpy.ops.wm.open_mainfile(filepath=str(SOURCE));authored=authored_fingerprint()
 bpy.ops.wm.open_mainfile(filepath=str(PREP));assert authored_fingerprint()==authored
 source_scene=bpy.data.scenes['ORBITAL_ATELIER_V2'];root=source_scene.objects['F_Sculptural_Work_Chair'];dg=bpy.context.evaluated_depsgraph_get()
 scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene;bpy.context.view_layer.update();before=geometry(scene);before_uv=fingerprints(scene,include_shading=True)
 target=next(o for o in scene.objects if o.type=='MESH' and o.get('owner_asset_id')=='furniture.work_chair');matrix=target.matrix_world.copy();inv=matrix.inverted();old_tri=sum(len(p.vertices)-2 for p in target.data.polygons)
 image=bpy.data.images.new('WEB8_ATLAS_11',width=SIZE,height=SIZE,alpha=False,float_buffer=True);image.colorspace_settings.name='Linear Rec.709'
 # Read evaluated authored parts from their source scene, without decimation.
 bpy.context.window.scene=source_scene;bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();parts=[];cache={}
 from prepare_dual_bake_v8 import _isolated_material
 for old in sorted(root.children_recursive,key=lambda o:o.name):
  if old.type not in ('MESH','CURVE') or old.hide_render:continue
  ev=old.evaluated_get(dg);mesh=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=dg)
  transform=inv@ev.matrix_world
  for v in mesh.vertices:v.co=transform@v.co
  obj=bpy.data.objects.new('CHAIR_V15_'+old.name,mesh);scene.collection.objects.link(obj);obj.matrix_world=matrix.copy();parts.append(obj)
  if 'Continuous_Ceramic_Shell' in old.name:
   assert len(mesh.polygons)==5104,len(mesh.polygons)
   side=mesh.attributes.new('chair_shell_side','INT','FACE')
   for p in mesh.polygons:side.data[p.index].value=1 if p.index<2448 else 2 if p.index<4896 else 0
  for i,mat in enumerate(list(mesh.materials)):
   copied=_isolated_material(mat,'BAKE_A11',cache);mesh.materials[i]=copied
   if not copied.node_tree.nodes.get('WEB8_BAKE_TARGET'):
    n=copied.node_tree.nodes.new('ShaderNodeTexImage');n.name='WEB8_BAKE_TARGET';n.image=image;copied.node_tree.nodes.active=n
   copied['bake_atlas']=11
 bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT')
 for o in parts:o.select_set(True)
 bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();joined=bpy.context.object
 assert sum(len(p.vertices)-2 for p in joined.data.polygons)==48652
 target.data=joined.data.copy();bpy.data.objects.remove(joined,do_unlink=True)
 target['bake_atlas']=target['geometry_atlas']=11;target['precision_revision']=15;target['chair_geometry_policy']='full authored 48652 triangles; continuous ceramic shell UV'
 mesh=target.data
 if mesh.uv_layers.get('BakeUV'):mesh.uv_layers.remove(mesh.uv_layers['BakeUV'])
 uv=mesh.uv_layers.new(name='BakeUV');mesh.uv_layers.active=uv;uv.active_render=True
 bpy.ops.object.select_all(action='DESELECT');target.select_set(True);bpy.context.view_layer.objects.active=target
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(70),island_margin=.003,area_weight=.25,correct_aspect=True,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
 original=mesh.uv_layers['UVMap'];uv=mesh.uv_layers['BakeUV'];side=mesh.attributes['chair_shell_side'];pinned={}
 # Two full, continuous surfaces. Solidify thickness edges keep separate UVs.
 for p in mesh.polygons:
  surface=side.data[p.index].value
  if surface not in (1,2):continue
  for li in p.loop_indices:
   u,v=original.data[li].uv;uv.data[li].uv=((.010 if surface==1 else .285)+.255*u,.015+.97*v);uv.data[li].pin_uv=True;pinned[li]=tuple(uv.data[li].uv)
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.pack_islands(rotate=True,rotate_method='ANY',scale=True,merge_overlap=False,margin_method='FRACTION',margin=12/SIZE,pin=True,pin_method='LOCKED',shape_method='CONCAVE');bpy.ops.object.mode_set(mode='OBJECT')
 uv=mesh.uv_layers['BakeUV'];assert all((uv.data[i].uv.x-x)**2+(uv.data[i].uv.y-y)**2<1e-12 for i,(x,y) in pinned.items())
 assert all(math.isfinite(v) and -.0001<=v<=1.0001 for t in uv.data for v in t.uv)
 # Internal surface edges on either white side must have a single UV value.
 discontinuities=[]
 for surface in (1,2):
  values={}
  for p in mesh.polygons:
   if side.data[p.index].value!=surface:continue
   for li in p.loop_indices:
    vi=mesh.loops[li].vertex_index;val=tuple(round(x,7) for x in uv.data[li].uv)
    if vi in values and values[vi]!=val:discontinuities.append([surface,vi])
    values[vi]=val
 assert not discontinuities
 after=geometry(scene);assert {k:v for k,v in before.items() if k!=target.name}=={k:v for k,v in after.items() if k!=target.name}
 after_uv=fingerprints(scene,include_shading=True);assert {k:v for k,v in before_uv.items() if v['atlas']!=1 or 'furniture.work_chair' not in k}=={k:v for k,v in after_uv.items() if v['atlas']!=11}
 report={'revision':15,'preparedBeforeSha256':sha(PREP),'sourceSha256':sha(SOURCE),'backup':str(BACK.relative_to(ROOT)),
  'object':target.name,'assetId':'furniture.work_chair','authoredParts':authored,'oldTriangles':old_tri,'newTriangles':48652,'sceneTriangles':413855,
  'atlas':11,'size':SIZE,'samples':96,'material':'WEB8_LIGHTMAP_11','shellInternalUvDiscontinuities':0,
  'whiteShellTriangles':10208,'whiteShellSurfaceUVRectangles':[[.010,.015,.265,.985],[.285,.015,.540,.985]],
  'metrics':metrics(target,range(len(mesh.polygons)),SIZE),'whiteShellMetrics':metrics(target,[p.index for p in mesh.polygons if 'Ivory_Ceramic' in mesh.materials[p.material_index].name],SIZE),
  'otherGeometryAndUVUnchanged':True,'stableRootTransform':before[target.name], 'bakeInputsFingerprint':after_uv['11::furniture.work_chair']}
 scene['chair_precision_revision']=15;bpy.ops.wm.save_as_mainfile(filepath=str(PREP),compress=True);report['preparedSha256']=sha(PREP);write(REPORT,report);print(json.dumps(report,indent=2))
 return report

def bake(state):
 report=json.loads(REPORT.read_text());assert sha(PREP)==report['preparedSha256'];bpy.ops.wm.open_mainfile(filepath=str(PREP))
 from run_wall_lighting_v10 import configure_day
 warm=scope_from(ROOT/'assets/blender/scripts/night_warm_v13.py',[("night-warm-v13-design.json","night-warm-v15-chair-design.json"),("lighting-night-v13.json","lighting-night-v15-chair.json")],'chair_inherited_night')
 baking=scope_from(ROOT/'assets/blender/scripts/bake_lighting_v8.py',[("OUT = ROOT / 'public/textures/lighting-v8'","OUT = ROOT / 'public/textures/lighting-v15'"),('scene.cycles.samples = 40','scene.cycles.samples = 96'),('scene.cycles.adaptive_threshold = .035','scene.cycles.adaptive_threshold = .01'),('margin = 32 if atlas == 7 else 16','margin = 12')],'chair_baker')
 def transform(scene):
  if state=='day':
   import day_sunlight_v9;day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57);configure_day(scene,revision=15)
  else:warm['configure_night_warm'](scene)
  scene.cycles.samples=96;scene.cycles.adaptive_threshold=.01
 record=baking['bake_state'](state,indices=[11],scene_transform=transform,output_directory=OUT,revision='15-chair')
 record.update(complete=True,samples=96,preparedSha256=sha(PREP),geometryAndUV=report['bakeInputsFingerprint'])
 for r in record['atlases']:r['sha256']=sha(ROOT/r['path'])
 write(OUT/f'{state}-v15-chair-manifest.json',record);print(json.dumps(record,indent=2));return record

def export():
 chair=json.loads(REPORT.read_text());assert sha(PREP)==chair['preparedSha256']
 for state in ('day','night'):
  manifest=json.loads((OUT/f'{state}-v15-chair-manifest.json').read_text());assert manifest['complete'] and manifest['preparedSha256']==sha(PREP)
  assert manifest['atlases'][0]['sha256']==sha(OUT/f'{state}-11.png')
 bpy.ops.wm.open_mainfile(filepath=str(PREP))
 exporting=scope_from(ROOT/'assets/blender/scripts/export_dual_lighting_v8.py',[
 ('for atlas in range(8):','for atlas in range(12):'),("'atlasSizes':[4096]*6+[3072,2048]","'atlasSizes':[4096]*6+[3072,2048,3072,4096,4096,3072]"),("'samples':40","'samples':96")],'chair_export')
 final=ROOT/'public/models/orbital-atelier-v15.glb';pending=final.with_name('orbital-atelier-v15.pending.glb')
 result=exporting['export'](textures_directory=OUT,output_path=pending,source_path=str(SOURCE.relative_to(ROOT)),prepared_path=str(PREP.relative_to(ROOT)),geometry_revision=15,lighting_revision=15)
 previous=json.loads((BACK/'dual-lighting-v15-export-report.json').read_text());report={**previous,**result,'model':str(final.relative_to(ROOT)),
  'workChairRefinement':chair,'preparedSha256':sha(PREP),'sourceSha256':sha(SOURCE),'smallPropGeometryUnchanged':True,'workChairGeometryRestored':True,
  'rebakedAtlasIDs':[0,2,3,4,8,9,10,11]}
 assert sorted(report['componentIds'])==sorted(previous['componentIds']);assert report['triangles']==413855 and report['drawPrimitives']==102
 pending.replace(final);write(ROOT/'assets/blender/dual-lighting-v15-export-report.json',report);print(json.dumps(report,indent=2));return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--state',choices=('day','night'));parser.add_argument('--export',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
 if args.prepare:prepare()
 elif args.export:export()
 else:bake(args.state)
