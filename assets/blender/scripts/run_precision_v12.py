"""Bake the V12 precision repair, reusing only identical surface lightmaps."""
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

PREPARED = ROOT/'assets/blender/orbital-dual-bake-v12.blend'
OUT = ROOT/'public/textures/lighting-v12'
STATUS = ROOT/'assets/blender/precision-v12-bake-status.json'

def run():
    result = {'phase':'checking_surface_changes','started':time.time(),'states':{}}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v11.blend'))
        old = fingerprints(bpy.data.scenes['WEB_DUAL_V8'], include_shading=True)
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        new = fingerprints(bpy.data.scenes['WEB_DUAL_V8'], include_shading=True)
        changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
        rebake = sorted({0} | {int(key.split('::')[0]) for key in changed})
        retained = sorted(set(range(8)) - set(rebake))
        unchanged = {k:v for k,v in new.items() if v['atlas'] in retained}
        if unchanged != {k:v for k,v in old.items() if v['atlas'] in retained}:
            raise RuntimeError('Retained atlas surface differs from the previous bake.')
        proof = {'passed':True, 'comparison':'positions, loop topology, BakeUV, world matrix, corner normals and smooth-face flags',
                 'rebakedAtlasIDs':rebake,'retainedAtlasIDs':retained,'changedOwners':changed,'retainedSurfaces':unchanged,
                 'scope':'Local geometry/normal precision repair; lighting positions and powers unchanged. Retained maps preserve the previous indirect-light approximation.'}
        (ROOT/'assets/blender/retained-surfaces-v12-verification.json').write_text(json.dumps(proof,indent=2)+'\n')
        result['surfaceVerification'] = proof
        OUT.mkdir(parents=True, exist_ok=True)
        for path in (ROOT/'public/textures/lighting-v11').glob('*.png'):
            shutil.copy2(path, OUT/path.name)
        for state in ('day','night'):
            result.update(phase='baking',currentState=state)
            STATUS.write_text(json.dumps(result,indent=2)+'\n')
            bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
            result['states'][state] = bake_state(state, indices=rebake, render_preview=True,
                scene_transform=(lambda scene: configure_day(scene, revision=12)) if state == 'day' else None,
                output_directory=OUT, revision=12)
        result['phase']='exporting'
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        result['export'] = export(textures_directory=OUT,
            output_path=ROOT/'public/models/orbital-atelier-v12.glb',
            source_path='assets/blender/orbital-atelier-v12.blend',
            prepared_path=str(PREPARED.relative_to(ROOT)), geometry_revision=12, lighting_revision=12)
        result.update(phase='complete',finished=time.time())
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
    except Exception as error:
        result.update(phase='failed',error=str(error))
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        raise
    return result

if __name__ == '__main__':
    run()
