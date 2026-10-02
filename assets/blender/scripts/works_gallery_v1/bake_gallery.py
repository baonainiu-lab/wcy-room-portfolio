"""Bake four gallery atlases with one shared UV layout for day and night.

Blender API: bake_state('day'|'night', indices=None, prepared_path=None,
                        output_directory=None).
CLI: blender --background --python bake_gallery.py -- --state day [--indices 0 1]
The prepared and editable .blend files are read-only inputs to this phase.
"""
import argparse
import hashlib
import importlib
import json
import struct
import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREPARED = ROOT / "assets/blender/works-gallery-bake-v1.blend"
OUT = ROOT / "public/textures/works-gallery-v1"
REPORTS = ROOT / "assets/blender/works-gallery-v1"
SCENE_NAME = "WEB_WORKS_GALLERY_V1"
ATLAS_SIZES = (4096, 3072, 4096, 4096)
TARGET_NODE = "GALLERY_BAKE_TARGET"
IMAGE_PREFIX = "GALLERY_BAKE_ATLAS_"
PASS_FILTER = {"DIRECT", "INDIRECT", "COLOR", "DIFFUSE", "GLOSSY", "EMIT"}


def _json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def _relative(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_size(path):
    with Path(path).open("rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RuntimeError("Invalid PNG output: " + str(path))
    return struct.unpack(">II", header[16:24])


def _device(scene):
    try:
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "METAL"
        preferences.get_devices()
        available = [d for d in preferences.devices if d.type == "METAL"]
        for device in preferences.devices:
            device.use = device.type == "METAL"
        scene.cycles.device = "GPU" if available else "CPU"
        return {"device": scene.cycles.device, "backend": "METAL" if available else "CPU",
                "names": [d.name for d in available]}
    except Exception as exc:
        scene.cycles.device = "CPU"
        return {"device": "CPU", "backend": "CPU", "fallback_reason": str(exc)}


def setup_state(state, prepared_path=None):
    if state not in {"day", "night"}:
        raise ValueError("Lighting state must be 'day' or 'night'.")
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is None:
        path = Path(prepared_path or PREPARED).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is None or not scene.get("preparation_id"):
        raise RuntimeError("A prepared WEB_WORKS_GALLERY_V1 scene is required.")
    bpy.context.window.scene = scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .035
    scene.cycles.max_bounces = 7
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 6
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.gamma = 1
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.target = "IMAGE_TEXTURES"
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    lighting_module = importlib.import_module("gallery_build")
    # gallery_build's setter scans global warm materials. Restore materials not
    # owned by this disposable scene, then set its isolated warm copies explicitly.
    materials = {m for obj in scene.objects if obj.type == "MESH"
                 for m in obj.data.materials if m}
    external_values = []
    for material in bpy.data.materials:
        if material not in materials and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    socket = node.inputs.get("Emission Strength")
                    if socket:
                        external_values.append((socket, socket.default_value))
    try:
        report = lighting_module.set_lighting(scene, state)
    finally:
        for socket, value in external_values:
            socket.default_value = value
    for material in materials:
        original = material.get("source_material", material.name)
        if str(original).startswith("GALLERY_warm") and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    socket = node.inputs.get("Emission Strength")
                    if socket and not socket.is_linked:
                        socket.default_value = 1.2 if state == "day" else 3.3
    report.update(_device(scene))
    report.update(samples=40, state=state, preparation_id=scene["preparation_id"],
                  color_management="AgX save_render to sRGB PNG", passes=sorted(PASS_FILTER))
    return scene, report


def _bake_atlas(scene, atlas, output, device_report):
    meshes = [o for o in scene.objects if o.type == "MESH" and o.get("web_export")
              and o.get("web_kind") == "baked" and o.get("bake_atlas", -1) == atlas]
    if not meshes:
        raise RuntimeError("No baked mesh members for atlas %d." % atlas)
    image = bpy.data.images.get(IMAGE_PREFIX + str(atlas))
    size = ATLAS_SIZES[atlas]
    if image is None or tuple(image.size) != (size, size):
        raise RuntimeError("Missing or incorrectly sized prepared atlas %d." % atlas)
    for obj in meshes:
        if not obj.data.uv_layers.get("BakeUV"):
            raise RuntimeError("Missing BakeUV on " + obj.name)
        for material in obj.data.materials:
            target = material.node_tree.nodes.get(TARGET_NODE) if material and material.use_nodes else None
            if target is None or target.image != image:
                raise RuntimeError("Invalid atlas destination material on " + obj.name)
            material.node_tree.nodes.active = target
    visibility = {obj: obj.hide_render for obj in meshes}
    proxies, proxy_data = [], []
    pending = output.with_name("." + output.stem + ".pending.png")
    started = time.monotonic()
    try:
        bpy.ops.object.select_all(action="DESELECT")
        # Joining only disposable proxy meshes lets Blender clear and bake an
        # entire atlas exactly once; the independently interactive scene survives.
        for obj in meshes:
            proxy = obj.copy()
            proxy.data = obj.data.copy()
            scene.collection.objects.link(proxy)
            transform = obj.matrix_world.copy()
            proxy.parent = None
            proxy.matrix_world = transform
            proxy.hide_render = False
            proxy.hide_set(False)
            proxy["web_export"] = False
            proxy["export_exclude"] = True
            for key in ("asset_id", "stableAssetId", "stable_asset_id"):
                if key in proxy:
                    del proxy[key]
            proxy.select_set(True)
            proxies.append(proxy)
            proxy_data.append(proxy.data)
            obj.hide_render = True
        bpy.context.view_layer.objects.active = proxies[0]
        if len(proxies) > 1:
            bpy.ops.object.join()
        proxy = bpy.context.view_layer.objects.active
        proxy.name = "GALLERY_BAKE_PROXY_A%d" % atlas
        proxies = [proxy]
        bpy.context.view_layer.update()
        bake_args = dict(type="COMBINED", pass_filter=PASS_FILTER, uv_layer="BakeUV",
                         margin=16, use_clear=True, use_selected_to_active=False)
        try:
            bpy.ops.object.bake(**bake_args)
        except RuntimeError as exc:
            if scene.cycles.device != "GPU":
                raise
            device_report["runtime_fallback_reason"] = str(exc)
            device_report["device"] = "CPU"
            device_report["backend"] = "CPU"
            scene.cycles.device = "CPU"
            bpy.ops.object.bake(**bake_args)
        image.save_render(str(pending), scene=scene)
        if _png_size(pending) != (size, size):
            raise RuntimeError("Baked PNG dimensions are wrong for atlas %d." % atlas)
        pending.replace(output)
        return {"atlas": atlas, "path": _relative(output), "resolution": [size, size],
                "bytes": output.stat().st_size, "sha256": _hash(output), "margin": 16,
                "device": scene.cycles.device, "seconds": round(time.monotonic() - started, 2)}
    finally:
        for proxy in proxies:
            try:
                bpy.data.objects.remove(proxy, do_unlink=True)
            except ReferenceError:
                pass
        for data in proxy_data:
            try:
                if data.users == 0:
                    bpy.data.meshes.remove(data)
            except ReferenceError:
                pass
        for obj, hidden in visibility.items():
            obj.hide_render = hidden
        if pending.exists():
            pending.unlink()
        bpy.context.view_layer.update()


def bake_state(state, indices=None, prepared_path=None, output_directory=None):
    started = time.monotonic()
    indices = list(range(4)) if indices is None else list(indices)
    if not indices or any(type(i) is not int or i not in range(4) for i in indices):
        raise ValueError("indices must contain atlas integers from 0 through 3.")
    if len(indices) != len(set(indices)):
        raise ValueError("An atlas index may only be baked once per call.")
    scene, lighting = setup_state(state, prepared_path)
    output = Path(output_directory or OUT).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / (state + "-manifest.json")
    progress_path = REPORTS / ("bake-" + state + "-progress.json")
    previous = {}
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            previous = {}
    records = {}
    if previous.get("preparation_id") == scene["preparation_id"] and previous.get("state") == state:
        for record in previous.get("atlases", []):
            index = record.get("atlas")
            path = output / ("%s-%s.png" % (state, index))
            if index in range(4) and path.is_file() and record.get("sha256") == _hash(path):
                records[index] = record
    manifest = {"state": state, "preparation_id": scene["preparation_id"],
        "prepared": _relative(prepared_path or PREPARED), "scene": SCENE_NAME,
        "lighting": lighting, "atlases": [], "complete": False}
    _json(progress_path, dict(manifest, phase="preparing", current_atlas=None))
    try:
        for atlas in indices:
            _json(progress_path, dict(manifest, phase="baking", current_atlas=atlas,
                                     completed=sorted(records), elapsed=round(time.monotonic() - started, 2)))
            records[atlas] = _bake_atlas(scene, atlas, output / ("%s-%d.png" % (state, atlas)), lighting)
            manifest["atlases"] = [records[i] for i in sorted(records)]
            manifest["complete"] = len(records) == 4
            manifest["seconds"] = round(time.monotonic() - started, 2)
            _json(manifest_path, manifest)
    except Exception as exc:
        _json(progress_path, dict(manifest, phase="failed", error=str(exc), completed=sorted(records),
                                 elapsed=round(time.monotonic() - started, 2)))
        raise
    scene["last_bake_state"] = state
    scene["last_bake_manifest"] = json.dumps(manifest, ensure_ascii=False)
    _json(progress_path, dict(manifest, phase="complete" if manifest["complete"] else "partial",
                             current_atlas=None))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("day", "night"), required=True)
    parser.add_argument("--indices", nargs="+", type=int)
    parser.add_argument("--prepared", type=Path, default=PREPARED)
    parser.add_argument("--output-directory", type=Path, default=OUT)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    print(json.dumps(bake_state(args.state, args.indices, args.prepared, args.output_directory),
                     ensure_ascii=False, indent=2))
