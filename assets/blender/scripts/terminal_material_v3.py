"""Run only through the Blender MCP file-targeted tool; never opens the UI project.
Material-only derivative of the 27-mesh terminal, with an extra SurfaceUV atlas.
"""
import bpy, json, hashlib, array, time, fcntl, math
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE=ROOT/'assets/blender/welcome-terminal-v2.blend'
PREP=ROOT/'assets/blender/welcome-terminal-v3-material-source.blend'
FINAL=ROOT/'assets/blender/welcome-terminal-v3.blend'
OUT=ROOT/'public/textures/welcome-terminal-v3'; OUT.mkdir(parents=True,exist_ok=True)
REPORT=ROOT/'assets/blender/welcome-terminal-v3-material-report.json'
SCREEN='TERMINAL_OriginalScreenArtwork'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def geometry_state():
    records=[]
    for o in sorted((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:o.name):
        mesh=o.data;h=hashlib.sha256()
        for col,attr,width in [(mesh.vertices,'co',3),(mesh.loops,'vertex_index',1),(mesh.corner_normals,'vector',3),(mesh.uv_layers['UVMap'].data,'uv',2)]:
            values=array.array('i' if attr=='vertex_index' else 'f',[0])*(len(col)*width);col.foreach_get(attr,values);h.update(values.tobytes())
        h.update(json.dumps([(p.loop_start,p.loop_total,p.material_index,p.use_smooth)for p in mesh.polygons]).encode())
        records.append({'name':o.name,'hash':h.hexdigest(),'parent':o.parent.name if o.parent else None,'matrix':[list(r)for r in o.matrix_local],'vertices':len(mesh.vertices),'triangles':len(mesh.polygons)})
    return records

def record(**values):
    old=json.loads(REPORT.read_text())if REPORT.exists()else{}
    old.update(values);REPORT.write_text(json.dumps(old,indent=2,ensure_ascii=False)+'\n');return old

def material_sources(m):
    n=m.node_tree.nodes;l=m.node_tree.links;p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
    if m.name==SCREEN:
        p.inputs['Roughness'].default_value=.115;p.inputs['Specular IOR Level'].default_value=.18;p.inputs['Coat Weight'].default_value=.12;p.inputs['Coat Roughness'].default_value=.06
        return
    styles={
      'TERMINAL_DeepBlue_Enamel':(.8,.23,.36,.003,.11),
      'TERMINAL_SatinTitanium':(.96,.19,.34,.0028,.035),
      'TERMINAL_DarkRubber':(0,.57,.78,.005,.0),
      'TERMINAL_WarmTrace':(.95,.19,.31,.0018,.05),
      'TERMINAL_IvoryCeramic':(0,.2,.33,.0011,.32),
      'TERMINAL_Vermilion':(0,.24,.38,.002,.3),
    }
    metallic,rmin,rmax,distance,coat=styles[m.name]
    p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=(rmin+rmax)/2
    p.inputs['Coat Weight'].default_value=coat;p.inputs['Coat Roughness'].default_value=.14 if coat else .25
    c=n.new('ShaderNodeTexCoord');c.name='V3 source object coordinates'
    v=n.new('ShaderNodeVectorMath');v.operation='MULTIPLY';v.name='V3 physical grain direction'
    brushed=m.name in ['TERMINAL_SatinTitanium','TERMINAL_WarmTrace','TERMINAL_DeepBlue_Enamel']
    v.inputs[1].default_value=(1,32,3) if brushed else (1,1,1);l.new(c.outputs['Object'],v.inputs[0])
    grain=n.new('ShaderNodeTexNoise');grain.name='V3 metal grain'if brushed else'V3 surface pores'
    grain.inputs['Scale'].default_value=13 if brushed else 145;grain.inputs['Detail'].default_value=2;grain.inputs['Roughness'].default_value=.68;l.new(v.outputs['Vector'],grain.inputs['Vector'])
    range_node=n.new('ShaderNodeMapRange');range_node.name='V3 authored roughness';range_node.inputs['From Min'].default_value=.2;range_node.inputs['From Max'].default_value=.8;range_node.inputs['To Min'].default_value=rmin;range_node.inputs['To Max'].default_value=rmax;l.new(grain.outputs['Fac'],range_node.inputs['Value']);l.new(range_node.outputs['Result'],p.inputs['Roughness'])
    fine=n.new('ShaderNodeTexNoise');fine.name='V3 fine finish';fine.inputs['Scale'].default_value=220;fine.inputs['Detail'].default_value=1;l.new(c.outputs['Object'],fine.inputs['Vector'])
    mix=n.new('ShaderNodeMixRGB');mix.name='V3 layered micro height';mix.blend_type='MIX';mix.inputs[0].default_value=.2;l.new(grain.outputs['Fac'],mix.inputs[1]);l.new(fine.outputs['Fac'],mix.inputs[2])
    bump=n.new('ShaderNodeBump');bump.name='V3 micron finish';bump.inputs['Strength'].default_value=.24 if brushed else .19;bump.inputs['Distance'].default_value=distance;l.new(mix.outputs['Color'],bump.inputs['Height']);l.new(bump.outputs['Normal'],p.inputs['Normal'])
    col=n.new('ShaderNodeMixRGB');col.name='V3 subtle body tint';col.blend_type='MULTIPLY';col.inputs[0].default_value=.075;col.inputs[1].default_value=p.inputs['Base Color'].default_value[:];l.new(fine.outputs['Fac'],col.inputs[2]);l.new(col.outputs['Color'],p.inputs['Base Color'])
    m['v3_finish']='Object-scale layered material baked into SurfaceUV; original base color retained with 7.5% micro variation'
    m['v3_roughness_range']=[rmin,rmax];m['v3_bump_distance']=distance

def prepare():
    assert Path(bpy.data.filepath)==SOURCE
    scene=bpy.context.scene;scene.frame_set(1);before=geometry_state();assert len(before)==27
    meshes=[o for o in scene.objects if o.type=='MESH' and all(m is None or m.name!=SCREEN for m in o.data.materials)]
    assert len(meshes)==26
    for o in meshes:
        uv=o.data.uv_layers.new(name='SurfaceUV');o.data.uv_layers.active=uv
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.12,island_margin=.008,area_weight=.0,correct_aspect=True,scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True,scale=True,merge_overlap=False,margin_method='FRACTION',margin=.006)
    bpy.ops.object.mode_set(mode='OBJECT')
    for m in bpy.data.materials:material_sources(m)
    scene.name='WELCOME_TERMINAL_V3';scene['material_revision']=3;scene['authoring_method']='Blender MCP file-targeted execution; material graphs and real UV bakes; no geometry modeling'
    after=geometry_state();assert before==after,'Original geometry, normals, UVMap or rest pose changed'
    bpy.ops.wm.save_as_mainfile(filepath=str(PREP),check_existing=False)
    return record(stage='prepared',source=str(SOURCE.relative_to(ROOT)),sourceSha256=digest(SOURCE),prepared=str(PREP.relative_to(ROOT)),preparedSha256=digest(PREP),originalGeometry=before,geometryNormalsOriginalUVsUnchanged=True,addedUV='SurfaceUV',meshCount=27,materialCount=7,surfaceAtlasSize=2048,productionMethod='Blender MCP execute_blender_code_for_cli file-targeted tool; interactive courtyard never opened or modified; material-only script assistance accurately recorded',license='Project-authored procedural finish nodes; existing original screen artwork unchanged; no downloaded third-party material used')

def configure_gpu():
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=False
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='METAL'
    scene.cycles.device='GPU';return scene

def refine_surface_uv():
    """Reserve texture area for fine ceramic dial engravings, retaining UV0."""
    assert Path(bpy.data.filepath)==PREP
    before=geometry_state()
    o=bpy.data.objects['terminal.v2.dial.ivoryceramic']
    for loop in o.data.uv_layers['SurfaceUV'].data:loop.uv*=12
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'and 'SurfaceUV'in o.data.uv_layers]
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True);o.data.uv_layers.active=o.data.uv_layers['SurfaceUV']
    bpy.context.view_layer.objects.active=meshes[0]
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True,scale=True,merge_overlap=False,margin_method='FRACTION',margin=.006)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert geometry_state()==before
    bpy.ops.wm.save_as_mainfile(filepath=str(PREP),check_existing=False)
    return record(stage='prepared',preparedSha256=digest(PREP),surfaceUVRevision=2,detailUVNote='Ceramic dial micro-engraving islands receive 12x UV edge scale before atlas repack, preventing subpixel empty bake coverage; original UV0 unchanged',bakes={})

def bake(channel):
    assert Path(bpy.data.filepath)==PREP;assert channel in ['basecolor','orm','normal']
    scene=configure_gpu();before=geometry_state();scene.frame_set(1)
    mats=[m for m in bpy.data.materials if m.name!=SCREEN];objects=[o for o in scene.objects if o.type=='MESH' and any(m in mats for m in o.data.materials)]
    image=bpy.data.images.new('TerminalV3_'+channel,width=2048,height=2048,alpha=True,float_buffer=True)
    image.colorspace_settings.name='sRGB'if channel=='basecolor'else'Non-Color'
    for m in mats:
        n=m.node_tree.nodes;l=m.node_tree.links;p=next(x for x in n if x.type=='BSDF_PRINCIPLED');out=next(x for x in n if x.type=='OUTPUT_MATERIAL')
        target=n.new('ShaderNodeTexImage');target.name='V3 BAKE TARGET';target.image=image;n.active=target
        if channel!='normal':
            emit=n.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=1
            if channel=='basecolor':l.new(p.inputs['Base Color'].links[0].from_socket,emit.inputs['Color'])
            else:
                combine=n.new('ShaderNodeCombineColor');combine.mode='RGB';combine.inputs['Red'].default_value=1;l.new(p.inputs['Roughness'].links[0].from_socket,combine.inputs['Green']);combine.inputs['Blue'].default_value=p.inputs['Metallic'].default_value;l.new(combine.outputs[0],emit.inputs['Color'])
            l.new(emit.outputs[0],out.inputs['Surface'])
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True);o.data.uv_layers.active=o.data.uv_layers['SurfaceUV']
    bpy.context.view_layer.objects.active=objects[0]
    started=time.monotonic()
    with open('/tmp/room-portfolio-blender-gpu.lock','w')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        bpy.ops.object.bake(type='NORMAL'if channel=='normal'else'EMIT',normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',uv_layer='SurfaceUV',margin=12,margin_type='EXTEND',use_clear=True,use_selected_to_active=False)
        image.file_format='PNG';image.filepath_raw=str(OUT/(channel+'.png'));image.save()
        fcntl.flock(lock,fcntl.LOCK_UN)
    assert geometry_state()==before
    report=json.loads(REPORT.read_text());channels=report.get('bakes',{});channels[channel]={'path':str((OUT/(channel+'.png')).relative_to(ROOT)),'sha256':digest(OUT/(channel+'.png')),'size':[2048,2048],'samples':16,'kind':'TANGENT_NORMAL'if channel=='normal'else'EMIT_data','seconds':round(time.monotonic()-started,2),'sourceSha256':digest(PREP)}
    record(stage='baking',bakes=channels)
    return channels[channel]

def finish():
    assert Path(bpy.data.filepath)==PREP;before=geometry_state()
    proof=json.loads(REPORT.read_text());assert set(proof['bakes'])=={'basecolor','orm','normal'}
    for channel,entry in proof['bakes'].items():
        assert entry['sourceSha256']==digest(PREP) and entry['sha256']==digest(OUT/(channel+'.png')),'Stale material bake'
    images={}
    for ch in ['basecolor','orm','normal']:
        images[ch]=bpy.data.images.load(str(OUT/(ch+'.png')),check_existing=False);images[ch].colorspace_settings.name='sRGB'if ch=='basecolor'else'Non-Color';images[ch].pack()
    for m in bpy.data.materials:
        if m.name==SCREEN:continue
        n=m.node_tree.nodes;l=m.node_tree.links;p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
        uv=n.new('ShaderNodeUVMap');uv.uv_map='SurfaceUV';uv.name='V3 runtime SurfaceUV'
        tex={}
        for ch,image in images.items():
            tex[ch]=n.new('ShaderNodeTexImage');tex[ch].image=image;tex[ch].name='V3 baked '+ch;l.new(uv.outputs['UV'],tex[ch].inputs['Vector'])
        l.new(tex['basecolor'].outputs['Color'],p.inputs['Base Color'])
        sep=n.new('ShaderNodeSeparateColor');l.new(tex['orm'].outputs['Color'],sep.inputs['Color']);l.new(sep.outputs['Green'],p.inputs['Roughness']);l.new(sep.outputs['Blue'],p.inputs['Metallic'])
        normal=n.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.uv_map='SurfaceUV';normal.inputs['Strength'].default_value=1;l.new(tex['normal'].outputs['Color'],normal.inputs['Color']);l.new(normal.outputs['Normal'],p.inputs['Normal'])
    for o in bpy.context.scene.objects:
        if o.type=='MESH':o.data.uv_layers.active=o.data.uv_layers['UVMap'];o.data.uv_layers['UVMap'].active_render=True
    assert geometry_state()==before
    bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(FINAL),check_existing=False)
    target=ROOT/'public/models/welcome-terminal-v3.glb'
    bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',export_extras=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name='TerminalUnfold',export_current_frame=True,export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False,export_texcoords=True,export_normals=True,export_tangents=False,export_apply=False)
    return record(stage='exported',finalSource=str(FINAL.relative_to(ROOT)),finalSourceSha256=digest(FINAL),model=str(target.relative_to(ROOT)),modelSha256=digest(target),modelBytes=target.stat().st_size,sourceV2Unchanged=digest(SOURCE)==json.loads(REPORT.read_text())['sourceSha256'])

def preview():
    assert Path(bpy.data.filepath)==FINAL;scene=configure_gpu();scene.cycles.samples=64;scene.cycles.use_denoising=True
    scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
    path=ROOT/'renders/welcome-terminal-v3-materials.png';scene.render.filepath=str(path);scene.render.image_settings.file_format='PNG';scene.frame_set(1)
    with open('/tmp/room-portfolio-blender-gpu.lock','w')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);bpy.ops.render.render(write_still=True);fcntl.flock(lock,fcntl.LOCK_UN)
    return {'path':str(path),'sha256':digest(path),'samples':64,'method':'MCP file-targeted Blender Cycles preview; not browser WebGL'}
