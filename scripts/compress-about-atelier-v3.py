#!/usr/bin/env python3
"""Extract the four atelier PNG atlases and build a validated Basis/KTX2 GLB.

Usage: python3 scripts/compress-about-atelier-v3.py [--wait] [--threads 2]
The source GLB is never modified. All material definitions, including glass and
metal, remain identical; only ATELIER_LIGHTMAP_0..3 texture payloads change.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "public/models/about-atelier-v3.glb"
OUTPUT = ROOT / "public/models/about-atelier-v3-compressed.glb"
TEXTURES = ROOT / "public/textures/about-atelier-v3"
REPORT = ROOT / "assets/blender/about-atelier-v3-web/compression-report.json"
AUDIT = ROOT / "assets/blender/about-atelier-v3-audit.json"
ENCODER = ROOT / "tools/ktx-software/bin/toktx"
VALIDATOR = ROOT / "tools/ktx-software/bin/ktx"
JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942
KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"
ENCODING = "UASTC quality 2 + Zstd 9; sRGB; complete mip chain"
ATLAS_PATTERN = re.compile(r"ATELIER_LIGHTMAP_([0-3])\Z")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def atomic_bytes(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == blob:
        return
    pending = path.with_name(path.name + ".tmp")
    pending.write_bytes(blob)
    pending.replace(path)


def atomic_json(path, document):
    atomic_bytes(path, (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode())


def parse_glb(blob):
    require(len(blob) >= 20, "Truncated GLB")
    magic, version, total = struct.unpack_from("<III", blob)
    require(magic == 0x46546C67 and version == 2 and total == len(blob), "Invalid GLB header")
    chunks, offset = [], 12
    while offset < total:
        require(offset + 8 <= total, "Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", blob, offset)
        require(length % 4 == 0 and offset + 8 + length <= total, "Invalid GLB chunk bounds")
        chunks.append((kind, blob[offset + 8:offset + 8 + length]))
        offset += 8 + length
    require([kind for kind, _ in chunks].count(JSON_CHUNK) == 1, "Expected one JSON chunk")
    require([kind for kind, _ in chunks].count(BIN_CHUNK) == 1, "Expected one BIN chunk")
    require(chunks[0][0] == JSON_CHUNK, "GLB JSON must be the first chunk")
    document = json.loads(chunks[0][1])
    require(len(document.get("buffers", [])) == 1 and "uri" not in document["buffers"][0],
            "Expected one embedded buffer")
    binary = next(data for kind, data in chunks if kind == BIN_CHUNK)
    require(document["buffers"][0]["byteLength"] <= len(binary), "Truncated GLB binary buffer")
    return document, chunks, binary


def pack_glb(document, chunks, binary):
    body = bytearray()
    for kind, original in chunks:
        payload = (json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
                   if kind == JSON_CHUNK else binary if kind == BIN_CHUNK else original)
        payload += (b" " if kind == JSON_CHUNK else b"\0") * (-len(payload) % 4)
        body.extend(struct.pack("<II", len(payload), kind) + payload)
    return struct.pack("<III", 0x46546C67, 2, len(body) + 12) + body


def view_bytes(document, binary, index):
    require(isinstance(index, int) and 0 <= index < len(document["bufferViews"]),
            f"Invalid bufferView index: {index}")
    view = document["bufferViews"][index]
    require(view.get("buffer", 0) == 0, "External buffer unsupported")
    start, length = view.get("byteOffset", 0), view["byteLength"]
    require(0 <= start <= start + length <= document["buffers"][0]["byteLength"],
            f"Invalid bufferView bounds: {index}")
    return binary[start:start + length]


def asset_ids(document):
    ids = [node["extras"]["asset_id"] for node in document.get("nodes", [])
           if "asset_id" in node.get("extras", {})]
    require(all(isinstance(value, str) and value for value in ids), "Invalid asset_id")
    require(len(ids) == len(set(ids)) == 128, "Expected exactly 128 unique asset IDs")
    return sorted(ids)


def material_texture_indices(value):
    """Find texture references including those in PBR material extensions."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("Texture") and isinstance(child, dict) and "index" in child:
                yield child["index"]
            yield from material_texture_indices(child)
    elif isinstance(value, list):
        for child in value:
            yield from material_texture_indices(child)


def atlas_inventory(document, binary):
    atlases, target_materials = {}, set()
    for material_index, material in enumerate(document.get("materials", [])):
        name = material.get("name", "")
        if not name.startswith("ATELIER_LIGHTMAP_"):
            continue
        match = ATLAS_PATTERN.fullmatch(name)
        require(match is not None, f"Unexpected atlas material: {name}")
        atlas = int(match[1])
        require(atlas not in atlases, f"Duplicate atlas material: {name}")
        texture_index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
        texture = document["textures"][texture_index]
        require("KHR_texture_basisu" not in texture.get("extensions", {}), "Source atlas is already Basis")
        image_index = texture["source"]
        image = document["images"][image_index]
        require(image.get("mimeType") == "image/png" and "uri" not in image, "Expected embedded PNG atlas")
        view_index = image["bufferView"]
        png = view_bytes(document, binary, view_index)
        require(len(png) >= 33 and png[:8] == b"\x89PNG\r\n\x1a\n" and png[12:16] == b"IHDR",
                f"Invalid atlas PNG: {atlas}")
        resolution = list(struct.unpack_from(">II", png, 16))
        require(all(dimension > 0 for dimension in resolution), "Invalid PNG dimensions")
        atlases[atlas] = {"atlas": atlas, "material": material_index, "texture": texture_index,
                          "image": image_index, "bufferView": view_index, "png": png,
                          "resolution": resolution}
        target_materials.add(material_index)
    require(set(atlases) == set(range(4)), "Expected ATELIER_LIGHTMAP_0..3")
    for key in ("texture", "image", "bufferView"):
        require(len({row[key] for row in atlases.values()}) == 4, f"Atlases share a {key}")
    target_textures = {row["texture"] for row in atlases.values()}
    target_images = {row["image"] for row in atlases.values()}
    target_views = {row["bufferView"] for row in atlases.values()}
    for index, material in enumerate(document.get("materials", [])):
        if index not in target_materials:
            require(not set(material_texture_indices(material)) & target_textures,
                    "An atlas texture is shared by a non-atlas material")
    for index, texture in enumerate(document.get("textures", [])):
        if index not in target_textures:
            image_refs = [texture.get("source")]
            image_refs += [value.get("source") for value in texture.get("extensions", {}).values()
                           if isinstance(value, dict)]
            require(not set(image_refs) & target_images, "Atlas image shared by another texture")
    for index, image in enumerate(document.get("images", [])):
        if index not in target_images:
            require(image.get("bufferView") not in target_views, "Atlas view shared by another image")
    for accessor in document.get("accessors", []):
        referenced = [accessor.get("bufferView")]
        referenced += [row.get("bufferView") for row in accessor.get("sparse", {}).values()
                       if isinstance(row, dict)]
        require(not set(referenced) & target_views, "Atlas view shared by geometry")
    return atlases


def ktx_info(blob):
    require(len(blob) >= 80 and blob[:12] == KTX2_MAGIC, "Invalid KTX2 header")
    vk, _, width, height, depth, layers, faces, levels, compression = struct.unpack_from("<9I", blob, 12)
    require(vk == 0 and depth == 0 and layers == 0 and faces == 1, "Expected Basis 2D texture")
    require(width > 0 and height > 0, "Invalid KTX2 dimensions")
    require(levels == int(math.log2(max(width, height))) + 1, "Incomplete mip chain")
    require(compression == 2, "Expected Zstd supercompression")
    require(80 + levels * 24 <= len(blob), "Truncated KTX2 level index")
    payload = 0
    for level in range(levels):
        offset, length, uncompressed = struct.unpack_from("<QQQ", blob, 80 + level * 24)
        require(offset + length <= len(blob), "KTX2 level exceeds file")
        expected = math.ceil(max(1, width >> level) / 4) * math.ceil(max(1, height >> level) / 4) * 16
        require(uncompressed == expected, "Expected 4x4 UASTC block size")
        payload += uncompressed
    rgba = sum(max(1, width >> level) * max(1, height >> level) * 4 for level in range(levels))
    return {"resolution": [width, height], "mipLevels": levels,
            "uastcAstcBc7MipBytes": payload, "rgba8MipBytes": rgba}


def compress_png(row, previous, threads):
    atlas = row["atlas"]
    source = TEXTURES / f"day-{atlas}.png"
    output = source.with_suffix(".ktx2")
    source_hash = sha(row["png"])
    atomic_bytes(source, row["png"])
    started = time.monotonic()
    reused = bool(previous and previous.get("sourceSha256") == source_hash
                  and previous.get("encoding") == ENCODING and output.is_file()
                  and previous.get("sha256") == sha(output.read_bytes()))
    pending = output.with_name(output.stem + ".pending.ktx2")
    if not reused:
        command = [str(ENCODER), "--encode", "uastc", "--uastc_quality", "2", "--zcmp", "9",
                   "--genmipmap", "--threads", str(threads), "--assign_oetf", "srgb", str(pending), str(source)]
        print(f"Encoding day-{atlas}: {row['resolution']}", flush=True)
        subprocess.run(command, check=True)
    candidate = output if reused else pending
    subprocess.run([str(VALIDATOR), "validate", str(candidate)], check=True)
    blob = candidate.read_bytes()
    info = ktx_info(blob)
    require(info["resolution"] == row["resolution"], "Encoder changed atlas dimensions")
    require(sha(source.read_bytes()) == source_hash, "Extracted PNG changed during compression")
    if not reused:
        pending.replace(output)
    record = {"state": "day", "atlas": atlas, "encoding": ENCODING, "source": rel(source),
              "sourceSha256": source_hash, "sourceBytes": len(row["png"]), "path": rel(output),
              "sha256": sha(blob), "bytes": len(blob), **info, "validated": True,
              "reused": reused, "seconds": round(time.monotonic() - started, 2)}
    print(f"Ready day-{atlas}: {len(row['png'])} -> {len(blob)} bytes", flush=True)
    return record, blob


def build_and_verify(original, chunks, binary, atlases, replacements):
    document = copy.deepcopy(original)
    for row in atlases.values():
        document["images"][row["image"]]["mimeType"] = "image/ktx2"
        texture = document["textures"][row["texture"]]
        texture.pop("source")
        texture.setdefault("extensions", {})["KHR_texture_basisu"] = {"source": row["image"]}
    for key in ("extensionsUsed", "extensionsRequired"):
        if "KHR_texture_basisu" not in document.setdefault(key, []):
            document[key].append("KHR_texture_basisu")
    rebuilt, unchanged_hashes = bytearray(), {}
    for index, view in enumerate(document["bufferViews"]):
        original_payload = view_bytes(original, binary, index)
        payload = replacements.get(index, original_payload)
        rebuilt.extend(b"\0" * (-len(rebuilt) % 4))
        view["byteOffset"], view["byteLength"] = len(rebuilt), len(payload)
        rebuilt.extend(payload)
        if index not in replacements:
            unchanged_hashes[str(index)] = sha(original_payload)
    document["buffers"][0]["byteLength"] = len(rebuilt)
    blob = pack_glb(document, chunks, bytes(rebuilt))
    verified, verified_chunks, verified_binary = parse_glb(blob)
    # Undo only the permitted serialization edits, then compare the entire JSON.
    normalized = copy.deepcopy(verified)
    for row in atlases.values():
        image = verified["images"][row["image"]]
        texture = verified["textures"][row["texture"]]
        require(image["mimeType"] == "image/ktx2" and "source" not in texture
                and texture["extensions"]["KHR_texture_basisu"] == {"source": row["image"]},
                "Invalid compressed texture binding")
        embedded = view_bytes(verified, verified_binary, row["bufferView"])
        require(embedded == replacements[row["bufferView"]], "Embedded KTX2 bytes differ from validated file")
        require(ktx_info(embedded)["resolution"] == row["resolution"], "Embedded atlas size changed")
        normalized["images"][row["image"]]["mimeType"] = original["images"][row["image"]]["mimeType"]
        restored = normalized["textures"][row["texture"]]
        restored["source"] = original["textures"][row["texture"]]["source"]
        del restored["extensions"]["KHR_texture_basisu"]
        if "extensions" not in original["textures"][row["texture"]]:
            require(not restored["extensions"], "Unexpected texture extensions")
            del restored["extensions"]
    for key in ("extensionsUsed", "extensionsRequired"):
        expected = list(original.get(key, []))
        if "KHR_texture_basisu" not in expected:
            expected.append("KHR_texture_basisu")
        require(verified[key] == expected, f"Unexpected {key} edit")
        if key in original:
            normalized[key] = copy.deepcopy(original[key])
        else:
            del normalized[key]
    require(len(normalized["bufferViews"]) == len(original["bufferViews"]), "BufferView count changed")
    for index, view in enumerate(normalized["bufferViews"]):
        old = original["bufferViews"][index]
        if "byteOffset" in old:
            view["byteOffset"] = old["byteOffset"]
        else:
            del view["byteOffset"]
        if index in replacements:
            view["byteLength"] = old["byteLength"]
        else:
            require(view["byteLength"] == old["byteLength"], "Non-atlas view length changed")
            require(sha(view_bytes(verified, verified_binary, index)) == unchanged_hashes[str(index)],
                    f"Non-atlas binary bufferView changed: {index}")
    normalized["buffers"][0]["byteLength"] = original["buffers"][0]["byteLength"]
    require(normalized == original, "JSON changed outside permitted atlas/buffer edits")
    require(verified.get("materials") == original.get("materials"), "Material definitions changed")
    require(asset_ids(verified) == asset_ids(original), "Asset IDs changed")
    require([(kind, data) for kind, data in chunks if kind not in (JSON_CHUNK, BIN_CHUNK)]
            == [(kind, data) for kind, data in verified_chunks if kind not in (JSON_CHUNK, BIN_CHUNK)],
            "Unknown GLB chunks changed")
    return blob, verified, unchanged_hashes


def load_source(wait, timeout, poll):
    started, announced = time.monotonic(), None
    while True:
        try:
            blob = MODEL.read_bytes()
            document, chunks, binary = parse_glb(blob)
            ids = asset_ids(document)
            atlases = atlas_inventory(document, binary)
            audit = json.loads(AUDIT.read_text())
            require(ids == sorted(audit["assetIds"]), "GLB asset IDs differ from the 128 approved source IDs")
            return blob, document, chunks, binary, atlases
        except (OSError, ValueError, RuntimeError, KeyError, IndexError, struct.error) as error:
            if not wait:
                raise
            message = f"Waiting for complete atelier GLB: {error}"
            if message != announced:
                print(message, flush=True)
                announced = message
            require(time.monotonic() - started < timeout, f"Timed out: {message}")
            time.sleep(poll)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", action="store_true", help="Wait for the final, complete GLB export")
    parser.add_argument("--timeout", type=float, default=3600, help="Maximum source wait in seconds")
    parser.add_argument("--poll", type=float, default=5, help="Source readiness poll interval in seconds")
    parser.add_argument("--threads", type=int, default=2, help="Threads used by the KTX encoder")
    args = parser.parse_args()
    require(args.threads > 0 and args.timeout > 0 and 0 < args.poll <= 60, "Invalid command options")
    require(ENCODER.is_file() and VALIDATOR.is_file(), "Official KTX tools are not installed locally")
    started = time.monotonic()
    source, original, chunks, binary, atlases = load_source(args.wait, args.timeout, args.poll)
    try:
        previous = json.loads(REPORT.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}
    previous_records = {record["atlas"]: record for record in previous.get("textures", [])}
    records, replacements = [], {}
    for atlas in range(4):
        record, encoded = compress_png(atlases[atlas], previous_records.get(atlas), args.threads)
        records.append(record)
        replacements[atlases[atlas]["bufferView"]] = encoded
    output, document, unchanged_hashes = build_and_verify(original, chunks, binary, atlases, replacements)
    require(sha(MODEL.read_bytes()) == sha(source), "Source GLB changed during compression")
    atomic_bytes(OUTPUT, output)
    require(OUTPUT.read_bytes() == output, "Written GLB differs from verified bytes")
    triangles = sum(document["accessors"][primitive["indices"]]["count"] // 3
                    for mesh in document.get("meshes", []) for primitive in mesh["primitives"]
                    if primitive.get("mode", 4) == 4 and "indices" in primitive)
    model = {"source": rel(MODEL), "sourceBytes": len(source), "sourceSha256": sha(source),
             "path": rel(OUTPUT), "bytes": len(output), "sha256": sha(output),
             "nodes": len(document.get("nodes", [])), "meshes": len(document.get("meshes", [])),
             "materials": len(document.get("materials", [])), "triangles": triangles,
             "assetCount": 128, "assetIds": asset_ids(document),
             "replacedImageBufferViews": sorted(replacements),
             "preservedNonAtlasBufferViews": len(unchanged_hashes),
             "preservedNonAtlasBufferViewSha256": unchanged_hashes,
             "geometryAndHierarchyUnchanged": True, "allMaterialsUnchanged": True,
             "allNonTextureJsonUnchanged": True, "otherImagesAndTexturesUnchanged": True,
             "assetIdsMatchSourceAudit": True, "assetIdsUnchanged": True,
             "sourceGlbUnchanged": True, "requiredExtension": "KHR_texture_basisu"}
    report = {"complete": True, "encoding": ENCODING, "model": model, "textures": records,
              "textureTransferBytes": sum(record["bytes"] for record in records),
              "sourcePngBytes": sum(record["sourceBytes"] for record in records),
              "estimatedRgba8MipBytes": sum(record["rgba8MipBytes"] for record in records),
              "estimatedAstcOrBc7MipBytes": sum(record["uastcAstcBc7MipBytes"] for record in records),
              "memoryEstimateNote": "Block payload only; GPU target must be ASTC 4x4 or BC7. RGBA fallback does not save GPU memory.",
              "ktxValidatePassed": True, "elapsedSeconds": round(time.monotonic() - started, 2)}
    atomic_json(REPORT, report)
    print(json.dumps({"complete": True, "model": rel(OUTPUT), "sourceBytes": len(source),
                      "bytes": len(output), "assetCount": 128, "report": rel(REPORT)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
