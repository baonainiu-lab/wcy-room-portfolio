"""CPU-only audit of saved V5 source/proxy-invariant scan projections."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];records=[]
for stem,scene_name in [('works-gallery','WORKS_GALLERY_V4'),('works-gallery-bake','WEB_WORKS_GALLERY_V4')]:
    path=ROOT/'assets/blender'/f'{stem}-v5.blend';before=hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.data.scenes[scene_name]
    materials={m for o in scene.objects if hasattr(o.data,'materials') for m in o.data.materials if m and m.get('maps')}
    rows=[]
    for mat in materials:
        tree=mat.node_tree;images=[n for n in tree.nodes if n.type=='TEX_IMAGE' and n.name!='GALLERY_BAKE_TARGET']
        assert len(images)==9 and all(n.projection=='FLAT' and n.inputs['Vector'].is_linked for n in images)
        assert not any(n.type in {'TEX_COORD','VECT_TRANSFORM'} for n in tree.nodes)
        geometry=next(n for n in tree.nodes if n.type=='NEW_GEOMETRY')
        assert geometry.outputs['Position'].is_linked and geometry.outputs['Normal'].is_linked
        absolute=geometry.outputs['Normal'].links[0].to_node;assert absolute.type=='VECT_MATH' and absolute.operation=='ABSOLUTE'
        split=absolute.outputs[0].links[0].to_node;assert split.type=='SEPXYZ'
        for channel in 'XYZ':
            power=split.outputs[channel].links[0].to_node
            assert power.operation=='POWER' and power.inputs[1].default_value==6
        assert sum(n.type=='MATH' and n.operation=='DIVIDE' for n in tree.nodes)==3
        rows.append({'material':mat.name,'scanSamples':9,'projection':'3 FLAT world-coordinate planes per map','weights':'Geometry.Normal WORLD -> abs -> power6 -> normalized sum','objectSpaceNodes':0})
    assert rows and hashlib.sha256(path.read_bytes()).hexdigest()==before
    records.append({'path':str(path.relative_to(ROOT)),'unchangedSha256':before,'materials':rows})
report={'complete':True,'sourceAndPreparedUseSameWorldCoordinateContract':True,'BOXProjectionCount':0,'objectNormalProjectionCount':0,'files':records,'gpuUsed':False}
(ROOT/'assets/blender/works-gallery-v5/world-triplanar-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'complete':True,'materialsPerFile':[len(r['materials'])for r in records],'BOX':0,'objectNormals':0,'gpuUsed':False}))
