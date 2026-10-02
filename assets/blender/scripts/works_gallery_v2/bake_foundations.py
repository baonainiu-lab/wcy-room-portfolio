"""Actual Cycles V2 contact lighting; retain byte-identical V1 interior atlases."""
import bpy,sys,json,shutil,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OLD=ROOT/'assets/blender/scripts/works_gallery_v1';sys.path.insert(0,str(OLD))
import bake_gallery as b
b.SCENE_NAME='WEB_WORKS_GALLERY_V2';b.PREPARED=ROOT/'assets/blender/works-gallery-bake-v2.blend'
b.OUT=ROOT/'public/textures/works-gallery-v2';b.REPORTS=ROOT/'assets/blender/works-gallery-v2';b.ATLAS_SIZES=(4096,3072,4096,4096,2048)
b.OUT.mkdir(parents=True,exist_ok=True)
prep=json.loads((b.REPORTS/'preparation-report.json').read_text())
for state in ('day','night'):
    scene,lighting=b.setup_state(state);scene.cycles.samples=64;scene.cycles.adaptive_threshold=.025;lighting['samples']=64
    records={};old=json.loads((ROOT/f'public/textures/works-gallery-v1/{state}-manifest.json').read_text())
    for i in (0,2,3):
        oldrec=next(r for r in old['atlases'] if r['atlas']==i)
        src=ROOT/oldrec['path'];dst=b.OUT/f'{state}-{i}.png';shutil.copy2(src,dst)
        assert b._hash(src)==b._hash(dst)==oldrec['sha256']
        records[i]=dict(oldrec,path=b._relative(dst),retained_from_preparation_id=old['preparation_id'],retained_original_geometry_uv_sha256=prep['retained_geometry_uv_sha256'],rebaked=False)
    manifest={'state':state,'preparation_id':scene['preparation_id'],'prepared':b._relative(b.PREPARED),'scene':b.SCENE_NAME,'lighting':lighting,'complete':False,'atlases':[records[i] for i in sorted(records)],'retained_atlases':[0,2,3],'rebaked_atlases':[1,4]}
    b._json(b.OUT/f'{state}-manifest.json',manifest)
    started=time.monotonic()
    for i in (1,4):
        b._json(b.REPORTS/f'bake-{state}-progress.json',dict(manifest,phase='baking',current_atlas=i))
        records[i]=b._bake_atlas(scene,i,b.OUT/f'{state}-{i}.png',lighting);records[i]['rebaked']=True;records[i]['samples']=64
        manifest['atlases']=[records[j] for j in sorted(records)];manifest['complete']=len(records)==5;manifest['seconds']=round(time.monotonic()-started,2)
        b._json(b.OUT/f'{state}-manifest.json',manifest)
        print(json.dumps({'state':state,'atlas':i,'complete':manifest['complete'],'seconds':records[i]['seconds']}),flush=True)
    b._json(b.REPORTS/f'bake-{state}-progress.json',dict(manifest,phase='complete',current_atlas=None))
