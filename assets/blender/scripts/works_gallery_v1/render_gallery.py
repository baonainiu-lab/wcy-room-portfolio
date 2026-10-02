"""Real Cycles acceptance renders; saves lighting back to the new gallery only."""
import bpy,sys,json,time,hashlib,argparse
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from gallery_build import set_lighting
ROOT=HERE.parents[3]

def run():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--state',choices=['day','night','both'],default='both');p.add_argument('--draft',action='store_true');args=p.parse_args(argv)
    scene=bpy.data.scenes['WORKS_GALLERY_V1'];bpy.context.window.scene=scene
    scene.render.engine='CYCLES';scene.cycles.samples=28 if args.draft else 72;scene.cycles.use_denoising=True
    scene.render.resolution_x=1400 if args.draft else 2000;scene.render.resolution_y=1000 if args.draft else 1200;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='METAL';prefs.get_devices()
        for device in prefs.devices:device.use=device.type=='METAL'
        scene.cycles.device='GPU'
    except Exception:scene.cycles.device='CPU'
    states=['day','night'] if args.state=='both' else [args.state];records=[]
    for state in states:
        started=time.time();set_lighting(scene,state)
        path=ROOT/'renders/works-gallery-v1'/f'{state}{"-draft" if args.draft else ""}.png';scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        records.append({'path':str(path.relative_to(ROOT)),'state':state,'resolution':[scene.render.resolution_x,scene.render.resolution_y],'samples':scene.cycles.samples,'seconds':round(time.time()-started,2),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'type':'actual Blender Cycles render, not concept image','device':scene.cycles.device})
    label='draft' if args.draft else 'final'
    (ROOT/'renders/works-gallery-v1'/f'render-{label}-{args.state}.json').write_text(json.dumps(records,indent=2)+'\n')
    if not args.draft:
        set_lighting(scene,'day')
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v1.blend'),compress=True)
    print(json.dumps(records));return records
if __name__=='__main__':run()
