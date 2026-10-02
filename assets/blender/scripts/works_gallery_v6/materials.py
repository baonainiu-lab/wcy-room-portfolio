"""Comprehensive V6 physical materials. Invoked through Blender MCP only.

Retains source geometry, UVs, materials slots, lighting and all asset IDs.
The approved About scene is an immutable texture-library dependency only.
"""
import importlib.util, json, hashlib, sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'assets/blender/works-gallery-v6'
TEX = ROOT/'assets/textures/about-atelier-v3'
spec=importlib.util.spec_from_file_location('gallery_v5_helpers',ROOT/'assets/blender/scripts/works_gallery_v5/refine_materials.py')
lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)

def color(h):
    c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)+(1,)

def range_socket(t,s,lo,hi):
    n=t.nodes.new('ShaderNodeMapRange');n.inputs['To Min'].default_value=lo;n.inputs['To Max'].default_value=hi
    t.links.new(s,n.inputs['Value']);return n.outputs[0]

def noise(t,scale,detail=3):
    geo=t.nodes.new('ShaderNodeNewGeometry');v=t.nodes.new('ShaderNodeVectorMath');v.operation='MULTIPLY'
    v.inputs[1].default_value=scale;t.links.new(geo.outputs['Position'],v.inputs[0])
    n=t.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=1;n.inputs['Detail'].default_value=detail
    t.links.new(v.outputs[0],n.inputs['Vector']);return n.outputs['Fac']

def bump(t,p,height,distance,strength=.4):
    n=t.nodes.new('ShaderNodeBump');n.inputs['Distance'].default_value=distance;n.inputs['Strength'].default_value=strength
    t.links.new(height,n.inputs['Height']);t.links.new(n.outputs[0],p.inputs['Normal'])

def vary_color(t,p,s,base,lo=.86,hi=1.08):
    n=t.nodes.new('ShaderNodeMixRGB');n.blend_type='MULTIPLY';n.inputs[0].default_value=1;n.inputs[1].default_value=base
    t.links.new(range_socket(t,s,lo,hi),n.inputs[2]);t.links.new(n.outputs[0],p.inputs['Base Color'])

def modify(m):
    name=m.get('source_material',m.name)
    if not str(name).startswith('GALLERY_'):return None
    kind=name.removeprefix('GALLERY_').split('.')[0]
    t=m.node_tree
    target=t.nodes.get('GALLERY_BAKE_TARGET');target_image=target.image if target else None
    t.nodes.clear();out=t.nodes.new('ShaderNodeOutputMaterial');p=t.nodes.new('ShaderNodeBsdfPrincipled')
    t.links.new(p.outputs[0],out.inputs['Surface']);p.inputs['IOR'].default_value=1.48
    p.inputs['Metallic'].default_value=0;p.inputs['Roughness'].default_value=.5
    desc='';dist=0
    if kind in ('silver','bronze'):
        base=color('C8D0D3' if kind=='silver' else 'C9A572')
        p.inputs['Base Color'].default_value=base;p.inputs['Metallic'].default_value=1
        grain=noise(t,(12,850,850));macro=noise(t,(4,4,4),2)
        t.links.new(range_socket(t,grain,.18 if kind=='silver' else .23,.38),p.inputs['Roughness'])
        vary_color(t,p,macro,base,.88,1.03);dist=.00009;bump(t,p,grain,dist,.3)
        anisotropic=p.inputs.get('Anisotropic IOR Level') or p.inputs.get('Anisotropic')
        if anisotropic:anisotropic.default_value=.42
        desc='Fine directional brushed aluminium' if kind=='silver' else 'Satin champagne brass, directional machining'
    elif kind in ('navy','black','ink'):
        base=color({'navy':'243844','black':'171D20','ink':'22252A'}[kind]);p.inputs['Base Color'].default_value=base
        grain=noise(t,(180,180,180));macro=noise(t,(5,5,5),2)
        lo,hi=(.28,.42) if kind=='navy' else (.52,.76) if kind=='black' else (.4,.58)
        t.links.new(range_socket(t,grain,lo,hi),p.inputs['Roughness']);vary_color(t,p,macro,base,.85,1.1)
        dist=.00012 if kind=='navy' else .00023;bump(t,p,grain,dist,.28)
        desc={'navy':'Midnight petrol powder-coated aluminium, orange-peel finish','black':'Dense soft-touch rubber and dark hardware','ink':'Matte pigment and archival ink'}[kind]
    elif kind in ('terrazzo','leather'):
        files=lib.MAPS[kind];coordinate=lib.triplanar(t,1.35 if kind=='terrazzo' else 2.0)
        albedo=lib.image(t,files[0],coordinate,True);rough=lib.image(t,files[1],coordinate,False);height=lib.image(t,files[2],coordinate,False)
        mul=t.nodes.new('ShaderNodeVectorMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=(1.08,1.055,1.0) if kind=='terrazzo' else (1.6,1.38,1.15)
        t.links.new(albedo,mul.inputs[0]);t.links.new(mul.outputs[0],p.inputs['Base Color'])
        t.links.new(range_socket(t,rough,.28 if kind=='terrazzo' else .32,.53 if kind=='terrazzo' else .66),p.inputs['Roughness'])
        dist=.00065 if kind=='terrazzo' else .0013;bump(t,p,height,dist,.5)
        if kind=='leather':p.inputs['Sheen Weight'].default_value=.12
        desc='Honed warm mineral terrazzo with photographed aggregate' if kind=='terrazzo' else 'Full-grain cognac saddle leather, photographed pores and folds'
    elif kind=='ivory':
        base=color('DFDACE');p.inputs['Base Color'].default_value=base
        fine=noise(t,(480,480,480));coarse=noise(t,(9,9,9),2)
        t.links.new(range_socket(t,fine,.20,.34),p.inputs['Roughness']);vary_color(t,p,coarse,base,.94,1.04)
        dist=.00006;bump(t,p,fine,dist,.18);desc='Satin glazed warm porcelain, restrained microscopic pores'
    elif kind=='paper':
        base=color('E4DDCF');fine=noise(t,(320,420,120));p.inputs['Base Color'].default_value=base
        vary_color(t,p,fine,base,.89,1.03);t.links.new(range_socket(t,fine,.72,.9),p.inputs['Roughness'])
        dist=.00018;bump(t,p,fine,dist,.4);p.inputs['Sheen Weight'].default_value=.1;desc='Uncoated cotton archival paper with visible fibre tooth'
    elif kind=='leaf':
        fine=noise(t,(65,240,65));macro=noise(t,(14,14,14))
        ramp=t.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=color('17372A');ramp.color_ramp.elements[1].color=color('567440')
        t.links.new(macro,ramp.inputs[0]);t.links.new(ramp.outputs['Color'],p.inputs['Base Color'])
        t.links.new(range_socket(t,fine,.3,.53),p.inputs['Roughness']);dist=.00024;bump(t,p,fine,dist,.28)
        desc='Botanical waxy leaves, restrained chlorophyll variation and vein relief'
    elif kind=='soil':
        fine=noise(t,(75,75,75));vary_color(t,p,fine,color('30271F'),.35,1.4)
        p.inputs['Roughness'].default_value=.95;dist=.002;bump(t,p,fine,dist,.7);desc='Granular dark mineral potting soil'
    elif kind in ('glass','ARCH_GLASS_PBR','v4_glass_edge_trim'):
        p.inputs['Base Color'].default_value=color('ECF5F3');p.inputs['Transmission Weight'].default_value=1
        p.inputs['IOR'].default_value=1.50;p.inputs['Roughness'].default_value=.045 if kind!='v4_glass_edge_trim' else .075
        desc='Low-iron optical glass, dielectric Fresnel and polished edges'
    elif kind=='warm':
        p.inputs['Base Color'].default_value=color('EEE0C0');p.inputs['Emission Color'].default_value=color('FFD09A')
        p.inputs['Emission Strength'].default_value=1.2;p.inputs['Roughness'].default_value=.32
        desc='Warm diffusing luminaire lens; day/night emission controlled by existing lighting'
    else:raise RuntimeError('Unmapped material: '+name)
    if target_image:
        target=t.nodes.new('ShaderNodeTexImage');target.name='GALLERY_BAKE_TARGET';target.image=target_image
        uv=t.nodes.new('ShaderNodeUVMap');uv.uv_map='BakeUV';t.links.new(uv.outputs[0],target.inputs[0]);t.nodes.active=target
    m['physical_revision']='Gallery V6';m['physical_family']=kind;m['physical_description']=desc
    m['physical_bump_metres']=dist;m['coordinates']='world metres; explicit normalized triplanar sampling'
    return {'name':m.name,'family':kind,'description':desc,'bumpMetres':dist}

def prepare_current():
    path=Path(bpy.data.filepath);prepared=path.name=='works-gallery-bake-v5.blend'
    assert path.name in ('works-gallery-v5.blend','works-gallery-bake-v5.blend')
    oldsha=lib.sha(path);s=bpy.context.scene;before=lib.geometry(s);oldlights=lib.lights(s)
    materials={m for o in s.objects if hasattr(o.data,'materials') for m in o.data.materials if m}
    records=[modify(m) for m in sorted(materials,key=lambda m:m.name)];records=[r for r in records if r]
    assert lib.geometry(s)==before and lib.lights(s)==oldlights
    target=ROOT/'assets/blender'/('works-gallery-bake-v6.blend' if prepared else 'works-gallery-v6.blend')
    assert not target.exists(),'Versioned derivative already exists'
    s['physical_material_revision']=6;s['source_blend']=str(ROOT/'assets/blender/works-gallery-v6.blend')
    if prepared:s['preparation_id']=hashlib.sha256((s['preparation_id']+'V6'+lib.sha(Path(__file__))).encode()).hexdigest()
    bpy.data.libraries.write(str(target),{s},fake_user=True,compress=True)
    OUT.mkdir(parents=True,exist_ok=True)
    report={'complete':True,'via':'Blender MCP isolated file operation','source':lib.relative(path),'sourceSha256':oldsha,'output':lib.relative(target),'outputSha256':lib.sha(target),'geometrySha256':before,'geometryUnchanged':True,'lightingUnchanged':True,'materials':records,'allUsedMaterialFamiliesCovered':True,'textureLicenseManifest':'assets/textures/about-atelier-v3/texture-manifest.json','preparation_id':s.get('preparation_id')}
    assert lib.sha(path)==oldsha
    (OUT/('prepared-materials.json' if prepared else 'source-materials.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return {'output':str(target),'materials':len(records),'families':sorted({r['family'] for r in records}),'geometryUnchanged':True}

def preview_current(state='day'):
    assert Path(bpy.data.filepath).name=='works-gallery-v6.blend'
    sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
    from gallery_build import set_lighting
    import bake_gallery as util
    from mathutils import Vector
    s=bpy.context.scene;set_lighting(s,state);s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;util._device(s)
    c=s.camera;c.location=(4.2,-5.7,3.3);c.rotation_euler=(Vector((.5,-1.9,.7))-c.location).to_track_quat('-Z','Y').to_euler();c.data.lens=57
    s.render.resolution_x=1400;s.render.resolution_y=960;s.render.resolution_percentage=100
    s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
    s.render.image_settings.file_format='PNG';path=ROOT/'renders/works-gallery-v6'/('materials-'+state+'.png');path.parent.mkdir(parents=True,exist_ok=True);s.render.filepath=str(path)
    import fcntl
    with open('/tmp/room-portfolio-blender-gpu.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);bpy.ops.render.render(write_still=True)
    return {'image':str(path),'samples':32,'state':state,'actualBlenderRender':True}
