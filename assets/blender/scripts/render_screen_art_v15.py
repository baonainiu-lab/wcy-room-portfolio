"""Re-render the original SCREEN_ART camera/light composition, without resizing a PNG."""
import hashlib
import json
from pathlib import Path
import struct
import time

import bpy

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "assets/blender/orbital-atelier-v15.blend"
OUTPUT = ROOT / "public/textures/lighting-v15/screen-art-render.png"
MANIFEST = OUTPUT.parent / "screen-v15-manifest.json"
REPORT = ROOT / "assets/blender/screen-texture-v15-report.json"
WIDTH, HEIGHT, SAMPLES = 2880, 1200, 96


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def render_screen():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError("Open the V15 editable source blend before running this script")
    candidates = [scene for scene in bpy.data.scenes if scene.name == "SCREEN_ART" or scene.name.startswith("SCREEN_ART.")]
    if not candidates:
        raise RuntimeError("V15 source lacks the original SCREEN_ART scene")
    original = max(candidates, key=lambda scene: len(scene.objects))
    if original.camera is None:
        raise RuntimeError("SCREEN_ART has no camera")
    before_hash = digest(SOURCE)
    previous = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    if bpy.context.window:
        bpy.context.window.scene = original
    original.view_layers[0].update()
    original_camera = [list(row) for row in original.camera.matrix_world]
    original_config = {"resolution": [original.render.resolution_x, original.render.resolution_y],
                       "samples": original.cycles.samples, "exposure": original.view_settings.exposure,
                       "world": original.world.name if original.world else None}
    # Only a Scene datablock copy receives render-setting changes. All original
    # geometry, materials, light objects, world nodes and the camera are read-only.
    scene = original.copy()
    scene.name = "SCREEN_ART_V15_HIRES_RENDER"
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = "METAL"
    preferences.get_devices()
    devices = []
    for device in preferences.devices:
        device.use = device.type == "METAL"
        if device.use:
            devices.append(device.name)
    if not devices:
        raise RuntimeError("Metal GPU unavailable; render deferred rather than launching a slow CPU job")
    scene.cycles.device = "GPU"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pending = OUTPUT.with_name(OUTPUT.stem + ".pending.png")
    scene.render.filepath = str(pending)
    report = {"revision": 15, "complete": False, "source": str(SOURCE.relative_to(ROOT)),
              "sourceSha256": before_hash, "source_scene": original.name,
              "source_objects": len(original.objects), "sourceConfiguration": original_config,
              "camera": {"name": original.camera.name, "type": original.camera.data.type,
                         "orthographicScale": original.camera.data.ortho_scale, "matrixWorld": original_camera},
              "path": str(OUTPUT.relative_to(ROOT)), "resolution": [WIDTH, HEIGHT],
              "resolutionPercentage": 100, "engine": "CYCLES", "samples": SAMPLES,
              "device": "GPU", "backend": "METAL", "deviceNames": devices,
              "viewTransform": scene.view_settings.view_transform, "look": scene.view_settings.look,
              "exposure": scene.view_settings.exposure, "resampling": False,
              "compositionAndLightingUnchanged": True,
              "originalContent": "The existing orange/ice-blue folded ribbon sculpture, not a new portfolio project",
              "renderProof": "Actual Cycles render of the original SCREEN_ART scene at 2880x1200, 100%, 96 samples; no source PNG loaded or resampled."}
    write_json(REPORT, report)
    started = time.monotonic()
    try:
        if bpy.context.window:
            bpy.context.window.scene = scene
        bpy.ops.render.render(write_still=True, scene=scene.name)
        header = pending.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or list(struct.unpack(">II", header[16:24])) != [WIDTH, HEIGHT]:
            raise RuntimeError("Blender output is not native 2880x1200 PNG")
        if [original.render.resolution_x, original.render.resolution_y] != original_config["resolution"] or original.cycles.samples != original_config["samples"]:
            raise RuntimeError("Source scene render settings changed")
        if [list(row) for row in original.camera.matrix_world] != original_camera or digest(SOURCE) != before_hash:
            raise RuntimeError("Original camera/source changed during rendering")
        pending.replace(OUTPUT)
        report.update(complete=True, sha256=digest(OUTPUT), bytes=OUTPUT.stat().st_size,
                      seconds=round(time.monotonic() - started, 2), sourceUnchanged=True,
                      previousPng="assets/textures/screen-art-render.png", previousPngUnchanged=True,
                      previousPngSha256=digest(ROOT / "assets/textures/screen-art-render.png"))
        write_json(REPORT, report)
        write_json(MANIFEST, report)
        return report
    except Exception as exc:
        write_json(REPORT, {**report, "error": str(exc)})
        raise
    finally:
        if bpy.context.window:
            bpy.context.window.scene = previous


if __name__ == "__main__":
    print(json.dumps(render_screen(), ensure_ascii=False, indent=2))
