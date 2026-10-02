"""V13 preview or complete night-only bake/export with byte-identical day maps."""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
import bpy

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from bake_lighting_v8 import setup_state, bake_state
from night_warm_v13 import configure_night_warm, save_sources
from export_dual_lighting_v8 import export

OUT = ROOT/'public/textures/lighting-v13'
PREPARED = ROOT/'assets/blender/orbital-dual-bake-v13.blend'
STATUS = ROOT/'assets/blender/night-warm-v13-status.json'


def preview():
    save_sources()
    scene = setup_state('night',report_revision=13)
    configure_night_warm(scene)
    scene.cycles.samples = 28
    scene.cycles.use_denoising = True
    scene.render.resolution_x,scene.render.resolution_y = 1100,807
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(ROOT/'renders/night-warm-v13-preview.png')
    bpy.ops.render.render(write_still=True)


def run():
    result = {'phase':'copying_unchanged_day','started':time.time(),
              'geometryInheritedFrom':12,'nightAtlasIDs':list(range(8))}
    try:
        OUT.mkdir(parents=True,exist_ok=True)
        for path in (ROOT/'public/textures/lighting-v12').glob('*.png'):
            shutil.copy2(path,OUT/path.name)
        result['phase']='baking_night'
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        result['night']=bake_state('night',indices=list(range(8)),render_preview=True,
            scene_transform=configure_night_warm,output_directory=OUT,revision=13)
        result['phase']='exporting'
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        result['export']=export(textures_directory=OUT,
            output_path=ROOT/'public/models/orbital-atelier-v13.glb',
            source_path='assets/blender/orbital-atelier-v13.blend',
            prepared_path=str(PREPARED.relative_to(ROOT)),geometry_revision=13,lighting_revision=13)
        result['daySha256']={}
        for path in (ROOT/'public/textures/lighting-v12').glob('*day*.png'):
            original=hashlib.sha256(path.read_bytes()).hexdigest()
            current=hashlib.sha256((OUT/path.name).read_bytes()).hexdigest()
            assert original==current,path.name
            result['daySha256'][path.name]=current
        result.update(phase='complete',finished=time.time(),dayByteIdentical=True)
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
    except Exception as error:
        result.update(phase='failed',error=str(error))
        STATUS.write_text(json.dumps(result,indent=2)+'\n')
        raise


if __name__=='__main__':
    preview() if '--preview' in sys.argv else run()
