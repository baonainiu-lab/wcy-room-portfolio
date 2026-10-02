"""Bake actual day/night irradiance into the same eight independent-object UV atlases.

Open orbital-dual-bake-v8.blend through the Blender MCP background tool.
Call bake_state('day'|'night', indices=None, render_preview=False).
This never overwrites any editable source blend.
"""
import bpy, json, time
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
OUT = ROOT / 'public/textures/lighting-v8'
OUT.mkdir(parents=True, exist_ok=True)


def setup_state(state, report_revision=8):
    scene = bpy.data.scenes['WEB_DUAL_V8']
    bpy.context.window.scene = scene
    scope = {'__name__': 'lighting_states_v8'}
    exec(compile((ROOT/'assets/blender/scripts/lighting_states_v8.py').read_text(), 'lighting_states_v8.py', 'exec'), scope)
    report = scope['configure_lighting'](scene, state)
    scene.cycles.samples = 40
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .035
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 4
    preferences = bpy.context.preferences.addons['cycles'].preferences
    try:
        preferences.compute_device_type = 'METAL'
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == 'METAL'
        scene.cycles.device = 'GPU' if any(d.type == 'METAL' for d in preferences.devices) else 'CPU'
    except Exception:
        scene.cycles.device = 'CPU'
    materials = {m for o in scene.objects if o.get('web_export') and o.type == 'MESH' for m in o.data.materials if m}
    window = bpy.data.images.load(str(OUT/f'window-{state}.png'), check_existing=True)
    for material in materials:
        if not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image and 'window-city' in node.image.name:
                node.image = window
            if node.type == 'BSDF_PRINCIPLED':
                socket = node.inputs.get('Emission Strength')
                if socket and not socket.is_linked:
                    socket.default_value *= .2 if state == 'day' else 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = 'EXTEND'
    report['cycles_samples'] = scene.cycles.samples
    report['device'] = scene.cycles.device
    (ROOT/'assets/blender'/f'lighting-{state}-v{report_revision}.json').write_text(json.dumps(report, indent=2)+'\n')
    return scene


def bake_state(state, indices=None, render_preview=False, scene_transform=None, output_directory=None, revision=8):
    started = time.monotonic()
    scene = setup_state(state, report_revision=revision)
    if scene_transform:
        scene_transform(scene)
    output_directory = Path(output_directory) if output_directory else OUT
    output_directory.mkdir(parents=True, exist_ok=True)
    progress_path = ROOT/'assets/blender'/f'bake-{state}-v{revision}-progress.json'
    progress_path.write_text(json.dumps({'state':state,'completed':[],'phase':'preparing','elapsed':0}, indent=2)+'\n')
    if render_preview:
        scene.cycles.use_denoising = True
        scene.render.resolution_x = 1500
        scene.render.resolution_y = 1100
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(ROOT/'renders'/f'lighting-v{revision}-{state}-blender.png')
        bpy.ops.render.render(write_still=True)
    records = []
    for atlas in (range(8) if indices is None else indices):
        progress_path.write_text(json.dumps({'state':state,'completed':records,'phase':'baking','currentAtlas':atlas,'elapsed':round(time.monotonic()-started,2)}, indent=2)+'\n')
        meshes = [o for o in scene.objects if o.type == 'MESH' and o.get('web_export') and o.get('bake_atlas', -1) == atlas]
        if not meshes:
            raise RuntimeError(f'No objects for atlas {atlas}')
        bpy.ops.object.select_all(action='DESELECT')
        proxies = []
        for obj in meshes:
            proxy = obj.copy()
            proxy.data = obj.data.copy()
            scene.collection.objects.link(proxy)
            transform = obj.matrix_world.copy()
            proxy.parent = None
            proxy.matrix_world = transform
            proxy.hide_render = False
            proxy.select_set(True)
            proxies.append(proxy)
            obj.hide_render = True
            for mat in proxy.data.materials:
                if mat and mat.node_tree:
                    target = mat.node_tree.nodes.get('WEB8_BAKE_TARGET')
                    if target:
                        mat.node_tree.nodes.active = target
        bpy.context.view_layer.objects.active = proxies[0]
        bpy.ops.object.join()
        proxy = bpy.context.object
        proxy.name = f'V8_BAKE_PROXY_{atlas}'
        margin = 32 if atlas == 7 else 16
        bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'}, uv_layer='BakeUV', margin=margin, use_clear=True)
        path = output_directory/f'{state}-{atlas}.png'
        image = bpy.data.images[f'WEB8_ATLAS_{atlas}']
        image.save_render(str(path), scene=scene)
        bpy.data.objects.remove(proxy, do_unlink=True)
        for obj in meshes:
            obj.hide_render = False
        records.append({'atlas':atlas,'path':str(path.relative_to(ROOT)), 'resolution':list(image.size), 'margin':margin, 'bytes':path.stat().st_size})
        progress_path.write_text(json.dumps({'state':state,'completed':records,'phase':'baking','elapsed':round(time.monotonic()-started,2)}, indent=2)+'\n')
    return {'state':state,'atlases':records,'seconds':round(time.monotonic()-started,2)}
