"""Long-running Blender CLI worker for the MCP-authored V8 scene.

The MCP background request is limited to 120 seconds. This worker uses the same
Blender binary and prepared scene, allowing complete atlases without interruption.
"""
import bpy, json, time, traceback
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SCRIPTS = ROOT/'assets/blender/scripts'
PREPARED = ROOT/'assets/blender/orbital-dual-bake-v8.blend'
STATUS = ROOT/'assets/blender/lighting-pipeline-v8-status.json'
started = time.monotonic()
results = {}


def module(name):
    namespace = {'__name__': name}
    exec(compile((SCRIPTS/(name+'.py')).read_text(), name+'.py', 'exec'), namespace)
    return namespace


def status(phase):
    STATUS.write_text(json.dumps({'phase':phase,'elapsed':round(time.monotonic()-started,2),'results':results}, indent=2)+'\n')


try:
    for state in ('night', 'day'):
        status('baking_'+state)
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        results[state] = module('bake_lighting_v8')['bake_state'](state, render_preview=True)
    status('exporting')
    bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
    results['export'] = module('export_dual_lighting_v8')['export']()
    status('saving_editable_source')
    results['editable_source'] = module('save_lighting_source_v8')['save_lighting_source_v8']()
    status('complete')
except Exception:
    results['error'] = traceback.format_exc()
    status('failed')
    raise
