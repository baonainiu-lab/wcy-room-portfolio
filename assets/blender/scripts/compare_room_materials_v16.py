"""Read-only material-slot, authored-color and texture-source comparison."""
import bpy,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[3];records=[]
for rev in [15,16]:
 p=R/f'assets/blender/orbital-dual-bake-v{rev}.blend';bpy.ops.wm.open_mainfile(filepath=str(p));s=bpy.data.scenes['WEB_DUAL_V8'];mats={m for o in s.objects if o.type=='MESH' and o.get('web_export') for m in o.data.materials if m};rows=[]
 for m in sorted(mats,key=lambda m:m.name):
  if not m.use_nodes:continue
  pbr=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
  if not pbr:continue
  rows.append({'material':m.name,'materialRevision':m.get('material_revision'),'normalLinked':pbr.inputs['Normal'].is_linked,'roughnessLinked':pbr.inputs['Roughness'].is_linked,'authoredBaseColor':list(pbr.inputs['Base Color'].default_value),'textures':[{'name':n.image.name,'size':list(n.image.size),'path':n.image.filepath} for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.name!='WEB8_BAKE_TARGET']})
 records.append({'revision':rev,'source':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'materials':rows,'normalLinked':sum(x['normalLinked'] for x in rows),'roughnessLinked':sum(x['roughnessLinked'] for x in rows),'changedMaterialCount':sum(x['materialRevision']==16 for x in rows)})
old={x['material']:x for x in records[0]['materials']};new={x['material']:x for x in records[1]['materials']};assert set(old)==set(new)
color_changes=[k for k in old if old[k]['authoredBaseColor']!=new[k]['authoredBaseColor']];assert not color_changes
out=R/'assets/blender/photoreal-materials-v16-comparison.json';out.write_text(json.dumps({'complete':True,'materialSlotsAndNamesUnchanged':True,'authoredColorsUnchanged':True,'states':records},indent=2)+'\n')
print('ROOM_MATERIAL_COMPARISON',json.dumps([{k:v for k,v in r.items() if k!='materials'} for r in records]))
