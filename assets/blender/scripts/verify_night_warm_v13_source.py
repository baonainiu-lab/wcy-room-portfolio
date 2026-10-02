"""Prove the editable V13 day scene remains identical to the V12 day scene."""
import array
import hashlib
import json
from pathlib import Path
import bpy

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')


def tree_signature(tree):
    if tree is None:
        return None
    nodes = []
    for node in tree.nodes:
        sockets = []
        for socket in node.inputs:
            if not hasattr(socket, 'default_value'):
                continue
            value = socket.default_value
            if not isinstance(value, (float,int,str,bool)):
                try:
                    value = list(value)
                except TypeError:
                    value = str(value)
            sockets.append([socket.name,value])
        nodes.append({'name':node.name,'type':node.bl_idname,'inputs':sockets,
            'image':getattr(getattr(node,'image',None),'name',None)})
    return {'nodes':nodes,'links':[[x.from_node.name,x.from_socket.name,x.to_node.name,x.to_socket.name] for x in tree.links]}


def mesh_signature(mesh):
    digest = hashlib.sha256()
    for collection, attr, count, kind in [(mesh.vertices,'co',3,'f'),(mesh.loops,'vertex_index',1,'I'),
                                         (mesh.polygons,'material_index',1,'I'),(mesh.polygons,'use_smooth',1,'b')]:
        values = array.array(kind,[0])*(len(collection)*count)
        collection.foreach_get(attr,values)
        digest.update(values.tobytes())
    for uv in mesh.uv_layers:
        digest.update(uv.name.encode())
        values = array.array('f',[0])*(len(uv.data)*2)
        uv.data.foreach_get('uv',values)
        digest.update(values.tobytes())
    return digest.hexdigest()


def snapshot(path, revision):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.data.scenes[f'ORIGINAL_DAY_V{revision}']
    night = bpy.data.scenes[f'ORIGINAL_NIGHT_V{revision}']
    bpy.context.window.scene=scene
    scene.view_layers[0].update()
    rows = []
    day_objects=set(scene.objects)
    day_meshes={o.data for o in scene.objects if o.type=='MESH'}
    sharing = {'sharedObjects':[o.name for o in night.objects if o in day_objects],
               'sharedMeshData':[o.data.name for o in night.objects if o.type=='MESH' and o.data in day_meshes]}
    for obj in sorted(scene.objects,key=lambda o:o.name):
        row={'name':obj.name,'type':obj.type,'matrix':[list(v) for v in obj.matrix_world],
             'hideRender':obj.hide_render,'assetId':obj.get('asset_id')}
        if obj.type=='MESH':
            row['geometryUvSmoothMaterialIndices']=mesh_signature(obj.data)
            row['materials']=[{'name':m.name,'nodes':tree_signature(m.node_tree),
                               'diffuseColor':list(m.diffuse_color)} if m else None for m in obj.data.materials]
        if obj.type=='LIGHT':
            row['light']={'type':obj.data.type,'energy':obj.data.energy,'color':list(obj.data.color),
                          'size':getattr(obj.data,'size',None)}
        rows.append(row)
    value={'objects':rows,'world':tree_signature(scene.world.node_tree),
           'view':{'transform':scene.view_settings.view_transform,'look':scene.view_settings.look,
                   'exposure':scene.view_settings.exposure,'gamma':scene.view_settings.gamma}}
    return value,sharing


def run():
    previous,sharing12=snapshot(ROOT/'assets/blender/orbital-atelier-v12.blend',12)
    current,sharing13=snapshot(ROOT/'assets/blender/orbital-atelier-v13.blend',13)
    def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    passed=previous==current
    report={'passed':passed,'daySignatureV12':sha(previous),'daySignatureV13':sha(current),
            'scope':'All editable day objects, transforms, mesh positions/topology/UVs/smooth flags/material indices, material node values/links, lights, world nodes and view settings.',
            'v12Sharing':sharing12,'v13Sharing':sharing13,
            'objectCount':len(current['objects']),
            'daySceneRenameOnly':'ORIGINAL_DAY_V12 to ORIGINAL_DAY_V13'}
    (ROOT/'assets/blender/source-day-v13-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    if not passed:
        before={o['name']:o for o in previous['objects']};after={o['name']:o for o in current['objects']}
        report['changedObjects']=[n for n in before.keys()|after.keys() if before.get(n)!=after.get(n)]
        raise RuntimeError(json.dumps(report))
    print(json.dumps(report,indent=2))


if __name__=='__main__':run()
