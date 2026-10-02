"""V13 localized night practicals. Geometry, UVs and daytime are untouched.

Run configure_night_warm() after the shared V8 night lighting setup. Values
are scene-linear approximations of 2700–3000 K practical lamps, deliberately
confined by existing desk, shelf and lamp housings.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
WARM_2700 = (1.0, .39, .105)
WARM_2900 = (1.0, .445, .145)
WARM_3000 = (1.0, .475, .17)


def configure_night_warm(scene):
    """Apply deterministic, idempotent night-only local practical adjustments."""
    if scene.get('v8_lighting_state') != 'night' and scene.get('lighting_state') != 'night':
        raise RuntimeError('V13 warm practicals may only run in a night scene.')
    for obj in scene.objects:
        if obj.type in {'MESH', 'LIGHT'} and len(obj.users_scene) > 1:
            raise RuntimeError('Night authoring object is shared across scenes: '+obj.name)
    changed = []
    rules = {
        'Floor_Lamp_Practical': (56., WARM_2900, 72.),
        'Interior_Warm_0': (34., WARM_3000, 82.),
        'Interior_Warm_1': (32., WARM_2700, 72.),
        'Interior_Warm_2': (22., WARM_2900, 82.),
    }
    for obj in scene.objects:
        if obj.type != 'LIGHT':
            continue
        rule = next((value for name, value in rules.items() if name in obj.name), None)
        if rule:
            obj.data = obj.data.copy()
            obj.data.energy, obj.data.color = rule[0], rule[1]
            if obj.data.type == 'AREA':
                obj.data.spread = math.radians(rule[2])
            changed.append(obj)
        elif 'L_Niche_' in obj.name:
            obj.data = obj.data.copy()
            obj.data.color = WARM_3000
            obj.data.energy = min(obj.data.energy, 34.)
            changed.append(obj)

    # Hidden sources are inset into existing structural undersides; their
    # emission faces point below the surface so no omnidirectional fill leaks.
    specifications = [
        dict(id='Desk_Underside', location=(-3.48, -.25, 1.70),
             target=(-3.10, -.50, .25), power=32., color=WARM_2700,
             width=.78, height=.075, spread=85.,
             fixture='concealed channel below cantilever desk; soft floor pool beside compute core'),
        dict(id='Window_Shelf_Left', location=(-.65, 2.40, 1.275),
             target=(-.65, 1.85, .22), power=22., color=WARM_2700,
             width=1.35, height=.055, spread=78.,
             fixture='concealed underside of existing window shelf, left segment'),
        dict(id='Window_Shelf_Right', location=(2.65, 2.40, 1.275),
             target=(2.65, 1.78, .22), power=17., color=WARM_2900,
             width=.78, height=.055, spread=76.,
             fixture='concealed underside of existing window shelf, right segment'),
    ]
    collection = bpy.data.collections.new('V13_LOCAL_NIGHT_PRACTICALS')
    scene.collection.children.link(collection)
    for old in list(scene.objects):
        if old.get('v13_generated_light'):
            bpy.data.objects.remove(old, do_unlink=True)
    for spec in specifications:
        data = bpy.data.lights.new('V13_WARM_' + spec['id'], 'AREA')
        data.energy = spec['power']
        data.color = spec['color']
        data.shape = 'RECTANGLE'
        data.size, data.size_y = spec['width'], spec['height']
        data.spread = math.radians(spec['spread'])
        obj = bpy.data.objects.new(data.name, data)
        collection.objects.link(obj)
        obj.location = spec['location']
        obj.rotation_euler = (Vector(spec['target'])-obj.location).to_track_quat('-Z','Y').to_euler()
        obj['v13_generated_light'] = True
        obj['v8_generated_light'] = True
        obj['fixture_intent'] = spec['fixture']
        changed.append(obj)

    # Copy just affected night material slots. A source day scene may share a
    # material, so edits must never alter its original datablock.
    material_copies = {}
    emitter_report = []
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        for i, mat in enumerate(list(obj.data.materials)):
            if not mat or not mat.node_tree:
                continue
            is_small = 'IW8_MAT_WarmDiffuser' in mat.name
            is_ring = 'V5_MAT_WarmDiffuser' in mat.name
            is_shelf = 'MAT_Warm_White' in mat.name
            if not (is_small or is_ring or is_shelf):
                continue
            # Material slots belong to mesh data. Copying a material alone
            # would still mutate another object's slots if mesh data is linked.
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            if mat not in material_copies:
                new = mat.copy()
                new.name = 'V13_NIGHT_' + mat.name
                for node in new.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Emission Color'].default_value = (*WARM_2900,1)
                        node.inputs['Emission Strength'].default_value = 1.05 if is_small else 1.8
                material_copies[mat] = new
                emitter_report.append({'original':mat.name,'nightMaterial':new.name,
                    'linearColor':list(WARM_2900),'strength':1.05 if is_small else 1.8})
            obj.data.materials[i] = material_copies[mat]
    scene.view_layers[0].update()
    report = {'revision':13,'geometryInheritedFrom':12,'scene':scene.name,
        'intent':'Low local amber pools below existing desk and window shelf, warmer desk/reading/ring lamps; preserve cool night ambient and dark walls.',
        'colorTemperature':'Approximate 2700–3000 K, scene-linear RGB; no whole-image tint',
        'worldAndExposureUnchanged':True,'newLightObjects':len(specifications),
        'newSources':specifications,'nightEmitterChanges':emitter_report,
        'lights':[{'name':o.name,'watts':o.data.energy,'color':list(o.data.color),
                   'position':list(o.matrix_world.translation)} for o in changed]}
    scene['v13_local_warm_lighting'] = json.dumps(report)
    (ROOT/'assets/blender/night-warm-v13-design.json').write_text(json.dumps(report,indent=2)+'\n')
    # The shared bake setup writes its baseline report before this callback.
    # Extend V13's report with the actual final lights, never overwrite V8–V12.
    base_report = ROOT/'assets/blender/lighting-night-v13.json'
    if scene.name == 'WEB_DUAL_V8' and base_report.exists():
        complete = json.loads(base_report.read_text())
        complete['v13LocalPracticalDesign'] = report
        lights = [o for o in scene.objects if o.type == 'LIGHT']
        complete['light_count'] = len(lights)
        complete['active_light_count'] = sum(o.data.energy > 0 for o in lights)
        complete['lights'] = [{'name':o.name,'type':o.data.type,'energy':o.data.energy,
                               'color_linear':list(o.data.color),
                               'position':list(o.matrix_world.translation)} for o in lights]
        base_report.write_text(json.dumps(complete,indent=2)+'\n')
    return report


def save_sources():
    """Save only new V13 files; preserve V12 sources and the editable day scene."""
    from bake_geometry_fingerprint import fingerprints
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-atelier-v12.blend'))
    scene = bpy.data.scenes['ORIGINAL_NIGHT_V12']
    bpy.context.window.scene = scene
    report = configure_night_warm(scene)
    scene.name = 'ORIGINAL_NIGHT_V13'
    bpy.data.scenes['ORIGINAL_DAY_V12'].name = 'ORIGINAL_DAY_V13'
    scene['lighting_source_revision'] = 13
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/orbital-atelier-v13.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v12.blend'))
    scene = bpy.data.scenes['WEB_DUAL_V8']
    bpy.context.window.scene = scene
    baseline = fingerprints(scene, include_shading=True)
    scene['v13_lighting_design'] = json.dumps(report)
    scene['geometry_revision'] = 12
    scene['lighting_revision'] = 13
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v13.blend'))
    assert baseline == fingerprints(scene, include_shading=True)
    prep = json.loads((ROOT/'assets/blender/dual-bake-v12-preparation.json').read_text())
    prep.update(lightingRevision=13,geometryInheritedFrom=12,
                source='assets/blender/orbital-atelier-v13.blend',
                prepared='assets/blender/orbital-dual-bake-v13.blend',
                geometryUvNormalsUnchanged=True,
                notes='V13 copies V12 prepared geometry exactly; only night light configuration and baked maps change.')
    (ROOT/'assets/blender/dual-bake-v13-preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
    return report
