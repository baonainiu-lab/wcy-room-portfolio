import bpy,math,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
P=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio');s=bpy.context.scene;dg=bpy.context.evaluated_depsgraph_get()
model=[]
for c in bpy.data.collections:
    if c.name.startswith(('01_','02_','03_','04_')):model.extend(c.objects)
model=list(set(model));points=[];render_tri=0;bad=[];tiny={}
world_min=np.array([float('inf')]*3);world_max=-world_min.copy()
proj_min=np.array([float('inf')]*2);proj_max=-proj_min.copy()
camproj=np.array(s.camera.calc_matrix_camera(dg,x=s.render.resolution_x,y=s.render.resolution_y)@s.camera.matrix_world.inverted(),dtype=float)
for o in model:
    if o.type not in ['MESH','CURVE','FONT']:continue
    e=o.evaluated_get(dg);me=e.to_mesh();me.calc_loop_triangles();render_tri+=len(me.loop_triangles)
    for v in me.vertices:
        if not all(math.isfinite(a) for a in v.co):bad.append(o.name);break
    deg=0
    for f in me.loop_triangles:
        a,b,c=(me.vertices[i].co for i in f.vertices)
        if (b-a).cross(c-a).length*.5<1e-15:deg+=1
    if deg:tiny[o.name]=deg
    coords=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',coords)
    coords=coords.reshape(-1,3);hm=np.ones((len(coords),4));hm[:,:3]=coords
    wp=hm@np.array(e.matrix_world,dtype=float).T
    if len(wp):
        world_min=np.minimum(world_min,wp[:,:3].min(axis=0));world_max=np.maximum(world_max,wp[:,:3].max(axis=0))
        cp=wp@camproj.T;xy=(cp[:,:2]/cp[:,3:4]+1)/2
        proj_min=np.minimum(proj_min,xy.min(axis=0));proj_max=np.maximum(proj_max,xy.max(axis=0))
    e.to_mesh_clear()
mins=world_min.tolist();maxs=world_max.tolist()
frame={'xmin':float(proj_min[0]),'xmax':float(proj_max[0]),'ymin':float(proj_min[1]),'ymax':float(proj_max[1])}
frame['widthFraction']=frame['xmax']-frame['xmin'];frame['heightFraction']=frame['ymax']-frame['ymin']
roots=[o for o in model if o.get('asset_id')];ids=[o['asset_id'] for o in roots]
missing=[]
for im in bpy.data.images:
    if im.source=='FILE' and not im.packed_file and not Path(bpy.path.abspath(im.filepath)).exists():missing.append(im.filepath)
out={'source':'assets/blender/about-atelier-v3.blend','sourceSha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'blender':bpy.app.version_string,'modelObjectCount':len(model),'independentAssetRoots':len(roots),'interactiveRoots':sum(bool(o.get('interactive')) for o in roots),'stableIdsUnique':len(ids)==len(set(ids)),'evaluatedModelTriangles':render_tri,'invalidGeometry':bad,'zeroAreaTriangles':tiny,'packedImageCount':sum(bool(i.packed_file) for i in bpy.data.images),'missingExternalFiles':missing,'modelBoundsMetres':{'min':mins,'max':maxs,'dimensions':[maxs[i]-mins[i] for i in range(3)]},'heroFraming':frame,'conceptApproved':True,'renderApproval':'pending','websiteIntegrated':False,'notes':['Actual Blender source and Cycles rendering, not the concept image.','Runtime GLB, baking and FPS validation are intentionally pending render approval.','Offline atrium/landscape is in a separate render-context collection.'],'assetIds':sorted(ids)}
(P/'assets/blender/about-atelier-v3-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='assetIds'},ensure_ascii=False))
