"""Reproducible daylight web derivative. Run only in a BACKGROUND Blender process.

blender -b --python assets/blender/scripts/about_atelier_v3/web_export.py -- --stage all
The editable about-atelier-v3.blend is read-only. Source object-space position
and split-normal attributes preserve procedural/triplanar coordinates through
the disposable atlas bake joins. Independent asset roots are never joined.
"""
import argparse, hashlib, json, math, shutil, struct, sys, time
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT/'assets/blender/about-atelier-v3.blend'
PREPARED = ROOT/'assets/blender/about-atelier-v3-web.blend'
REPORTS = ROOT/'assets/blender/about-atelier-v3-web'
TEXTURES = ROOT/'public/textures/about-atelier-v3'
OUTPUT = ROOT/'public/models/about-atelier-v3.glb'
SCENE = 'WEB_ABOUT_ATELIER_V3'
TARGET = 'ATELIER_BAKE_TARGET'
SIZE = 4096
POS, NORMAL = 'AtelierSourcePosition', 'AtelierSourceNormal'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rel(path): return str(Path(path).relative_to(ROOT))
def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def props(old,new):
    for key in old.keys():
        if key != '_RNA_UI':
            try:new[key]=old[key]
            except (ValueError,TypeError):pass
def owner(o):
    while o:
        if o.get('asset_id'):return o
        o=o.parent
def triangles(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
def reparent(o,p):
    m=o.matrix_world.copy();o.parent=p;o.matrix_world=m
def principle(m):return next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
def kind(m):
    p=principle(m)
    if p and p.inputs['Transmission Weight'].default_value>.5:return 'glass'
    if p and p.inputs['Metallic'].default_value>=.8:return 'metal_'+m.name
    return 'baked'
def attrs(mesh):
    a=mesh.attributes.new(POS,'FLOAT_VECTOR','POINT')
    for dst,v in zip(a.data,mesh.vertices):dst.vector=v.co
    normals=[tuple(n.vector) for n in mesh.corner_normals]
    a=mesh.attributes.new(NORMAL,'FLOAT_VECTOR','CORNER')
    for dst,n in zip(a.data,normals):dst.vector=n

def frozen_material(old,atlas,cache):
    key=(old.name,atlas)
    if key in cache:return cache[key]
    m=old.copy();m.name='ATELIER_PREP_A%d_%s'%(atlas,old.name);cache[key]=m
    nodes,links=m.node_tree.nodes,m.node_tree.links
    position=nodes.new('ShaderNodeAttribute');position.attribute_name=POS
    normal=nodes.new('ShaderNodeAttribute');normal.attribute_name=NORMAL
    for n in list(nodes):
        if n.type=='TEX_COORD':
            for link in list(n.outputs['Object'].links):links.new(position.outputs['Vector'],link.to_socket)
        if n.type=='VECT_TRANSFORM' and n.vector_type=='NORMAL' and n.convert_to=='OBJECT':
            for link in list(n.outputs['Vector'].links):links.new(normal.outputs['Vector'],link.to_socket)
    # BOX projection chooses the current joined object's axes. Replace it with
    # explicit source-local face sampling so rotated leather/fabric/stone stays
    # in the source coordinate frame. The source wood FLAT network is untouched.
    boxes=[n for n in nodes if n.type=='TEX_IMAGE' and n.projection=='BOX']
    if boxes:
        absolute=nodes.new('ShaderNodeVectorMath');absolute.operation='ABSOLUTE';links.new(normal.outputs['Vector'],absolute.inputs[0])
        separate=nodes.new('ShaderNodeSeparateXYZ');links.new(absolute.outputs['Vector'],separate.inputs[0])
        weights=[]
        for axis in 'XYZ':
            power=nodes.new('ShaderNodeMath');power.operation='POWER';power.inputs[1].default_value=8
            links.new(separate.outputs[axis],power.inputs[0]);weights.append(power.outputs[0])
        add=nodes.new('ShaderNodeMath');add.operation='ADD';links.new(weights[0],add.inputs[0]);links.new(weights[1],add.inputs[1])
        total=nodes.new('ShaderNodeMath');total.operation='ADD';links.new(add.outputs[0],total.inputs[0]);links.new(weights[2],total.inputs[1])
        for i,w in enumerate(weights):
            div=nodes.new('ShaderNodeMath');div.operation='DIVIDE';links.new(w,div.inputs[0]);links.new(total.outputs[0],div.inputs[1]);weights[i]=div.outputs[0]
        for image in boxes:
            assert image.inputs['Vector'].is_linked
            coords=nodes.new('ShaderNodeSeparateXYZ');links.new(image.inputs['Vector'].links[0].from_socket,coords.inputs[0])
            colors=[]
            for i,(u,v) in enumerate((('Y','Z'),('X','Z'),('X','Y'))):
                xy=nodes.new('ShaderNodeCombineXYZ');links.new(coords.outputs[u],xy.inputs['X']);links.new(coords.outputs[v],xy.inputs['Y'])
                im=nodes.new('ShaderNodeTexImage');im.image=image.image;im.projection='FLAT';im.extension=image.extension;im.interpolation=image.interpolation
                links.new(xy.outputs[0],im.inputs['Vector'])
                mul=nodes.new('ShaderNodeVectorMath');mul.operation='SCALE';links.new(im.outputs['Color'],mul.inputs[0]);links.new(weights[i],mul.inputs['Scale']);colors.append(mul.outputs['Vector'])
            a=nodes.new('ShaderNodeVectorMath');a.operation='ADD';links.new(colors[0],a.inputs[0]);links.new(colors[1],a.inputs[1])
            b=nodes.new('ShaderNodeVectorMath');b.operation='ADD';links.new(a.outputs[0],b.inputs[0]);links.new(colors[2],b.inputs[1])
            for link in list(image.outputs['Color'].links):links.new(b.outputs[0],link.to_socket)
            nodes.remove(image)
    return m

def prepare():
    started=time.monotonic();source_sha=sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));source=bpy.context.scene
    selected={o:i for i,prefix in enumerate(('01_','02_','03_','04_')) for c in source.collection.children if c.name.startswith(prefix) for o in c.all_objects}
    roots=[o for o in selected if o.get('asset_id')];assert len(roots)==128
    hierarchy={o['asset_id']:(owner(o.parent)['asset_id'] if owner(o.parent) else None) for o in roots}
    original_world={o:o.matrix_world.copy() for o in selected}
    # Keep each silhouette, reducing only bevel rings and curve cross-sections.
    for o in selected:
        for mod in o.modifiers:
            if mod.type=='BEVEL':mod.segments=min(mod.segments,2)
        if o.type=='CURVE':o.data.bevel_resolution=min(o.data.bevel_resolution,2)
    bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
    s=bpy.data.scenes.new(SCENE);s.world=source.world.copy();s.render.engine='CYCLES'
    for k in ('view_transform','look','exposure','gamma'):setattr(s.view_settings,k,getattr(source.view_settings,k))
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
    s.cycles.samples=32;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.035
    s.cycles.max_bounces=8;s.cycles.diffuse_bounces=3;s.cycles.glossy_bounces=3;s.cycles.transmission_bounces=8
    copies={}
    static=bpy.data.objects.new('ATELIER_STATIC_PLATFORM',None);s.collection.objects.link(static);static['web_export']=True;static['interactive']=False
    for old in roots:
        o=bpy.data.objects.new(old.name,None);s.collection.objects.link(o);o.matrix_world=original_world[old];props(old,o);o['web_export']=True;copies[old]=o
    bpy.context.window.scene=s
    for old,o in copies.items():
        ancestor=owner(old.parent)
        if ancestor:reparent(o,copies[ancestor])
    bpy.context.window.scene=source
    cache={};parts=[];counts={}
    for old,atlas in selected.items():
        if old.type not in {'MESH','CURVE','FONT','SURFACE'}:continue
        data=bpy.data.meshes.new_from_object(old.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
        if not data.polygons:bpy.data.meshes.remove(data);continue
        asset_owner=owner(old)
        assert asset_owner in copies or (atlas==0 and old.name.startswith('atelier.plinth.')),old.name
        kinds={kind(data.materials[p.material_index]) for p in data.polygons}
        assert len(kinds)==1,(old.name,kinds)
        k=next(iter(kinds));attrs(data)
        data.transform(original_world[old]);data.update()
        o=bpy.data.objects.new('ATELIER_PART_'+old.name,data);s.collection.objects.link(o)
        o['owner_asset_id']=asset_owner['asset_id'] if asset_owner else '__static_platform';o['geometry_atlas']=atlas;o['web_kind']=k;o['web_export']=True;o['source_node']=old.name
        o['bake_atlas']=atlas if k=='baked' else -1
        for i,m in enumerate(list(data.materials)):
            if k=='baked':data.materials[i]=frozen_material(m,atlas,cache)
        parts.append(o)
    # Offline atrium still contributes its original daylight bounce and window
    # shadows while baking, but never enters the selected web export.
    context=[]
    for old in source.objects:
        if old in selected or old.type=='CAMERA':continue
        s.collection.objects.link(old);context.append(old.name)
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    buckets={}
    for o in parts:buckets.setdefault((o['owner_asset_id'],o['web_kind'],o['geometry_atlas']),[]).append(o)
    root_by_id={o['asset_id']:o for o in copies.values()};root_by_id['__static_platform']=static;meshes=[]
    for (identity,k,atlas),members in buckets.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in members:o.select_set(True)
        bpy.context.view_layer.objects.active=members[0]
        count=sum(triangles(o) for o in members)
        if len(members)>1:bpy.ops.object.join()
        o=bpy.context.object;o.name='ATELIER_WEB_'+identity+'__'+k
        reparent(o,root_by_id[identity]);assert triangles(o)==count
        o['source_nodes_count']=len(members);meshes.append(o)
    atlas_reports=[]
    for atlas in range(4):
        ms=[o for o in meshes if o['web_kind']=='baked' and o['bake_atlas']==atlas]
        bpy.ops.object.select_all(action='DESELECT')
        for o in ms:
            uv=o.data.uv_layers.new(name='BakeUV',do_init=False);o.data.uv_layers.active=uv;uv.active_render=True;o.select_set(True)
        bpy.context.view_layer.objects.active=ms[0]
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.0025,area_weight=.25,correct_aspect=True,scale_to_bounds=True)
        bpy.ops.object.mode_set(mode='OBJECT')
        im=bpy.data.images.new('ATELIER_BAKE_ATLAS_'+str(atlas),width=SIZE,height=SIZE,alpha=False,float_buffer=True);im.colorspace_settings.name='Linear Rec.709'
        for m in {m for o in ms for m in o.data.materials}:
            for n in m.node_tree.nodes:n.select=False
            n=m.node_tree.nodes.new('ShaderNodeTexImage');n.name=TARGET;n.image=im;n.select=True;m.node_tree.nodes.active=n
        atlas_reports.append({'atlas':atlas,'resolution':[SIZE,SIZE],'meshes':len(ms),'triangles':sum(triangles(o) for o in ms)})
        print('ATELIER_UV_READY',atlas,flush=True)
    bpy.context.view_layer.update()
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    bounds={'min':[min(v[i] for v in points) for i in range(3)],'max':[max(v[i] for v in points) for i in range(3)]}
    pid=hashlib.sha256((source_sha+str(time.time_ns())).encode()).hexdigest();s['preparation_id']=pid
    report={'source':rel(SOURCE),'sourceSha256':source_sha,'prepared':rel(PREPARED),'preparation_id':pid,'asset_count':len(roots),'asset_ids':sorted(hierarchy),'asset_hierarchy':hierarchy,'mesh_count':len(meshes),'triangles':sum(triangles(o) for o in meshes),'atlases':atlas_reports,'boundsBlender':bounds,'context_objects':context,'sourceFileUnchanged':sha(SOURCE)==source_sha,'geometryOptimization':'Bevel rings capped at 2 and curve bevel_resolution at 2; no asset removed or decimation','proceduralCoordinates':'Original local positions and split normals retained in named mesh attributes before joins. Original explicit three-FLAT walnut shader preserved. Other BOX maps converted to equivalent explicit source-local triplanar projection.','seconds':round(time.monotonic()-started,2)}
    s['preparation_report']=json.dumps(report);REPORTS.mkdir(parents=True,exist_ok=True)
    bpy.data.libraries.write(str(PREPARED),{s},fake_user=True,compress=True);write_json(REPORTS/'preparation-report.json',report)
    print('ATELIER_PREPARED',json.dumps({k:report[k] for k in ('triangles','mesh_count','asset_count','seconds')}),flush=True)

def load_prepared():
    bpy.ops.wm.open_mainfile(filepath=str(PREPARED));s=bpy.data.scenes[SCENE];bpy.context.window.scene=s;return s
def device(s):
    p=bpy.context.preferences.addons['cycles'].preferences
    try:
        p.compute_device_type='METAL';p.get_devices()
        for d in p.devices:d.use=d.type=='METAL'
        s.cycles.device='GPU' if any(d.type=='METAL' for d in p.devices) else 'CPU'
    except Exception:s.cycles.device='CPU'
    return s.cycles.device
def bake(indices):
    s=load_prepared();device(s);TEXTURES.mkdir(parents=True,exist_ok=True)
    manifest={'complete':False,'state':'day','preparation_id':s['preparation_id'],'samples':32,'atlases':[]}
    path=TEXTURES/'day-manifest.json'
    if path.exists():
        old=json.loads(path.read_text())
        if old.get('preparation_id')==s['preparation_id']:manifest=old
    for atlas in indices:
        started=time.monotonic();ms=[o for o in s.objects if o.get('web_export') and o.type=='MESH' and o.get('bake_atlas')==atlas]
        bpy.ops.object.select_all(action='DESELECT');proxies=[]
        for o in ms:
            q=o.copy();q.data=o.data.copy();s.collection.objects.link(q);reparent(q,None);q.select_set(True);proxies.append(q);o.hide_render=True
        bpy.context.view_layer.objects.active=proxies[0]
        bpy.ops.object.join();proxy=bpy.context.object
        image=bpy.data.images['ATELIER_BAKE_ATLAS_'+str(atlas)]
        for m in proxy.data.materials:m.node_tree.nodes.active=m.node_tree.nodes[TARGET]
        print('ATELIER_BAKE_START',atlas,s.cycles.device,flush=True)
        bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=16,use_clear=True,use_selected_to_active=False)
        out=TEXTURES/('day-%d.png'%atlas);image.save_render(str(out),scene=s)
        record={'atlas':atlas,'resolution':[SIZE,SIZE],'path':rel(out),'bytes':out.stat().st_size,'sha256':sha(out),'seconds':round(time.monotonic()-started,2)}
        manifest['atlases']=[r for r in manifest['atlases'] if r['atlas']!=atlas]+[record]
        manifest['complete']=len(manifest['atlases'])==4;write_json(path,manifest)
        bpy.data.objects.remove(proxy,do_unlink=True)
        for o in ms:o.hide_render=False
        print('ATELIER_BAKE_DONE',json.dumps(record),flush=True)

def export():
    s=load_prepared();manifest=json.loads((TEXTURES/'day-manifest.json').read_text());assert manifest['complete'] and manifest['preparation_id']==s['preparation_id']
    prep=json.loads((REPORTS/'preparation-report.json').read_text())
    assert sha(SOURCE)==prep['sourceSha256'],'Editable source changed after preparation'
    assert {r['atlas'] for r in manifest['atlases']}==set(range(4))
    for record in manifest['atlases']:
        p=TEXTURES/('day-%d.png'%record['atlas'])
        assert sha(p)==record['sha256'] and p.stat().st_size==record['bytes'],'Stale bake atlas'
        assert struct.unpack_from('>II',p.read_bytes(),16)==(SIZE,SIZE)
    environment=TEXTURES/'landscape';environment.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'assets/textures/about-atelier-v3/landscape/lake_pier_2k.hdr',environment/'lake_pier_2k.hdr')
    shutil.copy2(ROOT/'assets/textures/about-atelier-v3/landscape/manifest.json',environment/'source-manifest.json')
    cache={}
    for atlas in range(4):
        im=bpy.data.images.load(str(TEXTURES/('day-%d.png'%atlas)));im.colorspace_settings.name='sRGB'
        m=bpy.data.materials.new('ATELIER_LIGHTMAP_'+str(atlas));m.use_nodes=True;m.node_tree.nodes.clear()
        nodes,links=m.node_tree.nodes,m.node_tree.links
        out=nodes.new('ShaderNodeOutputMaterial');e=nodes.new('ShaderNodeEmission');t=nodes.new('ShaderNodeTexImage');t.image=im
        uv=nodes.new('ShaderNodeUVMap');uv.uv_map='BakeUV';links.new(uv.outputs[0],t.inputs['Vector']);links.new(t.outputs['Color'],e.inputs['Color']);links.new(e.outputs[0],out.inputs[0]);cache['baked'+str(atlas)]=m
    bpy.ops.object.select_all(action='DESELECT')
    for o in s.objects:
        if not o.get('web_export') or o.type not in {'MESH','EMPTY'}:continue
        o.select_set(True)
        if o.type=='EMPTY':continue
        k=o['web_kind']
        if k=='baked':m=cache['baked'+str(o['bake_atlas'])]
        else:
            original=o.data.materials[0];key=original.name
            if key not in cache:
                p=principle(original);m=bpy.data.materials.new('ATELIER_GLASS' if k=='glass' else 'ATELIER_METAL_'+key.removeprefix('ATELIER_V3_'));m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF')
                for name in ('Base Color','Metallic','Roughness','Transmission Weight','IOR'):
                    n.inputs[name].default_value=p.inputs[name].default_value
                if k=='glass':n.inputs['Roughness'].default_value=.055
                else:
                    # Original procedural roughness is centred at .24.
                    n.inputs['Roughness'].default_value=.24
                cache[key]=m
            m=cache[key]
        o.data.materials.clear();o.data.materials.append(m)
        for p in o.data.polygons:p.material_index=0
        for a in list(o.data.attributes):
            if a.name in {POS,NORMAL}:o.data.attributes.remove(a)
        if k=='baked':
            for uv in list(o.data.uv_layers):
                if uv.name!='BakeUV':o.data.uv_layers.remove(uv)
        for key in ('source_node','source_nodes_count'):
            if key in o:del o[key]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    pending=OUTPUT.with_name('.about-atelier-v3.pending.glb')
    bpy.ops.export_scene.gltf(filepath=str(pending),export_format='GLB',use_selection=True,export_extras=True,export_yup=True,export_cameras=False,export_lights=False,export_materials='EXPORT',export_normals=True,export_texcoords=True)
    # Inject provenance on the GLB asset without touching geometry or images.
    blob=pending.read_bytes();jlen,jtype=struct.unpack_from('<II',blob,12);doc=json.loads(blob[20:20+jlen]);remaining=blob[20+jlen:]
    for m in doc['materials']:
        if not m['name'].startswith('ATELIER_LIGHTMAP_'):continue
        texture=m.get('pbrMetallicRoughness',{}).get('baseColorTexture') or m.get('emissiveTexture')
        assert texture,m['name']
        m['pbrMetallicRoughness']={'baseColorTexture':texture,'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1}
        for key in ('emissiveTexture','emissiveFactor','normalTexture','occlusionTexture'):m.pop(key,None)
        m['extensions']={'KHR_materials_unlit':{}};m['doubleSided']=True
    for key in ('extensionsUsed','extensionsRequired'):
        doc.setdefault(key,[])
        if 'KHR_materials_unlit' not in doc[key]:doc[key].append('KHR_materials_unlit')
    doc['asset']['extras']={'preparation_id':s['preparation_id'],'source':rel(SOURCE),'sourceSha256':sha(SOURCE),'bake':'daylight Cycles COMBINED, AgX, 32 samples'}
    js=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();js+=b' '*(-len(js)%4)
    pending.write_bytes(struct.pack('<III',0x46546c67,2,20+len(js)+len(remaining))+struct.pack('<II',len(js),jtype)+js+remaining);pending.replace(OUTPUT)
    ids=[n['extras']['asset_id'] for n in doc['nodes'] if n.get('extras',{}).get('asset_id')]
    assert sorted(ids)==prep['asset_ids'] and len(ids)==128
    b=prep['boundsBlender'];gltf_bounds={'min':[b['min'][0],b['min'][2],-b['max'][1]],'max':[b['max'][0],b['max'][2],-b['min'][1]]}
    report={'complete':True,'source':rel(SOURCE),'sourceSha256':sha(SOURCE),'sourceUnchanged':sha(SOURCE)==prep['sourceSha256'],'model':rel(OUTPUT),'bytes':OUTPUT.stat().st_size,'sha256':sha(OUTPUT),'preparation_id':s['preparation_id'],'assetCount':len(ids),'assetIds':sorted(ids),'nodes':len(doc['nodes']),'meshes':len(doc['meshes']),'materials':[m['name'] for m in doc['materials']],'triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),'drawPrimitives':sum(len(m['primitives']) for m in doc['meshes']),'boundsGltf':gltf_bounds,'boundsBlender':b,'atlasTextures':manifest['atlases'],'runtimeContract':{'units':'metres','up':'Y','sourceToGltf':'(x,y,z) -> (x,z,-y)','rootIdentity':'node.extras.asset_id','interaction':'node.extras.interaction / interactive','lightmapMaterial':'ATELIER_LIGHTMAP_0..3, KHR_materials_unlit, toneMapped=false','glass':'ATELIER_GLASS; PBR transmission=1, IOR=1.46; renderer may use its established optimized transparent-glass path','metal':'ATELIER_METAL_SatinBrass and ATELIER_METAL_BrushedSteel; PBR, metallic=1, roughness=.24; provide environment reflections','lighting':'Daylight baked on opaque surfaces; runtime dimming can modulate unlit colour, not true night relighting'},'sources':['assets/textures/about-atelier-v3/README.md','assets/textures/about-atelier-v3/texture-manifest.json','assets/textures/about-atelier-v3/landscape/manifest.json','assets/font-candidates/v4/douyin-upstream/DouyinSans/OFL.txt']}
    write_json(REPORTS/'export-report.json',report);print('ATELIER_EXPORT_DONE',json.dumps(report),flush=True)

if __name__=='__main__':
    assert bpy.app.background,'Do not run in an interactive Blender session.'
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=('prepare','bake','export','all'),default='all');parser.add_argument('--indices',type=int,nargs='+',default=list(range(4)))
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.stage in {'prepare','all'}:prepare()
    if a.stage in {'bake','all'}:bake(a.indices)
    if a.stage in {'export','all'}:export()
