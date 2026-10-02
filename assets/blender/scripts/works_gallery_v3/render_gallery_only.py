"""Native same-camera V3 day/night renders for the room's live gallery preview."""
import bpy,sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v3.blend'))
s=bpy.data.scenes['WORKS_GALLERY_V3'];bpy.context.window.scene=s
s.render.engine='CYCLES';s.cycles.samples=72;s.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='METAL'
s.cycles.device='GPU';s.render.resolution_x=2000;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
# A plain render-only floor matches the native web stage at -0.88. It is not
# a city/platform asset, not saved to the source and never exported to the GLB.
bpy.ops.mesh.primitive_plane_add(size=1800,location=(0,0,-.88));floor=bpy.context.object;floor.name='V3 neutral render-only floor';floor['export_exclude']=True
mat=bpy.data.materials['GALLERY_ivory'].copy();mat.name='V3_RENDER_ONLY_NEUTRAL_FLOOR';p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.36,.40,.43,1);p.inputs['Roughness'].default_value=.8;p.inputs['Metallic'].default_value=0;floor.data.materials.append(mat)
out=ROOT/'renders/works-gallery-v3';out.mkdir(parents=True,exist_ok=True);records=[];source_sha=hashlib.sha256((ROOT/'assets/blender/works-gallery-v3.blend').read_bytes()).hexdigest()
for state in ('day','night'):
    set_lighting(s,state);path=out/(state+'.png');s.render.filepath=str(path);started=time.monotonic();bpy.ops.render.render(write_still=True)
    records.append({'path':str(path.relative_to(ROOT)),'state':state,'resolution':[2000,1200],'samples':72,'engine':'Cycles','device':'Metal GPU','seconds':round(time.monotonic()-started,2),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'camera_location':list(s.camera.location),'camera_rotation':list(s.camera.rotation_euler),'lens':s.camera.data.lens,'camera_unchanged_from_v1':True,'render_only_floor_y':-.88,'no_city_or_surrounding_geometry':True})
assert hashlib.sha256((ROOT/'assets/blender/works-gallery-v3.blend').read_bytes()).hexdigest()==source_sha
(out/'render-final-both.json').write_text(json.dumps({'complete':True,'source_sha256':source_sha,'source_unchanged':True,'renders':records},indent=2)+'\n');print(json.dumps(records))
