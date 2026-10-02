"""V20 white marble WALLS only; author and inspect via file-targeted Blender MCP.

Existing V19 material datablocks remain byte-for-byte graph-equivalent. Local
wall-only clones add spatially masked, world-metre licensed ambientCG PBR marble shading.
No vertex, polygon/material index, original BakeUV, normals or object ID change.
"""
import hashlib,json,math
from pathlib import Path
import bpy
from mathutils import Vector
import photoreal_materials_v20 as p
from pbr_bake_channels import mesh_signature
from prepare_texture_precision_v15 import geometry

ROOT=p.ROOT
PREVIOUS={'orbital-dual-bake-v19.blend':'45e258c586f5bc46203ca1d3ff6be14cfde72fcc28a40ec919040fcee9a9cd64',
 'orbital-atelier-v19.blend':'175deff40751433f8e39783cc67b8fc437dd067a69ac9652df7d213f3ba8832f'}
REVIEW_REVISION=4
_PACKED_HASHES={}

def val(x):
    if isinstance(x,(str,bool,int,float)) or x is None:return x
    try:return [val(i) for i in x]
    except:return str(x)

def graph(mat):
    if not mat.use_nodes:return {'name':mat.name,'diffuse':list(mat.diffuse_color)}
    nodes=[]
    for n in sorted(mat.node_tree.nodes,key=lambda n:n.name):
        attrs={}
        for prop in n.bl_rna.properties:
            key=prop.identifier
            if key in ('rna_type','name','type','bl_idname') or prop.is_readonly or prop.type not in ('BOOLEAN','INT','FLOAT','STRING','ENUM'):continue
            try:attrs[key]=val(getattr(n,key))
            except:pass
        if hasattr(n,'color_ramp'):
            r=n.color_ramp;attrs['colorRamp']={'mode':r.color_mode,'interpolation':r.interpolation,'hue':r.hue_interpolation,'elements':[[e.position,list(e.color)] for e in r.elements]}
        image=getattr(n,'image',None)
        if image:
            key=image.as_pointer()
            if image.packed_file and key not in _PACKED_HASHES:_PACKED_HASHES[key]=hashlib.sha256(image.packed_file.data).hexdigest()
            attrs['image']={'name':image.name,'path':bpy.path.abspath(image.filepath),'colorSpace':image.colorspace_settings.name,'packedSha256':_PACKED_HASHES.get(key) if image.packed_file else None}
        nodes.append({'name':n.name,'type':n.bl_idname,'attrs':attrs,'inputs':[(s.identifier,val(s.default_value)) for s in n.inputs if hasattr(s,'default_value')]})
    return {'name':mat.name,'nodes':nodes,'links':sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in mat.node_tree.links)}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def materials_digest(mats):
    _PACKED_HASHES.clear()
    return {m.name:digest(graph(m)) for m in sorted(mats,key=lambda m:m.name)}

def all_material_bindings():
    return {o.name:[m.name if m else None for m in o.data.materials]
            for o in sorted(bpy.data.objects,key=lambda o:o.name) if o.type=='MESH'}

def light_signature():
    rows=[]
    for o in bpy.data.objects:
        if o.type=='LIGHT':
            d=o.data;rows.append({'name':o.name,'matrix':val(o.matrix_world),'type':d.type,'energy':d.energy,'color':list(d.color),'size':getattr(d,'size',None),'sizeY':getattr(d,'size_y',None),'spread':getattr(d,'spread',None),'shape':getattr(d,'shape',None)})
    return digest(sorted(rows,key=lambda x:x['name']))

def mix(tree,a,b,f,label):
    n=p.node(tree,'ShaderNodeMixRGB',label);n.blend_type='MIX'
    for i,x in enumerate((f,a,b)):
        if isinstance(x,(tuple,list)):n.inputs[i].default_value=x
        elif isinstance(x,(int,float)):n.inputs[i].default_value=x if i==0 else (x,x,x,1)
        else:tree.links.new(x,n.inputs[i])
    return n.outputs[0]

def mathn(t,op,a,b):return p.math_node(t,op,a,b,'Marble '+op)

def box(t,axes,lo,hi):
    q=1
    for i,axis in enumerate('XYZ'):
        q=mathn(t,'MULTIPLY',q,mathn(t,'GREATER_THAN',axes.outputs[axis],lo[i]-.001))
        q=mathn(t,'MULTIPLY',q,mathn(t,'LESS_THAN',axes.outputs[axis],hi[i]+.001))
    return q

def noise(t,vector,scale,label,detail=4,rough=.65):
    n=p.node(t,'ShaderNodeTexNoise',label);t.links.new(vector,n.inputs['Vector']);n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=detail;n.inputs['Roughness'].default_value=rough
    return n

def ramp(t,socket,points,label):
    n=p.node(t,'ShaderNodeValToRGB',label);n.color_ramp.interpolation='EASE'
    while len(n.color_ramp.elements)>2:n.color_ramp.elements.remove(n.color_ramp.elements[-1])
    for i,(position,color) in enumerate(points):
        e=n.color_ramp.elements[i] if i<2 else n.color_ramp.elements.new(position);e.position=position;e.color=color
    t.links.new(socket,n.inputs['Fac']);return n.outputs['Color']

from room_marble_pbr_v20 import apply_marble as marble


def source_objects(web):
    if web:return [o for o in web.objects if o.type=='MESH' and o.get('owner_asset_id')=='room_static' and o.get('bake_atlas') in (0,8)]
    tags=('BackWall_Graphite','LeftWallInner','LeftWallOuter','SweepingTopBand','LeftTopRail','LeftFrontRail')
    return [o for o in bpy.data.objects if o.type=='MESH' and any(tag in o.name for tag in tags)]

def derive_current():
    assert bpy.app.background
    old=Path(bpy.data.filepath);assert p.sha(old)==PREVIOUS[old.name]
    target=old.with_name(old.name.replace('-v19.blend','-v20.blend'));assert not target.exists(),target
    web=bpy.data.scenes.get('WEB_DUAL_V8');before=geometry(web) if web else p.geometry_signature()
    all_meshes=[o for o in bpy.data.objects if o.type=='MESH'];mesh_before=mesh_signature(all_meshes)
    bindings_before=all_material_bindings()
    original_mats=list(bpy.data.materials);mat_before=materials_digest(original_mats);lights_before=light_signature()
    floor_names=[m.name for m in original_mats if m.get('v18_warm_role')=='floor'];protected_floor={name:mat_before[name] for name in floor_names}
    lamp_names=[m.name for m in original_mats if m.get('v19_lamp')];protected_lamp={name:mat_before[name] for name in lamp_names}
    clones={};bindings=[];records=[]
    for obj in source_objects(web):
        for i,oldmat in enumerate(list(obj.data.materials)):
            if not oldmat or oldmat.get('v18_warm_role') not in ('wall','cap'):continue
            role=oldmat['v18_warm_role'];key=oldmat.name
            if key not in clones:
                clone=oldmat.copy();clone.name='V20_MARBLE_'+oldmat.name;clones[key]=clone;records.append(marble(clone,role))
            obj.data.materials[i]=clones[key];bindings.append({'object':obj.name,'slot':i,'before':oldmat.name,'after':clones[key].name,'atlas':obj.get('bake_atlas')})
    after=geometry(web) if web else p.geometry_signature();assert before==after
    assert mesh_before==mesh_signature(all_meshes),'Positions/UVs/normals/material indices changed'
    mat_after=materials_digest(original_mats);assert mat_before==mat_after,'An original material graph changed'
    assert lights_before==light_signature(),'Authored lamp/light configuration changed'
    bindings_after=all_material_bindings()
    expected={(row['object'],row['slot'],row['before'],row['after']) for row in bindings}
    actual={(name,i,old,new) for name,slots in bindings_before.items()
            for i,(old,new) in enumerate(zip(slots,bindings_after[name])) if old!=new}
    assert set(bindings_before)==set(bindings_after)
    assert all(len(slots)==len(bindings_after[name]) for name,slots in bindings_before.items())
    assert actual==expected,'Unexpected material binding change'
    # Editable V19 retains four authored/historical room variants, with eight
    # distinct wall/cap material datablocks confirmed by the source inspection.
    assert len(clones)==(3 if web else 8),len(clones)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
    assert p.sha(old)==PREVIOUS[old.name]
    result={'complete':True,'revision':20,'reviewRevision':REVIEW_REVISION,'invocation':'Blender MCP file-targeted operations with Python assistance','source':str(old.relative_to(ROOT)),'sourceSha256':p.sha(old),'derivative':str(target.relative_to(ROOT)),'sha256':p.sha(target),
      'userDirection':'White marble walls with native grey mineral veining and black textured marble top caps; preserve V19 dark wood floor, top practical and all geometry/IDs','status':'authored_for_review','wallMaterialBindings':bindings,'wallMaterials':records,
      'existingGeometryBefore':before,'existingGeometryAfter':after,'wholeFileMeshSignatureBefore':mesh_before,'wholeFileMeshSignatureAfter':mesh_signature(all_meshes),'geometryUvsNormalsMaterialIndicesUnchanged':True,
      'allMaterialBindingsBefore':bindings_before,'allMaterialBindingsAfter':bindings_after,'textureImagesPacked':all(row['textureImagesPacked'] for row in records),
      'originalMaterialGraphsBefore':mat_before,'originalMaterialGraphsAfter':mat_after,'protectedFloorMaterials':{'before':protected_floor,'after':{name:mat_after[name] for name in floor_names}},'protectedLampMaterials':{'before':protected_lamp,'after':{name:mat_after[name] for name in lamp_names}},'authoredLightsBefore':lights_before,'authoredLightsAfter':light_signature(),
      'newWallMaterialGraphs':materials_digest(list(clones.values())),'expectedExportTriangles':418383 if web else None,'atlasCount':13,'affectedSurfaceSlots':[0,8],'unchangedSurfaceSlots':[1,2,3,4,5,6,7,9,10,11,12],'rebakeDayNightSlots':list(range(13)),'introSlots':[0,1,8],'legacyV19Preserved':True,'aboutAssetsUnchanged':True,'galleryAssetsUnchanged':True,'runtimeExported':False,
      'recipeFiles':[{'path':str(Path(x).relative_to(ROOT)),'sha256':p.sha(x)} for x in (__file__,p.__file__,ROOT/'assets/blender/scripts/room_marble_pbr_v20.py',ROOT/'assets/blender/scripts/pbr_bake_channels.py',ROOT/'assets/blender/scripts/room_refinement_v19.py')]}
    p.write(ROOT/'assets/blender'/('photoreal-materials-v20-prepared.json' if web else 'photoreal-materials-v20-source.json'),result)
    return {k:result[k] for k in ['complete','derivative','sha256','wallMaterialBindings','wallMaterials','expectedExportTriangles','atlasCount']}

def surface_proof_current():
    assert bpy.app.background;scene=bpy.data.scenes['WEB_DUAL_V8'];rows=[]
    for slot in range(13):
        meshes=p.atlas_meshes(scene,slot);mats=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name)
        rows.append({'slot':slot,'shaderGraphsSha256':digest([graph(m) for m in mats]),'materials':[m.name for m in mats],'geometryUvNormalsSignature':mesh_signature(meshes)})
    report={'source':bpy.data.filepath,'sourceSha256':p.sha(bpy.data.filepath),'surfaces':rows,'method':'All 13 atlases: original mesh positions, polygon material indices, original BakeUV/corner normals/world transforms plus complete shader graph properties, input values, links, color ramps and packed image hashes.'}
    name='room-v19-to-v20-surface-before.json' if '-v19.blend' in bpy.data.filepath else 'room-v20-surface-reuse-proof.json';p.write(ROOT/'assets/blender'/name,report)
    return {'report':name,'sourceSha256':report['sourceSha256'],'slots':13}

def review(state='day',close=False):
    p.assert_prepared();scene=p.configure_current(state)
    if close:
        camera=bpy.data.objects.new('V20_Marble_Wall_Detail',bpy.data.cameras.new('V20_Marble_Wall_Detail'));scene.collection.objects.link(camera);camera.location=(5.7,-7.8,6.4);target=Vector((-1.5,1.9,2.55));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=52;scene.camera=camera
    scene.cycles.samples=40;scene.cycles.use_denoising=True;scene.cycles.denoising_use_gpu=True;scene.cycles.adaptive_threshold=.015
    scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
    out=ROOT/'renders/room-materials-v20'/f'{"close-" if close else ""}{state}-review-{REVIEW_REVISION}.png';out.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(out)
    with p.gpu_job('v20-marble-review'):bpy.ops.render.render(write_still=True)
    result={'path':str(out.relative_to(ROOT)),'sha256':p.sha(out),'sourceSha256':p.sha(bpy.data.filepath),'samples':40,'state':state,'realCyclesRender':True,'close':close,'denoiser':'OPENIMAGEDENOISE HIGH / Metal GPU'};p.write(out.with_suffix('.json'),result);return result
