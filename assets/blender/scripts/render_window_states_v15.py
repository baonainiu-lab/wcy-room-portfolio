"""Real 3072x1344 window renders from unchanged ENV_CITY; never resize V14 PNGs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time

import bpy

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "assets/blender/orbital-atelier-v15.blend"
OUTPUT = ROOT / "public/textures/lighting-v15"
REPORT = ROOT / "assets/blender/window-texture-v15-report.json"
PROGRESS = ROOT / "assets/blender/window-texture-v15-progress.json"
INSPECTION = ROOT / "assets/blender/window-texture-v15-inspection.json"
WIDTH, HEIGHT = 3072, 1344


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def png_dimensions(path):
    data = Path(path).read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("Invalid PNG output: " + str(path))
    return list(struct.unpack(">II", data[16:24]))


def scene_facts(scene):
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()
    camera = scene.camera
    return {
        "scene": scene.name, "objects": len(scene.objects), "engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "resolutionPercentage": scene.render.resolution_percentage,
        "camera": None if camera is None else {
            "name": camera.name, "type": camera.data.type, "lens": camera.data.lens,
            "orthographicScale": camera.data.ortho_scale,
            "matrixWorld": [list(row) for row in camera.matrix_world],
        },
        "cyclesSamples": scene.cycles.samples,
        "meshes": sum(obj.type == "MESH" for obj in scene.objects),
        "curves": sum(obj.type == "CURVE" for obj in scene.objects),
        "lights": sum(obj.type == "LIGHT" for obj in scene.objects),
    }


def inspect_source():
    cities = [scene for scene in bpy.data.scenes if scene.name == "ENV_CITY" or scene.name.startswith("ENV_CITY.")]
    if not cities:
        raise RuntimeError("V15 source has no authored ENV_CITY; refusing to generate a replacement composition")
    city = max(cities, key=lambda scene: (len(scene.objects), scene.name))
    if city.camera is None:
        raise RuntimeError("Original ENV_CITY has no camera")
    screen_scenes = [scene for scene in bpy.data.scenes if scene.name == "SCREEN_ART" or scene.name.startswith("SCREEN_ART.")]
    screen = max(screen_scenes, key=lambda scene: len(scene.objects)) if screen_scenes else None
    screen_image = ROOT / "assets/textures/screen-art-render.png"
    inspection = {
        "source": str(SOURCE.relative_to(ROOT)), "sourceSha256": digest(SOURCE),
        "window": scene_facts(city),
        "screen": scene_facts(screen) if screen else None,
        "screenCurrentPng": {"path": str(screen_image.relative_to(ROOT)),
                             "dimensions": png_dimensions(screen_image), "sha256": digest(screen_image)},
        "plannedWindowResolution": [WIDTH, HEIGHT], "resampling": False,
        "screenRecommendation": {
            "trueRerenderPossible": bool(screen and screen.camera),
            "suggestedResolution": [2880, 1200], "suggestedCyclesSamples": 96,
            "compositionChange": False, "originalContentOverwriteAuthorized": False,
            "note": "Existing SCREEN_ART retains actual folded glass/metal ribbon geometry and its camera; a real 2x rerender can preserve original composition. No screen render is performed by this script.",
        },
    }
    write_json(INSPECTION, inspection)
    return city, inspection


def render_states(states=("day", "night")):
    city, inspection = inspect_source()
    module_path = ROOT / "assets/blender/scripts/render_window_states_v8.py"
    spec = importlib.util.spec_from_file_location("original_window_lighting_for_v15", module_path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    original.PREFIX = "WINDOW_V15_"
    original.OUTPUT = OUTPUT
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {"revision": 15, "source": inspection["source"], "sourceSha256": inspection["sourceSha256"],
              "source_scene": city.name, "source_objects": len(city.objects),
              "camera": inspection["window"]["camera"], "lightingSource": str(module_path.relative_to(ROOT)),
              "lightingSourceSha256": digest(module_path), "resampling": False,
              "originalCompositionPreserved": True, "source_unchanged": True, "renders": {}, "paths": {},
              "screenUnchanged": True, "complete": False}
    previous = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    try:
        for state in states:
            if state not in ("day", "night"):
                raise ValueError("Unknown lighting state")
            write_json(PROGRESS, {**report, "phase": "rendering", "currentState": state})
            scene, materials = original._copy_scene(city, state)
            original._materials(materials, state)
            original._lighting(scene, state)
            output = OUTPUT / f"window-{state}.png"
            pending = output.with_name(output.stem + ".pending.png")
            scene.render.engine = "BLENDER_EEVEE"
            scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGB"
            scene.render.image_settings.color_depth = "8"
            scene.render.film_transparent = False
            scene.render.filepath = str(pending)
            scene.view_settings.view_transform = "AgX"
            scene.view_settings.look = "AgX - Medium High Contrast"
            scene.view_settings.exposure = -0.25 if state == "day" else -0.10
            scene.view_settings.gamma = 1.0
            eevee = getattr(scene, "eevee", None)
            if eevee and hasattr(eevee, "taa_render_samples"):
                eevee.taa_render_samples = 128
            if bpy.context.window:
                bpy.context.window.scene = scene
            before = time.monotonic()
            bpy.ops.render.render(write_still=True, scene=scene.name)
            if png_dimensions(pending) != [WIDTH, HEIGHT]:
                raise RuntimeError("Blender did not render the requested native resolution")
            pending.replace(output)
            report["paths"][state] = str(output)
            report["renders"][state] = {
                "scene": scene.name, "width": WIDTH, "height": HEIGHT,
                "bytes": output.stat().st_size, "sha256": digest(output),
                "engine": scene.render.engine, "renderPercentage": scene.render.resolution_percentage,
                "samples": getattr(eevee, "taa_render_samples", None),
                "seconds": round(time.monotonic() - before, 2),
                "sun_energy": 3.0 if state == "day" else 0.15,
                "exposure": scene.view_settings.exposure, "moon_visible": state == "night",
                "warm_procedural_lit_windows": state == "night", "resampling": False,
            }
            write_json(REPORT, report)
        if digest(SOURCE) != inspection["sourceSha256"]:
            raise RuntimeError("Source blend changed during the render session")
        report["complete"] = len(report["renders"]) == len(states)
        report["seconds"] = round(time.monotonic() - started, 2)
        write_json(REPORT, report)
        write_json(OUTPUT / "window-v15-manifest.json", {
            "revision": 15, "complete": set(report["renders"]) == {"day", "night"},
            "source": report["source"], "sourceSha256": report["sourceSha256"],
            "source_scene": city.name, "source_objects": len(city.objects),
            "camera": report["camera"], "resampling": False,
            "originalCompositionPreserved": True, "sourceUnchanged": True,
            "renderProof": "Blender rendered original ENV_CITY geometry at native resolution_percentage=100; no source PNG was loaded or resampled.",
            "renders": [{"state": state, "path": str(Path(report["paths"][state]).relative_to(ROOT)),
                         "resolution": [WIDTH, HEIGHT], **record} for state, record in report["renders"].items()],
            "report": str(REPORT.relative_to(ROOT)),
        })
        write_json(PROGRESS, {**report, "phase": "complete", "currentState": None})
        return report
    except Exception as exc:
        write_json(PROGRESS, {**report, "phase": "failed", "error": str(exc)})
        raise
    finally:
        if bpy.context.window:
            bpy.context.window.scene = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--state", choices=("day", "night", "both"), default="both")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError("Open the V15 editable source blend before running this script")
    result = inspect_source()[1] if args.inspect_only else render_states(("day", "night") if args.state == "both" else (args.state,))
    print(json.dumps(result, ensure_ascii=False, indent=2))
