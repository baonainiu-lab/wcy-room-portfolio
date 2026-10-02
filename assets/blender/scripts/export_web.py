"""Create disposable glTF scene from the approved-for-modeling V4 source.
Does not save or modify the source scene. Logical assets/components remain separate.
"""
import bpy, json, math, numpy as np
from pathlib import Path
from mathutils import Matrix
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
source=bpy.data.scenes['ORBITAL_ATELIER_V2']
previous=bpy.context.window.scene
export_scene=bpy.data.scenes.new('WEB_PREVIEW_EXPORT')
bpy.context.window.scene=source
dg=bpy.context.evaluated_depsgraph_get()
objects=[o for o in source.objects if o.type in {'MESH','CURVE','EMPTY'} and not o.hide_render and not any(c.name=='STUDIO_NON_EXPORT' for c in o.users_collection)]
materials={}; normal_images={}; copies={}; geometries=[]

def normal_image(image):
    if image.name in normal_images:return normal_images[image.name]
    w,h=image.size;arr=np.array(image.pixels[:],dtype=np.float32).reshape(h,w,4)[:,:,0]
    dy,dx=np.gradient(arr);n=np.stack([-dx*.16,-dy*.16,np.ones_like(arr)],axis=-1);n/=np.linalg.norm(n,axis=-1,keepdims=True)
    rgba=np.ones((h,w,4),dtype=np.float32);rgba[:,:,:3]=n*.5+.5
    im=bpy.data.images.new('WEB_Normal_'+image.name,width=w,height=h,alpha=False);im.colorspace_settings.name='Non-Color';im.pixels.foreach_set(rgba.ravel());im.pack();normal_images[image.name]=im
    return im

def web_material(original):
    if original is None:return None
    if original.name in materials:return materials[original.name]
    m=bpy.data.materials.new('WEB_'+original.name);m.use_nodes=True;m['source_material']=original.name
    nt=m.node_tree;p=nt.nodes.get('Principled BSDF');src=next((n for n in original.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if original.node_tree else None
    emission=next((n for n in original.node_tree.nodes if n.type=='EMISSION'),None) if original.node_tree else None
    if src:
        for socket in p.inputs:
            old=src.inputs.get(socket.name)
            if old is not None:
                try:socket.default_value=old.default_value
                except (AttributeError,TypeError):pass
        image_node=next((n for n in original.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name in {'fabric_weave','titanium_brush','micro_grain'}),None)
        if image_node:
            tex=nt.nodes.new('ShaderNodeTexImage');tex.image=normal_image(image_node.image)
            uv=nt.nodes.new('ShaderNodeTexCoord');mapping=nt.nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(3,3,3)
            nt.links.new(uv.outputs['UV'],mapping.inputs['Vector']);nt.links.new(mapping.outputs['Vector'],tex.inputs['Vector'])
            normal=nt.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.35;nt.links.new(tex.outputs['Color'],normal.inputs['Color']);nt.links.new(normal.outputs['Normal'],p.inputs['Normal'])
    elif emission:
        nt.nodes.remove(p);e=nt.nodes.new('ShaderNodeEmission');e.inputs['Color'].default_value=emission.inputs['Color'].default_value;e.inputs['Strength'].default_value=emission.inputs['Strength'].default_value
        texsrc=next((n for n in original.node_tree.nodes if n.type=='TEX_IMAGE' and n.image),None)
        if texsrc:
            tex=nt.nodes.new('ShaderNodeTexImage');tex.image=texsrc.image;nt.links.new(tex.outputs['Color'],e.inputs['Color'])
        nt.links.new(e.outputs[0],nt.nodes.get('Material Output').inputs['Surface'])
    materials[original.name]=m;return m

# Evaluate original modifiers, preserving source transforms and asset metadata.
for old in objects:
    if old.type=='EMPTY':new=bpy.data.objects.new(old.name+'__web',None)
    else:
        mesh=bpy.data.meshes.new_from_object(old.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
        if not len(mesh.vertices):bpy.data.meshes.remove(mesh);continue
        for i,mat in enumerate(list(mesh.materials)):mesh.materials[i]=web_material(mat)
        new=bpy.data.objects.new(old.name+'__web',mesh);geometries.append(new)
    export_scene.collection.objects.link(new);new.matrix_world=old.matrix_world.copy();copies[old]=new
    for key in old.keys():
        if key!='_RNA_UI':
            try:new[key]=old[key]
            except TypeError:pass
    new['source_node']=old.name
bpy.context.window.scene=export_scene
bpy.context.view_layer.update()
for old,new in copies.items():
    par=old.parent
    while par and par not in copies:par=par.parent
    if par:
        mx=new.matrix_world.copy();new.parent=copies[par];new.matrix_world=mx
bpy.context.view_layer.update()
# Consolidate details only inside each independent component; no cross-asset merging.
# Material slots are preserved by join, producing one primitive per material.
buckets={}
for o in geometries:
    owner=o.parent
    while owner and not owner.get('asset_id'):owner=owner.parent
    buckets.setdefault(owner,[]).append(o)
for owner,parts in buckets.items():
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:part.select_set(True)
    active=parts[0];bpy.context.view_layer.objects.active=active
    if len(parts)>1:bpy.ops.object.join()
    mx=active.matrix_world.copy();active.parent=owner;active.matrix_world=mx
    active.name=(owner.get('asset_id') if owner else 'room_static')+'__geometry'
bpy.ops.object.select_all(action='SELECT')
out=ROOT/'public/models/orbital-atelier-v4.glb'
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',use_active_scene=True,use_selection=True,export_apply=False,export_extras=True,export_yup=True,export_animations=False,export_lights=False,export_cameras=False,export_image_format='AUTO',export_materials='EXPORT',export_copyright='Original orbital atelier assets created for this portfolio in Blender; template code copyright 2025 Andrew Woan (MIT).')
report={'source':'assets/blender/orbital-atelier-v2.blend','output':'public/models/orbital-atelier-v4.glb','source_scene':source.name,'logical_roots':[{'id':o.get('asset_id'),'source_node':o.get('source_node')} for o in export_scene.objects if o.type=='EMPTY' and not o.parent],'component_groups':sum(o.type=='EMPTY' for o in export_scene.objects),'mesh_groups':sum(o.type=='MESH' for o in export_scene.objects),'vertices':sum(len(o.data.vertices) for o in export_scene.objects if o.type=='MESH'),'material_count':len(materials),'bytes':out.stat().st_size,'method':'Evaluated Blender geometry; mesh joins limited to nearest asset/component parent; PBR parameters, original screen/city textures, derived micro normal maps; no third-party artwork.'}
(ROOT/'assets/blender/web-export-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
bpy.context.window.scene=previous
for o in list(export_scene.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.data.scenes.remove(export_scene)
# Keep original render file untouched on disk. Unused export datablocks are discarded on reload.
result=report
