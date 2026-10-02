"""Reimport the actual web GLB into the saved studio and verify same model bounds."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

here = Path(__file__).resolve().parent
project = here.parents[2]
bpy.ops.wm.open_mainfile(filepath=str(here / 'geometric-creator-v1.blend'))
scene = bpy.context.scene
root = bpy.data.objects['GeometricCreator']
source = [root, *root.children_recursive]


def bounds(objects):
    points = [o.matrix_world @ v.co for o in objects if o.type == 'MESH' for v in o.data.vertices]
    return [[min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]]


source_bounds = bounds(source)
for o in source:
    o.hide_render = True
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(project / 'public/models/avatar/geometric-creator-v1.glb'))
imported = set(bpy.data.objects)-before
bpy.context.view_layer.update()
imported_bounds = bounds(imported)
max_delta = max(abs(a-b) for ar, br in zip(source_bounds, imported_bounds) for a, b in zip(ar, br))
assert max_delta < .00001, (source_bounds, imported_bounds, max_delta)
report = {'source_bounds_blender': source_bounds, 'reimported_bounds_blender': imported_bounds,
          'max_bound_delta_m': max_delta, 'same_geometry_bounds': True,
          'reimported_mesh_count': sum(o.type == 'MESH' for o in imported),
          'verification': 'Actual exported web GLB reimported into same studio; original model hidden.'}
(here / 'verification.json').write_text(json.dumps(report, indent=2))
scene.render.filepath = str(project / 'renders/avatar-geometric/geometric-creator-v1-glb-verified.png')
bpy.ops.render.render(write_still=True)
print('GLB_VERIFIED=' + json.dumps(report))
