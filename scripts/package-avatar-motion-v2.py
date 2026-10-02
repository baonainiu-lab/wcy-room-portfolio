#!/usr/bin/env python3
"""Non-creative packaging for imagegen avatar animation frames.

Matting is deliberately specific to #ff00ff. Near-pure key pixels (maximum
RGB distance <= 12), OR bright magenta with min(R,B)>=220,
min(R,B)-G>=170 and abs(R-B)<=45, become transparent. The hue gate covers
imagegen's non-flat/compressed magenta (observed corners around 236/36/236)
without keying less-saturated antialiased foreground edges. Edge despill starts
within two pixels of transparent/key background and propagates only through
connected magenta-dominant pixels (at most 32 passes), never through normal
foreground colors or into isolated non-key-colored interior regions.
They must have BOTH red and blue at least 24 above green, with abs(R-B)<=100.
The estimated key contribution is (min(R,B)-G)/255; remove this contribution
from RGB and alpha without moving or drawing pixels. Ivory/gray lack that
magenta dominance; blue lacks red dominance; orange/gold/brown lack blue
dominance. Those colors are not keyed. No white/gray-background removal,
interior recoloring, per-frame fitting, pose synthesis or network operations.

Matting cannot distinguish genuine magenta artwork from a magenta key. Use
only source images whose character palette excludes magenta, and inspect the
result. --matte-only preserves canvas size, coordinates and input file.

Full packaging consumes three same-sized, evenly divisible 2x2 sheets in
reading order: keys=02/05/08/11; inA=01/03/04/06; inB=07/09/10/12.
One uniform scale and one common X/Y offset apply to ALL twelve cells. The
default scale is min(baseline_width/cell_width, baseline_height/cell_height),
with the resulting whole cell centered in the baseline canvas. Override the
global --scale/--offset-x/--offset-y only after checking the entire sequence.
No frame is auto-fitted, individually centered, rotated, warped or repaired.
Explicit --align-ground permits ONLY whole-frame integer Y translation to
the baseline's foot line, after reporting the raw foot line. Its default
maximum is eight pixels; larger deviations are reported and rejected. It
does not change scale, limb pixels or pose, and is disabled by default.

The baseline must already be a PNG RGBA on the final fixed canvas. It is
byte-copied to 00 and 13, never resized or re-encoded. Source sheets are
preserved in a separate tmp directory, outside the contract output. An
existing output directory may contain only keyframe-prompts.md. Existing
artifacts are not deleted or overwritten; use a new version directory.

Output is keyframe-prompts.md, keyframe/, fullframe/, spritesheet.png,
contact-sheet.png, preview.gif and manifest.json. The installed skill's GIF
helper and validator are imported locally. A nonzero validation result,
clipping, missing transparency, or baseline drift returns exit code 2 but
leaves the clearly marked review package and per-frame diagnostics intact.
Structural success is never visual approval. Inspect contact sheet and GIF.

Requires Python and Pillow; this tool never installs dependencies, accesses
the network, invokes a shell, or creates motion artwork.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


KEY_INDICES = (2, 5, 8, 11)
SHEET_INDICES = {"keys": KEY_INDICES, "inA": (1, 3, 4, 6), "inB": (7, 9, 10, 12)}


def pixels_of(image: Image.Image):
    getter = getattr(image, "get_flattened_data", None)
    return list(getter() if getter else image.getdata())


def bbox_at_alpha(image: Image.Image, threshold: int = 1):
    alpha = image.getchannel("A")
    if threshold > 1:
        alpha = alpha.point(lambda value: 255 if value >= threshold else 0)
    bbox = alpha.getbbox()
    return list(bbox) if bbox else None


def matte_magenta(image: Image.Image, *, tolerance: int = 12,
                  edge_radius: int = 2, alpha_cutoff: int = 2):
    """Return same-sized RGBA and a report. No geometric or pose changes."""
    rgba = image.convert("RGBA")
    source = pixels_of(rgba)
    background = []
    hard_removed = 0
    for red, green, blue, alpha in source:
        is_key = (max(255 - red, green, 255 - blue) <= tolerance
                  or (min(red, blue) >= 220 and min(red, blue) - green >= 170 and abs(red - blue) <= 45))
        background.append(255 if alpha == 0 or is_key else 0)
        hard_removed += int(is_key and alpha > 0)
    key_mask = Image.new("L", rgba.size)
    key_mask.putdata(background)
    propagation_passes = 0
    if edge_radius:
        key_mask = key_mask.filter(ImageFilter.MaxFilter(2 * edge_radius + 1))
        candidates = Image.new("L", rgba.size)
        candidates.putdata([255 if alpha > 0 and min(red, blue) - green >= 24 and abs(red - blue) <= 100 else 0
                            for red, green, blue, alpha in source])
        connected = ImageChops.multiply(key_mask, candidates)
        for _ in range(32):
            expanded = ImageChops.lighter(connected, ImageChops.multiply(connected.filter(ImageFilter.MaxFilter(3)), candidates))
            if ImageChops.difference(expanded, connected).getbbox() is None:
                break
            connected = expanded
            propagation_passes += 1
        key_mask = ImageChops.lighter(key_mask, connected)
    adjacent = pixels_of(key_mask)
    output = []
    softened = 0
    for pixel, is_background, near_background in zip(source, background, adjacent):
        red, green, blue, alpha = pixel
        if is_background:
            output.append((0, 0, 0, 0))
            continue
        dominance = min(red, blue) - green
        if edge_radius and near_background and dominance >= 24 and abs(red - blue) <= 100:
            key_fraction = dominance / 255.0
            keep = 1.0 - key_fraction
            new_alpha = round(alpha * keep)
            if new_alpha <= alpha_cutoff or keep <= 0:
                output.append((0, 0, 0, 0))
            else:
                recover = lambda channel, key: max(0, min(255, round((channel - key_fraction * key) / keep)))
                output.append((recover(red, 255), recover(green, 0), recover(blue, 255), new_alpha))
            softened += 1
        else:
            output.append(pixel)
    result = Image.new("RGBA", rgba.size)
    result.putdata(output)
    width, height = rgba.size
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    residue = sum(1 for red, green, blue, alpha in output
                  if alpha > 24 and min(red, blue) - green >= 48 and abs(red - blue) <= 100)
    report = {
        "canvas": [width, height], "bbox": bbox_at_alpha(result),
        "bboxAlpha16": bbox_at_alpha(result, 16),
        "hardKeyPixelsRemoved": hard_removed, "edgePixelsDespilled": softened,
        "connectedEdgePropagationPasses": propagation_passes,
        "magentaCandidatePixelsRemaining": residue,
        "transparentCorners": all(result.getpixel(point)[3] == 0 for point in corners),
        "parameters": {"key": "#FF00FF", "maxRgbDistance": tolerance,
                       "brightMagentaMinRedBlue": 220, "brightMagentaDominanceMin": 170,
                       "brightMagentaRedBlueDifferenceMax": 45,
                       "edgeRadius": edge_radius, "edgeMagentaDominanceMin": 24,
                       "edgeRedBlueDifferenceMax": 100, "edgeAlphaCutoff": alpha_cutoff},
        "geometryChanged": False, "grayOrWhiteKeying": False,
    }
    return result, report


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_helper(skill_dir: Path, filename: str):
    path = skill_dir / "scripts" / filename
    if not path.is_file():
        raise ValueError(f"Installed skill helper is missing: {path}")
    spec = importlib.util.spec_from_file_location(f"avatar_motion_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load installed helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def frame_report(image: Image.Image, *, index: int, baseline_bottom: int):
    bbox = bbox_at_alpha(image)
    width, height = image.size
    margins = None if not bbox else {
        "left": bbox[0], "top": bbox[1], "right": width - bbox[2], "bottom": height - bbox[3],
    }
    corners = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
    return {
        "index": index, "bbox": bbox, "bboxAlpha16": bbox_at_alpha(image, 16),
        "footBaselineExclusive": bbox[3] if bbox else None,
        "footBaselineDelta": bbox[3] - baseline_bottom if bbox else None,
        "margins": margins, "empty": bbox is None,
        "canvasEdgeRisk": bool(margins and min(margins.values()) <= 2),
        "transparentCorners": all(image.getpixel(point)[3] == 0 for point in corners),
    }


def place_cell(cell: Image.Image, *, canvas_size, scale: float, offset,
               tolerance: int, edge_radius: int, alpha_cutoff: int):
    matted, matte_report = matte_magenta(cell, tolerance=tolerance,
                                        edge_radius=edge_radius, alpha_cutoff=alpha_cutoff)
    source_bbox = bbox_at_alpha(matted)
    cell_width, cell_height = cell.size
    source_margins = None if not source_bbox else {
        "left": source_bbox[0], "top": source_bbox[1],
        "right": cell_width - source_bbox[2], "bottom": cell_height - source_bbox[3],
    }
    target_size = (max(1, round(cell_width * scale)), max(1, round(cell_height * scale)))
    scaled = matted.resize(target_size, Image.Resampling.LANCZOS) if target_size != matted.size else matted.copy()
    if alpha_cutoff:
        # Remove only sub-1% resampling/key fringe, never fit the subject bbox.
        data = [(r, g, b, a) if a > alpha_cutoff else (0, 0, 0, 0)
                for r, g, b, a in pixels_of(scaled)]
        scaled.putdata(data)
    scaled_bbox = bbox_at_alpha(scaled)
    projected = None if not scaled_bbox else [scaled_bbox[0] + offset[0], scaled_bbox[1] + offset[1],
                                             scaled_bbox[2] + offset[0], scaled_bbox[3] + offset[1]]
    clipped = bool(projected and (projected[0] < 0 or projected[1] < 0
                                  or projected[2] > canvas_size[0] or projected[3] > canvas_size[1]))
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(scaled, offset)
    return canvas, {
        "matte": matte_report, "sourceCellBbox": source_bbox,
        "sourceCellMargins": source_margins,
        "sourceCellEdgeRisk": bool(source_margins and min(source_margins.values()) <= 2),
        "projectedBboxBeforeCanvasClip": projected, "contentClippedByCanvas": clipped,
    }


def preserve_source(source: Path, destination: Path):
    if source.resolve() == destination.resolve():
        return
    if destination.exists():
        if sha256(source) != sha256(destination):
            raise ValueError(f"Different source already exists in tmp directory: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def package(args) -> int:
    baseline_path = args.baseline.resolve()
    output = args.output.resolve()
    source_paths = {"keys": args.keys.resolve(), "inA": args.in_a.resolve(), "inB": args.in_b.resolve()}
    tmp_dir = (args.tmp_dir or output.parent / "tmp" / f"{output.name}-sources").resolve()
    if output == tmp_dir or output in tmp_dir.parents or tmp_dir in output.parents:
        raise ValueError("Temporary source and final output directories must be separate, not nested.")
    if any(path == output or output in path.parents for path in [baseline_path, *source_paths.values()]):
        raise ValueError("Inputs must be outside the final output directory.")
    if output.exists() and (not output.is_dir() or any(item.name != "keyframe-prompts.md" for item in output.iterdir())):
        raise ValueError("Output must be new/empty or contain only keyframe-prompts.md; use a new version directory.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.prefix):
        raise ValueError("--prefix must contain only ASCII letters, digits, _ and -.")
    with Image.open(baseline_path) as source:
        if source.mode != "RGBA" or source.format != "PNG":
            raise ValueError("Baseline must already be a final-canvas PNG in RGBA mode.")
        baseline = source.copy()
    baseline_bbox = bbox_at_alpha(baseline)
    if not baseline_bbox:
        raise ValueError("Baseline is empty.")
    baseline_diagnostics = frame_report(baseline, index=0, baseline_bottom=baseline_bbox[3])
    if not baseline_diagnostics["transparentCorners"]:
        raise ValueError("Baseline corners are not transparent; gray/white backgrounds are never auto-keyed.")
    sheets = {}
    for name, path in source_paths.items():
        with Image.open(path) as source:
            sheets[name] = source.convert("RGBA")
    sheet_size = sheets["keys"].size
    if any(sheet.size != sheet_size for sheet in sheets.values()):
        raise ValueError("All three source sheets must have identical pixel dimensions; no per-sheet fitting is allowed.")
    if sheet_size[0] % 2 or sheet_size[1] % 2:
        raise ValueError("Source sheet width and height must be even for exact 2x2 equal-cell splitting.")
    cell_size = (sheet_size[0] // 2, sheet_size[1] // 2)
    canvas_size = baseline.size
    scale = args.scale if args.scale is not None else min(canvas_size[0] / cell_size[0], canvas_size[1] / cell_size[1])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("--scale must be finite and greater than zero.")
    target_size = (max(1, round(cell_size[0] * scale)), max(1, round(cell_size[1] * scale)))
    offset = (args.offset_x if args.offset_x is not None else round((canvas_size[0] - target_size[0]) / 2),
              args.offset_y if args.offset_y is not None else round((canvas_size[1] - target_size[1]) / 2))
    gif_helper, gif_helper_path = load_helper(args.skill_dir, "fullframes_to_gif.py")
    validator, validator_path = load_helper(args.skill_dir, "validate_14frame_pattern.py")
    if args.prompts and not args.prompts.is_file():
        raise ValueError(f"Prompt file not found: {args.prompts}")
    prompt_path = output / "keyframe-prompts.md"
    if args.prompts and args.prompts.resolve() != prompt_path.resolve() and prompt_path.exists():
        raise ValueError("Existing keyframe-prompts.md will not be overwritten; omit --prompts to preserve it.")
    frames = {0: baseline, 13: baseline.copy()}
    reports = {0: baseline_diagnostics,
               13: frame_report(baseline, index=13, baseline_bottom=baseline_bbox[3])}
    for name, indices in SHEET_INDICES.items():
        sheet = sheets[name]
        for slot, index in enumerate(indices):
            column, row = slot % 2, slot // 2
            cell_box = (column * cell_size[0], row * cell_size[1], (column + 1) * cell_size[0], (row + 1) * cell_size[1])
            frame, processing = place_cell(sheet.crop(cell_box), canvas_size=canvas_size, scale=scale, offset=offset,
                                           tolerance=args.key_tolerance, edge_radius=args.edge_radius,
                                           alpha_cutoff=args.alpha_cutoff)
            raw_bbox = bbox_at_alpha(frame)
            raw_bottom = raw_bbox[3] if raw_bbox else None
            requested_shift = baseline_bbox[3] - raw_bottom if raw_bottom is not None else None
            alignment_error = None
            ground_shift = 0
            if args.align_ground and requested_shift is not None:
                if abs(requested_shift) > args.max_ground_shift:
                    alignment_error = f"raw foot delta {requested_shift:+d}px exceeds allowed {args.max_ground_shift}px; not aligned"
                elif raw_bbox[1] + requested_shift < 0 or raw_bbox[3] + requested_shift > canvas_size[1]:
                    alignment_error = "integer ground alignment would clip visible content; not aligned"
                else:
                    ground_shift = requested_shift
                    if ground_shift:
                        translated = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                        translated.paste(frame, (0, ground_shift))
                        frame = translated
            frames[index] = frame
            report = frame_report(frame, index=index, baseline_bottom=baseline_bbox[3])
            report.update({"sourceSheet": name, "sourceSlot": slot, "sourceCell": list(cell_box), **processing,
                           "rawBboxBeforeGroundAlignment": raw_bbox, "rawFootBaselineExclusive": raw_bottom,
                           "requestedGroundShiftY": requested_shift, "appliedGroundShiftY": ground_shift,
                           "groundAlignmentError": alignment_error})
            reports[index] = report
    output.mkdir(parents=True, exist_ok=True)
    for name, source in source_paths.items():
        preserve_source(source, tmp_dir / f"{name}{source.suffix.lower()}")
    full_dir, key_dir = output / "fullframe", output / "keyframe"
    full_dir.mkdir()
    key_dir.mkdir()
    for index in range(14):
        path = full_dir / f"{args.prefix}_{index:02d}.png"
        if index in (0, 13):
            shutil.copyfile(baseline_path, path)
        else:
            frames[index].save(path, format="PNG")
        if index in KEY_INDICES:
            shutil.copyfile(path, key_dir / path.name)
    prompts_status = "existing" if prompt_path.exists() else "placeholder-needs-root-prompts"
    if args.prompts and args.prompts.resolve() != prompt_path.resolve():
        shutil.copyfile(args.prompts, prompt_path)
        prompts_status = "copied-from-root"
    elif not prompt_path.exists():
        prompt_path.write_text("# Model-generated keyframe prompts\n\nPending: root must record the identity and screen-space topology lock, and the actual prompts used for 02 / 05 / 08 / 11 and the two in-between batches.\n\nThis packager only keys, splits, places and exports existing generated pixels; it creates no poses.\n", encoding="utf-8")
    width, height = canvas_size
    strip = Image.new("RGBA", (width * 14, height), (0, 0, 0, 0))
    label_height = 24
    contact = Image.new("RGB", (width * 7, (height + label_height) * 2), "white")
    labels = ImageDraw.Draw(contact)
    for index in range(14):
        frame = frames[index]
        strip.alpha_composite(frame, (index * width, 0))
        white = Image.new("RGBA", canvas_size, "white")
        white.alpha_composite(frame)
        column, row = index % 7, index // 7
        contact.paste(white.convert("RGB"), (column * width, row * (height + label_height)))
        label = f"{index:02d} / {'BASELINE' if index in (0, 13) else 'KEY' if index in KEY_INDICES else 'INBETWEEN'}"
        labels.text((column * width + 8, row * (height + label_height) + height + 5), label, fill="#19303c")
    strip.save(output / "spritesheet.png")
    contact.save(output / "contact-sheet.png")
    gif_helper.write_gif(fullframes_dir=full_dir, output=output / "preview.gif", duration_ms=args.duration_ms,
                         loop=0, background=(255, 255, 255), pattern=f"{args.prefix}_*.png")
    errors = validator.validate_pattern(baseline=baseline_path, keyframes_dir=key_dir, fullframes_dir=full_dir,
                                        preview=output / "preview.gif", prefix=args.prefix)
    if (full_dir / f"{args.prefix}_00.png").read_bytes() != baseline_path.read_bytes():
        errors.append("Frame 00 differs byte-for-byte from the baseline.")
    if (full_dir / f"{args.prefix}_13.png").read_bytes() != baseline_path.read_bytes():
        errors.append("Frame 13 differs byte-for-byte from the baseline.")
    for index in KEY_INDICES:
        filename = f"{args.prefix}_{index:02d}.png"
        if (key_dir / filename).read_bytes() != (full_dir / filename).read_bytes():
            errors.append(f"Key {index:02d} is not byte-identical to its full frame.")
    warnings = []
    for index, report in reports.items():
        if report.get("groundAlignmentError"):
            errors.append(f"Frame {index:02d}: {report['groundAlignmentError']}")
        if report.get("contentClippedByCanvas"):
            errors.append(f"Frame {index:02d} has visible content outside the fixed canvas.")
        if report.get("sourceCellEdgeRisk"):
            errors.append(f"Frame {index:02d} source silhouette is within 2px of its cell edge; inspect possible source cuts.")
        if report["canvasEdgeRisk"]:
            errors.append(f"Frame {index:02d} silhouette is within 2px of the output edge.")
        residue = report.get("matte", {}).get("magentaCandidatePixelsRemaining", 0)
        if residue:
            warnings.append(f"Frame {index:02d} retains {residue} possible magenta pixels; inspect key residue.")
    manifest = {
        "version": 2, "action": args.action or args.prefix,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "structural-check-failed-review-required" if errors else "structural-pass-visual-review-required",
        "frameCount": 14, "frameOrder": list(range(14)), "keyframeIndices": list(KEY_INDICES),
        "anchorIndices": [0, 2, 5, 8, 11, 13], "segmentInsertions": [1, 2, 2, 2, 1],
        "previewBackground": "#FFFFFF", "frameDurationMs": args.duration_ms, "loop": True,
        "canvas": {"width": width, "height": height, "mode": "RGBA"},
        "coordinateSpace": "screen-space", "activeLimb": args.active_limb,
        "activeShoulder": args.active_shoulder or (args.active_limb + " shoulder" if args.active_limb.startswith("screen-") else "not-applicable"),
        "anchorLimb": args.anchor_limb, "carriedProp": "terminal", "propHand": args.prop_hand,
        "baseline": {"path": str(baseline_path), "sha256": sha256(baseline_path), "byteCopiedTo": [0, 13]},
        "sources": {name: {"originalPath": str(path), "preservedPath": str(tmp_dir / f"{name}{path.suffix.lower()}"),
                            "sha256": sha256(path), "indices": list(SHEET_INDICES[name])}
                    for name, path in source_paths.items()},
        "sharedTransform": {"sourceSheet": list(sheet_size), "sourceCell": list(cell_size),
                            "scale": scale, "resampledCell": list(target_size), "offset": list(offset),
                            "perFrameFit": False, "perFrameTranslation": bool(args.align_ground), "rotation": 0,
                            "note": "One uniform scale and common offset, rounded to whole output pixels; no per-pose fitting."},
        "groundAlignment": {"enabled": bool(args.align_ground), "maxShiftPixels": args.max_ground_shift,
                            "type": "explicit whole-frame integer Y translation only",
                            "referenceFootBaselineExclusive": baseline_bbox[3],
                            "perFrameOffsets": {f"{index:02d}": [0, reports[index].get("appliedGroundShiftY", 0)] for index in range(14)}},
        "generation": {"poses": "model-generated source artwork supplied by root", "localPoseSynthesis": False,
                       "postProcessing": ["magenta matte and edge despill", "equal-cell split", "one shared canvas transform",
                                          "byte copies for endpoints and anchors", "spritesheet/contact/GIF packing"],
                       "promptFile": "keyframe-prompts.md", "promptsStatus": prompts_status},
        "validation": {"helperPath": str(validator_path), "helperSha256": sha256(validator_path),
                       "gifHelperPath": str(gif_helper_path), "gifHelperSha256": sha256(gif_helper_path),
                       "structuralPass": not errors, "errors": errors, "warnings": warnings,
                       "visualAcceptance": "pending-root-inspection", "frameReports": [reports[index] for index in range(14)]},
        "artifacts": {"fullframe": "fullframe/", "keyframe": "keyframe/", "spritesheet": "spritesheet.png",
                      "contactSheet": "contact-sheet.png", "preview": "preview.gif"},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": manifest["status"], "sharedTransform": manifest["sharedTransform"],
                      "rawFootBaselines": [reports[index].get("rawFootBaselineExclusive", reports[index]["footBaselineExclusive"]) for index in range(14)],
                      "footBaselines": [reports[index]["footBaselineExclusive"] for index in range(14)],
                      "errors": errors, "warnings": warnings, "manifest": str(output / "manifest.json")}, ensure_ascii=False, indent=2))
    return 2 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matte-only", nargs=2, metavar=("INPUT", "OUTPUT"), help="Only remove magenta key; preserve size and coordinates.")
    parser.add_argument("--key-tolerance", type=int, default=12)
    parser.add_argument("--edge-radius", type=int, default=2)
    parser.add_argument("--alpha-cutoff", type=int, default=2)
    parser.add_argument("--baseline", type=Path, help="Already standardized final-canvas RGBA PNG; copied unchanged to 00/13.")
    parser.add_argument("--keys", type=Path, help="2x2 source: 02,05,08,11 in reading order.")
    parser.add_argument("--in-a", type=Path, help="2x2 source: 01,03,04,06 in reading order.")
    parser.add_argument("--in-b", type=Path, help="2x2 source: 07,09,10,12 in reading order.")
    parser.add_argument("--output", type=Path, help="New contract-only output directory.")
    parser.add_argument("--tmp-dir", type=Path, help="Separate source archive directory; defaults to sibling tmp/<output-name>-sources.")
    parser.add_argument("--prefix", help="Frame filename prefix, e.g. avatar-look-up.")
    parser.add_argument("--action", help="Human-readable action name for the manifest.")
    parser.add_argument("--prompts", type=Path, help="Actual root-authored prompts to copy; otherwise preserve/create prompt file.")
    parser.add_argument("--scale", type=float, help="ONE shared uniform scale for all source cells; default whole-cell fit.")
    parser.add_argument("--offset-x", type=int, help="ONE common placement X; default center complete cell on baseline canvas.")
    parser.add_argument("--offset-y", type=int, help="ONE common placement Y; default center complete cell on baseline canvas.")
    parser.add_argument("--align-ground", action="store_true", help="Explicit whole-frame integer Y normalization to baseline feet; default OFF.")
    parser.add_argument("--max-ground-shift", type=int, default=8, help="Reject ground-alignment shifts beyond this number of pixels; default 8.")
    parser.add_argument("--duration-ms", type=int, default=100, help="GIF frame duration; default 100ms.")
    parser.add_argument("--active-limb", choices=("screen-left", "screen-right", "head", "torso"))
    parser.add_argument("--active-shoulder", help="Explicit active shoulder lock; inferred only from a screen-side limb.")
    parser.add_argument("--anchor-limb", choices=("screen-left", "screen-right"))
    parser.add_argument("--prop-hand", choices=("screen-left", "screen-right"))
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".codex/skills/2dimg2motion")
    args = parser.parse_args()
    if not 0 <= args.key_tolerance <= 32 or not 0 <= args.edge_radius <= 4 or not 0 <= args.alpha_cutoff <= 8:
        parser.error("Matte ranges: tolerance 0..32; edge-radius 0..4; alpha-cutoff 0..8.")
    if args.matte_only:
        source, output = map(Path, args.matte_only)
        if source.resolve() == output.resolve():
            parser.error("Input and output must be different; originals are never overwritten.")
        if output.exists():
            parser.error("Output already exists; choose a new versioned filename.")
        with Image.open(source) as image:
            result, report = matte_magenta(image, tolerance=args.key_tolerance,
                                           edge_radius=args.edge_radius, alpha_cutoff=args.alpha_cutoff)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format="PNG")
        report.update({"input": str(source.resolve()), "output": str(output.resolve())})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["transparentCorners"] and report["bbox"] else 2
    required = ("baseline", "keys", "in_a", "in_b", "output", "prefix", "active_limb", "anchor_limb", "prop_hand")
    missing = ["--" + name.replace("_", "-") for name in required if getattr(args, name) is None]
    if missing:
        parser.error("Full packaging requires " + ", ".join(missing))
    if args.duration_ms < 10:
        parser.error("--duration-ms must be at least 10ms.")
    if not 0 <= args.max_ground_shift <= 32:
        parser.error("--max-ground-shift must be between 0 and 32 pixels.")
    try:
        return package(args)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Packaging stopped: {error}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
