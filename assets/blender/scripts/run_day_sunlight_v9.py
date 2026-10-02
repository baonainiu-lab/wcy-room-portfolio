"""Bake only the revised daylight, retaining V8 geometry, UVs and night textures."""
import bpy
import json
import sys
import time
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0, str(ROOT/'assets/blender/scripts'))
from bake_lighting_v8 import bake_state
from day_sunlight_v9 import apply_day_sunlight

status = ROOT/'assets/blender/day-sunlight-v9-status.json'
started = time.time()

def configure(scene):
    report = apply_day_sunlight(scene)
    (ROOT/'assets/blender/lighting-day-v9.json').write_text(json.dumps(report, indent=2)+'\n')
    # Preserve this exact editable bake scene before temporary proxies are used.
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/orbital-day-bake-v9.blend'), compress=True, check_existing=False)

try:
    status.write_text(json.dumps({'phase':'baking','started':started}, indent=2)+'\n')
    result = bake_state('day', render_preview=True, scene_transform=configure,
                        output_directory=ROOT/'public/textures/lighting-v9', revision=9)
    status.write_text(json.dumps({'phase':'complete','started':started,'finished':time.time(),
                                 'night_changed':False,'result':result}, indent=2)+'\n')
except Exception as error:
    status.write_text(json.dumps({'phase':'failed','started':started,'error':str(error)}, indent=2)+'\n')
    raise
