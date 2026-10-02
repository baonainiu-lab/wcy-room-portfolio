"""Retain original interior maps, rebake only the clean thin gallery terrace."""
import bpy,sys,json,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
import bake_gallery as b
b.SCENE_NAME='WEB_WORKS_GALLERY_V3';b.PREPARED=ROOT/'assets/blender/works-gallery-bake-v3.blend';b.OUT=ROOT/'public/textures/works-gallery-v3';b.REPORTS=ROOT/'assets/blender/works-gallery-v3';b.ATLAS_SIZES=(4096,4096,4096,1024);b.OUT.mkdir(parents=True,exist_ok=True)
prep=json.loads((b.REPORTS/'preparation-report.json').read_text())
for state in ('day','night'):
    scene,lighting=b.setup_state(state);scene.cycles.samples=64;scene.cycles.adaptive_threshold=.025;lighting['samples']=64
    old=json.loads((ROOT/f'public/textures/works-gallery-v1/{state}-manifest.json').read_text());records={}
    for old_i,new_i in ((0,0),(2,1),(3,2)):
        oldrec=next(r for r in old['atlases'] if r['atlas']==old_i);src=ROOT/oldrec['path'];dst=b.OUT/f'{state}-{new_i}.png';shutil.copy2(src,dst);assert b._hash(src)==b._hash(dst)==oldrec['sha256']
        records[new_i]=dict(oldrec,atlas=new_i,path=b._relative(dst),original_atlas=old_i,retained_from_preparation_id=old['preparation_id'],rebaked=False)
    manifest={'state':state,'preparation_id':scene['preparation_id'],'prepared':b._relative(b.PREPARED),'scene':b.SCENE_NAME,'lighting':lighting,'complete':False,'atlases':[records[i] for i in sorted(records)],'retained_atlases':[0,1,2],'rebaked_atlases':[3]}
    b._json(b.OUT/f'{state}-manifest.json',manifest);b._json(b.REPORTS/f'bake-{state}-progress.json',dict(manifest,phase='baking',current_atlas=3))
    records[3]=b._bake_atlas(scene,3,b.OUT/f'{state}-3.png',lighting);records[3]['rebaked']=True;records[3]['samples']=64;manifest['atlases']=[records[i] for i in sorted(records)];manifest['complete']=True
    b._json(b.OUT/f'{state}-manifest.json',manifest);b._json(b.REPORTS/f'bake-{state}-progress.json',dict(manifest,phase='complete'));print(json.dumps({'state':state,'seconds':records[3]['seconds'],'complete':True}),flush=True)
