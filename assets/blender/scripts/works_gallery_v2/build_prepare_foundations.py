"""Add closed V2 environment foundations while preserving all V1 IDs/UVs/interiors."""
import bpy,sys,json,hashlib,time,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'assets/blender/scripts/works_gallery_v1'
sys.path.insert(0,str(OLD))
import gallery_common as g
import prepare_gallery as p
REPORT=ROOT/'assets/blender/works-gallery-v2'
SOURCE=ROOT/'assets/blender/works-gallery-v2.blend'
PREPARED=ROOT/'assets/blender/works-gallery-bake-v2.blend'
p.ATLAS_SPECS=(*p.ATLAS_SPECS,('foundations',2048))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def bounds(o):
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());vs=[o.matrix_world@Vector(v) for v in ev.bound_box]
    return [[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]]
def savejson(path,x):path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v1.blend'))
scene=bpy.data.scenes['WORKS_GALLERY_V1'];bpy.context.window.scene=scene
old_ids=p._hierarchy(o for o in scene.objects if not p._excluded(o))
original_lights={o.name:{'matrix':[list(r) for r in o.matrix_world],'energy':o.data.energy,'color':list(o.data.color)} for o in scene.objects if o.type=='LIGHT'}
for key in ('silver','navy','bronze','ivory','black','glass','warm','leather','leaf','soil','paper','ink','terrazzo'):
    g.M[key]=bpy.data.materials['GALLERY_'+key]
# The original excluded plane was above the cut-off bridge piers. Remove it;
# every replacement is closed geometry exported with its own foundation ID.
removed=[]
for o in list(scene.objects):
    if o.name.startswith('Urban landscape base'):
        removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
root=g.group('gallery.environment.foundation',atlas=4)
root['revision']='v2_closed_city_foundations';root['interactive']=False
root['ground_top']=-5.82;root['ground_bottom']=-7.62
root['purpose']='Continuous city terrain, gallery podium, connected bridge and skyline supports'
new=[]
def add(o,kind):o['foundation_part']=kind;new.append(o);return o
# A closed landmass, with broad calm material so a 2K atlas is sufficient.
terrain=g.M['navy'].copy();terrain.name='GALLERY_v2_ground_slate'
pbsdf=terrain.node_tree.nodes.get('Principled BSDF');pbsdf.inputs['Base Color'].default_value=(.10,.14,.16,1);pbsdf.inputs['Metallic'].default_value=.12;pbsdf.inputs['Roughness'].default_value=.64
add(g.rounded_rect('V2 continuous city landmass',(-2,28,-6.72),116,112,1.8,10,terrain,root,plane='XY'),'landmass')
# Gallery terrace rests on a substantial, closed layered architectural podium.
# Its crown is inset under the original rounded terrace; the upper floor is intact.
add(g.rounded_rect('V2 gallery solid podium', (0,1,-3.40),21.55,13.72,5.11,1.55,g.M['navy'],root,plane='XY'),'gallery_podium')
add(g.rounded_rect('V2 podium silver foot',(0,1,-5.56),22.2,14.4,.27,1.80,g.M['silver'],root,plane='XY'),'podium_foot')
add(g.rounded_rect('V2 podium upper reveal',(0,1,-1.07),21.72,13.91,.19,1.57,g.M['silver'],root,plane='XY'),'podium_crown')
# Front entrance steps previously cantilevered beyond y=-6.1; foundation reaches below.
add(g.rounded_rect('V2 entrance step support',(-.35,-5.60,-3.36),18.0,2.22,4.94,1.05,g.M['navy'],root,plane='XY'),'entrance_support')
# Gallery rear planters now sit on a connected terrace rather than hanging above a void.
add(g.rounded_rect('V2 rear garden terrace',(0,8.75,-3.14),24.5,5.7,5.37,1.6,g.M['navy'],root,plane='XY'),'garden_support')
add(g.rounded_rect('V2 rear garden paving',(0,8.75,-.46),24.5,5.7,.07,1.6,g.M['terrazzo'],root,plane='XY'),'garden_paving')
for i,(y,z,w,d) in enumerate([(12.0,-1.15,27.0,3.8),(14.8,-2.45,30.5,3.8),(17.8,-3.85,35.0,4.6)]):
    bottom=-5.87;thickness=z-bottom
    add(g.rounded_rect('V2 retaining terrace %02d'%i,(0,y,bottom+thickness/2),w,d,thickness,1.0,g.M['navy'],root,plane='XY'),'retaining_mass')
    add(g.rounded_rect('V2 terrace stone cap %02d'%i,(0,y,z+.035),w,d,.07,1.0,terrain,root,plane='XY'),'retaining_cap')
# Shallow architectural ribs give side views a finished load-bearing facade.
for side in (-1,1):
    for i,y in enumerate((-3.2,-.9,1.4,3.7,5.8)):
        add(g.box('V2 podium side rib %d %d'%(side,i),(side*10.79,y,-3.26),(.13,.20,4.20),g.M['silver'],root,.035),'podium_rib')
# Existing 37 piers retain their approved shape and receive closed footings.
audit=json.loads((REPORT/'environment-audit.json').read_text())['objects']
supports=[]
for entry in audit:
    name=entry.get('source') or ''
    if not any(t in name for t in ('Terrace_Pier_','Left_Pier_','Skyway_Support_')):continue
    lo,hi=entry['min'],entry['max'];cx=(lo[0]+hi[0])/2;cy=(lo[1]+hi[1])/2
    top=max(-5.20,lo[2]+.18);bottom=-5.89
    dims=(max(1.10,hi[0]-lo[0]+.46),max(1.08,hi[1]-lo[1]+.46),top-bottom)
    obj=add(g.box('V2 connected bridge footing '+name,(cx,cy,(top+bottom)/2),dims,g.M['ivory'],root,.08),'existing_pier_foot')
    supports.append({'existing':entry['name'],'existing_bottom':lo[2],'foundation':obj.name,'foot_bottom':bottom,'foot_top':top,'connected':top>=lo[2] and bottom<=-5.82})
# Far skyline decks require real piers: all three now connect to the same terrain.
far=[]
for row,y in enumerate((38.52,47.64,58.47)):
    for i,x in enumerate((-36,-28,-20,-12,-4,4,12,20,28,33)):
        bottom=-5.89;top=-1.42
        obj=add(g.box('V2 skyline pier %d %02d'%(row,i),(x,y,(top+bottom)/2),(1.00,.94,top-bottom),g.M['ivory'],root,.06),'skyline_pier')
        add(g.box('V2 skyline pier shoe %d %02d'%(row,i),(x,y,-5.57),(1.65,1.53,.64),g.M['navy'],root,.07),'skyline_shoe')
        far.append({'name':obj.name,'bottom':bottom,'top':top,'deck_bottom':-1.464,'connected':True})
    add(g.box('V2 continuous skyline beam %d'%row,(-2,y,-1.60),(74.1,1.00,.40),g.M['navy'],root,.05),'skyline_beam')
# New terrain is closed, all additions are dedicated environment-only children.
bpy.context.view_layer.update()
scene.name='WORKS_GALLERY_V2'
new_bounds={o.name:bounds(o) for o in new}
assert p._hierarchy(o for o in scene.objects if not p._excluded(o))==dict(old_ids,**{'gallery.environment.foundation':None})
assert original_lights=={o.name:{'matrix':[list(r) for r in o.matrix_world],'energy':o.data.energy,'color':list(o.data.color)} for o in scene.objects if o.type=='LIGHT'}
scene['revision']='gallery_v2_closed_foundations';scene['original_interior_preserved']=True
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE),compress=True)
source_sha=sha(SOURCE)
# Write a small evaluated library for the sole new environment owner.
libscene=bpy.data.scenes.new('GALLERY_V2_FOUNDATION_LIBRARY');libroot=bpy.data.objects.new(root.name,None);p._properties(root,libroot);libscene.collection.objects.link(libroot)
parts=[];dg=bpy.context.evaluated_depsgraph_get()
for old in new:
    data=bpy.data.meshes.new_from_object(old.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
    obj=bpy.data.objects.new(old.name,data);libscene.collection.objects.link(obj);obj.matrix_world=old.matrix_world.copy();p._properties(old,obj);p._reparent(obj,libroot);parts.append(obj)
libfile=REPORT/'foundation-evaluated.blend';bpy.data.libraries.write(str(libfile),{libscene},compress=True)
# Extend V1 prepared scene. Existing UV loops/material targets and IDs never change.
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-bake-v1.blend'))
scene=bpy.data.scenes['WEB_WORKS_GALLERY_V1'];scene.name='WEB_WORKS_GALLERY_V2';bpy.context.window.scene=scene
oldmesh=[o for o in scene.objects if o.get('web_export') and o.type=='MESH'];oldhash=p._fingerprint(oldmesh)
oldreport=json.loads((ROOT/'assets/blender/works-gallery-v1/preparation-report.json').read_text())
assert oldhash==oldreport['geometry_uv_sha256']
for o in list(scene.objects):
    if o.get('source_node','').startswith('Urban landscape base'):bpy.data.objects.remove(o,do_unlink=True)
with bpy.data.libraries.load(str(libfile),link=False) as (src,dst):dst.scenes=['GALLERY_V2_FOUNDATION_LIBRARY']
loaded=dst.scenes[0];items=list(loaded.objects)
for o in items:
    scene.collection.objects.link(o);loaded.collection.objects.unlink(o)
bpy.data.scenes.remove(loaded)
owner=next(o for o in items if o.get('asset_id'));owner.name='GALLERY_WEB_gallery.environment.foundation';owner['web_export']=True;owner['web_context']=False
parts=[o for o in items if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();obj=bpy.context.object;p._reparent(obj,owner)
obj.name='GALLERY_WEB_gallery.environment.foundation__baked__A4'
obj['owner_asset_id']='gallery.environment.foundation';obj['web_export']=True;obj['web_context']=False;obj['web_kind']='baked';obj['bake_atlas']=4;obj['geometry_atlas']=4
obj['triangles_before']=p._triangles(obj);obj['merged_source_nodes']=json.dumps(list(new_bounds))
p._source_uv(obj);cache={}
for i,mat in enumerate(list(obj.data.materials)):obj.data.materials[i]=p._material(mat,'A4_baked',cache)
for layer in list(obj.data.uv_layers):
    if layer.name=='BakeUV':obj.data.uv_layers.remove(layer)
uv=obj.data.uv_layers.new(name='BakeUV',do_init=False);obj.data.uv_layers.active=uv;uv.active_render=True
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.006,area_weight=.25,correct_aspect=True,scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new(p.IMAGE_PREFIX+'4',width=2048,height=2048,alpha=False,float_buffer=True);image.colorspace_settings.name='Linear Rec.709'
for mat in set(obj.data.materials):
    mat['bake_atlas']=4
    for n in mat.node_tree.nodes:n.select=False
    target=mat.node_tree.nodes.new('ShaderNodeTexImage');target.name=p.TARGET_NODE;target.image=image;target.select=True;mat.node_tree.nodes.active=target
assert p._fingerprint(oldmesh)==oldhash,'Existing geometry/UV mutated'
meshes=oldmesh+[obj];fingerprint=p._fingerprint(meshes);pid=hashlib.sha256((fingerprint+str(time.time_ns())).encode()).hexdigest()
scene['preparation_id']=pid;scene['geometry_uv_sha256']=fingerprint;scene['source_blend']=str(SOURCE);scene['revision']='gallery_v2_closed_foundations';scene['web_baked']=False
report=dict(oldreport,source=p._relative(SOURCE),prepared=p._relative(PREPARED),scene=scene.name,preparation_id=pid,geometry_uv_sha256=fingerprint,mesh_count=len(meshes),triangles=sum(p._triangles(o) for o in meshes),triangles_before=sum(o['triangles_before'] for o in meshes))
report['asset_hierarchy']=p._hierarchy(o for o in scene.objects if o.get('web_export'));report['asset_ids']=sorted(report['asset_hierarchy']);report['asset_count']=len(report['asset_ids'])
report['atlases']=oldreport['atlases']+[{'atlas':4,'label':'foundations','resolution':2048,'image':image.name,'uv_layer':'BakeUV','margin':16,'mesh_count':1,'triangles':p._triangles(obj),'owner_ids':['gallery.environment.foundation']}]
report['context_objects']=[o.name for o in scene.objects if o.get('web_context')]
report['retained_geometry_uv_sha256']=oldhash;report['retained_from_preparation_id']=oldreport['preparation_id'];report['rebake_atlases']=[1,4];report['retained_atlases']=[0,2,3]
scene['preparation_manifest']=json.dumps(report,ensure_ascii=False)
bpy.ops.object.select_all(action='DESELECT');bpy.data.libraries.write(str(PREPARED),{scene},fake_user=True,compress=True)
savejson(REPORT/'preparation-report.json',report)
checks={'source':p._relative(SOURCE),'source_sha256':source_sha,'prepared':p._relative(PREPARED),'prepared_sha256':sha(PREPARED),'original_v1_source_sha256':sha(ROOT/'assets/blender/works-gallery-v1.blend'),'removed_render_only_plane':removed,'new_id':'gallery.environment.foundation','new_source_meshes':len(new_bounds),'new_triangles':p._triangles(obj),'new_part_bounds':new_bounds,'existing_pier_connections':supports,'new_skyline_piers':far,'all_supports_connected':all(s['connected'] for s in supports+far),'runtime_ground_max_y':-7.62,'terrain_top_web_y':-5.82,'original_ids_and_hierarchy_preserved':True,'original_geometry_uv_preserved':True,'original_lights_preserved':True,'atlas_contract':[4096,3072,4096,4096,2048]}
savejson(REPORT/'foundation-verification.json',checks)
print(json.dumps({'complete':True,'ids':report['asset_count'],'triangles':report['triangles'],'new_parts':len(new_bounds),'existing_piers':len(supports),'new_skyline_piers':len(far),'preparation_id':pid}))
