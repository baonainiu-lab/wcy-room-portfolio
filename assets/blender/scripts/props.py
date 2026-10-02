"""Orbital creative cabin V2: individually addressable precision props.
Executed from Blender by the main room builder. Coordinates are metres.
No scene reset, save, lighting, camera, or rendering side effects.
"""
import bpy
import math
import random
from mathutils import Vector, Matrix
from common import M

COL = None
ROOTS = []
PREFIX = 'P_'

def _link(obj):
    for c in tuple(obj.users_collection):
        c.objects.unlink(obj)
    COL.objects.link(obj)
    return obj

def mat(name, color, metallic=0.0, roughness=.45):
    m = bpy.data.materials.get('P_' + name) or bpy.data.materials.new('P_' + name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    return m

def material(obj, material):
    if isinstance(material, str):
        material = M[material]
    obj.data.materials.append(material)
    return obj

def parent(obj, par):
    if par is not None:
        obj.parent = par
        obj.matrix_parent_inverse = Matrix.Identity(4)
    return obj

def group(name, loc=(0,0,0), par=None, asset=None):
    obj = bpy.data.objects.new(PREFIX + name, None)
    COL.objects.link(obj)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .07
    obj.location = loc
    parent(obj, par)
    if asset:
        obj['asset_id'] = asset
        obj['interactive'] = True
    return obj

def root(name, loc, asset):
    ob=group(name,loc,asset=asset)
    ROOTS.append(ob)
    return ob

def mesh(name, verts, faces, material_name, par=None, smooth=True):
    d=bpy.data.meshes.new(PREFIX+name+'Mesh')
    d.from_pydata(verts, [], faces)
    d.update()
    o=bpy.data.objects.new(PREFIX+name,d)
    COL.objects.link(o)
    parent(o,par)
    material(o,material_name)
    if smooth:
        for p in d.polygons: p.use_smooth=True
    return o

def beveled(o, amount=.01, segments=3):
    b=o.modifiers.new('Precision edge radii','BEVEL')
    b.width=amount
    b.segments=segments
    b.limit_method='ANGLE'
    n=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
    n.keep_sharp=True
    return o

def box(name, loc, size, material_name, par, radius=.01):
    x,y,z=[v*.5 for v in size]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    ob=mesh(name,vs,fs,material_name,par)
    ob.location=loc
    if radius: beveled(ob,radius,4)
    return ob

def sphere(name, loc, scale, material_name, par, seg=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg,ring_count=rings,radius=1,location=loc)
    ob=_link(bpy.context.object)
    ob.name=PREFIX+name
    for v in ob.data.vertices:
        v.co.x*=scale[0]; v.co.y*=scale[1]; v.co.z*=scale[2]
    material(ob,material_name)
    parent(ob,par)
    for p in ob.data.polygons:p.use_smooth=True
    return ob

def cylinder(name, a, b, radius, material_name, par, vertices=48):
    a,b=Vector(a),Vector(b)
    d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=d.length,location=(a+b)*.5)
    ob=_link(bpy.context.object); ob.name=PREFIX+name
    ob.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    parent(ob,par); material(ob,material_name)
    for p in ob.data.polygons:p.use_smooth=True
    beveled(ob,min(radius*.15,.009),3)
    return ob

def torus(name, loc, major, minor, material_name, par, rot=(0,0,0), scale=(1,1,1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=12,location=loc,rotation=rot)
    ob=_link(bpy.context.object); ob.name=PREFIX+name
    for v in ob.data.vertices:
        v.co.x*=scale[0];v.co.y*=scale[1];v.co.z*=scale[2]
    parent(ob,par);material(ob,material_name)
    for p in ob.data.polygons:p.use_smooth=True
    return ob

def tube(name, pts, radius, material_name, par, res=12):
    d=bpy.data.curves.new(PREFIX+name+'Curve','CURVE'); d.dimensions='3D'
    d.resolution_u=16;d.bevel_depth=radius;d.bevel_resolution=3;d.resolution_u=res
    s=d.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
    for bp,co in zip(s.bezier_points,pts):
        bp.co=co; bp.handle_left_type='AUTO';bp.handle_right_type='AUTO'
    o=bpy.data.objects.new(PREFIX+name,d);COL.objects.link(o)
    parent(o,par);material(o,material_name)
    return o

def lathe(name, profile, material_name, par, loc=(0,0,0), sides=64):
    vs=[];fs=[]
    for r,z in profile:
        for i in range(sides):
            a=2*math.pi*i/sides;vs.append((r*math.cos(a),r*math.sin(a),z))
    for j in range(len(profile)-1):
        for i in range(sides):
            n=(i+1)%sides;fs.append((j*sides+i,j*sides+n,(j+1)*sides+n,(j+1)*sides+i))
    ob=mesh(name,vs,fs,material_name,par);ob.location=loc
    return ob

def disk_y(name, center, radius, depth, material_name, par):
    x,y,z=center
    return cylinder(name,(x,y-depth*.5,z),(x,y+depth*.5,z),radius,material_name,par)

def precision_screw(name, center, radius, par, axis='Y'):
    """A dark machined countersink and bright inset slotted screw head."""
    x,y,z=center
    if axis=='Y':
        disk_y(name+'_Socket',(x,y,z),radius,.002,'graphite',par)
        disk_y(name+'_Head',(x,y-.0015,z),radius*.69,.002,'titanium',par)
        box(name+'_Slot',(x,y-.003,z),(radius*.88,.001,radius*.13),'black',par,.0003)
    else:
        cylinder(name+'_Socket',(x,y,z-.002),(x,y,z),radius,'graphite',par,24)
        cylinder(name+'_Head',(x,y,z),(x,y,z+.001),radius*.69,'titanium',par,24)
        box(name+'_Slot',(x,y,z+.0018),(radius*.88,radius*.13,.001),'black',par,.0003)

def knurled_ring_y(name, center, radius, width, par, count=48):
    x,y,z=center
    for i in range(count):
        a=i*math.tau/count
        cx=x+radius*math.cos(a);cz=z+radius*math.sin(a)
        cylinder(name+'_%02d'%i,(cx,y-width*.5,cz),(cx,y+width*.5,cz),.0016,'titanium',par,8)

def mark_asset(ob, name, interaction='inspect'):
    ob['asset_id']=name;ob['interaction']=interaction;ob['interactive']=True
    return ob

def robot():
    r=root('ROBOT_Root',(-3.05,-2,.18),'robot_companion')
    r['interaction']='wake_and_greet'
    # Upper and lower ceramic surfaces around a continuous dark optical visor.
    sphere('Robot_LowerBody',(0,0,.505),(.302,.245,.173),'ceramic',r)
    sphere('Robot_UpperDome',(0,0,.569),(.301,.245,.145),'ceramic',r)
    vs=[];fs=[];n=96
    for z,rx,ry in [(.535,.297,.242),(.545,.306,.249),(.597,.300,.245),(.613,.290,.237)]:
        for i in range(n):
            a=i*math.tau/n;vs.append((rx*math.cos(a),ry*math.sin(a),z))
    for j in range(3):
        for i in range(n):fs.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    mesh('Robot_ContinuousOpticalVisor',vs,fs,'black',r)
    torus('Robot_CrownSeam',(0,0,.687),.130,.003,'graphite',r,scale=(1,.82,1))
    sphere('Robot_CrownCap',(0,0,.69),(.127,.104,.017),'ceramic',r)
    torus('Robot_LowerShellSeal',(0,0,.426),.251,.004,'titanium',r,scale=(1,.81,1))
    # Tiny panel fasteners and a recessed service hatch distinguish a product
    # shell from a featureless sphere in the close inspection view.
    service=group('Robot_ServiceHatch',(0,.136,.434),r,asset='robot_service_hatch')
    box('Robot_ServicePanel',(0,0,0),(.123,.017,.058),'graphite',service,.014)
    for x in [-.045,.045]:
        precision_screw('Robot_ServiceScrew_'+str(x),(x,-.010,0),.006,service)
    for i,x in enumerate([-.225,-.135,-.078,.078,.135,.225]):
        y=-.249*math.sqrt(1-(x/.306)**2)-.003
        led=box('Robot_AmberPixel_%02d'%i,(x,y,.573),(.018 if abs(x)<.2 else .036,.008,.008),'amber_light',r,.003)
        led.rotation_euler[2]=-math.asin(x/.31)
    sphere('Robot_Underbelly',(0,.005,.359),(.178,.153,.153),'graphite',r)
    sphere('Robot_CentralGimbal',(0,-.08,.308),(.105,.077,.071),'titanium',r)
    for i,ang in enumerate([-37,-143,90]):
        a=math.radians(ang);vx,vy=math.cos(a),math.sin(a)
        leg=group('Robot_Leg_%02d_Pivot'%i,(.215*vx,.185*vy,.413),r,asset='robot_leg_%02d'%i)
        shoulder=(0,0,0);elbow=(.105*vx,.09*vy,-.078);knee=(.173*vx,.147*vy,-.105);ankle=(.255*vx,.208*vy,-.345)
        sphere('Robot_Shoulder_%d'%i,shoulder,(.073,.069,.07),'graphite',leg)
        cylinder('Robot_UpperArm_%d'%i,shoulder,elbow,.042,'titanium',leg)
        sphere('Robot_Elbow_%d'%i,elbow,(.053,.05,.05),'graphite',leg)
        cylinder('Robot_Link_%d'%i,elbow,knee,.037,'graphite',leg)
        sphere('Robot_Knee_%d'%i,knee,(.068,.061,.068),'ceramic',leg)
        outer=Vector(knee)+Vector((.016*vx,.016*vy,.005))
        disk_center=tuple(outer+Vector((0,-.040,0)))
        disk_y('Robot_KneeBearing_%d'%i,disk_center,.038,.022,'graphite',leg)
        disk_y('Robot_KneeStatus_%d'%i,(disk_center[0],disk_center[1]-.014,disk_center[2]),.015,.005,'amber_light',leg)
        ptop=Vector(knee);pbot=Vector(ankle)
        cylinder('Robot_ShinPiston_%d'%i,ptop,pbot,.037,'titanium',leg)
        mid=ptop.lerp(pbot,.34)
        sh=sphere('Robot_CeramicShinGuard_%d'%i,mid,(.065,.053,.113),'ceramic',leg)
        sh.rotation_euler=(pbot-ptop).to_track_quat('Z','Y').to_euler()
        cylinder('Robot_LowerDamper_%d'%i,ptop.lerp(pbot,.55),pbot,.035,'graphite',leg)
        sphere('Robot_Ankle_%d'%i,ankle,(.037,.038,.037),'graphite',leg)
        foot=Vector(ankle)+Vector((.012*vx,.012*vy,-.040))
        pad=box('Robot_FootPad_%d'%i,foot,(.080,.106,.035),'graphite',leg,.015)
        pad.rotation_euler[2]=a-math.pi/2
        for groove in range(3):
            tread=box('Robot_FootTread_%d_%d'%(i,groove),foot+Vector((0,(groove-1)*.021,-.017)),(.059,.007,.005),'black',leg,.002)
            tread.rotation_euler[2]=a-math.pi/2
        # Small exposed silver pin head at each ankle.
        disk_y('Robot_AnklePin_%d'%i,(ankle[0],ankle[1]-.035,ankle[2]),.015,.009,'titanium',leg)
    return r

def terminal():
    r=root('TERMINAL_Root',(-1.45,1.48,1.64),'folding_drawing_terminal')
    r.rotation_euler[2]=math.radians(-5)
    base=box('Terminal_Foot',(0,.035,.025),(.54,.29,.045),'titanium',r,.06)
    box('Terminal_RubberFoot',(0,.035,.007),(.46,.235,.012),'graphite',r,.04)
    # The pedestal is a softly swept, tapering titanium neck.
    lathe('Terminal_Pedestal',[(.095,.035),(.096,.045),(.065,.063),(.045,.14),(.049,.19),(.068,.205)],'titanium',r,loc=(0,.07,0))
    assembly=group('Terminal_TiltPivot',(0,0,.175),r,asset='terminal_tilt')
    assembly.rotation_euler[0]=math.radians(-13)
    cylinder('Terminal_Hinge',(0,0,.015),(0,0,.59),.027,'titanium',assembly)
    for j,z in enumerate([.075,.19,.31,.43,.55]):
        cylinder('Terminal_HingeBand_%d'%j,(0,0,z-.014),(0,0,z+.014),.0285,'graphite',assembly)
    for side in [-1,1]:
        tag='L' if side<0 else 'R'
        p=group('Terminal_'+tag+'_FoldPivot',(0,0,0),assembly,asset='terminal_panel_'+tag)
        p.rotation_euler[2]=math.radians(-side*7)
        p['hinge_axis']='Z';p['interaction']='fold'
        cx=side*.215
        box('Terminal_'+tag+'_AluminiumFrame',(cx,0,.312),(.404,.036,.592),'titanium',p,.025)
        box('Terminal_'+tag+'_ScreenBezel',(cx,-.022,.312),(.377,.016,.568),'black',p,.018)
        box('Terminal_'+tag+'_Screen',(cx,-.032,.312),(.345,.007,.533),'P_screen',p,.010)
        # Original orbital line art: curves are editable geometry, not borrowed imagery.
        for orbit in range(12):
            pts=[]
            for k in range(55):
                a=math.tau*k/54
                xx=.127*math.cos(a);zz=.160*math.sin(a)
                rotation=math.radians(orbit*13+side*10)
                xx2=xx*math.cos(rotation)-zz*math.sin(rotation)
                zz2=xx*math.sin(rotation)+zz*math.cos(rotation)
                pts.append((cx+xx2*.83,-.037-.0003*orbit,.321+zz2))
            tube('Terminal_'+tag+'_Orbit_%d'%orbit,pts,.00048,'P_screenline',p,4)
        for i in range(4):
            x=cx+(.045 if i%2 else -.070);z=.18+i*.078
            disk_y('Terminal_'+tag+'_Star_%d'%i,(x,-.039,z),.003,.002,'warm_light',p)
        sphere('Terminal_'+tag+'_AmberNucleus',(cx,-.044,.320),(.019,.007,.019),'amber_light',p,20,12)
        disk_y('Terminal_'+tag+'_CameraLens',(cx,-.033,.579),.004,.002,'P_lens',p)
        for j in range(3):
            box('Terminal_'+tag+'_InterfaceLine_%d'%j,(cx-.117,-.037,.081+j*.010),(.035+j*.01,.001,.002),'P_screenline',p,.0007)
    # Stylus sits on its own contact points and has an independently addressable root.
    pen=group('Terminal_Stylus_Root',(.32,-.27,.025),r,asset='drawing_stylus')
    a=(-.21,0,0);b=(.21,0,0)
    cylinder('Stylus_Barrel',(-.17,0,0),(.19,0,0),.013,'graphite',pen)
    cylinder('Stylus_Ferrule',(-.195,0,0),(-.165,0,0),.012,'titanium',pen)
    sphere('Stylus_Nib',(-.202,0,0),(.015,.005,.005),'titanium',pen)
    cylinder('Stylus_AmberEnd',(.18,0,0),(.185,0,0),.0138,'amber_light',pen)
    sphere('Stylus_Endcap',(.195,0,0),(.01,.013,.013),'graphite',pen)
    box('Stylus_SideButton',(.068,-.012,.002),(.044,.005,.006),'titanium',pen,.002)
    pen.rotation_euler[2]=math.radians(18)
    return r

def archives():
    r=root('ARCHIVE_Root',(4,2.9,2.0),'c_archive_dock')
    r['interaction']='select_cartridge'
    # A continuous C-shaped ribbon, thick extruded titanium with softened margins.
    pts=[(.39,.69)]
    for k in range(33):
        a=math.pi/2+k*math.pi/32
        pts.append((-.055+.31*math.cos(a),.38+.31*math.sin(a)))
    pts.append((.39,.07))
    vs=[];fs=[]
    for i,(x,z) in enumerate(pts):
        prev=Vector(pts[max(i-1,0)]);nxt=Vector(pts[min(i+1,len(pts)-1)])
        d=(nxt-prev).normalized();nn=Vector((-d.y,d.x))*.034
        for yy,sgn in [(-.19,1),(.19,1),(.19,-1),(-.19,-1)]:
            vs.append((x+nn.x*sgn,yy,z+nn.y*sgn))
    for i in range(len(pts)-1):
        for k in range(4):fs.append((i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4,(i+1)*4+k))
    fs.extend([(3,2,1,0),tuple(range((len(pts)-1)*4,len(pts)*4))])
    ob=mesh('Archive_C_Frame',vs,fs,'titanium',r);beveled(ob,.018,4)
    box('Archive_DockInsert',(.035,0,.099),(.64,.28,.015),'graphite',r,.045)
    box('Archive_TopLight',(.15,-.07,.651),(.30,.025,.005),'warm_light',r,.002)
    for i,x in enumerate([-.18,.022,.224]):
        z=.106+(0 if i<2 else .075)
        p=group('Archive_Cartridge_%02d_Root'%i,(x,0,z),r,asset='archive_cartridge_%02d'%i)
        p['interaction']='slide_out';p['slide_axis']='Y';p['slide_distance']=-.42
        body='ceramic' if i<2 else 'graphite'
        box('Archive_Cartridge_%d_Shell'%i,(0,0,.215),(.174,.215,.414),body,p,.042)
        box('Archive_Cartridge_%d_FrontSlot'%i,(0,-.109,.205),(.050,.009,.284),'black',p,.024)
        box('Archive_Cartridge_%d_Status'%i,(.025,-.117,.291),(.005,.006,.051),'amber_light',p,.002)
        # Rounded access plates, lateral contacts and three shallow vents read
        # clearly once the cartridge slides out independently in the website.
        box('Archive_Cartridge_%d_RearPlate'%i,(0,.111,.209),(.130,.008,.344),'titanium',p,.020)
        for q in range(3):
            box('Archive_Cartridge_%d_Contact_%d'%(i,q),(.089,.032+(q-1)*.031,.316),(.005,.015,.046),'P_gold',p,.002)
            box('Archive_Cartridge_%d_Vent_%d'%(i,q),(-.089,.003,.081+q*.019),(.005,.078,.004),'black',p,.001)
        for j,zr in enumerate([.048,.373]):
            disk_y('Archive_Cartridge_%d_Fastener_%d'%(i,j),(-.047,-.109,zr),.005,.003,'titanium',p)
        # Squared fabric pull-loop, modelled as four separate ribbon segments.
        looppts=[(-.031,.012,.412),(-.031,.012,.479),(0,.012,.490),(.031,.012,.479),(.031,.012,.412)]
        tube('Archive_Cartridge_%d_PullLoop'%i,looppts,.009,'P_gold',p)
        for xx in [-.031,.031]:
            box('Archive_Cartridge_%d_LoopStrap_%s'%(i,str(xx)),(xx,.012,.446),(.013,.033,.066),'P_gold',p,.004)
        # Individual dock rails are exposed below a partially raised cartridge.
        cylinder('Archive_DockRail_%d'%i,(x,.040,.112),(x,.040,z+.16),.012,'titanium',r)
    return r

def mechanical_flower():
    r=root('FLOWER_Root',(4,2.9,3.25),'kinetic_three_petal_flower')
    r['interaction']='unfold_petals'
    base=cylinder('Flower_Base',(0,0,.015),(0,0,.098),.245,'graphite',r)
    torus('Flower_BaseSilverRim',(0,0,.096),.232,.005,'titanium',r)
    cylinder('Flower_Stem',(0,.012,.099),(0,.012,.25),.048,'graphite',r)
    sphere('Flower_Core',(0,0,.30),(.128,.090,.128),'graphite',r)
    disk_y('Flower_CoreIris',(0,-.09,.30),.101,.026,'titanium',r)
    sphere('Flower_CoreLens',(0,-.112,.30),(.074,.035,.074),'titanium',r)
    torus('Flower_IrisOutline',(0,-.125,.30),.075,.005,'graphite',r,rot=(math.pi/2,0,0))
    torus('Flower_CoreBezel',(0,-.095,.30),.108,.005,'titanium',r,rot=(math.pi/2,0,0))
    for j in range(3):
        a=math.radians(30+120*j)
        precision_screw('Flower_CoreBolt_%d'%j,(.093*math.cos(a),-.113,.30+.093*math.sin(a)),.009,r)
    for i,deg in enumerate([126,38,202]):
        a=math.radians(deg);direc=Vector((math.cos(a),0,math.sin(a)))
        origin=direc*.077+Vector((0,-.012,.30))
        p=group('Flower_Petal_%d_Hinge'%i,origin,r,asset='flower_petal_%d'%i)
        p['interaction']='hinge_open';p['hinge_axis']='Y'
        # Real hinge cheeks and pivot pins, visible between petal and core.
        disk_y('Flower_Petal_%d_Pin'%i,(0,-.039,0),.024,.066,'graphite',p)
        disk_y('Flower_Petal_%d_PinCap'%i,(0,-.076,0),.014,.010,'titanium',p)
        vs=[];fs=[];rows=25;cols=11
        perp=Vector((-direc.z,0,direc.x))
        for j in range(rows):
            t=j/(rows-1);wid=.135*(math.sin(math.pi*t)**.65)+.009*(1-t)
            for k in range(cols):
                s=-1+2*k/(cols-1)
                v=direc*(.365*t)+perp*(wid*s)
                # Concave spoon face, arched sides and a finely upturned tip.
                v.y=-.032-.055*math.sin(math.pi*t)+.055*s*s*math.sin(math.pi*t)+.025*t*t
                vs.append(tuple(v))
        for j in range(rows-1):
            for k in range(cols-1):
                n=j*cols+k;fs.append((n,n+1,n+1+cols,n+cols))
        petal=mesh('Flower_Petal_%d_SatinBlade'%i,vs,fs,'P_petal_metal',p)
        sub=petal.modifiers.new('Continuous petal curvature','SUBSURF');sub.levels=1;sub.render_levels=2
        sol=petal.modifiers.new('Precision petal wall','SOLIDIFY');sol.thickness=.007
        edge=petal.modifiers.new('Polished blade edge','BEVEL');edge.width=.002;edge.segments=2
        # Continuous polished boundaries outline the three spoon forms at room
        # scale; the subtly darker underside separates overlapping petals.
        for side in [-1,1]:
            pts=[]
            for j in range(rows):
                t=j/(rows-1);wid=.135*(math.sin(math.pi*t)**.65)+.009*(1-t)
                v=direc*(.365*t)+perp*(wid*side)
                v.y=-.032+.025*t*t
                pts.append(tuple(v))
            tube('Flower_Petal_%d_RolledEdge_%d'%(i,side),pts,.0021,'titanium',p,8)
        cylinder('Flower_Petal_%d_ConnectingRod'%i,(-.013,.021,-.019),tuple(direc*.065+Vector((0,.014,0))),.010,'graphite',p)
    return r

def headphones():
    r=root('HEADPHONES_Root',(-4.02,1.30,1.64),'headphones_on_stand')
    cylinder('Headphones_Base',(0,0,.009),(0,0,.04),.185,'titanium',r)
    cylinder('Headphones_BaseGasket',(0,0,.003),(0,0,.011),.171,'graphite',r)
    lathe('Headphones_Stand',[(.069,.04),(.069,.05),(.044,.08),(.025,.18),(.022,.46),(.049,.49),(.055,.51)],'graphite',r,loc=(0,.047,0))
    arc=[]
    for i in range(41):
        a=math.pi*i/40
        arc.append((.205*math.cos(a),0,.386+.238*math.sin(a)))
    # Band width in depth and a precise flat outer ribbon.
    vs=[];fs=[]
    for i,co in enumerate(arc):
        x,y,z=co;a=math.pi*i/40
        nx,nz=math.cos(a),math.sin(a)
        for yy,th in [(-.033,.008),(.033,.008),(.033,-.008),(-.033,-.008)]:vs.append((x+nx*th,yy,z+nz*th))
    for i in range(40):
        for k in range(4):fs.append((4*i+k,4*i+(k+1)%4,4*(i+1)+(k+1)%4,4*(i+1)+k))
    fs.extend([(3,2,1,0),(160,161,162,163)])
    ob=mesh('Headphones_ArchedTitaniumBand',vs,fs,'titanium',r);beveled(ob,.005,3)
    tube('Headphones_BandInnerPadding',[(x*.963,y,z-.013) for x,y,z in arc[5:-5]],.018,'charcoal_fabric',r)
    for i,side in enumerate([-1,1]):
        p=group('Headphones_Cup_%d_Pivot'%i,(side*.188,0,.29),r,asset='headphone_cup_%d'%i)
        p.rotation_euler[1]=math.radians(side*-8)
        cylinder('Headphones_Cup_%d_Aluminium'%i,(side*-.018,0,0),(side*.039,0,0),.109,'titanium',p)
        cylinder('Headphones_Cup_%d_OuterCap'%i,(side*.039,0,0),(side*.044,0,0),.095,'graphite',p)
        torus('Headphones_Cup_%d_Cushion'%i,(side*-.04,0,0),.076,.032,'charcoal_fabric',p,rot=(0,math.pi/2,0),scale=(1.18,1,1))
        cylinder('Headphones_Cup_%d_DriverMesh'%i,(side*-.050,0,0),(side*-.053,0,0),.065,'charcoal_fabric',p)
        sphere('Headphones_Cup_%d_Joint'%i,(side*.012,0,.117),(.035,.035,.035),'titanium',p)
        tube('Headphones_Cup_%d_Fork'%i,[(side*.012,-.055,.128),(side*.035,-.080,.066),(side*.04,-.078,-.025)],.009,'titanium',p)
        torus('Headphones_Cup_%d_OuterSeam'%i,(side*.045,0,0),.091,.003,'titanium',p,rot=(0,math.pi/2,0))
        # Twin sliding arms and independent swivel axles.
        box('Headphones_Cup_%d_Slider'%i,(side*.005,.009,.139),(.021,.031,.071),'titanium',p,.007)
        box('Headphones_Cup_%d_SliderInset'%i,(side*.005,-.008,.139),(.010,.003,.046),'graphite',p,.003)
        disk_y('Headphones_Cup_%d_PivotScrew'%i,(side*.012,-.036,.117),.011,.009,'graphite',p)
        for notch in range(4):
            box('Headphones_Cup_%d_SliderMark_%d'%(i,notch),(side*.005,-.010,.129+notch*.010),(.010,.002,.001),'titanium',p,.0003)
        sphere('Headphones_Cup_%d_Indicator'%i,(side*.047,-.003,0),(.002,.003,.006),'amber_light',p,12,8)
    return r

def speaker():
    r=root('SPEAKER_Root',(-1.02,2.17,1.64),'ceramic_ring_speaker')
    r.rotation_euler[2]=math.radians(-12)
    cylinder('Speaker_Base',(0,0,.008),(0,0,.047),.198,'titanium',r)
    cylinder('Speaker_BaseRubber',(0,0,.002),(0,0,.008),.181,'graphite',r)
    sphere('Speaker_Swivel',(0,.022,.092),(.068,.068,.064),'titanium',r)
    shell=group('Speaker_Gimbal',(0,0,.324),r,asset='speaker_gimbal')
    shell.rotation_euler[0]=math.radians(12)
    torus('Speaker_CeramicToroid',(0,0,0),.176,.060,'ceramic',shell,rot=(math.pi/2,0,0))
    torus('Speaker_OuterPolishedSeam',(0,.012,0),.229,.003,'titanium',shell,rot=(math.pi/2,0,0))
    disk_y('Speaker_RearCasing',(0,.032,0),.171,.035,'graphite',shell)
    torus('Speaker_RubberSurround',(0,-.032,0),.133,.012,'black',shell,rot=(math.pi/2,0,0))
    disk_y('Speaker_DriverCloth',(0,-.031,0),.124,.019,'charcoal_fabric',shell)
    sphere('Speaker_CentralDiaphragm',(0,-.042,0),(.085,.010,.085),'charcoal_fabric',shell)
    for j in range(3):
        torus('Speaker_DiaphragmRipple_%d'%j,(0,-.044,0),.063+j*.020,.0014,'graphite',shell,rot=(math.pi/2,0,0))
    disk_y('Speaker_RearPort',(0,.055,0),.042,.011,'black',shell)
    box('Speaker_Status',(0,-.166,-.164),(.014,.005,.004),'amber_light',shell,.002)
    return r

def keyboard():
    r=root('KEYBOARD_Root',(-2.72,1.18,1.64),'split_keyboard')
    for i,side in enumerate([-1,1]):
        p=group('Keyboard_%s_Half'%('L' if side<0 else 'R'),(side*.225,0,0),r,asset='keyboard_half_%d'%i)
        p.rotation_euler[2]=math.radians(-side*9)
        box('Keyboard_%d_Base'%i,(0,0,.026),(.384,.225,.049),'graphite',p,.032)
        box('Keyboard_%d_TopPlate'%i,(0,0,.050),(.357,.204,.012),'titanium',p,.019)
        for row in range(3):
            for col in range(5):
                x=(col-2)*.063+(.005 if row==1 else 0);y=(row-1)*.056
                key=box('Keyboard_%d_Key_%d_%d'%(i,row,col),(x,y,.073),(.055,.048,.035),'ceramic',p,.009)
                mark_asset(key,'keyboard_%d_key_%d_%d'%(i,row,col),'press')
                if row!=2:
                    box('Keyboard_%d_KeyLegend_%d_%d'%(i,row,col),(x-.01,y+.007,.091),(.010,.002,.0007),'graphite',p,.0004)
        for t in range(2):
            k=box('Keyboard_%d_Thumb_%d'%(i,t),(side*.074+t*.06,-.127,.065),(.054,.039,.031),'ceramic',p,.008)
            mark_asset(k,'keyboard_%d_thumb_%d'%(i,t),'press')
    knob=group('Keyboard_Dial_Root',(0,.014,.008),r,asset='keyboard_dial')
    cylinder('Keyboard_DialBase',(0,0,0),(0,0,.025),.066,'graphite',knob)
    cylinder('Keyboard_DialWheel',(0,0,.025),(0,0,.068),.055,'titanium',knob)
    cylinder('Keyboard_DialTop',(0,0,.068),(0,0,.072),.046,'graphite',knob)
    box('Keyboard_DialMarker',(0,-.029,.074),(.005,.016,.002),'cool_light',knob,.001)
    for i in range(32):
        a=i*math.tau/32
        cylinder('Keyboard_DialKnurl_%02d'%i,(.054*math.cos(a),.054*math.sin(a),.031),(.054*math.cos(a),.054*math.sin(a),.061),.0018,'titanium',knob,8)
    control=group('Desktop_Controller_Root',(.48,.20,.011),r,asset='desktop_creative_controller')
    control['interaction']='rotate_and_press'
    cylinder('Desktop_Controller_Base',(0,0,.001),(0,0,.022),.087,'graphite',control)
    cylinder('Desktop_Controller_Bezel',(0,0,.022),(0,0,.051),.079,'titanium',control)
    cylinder('Desktop_Controller_Display',(0,0,.051),(0,0,.055),.067,'black',control)
    torus('Desktop_Controller_IlluminatedRing',(0,0,.056),.050,.0018,'cool_light',control)
    for i in range(12):
        a=i*math.tau/12
        tick=box('Desktop_Controller_Tick_%02d'%i,(.060*math.sin(a),.060*math.cos(a),.057),(.002,.006,.0015),'titanium',control,.0004)
        tick.rotation_euler[2]=-a
    box('Desktop_Controller_Readout',(0,0,.057),(.017,.006,.002),'amber_light',control,.002)
    return r

def camera():
    r=root('CAMERA_Root',(-3.48,1.065,1.64),'compact_camera')
    r.rotation_euler[2]=math.radians(-9)
    box('Camera_Body',(0,0,.105),(.32,.142,.194),'titanium',r,.026)
    box('Camera_TopPlate',(0,.002,.207),(.290,.128,.014),'graphite',r,.010)
    box('Camera_LeatherGrip',(.111,-.070,.106),(.070,.019,.161),'graphite',r,.014)
    lens=group('Camera_Lens_Root',(-.024,-.092,.108),r,asset='camera_focus_lens')
    lens['interaction']='focus_ring';lens['rotation_axis']='Y'
    disk_y('Camera_LensMount',(0,0,0),.073,.042,'graphite',lens)
    torus('Camera_LensFlange',(0,-.023,0),.067,.003,'titanium',lens,rot=(math.pi/2,0,0))
    disk_y('Camera_LensBarrel',(0,-.033,0),.063,.035,'titanium',lens)
    disk_y('Camera_FocusRubber',(0,-.040,0),.064,.020,'graphite',lens)
    knurled_ring_y('Camera_FocusGrip',(0,-.040,0),.064,.019,lens,56)
    torus('Camera_AmberLensRing',(0,-.055,0),.055,.0035,'P_gold',lens,rot=(math.pi/2,0,0))
    disk_y('Camera_OpticalGlass',(0,-.058,0),.048,.008,'P_lens',lens)
    disk_y('Camera_LensInner',(0,-.064,0),.029,.004,'black',lens)
    torus('Camera_InternalGlassRing',(0,-.066,0),.034,.0012,'P_screenline',lens,rot=(math.pi/2,0,0))
    sphere('Camera_OpticReflection',(-.017,-.067,.017),(.011,.0015,.006),'P_screenline',lens,16,8)
    for j in range(3):
        a=j*math.tau/3+math.pi/2
        precision_screw('Camera_LensMountScrew_%d'%j,(.066*math.cos(a),-.025,.066*math.sin(a)),.0035,lens)
    box('Camera_Viewfinder',(-.109,-.073,.172),(.044,.015,.025),'black',r,.006)
    disk_y('Camera_Tally',(.034,-.074,.175),.006,.002,'amber_light',r)
    cylinder('Camera_Shutter',(.079,-.005,.21),(.079,-.005,.225),.025,'titanium',r)
    box('Camera_Hotshoe',(-.03,.012,.217),(.052,.044,.008),'titanium',r,.002)
    box('Camera_HotshoeInset',(-.03,.012,.222),(.027,.036,.002),'black',r,.001)
    cylinder('Camera_ExposureDial',(-.111,.009,.215),(-.111,.009,.225),.021,'titanium',r,32)
    box('Camera_ExposureMark',(-.111,-.002,.226),(.003,.009,.001),'black',r,.0004)
    box('Camera_RearDisplay',(-.02,.074,.112),(.181,.008,.108),'black',r,.011)
    box('Camera_RearDisplayGlass',(-.02,.079,.112),(.155,.003,.083),'P_lens',r,.008)
    for j in range(3):
        sphere('Camera_RearButton_%d'%j,(.103,.080,.140-j*.034),(.012,.004,.012),'graphite',r,16,8)
    for j,x in enumerate([-.132,.142]):
        precision_screw('Camera_FrontScrew_%d'%j,(x,-.073,.060),.004,r)
    for x in [-.171,.171]:
        torus('Camera_StrapEye_%s'%str(x),(x,.008,.17),.012,.004,'titanium',r,rot=(math.pi/2,0,0))
    return r

def mug():
    r=root('CUP_Root',(-.69,1.74,1.64),'thermal_cup')
    lathe('Cup_DoubleWall',[(.055,.003),(.065,.01),(.07,.026),(.070,.232),(.067,.245),(.061,.245),(.062,.226),(.058,.025),(.055,.020)],'graphite',r)
    torus('Cup_BottomBand',(0,0,.022),.068,.003,'titanium',r)
    torus('Cup_PolishedLip',(0,0,.242),.064,.005,'titanium',r)
    torus('Cup_AmberTemperatureRing',(0,0,.124),.071,.004,'amber_light',r)
    torus('Cup_AmberFineBand',(0,0,.134),.071,.0015,'P_gold',r)
    cylinder('Cup_Drink',(0,0,.222),(0,0,.224),.059,'P_tea',r)
    for j in range(6):
        x=(j-2.5)*.006
        box('Cup_TemperaturePixel_%d'%j,(x,-.071,.168),(.003,.002,.006),'P_gold',r,.0008)
    return r

def coffee_objects():
    r=root('TABLE_OBJECTS_Root',(.65,-1.02,.88),'table_notebook_group')
    book=group('Notebook_Root',(-.065,.025,0),r,asset='notebook')
    # A second thin creative folio sits beneath the notebook with a different
    # rotation, forming a visible layered still life without unrelated clutter.
    folio=group('CreativeFolio_Root',(-.080,.020,0),r,asset='creative_folio')
    folio.rotation_euler[2]=math.radians(8)
    box('CreativeFolio_LowerCover',(0,0,.005),(.545,.345,.009),'P_folio',folio,.006)
    box('CreativeFolio_Paper',(.003,0,.015),(.529,.329,.012),'P_paper',folio,.003)
    box('CreativeFolio_UpperCover',(0,0,.024),(.545,.345,.009),'P_folio',folio,.006)
    box('CreativeFolio_Spine',(-.268,0,.014),(.011,.335,.025),'P_gold',folio,.004)
    book.location.z=.029
    book.rotation_euler[2]=math.radians(-14)
    box('Notebook_LowerCover',(0,0,.007),(.50,.33,.014),'black',book,.008)
    box('Notebook_Pages',(.003,.001,.025),(.480,.308,.026),'P_paper',book,.004)
    box('Notebook_UpperCover',(0,0,.046),(.50,.33,.014),'graphite',book,.009)
    box('Notebook_Spine',(-.245,0,.026),(.017,.319,.047),'graphite',book,.006)
    for j,z in enumerate([.017,.023,.029,.035]):
        box('Notebook_PageEdge_%d'%j,(.243,0,z),(.001,.305,.0007),'P_pageedge',book,.0002)
    tube('Notebook_AbstractGlyph',[(-.025,.040,.054),(-.045,.080,.054),(.018,.072,.054)],.0015,'titanium',book)
    box('Notebook_Bookmark',(.065,-.171,.026),(.021,.060,.002),'P_gold',book,.001)
    box('Notebook_ElasticStrap',(.187,0,.055),(.016,.330,.002),'black',book,.001)
    pen=group('CoffeePen_Root',(-.37,.13,.03),r,asset='coffee_table_pen')
    pen.rotation_euler[2]=math.radians(38)
    cylinder('CoffeePen_Barrel',(-.18,0,0),(.11,0,0),.009,'graphite',pen)
    cylinder('CoffeePen_Clip',(.07,-.008,.010),(.12,-.008,.010),.003,'titanium',pen,12)
    cylinder('CoffeePen_Ferrule',(-.205,0,0),(-.18,0,0),.009,'titanium',pen)
    sphere('CoffeePen_Nib',(-.210,0,0),(.012,.003,.003),'titanium',pen,16,10)
    cylinder('CoffeePen_EndBand',(.089,0,0),(.094,0,0),.0095,'P_gold',pen,24)
    dial=group('CoffeeDial_Root',(.30,-.028,0),r,asset='coffee_table_dial')
    cylinder('CoffeeDial_Base',(0,0,.004),(0,0,.020),.075,'graphite',dial)
    cylinder('CoffeeDial_Knob',(0,0,.020),(0,0,.045),.072,'titanium',dial)
    sphere('CoffeeDial_Top',(0,0,.044),(.066,.066,.008),'titanium',dial)
    cylinder('CoffeeDial_Centre',(0,0,.050),(0,0,.054),.019,'graphite',dial)
    box('CoffeeDial_Marker',(0,-.044,.052),(.005,.014,.003),'cool_light',dial,.001)
    for j in range(24):
        a=j*math.tau/24
        cylinder('CoffeeDial_Knurl_%02d'%j,(.071*math.cos(a),.071*math.sin(a),.024),(.071*math.cos(a),.071*math.sin(a),.040),.0015,'graphite',dial,8)
    return r

def leaf(name, origin, direction, length, width, material_name, par, bend=.016):
    ori=Vector(origin);d=Vector(direction).normalized()
    # Leaves generally present their smooth upper surface toward the room camera.
    facing=Vector((0,-1,.22));side=d.cross(facing)
    if side.length<.05:side=Vector((1,0,0))
    side.normalize();normal=side.cross(d).normalized()
    vs=[];fs=[];rows=9
    for i in range(rows):
        t=i/(rows-1);w=width*(math.sin(math.pi*t)**.85)
        for s in [-1,0,1]:
            pos=ori+d*length*t+side*w*s+normal*(bend*math.sin(math.pi*t)*(1-s*s*.8))
            vs.append(tuple(pos))
    for i in range(rows-1):
        j=i*3;fs.extend([(j,j+1,j+4,j+3),(j+1,j+2,j+5,j+4)])
    ob=mesh(name,vs,fs,material_name,par)
    solid=ob.modifiers.new('Leaf lamina','SOLIDIFY');solid.thickness=.0008
    return ob

def terrarium():
    r=root('TERRARIUM_Root',(4,2.9,.75),'glass_bonsai_terrarium')
    lathe('Terrarium_Base',[(.0,.008),(.21,.008),(.28,.032),(.319,.092),(.324,.126),(.317,.145),(.299,.145),(.294,.12),(.20,.051),(0,.051)],'graphite',r)
    torus('Terrarium_PolishedBaseRim',(0,0,.133),.318,.005,'titanium',r)
    globe=sphere('Terrarium_GlassGlobe',(0,0,.395),(.347,.347,.347),'P_clear_glass',r,64,40)
    wall=globe.modifiers.new('Thin handblown glass shell','SOLIDIFY');wall.thickness=.0025
    torus('Terrarium_TopLip',(0,0,.717),.121,.003,'P_gold',r)
    sphere('Terrarium_Soil',(0,0,.165),(.288,.282,.068),'P_soil',r)
    rng=random.Random(321)
    for i in range(15):
        a=rng.random()*math.tau;rad=rng.uniform(.14,.25)
        sphere('Terrarium_Pebble_%02d'%i,(rad*math.cos(a),rad*math.sin(a),.197),(.025*rng.uniform(.6,1.3),.020,.015),'P_stone',r,12,8)
    tube('Terrarium_Trunk',[(.01,.015,.187),(-.037,.008,.281),(-.044,.016,.370),(.005,.02,.453),(.030,.023,.517)],.016,'P_bark',r)
    ends=[(-.150,-.02,.430),(.143,.027,.480),(-.080,.063,.540),(.049,-.066,.565),(.133,-.091,.401),(-.151,.065,.376)]
    for i,end in enumerate(ends):
        start=(-.027,.016,.34+i*.022)
        mid=Vector(start).lerp(Vector(end),.5)+Vector((0,0,.022))
        tube('Terrarium_Branch_%d'%i,[start,tuple(mid),end],.005,'P_bark',r)
        for j in range(30):
            ox=rng.uniform(-.073,.073);oy=rng.uniform(-.044,.044);oz=rng.uniform(-.025,.036)
            ori=Vector(end)+Vector((ox,oy,oz))
            direc=(rng.uniform(-1,1),rng.uniform(-.5,.5),rng.uniform(-.4,1))
            leaf('Terrarium_Leaf_%d_%02d'%(i,j),ori,direc,.042+rng.random()*.024,.016+rng.random()*.007,'P_leaf_light' if j%3==0 else 'P_leaf',r,.003)
    for j in range(16):
        a=j*math.tau/16;rad=rng.uniform(.17,.25)
        moss=sphere('Terrarium_MossPad_%02d'%j,(rad*math.cos(a),rad*math.sin(a),.207),(.025+rng.random()*.015,.032,.014),'P_moss',r,16,10)
    for i,angle in enumerate([0,70,156,230,310]):
        a=math.radians(angle)
        tube('Terrarium_ExposedRoot_%d'%i,[(.01,.015,.208),(.09*math.cos(a),.09*math.sin(a),.189),(.16*math.cos(a),.16*math.sin(a),.186)],.006,'P_bark',r)
    return r

def vines():
    r=root('VINES_Root',(4.38,3.0,4.4),'trailing_wall_plant')
    rng=random.Random(748)
    paths=[[(0,0,0),(.10,-.10,-.12),(.17,-.18,-.42),(.19,-.22,-.72),(.14,-.20,-1.12)],
           [(-.13,-.04,.01),(.02,-.15,-.19),(.11,-.24,-.45),(.04,-.30,-.69),(.08,-.31,-.88)],
           [(-.36,.01,.02),(-.19,-.08,.01),(-.09,-.16,-.19),(-.05,-.17,-.36)],
           [(0,.02,0),(.18,.0,-.08),(.29,-.06,-.33),(.28,-.14,-.53),(.32,-.13,-.80)]]
    for i,path in enumerate(paths):
        tube('Vine_Stem_%d'%i,path,.007,'P_stem',r)
        # Sample along each polyline for alternating attached leaves.
        for seg in range(len(path)-1):
            a,b=Vector(path[seg]),Vector(path[seg+1])
            for j in range(5):
                t=(j+.2)/5;ori=a.lerp(b,t)
                for side in [-1,1]:
                    direction=Vector((side*rng.uniform(.6,1),rng.uniform(-.6,-.1),rng.uniform(-.25,.35)))
                    tip=ori+direction*.02
                    tube('Vine_Petiole_%d_%d_%d_%d'%(i,seg,j,side),[ori,tip],.002,'P_stem',r)
                    leaf('Vine_Leaf_%d_%d_%d_%d'%(i,seg,j,side),tip,direction,.082+rng.random()*.035,.036+rng.random()*.012,'P_leaf_light' if (i+j)%4==0 else 'P_leaf',r,.009)
    # A low upper crown rests on the architecture rather than floating above it.
    for j in range(22):
        ori=(rng.uniform(-.42,.09),rng.uniform(-.08,.08),rng.uniform(0,.06))
        leaf('Vine_CrownLeaf_%02d'%j,ori,(rng.uniform(-1,1),rng.uniform(-1,-.2),rng.uniform(.1,.8)),.10,.045,'P_leaf',r,.01)
    return r

def build():
    global COL
    if bpy.data.collections.get('PROPS'):
        COL=bpy.data.collections['PROPS']
    else:
        COL=bpy.data.collections.new('PROPS');bpy.context.scene.collection.children.link(COL)
    # Original materials supplement the shared room finishes.
    extras={
        'P_clear_glass':mat('ClearTerrariumGlass',(.89,.95,.97),0,.045),
        'P_petal_metal':mat('PetalBrushedSilver',(.58,.64,.70),.94,.27),
        'P_gold':mat('WarmAnodizedMetal',(.56,.32,.10),.75,.30),
        'P_screen':mat('DisplayInk',(.008,.016,.021),.20,.20),
        'P_screenline':mat('DisplaySilverBlue',(.20,.33,.39),.25,.35),
        'P_lens':mat('LensCoating',(.012,.065,.088),.75,.08),
        'P_tea':mat('TeaSurface',(.052,.018,.007),.05,.16),
        'P_paper':mat('WarmPaper',(.64,.61,.54),0,.70),
        'P_pageedge':mat('PageEdge',(.22,.21,.18),0,.8),
        'P_folio':mat('CreativeFolioCover',(.105,.13,.145),.03,.66),
        'P_moss':mat('TerrariumMoss',(.075,.14,.024),0,.90),
        'P_leaf':mat('DeepLeaf',(.052,.10,.027),0,.52),
        'P_leaf_light':mat('NewLeaf',(.14,.20,.051),0,.48),
        'P_stem':mat('GreenStem',(.070,.097,.028),0,.66),
        'P_bark':mat('BonsaiBark',(.093,.050,.022),0,.86),
        'P_soil':mat('Soil',(.044,.036,.017),0,.93),
        'P_stone':mat('RiverStone',(.25,.25,.21),0,.72),
    }
    M.update(extras)
    glass_principled=M['P_clear_glass'].node_tree.nodes.get('Principled BSDF')
    glass_principled.inputs['Transmission Weight'].default_value=1.0
    glass_principled.inputs['IOR'].default_value=1.46
    petal_nodes=M['P_petal_metal'].node_tree
    petal_shader=petal_nodes.nodes.get('Principled BSDF')
    brush=petal_nodes.nodes.new('ShaderNodeTexNoise')
    brush.inputs['Scale'].default_value=230
    brush.inputs['Detail'].default_value=2
    brush_bump=petal_nodes.nodes.new('ShaderNodeBump')
    brush_bump.inputs['Strength'].default_value=.075
    brush_bump.inputs['Distance'].default_value=.001
    petal_nodes.links.new(brush.outputs['Fac'],brush_bump.inputs['Height'])
    petal_nodes.links.new(brush_bump.outputs['Normal'],petal_shader.inputs['Normal'])
    # Organic grain stays subtle at miniature scale.
    for key,scale,strength in [('P_soil',95,.34),('P_bark',42,.22),('P_leaf',18,.07),('P_leaf_light',18,.07)]:
        m=M[key];nt=m.node_tree;p=nt.nodes.get('Principled BSDF')
        noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale
        noise.inputs['Detail'].default_value=3
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=strength;bump.inputs['Distance'].default_value=.012 if key=='P_soil' else .002
        nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    builders=[robot,terminal,archives,mechanical_flower,headphones,speaker,keyboard,camera,mug,coffee_objects,terrarium,vines]
    names=[]
    for fn in builders:
        obj=fn();names.append(obj['asset_id'])
    return {'collection':COL.name,'root_assets':names,'objects':len(COL.objects),'independent_interaction_parts':sum(1 for o in COL.objects if o.get('interactive',False))}
