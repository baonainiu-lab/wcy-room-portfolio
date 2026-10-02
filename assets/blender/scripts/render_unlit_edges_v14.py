"""Render the actual exported GLB maps, not the original PBR source.

Uses the prepared source camera, the exported unlit materials and web night
exterior factors. This isolates the new baked edges for inspection; the web
browser remains the final evidence for sampling, animation and performance.
"""
import bpy,sys,json
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')

def run():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v14.blend'))
    source=bpy.data.scenes['WEB_DUAL_V8'];camera=source.camera.copy();camera.data=source.camera.data.copy();worldmatrix=source.camera.matrix_world.copy()
    scene=bpy.data.scenes.new('V14_GLTF_UNLIT_PROOF');bpy.context.window.scene=scene;scene.collection.objects.link(camera);camera.matrix_world=worldmatrix;scene.camera=camera
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/models/orbital-atelier-v14.glb'))
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
        for device in prefs.devices:device.use=device.type=='METAL'
        scene.cycles.device='GPU'
    except Exception:scene.cycles.device='CPU'
    scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    scene.world=bpy.data.worlds.new('V14 proof background');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.013,.019,.032,1)
    materials={m for o in scene.objects if o.type=='MESH' for m in o.data.materials if m}
    for state in ('night','day'):
        for mat in materials:
            if not mat.node_tree:continue
            atlas=None
            if mat.name.startswith('WEB8_LIGHTMAP_'):
                atlas=int(mat.name.removeprefix('WEB8_LIGHTMAP_').split('.')[0])
                path=ROOT/'public/textures/lighting-v14'/f'{state}-{atlas}.png'
            elif mat.name.startswith('WEB8_WINDOW_CITY'):
                path=ROOT/'public/textures/lighting-v14'/f'window-{state}.png'
            else:continue
            image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='sRGB'
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE':node.image=image
            # Unlit glTF imports may use either an Emission or Principled node.
            scale=.28 if state=='night' and atlas==5 else .12 if state=='night' and atlas==6 else 1.
            for node in mat.node_tree.nodes:
                if node.type=='EMISSION':node.inputs['Strength'].default_value=scale
        scene.render.filepath=str(ROOT/'renders'/f'edge-precision-v14-{state}-unlit.png')
        bpy.ops.render.render(write_still=True)
    report={'model':'public/models/orbital-atelier-v14.glb','type':'actual GLB imported into Blender; exported unlit maps, Standard display transform','limitation':'Not a browser screenshot or performance measurement. Prepared source camera, separate static background; web glass and viewport sampling may differ.','outputs':[f'renders/edge-precision-v14-{s}-unlit.png' for s in ('night','day')]}
    (ROOT/'renders/edge-precision-v14-unlit-proof.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':run()
