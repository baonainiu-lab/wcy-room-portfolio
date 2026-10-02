#!/usr/bin/env python3
"""Create optional KTX2 variants without changing the Blender export or PNG sources."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TEXTURES = ROOT / "public/textures/works-gallery-v5"
MODEL = ROOT / "public/models/works-gallery-v5.glb"
OUTPUT = ROOT / "public/models/works-gallery-v5-compressed.glb"
REPORT = ROOT / "assets/blender/works-gallery-v5/compression-report.json"
MANIFEST = TEXTURES / "compression-manifest.json"
TOOL = ROOT / "tools/ktx-software/bin/toktx"
VALIDATOR = ROOT / "tools/ktx-software/bin/ktx"
JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942
KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ktx_info(blob):
    require(blob[:12] == KTX2_MAGIC and len(blob) >= 80, "Invalid KTX2 header")
    fields = struct.unpack_from("<9I", blob, 12)
    vk, _, width, height, depth, layers, faces, levels, compression = fields
    require(vk == 0 and depth == 0 and layers == 0 and faces == 1, "Expected Basis 2D texture")
    require(levels == int(math.log2(max(width, height))) + 1, "Incomplete mip chain")
    require(compression == 2, "Expected Zstd supercompression")
    payload = 0
    for level in range(levels):
        offset, length, uncompressed = struct.unpack_from("<QQQ", blob, 80 + level * 24)
        require(offset + length <= len(blob), "KTX2 level exceeds file")
        expected = max(1, math.ceil(max(1, width >> level) / 4)) * max(1, math.ceil(max(1, height >> level) / 4)) * 16
        require(uncompressed == expected, "Expected 4x4 UASTC block size")
        payload += uncompressed
    rgba = sum(max(1, width >> level) * max(1, height >> level) * 4 for level in range(levels))
    return {"resolution": [width, height], "mipLevels": levels,
            "uastcAstcBc7MipBytes": payload, "rgba8MipBytes": rgba}


def compress_png(state, record, preparation_id, previous, threads):
    atlas = record["atlas"]
    source = TEXTURES / f"{state}-{atlas}.png"
    output = source.with_suffix(".ktx2")
    require(source.is_file(), f"Manifest references missing PNG: {source}")
    source_bytes = source.read_bytes()
    require(sha(source_bytes) == record["sha256"], f"PNG hash differs from bake manifest: {source}")
    require(source_bytes[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG: {source}")
    require(list(struct.unpack_from(">II", source_bytes, 16)) == record["resolution"], "PNG size mismatch")
    if (previous and previous.get("sourceSha256") == record["sha256"]
            and previous.get("preparation_id") == preparation_id and output.is_file()
            and previous.get("sha256") == sha(output.read_bytes())):
        ktx_info(output.read_bytes())
        return previous
    pending = output.with_name(output.stem + ".pending.ktx2")
    started = time.monotonic()
    command = [str(TOOL), "--encode", "uastc", "--uastc_quality", "2", "--zcmp", "9",
               "--genmipmap", "--threads", str(threads), "--assign_oetf", "srgb",
               str(pending), str(source)]
    print(f"Encoding {state}-{atlas} {record['resolution']}", flush=True)
    subprocess.run(command, check=True)
    subprocess.run([str(VALIDATOR), "validate", str(pending)], check=True)
    blob = pending.read_bytes()
    info = ktx_info(blob)
    require(info["resolution"] == record["resolution"], "Encoder changed texture resolution")
    require(sha(source.read_bytes()) == record["sha256"], "Source PNG changed during compression")
    pending.replace(output)
    result = {"state": state, "atlas": atlas, "preparation_id": preparation_id,
              "source": rel(source), "sourceSha256": record["sha256"], "sourceBytes": len(source_bytes),
              "path": rel(output), "sha256": sha(blob), "bytes": len(blob), **info,
              "seconds": round(time.monotonic() - started, 2), "validated": True}
    print(f"Ready {state}-{atlas}: {len(source_bytes)} -> {len(blob)} bytes", flush=True)
    return result


def parse_glb(blob):
    require(len(blob) >= 20, "Truncated GLB")
    magic, version, total = struct.unpack_from("<III", blob)
    require(magic == 0x46546C67 and version == 2 and total == len(blob), "Invalid GLB header")
    chunks, offset = [], 12
    while offset < total:
        length, kind = struct.unpack_from("<II", blob, offset)
        require(length % 4 == 0 and offset + 8 + length <= total, "Invalid GLB chunk bounds")
        chunks.append((kind, blob[offset + 8:offset + 8 + length]))
        offset += 8 + length
    require([kind for kind, _ in chunks].count(JSON_CHUNK) == 1, "Expected one GLB JSON chunk")
    require([kind for kind, _ in chunks].count(BIN_CHUNK) == 1, "Expected one GLB BIN chunk")
    document = json.loads(next(data for kind, data in chunks if kind == JSON_CHUNK))
    return document, chunks


def pack_glb(document, chunks):
    body = bytearray()
    for kind, original in chunks:
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode() if kind == JSON_CHUNK else original
        payload += (b" " if kind == JSON_CHUNK else b"\x00") * (-len(payload) % 4)
        body.extend(struct.pack("<II", len(payload), kind) + payload)
    return struct.pack("<III", 0x46546C67, 2, len(body) + 12) + body


def view_bytes(document, binary, view):
    require(view.get("buffer", 0) == 0, "External buffer unsupported")
    start, length = view.get("byteOffset", 0), view["byteLength"]
    require(0 <= start <= start + length <= document["buffers"][0]["byteLength"], "Invalid bufferView bounds")
    return binary[start:start + length]


def compress_glb(records, preparation_id):
    source_blob = MODEL.read_bytes()
    original, chunks = parse_glb(source_blob)
    require(original.get("asset", {}).get("extras", {}).get("preparation_id") == preparation_id,
            "Source GLB preparation ID is stale")
    require(len(original.get("buffers", [])) == 1 and "uri" not in original["buffers"][0], "Expected single embedded buffer")
    document = copy.deepcopy(original)
    binary = next(data for kind, data in chunks if kind == BIN_CHUNK)
    replacements, image_indices, atlas_texture_indices = {}, set(), {}
    for material in document.get("materials", []):
        name = material.get("name", "")
        if not name.startswith("GALLERY_LIGHTMAP_"):
            continue
        atlas = int(name.rsplit("_", 1)[1])
        require(atlas in range(4) and atlas not in atlas_texture_indices, "Duplicate or unexpected lightmap material")
        texture_index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
        texture = document["textures"][texture_index]
        image_index = texture["source"]
        require(image_index not in image_indices, "Atlas images unexpectedly share an image index")
        image_indices.add(image_index)
        image = document["images"][image_index]
        require(image.get("mimeType") == "image/png" and "uri" not in image, "Expected embedded PNG")
        view_index = image["bufferView"]
        record = records[f"night-{atlas}"]
        require(sha(view_bytes(original, binary, original["bufferViews"][view_index])) == record["sourceSha256"],
                f"Source GLB night atlas {atlas} differs from manifest")
        blob = (ROOT / record["path"]).read_bytes()
        require(sha(blob) == record["sha256"], "Compressed atlas changed")
        require(view_index not in replacements, "Shared image bufferView")
        replacements[view_index] = blob
        image["mimeType"] = "image/ktx2"
        image.setdefault("extras", {}).update(sha256=sha(blob), source_png_sha256=record["sourceSha256"])
        texture.pop("source")
        texture.setdefault("extensions", {})["KHR_texture_basisu"] = {"source": image_index}
        atlas_texture_indices[atlas] = texture_index
    require(set(atlas_texture_indices) == set(range(4)), "Expected all four lightmap materials")
    require(len(document["images"]) == 4, "Unexpected additional embedded images")
    for key in ("extensionsUsed", "extensionsRequired"):
        document.setdefault(key, [])
        if "KHR_texture_basisu" not in document[key]:
            document[key].append("KHR_texture_basisu")
    rebuilt = bytearray()
    unchanged_view_hashes = {}
    for index, view in enumerate(document["bufferViews"]):
        original_payload = view_bytes(original, binary, original["bufferViews"][index])
        payload = replacements.get(index, original_payload)
        rebuilt.extend(b"\x00" * (-len(rebuilt) % 4))
        view["byteOffset"], view["byteLength"] = len(rebuilt), len(payload)
        rebuilt.extend(payload)
        if index not in replacements:
            unchanged_view_hashes[str(index)] = sha(original_payload)
    document["buffers"][0]["byteLength"] = len(rebuilt)
    compressed_chunks = [(kind, bytes(rebuilt) if kind == BIN_CHUNK else data) for kind, data in chunks]
    output_blob = pack_glb(document, compressed_chunks)
    verified, verified_chunks = parse_glb(output_blob)
    verified_binary = next(data for kind, data in verified_chunks if kind == BIN_CHUNK)
    for key in set(original) - {"images", "textures", "bufferViews", "buffers", "extensionsUsed", "extensionsRequired"}:
        require(verified.get(key) == original[key], f"Non-texture JSON changed: {key}")
    for index, expected in unchanged_view_hashes.items():
        require(sha(view_bytes(verified, verified_binary, verified["bufferViews"][int(index)])) == expected,
                f"Non-image binary bufferView changed: {index}")
    for atlas, texture_index in atlas_texture_indices.items():
        texture = verified["textures"][texture_index]
        image_index = texture["extensions"]["KHR_texture_basisu"]["source"]
        image = verified["images"][image_index]
        require("source" not in texture and image["mimeType"] == "image/ktx2", "Invalid KHR_texture_basisu binding")
        ktx_info(view_bytes(verified, verified_binary, verified["bufferViews"][image["bufferView"]]))
    require(sha(MODEL.read_bytes()) == sha(source_blob), "Source GLB changed during compression")
    pending = OUTPUT.with_name(OUTPUT.name + ".tmp")
    pending.write_bytes(output_blob)
    pending.replace(OUTPUT)
    triangles = sum(verified["accessors"][primitive["indices"]]["count"] // 3
                    for mesh in verified.get("meshes", []) for primitive in mesh["primitives"]
                    if primitive.get("mode", 4) == 4 and "indices" in primitive)
    return {"source": rel(MODEL), "sourceBytes": len(source_blob), "sourceSha256": sha(source_blob),
            "path": rel(OUTPUT), "bytes": len(output_blob), "sha256": sha(output_blob),
            "nodes": len(verified.get("nodes", [])), "meshes": len(verified.get("meshes", [])),
            "materials": len(verified.get("materials", [])), "triangles": triangles,
            "replacedImageBufferViews": sorted(replacements),
            "preservedNonImageBufferViews": len(unchanged_view_hashes),
            "geometryAndHierarchyUnchanged": True, "otherTopLevelJsonUnchanged": True,
            "sourceGlbUnchanged": True, "requiredExtension": "KHR_texture_basisu"}


def decoder_files():
    source = ROOT / "node_modules/three/examples/jsm/libs/basis"
    target = ROOT / "public/basis"
    target.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ("basis_transcoder.js", "basis_transcoder.wasm", "README.md"):
        shutil.copy2(source / name, target / name)
        files.append({"path": rel(target / name), "sha256": sha((target / name).read_bytes())})
    shutil.copy2(ROOT / "node_modules/three/LICENSE", target / "THREE-LICENSE.txt")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", action="store_true", help="Wait for atomic bake manifests and final GLB")
    parser.add_argument("--timeout", type=float, default=2400)
    parser.add_argument("--poll", type=float, default=5)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    require(args.threads > 0 and args.timeout > 0 and args.poll > 0, "Invalid command options")
    require(TOOL.is_file() and VALIDATOR.is_file(), "Official KTX tools are not installed locally")
    started = time.monotonic()
    previous = read_json(MANIFEST)
    records = {f"{r['state']}-{r['atlas']}": r for r in previous.get("textures", [])}
    decoders = decoder_files()
    announced = None
    while True:
        manifests = {state: read_json(TEXTURES / f"{state}-manifest.json") for state in ("day", "night")}
        expected_id = read_json(ROOT / "assets/blender/works-gallery-v5/preparation-report.json").get("preparation_id")
        for state, manifest in list(manifests.items()):
            if manifest and manifest.get("preparation_id") != expected_id:
                require(args.wait, "Bake manifest does not match current prepared geometry")
                manifests[state] = {}
        ids = {m.get("preparation_id") for m in manifests.values() if m}
        require(len(ids) <= 1, "Day/night bake preparation IDs differ")
        preparation_id = next(iter(ids), None)
        valid_records = {}
        for state, manifest in manifests.items():
            if not manifest:
                continue
            require(manifest.get("state") == state and preparation_id, "Invalid bake manifest")
            for record in manifest.get("atlases", []):
                require(record.get("atlas") in range(4), "Unexpected atlas ID")
                key = f"{state}-{record['atlas']}"
                valid_records[key] = compress_png(state, record, preparation_id, records.get(key), args.threads)
                records[key] = valid_records[key]
                snapshot = {"complete": False, "preparation_id": preparation_id,
                            "encoding": "UASTC quality 2 + Zstd 9", "textures": list(records.values()),
                            "decoderFiles": decoders}
                atomic_json(MANIFEST, snapshot)
        complete = len(valid_records) == 8 and all(m.get("complete") for m in manifests.values())
        if complete and MODEL.is_file():
            try:
                source_doc, _ = parse_glb(MODEL.read_bytes())
                model_ready = source_doc.get("asset", {}).get("extras", {}).get("preparation_id") == preparation_id
            except (ValueError, RuntimeError, struct.error):
                model_ready = False
            if model_ready:
                model = compress_glb(valid_records, preparation_id)
                report = {"complete": True, "preparation_id": preparation_id,
                          "encoding": "UASTC quality 2 + Zstd 9", "model": model,
                          "textures": list(valid_records.values()), "decoderFiles": decoders,
                          "textureTransferBytes": sum(r["bytes"] for r in valid_records.values()),
                          "sourcePngBytes": sum(r["sourceBytes"] for r in valid_records.values()),
                          "estimatedRgba8MipBytesBothStates": sum(r["rgba8MipBytes"] for r in valid_records.values()),
                          "estimatedAstcOrBc7MipBytesBothStates": sum(r["uastcAstcBc7MipBytes"] for r in valid_records.values()),
                          "memoryEstimateNote": "Block payload estimate only; browser target format must be ASTC 4x4 or BC7. RGBA fallback does not save GPU texture memory.",
                          "elapsedSeconds": round(time.monotonic() - started, 2)}
                atomic_json(MANIFEST, report)
                atomic_json(REPORT, report)
                print(json.dumps({"complete": True, "model": model, "report": rel(REPORT)}, ensure_ascii=False), flush=True)
                return
        waiting = f"Waiting: {len(valid_records)}/8 textures validated; final GLB ready={complete and MODEL.is_file()}"
        if waiting != announced:
            print(waiting, flush=True)
            announced = waiting
        if not args.wait:
            raise RuntimeError("Bake/export pipeline incomplete; rerun with --wait")
        require(time.monotonic() - started < args.timeout, "Timed out waiting for bake/export pipeline")
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
