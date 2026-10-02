"""About Nexus V2: freestanding circular archive apparatus, approval only."""
import bpy, sys, math, json
from pathlib import Path
from mathutils import Vector
P=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0,str(P/'assets/blender/scripts/about_nexus_v2'))
bpy.ops.wm.read_factory_settings(use_empty=True)
from kit import *
from award_capsules import build_award_capsules
from skill_engine import build_skill_engine
materials();s=bpy.context.scene;s.name='ABOUT_NEXUS_V2_REVIEW'
s['approval']='pending_user_review';s['website_integrated']=False
bpy.context.preferences.filepaths.save_version=0
floor=root('about.nexus.platform');floor['interactive']=False

# Freestanding circular machinery foundation, complete solid underside.
cylinder('platform.lower',(0,0,.06),4.64,.22,M['rubber'],floor,160)
cylinder('platform.chassis',(0,0,.24),4.74,.22,M['navy'],floor,160)
arc('platform.metal_belt',(0,0,0),4.66,4.79,.27,.35,0,360,M['metal'],floor)
cylinder('platform.top',(0,0,.411),4.65,.15,M['dark'],floor,160)
cylinder('platform.stone',(0,0,.515),4.48,.09,M['stone'],floor,160)
torus('platform.inset_rim',(0,0,.563),4.48,.012,M['brass'],floor)
arc('deck.walnut_arc',(0,0,0),3.44,4.40,.559,.564,205,335,M['wood'],floor,.001)
for a in range(205,336,13):
    t=math.radians(a);tube('deck.wood_joint',[(3.45*math.cos(t),3.45*math.sin(t),.565),(4.40*math.cos(t),4.40*math.sin(t),.565)],.004,M['rubber'],floor)
for a in range(0,360,30):
    if 200<a<340:continue
    t=math.radians(a)
    tube('deck.radial_joint',[(3.27*math.cos(t),3.27*math.sin(t),.563),(4.44*math.cos(t),4.44*math.sin(t),.563)],.006,M['rubber'],floor)
    o=box('deck.bolt_mount',(4.27*math.cos(t),4.27*math.sin(t),.566),(.18,.09,.012),M['metal'],floor,.011);o.rotation_euler.z=t
    cylinder('deck.captive_bolt',(4.27*math.cos(t),4.27*math.sin(t),.576),.021,.009,M['dark'],floor,24)
for a in [8,70,130,175,350]:
    arc('platform.segmented_lamp',(0,0,0),4.728,4.746,.218,.234,a,a+20,M['light'],floor,.004)
for i in range(24):
    a=math.radians(45+i*5)
    o=box('platform.radial_cooling',(4.742*math.cos(a),4.742*math.sin(a),.228),(.017,.055,.08),M['rubber'],floor,.004);o.rotation_euler.z=a
# A shallow fan-shaped threshold and engraved entry tab.
arc('entry.lower',(0,0,0),4.1,5.04,-.018,.123,251,289,M['dark'],floor,.024)
arc('entry.cap',(0,0,0),4.15,5.01,.124,.162,251,289,M['metal'],floor,.01)
for r in [4.65,4.78,4.91]:arc('entry.traction',(0,0,0),r,r+.015,.163,.166,256,284,M['rubber'],floor,.0004)
text('entry.about','ABOUT',(0,-4.06,.567),.17,M['ivory'],floor,(0,0,0))

# Main C-shaped work surface: warm timber, inward opening, exposed machined legs.
desk=root('about.nexus.worktable',(0,-.68,.562))
arc('worktable.lower_beam',(0,0,0),1.13,1.78,.18,.35,-25,205,M['navy'],desk,.025)
arc('worktable.body',(0,0,0),1.17,1.80,.95,1.13,-25,205,M['orange'],desk,.035)
arc('worktable.metal_lip',(0,0,0),1.13,1.84,1.13,1.19,-25,205,M['metal'],desk,.015)
arc('worktable.wood_top',(0,0,0),1.18,1.79,1.19,1.255,-25,205,M['wood'],desk,.014)
arc('worktable.inner_inlay',(0,0,0),1.22,1.234,1.256,1.26,-22,202,M['brass'],desk,.001)
arc('worktable.underlight',(0,0,0),1.158,1.177,1.01,1.04,-21,201,M['light'],desk,.004)
for a in [0,68,140,185]:
    t=math.radians(a);x,y=1.47*math.cos(t),1.47*math.sin(t)
    cylinder('table.foot',(x,y,.035),.18,.07,M['rubber'],desk)
    cylinder('table.satin_column',(x,y,.50),.085,.88,M['metal'],desk)
    cylinder('table.column_collar',(x,y,.87),.13,.08,M['navy'],desk)
    for z in [.18,.32,.46]:torus('table.column_ring',(x,y,z),.087,.006,M['dark'],desk)
    o=box('table.radial_bracket',(x,y,.937),(.49,.10,.045),M['navy'],desk,.013);o.rotation_euler.z=t
for a in range(4,200,8):
    t=math.radians(a)
    o=box('table.case_seam',(1.805*math.cos(t),1.805*math.sin(t),1.04),(.008,.027,.079),M['dark'],desk,.002);o.rotation_euler.z=t

# New cluster assemblies sit on the floor, rather than in a repeated wall.
awards=build_award_capsules(api());awards.location=(-2.68,1.21,.562)
rear_sculpture=bpy.data.objects['about.award.03.sculpture'];rear_sculpture.location.z+=.38
cylinder('award.rear.elevating_plinth',(0,0,.445),.19,.38,M['navy'],bpy.data.objects['about.award.03'])
torus('award.rear.plinth_trim',(0,0,.623),.188,.007,M['brass'],bpy.data.objects['about.award.03'])
skills=build_skill_engine(api());skills.location=(2.48,1.22,.562);skills.rotation_euler.z=math.radians(-16)
# Display glazing uses a restrained edge reflection so the award remains readable.
glazing=M['glass'].copy();glazing.name='NEXUS_anti_reflection_display_glazing'
nt=glazing.node_tree;pr=nt.nodes.get('Principled BSDF');pr.inputs['Specular IOR Level'].default_value=.22
pr.inputs['Transmission Weight'].default_value=0;pr.inputs['Metallic'].default_value=1
pr.inputs['Base Color'].default_value=(.95,.98,.97,1)
trans=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader')
fresnel=nt.nodes.new('ShaderNodeFresnel');fresnel.inputs['IOR'].default_value=1.45
mult=nt.nodes.new('ShaderNodeMath');mult.operation='MULTIPLY_ADD';mult.inputs[1].default_value=.92;mult.inputs[2].default_value=.025
nt.links.new(fresnel.outputs[0],mult.inputs[0]);mix.inputs[0].default_value=.065
nt.links.new(trans.outputs[0],mix.inputs[1]);nt.links.new(pr.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],nt.nodes.get('Material Output').inputs['Surface'])
for o in s.objects:
    if 'closed_4mm_glass' in o.name:o.data.materials.clear();o.data.materials.append(glazing)
for i,(x,y,h) in enumerate([(-.66,-.3,1.62),(.66,-.3,1.95),(0,.53,2.30)],1):
    # Warm downlight is physically inside each cap, with a readable front fill.
    pos=(-2.68+x,1.21+y,.562+.235+h-.14)
    light('warm.capsule.%02d'%i,pos,8,(1,.84,.63),.34,(pos[0],pos[1],pos[2]-1))

# Central profile lens. Real supported pivot, single dominant round silhouette.
core=root('about.profile.core',(0,1.74,.562))
cylinder('profile.foundation',(0,.15,.08),.76,.16,M['dark'],core)
cylinder('profile.orange_collar',(0,.15,.2),.54,.14,M['orange'],core)
for x in [-.37,.37]:
    box('profile.column',(x,.28,1.36),(.13,.20,2.21),M['navy'],core,.045)
    box('profile.column_spine',(x,.397,1.4),(.06,.042,2.18),M['metal'],core,.013)
    rod('profile.diagonal_brace',(x,.36,.28),(x,.27,2.43),.039,M['metal'],core)
    hinge=cylinder('profile.pivot',(x,.29,2.45),.16,.20,M['brass'],core);hinge.rotation_euler.y=math.pi/2
box('profile.crossbar',(0,.23,2.55),(.93,.17,.20),M['navy'],core,.05)
display=root('about.profile.rotating_lens',(0,0,0));display.parent=core;display.location=(0,-.055,2.56);display.rotation_euler.x=math.radians(69)
cylinder('profile.disc_back',(0,0,-.061),1.14,.18,M['navy'],display,128)
arc('profile.outer_band',(0,0,0),1.102,1.184,-.055,.06,0,360,M['metal'],display,.012)
arc('profile.index_ring',(0,0,0),1.028,1.087,.038,.078,0,360,M['orange'],display,.009)
cylinder('profile.face',(0,0,.059),1.024,.042,M['dark'],display,128)
for a in range(0,360,15):
    t=math.radians(a);o=box('profile.dial_tick',(1.057*math.cos(t),1.057*math.sin(t),.082),(.032,.008,.004),M['ivory'],display,.001);o.rotation_euler.z=t
torus('profile.face_halo',(0,0,.086),.945,.007,M['brass'],display)
text('profile.name','关于我',(0,.28,.087),.31,M['ivory'],display,(0,0,0))
text('profile.placeholder','个人简介待补充',(0,-.03,.087),.093,M['ivory'],display,(0,0,0))
text('profile.micro','PERSONAL ARCHIVE',(0,-.47,.087),.070,M['brass'],display,(0,0,0))
text('profile.index','01',(0,.71,.087),.10,M['orange'],display,(0,0,0))
for y in [-.18,-.24]:box('profile.rule',(0,y,.09),(.81,.007,.003),M['metal'],display,.001)
for x in [-.48,-.16,.16,.48]:
    cylinder('profile.status_indicator',(x,-.67,.09),.026,.009,M['orange' if x==-.48 else 'metal'],display,24)
for x in [-1.08,1.08]:
    o=box('profile.side_handle',(x,0,-.01),(.08,.45,.095),M['rubber'],display,.035)

# An offset cantilever light draws an open arc over the machinery; no walls.
lamp=root('about.nexus.arc_lamp',(-.15,3.12,.562))
cylinder('arc_lamp.foot',(0,0,.1),.41,.2,M['dark'],lamp)
rod('arc_lamp.post',(0,0,.19),(0,0,3.84),.055,M['metal'],lamp)
for z in [.46,1.7,3.0]:cylinder('arc_lamp.collar',(0,0,z),.078,.13,M['orange'],lamp)
path=[]
for i in range(67):
    a=math.radians(24+i*2.1);path.append((2.55*math.cos(a),-1.68+1.68*math.sin(a),3.87))
tube('arc_lamp.shade',path,.038,M['navy'],lamp)
tube('arc_lamp.diffuser',[(x,y,z-.035) for x,y,z in path],.012,M['light'],lamp)
rod('arc_lamp.front_anchor',(0,0,3.78),(0,-.001,3.86),.09,M['navy'],lamp)

# Contact equipment lives on the right open end of the C-worktop.
contact=root('about.contact.console',(0,0,0));contact.parent=desk
contact.location=(1.4723,-.2596,1.255);contact.rotation_euler.z=math.radians(-14)
cylinder('contact.swivel',(0,0,.04),.29,.08,M['dark'],contact)
cylinder('contact.stem',(0,.06,.14),.09,.19,M['metal'],contact)
panel=root('about.contact.folded_panel',(0,0,0));panel.parent=contact;panel.location=(0,0,.28);panel.rotation_euler.x=math.radians(42)
box('contact.body',(0,0,0),(.91,.68,.08),M['navy'],panel,.033)
box('contact.orange_back',(0,0,-.045),(.77,.59,.045),M['orange'],panel,.02)
box('contact.face',(0,0,.047),(.81,.56,.026),M['ivory'],panel,.011)
box('contact.screen',(0,.027,.064),(.72,.37,.014),M['dark'],panel,.006)
tube('contact.envelope',[(-.078,.116,.073),(-.078,.205,.073),(.078,.205,.073),(.078,.116,.073),(-.078,.116,.073)],.004,M['brass'],panel)
tube('contact.fold',[(-.072,.2,.074),(0,.146,.074),(.072,.2,.074)],.004,M['brass'],panel)
text('contact.pending','联系方式待补充',(0,.01,.074),.06,M['ivory'],panel,(0,0,0))
text('contact.tap','CONTACT',(0,-.204,.079),.047,M['navy'],panel,(0,0,0))
for x in [-.34,.34]:cylinder('contact.fastener',(x,-.20,.08),.012,.008,M['brass'],panel,24)
rod('contact.power_cable',(0,0,.13),(0,.20,.03),.017,M['rubber'],contact)

# Independent archive tokens fan out across the left side of the wood counter.
for i in range(3):
    card=root('about.archive.card.%02d'%i,(0,0,0));card.parent=desk
    angle=math.radians(150+i*22)
    card.location=(1.49*math.cos(angle),1.49*math.sin(angle),1.255)
    card.rotation_euler.z=angle-math.pi/2
    box('archive.token',(0,0,.024),(.48,.34,.048),M['navy'],card,.021)
    box('archive.token_face',(0,0,.051),(.41,.28,.008),M['ivory'],card,.003)
    box('archive.token_tab',(.16,-.03,.058),(.028,.17,.009),M['orange'],card,.003)
    text('archive.token_label','待补充',(-.035,0,.057),.046,M['dark'],card,(0,0,0))

# Low ergonomic stool in the circular opening: swivel seat, honest floor contact.
stool=root('about.nexus.stool',(-.25,-1.92,.562))
cylinder('stool.foot',(0,0,.065),.43,.13,M['dark'],stool)
cylinder('stool.column',(0,0,.31),.085,.44,M['metal'],stool)
torus('stool.foot_ring',(0,0,.28),.31,.026,M['metal'],stool)
for a in [0,120,240]:
    t=math.radians(a);rod('stool.ring_spoke',(0,0,.28),(.31*math.cos(t),.31*math.sin(t),.28),.018,M['navy'],stool)
seat=root('about.stool.seat',(0,0,0));seat.parent=stool;seat.location=(0,0,.595)
cylinder('stool.seat_shell',(0,0,0),.46,.13,M['navy'],seat)
cylinder('stool.leather',(0,0,.113),.43,.15,M['leather'],seat)
torus('stool.stitching',(0,0,.182),.387,.0035,M['ivory'],seat)

# Front-left travel archive case and folded documents add personal workshop scale.
case=root('about.archive.carry_case',(-2.67,-1.68,.562));case.rotation_euler.z=math.radians(16)
box('case.lower',(0,0,.16),(1.03,.64,.32),M['navy'],case,.10)
box('case.lid',(0,0,.365),(1.03,.64,.12),M['orange'],case,.052)
for x in [-.37,.37]:
    box('case.strap',(x,0,.438),(.053,.66,.022),M['rubber'],case,.009)
    box('case.latch',(x,-.334,.28),(.105,.033,.12),M['brass'],case,.014)
tube('case.handle',[(-.14,-.352,.13),(-.14,-.41,.13),(.14,-.41,.13),(.14,-.352,.13)],.019,M['rubber'],case)
box('case.identity',(0,0,.433),(.29,.2,.012),M['ivory'],case,.005)
text('case.placeholder','待补充',(0,0,.442),.054,M['navy'],case,(0,0,0))

# A compact in-scene return pedal is reserved for future integration.
back=root('about.return.dock',(2.0,-2.14,.562));back.rotation_euler.z=math.radians(-28)
box('return.base',(0,0,.09),(.72,.68,.18),M['navy'],back,.075)
face=root('about.return.button',(0,0,0));face.parent=back;face.location=(0,.01,.31);face.rotation_euler.x=math.radians(27)
box('return.face',(0,0,0),(.64,.43,.055),M['orange'],face,.025)
text('return.caption','返回房间',(0,-.025,.031),.086,M['ivory'],face,(0,0,0))
text('return.arrow','←',(0,.108,.031),.11,M['ivory'],face,(0,0,0))
rod('return.support',(0,.05,.14),(0,.05,.31),.07,M['metal'],back)

# Small planted counterweight balances the archive case, not a copied floor pot.
green=root('about.nexus.terrarium',(3.35,-1.56,.562))
cylinder('terrarium.base',(0,0,.08),.35,.16,M['dark'],green)
cylinder('terrarium.pot',(0,0,.24),.27,.25,M['orange'],green)
cylinder('terrarium.soil',(0,0,.371),.245,.012,M['soil'],green)
for i in range(9):
    a=i*2.399;end=Vector((.26*math.cos(a),.26*math.sin(a),.70+.10*math.sin(i)))
    rod('terrarium.stem',(0,0,.37),end,.008,M['leaf'],green)
    o=sphere('terrarium.leaf',end,.1,M['leaf'],green,(.52,1.95,.2));o.rotation_euler=(0,math.radians(-18),a-.8)

# Actual lighting and neutral off-scene studio ground for approval renders.
environment=root('review.environment');environment['interactive']=False
box('review.ground',(0,0,-.19),(200,200,.1),mat('background','B3B9B5',0,.8),environment,.0)
w=bpy.data.worlds.new('NEXUS daylight');w.use_nodes=True;s.world=w
n=w.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputWorld');bg=n.new('ShaderNodeBackground');sky=n.new('ShaderNodeTexSky')
sky.sky_type='MULTIPLE_SCATTERING';sky.sun_disc=False;sky.sun_elevation=math.radians(30);sky.sun_rotation=math.radians(105);bg.inputs['Strength'].default_value=.10
w.node_tree.links.new(sky.outputs['Color'],bg.inputs['Color']);w.node_tree.links.new(bg.outputs[0],out.inputs[0])
sun=light('day.sun',(-7,-5,9),2.0,(1,.88,.71),1,(0,0,0),'SUN');sun.data.angle=.16
light('day.key',(-5,-5,9),1050,(1,.85,.68),7,(0,0,1))
light('day.rim',(5,3,8),1200,(.77,.90,1),6,(0,1,1.4))
light('day.front',(3,-7,6),350,(.88,.94,1),6,(0,1,2))
light('warm.arc',(0,1.9,4.28),130,(1,.69,.36),3.6,(0,0,1))
light('warm.awards',(-2.68,1.21,3.35),50,(1,.76,.44),1.6,(-2.68,1.21,1.4))
light('warm.table',(0,-.4,1.41),12,(1,.61,.3),.4,kind='POINT')
light('warm.skills',(2.48,.6,2.72),40,(1,.8,.5),1.6,(2.48,1.22,1.3))

def camera(name,loc,target,scale):
    d=bpy.data.cameras.new(name);d.type='ORTHO';d.ortho_scale=scale
    o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler();return o
s.camera=camera('CAM.hero',(10,-16,12),(0,0,1.72),11.95)
camera('CAM.awards',(-8,-10,7),(-2.0,1.1,1.83),5.8)
camera('CAM.workstation',(7,-9,7),(1.1,.55,1.95),6.9)
s.render.engine='CYCLES';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.max_bounces=16;s.cycles.transmission_bounces=12;s.cycles.transparent_max_bounces=32
s.render.resolution_x=2200;s.render.resolution_y=1800;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=0
for font in bpy.data.fonts:
    if font.filepath:
        try:font.pack()
        except RuntimeError:pass
bpy.data.texts.new('FONT_LICENSE_OFL.txt').write((P/'assets/font-candidates/v4/douyin-upstream/DouyinSans/OFL.txt').read_text())
bpy.data.texts.new('ABOUT_NEXUS_README.txt').write('Original Blender About Nexus V2. Pending visual approval; no website integration. All personal biography, award, skill, contact information is pending, abstract display devices are not factual claims. Font DouyinSans Bold: SIL OFL 1.1. See embedded font license. All component roots preserve editable geometry and independent pivots.')
bpy.context.view_layer.update()
for o in s.objects:
    if o.get('interactive'):
        o['content_status']='pending_user_information';o['interaction_status']='reserved_not_yet_integrated'
source=P/'assets/blender/about-nexus-v2.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source))
manifest={'scene':s.name,'source':str(source),'websiteIntegrated':False,'approval':'pending','objects':len(s.objects),
          'interactiveAssets':[{'id':o['asset_id'],'parent':o.parent.name if o.parent else None,'localPosition':list(o.location)} for o in s.objects if o.get('interactive')],
          'design':'Freestanding circular workshop island, central profile lens, clustered award capsules, radial skills workbench.'}
(P/'assets/blender/about-nexus-v2-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
result={'source':str(source),'objects':len(s.objects),'status':'pending_visual_review'}
