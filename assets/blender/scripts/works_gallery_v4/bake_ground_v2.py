"""True V4 architectural shadows on the unchanged V1 atmosphere floor. Default CPU check; --bake enables GPU."""
import bpy,sys,json,time,hashlib,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
import bake_gallery as util
SOURCE=ROOT/'assets/blender/works-gallery-v4.blend';OUTPUT=ROOT/'public/textures/gallery-atmosphere-v2';BLEND=ROOT/'assets/blender/gallery-atmosphere-v2.blend'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r):
    temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');temp.replace(p)
source_sha=sha(SOURCE)
protected_paths=[SOURCE,ROOT/'assets/blender/gallery-atmosphere-v1.blend',ROOT/'public/textures/gallery-atmosphere-v1/day.png',ROOT/'public/textures/gallery-atmosphere-v1/night.png']
protected_hashes={str(p.relative_to(ROOT)):sha(p) for p in protected_paths}
bake_enabled='--bake' in sys.argv
v1_manifest=json.loads((ROOT/'public/textures/gallery-atmosphere-v1/SOURCE.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.data.scenes['WORKS_GALLERY_V4'];bpy.context.window.scene=s;s.name='GALLERY_ATMOSPHERE_V2'
original_lights={o.name:{'matrix':[list(r) for r in o.matrix_world],'energy':o.data.energy,'base_power':o.get('base_power'),'color':list(o.data.color)} for o in s.objects if o.type=='LIGHT'}
mesh=bpy.data.meshes.new('Atmosphere floor closed UV quad');mesh.from_pydata([(-32,-32,-.88),(32,-32,-.88),(32,32,-.88),(-32,32,-.88)],[],[(0,1,2,3)]);mesh.update();floor=bpy.data.objects.new('Gallery atmosphere bake plane',mesh);s.collection.objects.link(floor);floor['bake_only']=True;floor['web_floor_y']=-.88;floor['extent_web_xz']=[-32,32,-32,32]
uv=mesh.uv_layers.new(name='BakeUV')
for loop,coord in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]):loop.uv=coord
mesh.uv_layers.active=uv;uv.active_render=True
mat=bpy.data.materials.new('ATMOSPHERE fine neutral stone');mat.use_nodes=True;t=mat.node_tree;t.nodes.clear();out=t.nodes.new('ShaderNodeOutputMaterial');p=t.nodes.new('ShaderNodeBsdfPrincipled');t.links.new(p.outputs['BSDF'],out.inputs['Surface']);p.inputs['Metallic'].default_value=.04;p.inputs['Roughness'].default_value=.66
coords=t.nodes.new('ShaderNodeTexCoord');n=t.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=32;n.inputs['Detail'].default_value=2;n.inputs['Roughness'].default_value=.58;t.links.new(coords.outputs['Object'],n.inputs['Vector'])
r=t.nodes.new('ShaderNodeValToRGB');r.color_ramp.elements[0].position=.15;r.color_ramp.elements[0].color=(.225,.233,.239,1);r.color_ramp.elements[1].position=.85;r.color_ramp.elements[1].color=(.258,.269,.277,1);t.links.new(n.outputs['Fac'],r.inputs[0]);t.links.new(r.outputs[0],p.inputs['Base Color'])
bump=t.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.055;bump.inputs['Distance'].default_value=.009;t.links.new(n.outputs['Fac'],bump.inputs['Height']);t.links.new(bump.outputs[0],p.inputs['Normal']);mesh.materials.append(mat)
img=bpy.data.images.new('ATMOSPHERE_REAL_BAKE',width=2048,height=2048,alpha=False,float_buffer=True);img.colorspace_settings.name='Linear Rec.709';target=t.nodes.new('ShaderNodeTexImage');target.name='ATMOSPHERE_BAKE_TARGET';target.image=img
for node in t.nodes:node.select=False
target.select=True;t.nodes.active=target
# Broad, render-only area light creates a gently warm foreground without changing
# the original sun direction; low night bounce remains local to the gallery.
def area(name,pos,target,power,color,size):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o['atmosphere_only']=True;o['export_exclude']=True;return o
key=area('ATMOSPHERE warm daylight softbox',(7,-11,12),(-1,-5,-.88),700,(1,.84,.65),11)
portal=area('ATMOSPHERE doorway warm bounce',(-8,-1.6,.45),(-12,-6,-.88),60,(1,.55,.25),3.0)
edge=area('ATMOSPHERE quiet amber floor bounce',(6,-3,.30),(9,-5,-.88),34,(1,.64,.34),2.5)
s.render.engine='CYCLES';s.cycles.samples=64;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.018;s.cycles.max_bounces=7;s.cycles.diffuse_bounces=4;s.cycles.glossy_bounces=3;s.cycles.transmission_bounces=6
s.render.bake.margin=16;s.render.bake.margin_type='EXTEND';s.render.bake.use_clear=True;s.render.bake.use_selected_to_active=False;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8';s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.gamma=1
# Preserve V1 floor and all three added-light definitions exactly. Dry runs do not
# render, allocate GPU devices, save a .blend, or write manifests.
assert len(mesh.vertices)==4 and len(mesh.polygons)==1
assert all(abs(v.co.z+.88)<1e-6 for v in mesh.vertices)
assert [list(loop.uv) for loop in uv.data]==[[0.0,0.0],[1.0,0.0],[1.0,1.0],[0.0,1.0]]
assert v1_manifest['floor']['size']==[64,64] and v1_manifest['floor']['web_y']==-.88
assert v1_manifest['material']['linear_color_ramp']==[[.225,.233,.239],[.258,.269,.277]]
for original in original_lights:
    assert original in v1_manifest['original_lights'], 'Unexpected original light '+original
    old=v1_manifest['original_lights'][original]
    assert original_lights[original]['matrix']==old['matrix'], 'Original light transform changed: '+original
if not bake_enabled:
    s.cycles.device='CPU'
    for path,expected in protected_hashes.items():assert sha(ROOT/path)==expected
    print(json.dumps({'check_complete':True,'baked':False,'gpu_requested':False,'source_sha256':source_sha,'scene':s.name,'original_light_count':len(original_lights),'added_area_lights':3,'size':[64,64],'resolution':[2048,2048],'samples':64,'web_y':-.88,'uv_contract_unchanged':True,'old_atmosphere_material_and_lights_preserved':True}),flush=True)
    raise SystemExit(0)
OUTPUT.mkdir(parents=True,exist_ok=True)
backend=util._device(s)
manifest={'complete':False,'source':'assets/blender/works-gallery-v4.blend','source_sha256':source_sha,'editable_background_source':'assets/blender/gallery-atmosphere-v2.blend','geometry':'one UV plane only for ground baking; V4 rebuilt gallery is shadow-casting context, no new buildings','floor':{'size':[64,64],'web_y':-.88,'web_xz_bounds':[-32,32,-32,32],'blender_xy_bounds':[-32,32,-32,32],'blender_z':-.88,'blender_uv_formula':['u=(x+32)/64','v=(y+32)/64'],'ktx2_or_png_flipY_false_sampler_uv_formula':['u=(webX+32)/64','v=(webZ+32)/64'],'three_plane_rotated_minus_half_pi_v_must_flip_for_ktx2':True},'texture_resolution':[2048,2048],'color_management':'Cycles scene-linear combined bake -> AgX Medium High Contrast save_render -> sRGB PNG. GPU decode sRGB, blend day/night in linear display-referred space; no second tone mapping.','material':{'name':mat.name,'linear_color_ramp':[[.225,.233,.239],[.258,.269,.277]],'metallic':.04,'roughness':.66,'stone_noise_scale_per_meter':32,'bump_strength':.055,'bump_distance':.009},'cycles':{'samples':64,'passes':sorted(util.PASS_FILTER),**backend},'original_lights':original_lights,'bakes':[],'protected_input_sha256':protected_hashes,'retained_floor_material_and_lights_from':'gallery-atmosphere-v1','changed':'V4 architectural geometry casts new real shadows; original ground material, helper lights, dimensions and mapping preserved'}
for state in ('day','night'):
    lighting=set_lighting(s,state)
    key.data.energy=700 if state=='day' else 0
    portal.data.energy=10 if state=='day' else 60
    edge.data.energy=6 if state=='day' else 34
    # Original source lighting parameters are set by the unchanged V1/V4 setter.
    for obj in s.objects:
        if obj.name in original_lights:assert [list(r) for r in obj.matrix_world]==original_lights[obj.name]['matrix']
    bpy.ops.object.select_all(action='DESELECT');floor.select_set(True);bpy.context.view_layer.objects.active=floor
    path=OUTPUT/(state+'.png');pending=OUTPUT/('.'+state+'.pending.png');started=time.monotonic()
    bpy.ops.object.bake(type='COMBINED',pass_filter=util.PASS_FILTER,uv_layer='BakeUV',margin=16,use_clear=True,use_selected_to_active=False)
    img.save_render(str(pending),scene=s);assert util._png_size(pending)==(2048,2048);pending.replace(path)
    manifest['bakes'].append({'state':state,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size,'seconds':round(time.monotonic()-started,2),'resolution':[2048,2048],'original_lighting':lighting,'added_area_lights':{key.name:key.data.energy,portal.name:portal.data.energy,edge.name:edge.data.energy}});write(OUTPUT/'SOURCE.json',manifest);print(json.dumps(manifest['bakes'][-1]),flush=True)
set_lighting(s,'day');key.data.energy=700;portal.data.energy=10;edge.data.energy=6;s['atmosphere_manifest']=json.dumps(manifest,ensure_ascii=False)
bpy.data.libraries.write(str(BLEND),{s},fake_user=True,compress=True)
for path,expected in protected_hashes.items():assert sha(ROOT/path)==expected
manifest.update(complete=True,background_blend_sha256=sha(BLEND),original_v4_source_unchanged=True,original_v1_atmosphere_unchanged=True,gpu_bake_complete=True);write(OUTPUT/'SOURCE.json',manifest)
print(json.dumps({'complete':True,'gpu_released':True,'source_sha256':source_sha}),flush=True)
