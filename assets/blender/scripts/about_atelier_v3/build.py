"""Reproducible Blender source for user-approved Archive Atelier A."""
import bpy,sys,math,json,hashlib,time
from pathlib import Path
from mathutils import Vector
P=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
HERE=P/'assets/blender/scripts/about_atelier_v3';sys.path.insert(0,str(HERE))
bpy.ops.wm.read_factory_settings(use_empty=True)
import kit as K
import archive,workbench,dressing,environment
K.materials()
s=bpy.context.scene;s.name='ABOUT_ATELIER_V3_APPROVAL';s.unit_settings.system='METRIC';s.unit_settings.scale_length=1

def collected(name,fn,export=True):
    before=set(bpy.data.objects);fn();created=set(bpy.data.objects)-before
    coll=bpy.data.collections.new(name);s.collection.children.link(coll);coll['web_export_candidate']=export
    for o in created:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
        if not export:o['web_export']=False;o['interactive']=False
    return coll

collected('01_ATELIER_Platform',environment.platform)
collected('02_ATELIER_Archive',archive.build)
collected('03_ATELIER_Workbench',workbench.build)
collected('04_ATELIER_Furniture',dressing.build)
collected('90_RENDER_Atrium_Lake',environment.surroundings,False)
collected('91_RENDER_Lighting',environment.lighting,False)
# Place actual task emitter inside the agent-authored lamp shade.
if 'warm.desk' in bpy.data.objects:
    o=bpy.data.objects['warm.desk'];o.location=(1.43,.14,3.18)
    o.rotation_euler=(Vector((1.35,-.28,1.66))-o.location).to_track_quat('-Z','Y').to_euler()

def camera(name,loc,target,lens):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.lens=lens;d.clip_end=500
    return o

s.camera=camera('CAM.hero',(8.0,-12.3,5.2),(0,.20,1.95),53.5)
s.camera.data.shift_x=-.012;s.camera.data.shift_y=-.06
camera('CAM.awards',(-.1,-5.3,4.0),(-1.72,.86,1.90),54)
camera('CAM.desk',(6.9,-5.2,5.0),(1.48,.30,1.83),54)
camera('CAM.chair',(3.5,-5.7,2.6),(.8,-1.55,1.07),63)
s.render.engine='CYCLES';s.cycles.samples=128;s.cycles.use_denoising=True;s.cycles.max_bounces=16;s.cycles.transmission_bounces=12;s.cycles.transparent_max_bounces=24
s.render.resolution_x=2400;s.render.resolution_y=1600;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=.25
s.render.film_transparent=False
try:
    pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='METAL';pref.get_devices()
    for d in pref.devices:d.use=d.type=='METAL'
    s.cycles.device='GPU'
except Exception as exc: print('GPU fallback:',exc)

for ob in s.objects:
    if ob.type=='MESH' and not ob.data.uv_layers:
        uv=ob.data.uv_layers.new(name='Local_metre_projection')
        for f in ob.data.polygons:
            axis=max(range(3),key=lambda i:abs(f.normal[i]));xy=[i for i in range(3) if i!=axis]
            for li in f.loop_indices:
                v=ob.data.vertices[ob.data.loops[li].vertex_index].co;uv.data[li].uv=(v[xy[0]],v[xy[1]])
    if ob.get('asset_id'):
        ob['original_location']=list(ob.location);ob['original_rotation']=list(ob.rotation_euler);ob['original_scale']=list(ob.scale)
s.camera.data.dof.use_dof=True;s.camera.data.dof.focus_distance=(s.camera.location-Vector((0,.20,1.95))).length;s.camera.data.dof.aperture_fstop=6.3
s['reference_image']='renders/about-photoreal-v3/a-archive-atelier.png'
s['reference_sha256']='9c9f624a750f47a17c6ab2ef02f92d008e9f54843425f386c5da7e0b93050509'
s['concept_approval']='用户：就按照这个建模吧还原灯光以及贴图材质'
s['render_approval']='pending';s['website_integrated']=False
fontlicense=P/'assets/font-candidates/v4/douyin-upstream/DouyinSans/OFL.txt'
if not fontlicense.exists():
    hits=list((P/'assets/font-candidates/v4/douyin-upstream').rglob('*OFL*'));fontlicense=hits[0] if hits else None
for title,path in [('FONT_LICENSE_OFL.txt',fontlicense),('TEXTURE_SOURCES.md',P/'assets/textures/about-atelier-v3/README.md')]:
    if path and path.exists():bpy.data.texts.new(title).write(path.read_text())
bpy.data.texts.new('ABOUT_ATELIER_V3_README.txt').write('New independent Blender model matching approved A archive atelier concept. Physical PBR materials and daylight. All awards/skills/contact content is placeholder. Interactive roots are separate and carry stable asset_id/original transforms. Atrium/lake is offline render context, not approved web environment. Render approval pending; website not integrated. Original room/gallery unaffected.')
bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
out=P/'assets/blender/about-atelier-v3.blend';bpy.ops.wm.save_as_mainfile(filepath=str(out))
summary={'source':str(out),'scene':s.name,'objects':len(s.objects),'meshes':sum(o.type=='MESH' for o in s.objects),'materials':len(bpy.data.materials),'images':len(bpy.data.images),'interactive':sum(bool(o.get('interactive')) for o in s.objects),'approval':'pending','websiteIntegrated':False}
(P/'assets/blender/about-atelier-v3-manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('ATELIER_BUILD_DONE',json.dumps(summary,ensure_ascii=False))

