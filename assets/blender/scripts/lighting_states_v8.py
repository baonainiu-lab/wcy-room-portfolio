# -*- coding: utf-8 -*-
"""Independent, physically lit day/night setups for a *copy* of the V7 scene.

Usage: report = configure_lighting(bake_scene, 'day')

This module neither switches the active scene nor saves, renders, or bakes.
Objects, light datablocks, and World datablocks belonging to another scene are
never edited. Collection links are isolated before inherited lights are removed.
Geometry, geometry materials, transforms, IDs, UVs, and cameras are untouched.
The caller must separately supply the matching day/night window-city artwork.
"""

import math
import json
from pathlib import Path

import bpy
from mathutils import Vector


PREFIX = 'V8_LIGHTING_'
SUN_POSITION = Vector((9.0, -12.0, 16.5))
MOON_POSITION = Vector((-10.0, 6.0, 17.0))


def _scene_collections(scene):
    """Traverse unique collections, including the scene's unique master."""
    seen = set()
    queue = [scene.collection]
    while queue:
        collection = queue.pop()
        if collection.as_pointer() in seen:
            continue
        seen.add(collection.as_pointer())
        yield collection
        queue.extend(collection.children)


def _isolate_collections(scene):
    """Clone collection containers; preserve all geometry/object links.

    Unlinking a light from a shared child collection would also remove it from
    the source scene. Copying the complete collection tree first avoids that
    subtle failure while retaining collection visibility and other properties.
    """
    if scene.get('v8_lighting_collections_isolated'):
        return
    copies = {}

    def clone(old):
        key = old.as_pointer()
        if key in copies:
            return copies[key]
        new = old.copy()
        new.name = PREFIX + scene.name + '_' + old.name
        copies[key] = new
        for child in list(new.children):
            new.children.unlink(child)
        for child in old.children:
            new.children.link(clone(child))
        return new

    for original in list(scene.collection.children):
        isolated = clone(original)
        scene.collection.children.link(isolated)
        scene.collection.children.unlink(original)
    scene['v8_lighting_collections_isolated'] = True


def _new_area(collection, name, location, target, power, color, size, size_y=None):
    data = bpy.data.lights.new(PREFIX + name, 'AREA')
    data.energy = power
    data.color = color
    data.shape = 'RECTANGLE' if size_y else 'DISK'
    data.size = size
    if size_y:
        data.size_y = size_y
    obj = bpy.data.objects.new(data.name, data)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    obj['v8_generated_light'] = True
    return obj


def _new_sun(collection, name, position, energy, color, angle_degrees):
    data = bpy.data.lights.new(PREFIX + name, 'SUN')
    data.energy = energy
    data.color = color
    data.angle = math.radians(angle_degrees)
    obj = bpy.data.objects.new(data.name, data)
    collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (-Vector(position)).to_track_quat('-Z', 'Y').to_euler()
    obj['v8_generated_light'] = True
    return obj


def _world(scene, state):
    # World.copy() also creates an independent embedded node tree.
    world = scene.world.copy() if scene.world else bpy.data.worlds.new(PREFIX + 'World')
    world.name = PREFIX + scene.name + '_' + state + '_World'
    scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    output = tree.nodes.new('ShaderNodeOutputWorld')
    background = tree.nodes.new('ShaderNodeBackground')
    tree.links.new(background.outputs['Background'], output.inputs['Surface'])
    if state == 'day':
        sky = tree.nodes.new('ShaderNodeTexSky')
        sky_types = {item.identifier for item in sky.bl_rna.properties['sky_type'].enum_items}
        sky.sky_type = 'MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in sky_types else 'NISHITA'
        # The separate Sun gives one well-defined solar shadow. The sky only
        # provides atmospheric scattered light: no double solar disc/lighting.
        sky.sun_disc = False
        direction = SUN_POSITION.normalized()
        sky.sun_elevation = math.asin(direction.z)
        sky.sun_rotation = math.atan2(direction.y, direction.x)
        sky.altitude = 0.25
        sky.air_density = 1.0
        if hasattr(sky, 'aerosol_density'):
            sky.aerosol_density = 0.8
        else:
            sky.dust_density = 0.8
        sky.ozone_density = 1.0
        background.inputs['Strength'].default_value = 0.075
        tree.links.new(sky.outputs['Color'], background.inputs['Color'])
        return {
            'model': sky.sky_type + ' atmosphere, solar disc disabled; separate physical Sun',
            'strength': 0.075,
            'sun_elevation_degrees': math.degrees(sky.sun_elevation),
            'sun_rotation_degrees': math.degrees(sky.sun_rotation),
        }
    # A little blue-grey ambient irradiance preserves dark metal forms. The
    # visible website backdrop is independently designed by the frontend.
    background.inputs['Color'].default_value = (0.055, 0.085, 0.16, 1.0)
    background.inputs['Strength'].default_value = 0.58
    return {'model': 'blue-grey night ambient', 'color_linear': [0.055, 0.085, 0.16], 'strength': 0.58}


def configure_lighting(scene, state):
    """Configure only the supplied bake scene; return a JSON-safe report.

    Day: a 48-degree neutral sun enters from the open front-right, producing
    coherent, fairly crisp physical shadows. Blue sky supplies soft indirect
    fill; theatrical key/fill/rim softboxes are removed. Existing warm fixtures
    remain dim orientation lights, rather than dominating the daytime image.

    Night: the sun and studio rig are off. A very low cold moonlight describes
    exterior metal; cabinet, floor-lamp, screen, and gallery practicals provide
    localized warm/cool light and real reflected light. No global orange wash.
    """
    state = str(state).lower()
    if state not in {'day', 'night'}:
        raise ValueError("state must be 'day' or 'night'")
    if not isinstance(scene, bpy.types.Scene):
        raise TypeError('scene must be a bpy.types.Scene')

    _isolate_collections(scene)
    inherited = []
    removed = []
    for obj in list(scene.objects):
        if obj.type != 'LIGHT':
            continue
        if not obj.get('v8_generated_light'):
            inherited.append(obj)
        # Only unlink from the supplied scene's now-independent containers.
        for collection in _scene_collections(scene):
            if obj.name in collection.objects:
                collection.objects.unlink(obj)

    collection = bpy.data.collections.new(PREFIX + scene.name + '_' + state)
    scene.collection.children.link(collection)
    retained = []

    for original in inherited:
        original_name = original.get('v8_original_light_name', original.name)
        source_energy = float(original.get('v8_original_light_energy', original.data.energy))
        is_gallery = original_name.startswith('Gallery warm practical ')
        is_niche = original_name.startswith('L_Niche_')
        is_window = original_name.startswith('L_WindowLight')
        if not (is_gallery or is_niche or is_window):
            removed.append(original_name)
            continue
        # Never mutate even a previously copied light: this also makes calling
        # day then night on one temporary scene deterministic.
        obj = original.copy()
        obj.data = original.data.copy()
        obj.animation_data_clear()
        obj.data.animation_data_clear()
        matrix = original.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = matrix
        obj.name = PREFIX + state + '_' + original_name
        obj.data.name = obj.name
        obj.hide_render = False
        collection.objects.link(obj)
        obj['v8_original_light_name'] = original_name
        obj['v8_original_light_energy'] = source_energy
        obj['v8_generated_light'] = False
        if is_gallery:
            # Keep the existing fixture positions, direction, warm color and
            # physical area. Daytime light levels are one tenth of nighttime.
            factor = (0.055 if obj.data.type == 'POINT' else 0.085) if state == 'day' else 1.0
            obj.data.energy = source_energy * factor
        elif is_niche:
            obj.data.energy = 7.0 if state == 'day' else 42.0
            obj.data.color = (1.0, 0.62, 0.31)
        else:
            obj.data.energy = 0.0 if state == 'day' else 42.0
            obj.data.color = (0.38, 0.58, 1.0)
        retained.append(obj)

    if state == 'day':
        _new_sun(collection, 'Day_Sun', SUN_POSITION, 5.0, (1.0, 0.94, 0.84), 0.526)
    else:
        _new_sun(collection, 'Night_Moon', MOON_POSITION, 0.075, (0.43, 0.64, 1.0), 2.0)

    # The V5 ring light had emissive trim but no actual practical light. Give
    # that visible fixture a localized warm pool on the lounge/table area.
    _new_area(collection, 'Floor_Lamp_Practical', (2.28, 0.68, 1.69),
              (1.48, -0.65, 0.35), 3.0 if state == 'day' else 60.0,
              (1.0, 0.68, 0.38), 0.43)

    # A low-energy broad screen source keeps workstation illumination local,
    # rather than restoring the removed front studio fill.
    _new_area(collection, 'Monitor_Reflected_Light', (-2.45, 1.93, 2.70),
              (-2.45, 0.25, 1.45), 2.0 if state == 'day' else 18.0,
              (0.48, 0.70, 1.0), 2.15, 0.75)

    # Small, shielded practicals illuminate only their nearby desk/window/reading
    # surfaces. The user's intent is soft localized warmth, not a brighter room.
    manifest = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio/assets/blender/interior-warm-v8-manifest.json')
    if manifest.exists():
        for index, lamp in enumerate(json.loads(manifest.read_text()).get('warm_light_sources', [])):
            color = lamp.get('color_linear', (1.0, 0.59, 0.27))
            _new_area(collection, 'Interior_Warm_' + str(index), lamp['position'], lamp['target'],
                      lamp.get('energy', 25) * (0.045 if state == 'day' else 1.0),
                      color, lamp.get('width', .20), lamp.get('height', .10))

    world_report = _world(scene, state)
    scene.render.engine = 'CYCLES'
    if hasattr(scene.cycles, 'use_light_tree'):
        scene.cycles.use_light_tree = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = 0.15 if state == 'day' else 0.10
    scene.view_settings.gamma = 1.0
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene['v8_lighting_state'] = state

    lights = [o for o in scene.objects if o.type == 'LIGHT']
    report = {
        'state': state,
        'scene': scene.name,
        'world': world_report,
        'view_transform': scene.view_settings.view_transform,
        'look': scene.view_settings.look,
        'exposure': scene.view_settings.exposure,
        'gamma': scene.view_settings.gamma,
        'source_light_objects_and_world_unchanged': True,
        'removed_studio_lights': removed,
        'light_count': len(lights),
        'active_light_count': sum(o.data.energy > 0 for o in lights),
        'lights': [{
            'name': o.name,
            'type': o.data.type,
            'energy': o.data.energy,
            'color_linear': list(o.data.color),
            'position': list(o.matrix_world.translation),
        } for o in lights],
        'caller_material_notes': {
            'day': 'Render a matching blue-white city sky without the moon; use a dedicated window image. Reduce emissive fixture strengths to about 0.20 of original, monitor artwork to about 0.65. Copy materials before changing them.',
            'night': 'Use a genuine dim city-night image with moon and localized lit windows, not the original bright blue daytime city. Keep warm diffuser emissions at original strength; monitor artwork may stay original.',
            'window': 'Window-image exposure is independent of physical world irradiance. Never increase all materials or unlit color globally to simulate sunlight.',
        },
    }
    return report
