# -*- coding: utf-8 -*-
"""Render genuine day/night views of the original modeled window city.

Call render_window_states() from Blender MCP. Existing ENV_CITY geometry is
copied into two independent scenes; only copies receive lighting/material edits.
No source objects/datablocks are edited and no .blend file is saved. Generated
PNG files are renders of authored 3D geometry, not image-generation outputs.
"""
import importlib.util
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
OUTPUT = ROOT / 'public/textures/lighting-v8'
PREFIX = 'WINDOW_V8_'


def _source_scene():
    candidates = [s for s in bpy.data.scenes if s.name == 'ENV_CITY' or s.name.startswith('ENV_CITY.')]
    if candidates:
        # ENV_CITY.001 is the refined 1,041-object scene in the V7 source.
        return max(candidates, key=lambda s: (len(s.objects), s.name))
    path = ROOT / 'assets/blender/scripts/environment.py'
    spec = importlib.util.spec_from_file_location('original_window_city_v8', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.build_environment(str(OUTPUT / 'window-day.png'), width=1536, height=672)
    return bpy.data.scenes[result['scene_name']]


def _copy_scene(source, state):
    # Inactive scenes reopened from a .blend can retain identity matrix_world
    # values until their dependency graph is evaluated. Reading those cached
    # matrices used to reset the city camera to the origin during duplication.
    # Evaluate the actual source before taking any transform snapshots.
    if bpy.context.window:
        bpy.context.window.scene = source
    source.view_layers[0].update()
    transforms = {obj: obj.matrix_world.copy() for obj in source.objects}
    scene = bpy.data.scenes.new(PREFIX + state.upper())
    collection = bpy.data.collections.new(PREFIX + state.upper() + '_CONTENT')
    scene.collection.children.link(collection)
    objects = {}
    materials = {}
    for original in source.objects:
        obj = original.copy()
        if original.data:
            obj.data = original.data.copy()
        obj.animation_data_clear()
        obj.name = PREFIX + state + '_' + original.name
        obj['window_v8_source_name'] = original.name
        matrix = transforms[original]
        obj.parent = None
        obj.matrix_world = matrix
        collection.objects.link(obj)
        objects[original] = obj
        if obj.data and hasattr(obj.data, 'materials'):
            for index, material in enumerate(obj.data.materials):
                if material is None:
                    continue
                if material not in materials:
                    new = material.copy()
                    new.name = PREFIX + state + '_' + material.name
                    materials[material] = new
                obj.data.materials[index] = materials[material]
    for original, obj in objects.items():
        if original.parent in objects:
            matrix = transforms[original]
            obj.parent = objects[original.parent]
            obj.matrix_world = matrix
    scene.camera = objects[source.camera]
    scene.world = source.world.copy() if source.world else bpy.data.worlds.new(PREFIX + state + '_WORLD')
    scene.world.name = PREFIX + state + '_WORLD'
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()
    return scene, materials


def _set_input(tree, socket, value):
    for link in list(socket.links):
        tree.links.remove(link)
    socket.default_value = value


def _math(tree, operation, a=None, b=None):
    node = tree.nodes.new('ShaderNodeMath')
    node.operation = operation
    for socket, value in zip(node.inputs, [a, b]):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            tree.links.new(value, socket)
    return node.outputs[0]


def _night_windows(material):
    """Lit and unlit individual facade cells, original procedural shader only."""
    tree = material.node_tree
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    coords = tree.nodes.new('ShaderNodeTexCoord')
    scale = tree.nodes.new('ShaderNodeVectorMath')
    scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = (21.0, 17.0, 64.0)
    tree.links.new(coords.outputs['Generated'], scale.inputs[0])
    cells = tree.nodes.new('ShaderNodeVectorMath')
    cells.operation = 'FLOOR'
    tree.links.new(scale.outputs[0], cells.inputs[0])
    random = tree.nodes.new('ShaderNodeTexWhiteNoise')
    random.noise_dimensions = '3D'
    tree.links.new(cells.outputs[0], random.inputs['Vector'])
    occupied = _math(tree, 'GREATER_THAN', random.outputs['Value'], 0.56)
    separate = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(scale.outputs[0], separate.inputs[0])
    x = _math(tree, 'FRACT', separate.outputs['X'])
    z = _math(tree, 'FRACT', separate.outputs['Z'])
    width = _math(tree, 'MULTIPLY', _math(tree, 'GREATER_THAN', x, 0.16), _math(tree, 'LESS_THAN', x, 0.77))
    height = _math(tree, 'MULTIPLY', _math(tree, 'GREATER_THAN', z, 0.17), _math(tree, 'LESS_THAN', z, 0.68))
    mask = _math(tree, 'MULTIPLY', occupied, _math(tree, 'MULTIPLY', width, height))
    strength = _math(tree, 'MULTIPLY', mask, 2.6)
    _set_input(tree, bsdf.inputs['Emission Color'], (1.0, 0.56, 0.23, 1.0))
    _set_input(tree, bsdf.inputs['Emission Strength'], 0.0)
    tree.links.new(strength, bsdf.inputs['Emission Strength'])
    # Preserve the original blue facade base-color shader and physical mullions.
    bsdf.inputs['Roughness'].default_value = 0.36
    bsdf.inputs['Metallic'].default_value = 0.34


def _materials(materials, state):
    night = state == 'night'
    for source, material in materials.items():
        if not material.use_nodes:
            continue
        name = source.name
        tree = material.node_tree
        bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if 'Gradient_Sky' in name:
            ramp = next((n for n in tree.nodes if n.type == 'VALTORGB'), None)
            if ramp:
                values = [(0.008, 0.019, 0.052, 1), (0.0038, 0.0095, 0.030, 1), (0.0018, 0.004, 0.014, 1)] if night else [
                    (0.66, 0.79, 0.91, 1), (0.33, 0.57, 0.85, 1), (0.12, 0.33, 0.70, 1)]
                elements = sorted(ramp.color_ramp.elements, key=lambda e: e.position)
                for i, element in enumerate(elements):
                    element.color = values[min(i, len(values) - 1)]
            continue
        if 'Cloud_Sea_Volume' in name:
            volume = next((n for n in tree.nodes if n.type == 'PRINCIPLED_VOLUME'), None)
            if volume:
                volume.inputs['Color'].default_value = (0.12, 0.19, 0.31, 1) if night else (0.78, 0.86, 0.95, 1)
                density = volume.inputs['Density']
                old = density.links[0].from_socket if density.is_linked else None
                if old:
                    _set_input(tree, density, 0.0)
                    factor = _math(tree, 'MULTIPLY', old, 0.13 if night else 0.60)
                    tree.links.new(factor, density)
            continue
        if not bsdf:
            continue
        if 'Haze_Layer' in name and night:
            layer = 1 if 'Layer_1' in name else 2 if 'Layer_2' in name else 3
            shade = [(0.018, 0.031, 0.056, 1), (0.014, 0.026, 0.050, 1), (0.011, 0.023, 0.046, 1)][layer - 1]
            _set_input(tree, bsdf.inputs['Base Color'], shade)
            _set_input(tree, bsdf.inputs['Emission Color'], shade)
            _set_input(tree, bsdf.inputs['Emission Strength'], 0.11)
        elif 'Curtain_Wall_Glass' in name and night:
            _night_windows(material)
        elif 'Distant_Planet' in name and night:
            ramp = next((n for n in tree.nodes if n.type == 'VALTORGB'), None)
            if ramp:
                ramp.color_ramp.elements[0].color = (0.07, 0.09, 0.13, 1)
                ramp.color_ramp.elements[-1].color = (0.49, 0.54, 0.63, 1)
            _set_input(tree, bsdf.inputs['Emission Strength'], 0.60)
        elif 'Fine_Cyan_Lines' in name:
            _set_input(tree, bsdf.inputs['Emission Strength'], 1.55 if night else 0.10)


def _lighting(scene, state):
    night = state == 'night'
    for obj in scene.objects:
        original = obj.get('window_v8_source_name', obj.name)
        if 'Large_Distant_Planet' in original:
            obj.hide_render = not night
        if obj.type != 'LIGHT':
            continue
        if obj.data.type == 'SUN':
            obj.data.energy = 0.15 if night else 3.0
            obj.data.color = (0.51, 0.67, 1.0) if night else (1.0, 0.955, 0.88)
            obj.data.angle = math.radians(1.6 if night else 0.526)
            direction = Vector((-10, 6, 17) if night else (9, -12, 16.5))
            obj.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
        elif obj.data.type == 'AREA':
            obj.data.energy = 300 if night else 1800
            obj.data.color = (0.40, 0.60, 1.0) if night else (0.68, 0.82, 1.0)
    scene.world.use_nodes = True
    tree = scene.world.node_tree
    tree.nodes.clear()
    background = tree.nodes.new('ShaderNodeBackground')
    output = tree.nodes.new('ShaderNodeOutputWorld')
    background.inputs['Color'].default_value = (0.022, 0.038, 0.077, 1) if night else (0.46, 0.65, 0.86, 1)
    background.inputs['Strength'].default_value = 0.32 if night else 0.40
    tree.links.new(background.outputs[0], output.inputs['Surface'])


def render_window_states(output_directory=None, width=1536, height=672, states=('day', 'night')):
    """Render original 3D city geometry to paired PNGs and return their paths.

    Optional states=('night',) supports a focused re-render without touching the
    other output. Outputs are public assets; the original .blend remains intact.
    """
    destination = Path(output_directory) if output_directory else OUTPUT
    destination.mkdir(parents=True, exist_ok=True)
    previous = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    source = _source_scene()
    report = {'source_scene': source.name, 'source_objects': len(source.objects),
              'source_unchanged': True, 'renders': {}, 'paths': {}}
    try:
        for state in states:
            if state not in {'day', 'night'}:
                raise ValueError("states may only include 'day' and 'night'")
            scene, materials = _copy_scene(source, state)
            _materials(materials, state)
            _lighting(scene, state)
            path = destination / ('window-' + state + '.png')
            scene.render.engine = 'BLENDER_EEVEE'
            scene.render.resolution_x = width
            scene.render.resolution_y = height
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGB'
            scene.render.image_settings.color_depth = '8'
            scene.render.film_transparent = False
            scene.render.filepath = str(path)
            scene.view_settings.view_transform = 'AgX'
            scene.view_settings.look = 'AgX - Medium High Contrast'
            scene.view_settings.exposure = -0.25 if state == 'day' else -0.10
            scene.view_settings.gamma = 1.0
            if bpy.context.window:
                bpy.context.window.scene = scene
            bpy.ops.render.render(write_still=True, scene=scene.name)
            report['paths'][state] = str(path)
            report['renders'][state] = {
                'scene': scene.name, 'width': width, 'height': height,
                'bytes': path.stat().st_size, 'engine': scene.render.engine,
                'sun_energy': 3.0 if state == 'day' else 0.15,
                'exposure': scene.view_settings.exposure,
                'moon_visible': state == 'night',
                'warm_procedural_lit_windows': state == 'night',
            }
    finally:
        if bpy.context.window:
            bpy.context.window.scene = previous
    return report
