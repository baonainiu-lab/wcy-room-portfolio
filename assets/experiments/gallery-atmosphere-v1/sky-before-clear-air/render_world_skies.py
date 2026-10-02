"""Real Cycles equirectangular physical skies and a cardinal-axis calibration."""
import bpy,sys,json,math,time,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
import bake_gallery as util
OUT=ROOT/'public/textures/gallery-atmosphere-v1';RENDERS=ROOT/'renders/gallery-atmosphere-v1';SOURCE=ROOT/'assets/blender/gallery-atmosphere-sky-v1.blend'
SUN=Vector((.575766,.523424,.628109)).normalized();ELEV=math.asin(SUN.z);ROT=math.atan2(SUN.x,SUN.y)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
s=bpy.data.scenes.new('GALLERY_REAL_WORLD_SKIES_V1');bpy.context.window.scene=s
s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.02;s.cycles.use_denoising=False
backend=util._device(s);s.render.resolution_x=2048;s.render.resolution_y=1024;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8';s.render.film_transparent=False
camdata=bpy.data.cameras.new('Calibrated world panorama camera');camera=bpy.data.objects.new('Calibrated world panorama camera',camdata);s.collection.objects.link(camera);camera.location=(0,0,0);camera.rotation_euler=(math.pi/2,0,0);camdata.type='PANO';camdata.panorama_type='EQUIRECTANGULAR';camdata.latitude_min=-math.pi/2;camdata.latitude_max=math.pi/2;camdata.longitude_min=-math.pi;camdata.longitude_max=math.pi;s.camera=camera
world=bpy.data.worlds.new('Gallery day physical sky');world.use_nodes=True;s.world=world
# Temporary emissive cardinal probes calibrate panorama sampling. They are removed
# before the real empty-world renders and are never saved in the background source.
t=world.node_tree;t.nodes.clear();o=t.nodes.new('ShaderNodeOutputWorld');b=t.nodes.new('ShaderNodeBackground');b.inputs['Color'].default_value=(0,0,0,1);t.links.new(b.outputs[0],o.inputs[0]);markers=[]
for name,d,col in [('plus_x',(1,0,0),(1,0,0,1)),('plus_y',(0,1,0),(0,1,0,1)),('minus_x',(-1,0,0),(1,0,1,1)),('minus_y',(0,-1,0),(1,1,0,1))]:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.23,location=Vector(d)*10);obj=bpy.context.object;obj.name='PANORAMA_CALIBRATION_'+name;mat=bpy.data.materials.new(obj.name);mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear();e=nt.nodes.new('ShaderNodeEmission');e.inputs[0].default_value=col;out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],out.inputs[0]);obj.data.materials.append(mat);markers.append(obj)
s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.cycles.samples=4;s.render.resolution_x=512;s.render.resolution_y=256;s.render.filepath=str(RENDERS/'sky-cardinal-calibration.png');bpy.ops.render.render(write_still=True)
for obj in markers:bpy.data.objects.remove(obj,do_unlink=True)
s.cycles.samples=32;s.render.resolution_x=2048;s.render.resolution_y=1024;s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.gamma=1

def cloud_nodes(tree):
    coord=tree.nodes.new('ShaderNodeTexCoord');coord.name='World spherical directions'
    mapping=tree.nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(1,1,2.5);tree.links.new(coord.outputs['Normal'],mapping.inputs[0])
    noise=tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3.2;noise.inputs['Detail'].default_value=3;noise.inputs['Roughness'].default_value=.60;tree.links.new(mapping.outputs['Vector'],noise.inputs['Vector'])
    ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.61;ramp.color_ramp.elements[0].color=(0,0,0,1);ramp.color_ramp.elements[1].position=.80;ramp.color_ramp.elements[1].color=(.23,.23,.23,1);tree.links.new(noise.outputs['Fac'],ramp.inputs[0])
    return coord,ramp

def day_world():
    w=bpy.data.worlds.new('DAY physical multiscattering atmosphere');w.use_nodes=True;t=w.node_tree;t.nodes.clear();output=t.nodes.new('ShaderNodeOutputWorld');bg=t.nodes.new('ShaderNodeBackground');bg.inputs[1].default_value=.055
    sky=t.nodes.new('ShaderNodeTexSky');sky.name='Physical sun matched to gallery SUN';sky.sky_type='MULTIPLE_SCATTERING';sky.sun_disc=True;sky.sun_elevation=ELEV;sky.sun_rotation=ROT;sky.sun_size=math.radians(.545);sky.sun_intensity=1;sky.altitude=.08;sky.air_density=1.0;sky.aerosol_density=.35
    coord,cloud=cloud_nodes(t)
    # Thin cloud wisps desaturate/softly brighten the physical sky; never an opaque cloud sea.
    veil=t.nodes.new('ShaderNodeMixRGB');veil.blend_type='SCREEN';veil.inputs[2].default_value=(.12,.13,.15,1);t.links.new(cloud.outputs[0],veil.inputs[0]);t.links.new(sky.outputs[0],veil.inputs[1]);t.links.new(veil.outputs[0],bg.inputs[0]);t.links.new(bg.outputs[0],output.inputs[0]);return w

def night_world():
    w=bpy.data.worlds.new('NIGHT quiet blue atmosphere');w.use_nodes=True;t=w.node_tree;t.nodes.clear();output=t.nodes.new('ShaderNodeOutputWorld');bg=t.nodes.new('ShaderNodeBackground');bg.inputs[1].default_value=1
    coord,cloud=cloud_nodes(t);sep=t.nodes.new('ShaderNodeSeparateXYZ');t.links.new(coord.outputs['Normal'],sep.inputs[0]);ab=t.nodes.new('ShaderNodeMath');ab.operation='ABSOLUTE';t.links.new(sep.outputs['Z'],ab.inputs[0])
    gradient=t.nodes.new('ShaderNodeValToRGB');gradient.color_ramp.elements[0].position=0;gradient.color_ramp.elements[0].color=(.020,.032,.064,1);gradient.color_ramp.elements[1].position=1;gradient.color_ramp.elements[1].color=(.0025,.007,.021,1);t.links.new(ab.outputs[0],gradient.inputs[0])
    veil=t.nodes.new('ShaderNodeMixRGB');veil.blend_type='MIX';veil.inputs[2].default_value=(.026,.035,.059,1);t.links.new(cloud.outputs[0],veil.inputs[0]);t.links.new(gradient.outputs[0],veil.inputs[1]);t.links.new(veil.outputs[0],bg.inputs[0]);t.links.new(bg.outputs[0],output.inputs[0]);return w
worlds={'day':day_world(),'night':night_world()};records=[]
for state in ('day','night'):
    s.world=worlds[state];s.view_settings.exposure=.18 if state=='day' else 0
    path=OUT/f'{state}-sky.png';pending=OUT/f'.{state}-sky.pending.png';s.render.filepath=str(pending);started=time.monotonic();bpy.ops.render.render(write_still=True);pending.replace(path)
    records.append({'state':state,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size,'resolution':[2048,1024],'samples':32,'seconds':round(time.monotonic()-started,2),'type':'actual Blender Cycles world equirectangular render; no image generation','world':worlds[state].name});print(json.dumps(records[-1]),flush=True)
s.world=worlds['day'];s.view_settings.exposure=.18
manifest={'complete':True,'source':str(SOURCE.relative_to(ROOT)),'format':'Equirectangular panorama 2:1; whole sphere; RGB sRGB PNG','resolution':[2048,1024],'cycles':backend,'camera_rotation_euler':list(camera.rotation_euler),'sun_blender_direction':list(SUN),'sun_web_direction':[SUN.x,SUN.z,-SUN.y],'sun_elevation_rad':ELEV,'sky_sun_rotation_rad':ROT,'sun_disc_degrees':.545,'color_management':'AgX Medium High Contrast, day exposure +0.18 / night 0; already display-referred sRGB; runtime SRGBColorSpace, no second tone mapping','clouds':'Sparse low-contrast 3D procedural wisps; no models, buildings, moon, starfield or external images','calibration':'renders/gallery-atmosphere-v1/sky-cardinal-calibration.png','renders':records,'direction_verification':'pending image peak and cardinal marker check'}
s['sky_manifest']=json.dumps(manifest,ensure_ascii=False);bpy.data.libraries.write(str(SOURCE),{s,worlds['day'],worlds['night']},fake_user=True,compress=True);manifest['source_sha256']=sha(SOURCE);write(OUT/'SKY_SOURCE.json',manifest);print(json.dumps({'complete':True,'gpu_released':True}))
