"""Actual Cycles finish inspection, read-only source and GPU lock per view."""
import bpy,sys,json,time,hashlib,fcntl
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
import bake_gallery as util
SOURCE=ROOT/'assets/blender/works-gallery-v5.blend'
source_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.data.scenes['WORKS_GALLERY_V4'];bpy.context.window.scene=scene
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;util._device(scene)
scene.render.resolution_x=1600;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
camera=scene.camera;original=(camera.location.copy(),camera.rotation_euler.copy(),camera.data.lens)
out=ROOT/'renders/works-gallery-v5';out.mkdir(parents=True,exist_ok=True);records=[]
views=[('materials-closeup','day',(4.2,-5.7,3.3),(.5,-1.9,.7),57),('day-wide','day',None,None,57),('night-wide','night',None,None,57)]
for name,state,pos,target,lens in views:
    set_lighting(scene,state)
    if pos:
        camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=lens
    else: camera.location,camera.rotation_euler,camera.data.lens=original
    path=out/(name+'.png');scene.render.filepath=str(path)
    with open('/tmp/room-portfolio-blender-gpu.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);start=time.monotonic();bpy.ops.render.render(write_still=True)
    records.append({'path':str(path.relative_to(ROOT)),'state':state,'source_sha256':source_sha,'samples':32,'seconds':round(time.monotonic()-start,2),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (out/'material-review.json').write_text(json.dumps(records,indent=2)+'\n')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_sha
print('MATERIAL_REVIEW_COMPLETE',json.dumps(records))
