"""V3 removes the city in new copies; reuses untouched gallery UV and remaps atlases."""
import bpy,bmesh,sys,json,hashlib,time,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
import prepare_gallery as p
REPORT=ROOT/'assets/blender/works-gallery-v3';SOURCE=ROOT/'assets/blender/works-gallery-v3.blend';PREPARED=ROOT/'assets/blender/works-gallery-bake-v3.blend'
MAP={0:0,2:1,3:2,1:3};SIZES=[4096,4096,4096,1024]
remove_ids={'gallery.environment.city'}|{'gallery.environment.plant.%02d'%i for i in range(8)}
def write(name,r):(REPORT/name).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def owner(o):
    while o:
        if o.get('asset_id'):return str(o['asset_id'])
        o=o.parent
    return None
def delete_city(scene):
    doomed=[o for o in scene.objects if owner(o) in remove_ids or o.get('owner_asset_id') in remove_ids or 'Urban landscape base' in o.name]
    names=[o.name for o in doomed]
    for o in doomed:bpy.data.objects.remove(o,do_unlink=True)
    return names
def geom_hash(o):
    h=hashlib.sha256()
    for row in o.matrix_world:h.update(str(tuple(row)).encode())
    for v in o.data.vertices:h.update(str(tuple(v.co)).encode())
    for poly in o.data.polygons:h.update(str(tuple(poly.vertices)).encode())
    for layer in o.data.uv_layers:
        if layer.name=='BakeUV':
            for l in layer.data:h.update(str(tuple(l.uv)).encode())
    return h.hexdigest()
# Editable source: original hall, thin terrace, exhibits and local plants/lights only.
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v1.blend'))
s=bpy.data.scenes['WORKS_GALLERY_V1'];bpy.context.window.scene=s;s.name='WORKS_GALLERY_V3'
source_deleted=delete_city(s)
for o in s.objects:
    if 'bake_atlas' in o and int(o['bake_atlas']) in MAP:o['bake_atlas']=MAP[int(o['bake_atlas'])]
s['model_revision']=3;s['environment_removed']=True;s['source_revision']='V1 gallery retained; city and external garden removed by user request'
bpy.data.libraries.write(str(SOURCE),{s},fake_user=True,compress=True)
# Prepared copy: measure direct environment shadows before deleting, then retain UVs.
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-bake-v1.blend'))
s=bpy.data.scenes['WEB_WORKS_GALLERY_V1'];bpy.context.window.scene=s
oldreport=json.loads((ROOT/'assets/blender/works-gallery-v1/preparation-report.json').read_text())
oldmesh=[o for o in s.objects if o.type=='MESH' and o.get('web_export')];assert p._fingerprint(oldmesh)==oldreport['geometry_uv_sha256']
retained={o.name:geom_hash(o) for o in oldmesh if o.get('owner_asset_id') not in remove_ids and o.get('geometry_atlas')!=1}
verts=[];faces=[]
for o in oldmesh:
    if o.get('owner_asset_id') in remove_ids:
        start=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices);faces.extend(tuple(start+i for i in f.vertices) for f in o.data.polygons)
bvh=BVHTree.FromPolygons(verts,faces,all_triangles=False)
sun=next(o for o in s.objects if o.type=='LIGHT' and o.data.type=='SUN');direction=(sun.matrix_world.to_quaternion()@Vector((0,0,1))).normalized()
probes=[Vector((x,y,z)) for x in (-6,-4,-2,0,2,4,6) for y in (-3,-1.5,0,1.5,3) for z in (.19,1,2,3.5)]
hits=[]
for point in probes:
    hit=bvh.ray_cast(point+direction*.002,direction,300)
    if hit[0] is not None:hits.append({'point':list(point),'hit':list(hit[0]),'distance':hit[3]})
write('lighting-impact-audit.json',{'probe_count':len(probes),'sun_direction':list(direction),'removed_environment_direct_sun_occlusion_count':len(hits),'hits':hits,'retained_lights':'all original local light positions/powers/materials preserved','indirect_limit':'Old A0/A2/A3 bake includes V1 indirect environment contribution. Removing the remote city may change subtle indirect bounce; no claim of mathematically identical global illumination. The user requested a fast clean gallery preview; original interior maps retain approved light and shadow appearance.'})
prepared_deleted=delete_city(s);s.name='WEB_WORKS_GALLERY_V3'
# Remap old atlas images without colliding with existing datablock names.
for i in range(4):bpy.data.images[p.IMAGE_PREFIX+str(i)].name='V1_ORIGINAL_ATLAS_'+str(i)
for old,new in MAP.items():
    if old==1:continue
    bpy.data.images['V1_ORIGINAL_ATLAS_'+str(old)].name=p.IMAGE_PREFIX+str(new)
for o in s.objects:
    if 'bake_atlas' in o and int(o['bake_atlas']) in MAP:o['bake_atlas']=MAP[int(o['bake_atlas'])]
    if 'geometry_atlas' in o:o['geometry_atlas']=MAP[int(o['geometry_atlas'])]
meshes=[o for o in s.objects if o.type=='MESH' and o.get('web_export')]
for o in meshes:
    if o.name in retained:assert geom_hash(o)==retained[o.name]
# Thin terrace gets a small dedicated atlas; no city pixels survive.
members=[o for o in meshes if o.get('web_kind')=='baked' and o.get('bake_atlas')==3]
assert len(members)==1 and members[0]['owner_asset_id']=='gallery.environment.terrace'
bpy.ops.object.select_all(action='DESELECT')
for o in members:
    o.select_set(True);uv=o.data.uv_layers.get('BakeUV')
    if uv:o.data.uv_layers.remove(uv)
    uv=o.data.uv_layers.new(name='BakeUV',do_init=False);o.data.uv_layers.active=uv;uv.active_render=True
bpy.context.view_layer.objects.active=members[0];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.012,area_weight=.25,correct_aspect=True,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
img=bpy.data.images.new(p.IMAGE_PREFIX+'3',width=1024,height=1024,alpha=False,float_buffer=True);img.colorspace_settings.name='Linear Rec.709'
for o in meshes:
    for mat in o.data.materials:
        if mat is None:continue
        if o.get('web_kind')=='baked':
            atlas=int(o['bake_atlas']);mat['bake_atlas']=atlas
            target=mat.node_tree.nodes.get(p.TARGET_NODE);assert target is not None
            target.image=bpy.data.images[p.IMAGE_PREFIX+str(atlas)];mat.node_tree.nodes.active=target
# Prove the thin deck's closed solid and retain all original bottom faces.
terrace=members[0];bm=bmesh.new();bm.from_mesh(terrace.data);components=[];seen=set()
for v in bm.verts:
    if v in seen:continue
    stack=[v];component=set()
    while stack:
        q=stack.pop()
        if q in seen:continue
        seen.add(q);component.add(q)
        for e in q.link_edges:stack.append(e.other_vert(q))
    edges={e for q in component for e in q.link_edges};points=[terrace.matrix_world@q.co for q in component]
    if points:
        lo=[min(q[i] for q in points) for i in range(3)];hi=[max(q[i] for q in points) for i in range(3)]
        components.append({'bounds':[lo,hi],'vertices':len(component),'boundary_edges':sum(e.is_boundary for e in edges),'non_manifold_edges':sum(not e.is_manifold for e in edges)})
bm.free();deck=next(c for c in components if c['bounds'][1][0]-c['bounds'][0][0]>22 and c['bounds'][0][2]<-.8);assert deck['boundary_edges']==deck['non_manifold_edges']==0
hierarchy=p._hierarchy(o for o in s.objects if o.get('web_export'));expected={k:v for k,v in oldreport['asset_hierarchy'].items() if k not in remove_ids};assert hierarchy==expected and len(hierarchy)==77
fp=p._fingerprint(meshes);pid=hashlib.sha256((fp+str(time.time_ns())).encode()).hexdigest();s['preparation_id']=pid;s['geometry_uv_sha256']=fp;s['source_blend']=str(SOURCE);s['web_baked']=False;s['revision']='v3_gallery_only'
reports=[]
for i,(label,size) in enumerate(zip(('architecture','exhibits','furnishings','thin_terrace'),SIZES)):
    ms=[o for o in meshes if o.get('web_kind')=='baked' and o.get('bake_atlas')==i]
    reports.append({'atlas':i,'label':label,'resolution':size,'image':p.IMAGE_PREFIX+str(i),'uv_layer':'BakeUV','margin':16,'mesh_count':len(ms),'triangles':sum(p._triangles(o) for o in ms),'owner_ids':sorted({o['owner_asset_id'] for o in ms})})
verts=[o.matrix_world@v.co for o in meshes for v in o.data.vertices];lo=[min(v[i] for v in verts) for i in range(3)];hi=[max(v[i] for v in verts) for i in range(3)]
report=dict(oldreport,source=p._relative(SOURCE),prepared=p._relative(PREPARED),scene=s.name,preparation_id=pid,geometry_uv_sha256=fp,atlases=reports,mesh_count=len(meshes),triangles=sum(p._triangles(o) for o in meshes),asset_count=len(hierarchy),asset_ids=sorted(hierarchy),asset_hierarchy=hierarchy,context_objects=[o.name for o in s.objects if o.get('web_context')],glass_meshes=[o.name for o in meshes if o.get('web_kind')=='glass'],removed_ids=sorted(remove_ids),retained_atlas_map={'0':0,'2':1,'3':2},retained_preparation_id=oldreport['preparation_id'],rebaked_atlases=[3])
report['triangles_before']=report['triangles'];s['preparation_manifest']=json.dumps(report,ensure_ascii=False);bpy.ops.object.select_all(action='DESELECT');bpy.data.libraries.write(str(PREPARED),{s},fake_user=True,compress=True);write('preparation-report.json',report)
write('deletion-verification.json',{'complete':True,'removed_ids':sorted(remove_ids),'remaining_ids':sorted(hierarchy),'portal_preserved':'gallery.architecture.portal' in hierarchy,'source_objects_removed':len(source_deleted),'prepared_objects_removed':len(prepared_deleted),'retained_non_terrace_mesh_geometry_uv_hashes':retained,'closed_thin_terrace_component':deck,'blender_bounds':{'min':lo,'max':hi},'web_bounds':{'min':[lo[0],lo[2],-hi[1]],'max':[hi[0],hi[2],-lo[1]]},'native_floor_y':-.88,'stage_offset_y_for_room_ground_minus_1_065':-1.065-lo[2]+.025,'stage_clearance_above_room_ground':.025,'removed_ids_relative_to_v2':sorted(remove_ids|{'gallery.environment.foundation'}),'atlas_sizes':SIZES,'triangles':report['triangles'],'mesh_count':len(meshes),'asset_count':len(hierarchy),'removed_environment_direct_sun_occlusion_count':len(hits)})
print(json.dumps({'complete':True,'ids':len(hierarchy),'triangles':report['triangles'],'min_z':lo[2],'direct_shadow_hits':len(hits),'pid':pid}))
