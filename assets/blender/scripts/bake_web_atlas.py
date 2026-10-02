"""Execute through Blender MCP after prepare_web_bake.py.
Set ATLAS_INDEX=0..3 in the caller; await check_is_finished before starting next.
The temporary unified bake proxy reduces per-object bake overhead while the
original independent meshes/UVs remain intact for export.
"""
import bpy,time
from pathlib import Path
index=int(ATLAS_INDEX)
if index not in range(4):raise ValueError('ATLAS_INDEX must be 0..3')
if bpy.app.is_job_running('OBJECT_BAKE'):raise RuntimeError('Wait for the previous bake to finish')
s=bpy.data.scenes['WEB_BAKE_V4'];bpy.context.window.scene=s
originals=[o for o in s.objects if o.get('bake_atlas')==index and not o.get('is_bake_proxy')]
visibility={o.name:o.hide_render for o in originals};bpy.ops.object.select_all(action='DESELECT');proxies=[]
for o in originals:
 n=o.copy();n.data=o.data.copy();s.collection.objects.link(n);mx=o.matrix_world.copy();n.parent=None;n.matrix_world=mx;n.select_set(True);proxies.append(n);o.hide_render=True
bpy.context.view_layer.objects.active=proxies[0];bpy.ops.object.join();proxy=bpy.context.object;proxy.name=f'BAKE_PROXY_{index}';proxy['is_bake_proxy']=True
started=time.monotonic();bpy.ops.object.bake('INVOKE_DEFAULT',type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','GLOSSY','EMIT'},uv_layer='BakeUV',margin=12,use_clear=True)
def check_is_finished():
 if bpy.app.is_job_running('OBJECT_BAKE'):return None
 out=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio/assets/textures/baked');out.mkdir(exist_ok=True,parents=True)
 s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
 bpy.data.images[f'ROOM_BAKED_{index}'].save_render(str(out/f'room-night-{index}.png'),scene=s)
 bpy.data.objects.remove(proxy,do_unlink=True)
 for name,hidden in visibility.items():s.objects[name].hide_render=hidden
 return {'atlas':index,'seconds':time.monotonic()-started,'path':str(out/f'room-night-{index}.png')}
