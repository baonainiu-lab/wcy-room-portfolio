"""Option C: 光核策展人 / Lumen Curator. Deterministic, editable Blender design.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python build.py
All generated files stay beside this script; nothing is integrated into the website.
"""
import bpy, math, json
from pathlib import Path
from mathutils import Vector, Euler
HERE = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
parts = []

def rgb(code):
    c = [int(code[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)

def mat(name, color, rough=.32, metal=0, glow=0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); c=(*rgb(color),1)
    p.inputs['Base Color'].default_value=c; p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    p.inputs['Emission Color'].default_value=c; p.inputs['Emission Strength'].default_value=glow
    m.diffuse_color=c; return m
ivory=mat('C_IvoryCeramic','E7E2D5',.27,.08)
graphite=mat('C_DeepGraphite','292B2D',.32,.36)
softblack=mat('C_JointRubber','15191A',.62,.05)
orange=mat('C_ArchiveOrange','D66C2E',.35,.20)
amber=mat('C_AmberVisor','633012',.22,.50)
bronze=mat('C_ChampagneAlloy','B29463',.29,.78)
white=mat('C_WhiteSignal','FFF4DA',.24,.03,1.5)
coremat=mat('C_AmberLight','FBA13E',.24,.15,2.0)
blackglass=mat('C_RecessGlass','241D16',.23,.3)
materials=[ivory,graphite,softblack,orange,amber,bronze,white,coremat,blackglass]

def reg(o,name,parent=None):
    o.name=name
    if parent:
        matrix=o.matrix_world.copy(); o.parent=parent; o.matrix_world=matrix
    parts.append(o); return o

def pivot(name,loc=(0,0,0),parent=None):
    o=bpy.data.objects.new(name,None); scene.collection.objects.link(o);o.location=loc
    bpy.context.view_layer.update();return reg(o,name,parent)

def finish(o,name,m,parent=None,bevel=0):
    bpy.context.view_layer.objects.active=o;o.select_set(True)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        b=o.modifiers.new('Precision edge fillet','BEVEL');b.width=bevel;b.segments=4
        b.limit_method='ANGLE';b.angle_limit=.45
        bpy.ops.object.modifier_apply(modifier=b.name)
    for p in o.data.polygons:p.use_smooth=True
    n=o.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL');n.keep_sharp=True;n.weight=40
    bpy.ops.object.modifier_apply(modifier=n.name)
    o.data.materials.append(m);bpy.context.view_layer.update();reg(o,name,parent);o.select_set(False)
    return o

def box(name,loc,size,m,r=.02,parent=None,rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=size
    if rotation:o.rotation_euler=rotation
    return finish(o,name,m,parent,r)

def ball(name,loc,scale,m,parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,radius=1,location=loc)
    o=bpy.context.object;o.scale=scale;return finish(o,name,m,parent)

def cyl(name,loc,r,depth,m,parent=None,axis='Z',verts=40):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc)
    o=bpy.context.object
    if axis=='Y':o.rotation_euler[0]=math.pi/2
    elif axis=='X':o.rotation_euler[1]=math.pi/2
    return finish(o,name,m,parent,min(.009,r*.17))

def rod(name,a,b,r,m,parent=None):
    a,b=Vector(a),Vector(b);o=cyl(name,(a+b)/2,r,(b-a).length,m,parent)
    matrix=(b-a).to_track_quat('Z','Y').to_matrix().to_4x4();matrix.translation=(a+b)/2;o.matrix_world=matrix
    return o

def curve(name,points,r,m,parent=None):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3;c.use_fill_caps=True
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for p,xyz in zip(s.points,points):p.co=(*xyz,1)
    o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);bpy.context.view_layer.objects.active=o;o.select_set(True)
    bpy.ops.object.convert(target='MESH');o=bpy.context.object
    for f in o.data.polygons:f.use_smooth=True
    o.data.materials.append(m);bpy.context.view_layer.update();reg(o,name,parent);o.select_set(False);return o

def profile(name,outline,y,depth,m,parent=None,bevel=.012,rounding=.25):
    # Rounded 2-D silhouette extruded through depth: actual topology, no image decals.
    pts=[];n=len(outline)
    for i,p in enumerate(outline):
        prev=Vector(outline[(i-1)%n]);v=Vector(p);nxt=Vector(outline[(i+1)%n])
        a=v+(prev-v)*rounding;b=v+(nxt-v)*rounding
        for j in range(9):
            t=j/8;v2=(1-t)**2*a+2*(1-t)*t*v+t*t*b;pts.append((v2.x,v2.y))
    count=len(pts);vertices=[(x,yy,z) for yy in (y-depth/2,y+depth/2) for x,z in pts]
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,count+(i+1)%count,count+i) for i in range(count)]
    me=bpy.data.meshes.new(name+'Mesh');me.from_pydata(vertices,[],faces);me.update()
    o=bpy.data.objects.new(name,me);scene.collection.objects.link(o)
    return finish(o,name,m,parent,bevel)

def arc(name,center,rx,rz,y,start,end,r,m,parent=None):
    pts=[(center[0]+rx*math.cos(math.radians(a)),y,center[1]+rz*math.sin(math.radians(a))) for a in [start+(end-start)*i/120 for i in range(121)]]
    return curve(name,pts,r,m,parent)

root=pivot('LumenCurator_OptionC');root['design_name']='光核策展人 / Lumen Curator';root['candidate_only']=True
body=pivot('AvatarBody',(0,0,1.08),root)
head=pivot('AvatarHead',(0,0,1.89),body)
armL=pivot('AvatarArmL',(.326,0,1.445),body)
armR=pivot('AvatarArmR',(-.326,0,1.445),body)
# Sculptural rounded wedge head: broad crown, tapered lower contour, entirely custom profile.
outline=[(-.29,2.115),(.22,2.115),(.365,1.945),(.235,1.655),(-.18,1.635),(-.365,1.89)]
profile('HeadSculpturalGraphite',outline,.014,.375,graphite,head,.04,.29)
visor=[(-.274,2.037),(.20,2.037),(.29,1.928),(.185,1.739),(-.139,1.723),(-.287,1.895)]
profile('VisorChampagneGasket',visor,-.186,.045,bronze,head,.013,.28)
vc=[(x*.965,1.885+(z-1.885)*.91) for x,z in visor]
profile('AmberInsetVisor',vc,-.217,.020,amber,head,.009,.29)
# Fine white optics; distinct scaleable geometry for future blink interaction.
box('EyeL',(.105,-.236,1.91),(.084,.014,.021),white,.009,head,(0,.02,-.05))
box('EyeR',(-.103,-.236,1.91),(.084,.014,.021),white,.009,head,(0,-.02,.05))
arc('GentleSmile',(0,1.865),.042,.025,-.239,208,331,.004,white,head)
for i in range(3):box('VisorStatus'+str(i),(.193,-.231,1.830+i*.017),(.012,.006,.004),bronze,.001,head)
# Ceramic temple inserts and a rear removable panel give every view a finished construction.
for sign in (-1,1):
    cyl('TempleBearing'+str(sign),(sign*.315,.025,1.926),.070,.036,softblack,head,'X')
    cyl('TempleShell'+str(sign),(sign*.337,.025,1.926),.056,.020,ivory,head,'X')
    cyl('TempleHub'+str(sign),(sign*.350,.025,1.926),.023,.009,bronze,head,'X')
profile('RearHeadServicePlate',[(-.20,1.77),(.14,1.77),(.22,1.95),(.13,2.02),(-.20,2.02),(-.255,1.91)],.211,.026,softblack,head,.009,.25)
for i in range(5):box('RearHeadVent'+str(i),(-.095+i*.042,.229,1.901),(.012,.007,.117),graphite,.004,head)
box('RearHeadSignal',(0,.232,1.995),(.102,.008,.008),coremat,.003,head)
# Offset orbit plane, tilted in three dimensions. This ring is a physical tube.
rot=Euler((math.radians(10),math.radians(21),math.radians(12))).to_matrix()
def halo_pts(start,end,r=.444):
    pts=[]
    for i in range(181):
        a=math.radians(start+(end-start)*i/180);v=rot@Vector((r*math.cos(a),0,r*math.sin(a)))
        pts.append(tuple(v+Vector((.056,.175,1.918))))
    return pts
curve('OffsetOrbitStructuralRing',halo_pts(0,360),.012,bronze,head)
curve('OrbitIvoryLongArc',halo_pts(30,175,.446),.016,ivory,head)
curve('OrbitAmberSignalArc',halo_pts(223,290,.446),.014,coremat,head)
for a in (17,191):
    p=Vector(halo_pts(a,a)[0]);ball('OrbitAnchor'+str(a),p,(.028,.023,.028),graphite,head)
rod('OrbitRearSupportA',(-.075,.219,1.825),halo_pts(225,225)[0],.014,graphite,head)
rod('OrbitRearSupportB',(.075,.219,1.825),halo_pts(312,312)[0],.014,graphite,head)
# C-shaped collar; the opening faces slightly to the left of the visitor.
cyl('NeckActuator',(0,.015,1.610),.069,.175,graphite,body)
pts=[]
for i in range(121):
    a=math.radians(-47+278*i/120);pts.append((.151*math.cos(a),.122*math.sin(a),1.560+.022*math.cos(a)))
curve('OpenCCeramicCollar',pts,.033,ivory,body)
curve('OpenCCollarGoldLip',[(x,y,z+.022) for x,y,z in pts],.006,bronze,body)
# Asymmetric ivory wrap vest: separate overlapping panels, curved chamfered outlines.
ball('ChestInterior',(0,.012,1.375),(.292,.166,.243),graphite,body)
profile('WrapVestLongPanel',[(-.294,1.523),(-.038,1.546),(.115,1.391),(.04,1.174),(-.199,1.214),(-.302,1.376)],-.064,.239,ivory,body,.027,.20)
profile('WrapVestShortPanel',[(.04,1.535),(.266,1.507),(.302,1.318),(.123,1.237),(.078,1.370),(-.032,1.486)],-.026,.249,ivory,body,.027,.20)
# Satin seam and small curatorial badge are geometry, not a texture.
curve('WrapDiagonalSeam',[(-.034,-.192,1.501),(.066,-.195,1.393),(.014,-.195,1.227)],.0055,bronze,body)
cyl('VestEmblemRecess',(-.166,-.190,1.399),.044,.012,graphite,body,'Y')
arc('VestCuratorMark',(-.166,1.399),.026,.026,-.202,40,320,.005,bronze,body)
ball('VestCuratorMarkDot',(-.143,-.205,1.414),(.008,.006,.008),coremat,body)
box('VestMicroTag',(.190,-.158,1.432),(.047,.013,.025),orange,.006,body)
# Open abdomen reveals a suspended luminous core and twin fine mechanical rails.
rod('CentralSpine',(0,.05,.923),(0,.05,1.266),.041,softblack,body)
for sign in (-1,1):
    rod('AbdomenExposedRail'+str(sign),(sign*.174,.021,.944),(sign*.158,.031,1.228),.019,bronze,body)
    cyl('AbdomenRailJoint'+str(sign),(sign*.162,-.006,1.194),.028,.043,graphite,body,'Y')
cyl('LightCoreHousing',(0,-.021,1.072),.123,.119,graphite,body,'Y')
cyl('LightCoreInset',(0,-.088,1.072),.100,.023,blackglass,body,'Y')
arc('LightCoreGuard',(0,1.072),.105,.105,-.103,0,360,.012,bronze,body)
ball('ExposedWarmCore',(0,-.121,1.072),(.075,.039,.075),coremat,body)
arc('CoreFineOpticLine',(0,1.072),.042,.042,-.157,22,326,.004,white,body)
for a in (45,135,225,315):
    aa=math.radians(a);cyl('CoreQuarterBolt'+str(a),(.103*math.cos(aa),-.119,1.072+.103*math.sin(aa)),.008,.013,graphite,body,'Y',16)
# Rear architecture: a high ivory yoke, exposed dark spine and champagne service rail.
profile('RearVestYoke',[(-.259,1.470),(-.115,1.543),(.176,1.506),(.267,1.390),(.225,1.270),(-.221,1.230),(-.287,1.356)],.150,.080,ivory,body,.024,.23)
box('RearServiceSpine',(0,.207,1.352),(.091,.047,.215),graphite,.025,body)
for i in range(4):box('RearSpineContacts'+str(i),(0,.234,1.28+i*.048),(.055,.008,.012),bronze,.003,body)
curve('RearPowerLoop',[(-.158,.090,1.208),(-.174,.133,1.092),(-.124,.142,.973)],.010,orange,body)
# Floating belt and orange three-slot archive pack.
box('HipGraphiteBridge',(0,.005,.884),(.353,.255,.161),graphite,.062,body)
profile('HipIvoryApron',[(-.165,.934),(.160,.934),(.167,.856),(.06,.795),(-.107,.809),(-.171,.864)],-.109,.075,ivory,body,.025,.25)
box('ArchivePackSupport',(-.274,-.016,.919),(.164,.202,.259),softblack,.031,body)
box('OrangeTripleArchivePack',(-.280,-.107,.935),(.189,.086,.241),orange,.034,body,(0,-.04,-.06))
for i in range(3):
    x=-.338+i*.059
    box('ArchiveSlot'+str(i),(x,-.154,.950),(.038,.010,.150),graphite,.008,body)
    box('ArchiveCartridge'+str(i),(x,-.166,.962),(.026,.022,.124),bronze if i==1 else ivory,.007,body)
    box('ArchiveCartridgeMark'+str(i),(x,-.180,.990),(.018,.004,.010),orange,.003,body)
box('ArchivePackLatch',(-.280,-.159,.846),(.062,.013,.021),graphite,.006,body)
# Segmented, expressive arms with visible joints and shaped ivory forearm sleeves.
for s,parent,side in ((1,armL,'L'),(-1,armR,'R')):
    shoulder=(s*.333,0,1.431);elbow=(s*.409,-.025,1.183);wrist=(s*.434,-.073,.996)
    cyl('ShoulderAxle'+side,shoulder,.078,.103,graphite,parent,'X')
    cyl('ShoulderCeramicDisc'+side,(s*.382,0,1.431),.068,.031,ivory,parent,'X')
    cyl('ShoulderAlloyHub'+side,(s*.402,0,1.431),.030,.011,bronze,parent,'X')
    rod('UpperArmDarkCore'+side,shoulder,elbow,.041,softblack,parent)
    rod('UpperArmOuterShell'+side,(s*.365,-.006,1.357),(s*.399,-.019,1.244),.055,ivory,parent)
    cyl('ElbowAxle'+side,elbow,.058,.085,graphite,parent,'X')
    cyl('ElbowAlloyRing'+side,(s*.447,-.025,1.183),.039,.010,bronze,parent,'X')
    rod('ForearmPistonA'+side,(s*.389,-.044,1.149),(s*.419,-.079,1.008),.013,bronze,parent)
    rod('ForearmPistonB'+side,(s*.432,-.002,1.150),(s*.453,-.035,1.010),.014,graphite,parent)
    box('ForearmCeramicCuff'+side,(s*.433,-.053,1.034),(.101,.117,.106),ivory,.029,parent,(0,s*.09,0))
    cyl('WristJoint'+side,wrist,.036,.067,graphite,parent)
    box('HandPalm'+side,(s*.441,-.082,.922),(.117,.091,.126),ivory,.040,parent,(0,s*.08,0))
    for finger in range(3):
        x=s*.441+(finger-1)*.031
        box('HandFinger'+side+str(finger),(x,-.113,.879),(.029,.049,.065),ivory,.014,parent)
        box('FingerSeam'+side+str(finger),(x,-.140,.892),(.019,.006,.006),graphite,.002,parent)
    ball('Thumb'+side,(s*.385,-.095,.935),(.031,.039,.048),ivory,parent)
# Lean articulated legs and broad premium sneaker-like ceramic boots.
for s,side in ((-1,'R'),(1,'L')):
    x=s*.136
    ball('HipBall'+side,(x,.012,.784),(.074,.068,.072),graphite,body)
    rod('ThighInner'+side,(x,.009,.775),(x,-.002,.531),.044,softblack,body)
    box('ThighCeramic'+side,(x,-.007,.659),(.129,.132,.197),ivory,.037,body)
    box('ThighSideInset'+side,(x+s*.065,-.002,.661),(.012,.065,.099),bronze,.005,body)
    cyl('KneeJoint'+side,(x,-.001,.511),.061,.130,graphite,body,'X')
    cyl('KneeFrontPad'+side,(x,-.066,.511),.041,.019,ivory,body,'Y')
    rod('ShinPiston'+side,(x,.005,.478),(x,-.015,.298),.031,bronze,body)
    box('ShinShell'+side,(x,-.036,.377),(.112,.114,.158),graphite,.031,body)
    box('ShinWhiteStripe'+side,(x,-.098,.380),(.040,.019,.114),ivory,.011,body)
    cyl('AnkleJoint'+side,(x,-.014,.246),.047,.091,graphite,body)
    box('WideBootSole'+side,(x,-.081,.060),(.245,.375,.112),graphite,.043,body)
    box('WideIvoryBoot'+side,(x,-.086,.164),(.239,.365,.197),ivory,.073,body)
    box('BootCollarLip'+side,(x,.006,.249),(.165,.151,.045),ivory,.020,body)
    curve('BootToeSeam'+side,[(x-.078,-.249,.178),(x,-.271,.170),(x+.078,-.249,.178)],.0045,bronze,body)
    box('BootHeelTab'+side,(x,.099,.193),(.066,.039,.077),orange,.012,body)
    for i in range(3):box('SoleSideSlot'+side+str(i),(x+s*.121,-.118+i*.07,.065),(.005,.038,.010),bronze,.002,body)

# Slightly taller sculpted head establishes approximately four head-heights, excluding the orbit.
head.scale.z=1.20
head.location.z += .018
bpy.context.view_layer.update()
# Pose is neutral and joint-separated so the same geometry can later be animated.
meshparts=[o for o in parts if o.type=='MESH']
triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshparts)
points=[o.matrix_world@v.co for o in meshparts for v in o.data.vertices]
mins=[min(p[i] for p in points) for i in range(3)];maxs=[max(p[i] for p in points) for i in range(3)]
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(HERE/'option-c.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False)
# Warm-gray photographic cyclorama, separate from the exported character.
ground=mat('StudioWarmGray','A9A49C',.79)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.003));bpy.context.object.name='STUDIO_ground';bpy.context.object.data.materials.append(ground)
world=bpy.data.worlds.new('WarmGrayStudio');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.62,.60,.56,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.28;scene.world=world

def light(name,loc,power,size,color,target=(0,0,1.2)):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
light('STUDIO_large_key',(-3.0,-4.5,5),520,4.0,(1,.86,.70))
light('STUDIO_soft_fill',(3,-2,3),270,3.0,(.78,.87,1))
light('STUDIO_rim',(1.5,3.0,4.5),670,2.8,(1,.86,.63))
light('STUDIO_front_reflection',(-.2,-4.5,2.2),70,1.8,(1,.97,.92))
d=bpy.data.cameras.new('OptionC_StudioCamera');camera=bpy.data.objects.new('OptionC_StudioCamera',d);scene.collection.objects.link(camera);scene.camera=camera
d.type='ORTHO';d.ortho_scale=2.90;d.lens=75
scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.render.image_settings.color_mode='RGBA'
scene.render.image_settings.color_depth='8'
for label,loc in [('front',(3.05,-6.2,3.03)),('back',(-3.1,6.2,2.85))]:
    camera.location=loc;camera.rotation_euler=(Vector((.015,0,1.205))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(HERE/(label+'.png'))
    if label=='front':bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'option-c.blend'))
    bpy.ops.render.render(write_still=True)
manifest={'name':'光核策展人 / Lumen Curator','status':'独立候选，待用户验收，未接入网站','geometry':'真实 Blender 几何；PNG 是同一模型的摄影棚渲染','generator':'build.py','blend':'option-c.blend','glb':'option-c.glb','renders':['front.png','back.png'],'triangles':triangles,'mesh_count':len(meshparts),'materials':len(materials),'glb_bytes':(HERE/'option-c.glb').stat().st_size,'blender_bounds':{'min':mins,'max':maxs},'head_body_ratio':'约 4 头身；头后偏轴环为附属结构，不计入头身比','features':['定制圆角三角头与琥珀嵌入面罩','细白独立双眼与温和弧形微笑','物理偏轴轨道环','非对称象牙白包裹背心与开放 C 形领','开放腹部暖光核心','分段手指、肘关节与双杆前臂','橙色三槽档案腰包','宽象牙白靴与后跟橙色提片'],'animation_preparation':'头部/身体/双臂独立父级，双眼独立 mesh；本候选未绑定蒙皮、未加入动画'}
(HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('OPTION_C_COMPLETE='+str(HERE))
