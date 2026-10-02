"""Render the actual V14 web room for the approved daylight-editorial homepage.

The GLB and source blend stay unchanged. Only the two exterior environment
branches are hidden in this disposable scene; all 37 interior roots remain.
"""
import bpy
import hashlib
import json
import time
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
MODEL = ROOT / 'public/models/orbital-atelier-v14.glb'
OUTPUT = ROOT / 'public/textures/home/room-day-v14.png'
REPORT = ROOT / 'renders/homepage-b-room-render.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    started = time.time()
    model_hash = digest(MODEL)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'assets/blender/orbital-dual-bake-v14.blend'))
    source_camera = bpy.data.scenes['WEB_DUAL_V8'].camera
    camera = source_camera.copy()
    camera.data = source_camera.data.copy()
    matrix = source_camera.matrix_world.copy()
    scene = bpy.data.scenes.new('HOMEPAGE_B_V14_DISPOSABLE')
    bpy.context.window.scene = scene
    scene.collection.objects.link(camera)
    camera.matrix_world = matrix
    scene.camera = camera
    bpy.ops.import_scene.gltf(filepath=str(MODEL))

    hidden = []
    interior_ids = []
    interior_roots = []
    for obj in scene.objects:
        asset_id = obj.get('asset_id', '')
        if asset_id.startswith('environment.'):
            hidden.append(asset_id)
            for item in [obj, *obj.children_recursive]:
                item.hide_render = True
        elif asset_id:
            interior_ids.append(asset_id)
            if not obj.parent or not obj.parent.get('asset_id'):
                interior_roots.append(asset_id)
    assert len(interior_ids) == 93, len(interior_ids)
    assert len(interior_roots) == 37, len(interior_roots)
    assert sorted(hidden) == ['environment.orbital_dock', 'environment.warm_gallery']

    materials = {m for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render for m in obj.data.materials if m}
    image_paths = []
    for material in materials:
        if not material.node_tree:
            continue
        if material.name.startswith('WEB8_LIGHTMAP_'):
            atlas = int(material.name.removeprefix('WEB8_LIGHTMAP_').split('.')[0])
            path = ROOT / 'public/textures/lighting-v14' / f'day-{atlas}.png'
        elif material.name.startswith('WEB8_WINDOW_CITY'):
            path = ROOT / 'public/textures/lighting-v14/window-day.png'
        else:
            continue
        image = bpy.data.images.load(str(path), check_existing=False)
        image.colorspace_settings.name = 'sRGB'
        image_paths.append(str(path.relative_to(ROOT)))
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                node.image = image
            if node.type == 'EMISSION':
                node.inputs['Strength'].default_value = 1.0

    # Orthographic fitting uses all actual visible mesh vertices, so neither the
    # wall tops nor the rounded rectangular room platform can be cropped.
    bpy.context.view_layer.update()
    inverse = camera.matrix_world.inverted()
    points = [inverse @ (obj.matrix_world @ vertex.co)
              for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render
              for vertex in obj.data.vertices]
    min_x = min(v.x for v in points)
    max_x = max(v.x for v in points)
    min_y = min(v.y for v in points)
    max_y = max(v.y for v in points)
    width, height = 1800, 1250
    margin = 0.045
    camera.data.type = 'ORTHO'
    camera.data.sensor_fit = 'HORIZONTAL'
    camera.data.ortho_scale = max(max_x - min_x, (max_y - min_y) * width / height) / (1 - margin * 2)
    offset = Vector(((min_x + max_x) / 2, (min_y + max_y) / 2, 0))
    camera.location += camera.matrix_world.to_3x3() @ offset

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    try:
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'METAL'
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == 'METAL'
        scene.cycles.device = 'GPU'
    except Exception:
        scene.cycles.device = 'CPU'
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.compression = 100
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new('Homepage B transparent warm neutral world')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes['Background']
    background.inputs['Color'].default_value = (0.72, 0.67, 0.59, 1)
    background.inputs['Strength'].default_value = 0.35
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(OUTPUT)
    bpy.ops.render.render(write_still=True)
    assert digest(MODEL) == model_hash
    rendered = bpy.data.images.load(str(OUTPUT), check_existing=False)
    pixels = np.empty(width * height * 4, dtype=np.float32)
    rendered.pixels.foreach_get(pixels)
    alpha = pixels.reshape(height, width, 4)[::-1, :, 3]
    rows, columns = np.nonzero(alpha > 0)
    alpha_bounds = [int(columns.min()), int(rows.min()), int(columns.max() + 1), int(rows.max() + 1)]
    assert alpha_bounds[0] > 0 and alpha_bounds[1] > 0
    assert alpha_bounds[2] < width and alpha_bounds[3] < height
    report = {
        'sourceModel': str(MODEL.relative_to(ROOT)),
        'sourceModelSha256': model_hash,
        'sourceModelUnchanged': True,
        'sourceBlendSaved': False,
        'renderType': 'Actual V14 GLB with the exported daytime baked maps, transparent film; no AI asset generation or raster retouching.',
        'hiddenExteriorBranches': sorted(hidden),
        'interiorRootCount': len(interior_roots),
        'interiorAssetIdCount': len(interior_ids),
        'roomAndRectangularPlatformComplete': True,
        'camera': {'type': camera.data.type, 'location': list(camera.location), 'rotation': list(camera.rotation_euler), 'orthoScale': camera.data.ortho_scale},
        'output': str(OUTPUT.relative_to(ROOT)),
        'resolution': [width, height],
        'colorMode': 'RGBA',
        'transparentBackground': True,
        'alphaBoundsExclusive': alpha_bounds,
        'alphaRange': [float(alpha.min()), float(alpha.max())],
        'fullyTransparentPixels': int(np.count_nonzero(alpha == 0)),
        'fullyOpaquePixels': int(np.count_nonzero(alpha == 1)),
        'transparentMarginPixels': {'left': alpha_bounds[0], 'top': alpha_bounds[1], 'right': width - alpha_bounds[2], 'bottom': height - alpha_bounds[3]},
        'fileBytes': OUTPUT.stat().st_size,
        'sha256': digest(OUTPUT),
        'dayMaps': sorted(set(image_paths)),
        'samples': scene.cycles.samples,
        'engine': scene.render.engine,
        'seconds': round(time.time() - started, 3),
        'limitations': 'Static homepage artwork, not interactive scene or frame-rate evidence. Glass shading may differ slightly from the browser shader.'
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == '__main__':
    run()
