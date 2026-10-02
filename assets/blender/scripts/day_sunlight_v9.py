# -*- coding: utf-8 -*-
"""Strong oblique window sunlight, applied only to a configured day scene.

apply_day_sunlight(scene) follows setup_state('day'). No renders or saves here.
The original cutaway has a solid wall and an image behind its modeled bezel.
For daylight transport only, a rounded window aperture lets shadow rays through
those surfaces. A camera-invisible ceiling flags direct rays that would enter
through the cutaway roof. Actual Sun rays then cast coherent frame, furnishing,
and prop shadows onto the room. All changes are confined to the supplied scene.

Three thin, shadow-only mullion proxies supply a divided-window shadow rhythm;
they are an explicit lighting rig, not newly exported visible architecture.
Set MULLION_SHADOWS=False before calling if only existing-frame shadows are wanted.
"""
import json
import math

import bpy
from mathutils import Vector


PREFIX = 'DAY_SUN_V9_'
SUN_POSITION = Vector((7.0, 16.0, 12.0))
SUN_ENERGY = 18.0
SKY_STRENGTH = 0.16
MULLION_SHADOWS = True
ROOF_HEIGHT = 4.86

# Slightly inside the original rounded window's clear image and physical bezel.
APERTURE = {'center_x': 0.25, 'center_z': 2.97,
            'width': 5.82, 'height': 2.35, 'radius': 0.29,
            'min_y': 3.075, 'max_y': 3.79}


def _math(tree, operation, first=None, second=None):
    node = tree.nodes.new('ShaderNodeMath')
    node.operation = operation
    node.label = PREFIX + operation
    for socket, value in zip(node.inputs, [first, second]):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            tree.links.new(value, socket)
    return node.outputs[0]


def _aperture_shader(material):
    """Patch only shadow-ray visibility inside the rounded world-space hole."""
    tree = material.node_tree
    outputs = [n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.inputs['Surface'].is_linked]
    if not outputs:
        return False
    geometry = tree.nodes.new('ShaderNodeNewGeometry')
    geometry.name = PREFIX + 'ApertureWorldPosition'
    separate = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(geometry.outputs['Position'], separate.inputs[0])
    qx = _math(tree, 'SUBTRACT',
               _math(tree, 'ABSOLUTE', _math(tree, 'SUBTRACT', separate.outputs['X'], APERTURE['center_x'])),
               APERTURE['width']*.5 - APERTURE['radius'])
    qz = _math(tree, 'SUBTRACT',
               _math(tree, 'ABSOLUTE', _math(tree, 'SUBTRACT', separate.outputs['Z'], APERTURE['center_z'])),
               APERTURE['height']*.5 - APERTURE['radius'])
    ox, oz = _math(tree, 'MAXIMUM', qx, 0), _math(tree, 'MAXIMUM', qz, 0)
    outside = _math(tree, 'SQRT', _math(tree, 'ADD', _math(tree, 'MULTIPLY', ox, ox), _math(tree, 'MULTIPLY', oz, oz)))
    inside = _math(tree, 'MINIMUM', _math(tree, 'MAXIMUM', qx, qz), 0)
    sdf = _math(tree, 'SUBTRACT', _math(tree, 'ADD', outside, inside), APERTURE['radius'])
    mask = _math(tree, 'LESS_THAN', sdf, 0)
    depth = _math(tree, 'MULTIPLY',
                  _math(tree, 'GREATER_THAN', separate.outputs['Y'], APERTURE['min_y']),
                  _math(tree, 'LESS_THAN', separate.outputs['Y'], APERTURE['max_y']))
    path = tree.nodes.new('ShaderNodeLightPath')
    path.name = PREFIX + 'ApertureRayClassification'
    factor = _math(tree, 'MULTIPLY', path.outputs['Is Shadow Ray'], _math(tree, 'MULTIPLY', mask, depth))
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    transparent.inputs['Color'].default_value = (1, 1, 1, 1)
    for output in outputs:
        old = output.inputs['Surface'].links[0].from_socket
        mix = tree.nodes.new('ShaderNodeMixShader')
        mix.name = PREFIX + 'RoundedWindowShadowAperture'
        tree.links.new(factor, mix.inputs[0])
        tree.links.new(old, mix.inputs[1])
        tree.links.new(transparent.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], output.inputs['Surface'])
    material['day_sun_v9_aperture'] = True
    return True


def _intersects_window(obj):
    corners = [obj.matrix_world @ Vector(point) for point in obj.bound_box]
    low = [min(p[k] for p in corners) for k in range(3)]
    high = [max(p[k] for p in corners) for k in range(3)]
    limits = ((APERTURE['center_x']-APERTURE['width']*.5, APERTURE['center_x']+APERTURE['width']*.5),
              (APERTURE['min_y'], APERTURE['max_y']),
              (APERTURE['center_z']-APERTURE['height']*.5, APERTURE['center_z']+APERTURE['height']*.5))
    return all(high[k] >= limits[k][0] and low[k] <= limits[k][1] for k in range(3))


def _shadow_box(collection, name, location, size, material):
    x, y, z = [v*.5 for v in size]
    vertices = [(dx*x, dy*y, dz*z) for dx, dy, dz in
                [(-1,-1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1),
                 (-1,-1,1), (1,-1,1), (1,1,1), (-1,1,1)]]
    faces = [(0,3,2,1), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)]
    data = bpy.data.meshes.new(PREFIX + name + '_Mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    data.materials.append(material)
    obj = bpy.data.objects.new(PREFIX + name, data)
    collection.objects.link(obj)
    obj.location = location
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.visible_shadow = True
    obj['web_export'] = False
    obj['lighting_proxy'] = 'shadow only; cutaway daylight transport'
    return obj


def apply_day_sunlight(scene):
    if scene.get('v8_lighting_state') != 'day':
        raise RuntimeError("Apply only after configuring the supplied scene as 'day'. Night is intentionally unchanged.")
    if scene.get('day_sunlight_v9_applied'):
        return json.loads(scene['day_sunlight_v9_report'])
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()

    # The setup helper creates single-user scene lights. Copy Sun data again if
    # needed, so even explicitly shared Light datablocks stay protected.
    suns = [o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN']
    if len(suns) != 1:
        raise RuntimeError('Expected the single configured daylight Sun, found ' + str(len(suns)))
    sun = suns[0]
    if sun.data.users > 1:
        sun.data = sun.data.copy()
    sun.location = SUN_POSITION
    sun.rotation_euler = (-SUN_POSITION).to_track_quat('-Z', 'Y').to_euler()
    sun.data.energy = SUN_ENERGY
    sun.data.color = (1.0, 0.94, 0.82)
    sun.data.angle = math.radians(0.526)
    scene.world = scene.world.copy()
    scene.world.name = PREFIX + scene.name + '_Sky'
    for node in scene.world.node_tree.nodes:
        if node.type == 'BACKGROUND':
            node.inputs['Strength'].default_value = SKY_STRENGTH
        elif node.type == 'TEX_SKY':
            direction = SUN_POSITION.normalized()
            node.sun_elevation = math.asin(direction.z)
            node.sun_rotation = math.atan2(direction.y, direction.x)
    scene.cycles.transparent_max_bounces = max(16, scene.cycles.transparent_max_bounces)

    # Clone only materials on objects crossing the actual window volume. The
    # world-space mask prevents this from changing the rest of joined walls,
    # floor, frame, or furniture that happen to share the same material slot.
    material_copies = {}
    patched_objects = []
    for obj in list(scene.objects):
        if obj.type not in {'MESH', 'CURVE', 'FONT'} or not _intersects_window(obj):
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        changed = False
        for slot in obj.material_slots:
            old = slot.material
            if not old or not old.use_nodes:
                continue
            if old not in material_copies:
                new = old.copy()
                new.name = PREFIX + old.name
                material_copies[old] = new
                _aperture_shader(new)
            slot.material = material_copies[old]
            changed = True
        if changed:
            patched_objects.append(obj.name)

    collection = bpy.data.collections.new(PREFIX + scene.name + '_ShadowRig')
    scene.collection.children.link(collection)
    material = bpy.data.materials.new(PREFIX + 'Opaque_Shadow_Flag')
    material.diffuse_color = (0.05, 0.05, 0.05, 1)
    # Room roof is absent for viewing; flag its light path only. The true window
    # aperture remains below this flag, allowing a beam with a readable border.
    roof = _shadow_box(collection, 'Cutaway_Roof_Flag', (0, 0.02, ROOF_HEIGHT), (10.18, 7.22, .035), material)
    proxies = [roof]
    if MULLION_SHADOWS:
        for index, x in enumerate((-1.22, .25, 1.72)):
            proxies.append(_shadow_box(collection, 'Window_Mullion_Shadow_' + str(index),
                                       (x, 3.23, 2.97), (.066, .045, 2.36), material))
    scene.view_layers[0].update()
    floor_z = .18
    distance = (APERTURE['center_z'] - floor_z)/SUN_POSITION.z
    report = {
        'scene': scene.name, 'state': 'day', 'sun_energy': SUN_ENERGY,
        'sun_position_direction': list(SUN_POSITION),
        'sun_elevation_degrees': math.degrees(math.asin(SUN_POSITION.normalized().z)),
        'solar_angular_diameter_degrees': .526, 'sky_strength': SKY_STRENGTH,
        'sun_color_linear': list(sun.data.color),
        'cutaway_roof_height': ROOF_HEIGHT,
        'projected_window_center_on_floor': [APERTURE['center_x'] - SUN_POSITION.x*distance,
                                             3.23 - SUN_POSITION.y*distance, floor_z],
        'aperture': APERTURE, 'shadow_aperture_material_count': len(material_copies),
        'patched_objects': patched_objects, 'shadow_proxies': [o.name for o in proxies],
        'proxy_exported': False, 'night_changed': False,
        'method': 'One real Sun through a rounded shadow-ray aperture, with a cutaway ceiling flag; coherent geometrical furniture shadows and localized oblique sunlight.',
        'tradeoff': 'The modeled backdrop wall is solid behind the city image. Day-only shadow transparency acts as its light aperture. Roof and three optional mullions are camera-invisible lighting proxies and are not exported visible geometry.',
    }
    scene['day_sunlight_v9_applied'] = True
    scene['day_sunlight_v9_report'] = json.dumps(report)
    return report
