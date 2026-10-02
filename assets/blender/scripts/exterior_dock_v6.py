# -*- coding: utf-8 -*-
"""Original solid orbital atelier berth; Blender Z-up, metres.

build() only recreates EXTERIOR_DOCK_V6. It never changes room objects, world,
lights, camera, render settings, or files. Six original PBR finishes. No external
textures. Closed solid geometry throughout; all apertures have physical depth.
No graph-evaluation/deletion interleaving and no automatic mesh consolidation.
"""
import math
import bpy
from mathutils import Vector

COLLECTION='EXTERIOR_DOCK_V6'
PREFIX='EXT6_'
C=None
STATIC_ROOT=None
M={}
PARTS=[]


def material(name,color,metal=0,rough=.4,emission=None):
    m=bpy.data.materials.get(PREFIX+'MAT_'+name) or bpy.data.materials.new(PREFIX+'MAT_'+name)
    m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    if emission:
        p.inputs['Emission Color'].default_value=(*emission[0],1)
        p.inputs['Emission Strength'].default_value=emission[1]
    return m


def mesh(name,verts,faces,mat,smooth=False):
    d=bpy.data.meshes.new(PREFIX+name+'_Mesh');d.from_pydata(verts,[],faces);d.update()
    o=bpy.data.objects.new(PREFIX+name,d);C.objects.link(o);d.materials.append(M[mat])
    o.parent=STATIC_ROOT
    o['environment_revision']=6;o['static_environment']=True
    for f in d.polygons:f.use_smooth=smooth
    # UVs survive a normal GLB export. The dedicated baking pass may replace them.
    uv=d.uv_layers.new(name='UVMap')
    for f in d.polygons:
        major=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3) if k!=major]
        for li in f.loop_indices:
            v=d.vertices[d.loops[li].vertex_index].co;uv.data[li].uv=(v[axes[0]],v[axes[1]])
    return o


def box(name,loc,dims,mat,bevel=0,angle=0):
    x,y,z=[d*.5 for d in dims]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o=mesh(name,vs,fs,mat);o.location=loc;o.rotation_euler.z=angle
    if bevel:
        b=o.modifiers.new('Solid machined chamfers','BEVEL');b.width=bevel;b.segments=1;b.limit_method='ANGLE'
    return o


def polygon_slab(name,outline,z0,z1,mat):
    n=len(outline);vs=[(x,y,z) for z in [z0,z1] for x,y in outline]
    fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    fs += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,vs,fs,mat)


def disk(name,x,y,radius,z0,z1,mat,steps=80):
    return polygon_slab(name,[(x+radius*math.cos(i*math.tau/steps),y+radius*math.sin(i*math.tau/steps)) for i in range(steps)],z0,z1,mat)


def annular_sector(name,inner,outer,start,stop,z0,z1,mat,steps=24,centre=(0,0)):
    """Watertight thick curved slab, including radial walls at both ends."""
    pts=[]
    for r in [outer,inner]:
        for i in range(steps+1):
            a=start+(stop-start)*i/steps
            pts.append((centre[0]+r*math.cos(a),centre[1]+r*math.sin(a)))
    n=steps+1;vs=[(x,y,z) for z in [z0,z1] for x,y in pts];fs=[]
    for i in range(steps):
        j=i+1
        fs.extend([(i,n+i,n+j,j),(2*n+i,2*n+j,3*n+j,3*n+i),
                   (i,j,2*n+j,2*n+i),(n+i,3*n+i,3*n+j,n+j)])
    fs.extend([(0,2*n,3*n,n),(steps,n+steps,3*n+steps,2*n+steps)])
    return mesh(name,vs,fs,mat)


def cylinder(name,a,b,radius,mat,sides=24):
    a,b=Vector(a),Vector(b);length=(b-a).length
    vs=[(radius*math.cos(i*math.tau/sides),radius*math.sin(i*math.tau/sides),z)
        for z in [-length*.5,length*.5] for i in range(sides)]
    fs=[tuple(reversed(range(sides))),tuple(range(sides,sides*2))]
    fs += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    o=mesh(name,vs,fs,mat,True);o.location=(a+b)*.5
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    o.data.polygons[0].use_smooth=False;o.data.polygons[1].use_smooth=False
    return o


def sweep(name,points,width,depth,mat,section_axis=(0,1,0)):
    """Closed octagonal rectangular structural beam, including terminal caps."""
    points=[Vector(p) for p in points];ref=Vector(section_axis).normalized()
    w,d=width*.5,depth*.5;c=min(w,d)*.23
    profile=[(-w+c,-d),(w-c,-d),(w,-d+c),(w,d-c),(w-c,d),(-w+c,d),(-w,d-c),(-w,-d+c)]
    vs=[];fs=[]
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized()
        side=ref-tangent*ref.dot(tangent)
        if side.length<.02:side=Vector((1,0,0))-tangent*tangent.x
        # Cross-section winding must point along the path tangent so all closed
        # beam faces are outward-facing under glTF's ordinary back-face culling.
        side.normalize();across=side.cross(tangent).normalized()
        for u,v in profile:vs.append(tuple(p+across*u+side*v))
    for i in range(len(points)-1):
        for j in range(8):fs.append((8*i+j,8*i+(j+1)%8,8*(i+1)+(j+1)%8,8*(i+1)+j))
    fs += [tuple(reversed(range(8))),tuple(8*(len(points)-1)+j for j in range(8))]
    return mesh(name,vs,fs,mat)


def rim_path(radius,start,stop,z,steps=32):
    return [(radius*math.cos(start+(stop-start)*i/steps),radius*math.sin(start+(stop-start)*i/steps),z) for i in range(steps+1)]


def deck():
    PARTS.append('thick layered circular berth with machined radial deck segments')
    disk('Berth_Underside',0,0,6.87,-.94,-.69,'graphite')
    disk('Berth_TitaniumFoundation',0,0,7.21,-.70,-.39,'titanium',96)
    disk('Berth_ShadowReveal',0,0,7.12,-.39,-.32,'graphite',96)
    disk('Berth_UpperDeck',0,0,7.02,-.32,-.218,'blue',96)
    # A subtly proud central carrier supports the existing 10 x 7 m room.
    disk('Berth_CentralCarrier',0,0,6.20,-.225,-.204,'graphite',80)
    for i in range(12):
        a=i*math.tau/12;gap=.023
        annular_sector('Berth_DeckTile_%02d'%i,6.26,6.88,a+gap,a+math.tau/12-gap,-.219,-.198,
                       'titanium' if i%3==0 else 'blue',12)
        # Solid recessed band sections let the base read as a manufactured object.
        annular_sector('Berth_LowerFlange_%02d'%i,7.12,7.25,a+.10,a+math.tau/12-.10,-.655,-.565,
                       'orange' if i in [7,10] else 'graphite',10)
        annular_sector('Berth_LuminousSeam_%02d'%i,6.94,6.974,a+.07,a+math.tau/12-.07,-.228,-.195,
                       'warm' if i in [7,10] else 'cool',10)
        p=(6.61*math.cos(a),6.61*math.sin(a))
        box('Berth_RadialConnector_%02d'%i,(*p,-.19),(.40,.035,.018),'graphite',.005,a)
    # Six squat support shoes stay attached to the underside rather than floating.
    for i in range(6):
        a=math.tau*i/6
        box('Berth_SupportShoe_%d'%i,(5.8*math.cos(a),5.8*math.sin(a),-.89),(.82,.48,.26),'graphite',.05,a)


def approach_steps():
    PARTS.append('two low front approach stairways with recessed warm riser lights')
    for side in [-1,1]:
        x=side*2.37
        # The landing intersects the solid circular rim, so each stair is attached.
        box('Approach_%d_Landing'%side,(x,-6.60,-.33),(1.32,.96,.25),'titanium',.035)
        for i in range(3):
            top=-.22-.16*(i+1);y=-7.15-i*.43
            box('Approach_%d_Step_%d'%(side,i),(x,y,top-.075),(1.27,.46,.15),'blue',.022)
            box('Approach_%d_Tread_%d'%(side,i),(x,y-.034,top+.01),(1.12,.35,.022),'titanium',.012)
            box('Approach_%d_Light_%d'%(side,i),(x,y-.234,top-.041),(.86,.014,.020),'warm',.004)
        for dx in [-.565,.565]:
            sweep('Approach_%d_Stringer'%side,[(x+dx,-6.97,-.42),(x+dx,-8.25,-.88)],.055,.08,'graphite',section_axis=(1,0,0))


def rear_corridor():
    PARTS.append('raised curved rear service gallery, bridges, and solid illuminated parapets')
    for i in range(7):
        start=math.radians(15+i*21.5);stop=start+math.radians(20.4)
        annular_sector('Gallery_Foundation_%d'%i,8.40,10.57,start,stop,-.87,-.44,'titanium',20)
        annular_sector('Gallery_WalkingDeck_%d'%i,8.52,10.45,start+.006,stop-.006,-.44,-.355,'blue',20)
        annular_sector('Gallery_InnerGuide_%d'%i,8.48,8.514,start+.028,stop-.028,-.39,-.335,'cool',20)
        annular_sector('Gallery_OuterReveal_%d'%i,10.50,10.56,start+.05,stop-.05,-.69,-.645,'warm' if i in [1,5] else 'cool',20)
    for i,deg in enumerate([39,90,141]):
        a=math.radians(deg);r=7.74
        box('Gallery_ConnectingBridge_%d'%i,(r*math.cos(a),r*math.sin(a),-.39),(1.75,.86,.18),'graphite',.035,a)
        box('Gallery_BridgeSurface_%d'%i,(r*math.cos(a),r*math.sin(a),-.283),(1.74,.79,.033),'titanium',.008,a)
        for side in [-1,1]:
            tangent=Vector((-math.sin(a),math.cos(a),0));centre=Vector((r*math.cos(a),r*math.sin(a),-.225))+tangent*(side*.39)
            box('Gallery_BridgeGuide_%d_%d'%(i,side),tuple(centre),(1.51,.026,.027),'warm',.004,a)
    for i,deg in enumerate([31,59,87,115,143]):
        a=math.radians(deg);b=a+math.radians(21)
        annular_sector('Gallery_BackShield_%d'%i,10.24,10.52,a,b,-.365,.79,'graphite',20)
        annular_sector('Gallery_BackShieldInlay_%d'%i,10.20,10.244,a+.018,b-.018,-.245,.575,'blue',20)
        annular_sector('Gallery_BackShieldCap_%d'%i,10.19,10.55,a,b,.78,.835,'titanium',20)
        annular_sector('Gallery_BackShieldLight_%d'%i,10.174,10.20,a+.035,b-.035,.635,.665,'cool',20)
        for t in [a,b]:
            box('Gallery_BackShieldUpright',(10.32*math.cos(t),10.32*math.sin(t),.24),(.16,.32,1.16),'titanium',.02,t)


def rear_supports():
    PARTS.append('anchored twin titanium parabolic portal with warm inner seam and cross-ties')
    # The two beams share substantial feet on the rear gallery. They are actual
    # swept octagonal solids, readable from the back and in oblique views.
    paths=[]
    for j,shift in enumerate([-.23,.23]):
        pts=[]
        for i in range(61):
            t=math.pi*i/60
            pts.append((7.45*math.cos(t),6.55+3.12*math.sin(t)+shift,-.40+6.35*math.sin(t)))
        paths.append(pts)
        sweep('Portal_MainBeam_%d'%j,pts,.245,.25,'titanium',section_axis=(0,1,0))
    inner=[]
    for i in range(61):
        t=math.pi*i/60
        inner.append((7.45*math.cos(t),6.275+3.12*math.sin(t),-.40+6.35*math.sin(t)))
    sweep('Portal_WarmInnerSeam',inner,.026,.018,'warm',section_axis=(0,1,0))
    for j,idx in enumerate([6,16,30,44,54]):
        a=Vector(paths[0][idx]);b=Vector(paths[1][idx])
        sweep('Portal_CrossTie_%d'%j,[tuple(a),tuple(b)],.20,.15,'orange' if j==2 else 'graphite',section_axis=(1,0,0))
    for side in [-1,1]:
        x=side*7.45;y=6.55
        box('Portal_Foundation_%d'%side,(x,y,-.67),(1.35,1.37,.48),'graphite',.065,side*math.radians(-18))
        box('Portal_Socket_%d'%side,(x,y,-.365),(.77,.92,.24),'titanium',.04)
        for dx in [-.47,.47]:
            cylinder('Portal_FootBolt',(x+dx,y,-.415),(x+dx,y,-.37),.058,'orange',20)
    # A lower asymmetric side gantry gives the berth depth beyond the rear arch.
    sidepts=[]
    for i in range(43):
        t=math.pi*i/42
        sidepts.append((-8.54-.90*math.sin(t),1.45+4.40*math.cos(t),-.47+4.40*math.sin(t)))
    sweep('LeftSide_Portal',sidepts,.22,.23,'titanium',section_axis=(1,0,0))
    for end in [sidepts[0],sidepts[-1]]:
        x,y,z=end
        box('LeftSide_Socket',(x,y,-.63),(1.14,.91,.41),'graphite',.05)
        box('LeftSide_AnchorPlate',(x,y,-.395),(.73,.67,.11),'titanium',.025)
    box('LeftSide_ConnectedFootWalkway',(-8.56,-2.32,-.58),(.87,1.73,.31),'graphite',.035)
    box('LeftSide_ConnectedFootTread',(-8.56,-2.32,-.405),(.78,1.66,.035),'blue',.012)
    seam=[(x+.125,y,z) for x,y,z in sidepts]
    sweep('LeftSide_CoolSeam',seam,.024,.018,'cool',section_axis=(1,0,0))


def side_station_base(tag,x,y):
    disk(tag+'_GroundedPedestal',x,y,.91,-1.025,-.80,'graphite',48)
    disk(tag+'_Island',x,y,1.14,-.83,-.41,'graphite',48)
    disk(tag+'_SilverLip',x,y,1.12,-.42,-.35,'titanium',48)
    disk(tag+'_Top',x,y,1.04,-.35,-.32,'blue',48)
    # Short physical gangway connects each station to the central dock edge.
    a=math.atan2(y,x);r=math.hypot(x,y);mid=(r+6.9)*.5
    box(tag+'_Bridge',(mid*math.cos(a),mid*math.sin(a),-.40),(r-6.9+.30,.72,.18),'titanium',.025,a)
    for side in [-1,1]:
        px=mid*math.cos(a)-math.sin(a)*side*.32;py=mid*math.sin(a)+math.cos(a)*side*.32
        box(tag+'_BridgeSeam',(px,py,-.30),(r-6.9+.15,.025,.020),'cool',.003,a)


def equipment_stations():
    PARTS.append('two connected equipment islands: power magazine and optical calibration station')
    x,y=-8.60,-1.02;side_station_base('PowerStation',x,y)
    box('PowerStation_MainCabinet',(x,y,.205),(1.04,.68,1.05),'titanium',.09)
    box('PowerStation_Recess',(x,y-.36,.24),(.81,.055,.74),'graphite',.045)
    box('PowerStation_Crown',(x,y,.76),(.93,.58,.105),'blue',.035)
    for i,dx in enumerate([-.255,0,.255]):
        box('PowerStation_Battery_%d'%i,(x+dx,y-.43,.26),(.162,.125,.56),'blue' if i!=1 else 'orange',.035)
        box('PowerStation_BatterySignal_%d'%i,(x+dx,y-.499,.43),(.033,.010,.14),'cool' if i!=1 else 'warm',.004)
        box('PowerStation_BatteryLatch_%d'%i,(x+dx,y-.50,.04),(.101,.015,.030),'titanium',.005)
    for dx in [-.48,.48]:
        box('PowerStation_SideGuard',(x+dx,y-.04,.24),(.08,.80,.80),'graphite',.035)
    # A tall but narrow optical instrument presents a recognisable silhouette.
    x,y=8.55,.65;side_station_base('OpticalStation',x,y)
    box('OpticalStation_Pedestal',(x,y,.0),(.75,.63,.66),'graphite',.065)
    box('OpticalStation_ServicePanel',(x,y-.335,.07),(.54,.026,.41),'blue',.025)
    box('OpticalStation_Status',(x,y-.35,.08),(.045,.012,.26),'warm',.004)
    for dx in [-.235,.235]:
        sweep('OpticalStation_Fork',[(x+dx,y,.32),(x+dx,y,1.22),(x+dx*.7,y,1.54)],.072,.085,'titanium',section_axis=(0,1,0))
    # Open optical ring: both inside and outside surfaces are real, thick geometry.
    ring=annular_sector('OpticalStation_Optic',.31,.39,0,math.tau,-.05,.05,'titanium',64)
    ring.rotation_euler.x=math.pi/2;ring.location=(x,y,1.34)
    inset=annular_sector('OpticalStation_OpticInset',.322,.343,0,math.tau,-.064,-.049,'cool',64)
    inset.rotation_euler.x=math.pi/2;inset.location=(x,y,1.34)
    cylinder('OpticalStation_CalibrationAxis',(x-.17,y,1.34),(x+.17,y,1.34),.022,'orange',20)
    cylinder('OpticalStation_LensHousing',(x,y-.06,1.34),(x,y+.07,1.34),.10,'graphite',32)
    cylinder('OpticalStation_Lens',(x,y-.075,1.34),(x,y-.061,1.34),.072,'cool',32)


def grounded_foundations():
    """Carry every outboard structure to the same exhibition floor datum."""
    PARTS.append('continuous grounded footings beneath arches, stairs and gallery')
    for side in [-1,1]:
        box('Portal_GroundFoot_%d'%side,(side*7.45,6.55,-.968),(1.19,1.21,.125),'graphite',.025)
        box('Approach_GroundFoot_%d'%side,(side*2.37,-8.09,-.971),(1.09,.37,.12),'graphite',.018)
    for y in [5.85,-2.95]:
        box('LeftSide_GroundFoot',(-8.54,y,-.927),(1.00,.78,.198),'graphite',.026)
    for i in range(7):
        angle=math.radians(25+i*21.5)
        box('Gallery_GroundPier_%d'%i,(9.4*math.cos(angle),9.4*math.sin(angle),-.963),(.72,1.10,.134),'graphite',.025,angle)


def build(consolidate=False):
    """Append the static environment; consolidation is left to the bake pipeline."""
    global C,STATIC_ROOT
    PARTS.clear()
    old=bpy.data.collections.get(COLLECTION)
    if old:
        for obj in list(old.all_objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(old)
        bpy.context.view_layer.update()
    C=bpy.data.collections.new(COLLECTION);bpy.context.scene.collection.children.link(C)
    STATIC_ROOT=bpy.data.objects.new(PREFIX+'ORBITAL_DOCK_Root',None)
    C.objects.link(STATIC_ROOT)
    STATIC_ROOT['asset_id']='environment.orbital_dock'
    STATIC_ROOT['static_environment']=True
    STATIC_ROOT['exclude_from_room_framing']=True
    STATIC_ROOT.empty_display_type='PLAIN_AXES';STATIC_ROOT.empty_display_size=.20
    M.update({
        'titanium':material('SatinTitanium',(.40,.47,.55),.77,.31),
        'blue':material('BlueGreyEnamel',(.095,.176,.235),.36,.38),
        'graphite':material('Graphite',(.020,.033,.047),.48,.36),
        'orange':material('BurntOrange',(.46,.102,.031),.24,.43),
        'cool':material('IceSignal',(.28,.67,.82),.1,.28,((.24,.61,.83),2.0)),
        'warm':material('WarmSignal',(.9,.45,.12),.05,.28,((1,.46,.13),2.6)),
    })
    for fn in [deck,approach_steps,rear_corridor,rear_supports,equipment_stations,grounded_foundations]:fn()
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get();triangles=0
    lo=Vector((1e6,1e6,1e6));hi=Vector((-1e6,-1e6,-1e6))
    # Read-only evaluation pass after all mutations. No object/data removal here.
    for obj in C.objects:
        if obj.type!='MESH':continue
        ev=obj.evaluated_get(deps);me=ev.to_mesh()
        try:
            me.calc_loop_triangles();triangles+=len(me.loop_triangles)
            for v in me.vertices:
                p=obj.matrix_world @ v.co
                for k in range(3):lo[k]=min(lo[k],p[k]);hi[k]=max(hi[k],p[k])
        finally:ev.to_mesh_clear()
    return {'collection':COLLECTION,'source_scene':bpy.context.scene.name,
            'root':STATIC_ROOT.name,'asset_id':STATIC_ROOT['asset_id'],
            'triangles':triangles,'triangle_budget':35000,'within_budget':triangles<=35000,
            'mesh_count_before_bake_merge':sum(o.type=='MESH' for o in C.objects),
            'material_count':len(M),'materials':[m.name for m in M.values()],
            'bounds_min':list(lo),'bounds_max':list(hi),'components':PARTS.copy(),
            'notes':'Closed solid geometry; six finishes; no room mutation; static exterior only.'}


run=build
if __name__=='__main__':
    import json
    print(json.dumps(build(),ensure_ascii=False,indent=2))
