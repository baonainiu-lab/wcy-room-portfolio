"""Read-only true V4 main and structural detail Cycles renders."""
import bpy,sys,json,time,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from gallery_build import set_lighting
import bake_gallery as b
SOURCE=ROOT/'assets/blender/works-gallery-v4.blend';source_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.data.scenes['WORKS_GALLERY_V4'];bpy.context.window.scene=s
s.render.engine='CYCLES';s.cycles.samples=16 if '--draft' in sys.argv else 72;s.cycles.use_denoising=True;b._device(s);s.render.resolution_x=1200 if '--draft' in sys.argv else 2000;s.render.resolution_y=800 if '--draft' in sys.argv else 1200;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
bpy.ops.mesh.primitive_plane_add(size=400,location=(0,0,-.88));floor=bpy.context.object;floor['export_exclude']=True;mat=bpy.data.materials.new('V4 temporary render floor');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.40,.43,1);mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;floor.data.materials.append(mat)
out=ROOT/'renders/works-gallery-v4';out.mkdir(parents=True,exist_ok=True);camera=s.camera;original=(camera.location.copy(),camera.rotation_euler.copy(),camera.data.lens);records=[]
views=[('day','day',None,None,57),('right-end-detail','day',(20,-15,8),(3,1,2.4),65)] if '--draft' in sys.argv else [('day','day',None,None,57),('night','night',None,None,57),('right-end-detail','day',(20,-15,8),(3,1,2.4),65),('portal-detail','day',(-17,-14,7),(-6.7,0,2.4),64)]
for name,state,pos,target,lens in views:
 set_lighting(s,state)
 if pos:camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=lens
 else:camera.location,camera.rotation_euler,camera.data.lens=original
 path=out/(name+('-draft' if '--draft' in sys.argv else '')+'.png');s.render.filepath=str(path);t=time.monotonic();bpy.ops.render.render(write_still=True);records.append({'source_sha256':source_sha,'source_blend_written':False,'path':str(path.relative_to(ROOT)),'state':state,'samples':s.cycles.samples,'seconds':round(time.monotonic()-t,2),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'resolution':[s.render.resolution_x,s.render.resolution_y]})
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_sha
(out/('render-draft.json' if '--draft' in sys.argv else 'render-final.json')).write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
