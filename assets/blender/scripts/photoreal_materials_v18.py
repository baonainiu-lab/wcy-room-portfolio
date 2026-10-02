"""Comprehensive Room V18 source material replacement, invoked via Blender MCP.

No action runs on import. Open the desired V16 file using the file-targeted MCP
tool, then call plan_current() or derive_current(). Call preview_current() in a
separate MCP invocation after GPU scheduling. Bake one atlas/channel per MCP
invocation; export only after all source-bound manifests pass. It never switches
or saves the interactive Blender file.
"""
import array, contextlib, fcntl, hashlib, json, math, re, shutil, struct, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from photoreal_materials_v16 import geometry_signature
from bake_geometry_fingerprint import fingerprints

PREVIOUS={
 'orbital-dual-bake-v16.blend':'6383e0985e9f3ea2eacd87a61bed9c8ef237b8dd0d96f16b873cfac828ac46e7',
 'orbital-atelier-v16.blend':'ecced0fd95522479728eda4e1808c5df07e1d705cd678f13eb7cd7870dbb1232',
}
SCAN_ROOT=ROOT/'assets/textures/about-atelier-v3'
REVIEW=ROOT/'renders/room-materials-v18'
SOURCE_SCENES=('ORBITAL_ATELIER_V2','ORIGINAL_DAY_V13','ORIGINAL_NIGHT_V13')

# Explicit coverage, including every EXT6/WG7 exterior and small prop material.
# No catch-all material substitution: unknown names stop the derivative.
ALIASES={
 'brushed_titanium':('MAT_Satin_Titanium','V5_MAT_SatinTitanium','IW8_MAT_SatinTitanium','EXT6_MAT_SatinTitanium','WG7_MAT_Titanium','P_PetalBrushedSilver'),
 'titanium_floor':('MAT_Titanium_Floor',),
 'anodized_warm':('P_WarmAnodizedMetal','D_SoftAnodizedGold','WG7_MAT_ChampagneMetal'),
 'powdercoat':('MAT_Graphite_Enamel','V5_MAT_Graphite','IW8_MAT_Graphite','EXT6_MAT_Graphite','WG7_MAT_Graphite','V5_MAT_BlueGreyEnamel','EXT6_MAT_BlueGreyEnamel','WG7_MAT_BlueGrey','V5_MAT_BurntOrange','EXT6_MAT_BurntOrange'),
 'ceramic':('MAT_Ivory_Ceramic','V5_MAT_PearlCeramic','IW8_MAT_IvoryCeramic','WG7_MAT_WarmCeramic'),
 'black_ceramic':('D_BlackCeramic',),
 'upholstery':('MAT_Vermilion_Woven','MAT_Charcoal_Woven'),
 'stitch':('F_Chair_Seam','F_Orange_Upholstery_Stitch'),
 'rug':('MAT_Graphite_Rug','F_Rug_Embossed_Grooves'),
 'bookcloth':('D_BlueGreyBookCloth','D_WarmGreyBookCloth'),
 'leather':('P_CreativeFolioCover',),
 'paper':('P_WarmPaper','D_BookPaper'),
 'paper_edges':('P_PageEdge','D_PaperEdges'),
 'wood_veneer':('WG7_MAT_WalnutOrangeEnamel',),
 'bark':('P_BonsaiBark',),
 'leaf':('P_DeepLeaf','P_NewLeaf','D_DeepLanceLeaf','D_SageLanceLeaf','WG7_MAT_DesaturatedBotanical'),
 'stem':('P_GreenStem','D_PaleMidrib'),
 'soil':('P_Soil','D_PlanterSoil'),
 'moss':('P_TerrariumMoss',),
 'river_stone':('P_RiverStone',),
 'soft_polymer':('MAT_Optical_Black','V5_MAT_RecessedOptics'),
 'display_ink':('P_DisplayInk',),
 'display_metal':('P_DisplaySilverBlue','D_SoftDisplayLine'),
 'optical_coating':('P_LensCoating','D_OpticCoating'),
 'glass':('D_PlanterGlass','D_SpecimenSmokeGlass','MAT_Compute_Smoked_Optical_Glass','MAT_Smoke_Glass','P_ClearTerrariumGlass'),
 'emitter':('MAT_Amber_Status','MAT_Optical_White','MAT_Warm_White','V5_MAT_AmberSignal','V5_MAT_IceSignal','V5_MAT_WarmDiffuser','IW8_MAT_WarmDiffuser','EXT6_MAT_IceSignal','EXT6_MAT_WarmSignal','WG7_MAT_AmberDiffuser','WG7_MAT_WarmWhiteDiffuser'),
 'tea':('P_TeaSurface',),
 'backdrop':('MAT_Studio_Backdrop',),
 'image_content':('MAT_Original_Window_City_V2','MAT_Rendered_3D_ScreenArtwork'),
 'lighting_helper':('DAY_SUN_V9_Opaque_Shadow_Flag',),
}
ROLE={name:role for role,names in ALIASES.items() for name in names}

# Physical values are in metres. Scan footprint is an authored calibration,
# never claimed to be metadata from the scan vendor (none is available).
PALETTE={
 'brushed_titanium':dict(metal=1,rough=(.22,.40),bump=.00010,macro_m=.08,feature_m=.0012,anisotropy=.55),
 'titanium_floor':dict(metal=1,rough=(.32,.53),bump=.00016,macro_m=.24,feature_m=.0020,anisotropy=.30),
 'anodized_warm':dict(metal=1,rough=(.21,.36),bump=.000075,macro_m=.06,feature_m=.0010,anisotropy=.40),
 'powdercoat':dict(metal=0,rough=(.30,.51),bump=.00013,macro_m=.11,feature_m=.0018,coat=.15),
 'ceramic':dict(metal=0,rough=(.19,.34),bump=0,macro_m=.045,feature_m=.005,coat=.28),
 'black_ceramic':dict(metal=0,rough=(.16,.35),bump=.00006,macro_m=.035,feature_m=.003,coat=.32),
 'upholstery':dict(metal=0,rough=(.65,.86),bump=.0011,scan='hessian_230',tile_m=.70,macro_m=.09,feature_m=.0028,sheen=.35),
 'stitch':dict(metal=0,rough=(.68,.86),bump=.00022,macro_m=.014,feature_m=.0012,sheen=.3),
 'rug':dict(metal=0,rough=(.78,.97),bump=.0018,scan='hessian_230',tile_m=1.0,macro_m=.14,feature_m=.004,sheen=.16),
 'bookcloth':dict(metal=0,rough=(.57,.79),bump=.00035,scan='hessian_230',tile_m=.30,macro_m=.05,feature_m=.0014,sheen=.2),
 'leather':dict(metal=0,rough=(.31,.58),bump=.0007,scan='brown_leather',tile_m=.32,macro_m=.045,feature_m=.0035,coat=.08),
 'paper':dict(metal=0,rough=(.72,.93),bump=.000075,macro_m=.07,feature_m=.0010),
 'paper_edges':dict(metal=0,rough=(.73,.92),bump=.00020,macro_m=.055,feature_m=.0008),
 'wood_veneer':dict(metal=0,rough=(.26,.51),bump=.00032,scan='walnut_veneer',tile_m=.85,macro_m=.13,feature_m=.0025,coat=.2),
 'bark':dict(metal=0,rough=(.70,.94),bump=.0012,macro_m=.08,feature_m=.006),
 'leaf':dict(metal=0,rough=(.28,.52),bump=.00008,macro_m=.045,feature_m=.003,subsurface=.06,transmission=.12),
 'stem':dict(metal=0,rough=(.39,.62),bump=.000075,macro_m=.04,feature_m=.002,subsurface=.04),
 'soil':dict(metal=0,rough=(.82,.98),bump=.0017,macro_m=.06,feature_m=.005),
 'moss':dict(metal=0,rough=(.75,.94),bump=.0011,macro_m=.035,feature_m=.0025),
 'river_stone':dict(metal=0,rough=(.43,.73),bump=.00075,macro_m=.06,feature_m=.005),
 'soft_polymer':dict(metal=0,rough=(.43,.66),bump=.00012,macro_m=.05,feature_m=.0012),
 'display_ink':dict(metal=0,rough=(.22,.34),bump=0,macro_m=.05,feature_m=.004,coat=.35),
 'display_metal':dict(metal=1,rough=(.24,.37),bump=.000035,macro_m=.06,feature_m=.0015),
 'optical_coating':dict(metal=0,rough=(.045,.09),bump=0,macro_m=.06,feature_m=.006,coat=.65,ior=1.52),
 'glass':dict(metal=0,rough=(.025,.045),bump=0,macro_m=.08,feature_m=.008,transmission=1,ior=1.48),
 'emitter':dict(metal=0,rough=(.32,.48),bump=.000025,macro_m=.03,feature_m=.002,transmission=.10),
 'tea':dict(metal=0,rough=(.065,.13),bump=.00008,macro_m=.035,feature_m=.007,transmission=.15,ior=1.333),
 'backdrop':dict(metal=0,rough=(.82,.91),bump=0,macro_m=.30,feature_m=.006),
}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
def canonical(name):
    name=re.sub(r'(?:\.\d+)$','',name)
    name=re.sub(r'^(?:WEB\d+_BAKE_A\d+_)+','',name)
    for prefix in ('DAY_SUN_V9_DAY_V8__','V13_NIGHT_','NIGHT_V8__','DAY_V8__','WEB8_GLASS_','WEB8_IMAGE_'):
        if name.startswith(prefix):name=name[len(prefix):]
    return name
def role_for(name):return ROLE.get(canonical(name))
def principled(mat):return next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if mat.use_nodes else None
def relevant_materials():
    web=bpy.data.scenes.get('WEB_DUAL_V8')
    scenes=[web] if web else [bpy.data.scenes[n] for n in SOURCE_SCENES if n in bpy.data.scenes]
    assert scenes,'Not a known Room source/prepared file'
    materials={}
    for scene in scenes:
        for obj in scene.objects:
            if obj.type!='MESH' or (web and not obj.get('web_export')):continue
            used={p.material_index for p in obj.data.polygons}
            for i,m in enumerate(obj.data.materials):
                if m and i in used:materials[m.name]=m
    return materials

def verify_scans():
    manifest=json.loads((SCAN_ROOT/'texture-manifest.json').read_text());records=[]
    for row in manifest['maps']:
        if row['asset'] in ('hessian_230','brown_leather','walnut_veneer'):
            assert row['license']=='CC0-1.0' and sha(SCAN_ROOT/row['file'])==row['sha256']
            records.append(row)
    assert len(records)==12
    return records

def plan_current():
    """Pure read-only material coverage and proposed physical properties."""
    assert bpy.app.background,'Use the file-targeted Blender MCP interface'
    materials=relevant_materials();rows=[];unknown=[]
    for name,mat in sorted(materials.items()):
        role=role_for(name)
        if role is None:unknown.append(name)
        p=principled(mat)
        rows.append({'name':name,'canonical':canonical(name),'role':role,
            'action':'preserve authored screen/panorama image content' if role=='image_content' else 'preserve technical shadow-ray helper' if role=='lighting_helper' else 'replace physical surface shader',
            'oldRevision':mat.get('material_revision'),'oldMetalness':p.inputs['Metallic'].default_value if p else None,
            'target':PALETTE.get(role),'sourceBaseColor':list(p.inputs['Base Color'].default_value) if p else None})
    return {'source':bpy.data.filepath,'sourceSha256':sha(bpy.data.filepath),'materials':rows,'usedMaterialCount':len(rows),
        'roleCounts':dict(Counter(r['role'] for r in rows)),'unmapped':unknown,'completeCoverage':not unknown,
        'verifiedScanMaps':verify_scans(),'scanScalePolicy':'Authored metre footprints evaluated against real geometry; vendor scan dimensions in metres are unknown.',
        'webWarning':'Legacy export discards normal/roughness/metalness and bakes view-dependent gloss into MeshBasicMaterial. New physical surface channels must reach a revised renderer; increasing combined bake resolution alone cannot fix this.'}

def node(tree,kind,name):
    n=tree.nodes.new(kind);n.name='V18_'+name;n.label=name;return n
def math_node(tree,op,a,b,name):
    n=node(tree,'ShaderNodeMath',name);n.operation=op
    for i,x in enumerate((a,b)):
        if isinstance(x,(int,float)):n.inputs[i].default_value=x
        else:tree.links.new(x,n.inputs[i])
    return n.outputs[0]
def remap(tree,value,lo,hi,name):
    n=node(tree,'ShaderNodeMapRange',name);n.clamp=True
    n.inputs['From Min'].default_value=0;n.inputs['From Max'].default_value=1
    n.inputs['To Min'].default_value=lo;n.inputs['To Max'].default_value=hi;tree.links.new(value,n.inputs['Value']);return n.outputs['Result']
def scale_vector(tree,vector,scale,name):
    n=node(tree,'ShaderNodeVectorMath',name);n.operation='MULTIPLY';n.inputs[1].default_value=scale
    tree.links.new(vector,n.inputs[0]);return n.outputs['Vector']
def noise(tree,position,metres,name,stretch=(1,1,1)):
    vec=scale_vector(tree,position,tuple(v/metres for v in stretch),name+' scale')
    n=node(tree,'ShaderNodeTexNoise',name);n.inputs['Scale'].default_value=1;n.inputs['Detail'].default_value=3;n.inputs['Roughness'].default_value=.68
    tree.links.new(vec,n.inputs['Vector']);return n.outputs['Fac']
def mix_value(tree,a,b,factor,name):
    return math_node(tree,'ADD',math_node(tree,'MULTIPLY',a,1-factor,name+' A'),math_node(tree,'MULTIPLY',b,factor,name+' B'),name)
def tint(tree,base,value,low,high,name):
    n=node(tree,'ShaderNodeMixRGB',name);n.blend_type='MULTIPLY';n.inputs[0].default_value=1;n.inputs[1].default_value=base
    tree.links.new(remap(tree,value,low,high,name+' density'),n.inputs[2]);return n.outputs['Color']

def triplanar(tree,path,position,normal,tile_m,color=False):
    """Explicit world-space FLAT samples: stable on joined bake proxies."""
    image=bpy.data.images.load(str(path),check_existing=True);image.colorspace_settings.name='sRGB' if color else 'Non-Color'
    coords=node(tree,'ShaderNodeSeparateXYZ',path.stem+' coordinates');tree.links.new(scale_vector(tree,position,(1/tile_m,)*3,path.stem+' metres'),coords.inputs[0])
    ab=node(tree,'ShaderNodeVectorMath',path.stem+' absolute normal');ab.operation='ABSOLUTE';tree.links.new(normal,ab.inputs[0])
    axes=node(tree,'ShaderNodeSeparateXYZ',path.stem+' normals');tree.links.new(ab.outputs[0],axes.inputs[0])
    weights=[math_node(tree,'POWER',axes.outputs[a],6,path.stem+' '+a+' weight') for a in 'XYZ']
    total=math_node(tree,'ADD',math_node(tree,'ADD',weights[0],weights[1],'weight XY'),weights[2],'weight total')
    sampled=[]
    for i,(u,v) in enumerate((('Y','Z'),('X','Z'),('X','Y'))):
        uv=node(tree,'ShaderNodeCombineXYZ',path.stem+' plane '+str(i));tree.links.new(coords.outputs[u],uv.inputs['X']);tree.links.new(coords.outputs[v],uv.inputs['Y'])
        tex=node(tree,'ShaderNodeTexImage',path.stem+' sample '+str(i));tex.image=image;tex.projection='FLAT';tex.extension='REPEAT';tree.links.new(uv.outputs[0],tex.inputs['Vector'])
        mul=node(tree,'ShaderNodeMixRGB',path.stem+' weighted '+str(i));mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1
        tree.links.new(tex.outputs['Color'],mul.inputs[1]);tree.links.new(math_node(tree,'DIVIDE',weights[i],total,'normalized weight'),mul.inputs[2]);sampled.append(mul.outputs[0])
    a=node(tree,'ShaderNodeMixRGB','triplanar pair');a.blend_type='ADD';a.inputs[0].default_value=1;tree.links.new(sampled[0],a.inputs[1]);tree.links.new(sampled[1],a.inputs[2])
    b=node(tree,'ShaderNodeMixRGB','triplanar final');b.blend_type='ADD';b.inputs[0].default_value=1;tree.links.new(a.outputs[0],b.inputs[1]);tree.links.new(sampled[2],b.inputs[2]);return b.outputs[0]

def scan_files(asset):
    prefixes={'hessian_230':('hessian_230','diff'),'brown_leather':('brown_leather','albedo'),'walnut_veneer':('walnut_veneer','diff')}
    prefix,albedo=prefixes[asset]
    return {key:SCAN_ROOT/asset/f'{prefix}_{suffix}_2k.jpg' for key,suffix in [('color',albedo),('roughness','rough'),('height','disp')]}

def replace_surface(mat,role):
    old=principled(mat);assert old is not None,mat.name
    tree=mat.node_tree;base=tuple(old.inputs['Base Color'].default_value)
    emission_color=tuple(old.inputs['Emission Color'].default_value);emission_strength=old.inputs['Emission Strength'].default_value
    target=tree.nodes.get('WEB8_BAKE_TARGET');target_image=target.image if target else None
    spec=PALETTE[role];tree.nodes.clear();out=node(tree,'ShaderNodeOutputMaterial','Surface output');p=node(tree,'ShaderNodeBsdfPrincipled','Physical '+role)
    tree.links.new(p.outputs['BSDF'],out.inputs['Surface']);p.inputs['Base Color'].default_value=base
    p.inputs['Metallic'].default_value=spec['metal'];p.inputs['IOR'].default_value=spec.get('ior',1.5)
    for key,param in [('Coat Weight','coat'),('Sheen Weight','sheen'),('Subsurface Weight','subsurface'),('Transmission Weight','transmission')]:p.inputs[key].default_value=spec.get(param,0)
    p.inputs['Coat Roughness'].default_value=.23;p.inputs['Sheen Roughness'].default_value=.68
    if spec.get('subsurface'):p.inputs['Subsurface Scale'].default_value=.001
    anisotropic=p.inputs.get('Anisotropic IOR Level')
    if anisotropic:anisotropic.default_value=spec.get('anisotropy',0)
    p.inputs['Emission Color'].default_value=emission_color;p.inputs['Emission Strength'].default_value=emission_strength
    geo=node(tree,'ShaderNodeNewGeometry','Stable world coordinates');position=geo.outputs['Position'];normal=geo.outputs['Normal']
    macro=noise(tree,position,spec['macro_m'],'Broad material variation')
    brushed=role in ('brushed_titanium','titanium_floor','anodized_warm','display_metal')
    fine=noise(tree,position,spec['feature_m'],'Readable surface structure',(.035,1,1) if brushed or role=='bark' else (1,1,1))
    height=fine;rough_signal=mix_value(tree,macro,fine,.65,'Two scale finish')
    if spec.get('scan'):
        files=scan_files(spec['scan'])
        col=triplanar(tree,files['color'],position,normal,spec['tile_m'],True)
        gray=node(tree,'ShaderNodeRGBToBW','Scanned luminance');tree.links.new(col,gray.inputs[0])
        height=triplanar(tree,files['height'],position,normal,spec['tile_m'])
        scanned_rough=triplanar(tree,files['roughness'],position,normal,spec['tile_m'])
        rough_signal=mix_value(tree,scanned_rough,macro,.18,'Scan and broad response')
        # Keep the scene palette while making the natural scanned grain visible.
        colour=tint(tree,base,gray.outputs[0],.55,1.28,'Authored colour with scanned grain')
        tree.links.new(colour,p.inputs['Base Color'])
    else:
        span=(.75,1.24) if role in ('bark','soil','moss','river_stone','leaf','stem') else (.9,1.08) if role in ('paper','paper_edges','stitch','soft_polymer') else (.96,1.025)
        if role not in ('glass','optical_coating','tea','emitter','display_ink'):
            tree.links.new(tint(tree,base,mix_value(tree,macro,fine,.3,'Colour structure'),*span,'Subtle reflectance variation'),p.inputs['Base Color'])
    if role=='paper_edges':
        wave=node(tree,'ShaderNodeTexWave','Individual paper layers');wave.wave_type='BANDS';wave.bands_direction='Z';wave.wave_profile='SIN'
        tree.links.new(position,wave.inputs['Vector']);wave.inputs['Scale'].default_value=1/spec['feature_m'];wave.inputs['Distortion'].default_value=.18;height=wave.outputs['Fac']
        tree.links.new(tint(tree,base,height,.72,1.05,'Paper layer edge tone'),p.inputs['Base Color'])
    if role in ('soil','moss','river_stone'):
        v=node(tree,'ShaderNodeTexVoronoi','Aggregate grains');tree.links.new(position,v.inputs['Vector']);v.inputs['Scale'].default_value=1/spec['feature_m']
        height=mix_value(tree,fine,v.outputs['Distance'],.55,'Organic grain relief')
    rough=remap(tree,rough_signal,*spec['rough'],'Physical roughness');tree.links.new(rough,p.inputs['Roughness'])
    if spec['bump']:
        bump=node(tree,'ShaderNodeBump','Metre calibrated microrelief');bump.inputs['Distance'].default_value=spec['bump'];bump.inputs['Strength'].default_value=.45 if spec.get('scan') else .30
        tree.links.new(height,bump.inputs['Height']);tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    if role=='optical_coating':
        if p.inputs.get('Thin Film Thickness'):p.inputs['Thin Film Thickness'].default_value=320
        if p.inputs.get('Thin Film IOR'):p.inputs['Thin Film IOR'].default_value=1.38
    if target_image:
        n=node(tree,'ShaderNodeTexImage','Bake target');n.name='WEB8_BAKE_TARGET';n.image=target_image;tree.nodes.active=n
    if mat.get('day_sun_v9_aperture'):
        import day_sunlight_v9
        day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57);day_sunlight_v9._aperture_shader(mat)
    mat['material_revision']=17;mat['v18_role']=role;mat['v18_surface_parameters']=json.dumps(spec,sort_keys=True)
    mat['v18_mapping']='World position in metres; explicit world-normal triplanar scan blend'
    return {'name':mat.name,'role':role,'baseColor':base,'metalness':spec['metal'],'roughnessRange':spec['rough'],'bumpDistanceMetres':spec['bump'],
        'physicalScale':spec,'geometryDisplacement':False,'emissionPreserved':True,'bakeTargetPreserved':bool(target_image)}

def derive_current():
    """Versioned warm derivative; never rerun the historical V16 preparation."""
    from room_warm_v18 import derive_current as warm_derive
    return warm_derive()

@contextlib.contextmanager
def gpu_job(label):
    with open('/tmp/room-portfolio-blender-gpu.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def configure_current(state):
    """Reuse the same authored day/night lighting in the current isolated file."""
    assert bpy.app.background and Path(bpy.data.filepath).name=='orbital-dual-bake-v18.blend'
    assert state in ('day','night')
    from run_texture_precision_v15 import scope_from
    scope=scope_from(ROOT/'assets/blender/scripts/bake_lighting_v8.py',[("OUT = ROOT / 'public/textures/lighting-v8'","OUT = ROOT / 'assets/blender/room-v18-review-lighting'"),("str(OUT/f'window-{state}.png')","str(ROOT/f'public/textures/lighting-v16/window-{state}.png')")],'v18_review_lighting')
    scene=scope['setup_state'](state,report_revision=18)
    if state=='day':
        import day_sunlight_v9
        from run_wall_lighting_v10 import configure_day
        day_sunlight_v9.APERTURE.update(center_x=.125,width=5.57);configure_day(scene,revision=18)
    else:
        warm=scope_from(ROOT/'assets/blender/scripts/night_warm_v13.py',[('night-warm-v13-design.json','night-warm-v18-review-design.json'),('lighting-night-v13.json','lighting-night-v18-review.json')],'v18_review_night');warm['configure_night_warm'](scene)
    return scene

def preview_current(view='hero',state='day',samples=64):
    """One scheduled GPU review only. No saved source changes or bulk jobs."""
    assert view in ('hero','ceramic','textile','metal','props','exterior')
    source=Path(bpy.data.filepath);source_hash=sha(source);scene=configure_current(state)
    if view!='hero':
        owners={'ceramic':['furniture.work_chair'],'textile':['furniture.lounge'],'metal':['furniture.desk'],'props':['creative_folio','notebook','thermal_cup','compact_camera'],'exterior':['environment.warm_gallery','environment.orbital_dock']}[view]
        objects=[o for o in scene.objects if o.type=='MESH' and o.get('owner_asset_id') in owners];assert objects
        points=[o.matrix_world@Vector(c) for o in objects for c in o.bound_box]
        lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)));center=(lo+hi)/2;radius=max(hi-lo)*.85
        camera=bpy.data.objects.new('V18_REVIEW_'+view,bpy.data.cameras.new('V18_REVIEW_'+view));scene.collection.objects.link(camera)
        camera.location=center+Vector((1.45,-2.2,1.3))*radius;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=70 if view=='textile' else 58;camera.data.clip_start=.02;scene.camera=camera
    REVIEW.mkdir(parents=True,exist_ok=True);out=REVIEW/f'{view}-{state}.png'
    scene.cycles.samples=samples;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.01
    scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100;scene.render.filepath=str(out)
    with gpu_job('room-v18-'+view+'-'+state):bpy.ops.render.render(write_still=True)
    assert sha(source)==source_hash
    result={'source':str(source.relative_to(ROOT)),'sourceSha256':source_hash,'path':str(out.relative_to(ROOT)),'sha256':sha(out),'engine':'CYCLES','samples':samples,'view':view,'state':state,'sourceUnchanged':True,
        'viewTransform':scene.view_settings.view_transform,'look':scene.view_settings.look,'exposureStops':scene.view_settings.exposure,
        'camera':scene.camera.name,'cameraLocation':list(scene.camera.location),'cameraEuler':list(scene.camera.rotation_euler)}
    write(REVIEW/f'{view}-{state}.json',result);return result


LIGHT_SIZES=[4096]*6+[3072,2048,3072,4096,4096,3072]
# Slot 7 is the large orange lounge chair, not exterior: its weave needs 2K.
# Slot 4 holds many close interactive props. Only slots 5/6 are true exterior.
DATA_SIZES=[2048,2048,2048,2048,2048,1024,1024,2048,2048,2048,2048,2048]
OUTPUT=ROOT/'public/textures/lighting-v18'

def assert_prepared():
    assert bpy.app.background and Path(bpy.data.filepath).name=='orbital-dual-bake-v18.blend'
    report=json.loads((ROOT/'assets/blender/photoreal-materials-v18-prepared.json').read_text())
    assert sha(bpy.data.filepath)==report['sha256']

def atlas_meshes(scene,slot):
    meshes=[o for o in scene.objects if o.type=='MESH' and o.get('web_export') and o.get('web_kind')=='baked' and o.get('bake_atlas')==slot]
    assert meshes and all(o.data.uv_layers.get('BakeUV') for o in meshes)
    return meshes

def bake_surface_current(slot,size=None,qa=False):
    """One MCP call -> one normal/F0/roughness group, releasing each pass lock."""
    assert_prepared();assert slot in range(12)
    from pbr_bake_channels import bake_channels
    scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene
    # CPU/device selection and light setup do not affect these geometric/data passes.
    scene=configure_current('day')
    out=ROOT/'assets/blender/room-v18-channel-qa' if qa else OUTPUT
    return bake_channels(scene,atlas_meshes(scene,slot),'WEB8_BAKE_TARGET',slot,size or DATA_SIZES[slot],out)

def bake_surface_pass_current(slot,channel,size=None):
    """One data pass per MCP call; last pass also assembles the validated maps."""
    assert_prepared();assert slot in range(12)
    from pbr_bake_channels import bake_channel,assemble_channels
    scene=configure_current('day');size=size or DATA_SIZES[slot];meshes=atlas_meshes(scene,slot)
    result=bake_channel(scene,meshes,'WEB8_BAKE_TARGET',slot,size,OUTPUT,channel)
    if channel=='roughness':
        assembled=assemble_channels(scene,meshes,'WEB8_BAKE_TARGET',slot,size,OUTPUT)
        result['assembled']={'complete':assembled['complete'],'rawNormalStatistics':assembled['rawNormalStatistics'],'normalSha256':assembled['normal']['sha256'],'specularSha256':assembled['specular']['sha256']}
    return result

def configure_intro_current(slot):
    """Original clean receiver lighting and isolation, now on V18 materials."""
    assert_prepared();assert slot in (0,1,8)
    scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene
    scene.render.engine='CYCLES';scene.cycles.max_bounces=6;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=2
    pref=bpy.context.preferences.addons['cycles'].preferences
    try:
        pref.compute_device_type='METAL';pref.get_devices()
        for device in pref.devices:device.use=device.type=='METAL'
        scene.cycles.device='GPU' if any(d.type=='METAL' for d in pref.devices) else 'CPU'
    except Exception:scene.cycles.device='CPU'
    group={1} if slot==1 else {0,8}
    receivers=[o for o in scene.objects if o.type=='MESH' and o.get('web_export') and o.get('web_kind')=='baked' and o.get('bake_atlas') in group]
    identities={o.as_pointer() for o in receivers}
    for obj in scene.objects:
        obj.hide_render=obj.as_pointer() not in identities
        if obj.as_pointer() in identities:obj.hide_set(False);obj.visible_shadow=False
    for mat in {m for o in receivers for m in o.data.materials if m}:
        p=principled(mat)
        if p and not p.inputs['Emission Strength'].is_linked:p.inputs['Emission Strength'].default_value*=.2
    world=bpy.data.worlds.new('V18_CLEAN_INTRO_SoftWorld');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.36,.44,.55,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8;scene.world=world
    for name,loc,target,watts,size,color in [('Key',(-4,-4,8),(0,0,1.2),1500,10,(.85,.92,1)),('Fill',(6,-2,5),(0,0,1.2),650,9,(.72,.85,1)),('Rear',(0,5,7),(0,0,1.5),1000,9,(1,.93,.84))]:
        data=bpy.data.lights.new('V18_CLEAN_INTRO_'+name,'AREA');data.shape='DISK';data.size=size;data.energy=watts;data.color=color
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    return scene

def bake_light_current(slot,state='day',intro=False,size=None,samples=96,qa=False):
    """One MCP call -> one linear RGBM diffuse/emission atlas, never a bulk loop."""
    assert not (ROOT/'assets/blender/room-v18-PAUSED').exists(),'V18 paused for new user colour direction; preserve completed passes.'
    assert_prepared();assert slot in range(12) and state in ('day','night')
    from pbr_bake_channels import bake_diffuse
    scene=configure_intro_current(slot) if intro else configure_current(state)
    out=ROOT/'assets/blender/room-v18-channel-qa' if qa else ROOT/'public/textures/intro-clean-v18' if intro else OUTPUT
    result=bake_diffuse(scene,atlas_meshes(scene,slot),'WEB8_BAKE_TARGET',slot,size or LIGHT_SIZES[slot],out,'day' if intro else state,samples)
    result['cleanIntro']=intro;result['receiverOnly']=intro
    write(out/f'{"day" if intro else state}-{slot}-manifest.json',result);return result

def reflection_current(state='day',width=2048):
    """One true scene-linear panoramic probe; identical camera for both states."""
    assert_prepared();scene=configure_current(state)
    camera=bpy.data.objects.new('V18_ReflectionProbe',bpy.data.cameras.new('V18_ReflectionProbe'));scene.collection.objects.link(camera)
    camera.location=(0,-.65,1.7);camera.rotation_euler=(math.pi/2,0,0);camera.data.type='PANO';camera.data.panorama_type='EQUIRECTANGULAR';camera.data.clip_start=.03;scene.camera=camera
    scene.render.resolution_x=width;scene.render.resolution_y=width//2;scene.render.resolution_percentage=100
    scene.cycles.samples=64;scene.cycles.use_denoising=True;scene.render.film_transparent=False
    # Radiance HDR carries linear values; no AgX or display exposure baked in.
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    scene.render.image_settings.file_format='HDR';scene.render.image_settings.color_mode='RGB'
    OUTPUT.mkdir(parents=True,exist_ok=True);path=OUTPUT/f'reflection-{state}.hdr';scene.render.filepath=str(path)
    with gpu_job('room-v18-reflection-'+state):bpy.ops.render.render(write_still=True)
    result={'state':state,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'dimensions':[width,width//2],'cameraLocation':list(camera.location),'cameraEuler':list(camera.rotation_euler),'encoding':'scene-linear Radiance HDR','samples':64,'sourceSha256':sha(bpy.data.filepath)}
    write(OUTPUT/f'reflection-{state}.json',result);return result

def audit_highlight_uvs_current():
    """Read-only scene audit: assign rare limited highlights to actual BakeUVs."""
    assert_prepared()
    from mathutils.bvhtree import BVHTree
    from pbr_bake_channels import mesh_signature
    scene=bpy.data.scenes['WEB_DUAL_V8'];results=[]
    for path in sorted((ROOT/'assets/blender').glob('room-v18-highlight-audit-*.json')):
        report=json.loads(path.read_text());meshes=atlas_meshes(scene,report['slot']);before=mesh_signature(meshes);trees=[]
        for obj in meshes:
            mesh=obj.data;mesh.calc_loop_triangles();layer=mesh.uv_layers['BakeUV']
            coords=[(float(v.uv[0]),float(v.uv[1]),0.) for v in layer.data]
            tris=[tuple(t.loops) for t in mesh.loop_triangles]
            tree=BVHTree.FromPolygons(coords,tris,all_triangles=True);trees.append((obj,tree))
        counts={};maximum=0;inside_count=0
        size=json.loads((OUTPUT/f'night-{report["slot"]}-manifest.json').read_text())['dimensions'][0]
        for sample in report['samples']:
            q=Vector((*sample['uv'],0));best=(float('inf'),None,None)
            for obj,tree in trees:
                position,normal,index,distance=tree.find_nearest(q)
                if position is not None and distance<best[0]:best=(distance,obj,index)
            distance,obj,index=best;assert obj
            pixels=distance*size;inside=pixels<.001;maximum=max(maximum,pixels);inside_count+=int(inside)
            polygon=obj.data.polygons[obj.data.loop_triangles[index].polygon_index];material=obj.data.materials[polygon.material_index].name
            sample.update(object=obj.name,material=material,ownerAssetId=obj.get('owner_asset_id'),insideIsland=inside,gutterDistanceTexels=round(pixels,4))
            row=counts.setdefault(obj.name,{'ownerAssetId':obj.get('owner_asset_id'),'pixels':0,'insideIslandPixels':0,'materials':{}})
            row['pixels']+=1;row['insideIslandPixels']+=int(inside);row['materials'][material]=row['materials'].get(material,0)+1
        assert mesh_signature(meshes)==before and maximum<=32
        report.update(complete=True,objectAttribution=counts,insideIslandPixels=inside_count,maxGutterDistanceTexels=maximum,
            renderedSurfaceFraction=inside_count/(size*size),notLargeArea=inside_count/(size*size)<3e-5,
            geometryUvsNormalsUnchanged=True,sourceScene='WEB_DUAL_V8',smallHighlightLimit={'channelFraction':1e-5,'sourceMaximum':64})
        write(path,report);results.append({k:v for k,v in report.items() if k!='samples'})
    return {'audits':results,'sourceSha256':sha(bpy.data.filepath)}

def export_current():
    """Export the original hierarchy with LogRGB lightmaps and genuine PBR glass.

    Runtime replaces the opaque base lobe using external F0/normal data. The
    GLB keeps the established atlas material names and UV0=original BakeUV.
    Export is explicitly separate from the per-atlas MCP bake calls.
    """
    assert_prepared();prepared_hash=sha(bpy.data.filepath)
    for state in ('day','night'):
        for slot in range(12):
            record=json.loads((OUTPUT/f'{state}-{slot}-manifest.json').read_text())
            assert record['sourceSha256']==prepared_hash and record['glossyExcluded'] and record['encoding']=='RGBM32'
            assert record['sha256']==sha(OUTPUT/f'{state}-{slot}.png')
    for slot in range(12):
        record=json.loads((OUTPUT/f'surface-{slot}-manifest.json').read_text());assert record['complete'] and record['sourceSha256']==prepared_hash
        for kind in ('normal','specular'):assert record[kind]['sha256']==sha(OUTPUT/f'{kind}-{slot}.png')
    for name in ('window-day.png','window-night.png','screen-art-render.png','day-window.ktx2','night-window.ktx2','static-screen.ktx2'):
        shutil.copy2(ROOT/'public/textures/lighting-v16'/name,OUTPUT/name)
    from export_dual_lighting_v8 import emission_material
    scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene;materials=[];night_scales={}
    for slot in range(12):
        compressed=json.loads((OUTPUT/f'night-{slot}.ktx2.json').read_text())
        encoded=compressed['encodedSource']
        if compressed.get('radianceScale',1)!=1:night_scales[str(slot)]=compressed['radianceScale']
        assert compressed['kind']=='logrgb32-k256' and compressed['codecRevision']=='linear-surface-v2-logrgb256'
        assert compressed['sourceSha256']==sha(OUTPUT/f'night-{slot}.png') and encoded['sha256']==sha(encoded['path'])
        image=bpy.data.images.load(encoded['path'],check_existing=False);image.colorspace_settings.name='Non-Color'
        materials.append(emission_material(f'WEB8_LIGHTMAP_{slot}',image,'BakeUV'))
    window=bpy.data.images.load(str(OUTPUT/'window-night.png'),check_existing=False);window.colorspace_settings.name='sRGB';window_material=emission_material('WEB8_WINDOW_CITY',window)
    objects=[o for o in scene.objects if o.get('web_export')];glass_records=[]
    for obj in objects:
        if obj.type!='MESH':continue
        kind=obj.get('web_kind')
        if kind=='baked':
            obj.data.materials.clear();obj.data.materials.append(materials[int(obj['bake_atlas'])])
            for polygon in obj.data.polygons:polygon.material_index=0
            for uv in list(obj.data.uv_layers):
                if uv.name!='BakeUV':obj.data.uv_layers.remove(uv)
            obj.data.uv_layers.active=obj.data.uv_layers['BakeUV'];obj.data.uv_layers['BakeUV'].active_render=True
        elif kind=='image':
            for i,mat in enumerate(obj.data.materials):
                if mat and role_for(mat.name)=='image_content' and 'Window' in mat.name:obj.data.materials[i]=window_material
        elif kind=='glass':
            old=obj.data.materials[0];old_p=principled(old);assert old_p
            mat=bpy.data.materials.new('WEB8_CLEAR_'+old.name);mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF')
            p.inputs['Base Color'].default_value=old_p.inputs['Base Color'].default_value
            p.inputs['Metallic'].default_value=0;p.inputs['Roughness'].default_value=sum(PALETTE['glass']['rough'])/2
            p.inputs['IOR'].default_value=1.48;p.inputs['Transmission Weight'].default_value=1
            obj.data.materials.clear();obj.data.materials.append(mat)
            for polygon in obj.data.polygons:polygon.material_index=0
            glass_records.append({'object':obj.name,'material':mat.name,'ior':1.48,'roughness':.035,'transmission':1,'note':'Runtime must not overwrite this with legacy unlit glass settings.'})
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.hide_set(False);obj.hide_render=False;obj.select_set(True)
    path=ROOT/'public/models/orbital-atelier-v18.glb'
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_active_scene=True,use_selection=True,
        export_extras=True,export_yup=True,export_animations=False,export_lights=False,export_cameras=False,
        export_materials='EXPORT',export_copyright='Original Blender room, geometry-preserving material revision 18; verified CC0 scanned materials and project-authored procedural finishes.')
    data=path.read_bytes();length=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+length]);offset=20+length;binary_size=struct.unpack_from('<I',data,offset)[0];binary=data[offset+8:offset+8+binary_size]
    for mat in doc['materials']:
        if mat['name'].startswith('WEB8_CLEAR_'):
            mat['doubleSided']=True;continue
        pbr=mat.setdefault('pbrMetallicRoughness',{})
        if 'emissiveTexture' in mat:pbr['baseColorTexture']=mat.pop('emissiveTexture')
        pbr.update(baseColorFactor=[1,1,1,1],metallicFactor=0,roughnessFactor=1)
        for key in ('emissiveFactor','normalTexture','occlusionTexture'):mat.pop(key,None)
        mat['extensions']={'KHR_materials_unlit':{}};mat['doubleSided']=True
        if mat['name'].startswith('WEB8_LIGHTMAP_'):mat.setdefault('extras',{}).update(diffuseEncoding='LogRGB32 gain256',logGain=256,radianceRange=32,nightRadianceScale=night_scales.get(mat['name'].rsplit('_',1)[1],1),surfaceData='external linear F0/roughness and tangent normals',glossyBaked=False)
    doc['extensionsUsed']=sorted((set(doc.get('extensionsUsed',[]))-{'KHR_materials_emissive_strength'})|{'KHR_materials_unlit'})
    doc.pop('extensionsRequired',None)
    for entry in doc.get('scenes',[]):entry.setdefault('extras',{}).update(web_baked=True,source_revision=18,lighting_revision=18,geometry_inherited_from=15,bake_mode='cycles_linear_diffuse_emit_logrgb32_gain256',surface_mode='view_dependent_ggx')
    raw=json.dumps(doc,separators=(',',':')).encode();raw+=b' '*(-len(raw)%4)
    blob=struct.pack('<III',0x46546C67,2,28+len(raw)+len(binary))+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(binary),0x004E4942)+binary
    path.write_bytes(blob)
    triangles=sum(doc['accessors'][p['indices']]['count']//3 for mesh in doc['meshes'] for p in mesh['primitives']);assert triangles==413855
    component_ids=[o.get('asset_id') for o in objects if o.get('asset_id')];old=json.loads((ROOT/'assets/blender/dual-lighting-v16-export-report.json').read_text());assert sorted(component_ids)==sorted(old['componentIds'])
    assert sha(bpy.data.filepath)==prepared_hash
    result={'complete':True,'model':str(path.relative_to(ROOT)),'bytes':len(blob),'sha256':sha(path),'preparedSha256':prepared_hash,'source':str((ROOT/'assets/blender/orbital-atelier-v18.blend').relative_to(ROOT)),
        'componentIds':component_ids,'triangles':triangles,'drawPrimitives':sum(len(m['primitives']) for m in doc['meshes']),'nodes':len(doc['nodes']),'materials':[m['name'] for m in doc['materials']],
        'atlasSizes':LIGHT_SIZES,'surfaceSizes':DATA_SIZES,'encoding':'LogRGB32 gain256, no baked gloss','rawBakeEncoding':'RGBM32','nightRadianceScale':night_scales,'normalBasis':'Tangent GL BakeUV exported as UV0; runtime derivative TBN','glass':glass_records,'geometryInheritedFrom':15}
    write(ROOT/'assets/blender/dual-lighting-v18-export-report.json',result);return result
