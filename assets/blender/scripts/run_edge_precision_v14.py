"""Bake only the new architectural edge atlas, preserving the V13 light rig.

No existing texture is re-encoded. Export uses the existing unlit dual-state
format with one additional WEB8_LIGHTMAP_8 entry, without changing owner IDs.
"""
import bpy, json, sys, time, hashlib, shutil
from pathlib import Path

ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from bake_lighting_v8 import bake_state
from run_wall_lighting_v10 import configure_day
PREP=ROOT/'assets/blender/orbital-dual-bake-v14.blend'
OUT=ROOT/'public/textures/lighting-v14'
STATUS=ROOT/'assets/blender/edge-precision-v14-status.json'

# Reuse the exact V13 practical-light implementation but isolate the new
# reports. Never overwrite the V13 provenance files while running V14.
warm_scope={'__name__':'v14_inherited_warm_rig'}
warm_code=(ROOT/'assets/blender/scripts/night_warm_v13.py').read_text().replace('night-warm-v13-design.json','night-warm-v14-design.json').replace('lighting-night-v13.json','lighting-night-v14.json')
exec(compile(warm_code,'v14_inherited_warm_rig','exec'),warm_scope)

# V8 export already accepts source/output overrides. This local specialization
# adds atlas 8 and correct report sizes without altering historic exporters.
export_scope={'__name__':'v14_nine_atlas_export'}
export_code=(ROOT/'assets/blender/scripts/export_dual_lighting_v8.py').read_text().replace('for atlas in range(8):','for atlas in range(9):').replace("'atlasSizes':[4096]*6+[3072,2048]","'atlasSizes':[4096]*6+[3072,2048,3072]")
exec(compile(export_code,'v14_nine_atlas_export','exec'),export_scope)

def snapshot_source():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-atelier-v13.blend'))
    for scene in bpy.data.scenes:
        scene['web_precision_revision']=14
        scene['web_precision_source']='assets/blender/orbital-dual-bake-v14.blend'
        scene['geometry_inherited_from']=12
        scene['light_rig_inherited_from']=13
        scene['precision_note']='V14 improves exported UV continuity and localized texel density; source geometry / PBR / rig unchanged.'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/orbital-atelier-v14.blend'),compress=True)

def run():
    started=time.time();result={'phase':'copying_retained_maps','started':started,'bakedAtlasIDs':[8],'retainedAtlasIDs':list(range(8)),'states':{}}
    try:
        OUT.mkdir(parents=True,exist_ok=True)
        for path in (ROOT/'public/textures/lighting-v13').glob('*.png'):shutil.copy2(path,OUT/path.name)
        for state in ('day','night'):
            result.update(phase='baking',currentState=state);STATUS.write_text(json.dumps(result,indent=2)+'\n')
            bpy.ops.wm.open_mainfile(filepath=str(PREP))
            transform=(lambda s:configure_day(s,revision=14)) if state=='day' else warm_scope['configure_night_warm']
            result['states'][state]=bake_state(state,indices=[8],render_preview=True,scene_transform=transform,output_directory=OUT,revision=14)
        result['phase']='exporting';STATUS.write_text(json.dumps(result,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREP))
        result['export']=export_scope['export'](textures_directory=OUT,output_path=ROOT/'public/models/orbital-atelier-v14.glb',source_path='assets/blender/orbital-atelier-v14.blend',prepared_path='assets/blender/orbital-dual-bake-v14.blend',geometry_revision=14,lighting_revision=14)
        result['retainedMapSha256']={}
        for original in (ROOT/'public/textures/lighting-v13').glob('*.png'):
            expected=hashlib.sha256(original.read_bytes()).hexdigest()
            assert expected==hashlib.sha256((OUT/original.name).read_bytes()).hexdigest(),original.name
            result['retainedMapSha256'][original.name]=expected
        snapshot_source()
        result.update(phase='complete',finished=time.time(),seconds=time.time()-started,retainedMapsByteIdentical=True)
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
    except Exception as error:
        result.update(phase='failed',error=str(error));STATUS.write_text(json.dumps(result,indent=2)+'\n');raise
    return result

if __name__=='__main__':run()
