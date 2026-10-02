"""MCP-callable V6 per-atlas physical bakes and linear HDR probes."""
import importlib.util,sys,json,math,hashlib,struct,time
from pathlib import Path
import bpy
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'public/textures/works-gallery-v6'
SIZES=[4096,4096,4096,1024]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
common=module('physical_bake_channels',ROOT/'assets/blender/scripts/pbr_bake_channels.py')
old=module('gallery_v4_bake',ROOT/'assets/blender/scripts/works_gallery_v4/bake_gallery.py')

def scene(state='day'):
    assert Path(bpy.data.filepath).name=='works-gallery-bake-v6.blend'
    s,report=old.setup_state(state)
    return s

def members(s,slot):
    return [o for o in s.objects if o.type=='MESH' and o.get('web_export') and o.get('web_kind')=='baked' and o.get('bake_atlas')==slot]

def bake(slot,state='day',data=False,preview=False):
    s=scene(state);ms=members(s,slot);assert ms
    out=OUT if not preview else ROOT/'renders/works-gallery-v6/channel-proof'
    if data:return common.bake_channels(s,ms,'GALLERY_BAKE_TARGET',slot,256 if preview else 2048 if slot<3 else 1024,out,samples=4)
    return common.bake_diffuse(s,ms,'GALLERY_BAKE_TARGET',slot,256 if preview else SIZES[slot],out,state,samples=16 if preview else 64)

def write_hdr(path,pixels):
    # Radiance RGBE, literal scanline packets, linear values without display transform.
    a=np.maximum(np.asarray(pixels,dtype=np.float32)[...,:3],0);h,w=a.shape[:2]
    peak=a.max(2);mantissa,exponent=np.frexp(peak);scale=np.where(peak>1e-32,mantissa*256/np.maximum(peak,1e-32),0)
    rgb=np.floor(np.clip(a*scale[...,None],0,255)).astype(np.uint8)
    e=np.where(peak>1e-32,exponent+128,0).astype(np.uint8)
    rgbe=np.concatenate([rgb,e[...,None]],2)[::-1]
    header=f'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {h} +X {w}\n'.encode()
    chunks=[header]
    for row in rgbe:
        chunks.append(bytes([2,2,w>>8,w&255]))
        for channel in range(4):
            for start in range(0,w,128):
                seq=row[start:start+128,channel].tobytes();chunks.append(bytes([len(seq)])+seq)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b''.join(chunks))
    return {'path':str(path),'size':[w,h],'maxRadiance':float(peak.max()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def probe(state):
    assert Path(bpy.data.filepath).name=='works-gallery-v6.blend'
    lib=module('gallery_v5_probe',ROOT/'assets/blender/scripts/works_gallery_v5/render_reflection_probes.py')
    s=bpy.context.scene;lib.set_lighting(s,state)
    with bpy.data.libraries.load(str(lib.SKY_SOURCE),link=False) as (a,b):b.worlds=[lib.WORLD_NAMES[state]]
    s.world=b.worlds[0];hidden,kept=lib.configure_visibility(s);lib.temporary_ground(s)
    data=bpy.data.cameras.new('V6 linear HDR probe');cam=bpy.data.objects.new('V6 linear HDR probe',data);s.collection.objects.link(cam)
    cam.location=lib.PROBE_LOCATION;cam.rotation_euler=lib.CAMERA_ROTATION;data.type='PANO';data.panorama_type='EQUIRECTANGULAR';s.camera=cam
    s.render.engine='CYCLES';old._device(s);s.cycles.samples=32;s.cycles.use_denoising=True
    s.cycles.max_bounces=7;s.cycles.diffuse_bounces=4;s.cycles.glossy_bounces=3;s.cycles.transmission_bounces=6
    s.render.resolution_x=2048;s.render.resolution_y=1024;s.render.resolution_percentage=100
    s.render.film_transparent=False;s.render.use_compositing=False;s.render.use_sequencer=False
    s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='32'
    OUT.mkdir(parents=True,exist_ok=True);exr=OUT/f'reflection-{state}.exr';s.render.filepath=str(exr)
    with common.gpu_job('gallery-probe-'+state):bpy.ops.render.render(write_still=True)
    image=bpy.data.images.load(str(exr),check_existing=False);result=write_hdr(OUT/f'reflection-{state}.hdr',common.image_pixels(image))
    result.update(state=state,samples=32,source=bpy.data.filepath,sourceSha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),encoding='scene-linear Radiance RGBE, no exposure/AgX applied',cameraLocation=list(cam.location),cameraRotation=list(cam.rotation_euler),hiddenArchitecturalGlass=hidden)
    (OUT/f'reflection-{state}-manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
