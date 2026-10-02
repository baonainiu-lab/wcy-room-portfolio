"""Snapshot the editable gallery into an isolated four-atlas bake scene.

Blender API: prepare(source_path=None, output_path=None, report_path=None).
CLI: blender --background --python prepare_gallery.py -- [--source ...]
The editable source is never saved or overwritten. No decimation is performed.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
import time
from pathlib import Path

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "assets/blender/works-gallery-v1.blend"
OUTPUT = ROOT / "assets/blender/works-gallery-bake-v1.blend"
REPORT = ROOT / "assets/blender/works-gallery-v1/preparation-report.json"
SOURCE_SCENE = "WORKS_GALLERY_V1"
SCENE_NAME = "WEB_WORKS_GALLERY_V1"
ATLAS_SPECS = (("architecture", 4096), ("environment", 3072),
               ("exhibits", 4096), ("furnishings", 4096))
TARGET_NODE = "GALLERY_BAKE_TARGET"
IMAGE_PREFIX = "GALLERY_BAKE_ATLAS_"
IDENTITY_KEYS = {"asset_id", "stableAssetId", "stable_asset_id"}


def _json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _relative(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _properties(source, target, skip=()):
    for key in source.keys():
        if key != "_RNA_UI" and key not in skip:
            try:
                target[key] = source[key]
            except (TypeError, ValueError):
                pass


def _parents(obj, include_self=False):
    if not include_self:
        obj = obj.parent
    while obj is not None:
        yield obj
        obj = obj.parent


def _owner(obj):
    # A marked mesh is itself an independently interactive asset.
    return next((p for p in _parents(obj, True) if p.get("asset_id")), None)


def _atlas(obj):
    for item in _parents(obj, True):
        if "bake_atlas" in item:
            atlas = int(item["bake_atlas"])
            if 0 <= atlas < len(ATLAS_SPECS):
                return atlas
            raise ValueError("Invalid atlas on " + item.name)
    raise ValueError("No inherited bake_atlas for " + obj.name)


def _excluded(obj):
    return obj.type in {"LIGHT", "CAMERA"} or any(
        p.get("export_exclude", False) for p in _parents(obj, True))


def _reparent(obj, parent):
    transform = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = transform


def _triangles(obj):
    return sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)


def _glass(material):
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                socket = node.inputs.get("Transmission Weight") or node.inputs.get("Transmission")
                if socket and socket.default_value > 0:
                    return True
    return False


def _partition(obj, scene):
    """Split mixed transparent/opaque faces without duplicating a mesh asset ID."""
    flags = [_glass(mat) for mat in obj.data.materials]
    face_kinds = {bool(flags[p.material_index]) if p.material_index < len(flags) else False
                  for p in obj.data.polygons}
    if len(face_kinds) < 2:
        return [(obj, "glass" if True in face_kinds else "baked")]
    other = obj.copy()
    other.data = obj.data.copy()
    other.name = obj.name + "__glass"
    scene.collection.objects.link(other)
    for key in IDENTITY_KEYS:
        if key in other:
            del other[key]
    other["interactive"] = False
    _reparent(other, obj if obj.get("asset_id") else obj.parent)
    for item, keep_glass in ((obj, False), (other, True)):
        bm = bmesh.new()
        try:
            bm.from_mesh(item.data)
            remove = [f for f in bm.faces
                      if (bool(flags[f.material_index]) if f.material_index < len(flags) else False) != keep_glass]
            bmesh.ops.delete(bm, geom=remove, context="FACES")
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context="VERTS")
            bm.to_mesh(item.data)
        finally:
            bm.free()
        item.data.update()
    return [(obj, "baked"), (other, "glass")]


def _source_uv(obj):
    layers = obj.data.uv_layers
    if not layers.get("UVMap"):
        # do_init copies the active source UV without renaming explicit UV maps.
        layers.new(name="UVMap", do_init=True)


def _material(old, key, cache):
    if old is None:
        raise RuntimeError("Every baked surface requires a source material.")
    cache_key = (old.as_pointer(), key)
    if cache_key in cache:
        return cache[cache_key]
    material = old.copy()
    material.name = "GALLERY_PREP_" + key + "_" + old.name
    material["source_material"] = old.name
    cache[cache_key] = material
    material.use_nodes = True
    tree = material.node_tree
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.name = "GALLERY_ORIGINAL_UV"
    uv.uv_map = "UVMap"
    for node in list(tree.nodes):
        if node.type == "TEX_COORD":
            for link in list(node.outputs["UV"].links):
                tree.links.new(uv.outputs["UV"], link.to_socket)
        elif node.type == "TEX_IMAGE" and not node.inputs["Vector"].is_linked:
            tree.links.new(uv.outputs["UV"], node.inputs["Vector"])
    return material


def _hierarchy(objects):
    result = {}
    for obj in objects:
        if obj.get("asset_id"):
            ancestor = next((p for p in _parents(obj) if p.get("asset_id")), None)
            result[str(obj["asset_id"])] = str(ancestor["asset_id"]) if ancestor else None
    return result


def _fingerprint(meshes):
    digest = hashlib.sha256()
    for obj in sorted(meshes, key=lambda item: item.name):
        digest.update(obj.name.encode())
        digest.update(str(obj.get("owner_asset_id", "")).encode())
        digest.update(struct.pack("<i", int(obj["geometry_atlas"])))
        for row in obj.matrix_world:
            digest.update(struct.pack("<4f", *row))
        for vertex in obj.data.vertices:
            digest.update(struct.pack("<3f", *vertex.co))
        for face in obj.data.polygons:
            digest.update(struct.pack("<I", len(face.vertices)))
            digest.update(struct.pack("<%dI" % len(face.vertices), *face.vertices))
        layer = obj.data.uv_layers.get("BakeUV")
        if layer:
            for item in layer.data:
                digest.update(struct.pack("<2f", *item.uv))
    return digest.hexdigest()


def prepare(source_path=None, output_path=None, report_path=None):
    started = time.monotonic()
    source_path = Path(source_path or SOURCE).resolve()
    output_path = Path(output_path or OUTPUT).resolve()
    report_path = Path(report_path or REPORT).resolve()
    if output_path.suffix.lower() != ".blend" or report_path.suffix.lower() != ".json":
        raise ValueError("Prepared output must be .blend and its report must be .json.")
    if output_path == source_path or output_path == SOURCE.resolve():
        raise ValueError("Prepared output must never overwrite the editable gallery source.")
    source = bpy.data.scenes.get(SOURCE_SCENE)
    if source is None:
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        bpy.ops.wm.open_mainfile(filepath=str(source_path))
        source = bpy.data.scenes.get(SOURCE_SCENE)
    if source is None:
        raise RuntimeError("The source must contain " + SOURCE_SCENE)
    if bpy.data.filepath and output_path == Path(bpy.data.filepath).resolve():
        raise ValueError("Prepared output must not overwrite the currently open source file.")
    if bpy.data.scenes.get(SCENE_NAME):
        raise RuntimeError("Prepared scene exists. Reopen the editable source before preparing again.")
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    source_ids = [str(o["asset_id"]) for o in source.objects if o.get("asset_id") and not _excluded(o)]
    if len(source_ids) != len(set(source_ids)):
        raise RuntimeError("Source contains duplicate export asset IDs.")
    source_hierarchy = _hierarchy(o for o in source.objects if not _excluded(o))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    scene = bpy.data.scenes.new(SCENE_NAME)
    _properties(source, scene)
    scene.world = source.world.copy() if source.world else None
    if scene.world:
        scene.world.name = "GALLERY_PREP_WORLD"
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .035
    scene.cycles.max_bounces = 7
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 6
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = source.view_settings.exposure
    scene.view_settings.gamma = source.view_settings.gamma
    try:
        scene.view_settings.look = source.view_settings.look
    except TypeError:
        pass
    scene.render.resolution_x = source.render.resolution_x
    scene.render.resolution_y = source.render.resolution_y
    scene.render.resolution_percentage = source.render.resolution_percentage
    scene.render.film_transparent = source.render.film_transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = True

    copies, geometry, context = {}, [], []
    # Finish every evaluated snapshot before editing, joining or deleting copies.
    for old in list(source.objects):
        if old.type not in {"MESH", "CURVE", "FONT", "SURFACE", "EMPTY", "LIGHT", "CAMERA"}:
            if old.get("asset_id") and not _excluded(old):
                raise RuntimeError("Unsupported identified object: " + old.name)
            continue
        is_context = _excluded(old)
        if old.hide_render and old.type not in {"EMPTY", "LIGHT", "CAMERA"} and not is_context:
            raise RuntimeError("Hidden export geometry needs an explicit source decision: " + old.name)
        if old.type == "EMPTY":
            new = bpy.data.objects.new("GALLERY_WEB_" + old.name, None)
            new.empty_display_type = old.empty_display_type
            new.empty_display_size = old.empty_display_size
        elif old.type in {"LIGHT", "CAMERA"}:
            new = bpy.data.objects.new("GALLERY_WEB_" + old.name, old.data.copy())
        else:
            data = bpy.data.meshes.new_from_object(old.evaluated_get(depsgraph),
                preserve_all_data_layers=True, depsgraph=depsgraph)
            if not len(data.polygons):
                bpy.data.meshes.remove(data)
                if old.get("asset_id"):
                    new = bpy.data.objects.new("GALLERY_WEB_" + old.name, None)
                else:
                    continue
            else:
                new = bpy.data.objects.new("GALLERY_WEB_" + old.name, data)
                if not is_context:
                    geometry.append(new)
        scene.collection.objects.link(new)
        new.matrix_world = old.matrix_world.copy()
        new.hide_render = old.hide_render
        _properties(old, new)
        new["source_node"] = old.name
        new["web_export"] = not is_context
        new["web_context"] = is_context
        if is_context:
            context.append(new)
        copies[old] = new

    bpy.context.window.scene = scene
    for old, new in copies.items():
        parent = next((p for p in _parents(old) if p in copies), None)
        if parent:
            _reparent(new, copies[parent])
    scene.camera = copies.get(source.camera)
    bpy.context.view_layer.update()
    # Keep ID-to-ID ancestry and pivots, but remove anonymous mesh nodes from the
    # parent chain so merging a fragment cannot orphan a marked descendant.
    for obj in list(scene.objects):
        if obj.get("web_export"):
            nearest = next((p for p in _parents(obj) if p.get("asset_id")), None)
            _reparent(obj, nearest)
    bpy.context.view_layer.update()
    materials = {}
    for obj in context:
        if obj.type == "MESH":
            _source_uv(obj)
            for index, old in enumerate(list(obj.data.materials)):
                if old:
                    obj.data.materials[index] = _material(old, "CONTEXT", materials)

    buckets = {}
    for obj in geometry:
        atlas = _atlas(obj)
        for part, kind in _partition(obj, scene):
            owner = _owner(part)
            if owner is None:
                raise RuntimeError("Export geometry requires its own or an ancestor asset_id: " + part.name)
            buckets.setdefault((owner, atlas, kind), []).append(part)
    meshes = []
    for (owner, atlas, kind), parts in buckets.items():
        # An identified mesh must remain the active object: join must not delete it.
        active = owner if owner in parts else parts[0]
        parent = active.parent if active is owner else owner
        bpy.ops.object.select_all(action="DESELECT")
        for part in parts:
            part.hide_set(False)
            part.select_set(True)
        bpy.context.view_layer.objects.active = active
        before = sum(_triangles(part) for part in parts)
        source_nodes = [p.get("source_node", p.name) for p in parts]
        if len(parts) > 1:
            bpy.ops.object.join()
        _reparent(active, parent)
        active.name = "GALLERY_WEB_" + str(owner["asset_id"]) + "__" + kind + "__A" + str(atlas)
        active["owner_asset_id"] = str(owner["asset_id"])
        active["web_kind"] = kind
        active["bake_atlas"] = atlas if kind == "baked" else -1
        active["geometry_atlas"] = atlas
        active["web_export"] = True
        active["merged_source_nodes"] = json.dumps(source_nodes, ensure_ascii=False)
        active["triangles_before"] = before
        if not active.data.materials or any(mat is None for mat in active.data.materials):
            raise RuntimeError("Missing source material on " + active.name)
        _source_uv(active)
        for index, old in enumerate(list(active.data.materials)):
            active.data.materials[index] = _material(old, "A%d_%s" % (atlas, kind), materials)
        if _triangles(active) != before:
            raise RuntimeError("Join unexpectedly changed triangle count: " + active.name)
        meshes.append(active)

    atlas_reports = []
    for atlas, (name, size) in enumerate(ATLAS_SPECS):
        members = [o for o in meshes if o.get("web_kind") == "baked" and o["bake_atlas"] == atlas]
        if not members:
            raise RuntimeError("Empty atlas: " + name)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in members:
            previous = obj.data.uv_layers.get("BakeUV")
            if previous:
                obj.data.uv_layers.remove(previous)
            layer = obj.data.uv_layers.new(name="BakeUV", do_init=False)
            obj.data.uv_layers.active = layer
            layer.active_render = True
            obj.select_set(True)
        bpy.context.view_layer.objects.active = members[0]
        try:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            status = bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.004,
                area_weight=.25, correct_aspect=True, scale_to_bounds=True)
            if "FINISHED" not in status:
                raise RuntimeError("UV projection did not finish for atlas " + name)
        finally:
            if bpy.context.object and bpy.context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
        for obj in members:
            layer = obj.data.uv_layers["BakeUV"]
            if len(layer.data) != len(obj.data.loops):
                raise RuntimeError("Incomplete BakeUV loop data on " + obj.name)
            for item in layer.data:
                if any(not math.isfinite(value) or value < -.001 or value > 1.001 for value in item.uv):
                    raise RuntimeError("Invalid packed BakeUV coordinates on " + obj.name)
        if bpy.data.images.get(IMAGE_PREFIX + str(atlas)):
            raise RuntimeError("A previous atlas image exists. Reopen the source before preparing again.")
        image = bpy.data.images.new(IMAGE_PREFIX + str(atlas), width=size, height=size,
                                   alpha=False, float_buffer=True)
        try:
            image.colorspace_settings.name = "Linear Rec.709"
        except TypeError:
            image.colorspace_settings.name = "Linear"
        atlas_materials = {m for obj in members for m in obj.data.materials if m}
        for material in atlas_materials:
            material["bake_atlas"] = atlas
            tree = material.node_tree
            for node in tree.nodes:
                node.select = False
            target = tree.nodes.new("ShaderNodeTexImage")
            target.name = TARGET_NODE
            target.label = "Shared day/night atlas destination"
            target.image = image
            target.select = True
            tree.nodes.active = target
        atlas_reports.append({"atlas": atlas, "label": name, "resolution": size,
            "image": image.name, "uv_layer": "BakeUV", "margin": 16,
            "mesh_count": len(members), "triangles": sum(_triangles(o) for o in members),
            "owner_ids": sorted({str(o["owner_asset_id"]) for o in members})})

    objects = [o for o in scene.objects if o.get("web_export")]
    ids = [str(o["asset_id"]) for o in objects if o.get("asset_id")]
    if len(ids) != len(set(ids)) or set(ids) != set(source_ids):
        raise RuntimeError("Preparation lost or duplicated source asset IDs.")
    hierarchy = _hierarchy(objects)
    if hierarchy != source_hierarchy:
        raise RuntimeError("Preparation changed the source asset hierarchy.")
    fingerprint = _fingerprint(meshes)
    # A fresh preparation must invalidate older maps even if only a shader or
    # lighting-relevant material changed while geometry and UVs stayed the same.
    preparation_id = hashlib.sha256((fingerprint + str(time.time_ns())).encode()).hexdigest()
    scene["preparation_id"] = preparation_id
    scene["geometry_uv_sha256"] = fingerprint
    scene["web_baked"] = False
    scene["dual_lighting_prepared"] = True
    scene["source_blend"] = str(source_path)
    scene["bake_mode"] = "cycles_combined_dual_day_night_agx"
    report = {"source": _relative(source_path), "prepared": _relative(output_path),
        "scene": SCENE_NAME, "preparation_id": preparation_id,
        "geometry_uv_sha256": fingerprint, "atlases": atlas_reports,
        "mesh_count": len(meshes), "triangles": sum(_triangles(o) for o in meshes),
        "triangles_before": sum(o["triangles_before"] for o in meshes), "decimated": False,
        "asset_count": len(ids), "asset_ids": sorted(ids), "asset_hierarchy": hierarchy,
        "context_objects": [o.name for o in context],
        "glass_meshes": [o.name for o in meshes if o["web_kind"] == "glass"],
        "seconds": round(time.monotonic() - started, 2)}
    scene["preparation_manifest"] = json.dumps(report, ensure_ascii=False)
    bpy.ops.object.select_all(action="DESELECT")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(output_path), {scene}, fake_user=True, compress=True)
    _json(report_path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    print(json.dumps(prepare(args.source, args.output, args.report), ensure_ascii=False, indent=2))
