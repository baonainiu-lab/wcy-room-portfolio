import bpy,sys
from pathlib import Path
P=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
out=P/'renders/about-nexus-v2';out.mkdir(exist_ok=True,parents=True)
s=bpy.context.scene
mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'day'
try:
    p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='METAL';p.get_devices()
    for d in p.devices:d.use=d.type=='METAL'
    if any(d.use for d in p.devices):s.cycles.device='GPU'
except Exception as e:print(e)
s.cycles.samples=80;s.cycles.use_denoising=True
if mode=='draft':
    s.cycles.samples=24;s.render.resolution_x=1200;s.render.resolution_y=982
elif mode=='night':
    bg=next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND')
    for l in list(bg.inputs['Color'].links):s.world.node_tree.links.remove(l)
    bg.inputs['Color'].default_value=(.17,.22,.28,1);bg.inputs['Strength'].default_value=.21
    for o in s.objects:
        if o.type!='LIGHT':continue
        if o.name=='day.sun':o.data.energy=.05;o.data.color=(.6,.73,1)
        elif o.name=='day.key':o.data.energy=160;o.data.color=(.64,.74,1)
        elif o.name=='day.rim':o.data.energy=340;o.data.color=(.56,.76,1)
        elif o.name=='day.front':o.data.energy=150;o.data.color=(.81,.87,1)
        elif o.name.startswith('warm.'):o.data.energy*=1.45
    s.view_settings.exposure=.4
elif mode in ['awards','workstation']:
    s.camera=bpy.data.objects['CAM.'+mode];s.render.resolution_x=1800;s.render.resolution_y=1500
s.render.filepath=str(out/(mode+'.png'));bpy.ops.render.render(write_still=True)
print('RENDER_DONE',mode)
