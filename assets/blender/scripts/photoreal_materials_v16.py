"""Material-only V16 derivatives; exact V15 geometry/UVs and paired Cycles bakes.

Background Blender only. --prepare, --preview, --bake, --export are independent.
Every GPU job uses the shared POSIX advisory lock, released between atlases.
"""
import argparse, array, contextlib, fcntl, hashlib, json, math, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from run_texture_precision_v15 import scope_from
from bake_geometry_fingerprint import fingerprints
SOURCE=ROOT/'assets/blender/orbital-atelier-v16.blend'
PREP=ROOT/'assets/blender/orbital-dual-bake-v16.blend'
OUT=ROOT/'public/textures/lighting-v16'
INPUTS=ROOT/'assets/textures/room-v16'
REPORT=ROOT/'assets/blender/photoreal-materials-v16.json'
RENDERS=ROOT/'renders/room-materials-v16'
ATLAS_SIZES=[4096]*6+[3072,2048,3072,4096,4096,3072]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n');t.replace(p)
def rel(p):return str(Path(p).relative_to(ROOT))

@contextlib.contextmanager
def gpu_job(label):
    with open('/tmp/room-portfolio-blender-gpu.lock','a') as lock:
        print('GPU_WAIT '+label,flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        print('GPU_ACQUIRED '+label,flush=True);started=time.monotonic()
        try:yield
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)
            print('GPU_RELEASE '+label+' '+str(round(time.monotonic()-started,2))+'s',flush=True)

def geometry_signature():
    """All loaded object geometry, normals, UVs, transforms, IDs and parenting."""
    h=hashlib.sha256();meshes=set();objects=0;tri=0
    for o in sorted(bpy.data.objects,key=lambda x:x.name):
        objects+=1
        h.update(json.dumps([o.name,o.type,o.parent.name if o.parent else None,
          {k:str(o[k]) for k in ('asset_id','owner_asset_id','bake_atlas','web_kind') if k in o}],sort_keys=True).encode())
        h.update(array.array('f',[v for row in o.matrix_world for v in row]).tobytes())
        if o.type!='MESH':continue
        m=o.data
        if m.as_pointer() in meshes:continue
        meshes.add(m.as_pointer());h.update(m.name.encode())
        for collection,field,kind,count in ((m.vertices,'co','f',3),(m.loops,'vertex_index','i',1),(m.polygons,'material_index','i',1)):
            a=array.array(kind,[0])*(len(collection)*count);collection.foreach_get(field,a);h.update(a.tobytes())
        for uv in m.uv_layers:
            h.update(uv.name.encode());a=array.array('f',[0])*(len(uv.data)*2);uv.data.foreach_get('uv',a);h.update(a.tobytes())
        a=array.array('f',[0])*(len(m.corner_normals)*3);m.corner_normals.foreach_get('vector',a);h.update(a.tobytes())
        h.update(bytes(int(p.use_smooth) for p in m.polygons));tri+=sum(max(0,len(p.vertices)-2) for p in m.polygons)
    return {'sha256':h.hexdigest(),'objects':objects,'uniqueMeshes':len(meshes),'triangles':tri}

def input_textures():
    INPUTS.mkdir(parents=True,exist_ok=True);size=2048
    rng=np.random.default_rng(16092026)
    # Deterministic seamless engineering microtextures, not synthesized photos.
    x=np.arange(size,dtype=np.float32)/size;y=x[:,None]
    grain=np.zeros((size,size),np.float32)
    for freq,amplitude in [(97,.22),(211,.14),(479,.08),(733,.035)]:
        grain+=amplitude*np.sin(2*np.pi*(freq*y+0.16*np.sin(2*np.pi*x*3)))
    grain+=.07*rng.normal(size=(size,size)).astype(np.float32)
    ceramic=np.zeros((size,size),np.float32)
    for freq,amp in [(7,.18),(29,.12),(113,.09),(311,.04)]:
        ceramic+=amp*np.sin(2*np.pi*freq*x+rng.uniform(0,6.28))*np.cos(2*np.pi*(freq+2)*y)
    results=[]
    for name,value in [('directional-brush-2k',np.clip(.5+grain,0,1)),('ceramic-microfinish-2k',np.clip(.5+ceramic,0,1))]:
        p=INPUTS/(name+'.png')
        if not p.exists():
            image=bpy.data.images.new(name,width=size,height=size,alpha=False,float_buffer=False)
            image.colorspace_settings.name='Non-Color';pixels=np.empty((size,size,4),np.float32)
            pixels[:,:,:3]=value[:,:,None];pixels[:,:,3]=1;image.pixels.foreach_set(pixels.ravel())
            image.filepath_raw=str(p);image.file_format='PNG';image.save();bpy.data.images.remove(image)
        results.append({'path':rel(p),'sha256':sha(p),'resolution':[size,size],'license':'Project-authored deterministic procedural texture','seed':16092026})
    manifest=json.loads((ROOT/'assets/textures/about-atelier-v3/texture-manifest.json').read_text())
    for row in manifest['maps']:
        if row['asset']=='hessian_230' and row['map'] in ('Diffuse','Rough','Displacement'):
            p=ROOT/'assets/textures/about-atelier-v3'/row['file'];assert sha(p)==row['sha256'] and row['license']=='CC0-1.0'
            results.append({**row,'path':rel(p)})
    write(INPUTS/'manifest.json',{'revision':16,'textures':results,'policy':'Existing verified CC0 scans and original deterministic engineering maps; no generated bitmap decoration.'})
    return results

def family(name):
    s=name.lower().replace('_','')
    if any(x in s for x in ('ext6','wg7')):return None
    if 'satin' in s and 'titanium' in s:return 'brushed_titanium'
    if 'titaniumfloor' in s:return 'titanium_floor'
    if 'graphiteenamel' in s:return 'graphite_enamel'
    if 'ivoryceramic' in s or 'pearlceramic' in s:return 'ceramic'
    if 'vermilionwoven' in s:return 'orange_fabric'
    if 'charcoalwoven' in s:return 'charcoal_fabric'
    if 'graphiterug' in s:return 'rug'
    return None

def image_node(tree,path,vector):
    im=bpy.data.images.load(str(path),check_existing=True);im.colorspace_settings.name='Non-Color'
    # Image BOX uses object-space normals, which change when the bake proxy
    # joins differently transformed owners. Explicit world-space projections
    # preserve the inspected material exactly without adding mesh attributes.
    geo=tree.nodes.new('ShaderNodeNewGeometry');absolute=tree.nodes.new('ShaderNodeVectorMath');absolute.operation='ABSOLUTE'
    tree.links.new(geo.outputs['Normal'],absolute.inputs[0]);normal=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(absolute.outputs[0],normal.inputs[0])
    coords=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(vector,coords.inputs[0]);weights=[]
    for axis in 'XYZ':
        power=tree.nodes.new('ShaderNodeMath');power.operation='POWER';power.inputs[1].default_value=6;tree.links.new(normal.outputs[axis],power.inputs[0]);weights.append(power.outputs[0])
    add=tree.nodes.new('ShaderNodeMath');add.operation='ADD';tree.links.new(weights[0],add.inputs[0]);tree.links.new(weights[1],add.inputs[1])
    total=tree.nodes.new('ShaderNodeMath');total.operation='ADD';tree.links.new(add.outputs[0],total.inputs[0]);tree.links.new(weights[2],total.inputs[1])
    colors=[]
    for i,(u,v) in enumerate((('Y','Z'),('X','Z'),('X','Y'))):
        uv=tree.nodes.new('ShaderNodeCombineXYZ');tree.links.new(coords.outputs[u],uv.inputs['X']);tree.links.new(coords.outputs[v],uv.inputs['Y'])
        tex=tree.nodes.new('ShaderNodeTexImage');tex.image=im;tex.projection='FLAT';tex.extension='REPEAT';tree.links.new(uv.outputs[0],tex.inputs['Vector'])
        weight=tree.nodes.new('ShaderNodeMath');weight.operation='DIVIDE';tree.links.new(weights[i],weight.inputs[0]);tree.links.new(total.outputs[0],weight.inputs[1])
        scaled=tree.nodes.new('ShaderNodeMixRGB');scaled.blend_type='MULTIPLY';scaled.inputs[0].default_value=1;tree.links.new(tex.outputs['Color'],scaled.inputs[1]);tree.links.new(weight.outputs[0],scaled.inputs[2]);colors.append(scaled.outputs['Color'])
    first=tree.nodes.new('ShaderNodeMixRGB');first.blend_type='ADD';first.inputs[0].default_value=1;tree.links.new(colors[0],first.inputs[1]);tree.links.new(colors[1],first.inputs[2])
    result=tree.nodes.new('ShaderNodeMixRGB');result.blend_type='ADD';result.inputs[0].default_value=1;tree.links.new(first.outputs[0],result.inputs[1]);tree.links.new(colors[2],result.inputs[2])
    return result

def map_range(tree,socket,low,high):
    n=tree.nodes.new('ShaderNodeMapRange');n.inputs['From Min'].default_value=0;n.inputs['From Max'].default_value=1
    n.inputs['To Min'].default_value=low;n.inputs['To Max'].default_value=high;tree.links.new(socket,n.inputs['Value']);return n.outputs['Result']

def refine_material(mat,kind):
    tree=mat.node_tree;old=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not old:return None
    color=tuple(old.inputs['Base Color'].default_value);metal=old.inputs['Metallic'].default_value;rough=old.inputs['Roughness'].default_value
    target=tree.nodes.get('WEB8_BAKE_TARGET');target_image=target.image if target else None
    tree.nodes.clear();out=tree.nodes.new('ShaderNodeOutputMaterial');p=tree.nodes.new('ShaderNodeBsdfPrincipled');tree.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=metal
    geo=tree.nodes.new('ShaderNodeNewGeometry');scale=tree.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE'
    # Geometry Position is in world metres and survives the temporary joined bake proxy.
    tree.links.new(geo.outputs['Position'],scale.inputs[0]);scale.inputs[3].default_value=4.0
    vector=scale.outputs['Vector'];bump_distance=0
    if kind in ('brushed_titanium','titanium_floor','graphite_enamel'):
        tex=image_node(tree,INPUTS/'directional-brush-2k.png',vector)
        if kind=='brushed_titanium':lo,hi,metal,bump_distance=.23,.34,.94,.000025
        elif kind=='titanium_floor':lo,hi,metal,bump_distance=.33,.44,.66,.00004
        else:lo,hi,metal,bump_distance=.27,.35,.55,.000018
        p.inputs['Metallic'].default_value=metal;tree.links.new(map_range(tree,tex.outputs['Color'],lo,hi),p.inputs['Roughness'])
        if kind=='brushed_titanium':
            anisotropic=p.inputs.get('Anisotropic IOR Level') or p.inputs.get('Anisotropic')
            if anisotropic:anisotropic.default_value=.32
        height=tex.outputs['Color']
    elif kind=='ceramic':
        tex=image_node(tree,INPUTS/'ceramic-microfinish-2k.png',vector)
        tree.links.new(map_range(tree,tex.outputs['Color'],.19,.255),p.inputs['Roughness'])
        p.inputs['Metallic'].default_value=.04;p.inputs['Coat Weight'].default_value=.20;p.inputs['Coat Roughness'].default_value=.22
        # Continuous white shell remains smooth: texture affects roughness, never its normal.
        height=tex.outputs['Color'];bump_distance=0
    else:
        # A 0.625 m scan repeat keeps ~2-3 mm yarns above a baked texel.
        # Finer initial repeats disappeared under normal render denoising.
        scale.inputs[3].default_value=1.6 if kind!='rug' else 1.2
        root=ROOT/'assets/textures/about-atelier-v3/hessian_230'
        scan=image_node(tree,root/'hessian_230_disp_2k.jpg',vector)
        rou=image_node(tree,root/'hessian_230_rough_2k.jpg',vector)
        tree.links.new(map_range(tree,rou.outputs['Color'],.70,.88 if kind!='rug' else .96),p.inputs['Roughness'])
        p.inputs['Sheen Weight'].default_value=.22 if kind!='rug' else .12
        p.inputs['Sheen Roughness'].default_value=.68
        # Only luminance modulates the authored color; no beige tint from the scan.
        multiply=tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1;multiply.inputs[1].default_value=color
        tree.links.new(map_range(tree,scan.outputs['Color'],.72,1.28),multiply.inputs[2]);tree.links.new(multiply.outputs[0],p.inputs['Base Color'])
        height=scan.outputs['Color'];bump_distance=.0009 if kind!='rug' else .0012
    if bump_distance:
        bump=tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.35 if kind in ('orange_fabric','charcoal_fabric','rug') else .16;bump.inputs['Distance'].default_value=bump_distance
        tree.links.new(height,bump.inputs['Height']);tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    if target_image:
        n=tree.nodes.new('ShaderNodeTexImage');n.name='WEB8_BAKE_TARGET';n.image=target_image;tree.nodes.active=n
    if mat.get('day_sun_v9_aperture'):
        import day_sunlight_v9
        day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57)
        day_sunlight_v9._aperture_shader(mat)
    mat['material_revision']=16;mat['texture_mapping']='world metres; stable during atlas proxy join'
    return {'name':mat.name,'family':kind,'authoredBaseColor':color,'normalDistanceMetres':bump_distance,'mapping':'world metres','ceramicNormalUntouched':kind=='ceramic'}

def restore_source_aperture():
    """Keep the editable source's pre-existing daylight shadow aperture wrapper.

    The live WEB_DUAL bake scene does not use these two historic source-scene
    materials. This repair only touches the editable V16 source file.
    """
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));before=geometry_signature();fixed=[]
    import day_sunlight_v9
    day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57)
    for mat in bpy.data.materials:
        if mat.get('material_revision')==16 and mat.get('day_sun_v9_aperture') and not any('RoundedWindowShadowAperture' in n.name for n in mat.node_tree.nodes):
            day_sunlight_v9._aperture_shader(mat);fixed.append(mat.name)
    assert geometry_signature()==before
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE),compress=True)
    report=json.loads(REPORT.read_text());report['sources'][0]['sha256']=sha(SOURCE)
    report['sources'][0]['preservedSourceDaylightApertureMaterials']=fixed;write(REPORT,report)
    print('V16_EDITABLE_APERTURE_PRESERVED '+json.dumps(fixed),flush=True)

def prepare(refresh=False):
    assert refresh or (not SOURCE.exists() and not PREP.exists()),'Versioned sources already exist; use --refresh for this material derivative only'
    bpy.context.preferences.filepaths.save_version=0
    textures=input_textures();report={'revision':16,'geometryRevision':15,'textures':textures,'sources':[],'atlasSizes':ATLAS_SIZES}
    for old,new in [(ROOT/'assets/blender/orbital-atelier-v15.blend',SOURCE),(ROOT/'assets/blender/orbital-dual-bake-v15.blend',PREP)]:
        oldsha=sha(old);bpy.ops.wm.open_mainfile(filepath=str(old));before=geometry_signature();changed=[]
        for mat in list(bpy.data.materials):
            kind=family(mat.name)
            if kind and mat.use_nodes:
                record=refine_material(mat,kind)
                if record:changed.append(record)
        after=geometry_signature();assert before==after,'Material refinement changed source geometry/UVs'
        if bpy.data.scenes.get('WEB_DUAL_V8'):
            record=fingerprints(bpy.data.scenes['WEB_DUAL_V8'],include_shading=True)
        else:record={}
        bpy.ops.wm.save_as_mainfile(filepath=str(new),compress=True);assert sha(old)==oldsha
        report['sources'].append({'original':rel(old),'originalSha256':oldsha,'derivative':rel(new),'sha256':sha(new),'geometryBefore':before,'geometryAfter':after,'bakeFingerprint':record,'materials':changed})
        write(REPORT,report)
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('window-day.png','window-night.png','screen-art-render.png'):
        shutil.copy2(ROOT/'public/textures/lighting-v15'/name,OUT/name)
    report['prepareComplete']=True;write(REPORT,report);print('V16_PREPARE_COMPLETE',flush=True)

def setup(state):
    bpy.ops.wm.open_mainfile(filepath=str(PREP))
    baking=scope_from(ROOT/'assets/blender/scripts/bake_lighting_v8.py',[("OUT = ROOT / 'public/textures/lighting-v8'","OUT = ROOT / 'public/textures/lighting-v16'")],'v16_baker')
    scene=baking['setup_state'](state,report_revision=16)
    if state=='day':
        import day_sunlight_v9
        from run_wall_lighting_v10 import configure_day
        day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57);configure_day(scene,revision=16)
    else:
        warm=scope_from(ROOT/'assets/blender/scripts/night_warm_v13.py',[('night-warm-v13-design.json','night-warm-v16-design.json'),('lighting-night-v13.json','lighting-night-v16.json')],'v16_night')
        warm['configure_night_warm'](scene)
    scene.cycles.samples=96;scene.cycles.adaptive_threshold=.01
    lighting_path=ROOT/f'assets/blender/lighting-{state}-v16.json'
    lighting=json.loads(lighting_path.read_text());lighting.update(cycles_samples=96,adaptive_threshold=.01,material_revision=16)
    write(lighting_path,lighting)
    return scene

def bounds(objects):
    pts=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
    lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)));hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return lo,hi

def preview(only=None,cpu=False,state='day'):
    scene=setup(state);RENDERS.mkdir(parents=True,exist_ok=True);scene.cycles.samples=64;scene.cycles.use_denoising=True
    scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
    if cpu:
        scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=4
        scene.render.resolution_x=1100;scene.render.resolution_y=825
    sourcecamera=scene.camera;print('PREVIEW_SOURCE_CAMERA',list(sourcecamera.location) if sourcecamera else None,flush=True)
    for label,owner in [('ceramic','furniture.work_chair'),('textile','furniture.lounge'),('metal','furniture.desk')]:
        if only and label!=only:continue
        objects=[o for o in scene.objects if o.type=='MESH' and o.get('owner_asset_id')==owner]
        if not objects:raise RuntimeError('Missing preview owner '+owner)
        lo,hi=bounds(objects);center=(lo+hi)*.5;radius=max(hi-lo)*.85
        camera=bpy.data.objects.new('V16_QA_'+label,bpy.data.cameras.new('V16_QA_'+label));scene.collection.objects.link(camera)
        camera.location=center+Vector((1.45,-2.2,1.3))*radius;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type='PERSP';camera.data.lens=78 if label=='textile' else 58;camera.data.clip_start=.02;scene.camera=camera
        scene.render.filepath=str(RENDERS/(label+'-'+state+'.png'))
        with contextlib.nullcontext() if cpu else gpu_job('room-v16-preview-'+label):bpy.ops.render.render(write_still=True)
        print('PREVIEW_READY '+scene.render.filepath,flush=True)
    write(RENDERS/('manifest-'+(only+'-' if only else '')+state+'.json'),{'state':state,'samples':64,'device':scene.cycles.device,'preparedSha256':sha(PREP),'views':[only] if only else ['ceramic','textile','metal']})

def bake():
    report=json.loads(REPORT.read_text());assert report['prepareComplete'];assert sha(PREP)==report['sources'][1]['sha256']
    for state in ('day','night'):
        scene=setup(state);started=time.monotonic();manifest_path=OUT/f'{state}-v16-manifest.json'
        previous=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        if previous:assert previous.get('preparedSha256')==report['sources'][1]['sha256'],'Existing bake belongs to another material preparation'
        records=previous.get('atlases',[]);done={r['atlas']:r for r in records if (ROOT/r['path']).exists() and sha(ROOT/r['path'])==r['sha256']}
        for atlas in range(12):
            if atlas in done:continue
            meshes=[o for o in scene.objects if o.type=='MESH' and o.get('web_export') and o.get('bake_atlas',-1)==atlas]
            assert meshes;before=fingerprints(scene,include_shading=True);bpy.ops.object.select_all(action='DESELECT');proxies=[]
            for obj in meshes:
                proxy=obj.copy();proxy.data=obj.data.copy();scene.collection.objects.link(proxy);transform=obj.matrix_world.copy();proxy.parent=None;proxy.matrix_world=transform
                proxy.hide_render=False;proxy.select_set(True);proxies.append(proxy);obj.hide_render=True
                for mat in proxy.data.materials:
                    if mat and mat.node_tree:
                        target=mat.node_tree.nodes.get('WEB8_BAKE_TARGET')
                        if target:mat.node_tree.nodes.active=target
            bpy.context.view_layer.objects.active=proxies[0];bpy.ops.object.join();proxy=bpy.context.object;proxy.name=f'V16_BAKE_PROXY_{atlas}'
            margin=8 if atlas in (2,9,10) else 12 if atlas==11 else 16
            write(ROOT/'assets/blender/bake-v16-progress.json',{'state':state,'atlas':atlas,'completed':sorted(done),'phase':'waiting_gpu','samples':96})
            t=time.monotonic()
            with gpu_job(f'room-v16-{state}-atlas-{atlas}'):
                write(ROOT/'assets/blender/bake-v16-progress.json',{'state':state,'atlas':atlas,'completed':sorted(done),'phase':'baking','samples':96})
                bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=margin,use_clear=True)
            image=bpy.data.images[f'WEB8_ATLAS_{atlas}'];path=OUT/f'{state}-{atlas}.png';image.save_render(str(path),scene=scene)
            bpy.data.objects.remove(proxy,do_unlink=True)
            for obj in meshes:obj.hide_render=False
            assert fingerprints(scene,include_shading=True)==before
            row={'atlas':atlas,'path':rel(path),'sha256':sha(path),'resolution':list(image.size),'margin':margin,'secondsIncludingGpuQueue':round(time.monotonic()-t,2),'bytes':path.stat().st_size}
            done[atlas]=row;records=[done[k] for k in sorted(done)]
            write(manifest_path,{'state':state,'samples':96,'preparedSha256':sha(PREP),'atlases':records,'complete':len(done)==12,'secondsThisRun':round(time.monotonic()-started,2)})
            print('ATLAS_COMPLETE '+json.dumps(row),flush=True)
    write(ROOT/'assets/blender/bake-v16-progress.json',{'phase':'complete','states':['day','night'],'samples':96})

def export():
    report=json.loads(REPORT.read_text());assert sha(PREP)==report['sources'][1]['sha256']
    for state in ('day','night'):
        manifest=json.loads((OUT/f'{state}-v16-manifest.json').read_text());assert manifest['complete'] and manifest['preparedSha256']==sha(PREP)
        for r in manifest['atlases']:assert sha(ROOT/r['path'])==r['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(PREP))
    exporter=scope_from(ROOT/'assets/blender/scripts/export_dual_lighting_v8.py',[
        ('for atlas in range(8):','for atlas in range(12):'),("'atlasSizes':[4096]*6+[3072,2048]","'atlasSizes':[4096]*6+[3072,2048,3072,4096,4096,3072]"),("'samples':40","'samples':96")],'v16_export')
    final=ROOT/'public/models/orbital-atelier-v16.glb'
    result=exporter['export'](textures_directory=OUT,output_path=final,source_path=rel(SOURCE),prepared_path=rel(PREP),geometry_revision=16,lighting_revision=16)
    previous=json.loads((ROOT/'assets/blender/dual-lighting-v15-export-report.json').read_text())
    assert sorted(result['componentIds'])==sorted(previous['componentIds'])
    assert result['triangles']==previous['triangles']==413855 and result['drawPrimitives']==previous['drawPrimitives']==102
    result.update(geometryInheritedFrom=15,materialRevision=16,sourceGeometryUVTransformsUnchanged=True,preparedSha256=sha(PREP),sourceSha256=sha(SOURCE),allAtlasesRebaked=True,materialReport=rel(REPORT))
    write(ROOT/'assets/blender/dual-lighting-v16-export-report.json',result);print('V16_EXPORT_COMPLETE '+json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--refresh',action='store_true');p.add_argument('--restore-source-aperture',action='store_true');p.add_argument('--preview',action='store_true');p.add_argument('--preview-kind',choices=['ceramic','textile','metal']);p.add_argument('--preview-state',choices=['day','night'],default='day');p.add_argument('--cpu-preview',action='store_true');p.add_argument('--bake',action='store_true');p.add_argument('--export',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.prepare:prepare(args.refresh)
    if args.restore_source_aperture:restore_source_aperture()
    if args.preview:preview(args.preview_kind,args.cpu_preview,args.preview_state)
    if args.bake:bake()
    if args.export:export()
