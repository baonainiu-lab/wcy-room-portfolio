"""Verify only the work chair geometry changed during the V15 finishing pass."""
import json,hashlib
from pathlib import Path
from validate_texture_precision_v15 import glb,structure,stats,png
ROOT=Path(__file__).resolve().parents[3]
old,ob=glb(ROOT/'assets/blender/v15-pre-chair/orbital-atelier-v15.glb');new,nb=glb(ROOT/'public/models/orbital-atelier-v15.glb')
assert structure(old)==structure(new);assert stats(new)['triangles']==413855;assert stats(new)['drawPrimitives']==102

def streams(doc,blob):
 result={}
 for node in doc['nodes']:
  if 'mesh' not in node:continue
  rows=[]
  for p in doc['meshes'][node['mesh']]['primitives']:
   row={}
   for kind,idx in {**p['attributes'],'INDICES':p['indices']}.items():
    a=doc['accessors'][idx];v=doc['bufferViews'][a['bufferView']];start=v.get('byteOffset',0)+a.get('byteOffset',0)
    width={5121:1,5123:2,5125:4,5126:4}[a['componentType']]*{'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];stride=v.get('byteStride',width)
    raw=b''.join(blob[start+i*stride:start+i*stride+width] for i in range(a['count']))
    row[kind]=hashlib.sha256(raw).hexdigest()
   rows.append(row)
  result[node['name']]=rows
 return result
oldstreams=streams(old,ob);newstreams=streams(new,nb);changed=[name for name in oldstreams if oldstreams[name]!=newstreams[name]]
assert changed==['WEB8_furniture.work_chair__baked__A1'],changed
checks=[png(ROOT/f'public/textures/lighting-v15/{s}-11.png') for s in ('day','night')];assert all(r['resolution']==[3072,3072] for r in checks)
p=ROOT/'public/models/orbital-atelier-v15.glb';report={'complete':True,'stableIds':len(structure(new)),'hierarchyAndTransformsUnchanged':True,'changedGeometryNodes':changed,'unchangedGeometryNodes':len(oldstreams)-len(changed),'before':stats(old),'after':stats(new),'images':checks,'modelSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'modelBytes':p.stat().st_size}
(ROOT/'assets/blender/work-chair-v15-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
