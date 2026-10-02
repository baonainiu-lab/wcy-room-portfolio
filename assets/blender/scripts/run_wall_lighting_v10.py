"""Rebake the thicker/taller Blender room in both lighting states and export V10."""
import bpy
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0, str(ROOT/'assets/blender/scripts'))
from bake_lighting_v8 import bake_state
from export_dual_lighting_v8 import export
import day_sunlight_v9

PREPARED = ROOT/'assets/blender/orbital-dual-bake-v10.blend'
OUT = ROOT/'public/textures/lighting-v10'
STATUS = ROOT/'assets/blender/wall-lighting-v10-status.json'

def configure_day(scene, revision=10):
    day_sunlight_v9.ROOF_HEIGHT = 5.21
    report = day_sunlight_v9.apply_day_sunlight(scene)
    # Match the full-quality source's cutaway flag to the outward wall envelope.
    for roof in scene.objects:
        if 'Cutaway_Roof_Flag' not in roof.name:
            continue
        matrix, inverse = roof.matrix_world.copy(), roof.matrix_world.inverted()
        points = [matrix @ v.co for v in roof.data.vertices]
        min_x, max_y = min(p.x for p in points), max(p.y for p in points)
        for vertex in roof.data.vertices:
            p = matrix @ vertex.co
            if abs(p.x-min_x) < .001:
                p.x = -5.38
            if abs(p.y-max_y) < .001:
                p.y = 3.81
            vertex.co = inverse @ p
        roof.data.update()
    scene.view_layers[0].update()
    report['wall_geometry_revision'] = revision
    report['cutaway_roof_outward_bounds'] = {'min_x':-5.38, 'max_y':3.81}
    (ROOT/'assets/blender'/f'lighting-day-v{revision}.json').write_text(json.dumps(report, indent=2)+'\n')

def run():
    OUT.mkdir(parents=True, exist_ok=True)
    for state in ('day', 'night'):
        shutil.copy2(ROOT/'public/textures/lighting-v8'/f'window-{state}.png', OUT/f'window-{state}.png')
    result = {'phase':'baking', 'started':time.time(), 'states':{}}
    try:
        for state in ('day', 'night'):
            result['currentState'] = state
            STATUS.write_text(json.dumps(result, indent=2)+'\n')
            bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
            result['states'][state] = bake_state(state, render_preview=True,
                scene_transform=configure_day if state == 'day' else None,
                output_directory=OUT, revision=10)
        result['phase'] = 'exporting'
        STATUS.write_text(json.dumps(result, indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(PREPARED))
        result['export'] = export(textures_directory=OUT,
            output_path=ROOT/'public/models/orbital-atelier-v10.glb',
            source_path='assets/blender/orbital-atelier-v10.blend',
            prepared_path=str(PREPARED.relative_to(ROOT)),
            geometry_revision=10, lighting_revision=10)
        result.update(phase='complete', finished=time.time())
        STATUS.write_text(json.dumps(result, indent=2)+'\n')
    except Exception as error:
        result.update(phase='failed', error=str(error))
        STATUS.write_text(json.dumps(result, indent=2)+'\n')
        raise
    return result

if __name__ == '__main__':
    run()
