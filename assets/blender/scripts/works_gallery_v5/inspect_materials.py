import bpy, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
result={}
for fname,sname in [('works-gallery-v4.blend','WORKS_GALLERY_V4'),('works-gallery-bake-v4.blend','WEB_WORKS_GALLERY_V4')]:
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender'/fname))
    scene=bpy.data.scenes[sname]
    mats={m for o in scene.objects if hasattr(o.data,'materials') for m in o.data.materials if m}
    result[fname]={'scene':dict(scene.items()),'materials':[{'name':m.name,'properties':dict(m.items()),'nodes':[(n.name,n.type) for n in m.node_tree.nodes] if m.use_nodes else [],'users':[o.name for o in scene.objects if hasattr(o.data,'materials') and m in list(o.data.materials)][:8]} for m in sorted(mats,key=lambda m:m.name)]}
    result[fname]['assets']=[{'id':o.get('asset_id'),'name':o.name,'location':list(o.matrix_world.translation),'dimensions':list(o.dimensions)} for o in scene.objects if o.get('asset_id')]
path=ROOT/'assets/blender/works-gallery-v5/material-inventory-before.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print('REPORT',path)
