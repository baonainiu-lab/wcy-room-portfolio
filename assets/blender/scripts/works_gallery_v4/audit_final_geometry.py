import bpy,bmesh,json,hashlib,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[4];source=root/'assets/blender/works-gallery-v4.blend';before=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source));s=bpy.data.scenes['WORKS_GALLERY_V4'];bpy.context.window.scene=s;s.cycles.device='CPU';dg=bpy.context.evaluated_depsgraph_get()
name='V4 unified continuous structural shell';o=s.objects[name];ev=o.evaluated_get(dg);me=ev.to_mesh();me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me);components=[];seen=set()
for v in bm.verts:
 if v in seen:continue
 vs=set();stack=[v]
 while stack:
  q=stack.pop()
  if q in seen:continue
  seen.add(q);vs.add(q);stack.extend(e.other_vert(q) for e in q.link_edges)
 es={e for q in vs for e in q.link_edges};fs={f for q in vs for f in q.link_faces};points=[o.matrix_world@q.co for q in vs]
 components.append({'vertices':len(vs),'faces':len(fs),'boundary_edges':sum(e.is_boundary for e in es),'non_manifold_edges':sum(not e.is_manifold for e in es),'bounds':{'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]}})
report={'source_sha256':before,'shell':{'object':name,'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'components':components,'component_count':len(components),'boundary_edges':sum(e.is_boundary for e in bm.edges),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'zero_length_edges':sum(e.calc_length()<1e-8 for e in bm.edges)},'canopy':[]}
bm.free();ev.to_mesh_clear()
# Audit evaluated vertices against the actual rounded outer back/side silhouettes.
# Back exterior top: center Z2.77, half-height2.64, half-width7.57, radius1.10.
# Side exterior top: center Y.59/Z2.77, half-width3.03, half-height2.64, radius.98.
def rounded_top(u,c,hw,hh,r):
 a=abs(u-c)
 if a>hw+1e-6:return float('-inf')
 if a<=hw-r:return 2.77+hh
 return 2.77+hh-r+math.sqrt(max(0,r*r-(a-(hw-r))**2))
for name in ['V4 solid canopy glass 00','V4 solid canopy glass 05']:
 o=s.objects[name];ev=o.evaluated_get(dg);me=ev.to_mesh();p=[o.matrix_world@v.co for v in me.vertices];verts=[o.matrix_world@v.co for v in o.data.vertices]
 rear=[v for v in p if v.y>=3.23-1e-6];side=[v for v in p if abs(v.x)>=7.13-1e-6]
 backclear=[rounded_top(v.x,0,7.57,2.64,1.10)-v.z for v in rear];sideclear=[rounded_top(v.y,.59,3.03,2.64,.98)-v.z for v in side]
 # Includes every evaluated corner and samples each evaluated edge, catching bevel overshoots.
 samples=list(p)
 for e in me.edges:
  a,b=(p[i] for i in e.vertices)
  samples.extend(a.lerp(b,t/8) for t in range(1,8))
 crossing=[v for v in samples if v.y>=3.23-1e-6]
 crossingclear=[rounded_top(v.x,0,7.57,2.64,1.10)-v.z for v in crossing]
 rec={'name':name,'source_vertices':len(verts),'source_top_footprint':[[round(q.x,6),round(q.y,6),round(q.z,6)] for q in verts[:len(verts)//2]],'evaluated_bounds':{'min':[min(q[i] for q in p) for i in range(3)],'max':[max(q[i] for q in p) for i in range(3)]},'back_region_min_clearance_to_outer_top_m':min(crossingclear),'side_region_min_clearance_to_outer_top_m':min(sideclear),'back_region_outside_outer_top_samples':sum(q<-.0001 for q in crossingclear),'back_region_samples':len(crossing),'max_x_inside_side_outer_plane_m':7.57-max(abs(v.x) for v in p),'max_y_inside_back_outer_plane_m':3.62-max(v.y for v in p)}
 report['canopy'].append(rec);ev.to_mesh_clear()
report['source_unchanged']=before==hashlib.sha256(source.read_bytes()).hexdigest();report['rendered']=False;report['gpu_requested']=False
output=root/'assets/blender/works-gallery-v4/geometry-final-audit.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
