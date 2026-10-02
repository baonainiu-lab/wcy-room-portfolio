"""Shared Room/Gallery data bakes for the linear diffuse + real specular renderer.

All scene functions require file-targeted Blender MCP background execution.
PNG IO deliberately writes no transfer-function chunks or display transforms.
Input arrays follow Blender image.pixels (bottom row first); PNG rows are flipped.
"""
import array, contextlib, fcntl, hashlib, json, struct, time, zlib
from pathlib import Path
import bpy
import numpy as np

RGBM_RANGE=32.0

def _chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
def _png(path,rgba):
    a=np.asarray(rgba,dtype=np.uint8);assert a.ndim==3 and a.shape[2]==4
    height,width=a.shape[:2]
    rows=b''.join(b'\x00'+row.tobytes() for row in a[::-1])
    blob=b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+_chunk(b'IDAT',zlib.compress(rows,6))+_chunk(b'IEND',b'')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.pending.png');tmp.write_bytes(blob);tmp.replace(path)
    return {'path':str(path),'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'dimensions':[width,height],'colorSpace':'NoColorSpace / linear data','orientation':'PNG top-down from Blender bottom-up pixels; glTF flipY=false','channels':4}

def image_pixels(image):
    w,h=image.size;a=np.empty(w*h*4,np.float32);image.pixels.foreach_get(a);return a.reshape(h,w,4)

def write_rgbm32(path,pixels):
    """Encode unclipped scene-linear radiance; report all range32 clipping."""
    rgb=np.asarray(pixels,dtype=np.float32)[...,:3];assert rgb.ndim==3 and np.isfinite(rgb).all()
    negative=float(np.mean(rgb<0));clipped=float(np.mean(rgb>RGBM_RANGE));maxvalue=float(rgb.max())
    # Keep every out-of-range source float and its exact bottom-up RGB index.
    # This permits later range changes without rerendering the lighting.
    outlier_record=None
    if clipped:
        indices=np.flatnonzero(rgb.reshape(-1)>RGBM_RANGE).astype(np.uint32);values=rgb.reshape(-1)[indices].copy()
        staging=Path(__file__).resolve().parents[1]/'linear-intermediates'/Path(path).parent.name;staging.mkdir(parents=True,exist_ok=True)
        outliers=staging/(Path(path).stem+'-hdr-outliers.npz');np.savez_compressed(outliers,indices=indices,values=values,shape=np.array(rgb.shape))
        outlier_record={'path':str(outliers),'sha256':hashlib.sha256(outliers.read_bytes()).hexdigest(),'count':len(indices),'indexConvention':'flattened bottom-up Blender RGB float buffer; restore before PNG row flip'}
    rgb=np.clip(rgb,0,RGBM_RANGE)
    multiplier=np.clip(np.ceil(np.max(rgb,axis=2)/RGBM_RANGE*255),1,255).astype(np.uint8)
    color=np.rint(np.clip(rgb/(multiplier[...,None].astype(np.float32)/255*RGBM_RANGE),0,1)*255).astype(np.uint8)
    encoded=np.concatenate([color,multiplier[...,None]],axis=2)
    decoded=color.astype(np.float32)/255*(multiplier[...,None].astype(np.float32)/255)*RGBM_RANGE
    result=_png(path,encoded);result.update(encoding='RGBM32',decode='32 * rgb * alpha',range=32,sourceRadianceMaximum=maxvalue,
        valuesAboveRangeFraction=clipped,negativeInputFraction=negative,quantizationMAE=float(np.mean(np.abs(decoded-rgb))),quantizationMaxError=float(np.max(np.abs(decoded-rgb))),alphaIsMultiplier=True,hdrOutliers=outlier_record)
    return result

def write_data_rgba(path,pixels):
    values=np.asarray(pixels,dtype=np.float32);assert values.ndim==3 and values.shape[2]==4 and np.isfinite(values).all()
    out=np.rint(np.clip(values,0,1)*255).astype(np.uint8)
    result=_png(path,out);result.update(encoding='RGBA8 linear numeric data',sourceRange=[float(values.min()),float(values.max())],
        valuesOutsideUnitRangeFraction=float(np.mean((values<0)|(values>1))),valuesOutsideRangeBeyondFloatToleranceFraction=float(np.mean((values<-.00001)|(values>1.00001))));return result

def numeric_selfcheck():
    x=np.array([[[0.,0,0],[.04,.04,.04],[1.,.2,.05],[4,12,31.9],[32,32,32]]],np.float32)
    m=np.clip(np.ceil(x.max(2)/32*255),1,255);rgb=np.rint(np.clip(x/(m[...,None]/255*32),0,1)*255)
    y=rgb/255*m[...,None]/255*32
    assert np.isfinite(y).all() and np.all(y[0,0]==0) and np.allclose(y[0,-1],32)
    assert np.max(np.abs(y-x))<32/255/2+.0001
    # IOR 1.5 with default level .5 => F0=.04; metalness one => base reflectance.
    dielectric=((1.5-1)/(1.5+1))**2*(2*.5);assert abs(dielectric-.04)<1e-9
    return {'rgbmRoundtripMaxError':float(np.max(np.abs(y-x))),'defaultDielectricF0':dielectric,'orientation':'Rows flipped exactly once in PNG writer'}

@contextlib.contextmanager
def gpu_job(label):
    assert bpy.app.background,'Never render or bake the interactive project'
    with open('/tmp/room-portfolio-blender-gpu.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def mesh_signature(meshes):
    h=hashlib.sha256()
    for obj in sorted(meshes,key=lambda o:o.name):
        mesh=obj.data;h.update(obj.name.encode());h.update(array.array('f',[x for row in obj.matrix_world for x in row]).tobytes())
        for collection,field,kind,width in ((mesh.vertices,'co','f',3),(mesh.loops,'vertex_index','i',1),(mesh.polygons,'material_index','i',1)):
            a=array.array(kind,[0])*(len(collection)*width);collection.foreach_get(field,a);h.update(a.tobytes())
        for uv in mesh.uv_layers:
            a=array.array('f',[0])*(len(uv.data)*2);uv.data.foreach_get('uv',a);h.update(uv.name.encode());h.update(a.tobytes())
        a=array.array('f',[0])*(len(mesh.corner_normals)*3);mesh.corner_normals.foreach_get('vector',a);h.update(a.tobytes())
    return h.hexdigest()

@contextlib.contextmanager
def bake_proxy(scene,meshes,label):
    assert meshes and all(o.type=='MESH' and o.data.uv_layers.get('BakeUV') for o in meshes)
    bpy.context.window.scene=scene;bpy.context.view_layer.update();before=mesh_signature(meshes)
    states={o:(o.hide_render,o.hide_get()) for o in meshes};bpy.ops.object.select_all(action='DESELECT');copies=[]
    for obj in meshes:
        proxy=obj.copy();proxy.data=obj.data.copy();scene.collection.objects.link(proxy);transform=obj.matrix_world.copy();proxy.parent=None;proxy.matrix_world=transform
        proxy.hide_render=False;proxy.hide_set(False);proxy.select_set(True);obj.hide_render=True;copies.append(proxy)
    bpy.context.view_layer.objects.active=copies[0];bpy.ops.object.join();proxy=bpy.context.object;proxy.name='PBR_DATA_PROXY_'+str(label)
    proxy.data.uv_layers.active=proxy.data.uv_layers['BakeUV'];proxy.data.uv_layers['BakeUV'].active_render=True
    try:yield proxy
    finally:
        if proxy.name in bpy.data.objects:bpy.data.objects.remove(proxy,do_unlink=True)
        for obj,(render,hidden) in states.items():obj.hide_render=render;obj.hide_set(hidden)
        assert mesh_signature(meshes)==before,'Bake proxy altered original mesh/UV/normal data'

def _target(materials,target_name,image):
    records=[]
    for mat in materials:
        assert mat.use_nodes,mat.name;tree=mat.node_tree;n=tree.nodes.get(target_name)
        created=n is None
        if created:n=tree.nodes.new('ShaderNodeTexImage');n.name=target_name
        assert n.type=='TEX_IMAGE',target_name
        records.append((mat,n,n.image,tree.nodes.active,created));n.image=image;tree.nodes.active=n
    return records
def _restore_targets(records):
    for mat,n,image,active,created in records:
        if created:mat.node_tree.nodes.remove(n)
        else:n.image=image
        mat.node_tree.nodes.active=active

def _value(tree,nodes,value,kind='VALUE'):
    if not isinstance(value,(int,float,tuple,list)):return value
    n=tree.nodes.new('ShaderNodeRGB' if kind=='RGB' else 'ShaderNodeValue');nodes.append(n);n.outputs[0].default_value=value;return n.outputs[0]
def _input(tree,nodes,socket):
    return socket.links[0].from_socket if socket.is_linked else _value(tree,nodes,list(socket.default_value) if hasattr(socket.default_value,'__iter__') else socket.default_value,'RGB' if hasattr(socket.default_value,'__iter__') else 'VALUE')
def _math(tree,nodes,op,a,b):
    n=tree.nodes.new('ShaderNodeMath');nodes.append(n);n.operation=op
    tree.links.new(_value(tree,nodes,a),n.inputs[0]);tree.links.new(_value(tree,nodes,b),n.inputs[1]);return n.outputs[0]

def principled_f0_socket(mat,nodes):
    """Principled base-lobe F0: true dielectric IOR level/tint mixed with metal."""
    tree=mat.node_tree;p=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None);assert p,mat.name
    ior=_input(tree,nodes,p.inputs['IOR']);metal=_input(tree,nodes,p.inputs['Metallic']);base=_input(tree,nodes,p.inputs['Base Color'])
    level=p.inputs.get('Specular IOR Level');level_value=_input(tree,nodes,level) if level else .5
    ratio=_math(tree,nodes,'DIVIDE',_math(tree,nodes,'SUBTRACT',ior,1),_math(tree,nodes,'ADD',ior,1))
    f0=_math(tree,nodes,'MULTIPLY',_math(tree,nodes,'POWER',ratio,2),_math(tree,nodes,'MULTIPLY',level_value,2))
    tint=p.inputs.get('Specular Tint');tint_value=_input(tree,nodes,tint) if tint else _value(tree,nodes,(1,1,1,1),'RGB')
    mul=tree.nodes.new('ShaderNodeMixRGB');nodes.append(mul);mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1
    tree.links.new(f0,mul.inputs[1]);tree.links.new(tint_value,mul.inputs[2])
    mix=tree.nodes.new('ShaderNodeMixRGB');nodes.append(mix);mix.blend_type='MIX';tree.links.new(metal,mix.inputs[0]);tree.links.new(mul.outputs[0],mix.inputs[1]);tree.links.new(base,mix.inputs[2])
    return mix.outputs[0]

@contextlib.contextmanager
def surface_as_data(materials,channel):
    records=[]
    try:
        for mat in materials:
            tree=mat.node_tree;p=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None);assert p,mat.name
            out=next((n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None);assert out
            links=[link.from_socket for link in out.inputs['Surface'].links];nodes=[];records.append((tree,out,links,nodes))
            value=principled_f0_socket(mat,nodes) if channel=='f0' else _input(tree,nodes,p.inputs['Roughness'])
            emit=tree.nodes.new('ShaderNodeEmission');nodes.append(emit);emit.inputs['Strength'].default_value=1;tree.links.new(value,emit.inputs['Color']);tree.links.new(emit.outputs[0],out.inputs['Surface'])
        yield
    finally:
        for tree,out,links,nodes in records:
            for link in list(out.inputs['Surface'].links):tree.links.remove(link)
            for socket in links:tree.links.new(socket,out.inputs['Surface'])
            for n in reversed(nodes):tree.nodes.remove(n)

def _image(name,size):
    image=bpy.data.images.new(name,width=size,height=size,alpha=True,float_buffer=True);image.colorspace_settings.name='Non-Color';return image

def bake_channels(scene,meshes,target_node_name,atlas_slot,data_size,outdir,samples=8,_prebaked=None):
    """Bake true per-material F0/roughness and tangent GL normals on existing BakeUV.

    Output specular-{slot}.png: RGB linear F0, A perceptual roughness.
    Output normal-{slot}.png: RGB tangent-space +Y normal, A=1.
    No albedo inferred from already-lit combined maps. Base lobe only: the common
    runtime contract cannot retain separate coat, anisotropy or transmission lobes.
    """
    assert bpy.app.background;outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    source_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest();before=mesh_signature(meshes)
    old_samples=scene.cycles.samples;scene.render.engine='CYCLES';scene.cycles.samples=samples
    material_set={mat for o in meshes for mat in o.data.materials if mat};materials=sorted(material_set,key=lambda m:m.name)
    margin=max(8,round(data_size/256));buffers={};seconds={};images=[]
    if _prebaked:buffers,seconds=_prebaked['buffers'],_prebaked['seconds']
    try:
        if not _prebaked:
            with bake_proxy(scene,meshes,atlas_slot):
                for channel in ('normal','f0','roughness'):
                    image=_image(f'PBR_{channel}_{atlas_slot}',data_size);images.append(image);targets=_target(materials,target_node_name,image);started=time.monotonic()
                    try:
                        with gpu_job(f'pbr-{atlas_slot}-{channel}'):
                            if channel=='normal':bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',uv_layer='BakeUV',margin=margin,use_clear=True)
                            else:
                                with surface_as_data(materials,channel):bpy.ops.object.bake(type='EMIT',uv_layer='BakeUV',margin=margin,use_clear=True)
                        buffers[channel]=image_pixels(image);seconds[channel]=round(time.monotonic()-started,2)
                    finally:_restore_targets(targets)
        normal=buffers['normal']
        # Blender versions may clear NORMAL to neutral +Z or black. EMIT data
        # reliably clears empty texels to zero; a real dielectric has nonzero F0.
        occupied=(np.max(buffers['f0'][...,:3],axis=2)>1e-7)|(buffers['roughness'][...,0]>1e-7)
        # Empty normal pixels must never decode to (-1,-1,-1) or pollute mips.
        raw_normal=normal[...,:3];vectors=raw_normal*2-1;lengths=np.linalg.norm(vectors,axis=2)
        valid=raw_normal[occupied];valid_lengths=lengths[occupied]
        raw_normal_statistics={'channelMin':valid.min(axis=0).tolist(),'channelMax':valid.max(axis=0).tolist(),
            'outsideExactUnitRangeFraction':float(np.mean((valid<0)|(valid>1))),
            'outsideUnitRangeBeyond1e5Fraction':float(np.mean((valid<-.00001)|(valid>1.00001))),
            'decodedVectorLengthPercentiles':np.percentile(valid_lengths,[0,1,50,99,100]).tolist(),
            'filteredVectorLengthBelowQuarterCount':int(np.sum(valid_lengths<.25)),
            'filteredVectorLengthBelowQuarterFraction':float(np.mean(valid_lengths<.25)),
            'zeroLengthFallbackCount':int(np.sum(valid_lengths<1e-6))}
        assert valid.min()>=-.0001 and valid.max()<=1.0001,raw_normal_statistics
        assert np.isfinite(valid_lengths).all() and valid_lengths.max()<1.1,raw_normal_statistics
        # Cycles interpolation and bake filtering can leave vectors slightly
        # non-unit, including planar Z just above 1 by a float epsilon. Preserve
        # their direction and normalize before UNORM quantization; never clip a
        # materially invalid vector into an apparently valid normal map.
        # At a tiny number of filtered island-edge samples, opposing normal
        # contributions can shorten the average. Normalizing their nonzero sum
        # is the ordinary normal-map filtering rule; only an undefined zero
        # vector receives the neutral fallback, with its count reported.
        vectors/=np.maximum(lengths[...,None],1e-8);vectors[lengths<1e-6]=(0,0,1);normal[...,:3]=vectors*.5+.5
        normal[~occupied,:3]=(.5,.5,1);normal[...,3]=1
        specular=buffers['f0'];specular[...,3]=buffers['roughness'][...,0]
        specular[~occupied,:3]=0;specular[~occupied,3]=1
        normal_record=write_data_rgba(outdir/f'normal-{atlas_slot}.png',normal)
        specular_record=write_data_rgba(outdir/f'specular-{atlas_slot}.png',specular)
    finally:
        scene.cycles.samples=old_samples
        for image in images:bpy.data.images.remove(image)
    assert mesh_signature(meshes)==before and hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()==source_hash
    result={'complete':True,'sourceBlend':bpy.data.filepath,'sourceSha256':source_hash,'slot':atlas_slot,'dataSize':data_size,'samples':samples,'normal':normal_record,'specular':specular_record,
        'geometryUvNormalsUnchanged':True,'rawNormalStatistics':raw_normal_statistics,'decodedNormalsRenormalizedBeforeQuantization':True,'occupiedTexelFraction':float(occupied.mean()),'unusedNormalTexels':'neutral +Z','unusedSpecularTexels':'zero F0, roughness one','seconds':seconds,'f0Formula':'mix(2 * specularIORLevel * ((IOR-1)/(IOR+1))^2 * specularTint, baseColor, metallic)',
        'normalConvention':'Tangent +X +Y +Z (OpenGL), BakeUV; PNG top-down, glTF flipY=false','limitations':['Single base specular lobe; coat, anisotropy and transmission remain source-only unless runtime handles separate lobes.']}
    (outdir/f'surface-{atlas_slot}-manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result

def bake_channel(scene,meshes,target_node_name,atlas_slot,data_size,outdir,channel,samples=8):
    """A single MCP-bounded data pass, persisted as lossless numeric floats."""
    assert bpy.app.background and channel in ('normal','f0','roughness')
    outdir=Path(outdir);intermediate=Path(__file__).resolve().parents[1]/'linear-intermediates'/outdir.name;intermediate.mkdir(parents=True,exist_ok=True)
    source_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest();before=mesh_signature(meshes)
    materials=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name)
    image=_image(f'PBR_SINGLE_{channel}_{atlas_slot}',data_size);targets=_target(materials,target_node_name,image)
    old_samples=scene.cycles.samples;scene.render.engine='CYCLES';scene.cycles.samples=samples;started=time.monotonic();margin=max(8,round(data_size/256))
    try:
        with bake_proxy(scene,meshes,atlas_slot):
            with gpu_job(f'pbr-single-{atlas_slot}-{channel}'):
                if channel=='normal':bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',uv_layer='BakeUV',margin=margin,use_clear=True)
                else:
                    with surface_as_data(materials,channel):bpy.ops.object.bake(type='EMIT',uv_layer='BakeUV',margin=margin,use_clear=True)
        values=image_pixels(image)
        path=intermediate/f'{channel}-{atlas_slot}.npz';temp=path.with_suffix('.pending.npz');np.savez_compressed(temp,pixels=values);temp.replace(path)
    finally:
        _restore_targets(targets);bpy.data.images.remove(image);scene.cycles.samples=old_samples
    assert before==mesh_signature(meshes) and hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()==source_hash
    result={'complete':True,'slot':atlas_slot,'channel':channel,'dataSize':data_size,'samples':samples,'sourceSha256':source_hash,'sourceBlend':bpy.data.filepath,
        'meshSignature':before,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seconds':round(time.monotonic()-started,2),
        'rawRange':[float(values.min()),float(values.max())],'losslessFloatIntermediate':True}
    (intermediate/f'{channel}-{atlas_slot}.json').write_text(json.dumps(result,indent=2)+'\n');return result

def assemble_channels(scene,meshes,target_node_name,atlas_slot,data_size,outdir):
    """CPU assembly after three independently scheduled MCP data passes."""
    outdir=Path(outdir);intermediate=Path(__file__).resolve().parents[1]/'linear-intermediates'/outdir.name;source_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
    buffers={};seconds={};signature=mesh_signature(meshes)
    for channel in ('normal','f0','roughness'):
        row=json.loads((intermediate/f'{channel}-{atlas_slot}.json').read_text());path=Path(row['path'])
        assert row['complete'] and row['sourceSha256']==source_hash and row['meshSignature']==signature and row['dataSize']==data_size
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        with np.load(path) as data:buffers[channel]=data['pixels'].copy()
        seconds[channel]=row['seconds']
    return bake_channels(scene,meshes,target_node_name,atlas_slot,data_size,outdir,_prebaked={'buffers':buffers,'seconds':seconds})

def bake_diffuse(scene,meshes,target_node_name,atlas_slot,size,outdir,state,samples=96):
    """One linear RGBM32 diffuse/emission atlas; glossy rays are excluded."""
    assert bpy.app.background;outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    before=mesh_signature(meshes);image=_image(f'LINEAR_DIFFUSE_{state}_{atlas_slot}',size)
    materials=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name);old_samples=scene.cycles.samples;scene.cycles.samples=samples
    started=time.monotonic();targets=_target(materials,target_node_name,image)
    try:
        with bake_proxy(scene,meshes,atlas_slot):
            with gpu_job(f'diffuse-{state}-{atlas_slot}'):
                bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','EMIT'},uv_layer='BakeUV',margin=max(8,round(size/256)),use_clear=True)
        result=write_rgbm32(outdir/f'{state}-{atlas_slot}.png',image_pixels(image))
    finally:
        _restore_targets(targets);bpy.data.images.remove(image);scene.cycles.samples=old_samples
    assert mesh_signature(meshes)==before
    result.update(slot=atlas_slot,state=state,engine='CYCLES',samples=samples,passFilter=['DIRECT','INDIRECT','COLOR','DIFFUSE','EMIT'],glossyExcluded=True,geometryUvNormalsUnchanged=True,seconds=round(time.monotonic()-started,2),sourceBlend=bpy.data.filepath,sourceSha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest())
    (outdir/f'{state}-{atlas_slot}-manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
