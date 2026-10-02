"""Authorized V19 timber/ceiling-practical refinement, file-targeted Blender MCP.

Never touches the foreground file or V18 sources. Geometry is edited only in
the derivative: nine obsolete floor-grid tubes removed, one separate lamp added.
"""
import array, hashlib, json, math, re, sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
import photoreal_materials_v19 as p
from pbr_bake_channels import mesh_signature
from prepare_texture_precision_v15 import geometry

ROOT=p.ROOT
SOURCE_HASHES={
 'orbital-atelier-v18.blend':'be32f059cce1727251da6c43d55cb022174e0dc6d39451e1ae8cac060905e632',
 'orbital-dual-bake-v18.blend':'80fbfa84eb4cc2cf8beea3a4a44e5978823de49ac6227cfa1549a61dd776ab79',
}
LAMP_ID='lighting.ceiling_warm'
WARM=(1.0,.475,.17)
LAMP_POWER=95.0

def floor_components(obj):
    mesh=obj.data;adj=[[] for _ in mesh.vertices]
    for edge in mesh.edges:
        a,b=edge.vertices;adj[a].append(b);adj[b].append(a)
    seen=set();parts=[]
    for v in mesh.vertices:
        if v.index in seen:continue
        stack=[v.index];seen.add(v.index);ids=[]
        while stack:
            i=stack.pop();ids.append(i)
            for j in adj[i]:
                if j not in seen:seen.add(j);stack.append(j)
        points=[obj.matrix_world@mesh.vertices[i].co for i in ids]
        lo=[min(x[k] for x in points) for k in range(3)];hi=[max(x[k] for x in points) for k in range(3)]
        if lo[2]>.182 and hi[2]<.188 and len(ids)==20:
            faces=[f for f in mesh.polygons if f.vertices[0] in ids]
            mats={mesh.materials[f.material_index].name for f in faces}
            if len(faces)==10 and all('MAT_Graphite_Enamel' in n for n in mats):parts.append({'indices':ids,'bounds':[lo,hi],'faces':10})
    return parts

def remove_grid_from_proxy(obj):
    parts=floor_components(obj);assert len(parts)==9
    mesh=obj.data.copy();obj.data=mesh
    old_norm=[tuple(n.vector) for n in mesh.corner_normals]
    old_uv={u.name:[tuple(v.uv) for v in u.data] for u in mesh.uv_layers}
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
    tag=bm.loops.layers.int.new('v19_original_corner')
    for face in bm.faces:
        for loop,idx in zip(face.loops,mesh.polygons[face.index].loop_indices):loop[tag]=idx
    ids={i for part in parts for i in part['indices']}
    bmesh.ops.delete(bm,geom=[bm.verts[i] for i in sorted(ids)],context='VERTS')
    bm.to_mesh(mesh);bm.free();mesh.update()
    mapping=[x.value for x in mesh.attributes['v19_original_corner'].data]
    for name,values in old_uv.items():assert all(tuple(mesh.uv_layers[name].data[i].uv)==values[j] for i,j in enumerate(mapping))
    error=max(abs(mesh.corner_normals[i].vector[k]-old_norm[j][k]) for i,j in enumerate(mapping) for k in range(3))
    if error>2e-5:
        mesh.normals_split_custom_set([old_norm[j] for j in mapping])
        error=max(abs(mesh.corner_normals[i].vector[k]-old_norm[j][k]) for i,j in enumerate(mapping) for k in range(3))
    assert error<.0005,error
    mesh.attributes.remove(mesh.attributes['v19_original_corner'])
    return {'object':obj.name,'removedComponents':9,'removedVertices':180,'removedPolygons':90,'removedTriangles':180,'remainingUvsExactlyPreserved':True,'remainingCornerNormalMaxError':error,'components':[{k:v for k,v in q.items() if k!='indices'} for q in parts]}

def enhance_floor(mat):
    """Wider scan footprint and centred contrast retain the approved deep oil tint."""
    tree=mat.node_tree
    gamma=next(n for n in tree.nodes if n.label=='About raw walnut gamma')
    sampled=gamma.inputs[0].links[0].from_socket
    gray=p.node(tree,'ShaderNodeRGBToBW','V19 scanned grain luminance');tree.links.new(sampled,gray.inputs[0])
    density=p.node(tree,'ShaderNodeMapRange','V19 visible natural grain');density.clamp=True
    density.inputs['From Min'].default_value=.125;density.inputs['From Max'].default_value=.195
    density.inputs['To Min'].default_value=.54;density.inputs['To Max'].default_value=1.44
    tree.links.new(gray.outputs[0],density.inputs['Value'])
    dye=next(n for n in tree.nodes if n.label=='Warm transparent wood oil')
    consumers=list(dye.outputs[0].links)
    mul=p.node(tree,'ShaderNodeMixRGB','V19 grain contrast without pale colour');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1
    tree.links.new(dye.outputs[0],mul.inputs[1]);tree.links.new(density.outputs['Result'],mul.inputs[2])
    for link in consumers:
        target=link.to_socket;tree.links.remove(link);tree.links.new(mul.outputs[0],target)
    changed=[]
    for n in tree.nodes:
        if n.type=='VECT_MATH' and n.operation=='MULTIPLY' and 'walnut_veneer' in n.label and n.label.endswith(' metres'):
            n.inputs[1].default_value=(1/2.65,)*3;changed.append(n.name)
        elif n.type=='BUMP' and n.label=='Walnut pores in metres':n.inputs['Distance'].default_value=.0007;n.inputs['Strength'].default_value=.55
    rough=next(n for n in tree.nodes if n.label=='Smoked raw walnut matte roughness')
    rough.inputs['To Min'].default_value=.41;rough.inputs['To Max'].default_value=.66
    assert tuple(dye.inputs[2].default_value)[:3]==tuple(float(x) for x in array.array('f',[.18,.12,.075]))
    mat['material_revision']=19;mat['v19_change']='scan footprint 2.65m; centred grain contrast; deep V18 oil tint retained'
    return {'name':mat.name,'oilTint':list(dye.inputs[2].default_value),'scanFootprintM':2.65,'contrastInput':[.125,.195],'contrastGain':[.54,1.44],'roughness':[.41,.66],'bumpDistance':.0007,'geometryDisplacement':False,'scanNodes':changed}

def material(name,color,metal=0,rough=.4,emission=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;bs=p.principled(m)
    bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
    bs.inputs['Emission Color'].default_value=(*WARM,1);bs.inputs['Emission Strength'].default_value=emission
    m['v19_lamp']=True;m['v19_role']='emitter' if emission else 'brushed_titanium' if metal else 'powdercoat'
    return m

def part(scene,root,name,loc,dim,mat,radius=.015):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=o.modifiers.new('Machined edge radii','BEVEL');bevel.width=radius;bevel.segments=5
    bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=bevel.name)
    for f in o.data.polygons:f.use_smooth=True
    normal=o.modifiers.new('Face-weighted hard surface normals','WEIGHTED_NORMAL');normal.keep_sharp=True;normal.weight=60
    bpy.ops.object.modifier_apply(modifier=normal.name)
    o.data.materials.append(mat);matrix=o.matrix_world.copy();o.parent=root;o.matrix_world=matrix
    o['v19_lamp_part']=True
    return o

def add_lamp(scene,prepared=False):
    bpy.context.window.scene=scene
    root=bpy.data.objects.new(('WEB19_' if prepared else 'V19_')+'CEILING_WARM_Root',None);scene.collection.objects.link(root)
    root.location=(0,3.08,4.43);root['asset_id']=LAMP_ID;root['display_name']='暖光顶灯';root['interaction']='ambient_fixture';root['v19_ceiling_fixture']=True
    if prepared:root['web_export']=True
    graphite=material('V19_Ceiling_Anodized_Graphite',(.035,.045,.052),.72,.33)
    brass=material('V19_Ceiling_Brushed_Champagne',(.32,.19,.09),.86,.29)
    diffuser=material('V19_Ceiling_Opal_Diffuser',(.61,.53,.39),0,.36,1.3)
    parts=[]
    def box(name,loc,dim,mat,rad=.012):
        o=part(scene,root,'V19_Ceiling_'+name,loc,dim,mat,rad);parts.append(o);return o
    box('Housing',(0,3.00,4.44),(1.72,.28,.145),graphite,.06)
    box('Top_Inlay',(0,3.00,4.507),(1.56,.22,.018),brass,.008)
    box('Recessed_Diffuser',(0,2.99,4.36),(1.54,.205,.029),diffuser,.013)
    for side in [-1,1]:
        box('Endcap_'+str(side),(side*.818,3.00,4.44),(.065,.235,.109),brass,.018)
        box('Wall_Bracket_'+str(side),(side*.59,3.20,4.46),(.052,.31,.071),graphite,.018)
        box('Mount_Plate_'+str(side),(side*.59,3.345,4.46),(.13,.03,.15),brass,.014)
    if prepared:
        bpy.ops.object.select_all(action='DESELECT')
        for o in parts:o.select_set(True)
        active=parts[0];bpy.context.view_layer.objects.active=active;bpy.ops.object.join();active.name='WEB19_lighting.ceiling_warm__baked__A12'
        active['web_export']=True;active['web_kind']='baked';active['bake_atlas']=12;active['owner_asset_id']=LAMP_ID
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(65),island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
        active.data.uv_layers.active.name='BakeUV'
        im=bpy.data.images.new('WEB19_LAMP_BAKE_TARGET',width=1024,height=1024,alpha=True)
        for m in active.data.materials:
            n=m.node_tree.nodes.new('ShaderNodeTexImage');n.name='WEB8_BAKE_TARGET';n.image=im;m.node_tree.nodes.active=n
        parts=[active]
    return {'assetId':LAMP_ID,'root':root.name,'parts':[o.name for o in parts],'location':list(root.location),'atlas':12 if prepared else None,'fixture':'Compact softly bevelled graphite bar with champagne endcaps, recessed opal diffuser, two wall-attached brackets','size':[1.72,.28,.145],'colorTemperatureK':3000,'nightWatts':LAMP_POWER,'dayWatts':0}

def configure_ceiling_light(scene,state):
    """Apply after existing lighting setup; actual night GI is baked on receivers."""
    for o in list(scene.objects):
        if o.type=='LIGHT' and o.get('v19_ceiling_light'):bpy.data.objects.remove(o,do_unlink=True)
    for o in scene.objects:
        if o.type!='MESH' or not o.get('v19_lamp_part'):continue
        for m in o.data.materials:
            if m and 'V19_Ceiling_Opal_Diffuser' in m.name:p.principled(m).inputs['Emission Strength'].default_value=1.3 if state=='night' else 0
    data=bpy.data.lights.new('V19_CEILING_WARM_3000K','AREA');data.shape='RECTANGLE';data.size=1.48;data.size_y=.18;data.spread=math.radians(112);data.energy=LAMP_POWER if state=='night' else 0;data.color=WARM
    o=bpy.data.objects.new(data.name,data);scene.collection.objects.link(o);o.location=(0,2.99,4.338)
    o.rotation_euler=(Vector((0,.10,.35))-o.location).to_track_quat('-Z','Y').to_euler();o['v19_ceiling_light']=True;o['v8_generated_light']=True
    return {'state':state,'watts':data.energy,'temperatureK':3000,'position':list(o.location),'target':[0,.1,.35],'fixtureAssetId':LAMP_ID,'realLightAffectsDiffuseBake':True}

def derive_current():
    assert bpy.app.background
    old=Path(bpy.data.filepath);assert p.sha(old)==SOURCE_HASHES[old.name]
    target=old.with_name(old.name.replace('-v18.blend','-v19.blend'));assert not target.exists()
    web=bpy.data.scenes.get('WEB_DUAL_V8');before=geometry(web) if web else None
    removed=[]
    if web:removed.append(remove_grid_from_proxy(bpy.data.objects['WEB8_room_static__baked__A0']))
    curves=[o for o in bpy.data.objects if 'A_FloorJoint' in o.name and o.type=='CURVE' and abs(o.data.bevel_depth-.003)<1e-7]
    curve_names=[o.name for o in curves]
    for o in curves:bpy.data.objects.remove(o,do_unlink=True)
    mats=p.relevant_materials();floor=[m for m in mats.values() if p.canonical(m.name)=='MAT_Titanium_Floor'];assert len(floor)==(2 if web else 3)
    finishes=[enhance_floor(m) for m in floor]
    lamps=[]
    if web:lamps.append(add_lamp(web,True))
    else:
        for name in ['ORBITAL_ATELIER_V2','ORIGINAL_DAY_V13','ORIGINAL_NIGHT_V13']:
            if name in bpy.data.scenes:
                scene=bpy.data.scenes[name];lamps.append(add_lamp(scene));configure_ceiling_light(scene,'night' if 'NIGHT' in name else 'day')
    after=geometry(web) if web else None
    if web:
        changed=[n for n in before if after[n]!=before[n]];assert changed==['WEB8_room_static__baked__A0'],changed
        assert len([o for o in web.objects if o.get('web_export') and o.get('asset_id')])==96
        triangles=sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in web.objects if o.type=='MESH' and o.get('web_export'))
    else:changed=[];triangles=None
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
    assert p.sha(old)==SOURCE_HASHES[old.name]
    result={'complete':True,'revision':19,'invocation':'Blender MCP file-targeted scene operations with Python assistance','source':str(old.relative_to(ROOT)),'sourceSha256':p.sha(old),'derivative':str(target.relative_to(ROOT)),'sha256':p.sha(target),'userDirection':'Remove black floor lines, make dark natural timber grain clearer, add one top warm night practical','removedFloorGrid':removed,'removedSourceCurves':curve_names,'floorMaterials':finishes,'lamps':lamps,'changedExistingExportObjects':changed,'allOtherExistingExportGeometryUnchanged':True if web else None,'existingGeometryBefore':before,'existingGeometryAfter':after,'expectedExportTriangles':triangles,'atlasCount':13,'affectedSurfaceSlots':[0,8,12],'unchangedSurfaceSlots':[1,2,3,4,5,6,7,9,10,11],'rebakeDayNightSlots':list(range(13)),'introSlots':[0,1,8],'runtimeExported':False,'aboutAssetsUnchanged':True}
    p.write(ROOT/'assets/blender'/('photoreal-materials-v19-prepared.json' if web else 'photoreal-materials-v19-source.json'),result)
    return {k:result[k] for k in ['complete','derivative','sha256','removedFloorGrid','floorMaterials','lamps','changedExistingExportObjects','expectedExportTriangles','atlasCount']}

def review(state='day',close=False):
    p.assert_prepared();scene=p.configure_current(state)
    if close:
        camera=bpy.data.objects.new('V19_Floor_Review',bpy.data.cameras.new('V19_Floor_Review'));scene.collection.objects.link(camera)
        camera.location=(7.6,-10,7.2);target=Vector((0,-.3,1.6));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=55;scene.camera=camera
    scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.025
    scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
    filename=('close-' if close else '')+state+'-review-1.png';out=ROOT/'renders/room-materials-v19'/filename;out.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(out)
    with p.gpu_job('v19-review-'+state):bpy.ops.render.render(write_still=True)
    result={'path':str(out.relative_to(ROOT)),'sha256':p.sha(out),'sourceSha256':p.sha(bpy.data.filepath),'samples':32,'state':state,'realCyclesRender':True,'nightWatts':LAMP_POWER}
    p.write(out.with_suffix('.json'),result);return result


def unchanged_surface_proof():
    """Read-only node and geometry fingerprints for safe V17 data-map reuse."""
    import hashlib
    assert bpy.app.background
    from pbr_bake_channels import mesh_signature
    scene=bpy.data.scenes['WEB_DUAL_V8'];rows=[]
    def value(v):
        if isinstance(v,(str,bool,int,float)) or v is None:return v
        try:return [float(x) for x in v]
        except:return str(v)
    for slot in range(12):
        if slot in (0,8):continue
        meshes=p.atlas_meshes(scene,slot);mats=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name)
        graphs=[]
        for m in mats:
            nodes=[]
            for n in sorted(m.node_tree.nodes,key=lambda n:n.name):
                attrs={k:value(getattr(n,k)) for k in ('operation','blend_type','projection','extension','interpolation','clamp','use_clamp','vector_type','convert_from','convert_to','noise_dimensions','normalize') if hasattr(n,k)}
                img=getattr(n,'image',None)
                if img:
                    attrs['image']={'name':img.name,'path':bpy.path.abspath(img.filepath),'colorSpace':img.colorspace_settings.name}
                nodes.append({'name':n.name,'type':n.bl_idname,'inputs':[(s.identifier,value(s.default_value)) for s in n.inputs if hasattr(s,'default_value')],'attrs':attrs})
            links=sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in m.node_tree.links)
            graphs.append({'name':m.name,'nodes':nodes,'links':links})
        digest=hashlib.sha256(json.dumps(graphs,sort_keys=True).encode()).hexdigest()
        rows.append({'slot':slot,'shaderGraphsSha256':digest,'materials':[m.name for m in mats],'geometryUvNormalsSignature':mesh_signature(meshes)})
    result={'source':bpy.data.filepath,'sourceSha256':p.sha(bpy.data.filepath),'surfaces':rows,'method':'Full node types/properties/input values/links, image names/paths/color spaces plus mesh positions/UVs/normals/world transforms; no lighting dependency for F0/roughness/tangent normal.'}
    version='v19' if '-v19.blend' in bpy.data.filepath else 'v18'
    p.write(p.ROOT/'assets/blender'/f'room-{version}-surface-reuse-proof.json',result)
    return {'path':f'assets/blender/room-{version}-surface-reuse-proof.json','sourceSha256':result['sourceSha256'],'slots':[r['slot'] for r in rows]}
