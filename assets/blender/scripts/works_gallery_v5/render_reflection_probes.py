"""Read-only V4 reflection capture. Default validates setup; pass --render for GPU work.

Blender --background --python render_reflection_probes.py -- --render
No .blend file is written. Temporary camera/ground/visibility changes live in RAM.
"""
import argparse
import fcntl
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
import bake_gallery as util

SOURCE = ROOT / 'assets/blender/works-gallery-v5.blend'
SKY_SOURCE = ROOT / 'assets/blender/gallery-atmosphere-sky-v1.blend'
SKY_METADATA = ROOT / 'public/textures/gallery-atmosphere-v1/SKY_SOURCE.json'
OUT = ROOT / 'public/textures/works-gallery-v5'
MANIFEST = OUT / 'reflection-SOURCE.json'
WORLD_NAMES = {'day': 'DAY physical multiscattering atmosphere',
               'night': 'NIGHT quiet blue atmosphere'}
SAMPLES = {'day': 32, 'night': 48}
REQUESTED_PROBE_LOCATION = (0.0, 3.36, 2.7)
PROBE_LOCATION = (0.12, 3.36, 2.7)  # Original point is inside the V4 central mullion.
CAMERA_ROTATION = (math.pi / 2, 0.0, 0.0)
SIZE = (2048, 1024)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    pending.replace(path)


def owner(obj):
    while obj:
        if obj.get('asset_id'):
            return str(obj['asset_id'])
        obj = obj.parent
    return None


def is_glass(material):
    if material is None:
        return False
    if material.get('architecture_glass') or material.name.startswith('GALLERY_ARCH_GLASS_PBR'):
        return True
    if 'glass' in material.name.lower():
        return True
    if material.use_nodes:
        return any(n.type == 'BSDF_PRINCIPLED' and
                   n.inputs.get('Transmission Weight') and
                   n.inputs['Transmission Weight'].default_value > .1
                   for n in material.node_tree.nodes)
    return False


def configure_visibility(scene):
    hidden, preserved_glass = [], []
    allowed = {'gallery.architecture.glazing', 'gallery.environment.terrace'}
    for obj in scene.objects:
        if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            continue
        mats = list(obj.data.materials)
        glass = [m for m in mats if is_glass(m)]
        if not glass:
            continue
        own = owner(obj)
        if own in allowed:
            if len(glass) != len(mats):
                raise RuntimeError('Mixed opaque/glass architecture object needs explicit split: ' + obj.name)
            obj.hide_render = True
            hidden.append({'name': obj.name, 'owner': own, 'materials': [m.name for m in glass]})
        else:
            preserved_glass.append({'name': obj.name, 'owner': own, 'hidden_originally': obj.hide_render})
    if not any(o['owner'] == 'gallery.architecture.glazing' for o in hidden):
        raise RuntimeError('No architectural glazing found; refusing an unverified capture')
    return hidden, preserved_glass


def temporary_ground(scene):
    size, z = 256.0, -.88
    h = size / 2
    mesh = bpy.data.meshes.new('REFLECTION_ONLY neutral ground mesh')
    mesh.from_pydata([(-h, -h, z), (h, -h, z), (h, h, z), (-h, h, z)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new('REFLECTION_ONLY neutral stone ground', mesh)
    scene.collection.objects.link(obj)
    obj['export_exclude'] = True
    mat = bpy.data.materials.new('REFLECTION_ONLY neutral fine stone')
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new('ShaderNodeOutputMaterial')
    p = tree.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Metallic'].default_value = .04
    p.inputs['Roughness'].default_value = .66
    tree.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    coords = tree.nodes.new('ShaderNodeTexCoord')
    noise = tree.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 32
    noise.inputs['Detail'].default_value = 2
    noise.inputs['Roughness'].default_value = .58
    tree.links.new(coords.outputs['Object'], noise.inputs['Vector'])
    ramp = tree.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .15
    ramp.color_ramp.elements[0].color = (.225, .233, .239, 1)
    ramp.color_ramp.elements[1].position = .85
    ramp.color_ramp.elements[1].color = (.258, .269, .277, 1)
    tree.links.new(noise.outputs['Fac'], ramp.inputs[0])
    tree.links.new(ramp.outputs[0], p.inputs['Base Color'])
    bump = tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .055
    bump.inputs['Distance'].default_value = .009
    tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    tree.links.new(bump.outputs[0], p.inputs['Normal'])
    mesh.materials.append(mat)
    return {'name': obj.name, 'size_meters': [size, size], 'blender_z': z, 'web_y': z,
            'saved_to_source': False, 'material': 'same neutral stone parameters as gallery-atmosphere-v1',
            'added_lights': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true', help='Enable actual GPU renders after scheduled GPU window')
    parser.add_argument('--state', choices=('both', 'day', 'night'), default='both')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    for path in (SOURCE, SKY_SOURCE, SKY_METADATA):
        if not path.is_file():
            raise RuntimeError('Required input is not ready: ' + str(path))
    hashes = {rel(path): sha(path) for path in (SOURCE, SKY_SOURCE, SKY_METADATA)}
    sky_metadata = json.loads(SKY_METADATA.read_text())
    if sha(SKY_SOURCE) != sky_metadata['source_sha256']:
        raise RuntimeError('Sky source differs from its validated metadata')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.data.scenes.get('WORKS_GALLERY_V4')
    if scene is None:
        raise RuntimeError('Expected WORKS_GALLERY_V4 source scene')
    bpy.context.window.scene = scene
    lighting_world = scene.world
    original_lights = {o.name: {'matrix': [list(row) for row in o.matrix_world],
                               'type': o.data.type, 'base_power': o.get('base_power')}
                       for o in scene.objects if o.type == 'LIGHT'}
    with bpy.data.libraries.load(str(SKY_SOURCE), link=False) as (source_data, loaded):
        for name in WORLD_NAMES.values():
            if name not in source_data.worlds:
                raise RuntimeError('Missing calibrated world: ' + name)
        loaded.worlds = [WORLD_NAMES['day'], WORLD_NAMES['night']]
    worlds = dict(zip(('day', 'night'), loaded.worlds))
    hidden, preserved_glass = configure_visibility(scene)
    ground = temporary_ground(scene)
    data = bpy.data.cameras.new('REFLECTION_ONLY calibrated panorama')
    camera = bpy.data.objects.new('REFLECTION_ONLY calibrated panorama', data)
    scene.collection.objects.link(camera)
    camera.location = PROBE_LOCATION
    camera.rotation_euler = CAMERA_ROTATION
    camera['export_exclude'] = True
    data.type = 'PANO'
    data.panorama_type = 'EQUIRECTANGULAR'
    data.latitude_min, data.latitude_max = -math.pi / 2, math.pi / 2
    data.longitude_min, data.longitude_max = -math.pi, math.pi
    data.clip_start, data.clip_end = .025, 1000
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'  # Setup/check mode never requests GPU resources.
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .025
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 7
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 6
    scene.cycles.transparent_max_bounces = 8
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.gamma = 1
    bpy.context.view_layer.update()
    sun = next(o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN')
    sun_direction = (sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    calibrated_sun = Vector(sky_metadata['sun_blender_direction']).normalized()
    error = math.degrees(sun_direction.angle(calibrated_sun))
    if error > .1:
        raise RuntimeError(f'Gallery sun and sky differ by {error:.4f} degrees')
    if not args.render:
        print(json.dumps({'check_complete': True, 'rendered': False, 'gpu_requested': False,
                          'source_sha256': hashes[rel(SOURCE)], 'scene': scene.name,
                          'hidden_glass': len(hidden), 'preserved_other_glass': len(preserved_glass),
                          'sun_direction_error_degrees': error, 'resolution': SIZE,
                          'samples': SAMPLES}), flush=True)
        for path, expected in hashes.items():
            assert sha(ROOT / path) == expected, path
        return
    OUT.mkdir(parents=True, exist_ok=True)
    backend = util._device(scene)
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    records = []
    if previous.get('input_sha256') == hashes and previous.get('camera_blender_location') == list(PROBE_LOCATION):
        for record in previous.get('renders', []):
            path = ROOT / record['path']
            if path.is_file() and sha(path) == record['sha256']:
                records.append(record)
    manifest = {'complete': False, 'type': 'Actual Blender Cycles reflection probe; not AI imagery',
                'source': rel(SOURCE), 'source_sha256': hashes[rel(SOURCE)], 'input_sha256': hashes,
                'world_source': rel(SKY_SOURCE), 'camera_blender_location': list(PROBE_LOCATION),
                'requested_probe_location': list(REQUESTED_PROBE_LOCATION),
                'probe_adjustment': 'Shifted 0.12m along X to avoid the solid central window mullion at the requested point; orientation and Y/Z unchanged.',
                'camera_web_location': [PROBE_LOCATION[0], PROBE_LOCATION[2], -PROBE_LOCATION[1]],
                'camera_rotation_euler': list(CAMERA_ROTATION), 'projection': 'EQUIRECTANGULAR',
                'resolution': list(SIZE), 'cycles': backend, 'hidden_architectural_glass': hidden,
                'preserved_other_glass': preserved_glass, 'ground': ground,
                'original_lights': original_lights, 'sun_blender_direction': list(sun_direction),
                'sun_web_direction': [sun_direction.x, sun_direction.z, -sun_direction.y],
                'sun_direction_error_degrees': error,
                'runtime_uv_contract': sky_metadata['runtime_uv_contract'],
                'color_management': 'AgX Medium High Contrast, day +0.18EV / night 0EV; display-referred sRGB LDR. Decode sRGB once; no second tone mapping.',
                'limitation': 'Single local probe captures static surroundings. Not an HDR irradiance map or view-dependent planar reflection; box projection can reduce parallax error.',
                'renders': records, 'source_blends_written': False, 'compression_complete': False}
    atomic_json(MANIFEST, manifest)
    states = ('day', 'night') if args.state == 'both' else (args.state,)
    for state in states:
        # The setter rebuilds its active World. Never let it clear a borrowed sky.
        scene.world = lighting_world
        original_lighting = set_lighting(scene, state)
        scene.world = worlds[state]
        for obj in scene.objects:
            if obj.name in original_lights:
                assert [list(row) for row in obj.matrix_world] == original_lights[obj.name]['matrix']
        scene.cycles.samples = SAMPLES[state]
        output = OUT / f'reflection-{state}.png'
        pending = OUT / f'.reflection-{state}.pending.png'
        scene.render.filepath = str(pending)
        started = time.monotonic()
        with open('/tmp/room-portfolio-blender-gpu.lock', 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            bpy.ops.render.render(write_still=True)
        assert util._png_size(pending) == SIZE
        pending.replace(output)
        record = {'state': state, 'path': rel(output), 'sha256': sha(output),
                  'bytes': output.stat().st_size, 'resolution': list(SIZE),
                  'samples': SAMPLES[state], 'seconds': round(time.monotonic() - started, 3),
                  'world': worlds[state].name, 'original_lighting_setter': original_lighting,
                  'lights': {o.name: {'energy': o.data.energy, 'color': list(o.data.color)}
                             for o in scene.objects if o.type == 'LIGHT'}}
        manifest['renders'] = [r for r in manifest['renders'] if r['state'] != state] + [record]
        atomic_json(MANIFEST, manifest)
        print(json.dumps(record), flush=True)
    for path, expected in hashes.items():
        assert sha(ROOT / path) == expected, 'Input changed during capture: ' + path
    manifest['complete'] = {r['state'] for r in manifest['renders']} == {'day', 'night'}
    manifest['source_inputs_unchanged'] = True
    manifest['gpu_jobs_complete'] = True
    atomic_json(MANIFEST, manifest)
    print(json.dumps({'complete': manifest['complete'], 'gpu_jobs_complete': True,
                      'manifest': rel(MANIFEST), 'source_inputs_unchanged': True}), flush=True)


if __name__ == '__main__':
    main()
