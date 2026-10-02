"""Export the prepared gallery without changing its editable/bake scene.

Run with Blender's Python (no .blend file is ever saved by this script)::

    blender --background --python export_gallery.py -- \
        --prepared assets/blender/works-gallery-bake-v3.blend

The public API is ``export(prepared_path=None, output_path=None,
textures_directory=None, report_path=None)``.  A loaded WEB_WORKS_GALLERY_V3
scene takes precedence over the prepared file.  Both bake manifests are required
so that old, merely same-sized atlases cannot silently accompany new geometry.
Pure PNG/GLB validation helpers can also be imported outside Blender.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[4]
SCENE_NAME = "WEB_WORKS_GALLERY_V3"
PREPARED = ROOT / "assets/blender/works-gallery-bake-v3.blend"
OUTPUT = ROOT / "public/models/works-gallery-v3.glb"
TEXTURES = ROOT / "public/textures/works-gallery-v3"
REPORT = ROOT / "assets/blender/works-gallery-v3/export-report.json"
ATLAS_SIZES = (4096, 4096, 4096, 1024)
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SOURCE_KEY = "export_source_object"


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _path_label(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _png_info(data, label="PNG"):
    """Check signature, IHDR, chunk bounds/CRCs and IEND, without Pillow."""
    _require(data.startswith(PNG_SIGNATURE), f"{label}: invalid PNG signature")
    offset, dimensions, seen_idat, ended = 8, None, False, False
    while offset < len(data):
        _require(offset + 12 <= len(data), f"{label}: truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        _require(end <= len(data), f"{label}: PNG chunk exceeds file bounds")
        payload = memoryview(data)[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        actual_crc = zlib.crc32(payload, zlib.crc32(kind)) & 0xFFFFFFFF
        _require(actual_crc == expected_crc, f"{label}: bad {kind!r} chunk CRC")
        if dimensions is None:
            _require(kind == b"IHDR" and length == 13, f"{label}: missing first IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            _require(width > 0 and height > 0, f"{label}: invalid dimensions")
            valid_depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8),
                            4: (8, 16), 6: (8, 16)}
            _require(depth in valid_depths.get(color, ()), f"{label}: invalid color/depth")
            _require(compression == 0 and filtering == 0 and interlace in (0, 1),
                     f"{label}: unsupported PNG coding")
            dimensions = [width, height]
        elif kind == b"IHDR":
            raise RuntimeError(f"{label}: duplicate IHDR")
        if kind == b"IDAT":
            seen_idat = True
        if kind == b"IEND":
            _require(length == 0 and end == len(data), f"{label}: invalid PNG ending")
            ended = True
            break
        offset = end
    _require(ended and seen_idat, f"{label}: missing PNG image data or IEND")
    return {"dimensions": dimensions, "bytes": len(data), "sha256": _sha256(data)}


def _read_textures(directory):
    records, night_bytes = {"day": [], "night": []}, {}
    for state in ("day", "night"):
        for atlas, resolution in enumerate(ATLAS_SIZES):
            path = directory / f"{state}-{atlas}.png"
            _require(path.is_file(), f"Missing bake atlas: {path}")
            data = path.read_bytes()
            record = _png_info(data, str(path))
            _require(record["dimensions"] == [resolution, resolution],
                     f"{path}: expected {resolution} x {resolution}, got {record['dimensions']}")
            record.update(atlas=atlas, state=state, path=_path_label(path), resolution=resolution)
            records[state].append(record)
            if state == "night":
                night_bytes[atlas] = data
    return records, night_bytes


def _verify_manifests(directory, preparation_id, records):
    _require(isinstance(preparation_id, str) and len(preparation_id) == 64
             and all(c in "0123456789abcdef" for c in preparation_id.lower()),
             "Prepared scene is missing a valid SHA-256 preparation_id; prepare it first")
    manifests = {}
    for state in ("day", "night"):
        path = directory / f"{state}-manifest.json"
        _require(path.is_file(), f"Missing bake manifest: {path}; bake this state first")
        manifest_bytes = path.read_bytes()
        manifest = json.loads(manifest_bytes)
        _require(manifest.get("preparation_id") == preparation_id,
                 f"{path}: preparation_id differs from the loaded prepared scene; rebake")
        _require(manifest.get("state") == state, f"{path}: wrong lighting state")
        entries = manifest.get("atlases", [])
        _require(isinstance(entries, list) and len(entries) == 4,
                 f"{path}: expected four completed atlas records")
        by_atlas = {}
        for entry in entries:
            _require(isinstance(entry, dict), f"{path}: invalid atlas record")
            atlas = entry.get("atlas")
            _require(type(atlas) is int and atlas in range(4) and atlas not in by_atlas,
                     f"{path}: invalid or duplicate atlas index {atlas!r}")
            by_atlas[atlas] = entry
        for record in records[state]:
            atlas = record["atlas"]
            entry = by_atlas[atlas]
            _require(entry.get("sha256") == record["sha256"]
                     and entry.get("bytes") == record["bytes"],
                     f"{path}: {state}-{atlas}.png differs from its completed bake record")
            _require(entry.get("resolution") in (record["resolution"], record["dimensions"]),
                     f"{path}: wrong atlas {atlas} resolution")
            _require(Path(str(entry.get("path", ""))).name == f"{state}-{atlas}.png",
                     f"{path}: wrong atlas {atlas} path")
        manifests[state] = {"path": _path_label(path), "sha256": _sha256(manifest_bytes),
                            "preparation_id": preparation_id}
    return manifests


def _asset_id(obj):
    value = obj.get("asset_id")
    if value is not None:
        _require(isinstance(value, str) and bool(value.strip()),
                 f"{obj.name}: asset_id must be a nonempty string")
    return value


def _nearest_asset(obj, include_self=False):
    current = obj if include_self else obj.parent
    seen = set()
    while current is not None:
        _require(current not in seen, f"Parent cycle at {obj.name}")
        seen.add(current)
        identity = _asset_id(current)
        if identity:
            return identity
        current = current.parent
    return None


def _source_inventory(scene):
    all_objects = set(scene.objects)
    assets = {}
    for obj in scene.objects:
        # Lighting-only context can retain source IDs, but is not part of the
        # prepared export contract (export_exclude is inherited in preparation).
        if not obj.get("web_export"):
            continue
        identity = _asset_id(obj)
        if identity:
            _require(identity not in assets, f"Duplicate source asset_id: {identity}")
            _require(obj.type in {"EMPTY", "MESH"}, f"Asset {identity} is not an EMPTY or MESH")
            assets[identity] = obj
    _require(bool(assets), "Prepared scene has no stable asset IDs")
    selected = {obj for obj in scene.objects if obj.get("web_export")}
    for obj in tuple(selected):
        current, seen = obj.parent, {obj}
        while current is not None:
            _require(current not in seen, f"Parent cycle at {obj.name}")
            _require(current in all_objects, f"{obj.name}: parent is outside prepared scene")
            selected.add(current)
            seen.add(current)
            current = current.parent
    atlas_meshes = {atlas: 0 for atlas in range(4)}
    glass_meshes = 0
    for obj in selected:
        _require(not obj.get("export_exclude") and not obj.get("web_context"),
                 f"{obj.name}: excluded context entered the export ancestry; prepare again")
        _require(obj.type in {"EMPTY", "MESH"}, f"Unsupported export object: {obj.name} ({obj.type})")
        _require(obj.parent_type == "OBJECT", f"{obj.name}: non-object parenting is unsupported")
        if obj.type != "MESH":
            continue
        owner = _nearest_asset(obj, include_self=True)
        _require(owner in assets, f"{obj.name}: no stable owning asset")
        _require(obj.get("owner_asset_id") == owner,
                 f"{obj.name}: owner_asset_id must identify nearest asset {owner}")
        kind, atlas = obj.get("web_kind"), obj.get("bake_atlas")
        geometry_atlas = obj.get("geometry_atlas")
        _require(type(geometry_atlas) is int and geometry_atlas in range(4),
                 f"{obj.name}: invalid geometry_atlas {geometry_atlas!r}")
        if kind == "baked":
            _require(type(atlas) is int and atlas in range(4), f"{obj.name}: invalid bake_atlas")
            _require(atlas == geometry_atlas, f"{obj.name}: bake/geometry atlas mismatch")
            _require(obj.data.uv_layers.get("BakeUV") is not None, f"{obj.name}: BakeUV is missing")
            _require(len(obj.data.polygons) > 0, f"{obj.name}: baked mesh has no polygons")
            atlas_meshes[atlas] += 1
        elif kind == "glass":
            _require(atlas == -1, f"{obj.name}: glass must have bake_atlas = -1")
            glass_meshes += 1
        else:
            raise RuntimeError(f"{obj.name}: web_kind must be 'baked' or 'glass', got {kind!r}")
    _require(all(atlas_meshes.values()), f"All four baked atlas groups must contain meshes: {atlas_meshes}")
    objects = sorted(selected, key=lambda obj: obj.name)
    return objects, {
        "asset_ids": sorted(assets),
        "asset_hierarchy": {identity: _nearest_asset(assets[identity]) for identity in sorted(assets)},
        "object_hierarchy": {obj.name: obj.parent.name if obj.parent in selected else None for obj in objects},
        "object_owners": {obj.name: _nearest_asset(obj, include_self=True) for obj in objects},
        "atlas_meshes": atlas_meshes,
        "glass_meshes": glass_meshes,
    }


def _emission_material(bpy, name, image=None):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (1, 1, 1, 1)
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1, 1, 1, 1)
    emission.inputs["Strength"].default_value = 1
    tree.links.new(emission.outputs[0], output.inputs["Surface"])
    if image is not None:
        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        texture.interpolation = "Linear"
        uv = tree.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "BakeUV"
        tree.links.new(uv.outputs["UV"], texture.inputs["Vector"])
        tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
    return material


@contextmanager
def _export_scene(bpy, source, objects, textures):
    """Own every disposable datablock and clean it up even after failed export."""
    window = bpy.context.window
    old_scene = window.scene if window else None
    temporary = None
    created_objects, created_meshes, materials, images = [], [], [], []
    try:
        if window:
            window.scene = source
        with bpy.context.temp_override(scene=source, view_layer=source.view_layers[0]):
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = {obj: obj.evaluated_get(depsgraph) for obj in objects}
            world_matrices = {obj: evaluated[obj].matrix_world.copy() for obj in objects}
            temporary = bpy.data.scenes.new("__WORKS_GALLERY_EXPORT_TEMP")
            temporary["export_kind"] = "works_gallery_dual_lightmap_v3"
            temporary["preparation_id"] = source["preparation_id"]
            material_names, atlas_materials = {}, {}
            for atlas in range(4):
                image = bpy.data.images.load(str(textures / f"night-{atlas}.png"), check_existing=False)
                images.append(image)
                image.colorspace_settings.name = "sRGB"
                material = _emission_material(bpy, f"__GALLERY_EXPORT_LIGHTMAP_{atlas}", image)
                materials.append(material)
                atlas_materials[atlas] = material
                material_names[material.name] = f"GALLERY_LIGHTMAP_{atlas}"
            clear = _emission_material(bpy, "__GALLERY_EXPORT_CLEAR")
            materials.append(clear)
            material_names[clear.name] = "GALLERY_CLEAR"
            copies = {}
            for original in objects:
                copy = original.copy()
                created_objects.append(copy)
                copy.animation_data_clear()
                copy.constraints.clear()
                copy.parent = None
                copy.hide_viewport = False
                copy.hide_render = False
                copy.hide_select = False
                copy[SOURCE_KEY] = original.name
                copy["web_export"] = True
                owner = _nearest_asset(original, include_self=True)
                if owner:
                    copy["owner_asset_id"] = owner
                if original.type == "MESH":
                    mesh = bpy.data.meshes.new_from_object(
                        evaluated[original], preserve_all_data_layers=True, depsgraph=depsgraph
                    )
                    created_meshes.append(mesh)
                    copy.data = mesh
                    copy.modifiers.clear()
                    mesh.materials.clear()
                    if original["web_kind"] == "baked":
                        mesh.materials.append(atlas_materials[int(original["bake_atlas"])])
                        _require(mesh.uv_layers.get("BakeUV") is not None,
                                 f"{original.name}: evaluation discarded BakeUV")
                        for layer in list(mesh.uv_layers):
                            if layer.name != "BakeUV":
                                mesh.uv_layers.remove(layer)
                        mesh.uv_layers.active_index = 0
                        mesh.uv_layers[0].active_render = True
                    else:
                        mesh.materials.append(clear)
                    for slot in copy.material_slots:
                        slot.link = "DATA"
                    for polygon in mesh.polygons:
                        polygon.material_index = 0
                temporary.collection.objects.link(copy)
                copies[original] = copy
            for original, copy in copies.items():
                copy.parent = copies.get(original.parent)
                copy.matrix_parent_inverse.identity()
                # Resolve directly from evaluated source world matrices.  This
                # preserves nested pivots without depending on update order.
                if original.parent in copies:
                    copy.matrix_basis = (world_matrices[original.parent].inverted_safe()
                                         @ world_matrices[original])
                else:
                    copy.matrix_basis = world_matrices[original]
        if window:
            window.scene = temporary
        with bpy.context.temp_override(scene=temporary, view_layer=temporary.view_layers[0]):
            for copy in created_objects:
                copy.hide_set(False, view_layer=temporary.view_layers[0])
                copy.select_set(True, view_layer=temporary.view_layers[0])
            temporary.view_layers[0].objects.active = created_objects[0]
            temporary.view_layers[0].update()
            yield temporary, material_names
    finally:
        if window and old_scene is not None:
            window.scene = old_scene
        for obj in reversed(created_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        if temporary is not None:
            bpy.data.scenes.remove(temporary)
        for mesh in created_meshes:
            bpy.data.meshes.remove(mesh, do_unlink=True)
        for material in materials:
            bpy.data.materials.remove(material, do_unlink=True)
        for image in images:
            bpy.data.images.remove(image, do_unlink=True)


def _parse_glb(blob):
    _require(len(blob) >= 20, "Truncated GLB header")
    magic, version, total = struct.unpack_from("<III", blob, 0)
    _require(magic == 0x46546C67 and version == 2 and total == len(blob), "Invalid GLB header")
    chunks, offset = [], 12
    while offset < total:
        _require(offset + 8 <= total, "Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", blob, offset)
        _require(length % 4 == 0 and offset + 8 + length <= total, "Invalid GLB chunk bounds")
        chunks.append((kind, blob[offset + 8:offset + 8 + length]))
        offset += 8 + length
    _require(chunks and chunks[0][0] == JSON_CHUNK, "GLB first chunk must be JSON")
    _require(sum(kind == JSON_CHUNK for kind, _ in chunks) == 1, "GLB needs exactly one JSON chunk")
    _require(sum(kind == BIN_CHUNK for kind, _ in chunks) == 1, "GLB needs exactly one BIN chunk")
    document = json.loads(chunks[0][1].decode("utf-8").rstrip(" \t\r\n\x00"))
    _require(document.get("asset", {}).get("version") == "2.0", "Expected glTF 2.0")
    return document, chunks


def _pack_glb(document, chunks):
    raw_json = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = []
    for kind, data in chunks:
        if kind == JSON_CHUNK:
            data = raw_json
        data += (b" " if kind == JSON_CHUNK else b"\x00") * (-len(data) % 4)
        packed.append(struct.pack("<II", len(data), kind) + data)
    body = b"".join(packed)
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def _texture_image(document, texture_info):
    index = texture_info.get("index")
    textures = document.get("textures", [])
    _require(type(index) is int and 0 <= index < len(textures), "Invalid lightmap texture index")
    source = textures[index].get("source")
    _require(type(source) is int and 0 <= source < len(document.get("images", [])),
             "Lightmap texture needs a standard PNG image source")
    return source


def _replace_night_images(document, chunks, atlas_images, night_bytes):
    buffers = document.get("buffers", [])
    _require(len(buffers) == 1 and "uri" not in buffers[0], "Expected one embedded GLB buffer")
    _require(len(document.get("images", [])) == 4 and len(set(atlas_images.values())) == 4,
             "Expected exactly four distinct embedded night atlas images")
    binary = next(data for kind, data in chunks if kind == BIN_CHUNK)
    _require(buffers[0].get("byteLength", -1) <= len(binary), "GLB buffer exceeds BIN chunk")
    views = document.get("bufferViews", [])
    replacements = {}
    for atlas, image_index in atlas_images.items():
        image = document["images"][image_index]
        view_index = image.get("bufferView")
        _require(type(view_index) is int and 0 <= view_index < len(views),
                 f"Atlas {atlas}: exporter did not embed PNG via bufferView")
        _require(view_index not in replacements, "Night images unexpectedly share a bufferView")
        _require(image.get("mimeType") == "image/png", f"Atlas {atlas}: exporter did not emit PNG")
        replacements[view_index] = night_bytes[atlas]
        document["images"][image_index] = {
            "name": f"GALLERY_NIGHT_{atlas}", "mimeType": "image/png", "bufferView": view_index,
            "extras": {"atlas": atlas, "state": "night", "sha256": _sha256(night_bytes[atlas])},
        }
    # Keep every bufferView index stable, including sparse/accessor references;
    # repack its contents so PNG replacement never leaves duplicate image bytes.
    rebuilt = bytearray()
    for index, view in enumerate(views):
        _require(view.get("buffer", 0) == 0, "Unexpected external bufferView")
        start, length = view.get("byteOffset", 0), view.get("byteLength")
        _require(type(start) is int and type(length) is int and start >= 0 and length >= 0
                 and start + length <= buffers[0]["byteLength"], "Invalid bufferView bounds")
        payload = replacements.get(index)
        if payload is None:
            payload = binary[start:start + length]
        rebuilt.extend(b"\x00" * (-len(rebuilt) % 4))
        view["byteOffset"], view["byteLength"] = len(rebuilt), len(payload)
        rebuilt.extend(payload)
    buffers[0]["byteLength"] = len(rebuilt)
    return [(kind, bytes(rebuilt) if kind == BIN_CHUNK else data) for kind, data in chunks]


def _used_extensions(value):
    names = set()
    if isinstance(value, dict):
        extensions = value.get("extensions", {})
        if isinstance(extensions, dict):
            names.update(extensions)
        for item in value.values():
            names.update(_used_extensions(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_used_extensions(item))
    return names


def _patch_glb(blob, material_names, night_bytes, preparation_id, day_records, output_path):
    document, chunks = _parse_glb(blob)
    atlas_images, material_identities = {}, set()
    for material in document.get("materials", []):
        old_name = material.get("name")
        _require(old_name in material_names, f"Unexpected exported material: {old_name!r}")
        name = material_names[old_name]
        _require(name not in material_identities, f"Duplicate exported material: {name}")
        material_identities.add(name)
        material["name"] = name
        if name == "GALLERY_CLEAR":
            pbr = {"baseColorFactor": [0.77, 0.87, 0.90, 0.10],
                   "metallicFactor": 0, "roughnessFactor": 1}
            material["alphaMode"] = "BLEND"
            material["extras"] = {"web_kind": "glass", "bake_atlas": -1}
        else:
            atlas = int(name.rsplit("_", 1)[1])
            texture_info = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if texture_info is None:
                texture_info = material.get("emissiveTexture")
            _require(isinstance(texture_info, dict), f"{name}: exported material lost its lightmap")
            _require(texture_info.get("texCoord", 0) == 0, f"{name}: BakeUV must be TEXCOORD_0")
            atlas_images[atlas] = _texture_image(document, texture_info)
            pbr = {"baseColorTexture": texture_info, "baseColorFactor": [1, 1, 1, 1],
                   "metallicFactor": 0, "roughnessFactor": 1}
            material["alphaMode"] = "OPAQUE"
            material["extras"] = {"web_kind": "baked", "bake_atlas": atlas}
        material["pbrMetallicRoughness"] = pbr
        for key in ("emissiveTexture", "emissiveFactor", "normalTexture", "occlusionTexture", "alphaCutoff"):
            material.pop(key, None)
        material["doubleSided"] = True
        material["extensions"] = {"KHR_materials_unlit": {}}
    _require(set(atlas_images) == set(range(4)), "Export is missing one or more lightmap materials")
    chunks = _replace_night_images(document, chunks, atlas_images, night_bytes)
    external_day = []
    for record in day_records:
        texture_path = Path(record["path"])
        if not texture_path.is_absolute():
            texture_path = ROOT / texture_path
        external_day.append({"atlas": record["atlas"],
                             "uri": Path(os.path.relpath(texture_path, output_path.parent)).as_posix(),
                             "resolution": record["resolution"], "sha256": record["sha256"]})
    metadata = {"export_kind": "works_gallery_dual_lightmap_v3", "web_baked": True,
                "preparation_id": preparation_id, "default_state": "night",
                "baked_states": ["day", "night"], "atlas_sizes": list(ATLAS_SIZES),
                "night_images_embedded": True, "day_lightmaps": external_day}
    document.setdefault("asset", {}).setdefault("extras", {}).update(metadata)
    for scene in document.get("scenes", []):
        scene.setdefault("extras", {}).update(metadata)
    used = _used_extensions(document)
    document["extensionsUsed"] = sorted(used)
    document["extensionsRequired"] = sorted(
        (set(document.get("extensionsRequired", [])) & used) | {"KHR_materials_unlit"}
    )
    return _pack_glb(document, chunks)


def _validate_export(blob, inventory, night_bytes):
    document, chunks = _parse_glb(blob)
    nodes = document.get("nodes", [])
    parents, source_nodes, asset_nodes = {}, {}, {}
    for index, node in enumerate(nodes):
        extras = node.get("extras", {})
        identity, source_name = extras.get("asset_id"), extras.get(SOURCE_KEY)
        if identity:
            _require(identity not in asset_nodes, f"Duplicate GLB asset_id: {identity}")
            asset_nodes[identity] = index
        if source_name is not None:
            _require(source_name not in source_nodes, f"Duplicate exported object: {source_name}")
            source_nodes[source_name] = index
        for child in node.get("children", []):
            _require(type(child) is int and 0 <= child < len(nodes) and child not in parents,
                     "GLB contains invalid or multiply parented nodes")
            parents[child] = index
    _require(sorted(asset_nodes) == inventory["asset_ids"], "GLB asset IDs differ from the prepared scene")
    _require(set(source_nodes) == set(inventory["object_hierarchy"]),
             "GLB object set differs from the source hierarchy closure")
    hierarchy = {}
    for identity, index in asset_nodes.items():
        current, seen, ancestor = parents.get(index), {index}, None
        while current is not None:
            _require(current not in seen, "GLB node hierarchy contains a cycle")
            seen.add(current)
            parent_id = nodes[current].get("extras", {}).get("asset_id")
            if parent_id:
                ancestor = parent_id
                break
            current = parents.get(current)
        hierarchy[identity] = ancestor
    _require(hierarchy == inventory["asset_hierarchy"], "GLB nearest-asset parent relationships changed")
    for source_name, index in source_nodes.items():
        actual_parent = parents.get(index)
        actual_parent_name = (nodes[actual_parent].get("extras", {}).get(SOURCE_KEY)
                              if actual_parent is not None else None)
        _require(actual_parent_name == inventory["object_hierarchy"][source_name],
                 f"GLB changed immediate parent of {source_name}")
        _require(nodes[index].get("extras", {}).get("owner_asset_id")
                 == inventory["object_owners"][source_name], f"GLB lost owner metadata: {source_name}")
    default_scene = document.get("scene", 0)
    scenes = document.get("scenes", [])
    _require(type(default_scene) is int and 0 <= default_scene < len(scenes), "GLB has no default scene")
    reachable, pending = set(), list(scenes[default_scene].get("nodes", []))
    while pending:
        index = pending.pop()
        _require(type(index) is int and 0 <= index < len(nodes), "Invalid GLB scene root")
        _require(index not in reachable, "GLB scene repeats a node or contains a cycle")
        reachable.add(index)
        pending.extend(nodes[index].get("children", []))
    _require(set(source_nodes.values()) <= reachable, "Exported source nodes are unreachable in the default scene")
    materials = document.get("materials", [])
    expected_names = {f"GALLERY_LIGHTMAP_{atlas}" for atlas in range(4)}
    if inventory["glass_meshes"]:
        expected_names.add("GALLERY_CLEAR")
    _require({mat.get("name") for mat in materials} == expected_names, "Incorrect GLB material set")
    binary = next(data for kind, data in chunks if kind == BIN_CHUNK)
    embedded = []
    for material in materials:
        _require("KHR_materials_unlit" in material.get("extensions", {}) and material.get("doubleSided"),
                 f"{material['name']}: expected double-sided unlit material")
        pbr = material["pbrMetallicRoughness"]
        if material["name"] == "GALLERY_CLEAR":
            _require(pbr["baseColorFactor"][3] == 0.10 and material.get("alphaMode") == "BLEND",
                     "Glass alpha must be 0.10 BLEND")
            continue
        atlas = int(material["name"].rsplit("_", 1)[1])
        image = document["images"][_texture_image(document, pbr["baseColorTexture"])]
        _require("uri" not in image and "bufferView" in image and image.get("mimeType") == "image/png",
                 f"Atlas {atlas}: night map must be embedded PNG")
        view = document["bufferViews"][image["bufferView"]]
        start, length = view.get("byteOffset", 0), view["byteLength"]
        data = binary[start:start + length]
        info = _png_info(data, f"embedded night-{atlas}.png")
        _require(info["dimensions"] == [ATLAS_SIZES[atlas]] * 2 and data == night_bytes[atlas],
                 f"Embedded night-{atlas}.png differs from the validated source bake")
        embedded.append(dict(info, atlas=atlas, bufferView=image["bufferView"]))
    _require(len(embedded) == len(document.get("images", [])) == 4, "Expected four embedded night PNGs")
    triangles, primitive_count, by_material = 0, 0, {}
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            _require(primitive.get("mode", 4) == 4, "Expected triangle primitives only")
            material_index = primitive.get("material")
            _require(type(material_index) is int and 0 <= material_index < len(materials),
                     "Primitive is missing an export material")
            accessor = primitive.get("indices", primitive.get("attributes", {}).get("POSITION"))
            _require(type(accessor) is int and 0 <= accessor < len(document.get("accessors", [])),
                     "Triangle primitive has no valid index/position accessor")
            count = document["accessors"][accessor]["count"]
            _require(count % 3 == 0, "Triangle primitive count is not divisible by three")
            if materials[material_index]["name"].startswith("GALLERY_LIGHTMAP_"):
                _require("TEXCOORD_0" in primitive.get("attributes", {}), "Baked mesh lost BakeUV/TEXCOORD_0")
            triangles += count // 3
            primitive_count += 1
            name = materials[material_index]["name"]
            item = by_material.setdefault(name, {"primitives": 0, "triangles": 0})
            item["primitives"] += 1
            item["triangles"] += count // 3
    _require(triangles > 0, "GLB contains no triangles")
    return {
        "triangles": triangles, "drawPrimitives": primitive_count, "primitive_count": primitive_count,
        "mesh_count": len(document.get("meshes", [])), "node_count": len(nodes),
        "materials": [mat["name"] for mat in materials], "material_statistics": by_material,
        "embedded_night_images": sorted(embedded, key=lambda item: item["atlas"]),
        "asset_ids": sorted(asset_nodes), "componentIds": sorted(asset_nodes),
        "asset_hierarchy": dict(sorted(hierarchy.items())),
        "root_asset_ids": sorted(identity for identity, parent in hierarchy.items() if parent is None),
        "object_hierarchy": inventory["object_hierarchy"], "object_owners": inventory["object_owners"],
        "checks": {"asset_ids_match_source": True, "asset_ids_unique": True,
                   "asset_hierarchy_matches_source": True, "object_hierarchy_matches_source": True,
                   "owner_metadata_preserved": True, "source_nodes_reachable": True,
                   "four_night_pngs_embedded_and_byte_identical": True,
                   "materials_unlit_double_sided": True, "png_chunk_crc_checks": True},
    }


def _temporary_path(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, path = tempfile.mkstemp(prefix=f".{destination.stem}-", suffix=destination.suffix,
                                        dir=str(destination.parent))
    os.close(descriptor)
    return Path(path)


def export(prepared_path=None, output_path=None, textures_directory=None, report_path=None):
    """Validate both bakes, export temporary copies, verify and atomically publish.

    Returns the JSON-serializable report.  An invalid bake or export never replaces
    an existing output model.  No save_mainfile/save_as_mainfile operation occurs.
    """
    prepared = Path(prepared_path or PREPARED).expanduser().resolve()
    output = Path(output_path or OUTPUT).expanduser().resolve()
    textures = Path(textures_directory or TEXTURES).expanduser().resolve()
    report_path = Path(report_path or REPORT).expanduser().resolve()
    _require(prepared.suffix.lower() == ".blend", "Prepared input must be a .blend file")
    _require(output.suffix.lower() == ".glb", "Output must be a .glb file")
    _require(report_path.suffix.lower() == ".json", "Report must be a .json file")
    protected = {prepared} | {textures / f"{state}-manifest.json" for state in ("day", "night")}
    _require(output not in protected and report_path not in protected and output != report_path,
             "Output paths collide with an input or bake manifest")
    records, night_bytes = _read_textures(textures)
    try:
        import bpy
    except ImportError as error:
        raise RuntimeError("Export requires Blender Python; run blender --background --python export_gallery.py -- ...") from error
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is None:
        _require(prepared.is_file(), f"Missing prepared gallery blend: {prepared}")
        bpy.ops.wm.open_mainfile(filepath=str(prepared))
        scene = bpy.data.scenes.get(SCENE_NAME)
    _require(scene is not None, f"Prepared blend has no {SCENE_NAME} scene")
    preparation_id = scene.get("preparation_id")
    manifests = _verify_manifests(textures, preparation_id, records)
    objects, inventory = _source_inventory(scene)
    temporary_output, temporary_report = None, None
    try:
        temporary_output = _temporary_path(output)
        with _export_scene(bpy, scene, objects, textures) as (_, material_names):
            status = bpy.ops.export_scene.gltf(
                filepath=str(temporary_output), export_format="GLB", use_active_scene=True,
                use_selection=True, export_extras=True, export_yup=True, export_animations=False,
                export_lights=False, export_cameras=False, export_materials="EXPORT",
                export_texcoords=True, export_normals=False, export_tangents=False,
                export_image_format="AUTO",
                export_copyright="Original editable gallery assets and Cycles lighting. Room interaction template: Andrew Woan, MIT.",
            )
            _require("FINISHED" in status, f"glTF exporter did not finish: {status}")
            blob = _patch_glb(temporary_output.read_bytes(), material_names, night_bytes,
                              preparation_id, records["day"], output)
            validation = _validate_export(blob, inventory, night_bytes)
        # Validate the serialized form and write only the export/report artifacts.
        temporary_output.write_bytes(blob)
        _require(_sha256(temporary_output.read_bytes()) == _sha256(blob), "Written GLB checksum mismatch")
        report = dict(validation,
                      model=_path_label(output), prepared=_path_label(prepared),
                      loaded_blend=_path_label(bpy.data.filepath) if bpy.data.filepath else None,
                      prepared_scene=SCENE_NAME, export_kind="works_gallery_dual_lightmap_v3",
                      preparation_id=preparation_id, bytes=len(blob), sha256=_sha256(blob),
                      bakedStates=["day", "night"], atlasSizes=list(ATLAS_SIZES),
                      external_baked_states=records, bake_manifests=manifests,
                      atlas_meshes=inventory["atlas_meshes"], glass_meshes=inventory["glass_meshes"],
                      source_scene_preserved=True, blend_files_written=False,
                      color="Cycles baked sRGB maps; KHR_materials_unlit; no runtime tone mapping")
        if scene.get("preparation_manifest"):
            manifest = scene["preparation_manifest"]
            report["preparation_manifest"] = json.loads(manifest) if isinstance(manifest, str) else str(manifest)
        temporary_report = _temporary_path(report_path)
        temporary_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary_output, output)
        os.replace(temporary_report, report_path)
        return report
    finally:
        for path in (temporary_output, temporary_report):
            if path is not None:
                path.unlink(missing_ok=True)


def main(argv=None):
    if argv is None:
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1:]
        elif Path(sys.argv[0]).name == Path(__file__).name:
            argv = sys.argv[1:]
        else:
            argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=PREPARED)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--textures", type=Path, default=TEXTURES)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    report = export(prepared_path=args.prepared, output_path=args.output,
                    textures_directory=args.textures, report_path=args.report)
    print(json.dumps({key: report[key] for key in
                      ("model", "bytes", "sha256", "triangles", "drawPrimitives", "materials")}, indent=2))
    return report


if __name__ == "__main__":
    main()
