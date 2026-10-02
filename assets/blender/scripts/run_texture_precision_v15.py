"""Real Cycles V15 prop bakes; inherited V14 maps/source remain unchanged."""
import argparse, bpy, hashlib, json, shutil, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
PREP=ROOT/'assets/blender/orbital-dual-bake-v15.blend'
OUT=ROOT/'public/textures/lighting-v15'
PREP_REPORT=ROOT/'assets/blender/texture-precision-v15-prepare.json'

def scope_from(path, replacements, name):
    scope={'__name__':name};code=path.read_text()
    for a,b in replacements:code=code.replace(a,b)
    exec(compile(code,str(path), 'exec'),scope);return scope

def copy_retained(bake_inputs=False):
    OUT.mkdir(parents=True,exist_ok=True)
    # Only these unchanged UV/geometry atlases are inherited. Independent
    # images are owned by the native-resolution V15 render manifests.
    for name in (f'{s}-{a}.png' for s in ('day','night') for a in (1,5,6,7)):
        p=ROOT/'public/textures/lighting-v14'/name
        target=OUT/p.name
        if not target.exists():shutil.copy2(p,target)
        assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
    if bake_inputs:
        for state in ('day','night'):
            target=OUT/f'window-{state}.png'
            if not target.exists():shutil.copy2(ROOT/f'public/textures/lighting-v14/window-{state}.png',target)

def bake(state, architecture=False, resume=False):
    copy_retained(bake_inputs=True);bpy.ops.wm.open_mainfile(filepath=str(PREP))
    prepared_hash=hashlib.sha256(PREP.read_bytes()).hexdigest()
    from run_wall_lighting_v10 import configure_day
    warm=scope_from(ROOT/'assets/blender/scripts/night_warm_v13.py',[
        ('night-warm-v13-design.json','night-warm-v15-design.json'),
        ('lighting-night-v13.json','lighting-night-v15.json')],'v15_inherited_night')
    baking=scope_from(ROOT/'assets/blender/scripts/bake_lighting_v8.py',[
        ("OUT = ROOT / 'public/textures/lighting-v8'","OUT = ROOT / 'public/textures/lighting-v15'"),
        ('scene.cycles.samples = 40','scene.cycles.samples = 96'),
        ('scene.cycles.adaptive_threshold = .035','scene.cycles.adaptive_threshold = .01'),
        ('margin = 32 if atlas == 7 else 16','margin = 8 if atlas in (2,9,10) else 16'),
    ],'v15_actual_baker')
    def transform(scene):
        if state=='day':
            import day_sunlight_v9
            day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57)
            configure_day(scene,revision=15)
        else:warm['configure_night_warm'](scene)
        scene.cycles.samples=96;scene.cycles.adaptive_threshold=.01
        p=ROOT/f'assets/blender/lighting-{state}-v15.json';r=json.loads(p.read_text());r['cycles_samples']=96;r['adaptive_threshold']=.01;p.write_text(json.dumps(r,indent=2)+'\n')
    record=baking['bake_state'](state,indices=[0,8] if architecture else [10,3,4] if resume else [9,2,10,3,4],render_preview=False,scene_transform=transform,output_directory=OUT,revision=15)
    record['samples']=96;record['preparedSha256']=prepared_hash
    for r in record['atlases']:
        r['sha256']=hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
        r['preparedSha256']=prepared_hash
        r['windowGeometry']='Repaired window with 25 cm narrower right edge; corrected daylight aperture.'
    if resume:
        retained=json.loads((OUT/f'{state}-v15-desk-retained-manifest.json').read_text())
        for r in retained['atlases']:assert r['sha256']==hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
        record['atlases']=retained['atlases']+record['atlases']
        record['mixedPreparationSnapshots']=True
    record['complete']=True
    (OUT/f'{state}-v15-architecture-manifest.json' if architecture else OUT/f'{state}-v15-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

def export():
    copy_retained()
    repair=json.loads((ROOT/'assets/blender/window-clearance-v15-repair.json').read_text())
    images=json.loads((ROOT/'assets/blender/precision-images-v15-bind-report.json').read_text())
    assert images['complete']
    bound_prepared=next(r for r in images['sources'] if r['source']==str(PREP.relative_to(ROOT)))
    assert bound_prepared['sha256BeforeImageBinding']==repair['preparedAfterWindowRepairSha256']
    assert bound_prepared['sha256AfterImageBinding']==hashlib.sha256(PREP.read_bytes()).hexdigest()
    for r in images['images'].values():assert r['sha256']==hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
    for state in ('day','night'):
        record=json.loads((OUT/f'{state}-v15-manifest.json').read_text());assert record['complete']
        assert record['preparedSha256']==repair['preparedAfterWindowRepairSha256']
        for r in record['atlases']:
            permitted={repair['preparedAfterWindowRepairSha256']}
            if r['atlas'] in (2,9):permitted.add(repair['preparedBeforeWindowRepairSha256'])
            assert r['preparedSha256'] in permitted
        for r in record['atlases']:assert r['sha256']==hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
        architecture=json.loads((OUT/f'{state}-v15-architecture-manifest.json').read_text());assert architecture['complete']
        assert architecture['preparedSha256']==repair['preparedAfterWindowRepairSha256']
        for r in architecture['atlases']:assert r['sha256']==hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(PREP))
    exporting=scope_from(ROOT/'assets/blender/scripts/export_dual_lighting_v8.py',[
        ('for atlas in range(8):','for atlas in range(11):'),
        ("'atlasSizes':[4096]*6+[3072,2048]","'atlasSizes':[4096]*6+[3072,2048,3072,4096,4096]"),
        ("'samples':40","'samples':96"),
    ],'v15_eleven_atlas_export')
    report=exporting['export'](textures_directory=OUT,output_path=ROOT/'public/models/orbital-atelier-v15.glb',
        source_path='assets/blender/orbital-atelier-v15.blend',prepared_path=str(PREP.relative_to(ROOT)),geometry_revision=15,lighting_revision=15)
    prep=json.loads(PREP_REPORT.read_text());assert sorted(report['componentIds'])==sorted(prep['assetIds'])
    report['geometryInheritedFrom']=14;report['newSamples']=96;report['rebakedAtlasIDs']=[0,2,3,4,8,9,10];report['retainedAtlasIDs']=[1,5,6,7]
    report['sourceGeometryUnchanged']=False;report['smallPropGeometryUnchanged']=True;report['windowClearanceRepair']=repair;report['uvAudit']='assets/blender/texture-precision-v15-prepare.json'
    report['nativeRerenderedImages']=images
    report['preparedSha256']=hashlib.sha256(PREP.read_bytes()).hexdigest()
    report['sourceSha256']=hashlib.sha256((ROOT/report['source']).read_bytes()).hexdigest()
    (ROOT/'assets/blender/dual-lighting-v15-export-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--state',choices=['day','night']);parser.add_argument('--export',action='store_true');parser.add_argument('--architecture',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    print(json.dumps(export() if args.export else bake(args.state,args.architecture,args.resume),indent=2))
