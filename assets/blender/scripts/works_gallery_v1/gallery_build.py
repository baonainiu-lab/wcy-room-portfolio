"""Approved B gallery: editable architecture, original furnishings and lighting."""
import bpy, math, json, random, sys, time
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from gallery_common import *

def frame(name,center,w,h,r,thickness,mat,parent,plane='XZ'):
    cx,cy,cz=center
    pts=[(cx+u,cy,cz+v) if plane=='XZ' else (cx+u,cy+v,cz) for u,v in outline(w,h,r,24)]
    return tube(name,pts,thickness,mat,parent,True)

def arch_geometry():
    root=group('gallery.architecture',(0,0,0),atlas=0)
    rounded_rect('Substantial silver foundation',(0,-.65,-.20),16.4,9.3,.58,1.35,M['silver'],root,'XY')
    rounded_rect('Blue platform fascia',(0,-.65,.045),16.04,8.98,.21,1.22,M['navy'],root,'XY')
    rounded_rect('Pale terrazzo inset',(0,-.65,.161),14.87,7.78,.025,1.10,M['terrazzo'],root,'XY')
    frame('Floor inlay border',(0,-.65,.181),15.0,7.94,1.16,.012,M['bronze'],root,'XY')
    frame('Floor metal perimeter',(0,-.65,.171),16.0,8.9,1.22,.026,M['silver'],root,'XY')
    # Thin inlaid joints separate physical tile panels without rough black edges.
    for x in [-5.4,-3.6,-1.8,0,1.8,3.6,5.4]:
        tube('Long stone seam',[(x,-3.7,.179),(x,2.9,.179)],.0035,M['ink'],root)
    for y in [-2.55,-.75,1.05]:
        tube('Cross stone seam',[(-6.65,y,.179),(6.65,y,.179)],.0035,M['ink'],root)
    # Continuous rounded back structural frame, thick enough to read as architecture.
    frame('Back structural blue core',(0,3.45,2.70),15.65,5.1,1.2,.17,M['navy'],root)
    frame('Back structural silver sleeve',(0,3.36,2.70),15.78,5.18,1.22,.105,M['silver'],root)
    box('Window base continuous rail',(0,3.42,.36),(14.2,.25,.34),M['navy'],root,.07)
    # Back panes remain separate meshes; glass does not become solid wall in export.
    glassroot=group('gallery.architecture.glazing',atlas=0)
    for i,x in enumerate([-5.3,-3.18,-1.06,1.06,3.18,5.3]):
        box('Panoramic clear panel '+str(i),(x,3.46,2.69),(2.08,.023,4.32),M['glass'],glassroot,.01)
    for x in [-6.38,-4.24,-2.12,0,2.12,4.24,6.38]:
        box('Slender window mullion',(x,3.39,2.72),(.065,.12,4.63),M['silver'],root,.022)
    # Roof ribs run front-to-back and cast the concept's distinct sunlight bands.
    ribxs=[-7.25,-4.75,-2.25,.25,2.75,5.25,7.25]
    for i,x in enumerate(ribxs):
        points=[]
        for j in range(41):
            t=j/40;y=3.45-t*5.2;z=5.18-.47*t+.10*math.sin(t*math.pi)
            points.append((x,y,z))
        tube('Silver roof rib '+str(i),points,.115,M['silver'],root)
        tube('Rib blue inset '+str(i),[(a,b,c-.07) for a,b,c in points],.062,M['navy'],root)
        for y in [2.7,-.8]:
            t=(3.45-y)/5.2;z=5.18-.47*t+.10*math.sin(t*math.pi)
            box('Rib machined connector',(x,y,z+.018),(.33,.33,.24),M['silver'],root,.065)
    # Deliberately transparent central skylight; no front wall over the exhibition.
    for i in range(len(ribxs)-1):
        left,right=ribxs[i]+.1,ribxs[i+1]-.1
        roof=mesh('Glass canopy segment '+str(i),[(left,3.45,5.19),(right,3.45,5.19),(right,-1.75,4.72),(left,-1.75,4.72)],[(0,1,2,3)],M['glass'],glassroot)
        roof['thin_glass']=True
    tube('Front canopy continuous rail',[(x,-1.75,4.72+.08*math.cos(x/7.25*math.pi/2)) for x in [(-7.25+j*14.5/100) for j in range(101)]],.15,M['silver'],root)
    # Support pillars at edges leave the cutaway entirely readable.
    for x in [-7.28,7.28]:
        pts=[(x,-1.75,.22),(x,-1.75,3.88)]
        pts += [(x,-1.75+.55*(1-math.cos(t)),3.88+.84*math.sin(t)) for t in [j*math.pi/2/30 for j in range(31)]]
        tube('Corner load-bearing column',pts,.17,M['silver'],root)
    # Lower outer deck and glazed safety edge complete non-front viewing angles.
    env=group('gallery.environment.terrace',atlas=1)
    rounded_rect('Secondary landscaped terrace',(0,1,-.63),22.2,14.2,.45,2.4,M['navy'],env,'XY')
    frame('Terrace silver band',(0,1,-.42),22.05,14.0,2.35,.08,M['silver'],env,'XY')
    for x in [-6.8,-3.4,0,3.4,6.8]:
        cyl('Terrace back rail post',(x,5.35,.28),.037,1.4,M['silver'],env)
    tube('Terrace top handrail',[(-7,5.35,.98),(7,5.35,.98)],.034,M['silver'],env)
    for i in range(4):box('Clear terrace balustrade',(-5.1+i*3.4,5.35,.43),(3.3,.018,1.0),M['glass'],env,.005)
    for i in range(3):
        rounded_rect('Entry step '+str(i),(0,-5.4-i*.34,-.04-i*.16),5.4+i*.35,.8,.17,.17,M['silver'],root,'XY')
    return root

def portal():
    root=group('gallery.architecture.portal',atlas=0)
    # Left wall: the gateway faces into the gallery. New doorway, not a hole in the old room.
    for x in [-7.30,-8.7]:
        for i,(w,h,r,thick,mat) in enumerate([(3.7,4.65,.90,.19,M['navy']),(3.50,4.44,.83,.075,M['silver']),(3.22,4.14,.74,.015,M['warm'])]):
            points=[(x,u-.05,v+2.48) for u,v in outline(w,h,r,24)]
            tube('Gateway rounded frame',points,thick,mat,root,True)
    # Solid ring wall pieces add mass without covering the passage aperture.
    box('Gateway rear pier',(-7.36,2.01,2.50),(.43,.62,4.75),M['navy'],root,.16)
    box('Gateway front pier',(-7.36,-2.07,2.50),(.43,.62,4.75),M['navy'],root,.16)
    box('Gateway lintel',(-7.36,0,4.64),(.43,3.55,.60),M['navy'],root,.19)
    for x in [-7.9,-8.35]:
        tube('Passage ceiling arch',[(x,u-.05,v+2.48) for u,v in outline(3.48,4.4,.85,20)],.055,M['silver'],root,True)
    box('Passage threshold',(-8.05,0,.20),(2.4,3.4,.13),M['silver'],root,.04)
    for y in [-1.53,1.43]:box('Passage side lining',(-8.05,y,2.36),(1.4,.15,3.85),M['navy'],root,.045)
    # A soft dark end indicates a connector awaiting final spatial integration.
    box('Connection return wall',(-9.23,0,2.3),(.12,3.25,4.1),M['navy'],root,.04)
    box('Connection vertical bronze inlay',(-9.15,.8,2.3),(.022,.04,3.2),M['bronze'],root,.008)
    sign=label('Works doorway sign','MY\nWORKS',(-7.09,-1.98,2.55),.19,M['ivory'],root,rotation=(math.pi/2,0,math.pi/2))
    area('Passage amber',(-8.6,0,3.95),(-7,0,.3),140,(1,.64,.33),1.4)

def landscape():
    random.seed(27);root=group('gallery.environment.city',atlas=1)
    # Broad architecture behind and below the glazed hall prevents empty background.
    box('Urban landscape base',(0,14,-1.43),(100,90,1.2),M['ivory'],root,.3)
    for row,y in enumerate([9,16,26,39]):
        for i in range(11):
            x=(i-5)*6.0+random.uniform(-1.5,1.5)
            w=random.uniform(1.15,2.4);height=random.uniform(3,8)+(2 if row>1 else 0)
            groupmat=M['silver'] if i%3==0 else M['ivory']
            rounded_rect('Distant rounded city tower',(x,y,height/2-1),w,height,random.uniform(1,1.9),min(.45,w*.2),groupmat,root,'XZ')
            for j in range(2):
                box('City vertical glazed fin',(x+(j-.5)*w*.4,y-.94,height/2-1),(.045,.08,height*.75),M['navy'],root,.01)
            if i%3==0:cyl('City spire',(x,y,height-.6),.045,1.0,M['silver'],root,vertices=16)
    for y,z in [(11,1.4),(22,2.0)]:
        tube('City elevated transit edge',[(-38+j*.8,y+.0008*(-38+j*.8)**2,z) for j in range(96)],.15,M['silver'],root)
    # Terrace planters and restrained botanical silhouettes at mid distance.
    for i,x in enumerate([-10,-8,-4,0,4,8,10]):
        y=6.9+abs(x)*.15
        rounded_rect('Terrace planting box',(x,y,-.04),2.3,1.3,.8,.35,M['navy'],root,'XY')
        box('Planter soil',(x,y,.39),(1.9,1.0,.06),M['soil'],root,.08)
        for n in range(15):
            dx=random.uniform(-.8,.8);dy=random.uniform(-.35,.35);z=.65+random.uniform(0,.60)
            # Small ellipsoidal leaves in clusters, not tall front occluding trees.
            leaf=sphere('Landscape leaf',(x+dx,y+dy,z),(.16,.10,.32),M['leaf'],root);leaf.rotation_euler=(random.uniform(-.6,.6),random.uniform(-.6,.6),random.random()*6.28)
    for x in [-9,-5,0,5,9]:
        y=6.0; cyl('Exterior lantern base',(x,y,-.12),.21,.32,M['silver'],root)
        cyl('Exterior lantern core',(x,y,.20),.13,.38,M['warm'],root)
        cyl('Exterior lantern cap',(x,y,.43),.21,.08,M['bronze'],root)

def configure_camera(scene):
    data=bpy.data.cameras.new('Gallery overview camera');camera=bpy.data.objects.new('Gallery overview camera',data);scene.collection.objects.link(camera)
    camera.location=(15.5,-26,14.9);target=Vector((-.4,.15,1.65));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO';data.ortho_scale=21.8;data.clip_end=300;camera['export_exclude']=True;scene.camera=camera

def set_lighting(scene,state):
    if not scene.world:scene.world=bpy.data.worlds.new('Gallery physical sky')
    world=scene.world;world.use_nodes=True;tree=world.node_tree;tree.nodes.clear()
    output=tree.nodes.new('ShaderNodeOutputWorld');bg=tree.nodes.new('ShaderNodeBackground');tree.links.new(bg.outputs[0],output.inputs['Surface'])
    if state=='day':
        sky=tree.nodes.new('ShaderNodeTexSky');sky.sky_type='MULTIPLE_SCATTERING';sky.sun_elevation=.52;sky.sun_rotation=2.40;sky.sun_disc=False;sky.air_density=1.15;sky.aerosol_density=.35
        tree.links.new(sky.outputs[0],bg.inputs[0]);bg.inputs[1].default_value=.055
    else:
        bg.inputs[0].default_value=(.035,.065,.115,1);bg.inputs[1].default_value=.34
    for obj in scene.objects:
        if obj.type!='LIGHT':continue
        if obj.data.type=='SUN':obj.data.energy=3.5 if state=='day' else .07;obj.data.color=(1,.86,.64) if state=='day' else (.40,.57,1)
        else:obj.data.energy=obj.get('base_power',obj.data.energy)*(.16 if state=='day' else 1)
    for mat in bpy.data.materials:
        if mat.name.startswith('GALLERY_warm'):
            p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Strength'].default_value=1.2 if state=='day' else 3.3
        if mat.get('gallery_city') and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type=='BSDF_PRINCIPLED' and not node.inputs['Emission Strength'].is_linked:
                    node.inputs['Emission Strength'].default_value=mat.get('day_emission',0)*(1 if state=='day' else .035)
    scene['lighting_state']=state;scene.view_settings.exposure=.18 if state=='day' else .0
    return {'state':state,'sunEnergy':3.5 if state=='day' else .07,'worldStrength':bg.inputs[1].default_value}

def lighting(scene):
    data=bpy.data.lights.new('Gallery directional sunlight','SUN');data.angle=math.radians(1.1)
    obj=bpy.data.objects.new('Gallery directional sunlight',data);scene.collection.objects.link(obj)
    obj.location=(8,6,12);obj.rotation_euler=(Vector((-3,-4,0))-obj.location).to_track_quat('-Z','Y').to_euler();obj['export_exclude']=True
    for index,x in enumerate([-4.8,-2.7,-.6,1.5,3.6,5.7]):area('Warm exhibit spotlight '+str(index),(x,1.90,3.85),(x,2.05,1.55),170,(1,.72,.42),.65)
    area('Warm table wash',(.2,-.45,4.3),(.2,-.5,.6),240,(1,.77,.52),3.5)
    for x in [-6.2,6.2]:area('Low lantern light',(x,-2.2,.95),(x,-1.7,.15),50,(1,.56,.22),.42)
    area('Dusk skylight bounce',(0,2.5,7),(0,0,1),500,(.42,.59,1),7)
    set_lighting(scene,'day')

def run():
    start=time.time()
    if bpy.data.scenes.get('WORKS_GALLERY_V1'):raise RuntimeError('Gallery scene exists; open a clean source or use a versioned build.')
    scene=bpy.data.scenes.new('WORKS_GALLERY_V1');bpy.context.window.scene=scene
    init_materials();arch_geometry();portal();landscape()
    import gallery_exhibits,gallery_furnishings
    exhibits=gallery_exhibits.build();furnishings=gallery_furnishings.build()
    configure_camera(scene);lighting(scene)
    refine_canopy(scene)
    import refine_gallery
    refine_gallery.run(scene)
    return finalize(scene,start,exhibits,furnishings)

def refine_canopy(scene):
    """Expose the works below a shallow back canopy, matching the approved cutaway."""
    if scene.get('canopy_refined'):return
    def roof_point(v,offset=0):
        t=(3.45-v[1])/5.2
        return (v[0],3.45-2.25*t,5.18-.18*t+.08*math.sin(t*math.pi)+offset)
    for obj in scene.objects:
        name=obj.name
        if name.startswith(('Silver roof rib','Rib blue inset')):
            for spl in obj.data.splines:
                for p in spl.points:p.co=(*roof_point(p.co,-.07 if name.startswith('Rib blue') else 0),1)
        elif name.startswith('Rib machined connector'):
            obj.location=roof_point(obj.location,.02)
        elif name.startswith('Glass canopy segment'):
            for v in obj.data.vertices:v.co=roof_point(v.co,.012)
        elif name.startswith('Front canopy continuous rail'):
            for spl in obj.data.splines:
                for p in spl.points:p.co=(p.co.x,1.2,5.0+.045*math.cos(p.co.x/7.25*math.pi/2),1)
        elif name.startswith('Corner load-bearing column'):
            for spl in obj.data.splines:
                for p in spl.points:p.co=(p.co.x,p.co.y+2.95,.22+(p.co.z-.22)*1.062,1)
    c=scene.camera;c.location=(17,-28,16);c.rotation_euler=(Vector((-.45,0,1.8))-c.location).to_track_quat('-Z','Y').to_euler();c.data.type='PERSP';c.data.lens=52
    scene['canopy_refined']=True

def finalize(scene,start=None,exhibits=None,furnishings=None):
    start=start or time.time()
    scene.render.engine='CYCLES';scene.cycles.samples=64;scene.cycles.use_denoising=True;scene.cycles.max_bounces=7;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=6
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
        for d in prefs.devices:d.use=d.type=='METAL'
        scene.cycles.device='GPU'
    except Exception:scene.cycles.device='CPU'
    scene.view_settings.view_transform='AgX';scene.render.resolution_x=1800;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8';scene.render.film_transparent=False
    ids=[obj['asset_id'] for obj in scene.objects if obj.get('asset_id')];assert len(ids)==len(set(ids))
    scene['concept']='B 日光玻璃长廊';scene['concept_sha256']='0087d6b949e0f571f2f073c337de23878542bdd14be289ebb381815c8b089acd';scene['content_status']='Concept placeholders; personal project details pending';scene['model_revision']=1
    path=ROOT/'assets/blender/works-gallery-v1.blend'
    bpy.data.libraries.write(str(path),{scene},fake_user=True,compress=True)
    report={'source':str(path.relative_to(ROOT)),'scene':scene.name,'sourcePreserved':bpy.data.filepath,'objects':len(scene.objects),'assetCount':len(ids),'assetIds':ids,'exhibits':exhibits,'furnishings':furnishings,'seconds':time.time()-start,'approval':'User chose B with attached image 2026-09-24','state':'model_complete_render_pending','personalProjects':'pending','websiteIntegrated':False}
    (ROOT/'assets/blender/works-gallery-v1/model-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(report,ensure_ascii=False,default=str))
    return report

if __name__=='__main__':run()
