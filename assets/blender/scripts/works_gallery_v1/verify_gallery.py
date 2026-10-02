"""Inspect actual evaluated Blender geometry and approved scene structure."""
import bpy,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def run():
    s=bpy.data.scenes['WORKS_GALLERY_V1'];bpy.context.window.scene=s;s.view_layers[0].update();dg=bpy.context.evaluated_depsgraph_get()
    ids={};dups=[];triangles=0;mesh_count=0;nonfinite=[];atlases={str(i):{'objects':0,'triangles':0} for i in range(4)}
    for o in s.objects:
        if o.get('asset_id'):
            ident=o['asset_id']
            if ident in ids:dups.append(ident)
            ids[ident]={'name':o.name,'type':o.type,'pivot':list(o.matrix_world.translation)}
        if o.type not in {'MESH','CURVE','FONT'} or o.hide_render or o.get('export_exclude'):continue
        ev=o.evaluated_get(dg);me=ev.to_mesh()
        try:
            n=sum(max(0,len(p.vertices)-2) for p in me.polygons);triangles+=n;mesh_count+=1
            if any(not math.isfinite(c) for v in me.vertices for c in v.co):nonfinite.append(o.name)
            ancestor=o
            while ancestor and 'bake_atlas' not in ancestor:ancestor=ancestor.parent
            if ancestor:
                a=atlases[str(ancestor['bake_atlas'])];a['objects']+=1;a['triangles']+=n
        finally:ev.to_mesh_clear()
    works=['gallery.work.%02d'%i for i in range(1,7)]
    missing=[k for k in works if k not in ids]
    assert not dups and not missing and not nonfinite,(dups,missing,nonfinite)
    original=ROOT/'public/models/orbital-atelier-v14.glb';digest=hashlib.sha256(original.read_bytes()).hexdigest()
    assert digest=='a933ce1ba865c5ad5293e11bfac51ad082f8c1522ff828ad89d45aa17bd5e232'
    report={'status':'passed','scene':s.name,'objects':len(s.objects),'independentAssetIDs':len(ids),'workStations':works,'duplicateIDs':dups,'nonfiniteGeometry':nonfinite,'evaluatedMeshObjects':mesh_count,'evaluatedTrianglesBeforeWebPreparation':triangles,'atlasesPlanned':atlases,'sourceBytes':(ROOT/'assets/blender/works-gallery-v1.blend').stat().st_size,'sourceSha256':hashlib.sha256((ROOT/'assets/blender/works-gallery-v1.blend').read_bytes()).hexdigest(),'originalRoomGLBUnchanged':True,'originalRoomGLBSha256':digest,'limits':['Counts reflect editable source, not runtime performance.','No exhaustive inter-object collision proof.','Web bakes and scene transition have not been executed or approved.'],'ids':ids}
    (ROOT/'assets/blender/works-gallery-v1/geometry-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='ids'},ensure_ascii=False));return report
if __name__=='__main__':run()
