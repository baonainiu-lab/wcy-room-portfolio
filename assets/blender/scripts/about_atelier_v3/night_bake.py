"""True night lightmaps on the exact shipped day UVs; never exports a GLB."""
import argparse,array,contextlib,fcntl,hashlib,json,math,struct,sys,time
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import web_export as W
ROOT=W.ROOT
MAIN=ROOT/'assets/blender/about-atelier-v3-night-bake.blend'
ARCH=ROOT/'assets/blender/about-atelier-v3-architecture-night-bake.blend'
REPORT=ROOT/'assets/blender/about-atelier-v3-web/night-preparation.json'
TEXTURES=W.TEXTURES
RENDERS=ROOT/'renders/about-atelier-v3-night'

@contextlib.contextmanager
def gpu(label):
    with open('/tmp/room-portfolio-blender-gpu.lock','a') as f:
        print('GPU_WAIT '+label,flush=True);fcntl.flock(f,fcntl.LOCK_EX);print('GPU_ACQUIRED '+label,flush=True)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN);print('GPU_RELEASE '+label,flush=True)

def uv_signature(objects):
    h=hashlib.sha256();count=0
    for o in sorted(objects,key=lambda x:x.name):
        if o.type!='MESH' or not o.data.uv_layers.get('BakeUV'):continue
        count+=1;h.update(o.name.encode());m=o.data
        for data,field,typ,dim in [(m.vertices,'co','f',3),(m.loops,'vertex_index','i',1),(m.uv_layers['BakeUV'].data,'uv','f',2)]:
            values=array.array(typ,[0])*(len(data)*dim);data.foreach_get(field,values);h.update(values.tobytes())
        h.update(array.array('f',[v for row in o.matrix_world for v in row]).tobytes())
    return {'meshCount':count,'geometryUvTransformSha256':h.hexdigest()}

def night(scene):
    scene.world=scene.world.copy();scene.world.name='Atelier physical night'
    for n in scene.world.node_tree.nodes:
        if n.type=='BACKGROUND':n.inputs['Strength'].default_value=.028
    lights=[]
    for o in scene.objects:
        if o.type!='LIGHT':continue
        o.data=o.data.copy()
        if o.data.type=='SUN':o.data.energy=.085;o.data.color=(.48,.65,1);o.data.angle=math.radians(4)
        elif o.name.startswith('warm.awards'):o.data.energy=68;o.data.color=(1,.66,.32)
        elif o.name.startswith('warm.desk'):o.data.energy=92;o.data.color=(1,.73,.42)
        elif o.name.startswith('day.'):o.data.energy=0
        lights.append({'name':o.name,'type':o.data.type,'energy':o.data.energy,'color':list(o.data.color)})
    materials={m for o in scene.objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes}
    emissives=[]
    for mat in materials:
        for n in mat.node_tree.nodes:
            if n.type=='BSDF_PRINCIPLED':
                strength=n.inputs.get('Emission Strength')
                if strength and not strength.is_linked and strength.default_value>0:
                    old=strength.default_value;strength.default_value=min(6,old*1.8);emissives.append({'material':mat.name,'before':old,'after':strength.default_value})
    scene.cycles.samples=64;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.02
    scene.cycles.max_bounces=8;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=8
    scene['lighting_state']='night';scene['night_bake_samples']=64
    return {'worldStrength':.028,'moonSunStrength':.085,'lights':lights,'emissives':emissives,'samples':64}

def glb_access(doc,binary,index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    dim={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];fmt={5126:'f',5125:'I',5123:'H',5121:'B'}[a['componentType']]
    width=struct.calcsize('<'+fmt*dim);stride=v.get('byteStride',width);start=v.get('byteOffset',0)+a.get('byteOffset',0)
    return [struct.unpack_from('<'+fmt*dim,binary,start+i*stride) for i in range(a['count'])]

def recover_shipped_arch_uv(opaque):
    path=ROOT/'public/models/about-atelier-v3-architecture.glb';blob=path.read_bytes();n=struct.unpack_from('<I',blob,12)[0];doc=json.loads(blob[20:20+n]);binary=blob[28+n:]
    mi=next(i for i,m in enumerate(doc['materials']) if m['name']=='ATELIER_ARCH_LIGHTMAP')
    primitives=[p for m in doc['meshes'] for p in m['primitives'] if p['material']==mi];assert len(primitives)==1
    p=primitives[0];positions=glb_access(doc,binary,p['attributes']['POSITION']);uvs=glb_access(doc,binary,p['attributes']['TEXCOORD_0']);indices=[v[0] for v in glb_access(doc,binary,p['indices'])]
    key=lambda p:tuple(round(float(x),4) for x in p)
    triangles={}
    for j in range(0,len(indices),3):
        ids=indices[j:j+3];keys=[key(positions[i]) for i in ids];signature=tuple(sorted(keys));row={k:(uvs[i][0],1-uvs[i][1]) for k,i in zip(keys,ids)}
        if signature in triangles:assert triangles[signature]==row,'Ambiguous overlapping architecture triangles'
        triangles[signature]=row
    m=opaque.data;m.calc_loop_triangles();uv=m.uv_layers['BakeUV'];assigned={};deltas=[]
    assert len(m.loop_triangles)*3==len(indices),(len(m.loop_triangles),len(indices))
    for tri in m.loop_triangles:
        keys=[]
        for vi in tri.vertices:
            pos=opaque.matrix_world@m.vertices[vi].co;keys.append(key((pos.x,pos.z,-pos.y)))
        signature=tuple(sorted(keys));assert signature in triangles,'Rebuilt architecture differs from shipped geometry'
        row=triangles[signature]
        for li,k in zip(tri.loops,keys):
            value=row[k]
            if li in assigned:assert max(abs(a-b) for a,b in zip(assigned[li],value))<1e-6
            assigned[li]=value;deltas.append(max(abs(a-b) for a,b in zip(uv.data[li].uv,value)))
    assert len(assigned)==len(m.loops)
    # Always copy the exact published UVs, avoiding pack-island nondeterminism.
    for li,value in assigned.items():uv.data[li].uv=value
    return {'sourceGlb':W.rel(path),'sourceGlbSha256':W.sha(path),'triangles':len(m.loop_triangles),'loopCorners':len(assigned),'maximumReconstructionUvDelta':max(deltas),'shippedUvsRecovered':True,'geometryMatchesShippedGlb':True}

def prepare():
    protected=[W.SOURCE,W.PREPARED,ROOT/'assets/blender/about-atelier-v3-architecture-v2.blend',ROOT/'public/models/about-atelier-v3.glb',ROOT/'public/models/about-atelier-v3-compressed.glb',ROOT/'public/models/about-atelier-v3-architecture.glb',*[TEXTURES/f'day-{i}.png' for i in range(4)],TEXTURES/'architecture/day.png']
    report={'protected':{W.rel(p):W.sha(p) for p in protected},'samples':64}
    s=W.load_prepared();before=uv_signature(s.objects);lighting=night(s);after=uv_signature(s.objects);assert before==after
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(MAIN),compress=True)
    report['main']={'path':W.rel(MAIN),'sha256':W.sha(MAIN),'before':before,'after':after,'lighting':lighting,'preparation_id':s['preparation_id']};W.write_json(REPORT,report)
    path=Path(__file__).with_name('architecture_export.py');code=path.read_text().split('    device = W.device(scene)')[0]
    code+='    return scene, opaque, image\n'
    scope={'__name__':'night_architecture_preparation','__file__':str(path)};exec(compile(code,str(path),'exec'),scope)
    s,opaque,image=scope['main']();uv_report=recover_shipped_arch_uv(opaque);before=uv_signature([opaque]);lighting=night(s);after=uv_signature([opaque]);assert before==after
    bpy.ops.wm.save_as_mainfile(filepath=str(ARCH),compress=True)
    report['architecture']={'path':W.rel(ARCH),'sha256':W.sha(ARCH),'before':before,'after':after,'uvValidation':uv_report,'lighting':lighting}
    for p,digest in report['protected'].items():assert W.sha(ROOT/p)==digest
    report['complete']=True;W.write_json(REPORT,report);print('ABOUT_NIGHT_PREPARED',flush=True)

def render_preview():
    bpy.ops.wm.open_mainfile(filepath=str(ARCH));s=bpy.data.scenes['WEB_ABOUT_ATELIER_ARCHITECTURE'];bpy.context.window.scene=s;W.device(s)
    camera=bpy.data.objects.new('CAM.about.night.preview',bpy.data.cameras.new('CAM.about.night.preview'));s.collection.objects.link(camera)
    camera.location=(10,-14,8.1);target=Vector((.4,-.4,1.5));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=44;s.camera=camera
    s.render.resolution_x=1600;s.render.resolution_y=1050;s.render.resolution_percentage=100;s.cycles.use_denoising=True
    RENDERS.mkdir(parents=True,exist_ok=True);s.render.filepath=str(RENDERS/'night-wide.png')
    with gpu('about-night-preview'):bpy.ops.render.render(write_still=True)
    print('ABOUT_NIGHT_PREVIEW '+s.render.filepath,flush=True)

def bake():
    report=json.loads(REPORT.read_text());assert report['complete'];manifest_path=TEXTURES/'night-manifest.json'
    manifest={'complete':False,'state':'night','samples':64,'preparedSha256':report['main']['sha256'],'preparation_id':report['main']['preparation_id'],'atlases':[]}
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old.get('preparedSha256')==manifest['preparedSha256']:manifest=old
    bpy.ops.wm.open_mainfile(filepath=str(MAIN));s=bpy.data.scenes[W.SCENE];bpy.context.window.scene=s;W.device(s)
    for atlas in range(4):
        done=next((r for r in manifest['atlases'] if r['atlas']==atlas),None)
        if done and W.sha(ROOT/done['path'])==done['sha256']:continue
        before=uv_signature(s.objects);meshes=[o for o in s.objects if o.get('web_export') and o.type=='MESH' and o.get('bake_atlas')==atlas]
        bpy.ops.object.select_all(action='DESELECT');proxies=[]
        for o in meshes:
            q=o.copy();q.data=o.data.copy();s.collection.objects.link(q);W.reparent(q,None);q.select_set(True);proxies.append(q);o.hide_render=True
        bpy.context.view_layer.objects.active=proxies[0];bpy.ops.object.join();proxy=bpy.context.object
        for m in proxy.data.materials:m.node_tree.nodes.active=m.node_tree.nodes[W.TARGET]
        started=time.monotonic()
        with gpu('about-night-atlas-'+str(atlas)):
            bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=16,use_clear=True,use_selected_to_active=False)
        path=TEXTURES/f'night-{atlas}.png';bpy.data.images['ATELIER_BAKE_ATLAS_'+str(atlas)].save_render(str(path),scene=s)
        bpy.data.objects.remove(proxy,do_unlink=True)
        for o in meshes:o.hide_render=False
        assert uv_signature(s.objects)==before
        row={'atlas':atlas,'path':W.rel(path),'sha256':W.sha(path),'resolution':[4096,4096],'bytes':path.stat().st_size,'secondsIncludingGpuQueue':round(time.monotonic()-started,2)}
        manifest['atlases']=[r for r in manifest['atlases'] if r['atlas']!=atlas]+[row];manifest['complete']=len(manifest['atlases'])==4;W.write_json(manifest_path,manifest);print('ABOUT_NIGHT_ATLAS_DONE '+json.dumps(row),flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(ARCH));s=bpy.data.scenes['WEB_ABOUT_ATELIER_ARCHITECTURE'];bpy.context.window.scene=s;W.device(s)
    opaque=s.objects['ATELIER_ARCH_OPAQUE'];bpy.ops.object.select_all(action='DESELECT');opaque.select_set(True);bpy.context.view_layer.objects.active=opaque
    for m in opaque.data.materials:m.node_tree.nodes.active=m.node_tree.nodes[W.TARGET]
    before=uv_signature([opaque]);started=time.monotonic()
    with gpu('about-night-architecture'):
        bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=16,use_clear=True,use_selected_to_active=False)
    path=TEXTURES/'architecture/night.png';bpy.data.images['ATELIER_ARCH_DAYLIGHT'].save_render(str(path),scene=s);assert uv_signature([opaque])==before
    W.write_json(TEXTURES/'architecture/night-manifest.json',{'complete':True,'state':'night','samples':64,'preparedSha256':report['architecture']['sha256'],'path':W.rel(path),'sha256':W.sha(path),'resolution':[4096,4096],'secondsIncludingGpuQueue':round(time.monotonic()-started,2),'uvValidation':report['architecture']['uvValidation']})
    for p,digest in report['protected'].items():assert W.sha(ROOT/p)==digest
    print('ABOUT_NIGHT_ALL_BAKED',flush=True)

def validate_pixels():
    import numpy as np
    prepared=json.loads(REPORT.read_text())
    for p,digest in prepared['protected'].items():assert W.sha(ROOT/p)==digest
    blob=(ROOT/'public/models/about-atelier-v3.glb').read_bytes();length=struct.unpack_from('<I',blob,12)[0];doc=json.loads(blob[20:20+length])
    assert doc['asset']['extras']['preparation_id']==prepared['main']['preparation_id']
    def sample(path):
        im=bpy.data.images.load(str(path),check_existing=False);values=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(values)
        result=values.reshape(-1,4)[::64,:3].copy();bpy.data.images.remove(im);return result
    records=[]
    for slot in [0,1,2,3,'architecture']:
        day=TEXTURES/(f'day-{slot}.png' if isinstance(slot,int) else 'architecture/day.png')
        night=TEXTURES/(f'night-{slot}.png' if isinstance(slot,int) else 'architecture/night.png')
        d,n=sample(day),sample(night);assert d.shape==n.shape and np.isfinite(n).all()
        dl=d@np.array([.2126,.7152,.0722]);nl=n@np.array([.2126,.7152,.0722]);mask=dl>.035
        assert mask.sum()>1000 and n.max()>.1 and np.std(n[mask])>.015 and W.sha(day)!=W.sha(night)
        ratios=nl[mask]/dl[mask]
        records.append({'slot':slot,'sampleCount':int(mask.sum()),'meanDayLuminance':float(dl[mask].mean()),'meanNightLuminance':float(nl[mask].mean()),'nonUniformNightToDayRatioStd':float(ratios.std()),'nightMeanRgb':n[mask].mean(axis=0).tolist(),'daySha256':W.sha(day),'nightSha256':W.sha(night)})
    W.write_json(W.REPORTS/'night-pixel-validation.json',{'complete':True,'mainPreparationMatchesShippedModel':True,'allProtectedDaySourcesAndModelsUnchanged':True,'textures':records})
    print('ABOUT_NIGHT_PIXELS_VALIDATED '+json.dumps(records),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--preview',action='store_true');p.add_argument('--bake',action='store_true');p.add_argument('--validate-pixels',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.prepare:prepare()
    if args.preview:render_preview()
    if args.bake:bake()
    if args.validate_pixels:validate_pixels()
