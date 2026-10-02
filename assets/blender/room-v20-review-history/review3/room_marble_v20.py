"""V20 white marble WALLS only; author and inspect via file-targeted Blender MCP.

Existing V19 material datablocks remain byte-for-byte graph-equivalent. Local
wall-only clones add spatially masked, world-metre procedural marble shading.
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
REVIEW_REVISION=3

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
        if image:attrs['image']={'name':image.name,'path':bpy.path.abspath(image.filepath),'colorSpace':image.colorspace_settings.name,'packedSha256':hashlib.sha256(image.packed_file.data).hexdigest() if image.packed_file else None}
        nodes.append({'name':n.name,'type':n.bl_idname,'attrs':attrs,'inputs':[(s.identifier,val(s.default_value)) for s in n.inputs if hasattr(s,'default_value')]})
    return {'name':mat.name,'nodes':nodes,'links':sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in mat.node_tree.links)}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def materials_digest(mats):return {m.name:digest(graph(m)) for m in sorted(mats,key=lambda m:m.name)}

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

def marble(mat,role):
    t=mat.node_tree;bs=p.principled(mat);geo=p.node(t,'ShaderNodeNewGeometry','V20 continuous world-metre stone')
    axes=p.node(t,'ShaderNodeSeparateXYZ','V20 wall mask world axes');t.links.new(geo.outputs['Position'],axes.inputs[0])
    if role=='wall':
        mask=mathn(t,'MAXIMUM',box(t,axes,(-4.961,3.309,.179),(4.961,3.741,5.131)),box(t,axes,(-5.311,-2.451,.179),(-4.929,3.741,4.617)))
    else:
        mask=mathn(t,'MAXIMUM',box(t,axes,(-4.918,3.118,4.463),(4.923,3.782,5.215)),box(t,axes,(-5.352,-2.551,3.746),(-4.758,3.780,4.717)))
    # Folded continuous density isosurfaces produce flowing mineral veins.
    # There is no Voronoi/cellular network and no periodic wave/stripe field.
    flow=p.node(t,'ShaderNodeCombineXYZ','V20 diagonal geological flow axes')
    x=mathn(t,'ADD',mathn(t,'MULTIPLY',axes.outputs['X'],.8),mathn(t,'MULTIPLY',axes.outputs['Z'],.45))
    y=mathn(t,'ADD',mathn(t,'MULTIPLY',axes.outputs['Y'],.8),mathn(t,'MULTIPLY',axes.outputs['Z'],.35))
    z=mathn(t,'ADD',mathn(t,'MULTIPLY',axes.outputs['Z'],.55),mathn(t,'ADD',mathn(t,'MULTIPLY',axes.outputs['X'],-.22),mathn(t,'MULTIPLY',axes.outputs['Y'],.20)))
    for socket,value in zip(flow.inputs,(x,y,z)):t.links.new(value,socket)
    warp=noise(t,flow.outputs[0],.57,'V20 gentle geological domain folding',2.5,.56)
    warp_scale=p.node(t,'ShaderNodeVectorMath','V20 metre-scale irregular drift');warp_scale.operation='SCALE';warp_scale.inputs['Scale'].default_value=.75;t.links.new(warp.outputs['Color'],warp_scale.inputs[0])
    folded=p.node(t,'ShaderNodeVectorMath','V20 stone folded coordinates');folded.operation='ADD';t.links.new(flow.outputs[0],folded.inputs[0]);t.links.new(warp_scale.outputs[0],folded.inputs[1])
    mineral=noise(t,folded.outputs[0],.53,'V20 continuous slow mineral density',5.5,.68)
    erosion=noise(t,folded.outputs[0],8.2,'V20 crystal-scale vein edge erosion',3,.68)
    perturbation=mathn(t,'MULTIPLY',mathn(t,'SUBTRACT',erosion.outputs['Fac'],.5),.020)
    distance=mathn(t,'ABSOLUTE',mathn(t,'ADD',mathn(t,'SUBTRACT',mineral.outputs['Fac'],.493),perturbation),0)
    vein=ramp(t,distance,[(0,(1,1,1,1)),(.0015,(.90,.90,.90,1)),(.006,(.48,.48,.48,1)),(.014,(.11,.11,.11,1)),(.025,(0,0,0,1))],'V20 dark flowing core to smoky grey shoulder')
    clouds=noise(t,geo.outputs['Position'],.31,'V20 varied mineral density',2,.56)
    gate=ramp(t,clouds.outputs['Fac'],[(.30,(.15,.15,.15,1)),(.42,(.38,.38,.38,1)),(.56,(1,1,1,1))],'V20 interrupted organic vein coverage')
    secondary_noise=noise(t,folded.outputs[0],1.63,'V20 local branching density',2,.54)
    secondary_distance=mathn(t,'ABSOLUTE',mathn(t,'SUBTRACT',secondary_noise.outputs['Fac'],.52),0)
    fine=ramp(t,secondary_distance,[(0,(.47,.47,.47,1)),(.004,(.36,.36,.36,1)),(.014,(0,0,0,1))],'V20 narrow subordinate branches')
    proximity=ramp(t,distance,[(.020,(1,1,1,1)),(.060,(0,0,0,1))],'V20 branches only near primary mineral veins')
    primary=mathn(t,'MULTIPLY',vein,gate);secondary=mathn(t,'MULTIPLY',fine,mathn(t,'MULTIPLY',proximity,gate));amount=mathn(t,'MAXIMUM',primary,secondary)
    chalk=noise(t,geo.outputs['Position'],1.9,'V20 soft ivory crystalline clouds',4,.56)
    white=mix(t,(.64,.655,.65,1),(.79,.80,.785,1),chalk.outputs['Fac'],'V20 off-white mineral body')
    grey=mix(t,(.065,.075,.082,1),(.16,.17,.173,1),clouds.outputs['Fac'],'V20 natural charcoal-grey seam variation')
    color=mix(t,white,grey,amount,'V20 legible grey veining in white stone')
    pores=noise(t,geo.outputs['Position'],420,'V20 polished stone microstructure',2,.55)
    rough=p.remap(t,pores.outputs['Fac'],.27,.38,'V20 satin honed marble roughness')
    bump=p.node(t,'ShaderNodeBump','V20 subtle real-scale mineral relief');bump.inputs['Distance'].default_value=.00010;bump.inputs['Strength'].default_value=.16;t.links.new(pores.outputs['Fac'],bump.inputs['Height'])
    for name,value in [('Base Color',color),('Roughness',rough),('Normal',bump.outputs['Normal']),('Metallic',0),('Coat Weight',0),('IOR',1.52),('Specular IOR Level',.42)]:
        inp=bs.inputs[name];old=inp.links[0].from_socket if inp.is_linked else tuple(inp.default_value) if name in ('Base Color','Normal') else inp.default_value
        if name=='Normal' and not inp.is_linked:old=geo.outputs['Normal']
        for link in list(inp.links):t.links.remove(link)
        t.links.new(mix(t,old,value,mask,'V20 wall-only '+name),inp)
    mat['material_revision']=20;mat['v20_role']='procedural_white_marble_'+role
    return {'name':mat.name,'role':role,'baseBodyLinear':[.64,.80],'veinLinear':[.065,.173],'macroVeinScalePerMetre':.53,'secondaryScalePerMetre':1.63,'veinMethod':'Domain-folded continuous mineral density isosurface; diagonal flow; sparse branches restricted near main veins; no Voronoi or periodic bands','roughness':[.27,.38],'ior':1.52,'specularIORLevel':.42,'normalReliefMetres':.00010,'geometryDisplacement':False,'license':'Project-authored native Blender procedural material; no external imagery'}

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
    # Editable V19 retains four authored/historical room variants, with eight
    # distinct wall/cap material datablocks confirmed by the source inspection.
    assert len(clones)==(3 if web else 8),len(clones)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
    assert p.sha(old)==PREVIOUS[old.name]
    result={'complete':True,'revision':20,'reviewRevision':REVIEW_REVISION,'invocation':'Blender MCP file-targeted operations with Python assistance','source':str(old.relative_to(ROOT)),'sourceSha256':p.sha(old),'derivative':str(target.relative_to(ROOT)),'sha256':p.sha(target),
      'userDirection':'White marble room walls with prominent natural grey veining; preserve V19 dark wood floor, top practical and all geometry/IDs','status':'authored_for_review','wallMaterialBindings':bindings,'wallMaterials':records,
      'existingGeometryBefore':before,'existingGeometryAfter':after,'wholeFileMeshSignatureBefore':mesh_before,'wholeFileMeshSignatureAfter':mesh_signature(all_meshes),'geometryUvsNormalsMaterialIndicesUnchanged':True,
      'originalMaterialGraphsBefore':mat_before,'originalMaterialGraphsAfter':mat_after,'protectedFloorMaterials':{'before':protected_floor,'after':{name:mat_after[name] for name in floor_names}},'protectedLampMaterials':{'before':protected_lamp,'after':{name:mat_after[name] for name in lamp_names}},'authoredLightsBefore':lights_before,'authoredLightsAfter':light_signature(),
      'newWallMaterialGraphs':materials_digest(list(clones.values())),'expectedExportTriangles':418383 if web else None,'atlasCount':13,'affectedSurfaceSlots':[0,8],'unchangedSurfaceSlots':[1,2,3,4,5,6,7,9,10,11,12],'rebakeDayNightSlots':list(range(13)),'introSlots':[0,1,8],'legacyV19Preserved':True,'aboutAssetsUnchanged':True,'galleryAssetsUnchanged':True,'runtimeExported':False,
      'recipeFiles':[{'path':str(Path(x).relative_to(ROOT)),'sha256':p.sha(x)} for x in (__file__,p.__file__,ROOT/'assets/blender/scripts/pbr_bake_channels.py',ROOT/'assets/blender/scripts/room_refinement_v19.py')]}
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
