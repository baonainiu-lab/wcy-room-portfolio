"""Rebake only architecture after a local junction repair, with checked UV reuse."""
import bpy
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0, str(ROOT/'assets/blender/scripts'))
from bake_geometry_fingerprint import fingerprints
from bake_lighting_v8 import bake_state
from export_dual_lighting_v8 import export
from run_wall_lighting_v10 import configure_day

PREPARED = ROOT/'assets/blender/orbital-dual-bake-v11.blend'
OUT = ROOT/'public/textures/lighting-v11'
STATUS = ROOT/'assets/blender/window-lighting-v11-status.json'

def run():
    result = {'phase':'checking_retained_uvs','started':time.time(),'states':{}}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v10.blend'))
        old = fingerprints(bpy.data.scenes['WEB_DUAL_V8'])
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        new = fingerprints(bpy.data.scenes['WEB_DUAL_V8'])
        retained_old = {k:v for k,v in old.items() if v['atlas'] != 0}
        retained_new = {k:v for k,v in new.items() if v['atlas'] != 0}
        if retained_old != retained_new:
            changed = sorted(k for k in retained_old.keys() | retained_new.keys() if retained_old.get(k) != retained_new.get(k))
            raise RuntimeError('Retained lightmap geometry or UVs changed: '+', '.join(changed))
        proof = {'passed':True,'retainedAtlasIDs':list(range(1,8)), 'geometryAndUVs':retained_new,
                 'rebakedAtlasIDs':[0], 'scope':'Window junction architecture repair; cabinet front, window aperture, furnishings and lighting remain in place.'}
        (ROOT/'assets/blender/retained-uv-v11-verification.json').write_text(json.dumps(proof,indent=2)+'\n')
        OUT.mkdir(parents=True, exist_ok=True)
        for path in (ROOT/'public/textures/lighting-v10').glob('*.png'):
            shutil.copy2(path, OUT/path.name)
        for state in ('day','night'):
            result.update(phase='baking',currentState=state)
            STATUS.write_text(json.dumps(result,indent=2)+'\n')
            bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
            result['states'][state] = bake_state(state, indices=[0], render_preview=True,
                scene_transform=(lambda scene: configure_day(scene, revision=11)) if state == 'day' else None,
                output_directory=OUT, revision=11)
        result['phase']='exporting'
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        result['export'] = export(textures_directory=OUT,
            output_path=ROOT/'public/models/orbital-atelier-v11.glb',
            source_path='assets/blender/orbital-atelier-v11.blend',
            prepared_path=str(PREPARED.relative_to(ROOT)), geometry_revision=11, lighting_revision=11)
        result.update(phase='complete',finished=time.time())
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
    except Exception as error:
        result.update(phase='failed',error=str(error))
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        raise
    return result

if __name__ == '__main__':
    run()
