# -*- coding: utf-8 -*-
"""Original warm, solid rear exhibition gallery for the orbital berth.

Append/rebuild WARM_GALLERY_V7 only; all geometry belongs to one static root.
No room/V6/world/camera/render changes. No third-party assets or text. No lights
are added: warm_light_sources provides world-space lighting/glow suggestions.
"""
import math
import bpy
from mathutils import Vector

COLLECTION='WARM_GALLERY_V7'
PREFIX='WG7_'
FLOOR=-1.04
C=None
ROOT=None
M={}
SOURCES=[]


def _mat(name,color,metal=0,rough=.4,emission=None):
    m=bpy.data.materials.get(PREFIX+'MAT_'+name) or bpy.data.materials.new(PREFIX+'MAT_'+name)
    m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    if emission:
        p.inputs['Emission Color'].default_value=(*emission[0],1)
        p.inputs['Emission Strength'].default_value=emission[1]
    return m


def mesh(name,verts,faces,mat,smooth=False):
    me=bpy.data.meshes.new(PREFIX+name+'_Mesh');me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(PREFIX+name,me);C.objects.link(o);o.parent=ROOT
    me.materials.append(M[mat]);o['static_environment']=True
    for f in me.polygons:f.use_smooth=smooth
    uv=me.uv_layers.new(name='UVMap')
    for f in me.polygons:
        major=max(range(3),key=lambda k:abs(f.normal[k]));ax=[i for i in range(3) if i!=major]
        for li in f.loop_indices:
            p=me.vertices[me.loops[li].vertex_index].co;uv.data[li].uv=(p[ax[0]],p[ax[1]])
    return o


def box(name,loc,size,mat,angle=0,bevel=0):
    x,y,z=[v*.5 for v in size]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o=mesh(name,vs,fs,mat);o.location=loc;o.rotation_euler.z=angle
    if bevel:
        b=o.modifiers.new('Architectural chamfer','BEVEL');b.width=bevel;b.segments=1;b.limit_method='ANGLE'
    return o


def cylinder(name,a,b,r,mat,sides=24):
    a,b=Vector(a),Vector(b);length=(b-a).length
    vs=[(r*math.cos(i*math.tau/sides),r*math.sin(i*math.tau/sides),z)
        for z in [-length*.5,length*.5] for i in range(sides)]
    fs=[tuple(reversed(range(sides))),tuple(range(sides,2*sides))]
    fs += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    o=mesh(name,vs,fs,mat,True);o.location=(a+b)*.5
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    o.data.polygons[0].use_smooth=False;o.data.polygons[1].use_smooth=False
    return o


def frustum(name,loc,rb,rt,height,mat,sides=32):
    vs=[(r*math.cos(i*math.tau/sides),r*math.sin(i*math.tau/sides),z)
        for r,z in [(rb,0),(rt,height)] for i in range(sides)]
    fs=[tuple(reversed(range(sides))),tuple(range(sides,2*sides))]
    fs += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    o=mesh(name,vs,fs,mat,True);o.location=loc
    o.data.polygons[0].use_smooth=False;o.data.polygons[1].use_smooth=False
    return o


def ring(name,centre,radius,wire,mat,plane='XZ',steps=40):
    # Analytic torus with outward-facing quads, no dependency graph operations.
    vs=[];fs=[]
    for i in range(steps):
        t=i*math.tau/steps
        for j in range(8):
            s=j*math.tau/8;r=radius+wire*math.cos(s)
            p=(r*math.cos(t),wire*math.sin(s),r*math.sin(t)) if plane=='XZ' else (r*math.cos(t),r*math.sin(t),wire*math.sin(s))
            vs.append(tuple(Vector(p)+Vector(centre)))
    for i in range(steps):
        for j in range(8):
            # XZ parameterisation has the opposite handedness from XY.
            q=(i*8+j,((i+1)%steps)*8+j,((i+1)%steps)*8+(j+1)%8,i*8+(j+1)%8)
            fs.append(tuple(reversed(q)) if plane=='XZ' else q)
    return mesh(name,vs,fs,mat,True)


def frame(deg,radius):
    a=math.radians(deg);angle=a-math.pi/2
    origin=Vector((radius*math.cos(a),radius*math.sin(a),0))
    xx=Vector((math.cos(angle),math.sin(angle),0));yy=Vector((-math.sin(angle),math.cos(angle),0))
    def point(x,y,z):return tuple(origin+xx*x+yy*y+Vector((0,0,z)))
    return point,angle


def fbox(tag,point,angle,loc,size,mat,bevel=0):
    return box(tag,point(*loc),size,mat,angle,bevel)


def source(name,position,radius=2.4,color=(1,.40,.10),kind='area',normal=(0,0,-1),width=1.5,height=1.0,strength=.32):
    target=Vector(position)+Vector(normal)*(2.3 if kind=='area' else 1.3)
    SOURCES.append({'id':name,'position':list(position),
        'color':'#ffb368' if color[1]>.45 else '#ff862c',
        'scale':min(3.0,max(1.0,radius)),'energy':230 if kind=='area' else 65,
        'target':list(target),'type':kind,'width':width,'height':height})


def rear_floor():
    n=84;inner=14.85;outer=20.10;a=math.radians(17);b=math.radians(160)
    vs=[]
    for z in [FLOOR,-.84]:
        for r in [outer,inner]:
            for i in range(n+1):
                t=a+(b-a)*i/n;vs.append((r*math.cos(t),r*math.sin(t),z))
    m=n+1;fs=[]
    for i in range(n):
        j=i+1
        fs.extend([(i,m+i,m+j,j),(2*m+i,2*m+j,3*m+j,3*m+i),
                   (i,j,2*m+j,2*m+i),(m+i,3*m+i,3*m+j,m+j)])
    fs.extend([(0,2*m,3*m,m),(n,m+n,3*m+n,2*m+n)])
    mesh('Continuous_Gallery_Foundation',vs,fs,'graphite')


def specimen_plant(tag,p,angle):
    base=p(-1.1,-.38,.744)
    frustum(tag+'_Pot',base,.35,.47,.57,'cream',32)
    cylinder(tag+'_Soil',p(-1.1,-.38,1.29),p(-1.1,-.38,1.32),.40,'graphite',24)
    for i,(dx,dy,h) in enumerate([(-.65,.08,1.62),(-.32,-.03,2.08),(.10,.08,2.38),(.43,.13,1.94),(.68,-.02,1.50)]):
        a=Vector(p(-1.1,-.38,1.29));b=Vector(p(-1.1+dx,-.38+dy,1.29+h))
        cylinder(tag+'_Stem_%d'%i,a,b,.022,'gold',12)
        # Thick faceted lancet silhouettes, deliberately calm and architectural.
        tangent=(b-a).normalized();side=Vector((math.cos(angle),math.sin(angle),0));depth=Vector((-math.sin(angle),math.cos(angle),0))
        c=a+(b-a)*.68;w=.17 if i%2 else .21
        vs=[tuple(a+(b-a)*.30),tuple(c+side*w),tuple(b),tuple(c-side*w),tuple(c+depth*.045),tuple(c-depth*.045)]
        fs=[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(1,0,5),(2,1,5),(3,2,5),(0,3,5)]
        mesh(tag+'_Leaf_%d'%i,vs,[tuple(reversed(f)) for f in fs],'leaf')


def loop_exhibit(tag,p,angle):
    fbox(tag+'_Pedestal',p,angle,(.25,-.26,1.245),(1.15,.93,1.01),'cream',.08)
    cylinder(tag+'_Mount',p(.25,-.26,1.74),p(.25,-.26,2.16),.066,'gold',24)
    # Triple orbital bronze rings on a real support; rotate geometry as a whole
    # about its local exhibit centre without introducing interactive asset roots.
    centre=p(.25,-.26,2.79)
    for i,(r,w) in enumerate([(.67,.055),(.48,.043),(.26,.035)]):
        ob=ring(tag+'_BronzeOrbit_%d'%i,(0,0,0),r,w,'gold','XZ',48)
        ob.location=centre;ob.rotation_euler=(0,math.radians(15*i),angle+math.radians(i*27))


def gallery_bay(i,deg,radius,top):
    p,angle=frame(deg,radius);name='Bay_%02d'%i
    height=top-FLOOR
    # A thick rear wall and deep piers frame a physically recessed inner chamber.
    fbox(name+'_Foundation',p,angle,(0,.04,-.87),(5.72,1.66,.34),'titanium',.055)
    fbox(name+'_BackWall',p,angle,(0,.50,FLOOR+height*.5),(5.35,.48,height),'walnut',.05)
    fbox(name+'_DarkNiche',p,angle,(0,.218,(top-.45+-.55)*.5),(4.45,.13,top+.10),'blue',.055)
    for side in [-1,1]:
        fbox(name+'_OuterPier_%d'%side,p,angle,(side*2.47,-.04,(FLOOR+top)*.5),(.48,1.27,height),'cream',.075)
        fbox(name+'_PierReveal_%d'%side,p,angle,(side*2.194,-.37,(FLOOR+top)*.5),(.076,.48,height-.26),'gold',.012)
    fbox(name+'_Crown',p,angle,(0,-.035,top+.10),(5.88,1.45,.24),'titanium',.035)
    fbox(name+'_FloatingCornice',p,angle,(0,-.29,top-.27),(5.16,1.11,.22),'cream',.035)
    # Broad warm underside remains recognisably golden after AgX baking.
    fbox(name+'_CorniceDiffuser',p,angle,(0,-.355,top-.402),(4.48,.65,.055),'warm',.012)
    normal=(-math.cos(math.radians(deg)),-math.sin(math.radians(deg)),0)
    source(name+'_Cornice',p(0,-.48,top-.43),3.0,(1,.56,.20),'area',(0,0,-1),4.5,.65,.34)
    fbox(name+'_LowCabinet',p,angle,(0,-.01,-.055),(4.47,.76,1.45),'graphite',.045)
    fbox(name+'_CabinetTop',p,angle,(0,-.03,.69),(4.55,.85,.10),'titanium',.025)
    for j in range(4):
        x=-1.66+j*1.10
        fbox(name+'_CabinetDoor_%d'%j,p,angle,(x,-.414,-.04),(1.04,.045,1.22),'walnut' if j%2 else 'blue',.025)
        fbox(name+'_CabinetGrip_%d'%j,p,angle,(x+.35,-.45,.23),(.031,.032,.27),'gold',.005)
    if i in [1,3,5]:
        screen_top=top-1.0;screen_bottom=1.12;h=screen_top-screen_bottom
        fbox(name+'_ScreenHousing',p,angle,(0,.076,(screen_top+screen_bottom)*.5),(3.32,.28,h+.28),'graphite',.05)
        fbox(name+'_AmberDiffusingScreen',p,angle,(0,-.085,(screen_top+screen_bottom)*.5),(2.99,.092,h),'amber',.025)
        # Five deep grille ribs and three cross rails catch grazing warm light.
        for j in range(5):
            fbox(name+'_GrilleRib_%d'%j,p,angle,(-1.22+j*.61,-.179,(screen_top+screen_bottom)*.5),(.062,.12,h+.03),'gold',.009)
        for j in range(3):
            fbox(name+'_GrilleCross_%d'%j,p,angle,(0,-.17,screen_bottom+(j+1)*h/4),(3.10,.13,.061),'walnut',.008)
        source(name+'_AmberScreen',p(0,-.30,(screen_top+screen_bottom)*.5),3.3,(1,.30,.055),'area',normal,3.0,h,.42)
    else:
        # Dark rear inset, shelf modules and selected exhibits fill the alcoves.
        for j in range(2):
            fbox(name+'_Shelf_%d'%j,p,angle,(0,-.01,top-1.27-j*1.28),(4.05,.81,.105),'titanium',.020)
        if i==0:specimen_plant(name,p,angle)
        elif i==4:loop_exhibit(name,p,angle)
        else:
            for j in range(3):
                x=-1.28+j*1.26
                fbox(name+'_ArchiveVessel_%d'%j,p,angle,(x,-.20,1.35+j*.09),(.61,.54,1.22+j*.18),'cream' if j%2 else 'walnut',.055)
                fbox(name+'_ArchiveInset_%d'%j,p,angle,(x,-.483,1.43+j*.09),(.33,.04,.66),'graphite',.025)
                fbox(name+'_ArchiveAmber_%d'%j,p,angle,(x,-.51,1.47+j*.09),(.073,.024,.47),'amber',.010)
    if i in [2,4]:
        # Pendant is rigidly connected to the canopy, not suspended in free space.
        z=top-2.17;pos=p(1.59,-.53,z)
        cylinder(name+'_PendantStem',p(1.59,-.53,z+.34),p(1.59,-.53,top-.43),.028,'gold',16)
        frustum(name+'_PendantShade',pos,.35,.19,.33,'walnut',32)
        cylinder(name+'_PendantDiffuser',p(1.59,-.53,z-.025),p(1.59,-.53,z+.018),.30,'warm',32)
        source(name+'_Pendant',p(1.59,-.53,z-.03),1.8,(1,.53,.17),'point',(0,0,-1),.60,.60,.24)


def foreground_lanterns():
    for i,(x,y,height) in enumerate([(-8.1,-4.35,1.67),(-9.0,-3.30,1.28),(8.15,-3.4,1.85),(9.12,-2.65,1.29)]):
        name='PathLantern_%d'%i;top=FLOOR+height
        cylinder(name+'_Foot',(x,y,FLOOR),(x,y,FLOOR+.17),.33,'graphite',32)
        cylinder(name+'_FootLip',(x,y,FLOOR+.16),(x,y,FLOOR+.21),.29,'titanium',32)
        cylinder(name+'_Stem',(x,y,FLOOR+.18),(x,y,top-.37),.076,'titanium',24)
        cylinder(name+'_LowerCap',(x,y,top-.39),(x,y,top-.32),.21,'gold',32)
        cylinder(name+'_AmberDiffuser',(x,y,top-.33),(x,y,top+.04),.171,'amber',32)
        cylinder(name+'_Crown',(x,y,top+.025),(x,y,top+.11),.235,'walnut',32)
        for j in range(4):
            a=math.tau*j/4
            cylinder(name+'_Cage_%d'%j,(x+.19*math.cos(a),y+.19*math.sin(a),top-.36),
                     (x+.19*math.cos(a),y+.19*math.sin(a),top+.04),.017,'gold',12)
        source(name,(x,y,top-.15),1.55,(1,.40,.09),'point',(0,0,1),.36,.40,.26)


def build(consolidate=False):
    global C,ROOT
    SOURCES.clear()
    old=bpy.data.collections.get(COLLECTION)
    if old:
        for o in list(old.all_objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(old);bpy.context.view_layer.update()
    C=bpy.data.collections.new(COLLECTION);bpy.context.scene.collection.children.link(C)
    ROOT=bpy.data.objects.new(PREFIX+'WARM_GALLERY_Root',None);C.objects.link(ROOT)
    ROOT['asset_id']='environment.warm_gallery';ROOT['static_environment']=True
    ROOT['exclude_from_room_framing']=True
    M.update({
        'titanium':_mat('Titanium',(.35,.43,.49),.76,.32),
        'cream':_mat('WarmCeramic',(.65,.59,.46),.10,.38),
        'walnut':_mat('WalnutOrangeEnamel',(.235,.075,.027),.18,.47),
        'blue':_mat('BlueGrey',(.049,.096,.124),.28,.45),
        'graphite':_mat('Graphite',(.018,.026,.031),.30,.48),
        'gold':_mat('ChampagneMetal',(.43,.235,.085),.75,.30),
        'leaf':_mat('DesaturatedBotanical',(.058,.115,.091),.12,.55),
        'amber':_mat('AmberDiffuser',(.94,.26,.025),.02,.44,((1,.27,.026),1.15)),
        'warm':_mat('WarmWhiteDiffuser',(.91,.53,.20),.02,.42,((1,.48,.13),.95)),
    })
    rear_floor()
    bays=[(24,17.15,5.70),(44,18.10,6.65),(64,18.50,7.20),(84,18.80,7.85),
          (104,18.35,7.10),(124,17.80,6.46),(146,17.15,5.55)]
    for i,(deg,r,top) in enumerate(bays):gallery_bay(i,deg,r,top)
    foreground_lanterns()
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    triangles=0;lo=Vector((1e6,1e6,1e6));hi=Vector((-1e6,-1e6,-1e6))
    # Single read-only evaluation pass; nothing is removed while graph is read.
    for o in C.objects:
        if o.type!='MESH':continue
        ev=o.evaluated_get(deps);me=ev.to_mesh()
        try:
            me.calc_loop_triangles();triangles+=len(me.loop_triangles)
            for v in me.vertices:
                p=o.matrix_world @ v.co
                for k in range(3):lo[k]=min(lo[k],p[k]);hi[k]=max(hi[k],p[k])
        finally:ev.to_mesh_clear()
    return {'collection':COLLECTION,'root':ROOT.name,'asset_id':ROOT['asset_id'],
            'triangles':triangles,'triangle_budget':35000,'within_budget':triangles<=35000,
            'mesh_count_before_bake_merge':sum(o.type=='MESH' for o in C.objects),
            'bounds_min':list(lo),'bounds_max':list(hi),'floor_z':FLOOR,
            'warm_light_sources':SOURCES.copy(),'gallery_bays':len(bays),
            'materials':[m.name for m in M.values()],
            'notes':'Seven deep solid gallery bays, 3 broad amber screens, 2 pendants, 4 foreground lanterns; all original static geometry.'}


run=build
if __name__=='__main__':
    import json
    print(json.dumps(build(),ensure_ascii=False,indent=2))
