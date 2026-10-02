# -*- coding: utf-8 -*-
"""Three small original shielded warm fixtures for the room interior.

Geometry only: root lighting configuration consumes warm_light_sources. Lamps
are independent interactive roots and emit softly below their opaque shades.
No camera, existing object, existing material, World, or light is modified.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
COLLECTION = 'INTERIOR_WARM_V8'
PREFIX = 'IW8_'

WARM_LIGHT_SOURCES = [
    {'id': 'v8_desk_glow_lamp', 'position': [-3.55, -0.20, 2.187],
     'target': [-2.91, -0.28, 1.87], 'type': 'area', 'energy': 24,
     'color_linear': [1.0, 0.62, 0.32], 'width': 0.26, 'height': 0.14},
    {'id': 'v8_window_light_bar', 'position': [1.45, 2.318, 1.234],
     'target': [1.45, 1.94, 0.63], 'type': 'area', 'energy': 26,
     'color_linear': [1.0, 0.58, 0.27], 'width': 0.70, 'height': 0.06},
    {'id': 'v8_reading_puck', 'position': [0.49, -0.948, 1.101],
     'target': [-0.19, -1.20, 0.96], 'type': 'area', 'energy': 18,
     'color_linear': [1.0, 0.66, 0.37], 'width': 0.18, 'height': 0.10},
]


def build(scene=None):
    scene = scene or bpy.data.scenes['ORBITAL_ATELIER_V2']
    if bpy.data.collections.get(COLLECTION):
        raise RuntimeError('INTERIOR_WARM_V8 already exists; use the untouched V7 source for a reproducible build.')
    collection = bpy.data.collections.new(COLLECTION)
    scene.collection.children.link(collection)
    materials = {}
    for name, color, metallic, roughness in [
        ('SatinTitanium', (0.36, 0.44, 0.50), 0.72, 0.30),
        ('IvoryCeramic', (0.69, 0.70, 0.64), 0.08, 0.37),
        ('Graphite', (0.018, 0.028, 0.037), 0.25, 0.44),
        ('WarmDiffuser', (0.86, 0.61, 0.32), 0.0, 0.40),
    ]:
        material = bpy.data.materials.new(PREFIX + 'MAT_' + name)
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*color, 1)
        shader.inputs['Metallic'].default_value = metallic
        shader.inputs['Roughness'].default_value = roughness
        if name == 'WarmDiffuser':
            shader.inputs['Emission Color'].default_value = (1.0, 0.64, 0.32, 1)
            shader.inputs['Emission Strength'].default_value = 1.2
        materials[name] = material

    roots = []

    def root(name, asset_id, position, label):
        obj = bpy.data.objects.new(PREFIX + name + '_Root', None)
        collection.objects.link(obj)
        obj.location = position
        obj['asset_id'] = asset_id
        obj['interactive'] = True
        obj['interaction'] = 'warm_lamp'
        obj['label_zh'] = label
        obj['asset_revision'] = 8
        obj.empty_display_type = 'PLAIN_AXES'
        obj.empty_display_size = 0.07
        roots.append(obj)
        return obj

    def mesh(name, vertices, faces, material, parent):
        data = bpy.data.meshes.new(PREFIX + name + '_Mesh')
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(PREFIX + name, data)
        collection.objects.link(obj)
        obj.parent = parent
        data.materials.append(materials[material])
        uv = data.uv_layers.new(name='UVMap')
        for face in data.polygons:
            major = max(range(3), key=lambda axis: abs(face.normal[axis]))
            axes = [axis for axis in range(3) if axis != major]
            for loop in face.loop_indices:
                point = data.vertices[data.loops[loop].vertex_index].co
                uv.data[loop].uv = (point[axes[0]], point[axes[1]])
        return obj

    def rounded(name, location, size, radius, material, parent):
        # Analytic small fillets, no expensive subdivision/bevel modifiers.
        width, depth, height = size
        points = []
        for x, y, start in [(width/2-radius, depth/2-radius, 0),
                            (-width/2+radius, depth/2-radius, 90),
                            (-width/2+radius, -depth/2+radius, 180),
                            (width/2-radius, -depth/2+radius, 270)]:
            for step in range(5):
                angle = math.radians(start + step * 22.5)
                points.append((x + radius*math.cos(angle), y + radius*math.sin(angle)))
        n = len(points)
        vertices = [(x+location[0], y+location[1], z+location[2])
                    for z in (-height/2, height/2) for x, y in points]
        faces = [tuple(reversed(range(n))), tuple(range(n, n*2))]
        faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        return mesh(name, vertices, faces, material, parent)

    def rod(name, start, end, radius, material, parent, sides=12):
        start, end = Vector(start), Vector(end)
        axis = (end-start).normalized()
        side = axis.cross(Vector((0, 0, 1)))
        if side.length < 0.1:
            side = axis.cross(Vector((0, 1, 0)))
        side.normalize()
        up = axis.cross(side)
        vertices = [tuple(p + radius*(side*math.cos(i*math.tau/sides) + up*math.sin(i*math.tau/sides)))
                    for p in (start, end) for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(sides, sides*2))]
        faces += [(i, (i+1)%sides, (i+1)%sides+sides, i+sides) for i in range(sides)]
        return mesh(name, vertices, faces, material, parent)

    # Measured free desk pocket between the projector (y<-0.66) and pen stand
    # (y>0.57), clear of the main display and split keyboard. Desk top z=1.858.
    desk = root('DeskPetal', 'v8_desk_glow_lamp', (-3.60, -0.20, 1.858), '桌面暖光小台灯')
    rounded('Desk_RubberFoot', (0, 0, .012), (.33, .23, .024), .07, 'Graphite', desk)
    rounded('Desk_CeramicBase', (0, 0, .039), (.35, .25, .037), .09, 'IvoryCeramic', desk)
    rounded('Desk_BaseInlay', (-.015, .024, .059), (.18, .09, .006), .025, 'SatinTitanium', desk)
    rod('Desk_RearStem', (-.085, .060, .056), (-.055, .060, .366), .018, 'SatinTitanium', desk)
    rod('Desk_HeadNeck', (-.055, .060, .366), (.050, 0, .379), .022, 'SatinTitanium', desk)
    rounded('Desk_TitaniumShadeRim', (.050, 0, .378), (.36, .22, .030), .09, 'SatinTitanium', desk)
    rounded('Desk_CeramicShade', (.050, 0, .404), (.35, .21, .035), .085, 'IvoryCeramic', desk)
    rounded('Desk_RecessedWarmLens', (.050, 0, .349), (.282, .152, .019), .056, 'WarmDiffuser', desk)
    rounded('Desk_TopTouchKey', (.099, -.020, .424), (.057, .042, .006), .017, 'Graphite', desk)

    # Physically mounted under the existing display ledge (underside z=1.345).
    # The narrow diffuser aims down/forward, rather than whitening the window.
    bar = root('WindowUndershelf', 'v8_window_light_bar', (1.45, 2.400, 1.294), '窗台下暖光灯条')
    rounded('Bar_RearMount', (0, .075, .024), (.77, .12, .045), .020, 'Graphite', bar)
    rounded('Bar_TitaniumHousing', (0, .003, 0), (.85, .13, .095), .040, 'SatinTitanium', bar)
    rounded('Bar_CeramicUpperShield', (0, .004, .042), (.87, .14, .018), .046, 'IvoryCeramic', bar)
    rounded('Bar_LensRecess', (0, -.059, -.026), (.768, .014, .039), .006, 'Graphite', bar)
    rounded('Bar_WarmLens', (0, -.068, -.026), (.711, .012, .025), .005, 'WarmDiffuser', bar)
    for x in (-.396, .396):
        rod('Bar_CapBolt_' + str(x), (x, -.063, -.004), (x, -.071, -.004), .009, 'Graphite', bar, 8)

    # The coffee table's free right-hand pocket, clear of the notebook/dial.
    # Opaque upper cap hides the source from above; the lens faces the notebook.
    puck = root('ReadingPuck', 'v8_reading_puck', (.54, -.90, .955), '茶几阅读暖光灯')
    rounded('Puck_RubberFoot', (0, 0, .010), (.23, .21, .020), .080, 'Graphite', puck)
    rounded('Puck_CeramicBase', (0, 0, .034), (.25, .23, .034), .085, 'IvoryCeramic', puck)
    rod('Puck_OffsetStem', (.059, .038, .049), (.020, .040, .177), .024, 'SatinTitanium', puck)
    rounded('Puck_ShadeRim', (-.035, .011, .186), (.295, .242, .032), .090, 'SatinTitanium', puck)
    rounded('Puck_CeramicCap', (-.035, .011, .211), (.279, .227, .031), .087, 'IvoryCeramic', puck)
    rounded('Puck_RecessedLens', (-.045, -.020, .162), (.209, .139, .015), .050, 'WarmDiffuser', puck)
    rounded('Puck_TouchInset', (.0, .029, .229), (.065, .042, .006), .015, 'Graphite', puck)

    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()
    triangle_count = 0
    for obj in collection.objects:
        if obj.type == 'MESH':
            obj.data.calc_loop_triangles()
            triangle_count += len(obj.data.loop_triangles)
    assets = []
    for obj in roots:
        vertices = [child.matrix_world @ Vector(corner)
                    for child in obj.children if child.type == 'MESH' for corner in child.bound_box]
        assets.append({'asset_id': obj['asset_id'], 'root': obj.name, 'position': list(obj.location),
                       'bounds_min': [min(v[k] for v in vertices) for k in range(3)],
                       'bounds_max': [max(v[k] for v in vertices) for k in range(3)]})
    report = {'collection': COLLECTION, 'scene': scene.name, 'roots': assets,
              'root_count': 3, 'interactive_group_count': 3,
              'mesh_count': sum(o.type == 'MESH' for o in collection.objects),
              'triangles': triangle_count, 'within_budget': triangle_count <= 2000,
              'warm_light_sources': WARM_LIGHT_SOURCES,
              'materials': [m.name for m in materials.values()],
              'notes': 'Three shielded tiny practical fixtures; 24W desk / 26W undershelf / 18W reading pools. No global fill or bright bare bulbs.'}
    scene['interior_warm_v8_sources'] = json.dumps(WARM_LIGHT_SOURCES)
    scene['interior_warm_v8_revision'] = 8
    return report


def build_and_save():
    source = ROOT / 'assets/blender/orbital-atelier-v7.blend'
    output = ROOT / 'assets/blender/orbital-atelier-v8-interior.blend'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    report = build()
    if not report['within_budget']:
        raise RuntimeError('Warm fixtures exceed 2,000-triangle budget.')
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True, check_existing=False)
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if after != before:
        raise RuntimeError('Protected V7 source unexpectedly changed.')
    report.update(source=str(source), output=str(output), bytes=output.stat().st_size,
                  source_unchanged=True, source_sha256=before)
    (ROOT / 'assets/blender/interior-warm-v8-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report
