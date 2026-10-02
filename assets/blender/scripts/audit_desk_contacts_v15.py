import bpy,json,sys
from pathlib import Path
from mathutils.bvhtree import BVHTree
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from refine_edge_atlas_v14 import bounds
s=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=s;bpy.context.view_layer.update()
meshes=[o for o in s.objects if o.type=='MESH' and o.get('web_export')]
desk=next(o for o in meshes if o.get('owner_asset_id')=='furniture.desk')
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons],epsilon=.000001)
dt=tree(desk);dlo,dhi=bounds(desk,range(len(desk.data.polygons)));results=[]
for o in meshes:
 if o==desk or o.get('owner_asset_id')=='room_static':continue
 lo,hi=bounds(o,range(len(o.data.polygons)))
 if not all(hi[i]>=dlo[i] and lo[i]<=dhi[i] for i in range(3)):continue
 hits=dt.overlap(tree(o))
 
 desk_hit_z=[(desk.matrix_world@desk.data.vertices[v].co).z for di,oi in hits for v in desk.data.polygons[di].vertices]
 prop_hit_z=[(o.matrix_world@o.data.vertices[v].co).z for di,oi in hits for v in o.data.polygons[oi].vertices]
 results.append({'deskHitZRange':[min(desk_hit_z),max(desk_hit_z)] if hits else None,'propHitZRange':[min(prop_hit_z),max(prop_hit_z)] if hits else None,'name':o.name,'owner':o.get('owner_asset_id'),'min':list(lo),'max':list(hi),'intersectionFaces':len(hits),'boundsOverlapsDesk':True})
report={'desk':{'name':desk.name,'min':list(dlo),'max':list(dhi)},'tests':results,'method':'World-space BVH triangle surface intersections on actual prepared mesh, epsilon 1e-6. AABB prefilter. Geometric surface contact may appear as overlap.'}
(ROOT/'assets/blender/desk-collision-v15-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
