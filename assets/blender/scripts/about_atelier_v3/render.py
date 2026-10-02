import bpy,sys
from pathlib import Path
P=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
s=bpy.context.scene;mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'hero'
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='METAL'
    s.cycles.device='GPU'
except Exception as ex:print(ex)
s.cycles.samples=128;s.cycles.use_denoising=True
if mode=='draft':s.cycles.samples=24;s.render.resolution_x=1440;s.render.resolution_y=960
elif mode in ['awards','desk','chair']:
    s.camera=bpy.data.objects['CAM.'+mode];s.render.resolution_x=1800;s.render.resolution_y=1500
out=P/'renders/about-atelier-v3';out.mkdir(parents=True,exist_ok=True)
s.render.filepath=str(out/(mode+'.png'));bpy.ops.render.render(write_still=True)
print('ATELIER_RENDER_DONE',mode)
