#!/usr/bin/env python3
"""Replace the architecture GLB's single 4K PNG atlas with validated UASTC KTX2.

Usage: python3 scripts/compress-about-atelier-v3-architecture.py [--threads 2]
Run only after Blender has finished exporting the PNG-backed architecture GLB.
The verified GLB replaces its source atomically. Encoding uses a temporary PNG,
so extracting the embedded source does not create a large public PNG asset.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "scripts/compress-about-atelier-v3.py"
_spec = importlib.util.spec_from_file_location("atelier_compression_helpers", HELPERS)
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
parse_glb = _helpers.parse_glb
pack_glb = _helpers.pack_glb
ktx_info = _helpers.ktx_info
require = _helpers.require
sha = _helpers.sha
view_bytes = _helpers.view_bytes
atomic_bytes = _helpers.atomic_bytes
atomic_json = _helpers.atomic_json
rel = _helpers.rel

MODEL = ROOT / "public/models/about-atelier-v3-architecture.glb"
TEXTURE = ROOT / "public/textures/about-atelier-v3/architecture/day.ktx2"
SOURCE_PNG = TEXTURE.with_suffix(".png")
REPORT = ROOT / "assets/blender/about-atelier-v3-web/architecture-compression-report.json"
ENCODER = _helpers.ENCODER
VALIDATOR = _helpers.VALIDATOR
ENCODING = 'UASTC quality 2, RDO lambda 3 + Zstd 9; sRGB; complete mip chain'
LIGHTMAP = "ATELIER_ARCH_LIGHTMAP"
GLASS = "ATELIER_ARCH_GLASS"
GEOMETRY_KEYS = ("nodes", "meshes", "accessors", "scenes", "scene", "skins", "animations", "cameras")


def json_sha(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def geometry_json(document):
    return {key: document[key] for key in GEOMETRY_KEYS if key in document}


def assert_no_asset_ids(value, path="$"):
    if isinstance(value, dict):
        require("asset_id" not in value, f"Architecture must not contain asset_id: {path}")
        for key, child in value.items():
            assert_no_asset_ids(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_asset_ids(child, f"{path}[{index}]")


def inspect_architecture(document):
    assert_no_asset_ids(document)
    materials = document.get("materials", [])
    names = [material.get("name") for material in materials]
    require(len(names) == 2 and set(names) == {LIGHTMAP, GLASS},
            f"Expected only {LIGHTMAP} and {GLASS}, found {names}")
    opaque_index, glass_index = names.index(LIGHTMAP), names.index(GLASS)
    require(materials[opaque_index].get("alphaMode", "OPAQUE") == "OPAQUE", "Lightmap must be opaque")
    meshes = document.get("meshes", [])
    counts = {"opaque": 0, "glass": 0}
    for index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives", [])
        require(primitives, f"Empty architecture mesh: {index}")
        bindings = {primitive.get("material") for primitive in primitives}
        require(bindings in ({opaque_index}, {glass_index}),
                f"Architecture mesh {index} mixes or omits materials")
        counts["opaque" if bindings == {opaque_index} else "glass"] += 1
    require(counts == {"opaque": 1, "glass": 8}, f"Expected 1 opaque + 8 glass meshes, found {counts}")
    mesh_nodes = [node["mesh"] for node in document.get("nodes", []) if "mesh" in node]
    require(sorted(mesh_nodes) == list(range(9)), "Expected each architecture mesh on exactly one node")
    require(len(document.get("textures", [])) == len(document.get("images", [])) == 1,
            "Architecture must contain exactly one image and texture")
    material = materials[opaque_index]
    texture_index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    require(texture_index == 0, "Unexpected lightmap texture index")
    require(set(_helpers.material_texture_indices(material)) == {texture_index},
            "Unexpected lightmap material texture binding")
    require(not list(_helpers.material_texture_indices(materials[glass_index])),
            "Glass must not share the lightmap texture")
    return {"opaqueMaterial": opaque_index, "glassMaterial": glass_index,
            "opaqueMeshes": counts["opaque"], "glassMeshes": counts["glass"]}


def source_atlas(document, binary):
    inventory = inspect_architecture(document)
    texture = document["textures"][0]
    require("KHR_texture_basisu" not in texture.get("extensions", {}),
            "Architecture GLB is already compressed; export the PNG source again before recompressing")
    require(texture.get("source") == 0, "Expected the single source image")
    image = document["images"][0]
    require(image.get("mimeType") == "image/png" and "uri" not in image,
            "Expected one embedded PNG lightmap")
    view_index = image["bufferView"]
    png = view_bytes(document, binary, view_index)
    require(len(png) >= 33 and png[:8] == b"\x89PNG\r\n\x1a\n" and png[12:16] == b"IHDR",
            "Invalid lightmap PNG")
    resolution = list(struct.unpack_from(">II", png, 16))
    require(resolution == [4096, 4096], f"Expected 4096 x 4096 lightmap, found {resolution}")
    for accessor in document.get("accessors", []):
        referenced = [accessor.get("bufferView")]
        referenced += [part.get("bufferView") for part in accessor.get("sparse", {}).values()
                       if isinstance(part, dict)]
        require(view_index not in referenced, "Texture bufferView is shared by geometry")
    target = document["bufferViews"][view_index]
    start, end = target.get("byteOffset", 0), target.get("byteOffset", 0) + target["byteLength"]
    for index, view in enumerate(document["bufferViews"]):
        view_bytes(document, binary, index)
        other_start = view.get("byteOffset", 0)
        other_end = other_start + view["byteLength"]
        require(index == view_index or other_end <= start or other_start >= end,
                f"Texture byte range overlaps another bufferView: {index}")
    return {"bufferView": view_index, "png": png, "resolution": resolution, **inventory}


def encode_atlas(row, threads):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="atelier-architecture-ktx-") as directory:
        source = Path(directory) / "day.png"
        pending = Path(directory) / "day.ktx2"
        source.write_bytes(row["png"])
        subprocess.run([str(ENCODER), "--encode", "uastc", "--uastc_quality", "2",
                        "--uastc_rdo_l", "3",
                        "--zcmp", "9", "--genmipmap", "--threads", str(threads),
                        "--assign_oetf", "srgb", str(pending), str(source)], check=True)
        subprocess.run([str(VALIDATOR), "validate", str(pending)], check=True)
        encoded = pending.read_bytes()
        info = ktx_info(encoded)
        require(info["resolution"] == row["resolution"], "Encoder changed atlas dimensions")
        require(source.read_bytes() == row["png"], "Encoding source changed")
    return encoded, {"state": "day", "encoding": ENCODING,
                     "source": rel(SOURCE_PNG), "embeddedSource": f"{rel(MODEL)}#images/0",
                     "sourceSha256": sha(row["png"]), "sourceBytes": len(row["png"]),
                     "path": rel(TEXTURE), "sha256": sha(encoded), "bytes": len(encoded),
                     **info, "validated": True, "sourcePngMatchesEmbeddedImage": True,
                     "seconds": round(time.monotonic() - started, 2)}


def build_and_verify(original, chunks, binary, row, encoded):
    document = copy.deepcopy(original)
    index = row["bufferView"]
    old_view = original["bufferViews"][index]
    start = old_view.get("byteOffset", 0)
    end = start + old_view["byteLength"]
    source_binary = binary[:original["buffers"][0]["byteLength"]]
    # Keep every original non-texture byte, including unreferenced data and gaps.
    # The inserted padding makes the offset delta a multiple of four.
    inserted = encoded + b"\0" * ((old_view["byteLength"] - len(encoded)) % 4)
    delta = len(inserted) - old_view["byteLength"]
    rebuilt = source_binary[:start] + inserted + source_binary[end:]
    for other_index, view in enumerate(document["bufferViews"]):
        if other_index == index:
            view["byteLength"] = len(encoded)
        elif view.get("byteOffset", 0) >= end:
            view["byteOffset"] = view.get("byteOffset", 0) + delta
    document["buffers"][0]["byteLength"] = len(rebuilt)
    document["images"][0]["mimeType"] = "image/ktx2"
    texture = document["textures"][0]
    texture.pop("source")
    texture.setdefault("extensions", {})["KHR_texture_basisu"] = {"source": 0}
    for key in ("extensionsUsed", "extensionsRequired"):
        if "KHR_texture_basisu" not in document.setdefault(key, []):
            document[key].append("KHR_texture_basisu")
    output = pack_glb(document, chunks, rebuilt)
    verified, verified_chunks, verified_binary = parse_glb(output)
    require(verified == document, "Packed GLB JSON differs from candidate")
    require(verified_binary[:len(rebuilt)] == rebuilt, "Packed GLB binary differs from candidate")
    require(verified_binary[:start] == source_binary[:start]
            and verified_binary[start + len(inserted):len(rebuilt)] == source_binary[end:],
            "Binary bytes outside the texture replacement changed")
    require(view_bytes(verified, verified_binary, index) == encoded, "Embedded KTX2 payload differs")
    require(ktx_info(view_bytes(verified, verified_binary, index))["resolution"] == [4096, 4096],
            "Embedded KTX2 resolution changed")
    require(inspect_architecture(verified) == inspect_architecture(original), "Architecture inventory changed")

    normalized = copy.deepcopy(verified)
    normalized["images"][0]["mimeType"] = original["images"][0]["mimeType"]
    restored = normalized["textures"][0]
    require("source" not in restored and restored["extensions"]["KHR_texture_basisu"] == {"source": 0},
            "Invalid Basis texture binding")
    restored["source"] = original["textures"][0]["source"]
    del restored["extensions"]["KHR_texture_basisu"]
    if "extensions" not in original["textures"][0]:
        require(not restored["extensions"], "Unexpected texture extension")
        del restored["extensions"]
    for key in ("extensionsUsed", "extensionsRequired"):
        expected = list(original.get(key, []))
        if "KHR_texture_basisu" not in expected:
            expected.append("KHR_texture_basisu")
        require(verified[key] == expected, f"Unexpected {key} change")
        if key in original:
            normalized[key] = copy.deepcopy(original[key])
        else:
            del normalized[key]
    preserved = {}
    for other_index, view in enumerate(normalized["bufferViews"]):
        old = original["bufferViews"][other_index]
        if "byteOffset" in old:
            view["byteOffset"] = old["byteOffset"]
        else:
            view.pop("byteOffset", None)
        if other_index == index:
            view["byteLength"] = old["byteLength"]
        else:
            before = view_bytes(original, binary, other_index)
            after = view_bytes(verified, verified_binary, other_index)
            require(before == after, f"Non-texture bufferView changed: {other_index}")
            preserved[str(other_index)] = sha(before)
    normalized["buffers"][0]["byteLength"] = original["buffers"][0]["byteLength"]
    require(normalized == original, "JSON changed outside permitted texture/buffer edits")
    require(geometry_json(verified) == geometry_json(original), "Geometry or hierarchy JSON changed")
    require(verified["materials"] == original["materials"], "Material JSON changed")
    known = {_helpers.JSON_CHUNK, _helpers.BIN_CHUNK}
    require([(kind, data) for kind, data in chunks if kind not in known]
            == [(kind, data) for kind, data in verified_chunks if kind not in known],
            "Unknown GLB chunks changed")
    evidence = {"sourceJsonSha256": json_sha(original), "normalizedOutputJsonSha256": json_sha(normalized),
                "sourceGeometryJsonSha256": json_sha(geometry_json(original)),
                "outputGeometryJsonSha256": json_sha(geometry_json(verified)),
                "sourceMaterialsJsonSha256": json_sha(original["materials"]),
                "outputMaterialsJsonSha256": json_sha(verified["materials"]),
                "preservedNonTextureBufferViewSha256": preserved,
                "preservedNonTextureBufferViews": len(preserved),
                "allNonTextureBinaryBytesUnchanged": True,
                "allNonTextureJsonUnchanged": True, "allMaterialsUnchanged": True,
                "geometryAndHierarchyUnchanged": True, "assetIdsAbsent": True}
    return output, verified, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, default=2, help="Threads used by the KTX encoder")
    args = parser.parse_args()
    require(args.threads > 0, "--threads must be positive")
    require(ENCODER.is_file() and VALIDATOR.is_file(), "Official KTX tools are not installed locally")
    started = time.monotonic()
    source = MODEL.read_bytes()
    original, chunks, binary = parse_glb(source)
    row = source_atlas(original, binary)
    require(SOURCE_PNG.read_bytes() == row["png"], "Public day.png differs from the GLB's embedded PNG")
    print("Encoding architecture lightmap: 4096 x 4096", flush=True)
    encoded, texture_record = encode_atlas(row, args.threads)
    output, document, evidence = build_and_verify(original, chunks, binary, row, encoded)
    require(MODEL.read_bytes() == source, "Source GLB changed during compression")
    require(SOURCE_PNG.read_bytes() == row["png"], "Public day.png changed during compression")
    atomic_bytes(TEXTURE, encoded)
    require(TEXTURE.read_bytes() == encoded, "Written external KTX2 differs from validated bytes")
    require(MODEL.read_bytes() == source, "Source GLB changed before replacement")
    atomic_bytes(MODEL, output)
    require(MODEL.read_bytes() == output, "Written GLB differs from verified bytes")
    triangles = sum(document["accessors"][primitive["indices"]]["count"] // 3
                    for mesh in document["meshes"] for primitive in mesh["primitives"]
                    if primitive.get("mode", 4) == 4 and "indices" in primitive)
    report = {"complete": True, "encoding": ENCODING,
              "model": {"source": rel(MODEL), "sourceBytes": len(source), "sourceSha256": sha(source),
                        "path": rel(MODEL), "bytes": len(output), "sha256": sha(output),
                        "sourceReplacedInPlace": True, "nodes": len(document.get("nodes", [])),
                        "meshes": len(document["meshes"]), "opaqueMeshes": 1, "glassMeshes": 8,
                        "materials": 2, "materialNames": [material["name"] for material in document["materials"]],
                        "triangles": triangles, "assetCount": 0, "assetIds": [],
                        "replacedImageBufferViews": [row["bufferView"]],
                        "requiredExtension": "KHR_texture_basisu", **evidence},
              "textures": [texture_record], "textureTransferBytes": len(encoded),
              "sourcePngBytes": len(row["png"]),
              "estimatedRgba8MipBytes": texture_record["rgba8MipBytes"],
              "estimatedAstcOrBc7MipBytes": texture_record["uastcAstcBc7MipBytes"],
              "memoryEstimateNote": "Block payload only; GPU target must be ASTC 4x4 or BC7. RGBA fallback does not save GPU memory.",
              "ktxValidatePassed": True, "elapsedSeconds": round(time.monotonic() - started, 2)}
    atomic_json(REPORT, report)
    print(json.dumps({"complete": True, "model": rel(MODEL), "sourceBytes": len(source),
                      "bytes": len(output), "texture": rel(TEXTURE), "report": rel(REPORT)},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
