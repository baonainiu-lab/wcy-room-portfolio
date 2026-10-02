import bpy,json,sys
from pathlib import Path
from mathutils.bvhtree import BVHTree
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio');sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from refine_edge_atlas_v14 import components,bounds
s=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=s;bpy.context.view_layer.update()
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons],epsilon=.000001)
a=next(o for o in s.objects if o.type=='MESH' and o.get('owner_asset_id')=='furniture.desk');b=next(o for o in s.objects if o.type=='MESH' and o.get('owner_asset_id')=='compute_core' and o.get('web_kind')=='baked')
hits=tree(a).overlap(tree(b));report={'pairs':len(hits),'objects':[]}
for o,axis in ((a,0),(b,1)):
 indices={hit[axis] for hit in hits};found=[]
 for fs in components(o):
  shared=indices.intersection(fs)
  if not shared:continue
  lo,hi=bounds(o,fs);slo,shi=bounds(o,shared)
  found.append({'componentMin':list(lo),'componentMax':list(hi),'intersectingFaces':len(shared),'intersectionFaceMin':list(slo),'intersectionFaceMax':list(shi)})
 report['objects'].append({'name':o.name,'components':found})
(ROOT/'assets/blender/compute-core-foot-contact-v15.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
