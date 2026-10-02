"""Verify that retained lightmaps still have exactly matching geometry and UVs."""
import array
import bpy
import hashlib
import json

def fingerprints(scene, include_shading=False):
    bpy.context.window.scene = scene
    scene.view_layers[0].update()
    records = {}
    for obj in scene.objects:
        if obj.type != 'MESH' or not obj.get('web_export') or obj.get('web_kind') != 'baked':
            continue
        digest = hashlib.sha256()
        mesh = obj.data
        positions = array.array('f', [0]) * (len(mesh.vertices)*3)
        mesh.vertices.foreach_get('co', positions)
        digest.update(positions.tobytes())
        loops = array.array('i', [0]) * len(mesh.loops)
        mesh.loops.foreach_get('vertex_index', loops)
        digest.update(loops.tobytes())
        uvs = array.array('f', [0]) * (len(mesh.loops)*2)
        mesh.uv_layers['BakeUV'].data.foreach_get('uv', uvs)
        digest.update(uvs.tobytes())
        if include_shading:
            # Normal fixes change baked highlights even if positions/UVs match.
            normals = array.array('f', [0]) * (len(mesh.corner_normals)*3)
            mesh.corner_normals.foreach_get('vector', normals)
            digest.update(normals.tobytes())
            digest.update(bytes(int(face.use_smooth) for face in mesh.polygons))
        digest.update(array.array('f', [v for row in obj.matrix_world for v in row]).tobytes())
        key = str(obj['bake_atlas'])+'::'+obj['owner_asset_id']
        if key in records:
            raise RuntimeError('Ambiguous geometry owner: '+key)
        records[key] = {'atlas':obj['bake_atlas'], 'vertices':len(mesh.vertices), 'loops':len(mesh.loops), 'sha256':digest.hexdigest()}
    return records
