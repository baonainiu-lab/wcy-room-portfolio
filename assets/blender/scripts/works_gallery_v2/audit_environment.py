import bpy,json,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[4];p=ROOT/'assets/blender/works-gallery-v1.blend';bpy.ops.wm.open_mainfile(filepath=str(p));s=bpy.data.scenes['WORKS_GALLERY_V1'];bpy.context.window.scene=s;bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();rows=[]
for o in s.objects:
 if o.type not in ('MESH','CURVE'):continue
 parent=o
 while parent and not parent.get('asset_id'):parent=parent.parent
 if not parent or not str(parent.get('asset_id','')).startswith('gallery.environment'):continue
 ev=o.evaluated_get(dg);m=ev.to_mesh()
 if not m or not len(m.vertices):continue
 points=[ev.matrix_world@v.co for v in m.vertices];lo=[min(v[i] for v in points) for i in range(3)];hi=[max(v[i] for v in points) for i in range(3)]
 rows.append({'name':o.name,'source':o.get('source_original_city'),'owner':parent['asset_id'],'type':o.type,'min':lo,'max':hi,'triangles':sum(len(f.vertices)-2 for f in m.polygons),'excluded':bool(o.get('export_exclude'))});ev.to_mesh_clear()
report={'source':str(p.relative_to(ROOT)),'objects':rows,'nameFamilies':Counter(re.sub(r'[._-]?\d+','',r['source'] or r['name']) for r in rows)}
(ROOT/'assets/blender/works-gallery-v2/environment-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'families':report['nameFamilies'],'structural':[r for r in rows if any(x in r['name'].lower() for x in ('platform','deck','bridge','pillar','terrain','base','terrace','road'))]},indent=2))
