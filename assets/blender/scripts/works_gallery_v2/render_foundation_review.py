"""Read-only native previews of V2 podium and skyline foundations."""
import bpy,sys,json,time,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v2.blend'))
s=bpy.data.scenes['WORKS_GALLERY_V2'];bpy.context.window.scene=s
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='METAL'
s.cycles.device='GPU';s.render.resolution_x=1200;s.render.resolution_y=820;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
out=ROOT/'renders/works-gallery-v2';out.mkdir(parents=True,exist_ok=True)
camera=s.camera;records=[]
views=[('day-foundation-overview','day',(52,-65,37),(0,21,-.8),50),('day-podium-low','day',(23,-28,4),(0,4,-1),42),('day-city-supports','day',(48,12,3),(-4,37,.3),48)]
for name,state,pos,target,lens in views:
    set_lighting(s,state);camera.location=pos;camera.rotation_euler=(Vector(target)-Vector(pos)).to_track_quat('-Z','Y').to_euler();camera.data.lens=lens
    path=out/(name+'.png');s.render.filepath=str(path);started=time.monotonic();bpy.ops.render.render(write_still=True)
    records.append({'name':name,'path':str(path.relative_to(ROOT)),'state':state,'camera':pos,'target':target,'lens':lens,'resolution':[1200,820],'samples':24,'engine':'Cycles Metal','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seconds':round(time.monotonic()-started,2)})
(out/'foundation-review-renders.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
