"""Six original, individually interactive studio additions for the V2 room.
Only appends the STUDIO_ADDITIONS collection. No camera/render/world changes.
"""
import bpy
import math
from mathutils import Vector, Matrix
from common import M

C = None
ROOTS = []

def _link(o, par=None):
    for c in tuple(o.users_collection): c.objects.unlink(o)
    C.objects.link(o)
    if par is not None:
        o.parent=par; o.matrix_parent_inverse=Matrix.Identity(4)
    return o

def _mat(name,color,metal=0,rough=.45,trans=0):
    m=bpy.data.materials.get('D_'+name) or bpy.data.materials.new('D_'+name)
    m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    p.inputs['Transmission Weight'].default_value=trans
    if trans:p.inputs['IOR'].default_value=1.46
    return m

def _apply(o,mat):
    o.data.materials.append(M[mat] if isinstance(mat,str) else mat)
    return o

def _smooth(o):
    for p in o.data.polygons:p.use_smooth=True
    return o

def group(name,loc,par=None,asset=None):
    o=bpy.data.objects.new('D_'+name,None);C.objects.link(o)
    o.location=loc;o.empty_display_type='PLAIN_AXES';o.empty_display_size=.05
    if par is not None:o.parent=par;o.matrix_parent_inverse=Matrix.Identity(4)
    if asset:o['asset_id']=asset;o['interactive']=True;o['interaction']='inspect'
    return o

def root(name,loc,asset):
    o=group(name,loc,asset=asset);ROOTS.append(o);return o

def mesh(name,verts,faces,mat,par):
    d=bpy.data.meshes.new('D_'+name+'Mesh');d.from_pydata(verts,[],faces);d.update()
    o=bpy.data.objects.new('D_'+name,d);C.objects.link(o);o.parent=par
    _apply(o,mat);_smooth(o);return o

def bevel(o,rad=.008):
    b=o.modifiers.new('Soft precision edges','BEVEL');b.width=rad;b.segments=4
    n=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');n.keep_sharp=True
    return o

def box(name,loc,dim,mat,par,rad=.01):
    x,y,z=[v*.5 for v in dim]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o=mesh(name,vs,fs,mat,par);o.location=loc
    return bevel(o,rad) if rad else o

def sphere(name,loc,scale,mat,par):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,radius=1,location=loc)
    o=_link(bpy.context.object,par);o.name='D_'+name
    for v in o.data.vertices:
        v.co.x*=scale[0];v.co.y*=scale[1];v.co.z*=scale[2]
    return _smooth(_apply(o,mat))

def cylinder(name,a,b,rad,mat,par,sides=48):
    a,b=Vector(a),Vector(b);d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=rad,depth=d.length,location=(a+b)*.5)
    o=_link(bpy.context.object,par);o.name='D_'+name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    return bevel(_smooth(_apply(o,mat)),min(.006,rad*.15,d.length*.15))

def tube(name,pts,rad,mat,par,closed=False):
    d=bpy.data.curves.new('D_'+name+'Curve','CURVE');d.dimensions='3D';d.bevel_depth=rad;d.bevel_resolution=4
    s=d.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
    for p,co in zip(s.bezier_points,pts):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    s.use_cyclic_u=closed
    o=bpy.data.objects.new('D_'+name,d);C.objects.link(o);o.parent=par;return _apply(o,mat)

def lathe(name,profile,mat,par,offset=0):
    n=64;vs=[];fs=[]
    for radius,z in profile:
        for i in range(n):
            a=i*math.tau/n
            vs.append((radius*math.cos(a)+offset*math.sin(z*4),radius*math.sin(a),z))
    for j in range(len(profile)-1):
        for i in range(n):fs.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    return mesh(name,vs,fs,mat,par)

def circle(name,loc,radius,rad,mat,par,plane='XY'):
    x,y,z=loc;pts=[]
    for i in range(48):
        a=i*math.tau/48
        pts.append((x+radius*math.cos(a),y+radius*math.sin(a),z) if plane=='XY' else (x+radius*math.cos(a),y,z+radius*math.sin(a)))
    return tube(name,pts,rad,mat,par,True)

def studio_books():
    r=root('BOOKS_Root',(-1.50,2.78,1.42),'studio_reference_books')
    # Tall slim editions: original abstract jackets without invented titles.
    for i,x in enumerate([-.135,-.035,.064]):
        b=group('Book_%d_Root'%i,(x,0,.015),r,'creative_book_%d'%i)
        b.rotation_euler[1]=math.radians(-5 if i==0 else -2 if i==1 else 1)
        h=[.48,.515,.457][i];depth=[.24,.258,.229][i]
        cover=['D_cover_blue','graphite','D_cover_cream'][i]
        box('Book_%d_Pages'%i,(0,0,h/2),(.069,depth-.016,h-.017),'D_paper',b,.003)
        for side in [-1,1]:
            box('Book_%d_Cover_%d'%(i,side),(side*.039,0,h/2),(.008,depth,h),cover,b,.004)
        box('Book_%d_Spine'%i,(0,-depth/2,h/2),(.081,.012,h),cover,b,.005)
        for j in range(3):
            box('Book_%d_SpineBand_%d'%(i,j),(0,-depth/2-.007,h*.23+j*.021),(.049,.002,.003),'titanium',b,.0005)
        box('Book_%d_SpineMedallion'%i,(0,-depth/2-.008,h*.76),(.028,.002,.046),'D_gold',b,.005)
        for j in range(5):
            box('Book_%d_PageEdge_%d'%(i,j),((j-2)*.011,depth/2-.007,h/2),(.001,.001,h-.026),'D_paperline',b,.0002)
    for i,x in enumerate([-.234,.172]):
        b=group('Bookend_%d_Root'%i,(x,0,0),r,'titanium_bookend_%d'%i)
        box('Bookend_%d_Foot'%i,(0,.008,.009),(.155,.302,.018),'titanium',b,.012)
        panel=box('Bookend_%d_Upright'%i,(0,.031,.16),(.022,.265,.302),'titanium',b,.021)
        # Rounded rectangular cut-out impression, set within the broad metal face.
        box('Bookend_%d_Inset'%i,((-.012 if i==0 else .012),.028,.169),(.004,.152,.172),'graphite',b,.022)
        tube('Bookend_%d_RoundedShoulder'%i,[(0,-.119,.034),(0,-.119,.273),(0,-.088,.312),(0,.114,.312)],.010,'titanium',b)
    return r

def specimen():
    r=root('SPECIMEN_Root',(-.35,2.78,1.42),'geometric_specimen_cloche')
    lathe('Specimen_Base',[(0,0),(.19,0),(.218,.013),(.221,.031),(.212,.049),(0,.049)],'graphite',r)
    circle('Specimen_BaseRim',(0,0,.037),.216,.003,'titanium',r)
    dome=lathe('Specimen_SmokeGlass',[(.206,.050),(.210,.080),(.210,.386),(.198,.455),(.161,.511),(.104,.551),(.030,.571),(0,.574)],'D_smoke_glass',r)
    s=dome.modifiers.new('Thin glass enclosure','SOLIDIFY');s.thickness=.0022
    a=group('Specimen_Geometry_Root',(0,0,.300),r,'original_trefoil_geometry')
    a['interaction']='rotate'
    # An original parametric trefoil, freely standing on a minimal clear stem.
    pts=[]
    for i in range(90):
        t=i*math.tau/90
        pts.append((.053*(2+math.cos(3*t))*math.cos(2*t),.053*(2+math.cos(3*t))*math.sin(2*t),.082*math.sin(3*t)))
    form=tube('Specimen_Trefoil',pts,.018,'titanium',a,True)
    a.rotation_euler=(math.radians(64),math.radians(11),math.radians(-18))
    sphere('Specimen_InnerOrb',(0,0,0),(.038,.038,.038),'D_gold',a)
    cylinder('Specimen_Stem',(0,0,.049),(0,0,.187),.007,'D_smoke_glass',r)
    circle('Specimen_DisplaySeat',(0,0,.058),.048,.004,'D_gold',r)
    return r

def communicator():
    r=root('COMMUNICATOR_Root',(1.0,2.78,1.42),'portable_fold_communicator')
    box('Comms_DockFoot',(0,.016,.020),(.312,.258,.038),'titanium',r,.044)
    box('Comms_DockGrip',(0,.016,.006),(.270,.215,.010),'graphite',r,.027)
    tube('Comms_DockNeck',[(0,.076,.035),(0,.079,.084),(0,.024,.156)],.030,'graphite',r)
    body=group('Comms_Handset_Root',(0,-.023,.059),r,'folding_communicator_handset')
    body.rotation_euler[0]=math.radians(-8)
    for i,z in enumerate([.123,.347]):
        p=group('Comms_Panel_%d_Hinge'%i,(0,0,z-.105),body,'communicator_panel_%d'%i)
        if i==1:p.rotation_euler[0]=math.radians(-7)
        box('Comms_Panel_%d_Shell'%i,(0,0,.105),(.239,.033,.212),'titanium',p,.024)
        box('Comms_Panel_%d_Glass'%i,(0,-.020,.106),(.216,.008,.185),'black',p,.017)
        # Abstract map and signal graphics avoid fabricated personal information.
        for j in range(4):
            circle('Comms_Panel_%d_Orbit_%d'%(i,j),(0,-.026,.113),.018+j*.012,.00065,'D_screen_line',p,'XZ')
        if i==0:
            for j in range(3):
                box('Comms_DeckReadout_%d'%j,(-.033+j*.033,-.026,.036),(.019,.001,.004),'cool_light' if j==0 else 'D_screen_line',p,.001)
        else:
            sphere('Comms_OpticalPort',(0,-.026,.194),(.004,.002,.004),'D_lens',p)
            tube('Comms_SignalArc',[(-.059,-.027,.155),(-.006,-.027,.121),(.054,-.027,.168)],.001,'amber_light',p)
    cylinder('Comms_FoldHinge',(-.117,0,.232),(.117,0,.232),.011,'graphite',body)
    for x in [-.081,.081]:
        cylinder('Comms_HingeCollar', (x-.016,0,.232),(x+.016,0,.232),.012,'titanium',body)
    return r

def ceramic_sculpture():
    r=root('SCULPTURE_Root',(2.25,2.78,1.42),'ceramic_mobius_study')
    cylinder('Sculpture_Foot',(0,0,.005),(0,0,.043),.181,'graphite',r)
    circle('Sculpture_FootRim',(0,0,.041),.172,.003,'titanium',r)
    a=group('Sculpture_Form_Root',(0,0,.294),r,'ceramic_mobius_form')
    a.rotation_euler[2]=math.radians(-18)
    # Broad continuous porcelain ribbon with a true half twist and open centre.
    vs=[];fs=[];n=112;m=13
    for i in range(n):
        t=i*math.tau/n
        for j in range(m):
            u=(j/(m-1)-.5)*.127
            radius=.172+u*math.cos(t*.5)
            vs.append((radius*math.cos(t),u*math.sin(t*.5),radius*math.sin(t)))
    for i in range(n):
        for j in range(m-1):
            if i<n-1:fs.append((i*m+j,i*m+j+1,(i+1)*m+j+1,(i+1)*m+j))
            else:fs.append((i*m+j,i*m+j+1,m-2-j,m-1-j))
    ob=mesh('Sculpture_PorcelainMobius',vs,fs,'ceramic',a)
    so=ob.modifiers.new('Porcelain ribbon wall','SOLIDIFY');so.thickness=.023
    be=ob.modifiers.new('Rolled ceramic lips','BEVEL');be.width=.009;be.segments=4
    sub=ob.modifiers.new('Silky ceramic surface','SUBSURF');sub.levels=1;sub.render_levels=2
    cylinder('Sculpture_Mount',(0,0,.043),(0,0,.083),.020,'D_gold',r)
    return r

def curved_leaf(name,par,base,tip,width,mat,asset,bend=.045):
    p=group(name+'_Pivot',base,par,asset)
    end=Vector(tip)-Vector(base)
    # A gently cupped lanceolate surface, each leaf on its own animation pivot.
    tangent=end.normalized();side=Vector((1,0,0))
    if abs(tangent.dot(side))>.85:side=Vector((0,1,0))
    side=(side-tangent*side.dot(tangent)).normalized()
    facing=tangent.cross(side).normalized()
    vs=[];fs=[];rows=19;cols=7
    for j in range(rows):
        t=j/(rows-1);centre=end*t+Vector((0,-bend*math.sin(math.pi*t),.027*math.sin(math.pi*t)))
        w=width*math.sin(math.pi*t)**.8
        for k in range(cols):
            s=-1+2*k/(cols-1)
            co=centre+side*w*s+facing*(.018*(1-s*s)*math.sin(math.pi*t))
            vs.append(tuple(co))
    for j in range(rows-1):
        for k in range(cols-1):
            q=j*cols+k;fs.append((q,q+1,q+1+cols,q+cols))
    o=mesh(name,vs,fs,mat,p)
    so=o.modifiers.new('Botanical lamina','SOLIDIFY');so.thickness=.0012
    pts=[]
    for i in range(9):
        t=i/8;co=end*t+Vector((0,-bend*math.sin(math.pi*t),.027*math.sin(math.pi*t)))+facing*.020*math.sin(math.pi*t);pts.append(tuple(co))
    tube(name+'_Midrib',pts,.0014,'D_leaf_vein',p)
    return p

def small_planter():
    r=root('SMALL_PLANTER_Root',(3.0,2.72,1.42),'glass_cutting_planter')
    lathe('Planter_Glass',[(.084,.006),(.124,.021),(.139,.074),(.136,.152),(.110,.206),(.087,.215),(.082,.211)],'D_clear_glass',r)
    base=cylinder('Planter_CeramicFoot',(0,0,0),(0,0,.023),.091,'graphite',r)
    sphere('Planter_Soil',(0,0,.133),(.118,.118,.034),'D_soil',r)
    circle('Planter_Lip',(0,0,.214),.085,.003,'titanium',r)
    leaves=[((-.015,0,.141),(-.140,-.018,.405),.047),((.009,.01,.142),(.084,.012,.471),.048),((.001,-.015,.146),(.151,-.056,.343),.042),((-.003,.007,.146),(-.051,.058,.499),.041),((.002,-.013,.143),(-.074,-.082,.295),.039)]
    for i,(base,tip,w) in enumerate(leaves):curved_leaf('Planter_Leaf_%d'%i,r,base,tip,w,'D_leaf' if i%2 else 'D_leaf_light','small_planter_leaf_%d'%i,.022)
    return r

def floor_vase():
    r=root('FLOOR_VASE_Root',(4.1,.45,.18),'black_ceramic_floor_planter')
    profile=[(0,.006),(.146,.006),(.201,.037),(.236,.099),(.251,.237),(.239,.414),(.202,.560),(.132,.682),(.111,.718),(.108,.734),(.096,.734),(.096,.716),(.117,.676),(.187,.555),(.222,.414),(.232,.24),(.213,.10),(.18,.06),(0,.06)]
    vase=lathe('FloorVase_AsymmetricCeramic',profile,'D_black_ceramic',r,.032)
    circle('FloorVase_BaseEdge',(0,0,.028),.174,.003,'titanium',r)
    circle('FloorVase_Mouth',(math.sin(.734*4)*.032,0,.734),.102,.003,'graphite',r)
    sphere('FloorVase_Soil',(.010,0,.680),(.10,.10,.027),'D_soil',r)
    leaves=[((0,.014,.66),(-.282,-.03,1.204),.060),((.009,.005,.66),(-.151,.08,1.318),.050),((.017,.008,.66),(.086,.029,1.355),.048),((.004,-.010,.66),(.252,-.072,1.235),.061),((.012,-.004,.66),(.298,.050,1.075),.062),((-.008,-.010,.66),(-.244,-.124,1.015),.055),((.0,-.014,.66),(.031,-.164,1.292),.060)]
    for i,(base,tip,w) in enumerate(leaves):
        # The floor foliage stays within an approximately 65 cm wide footprint.
        leaf=curved_leaf('FloorVase_Leaf_%d'%i,r,base,tip,w,'D_leaf' if i%3 else 'D_leaf_light','floor_vase_leaf_%d'%i,.035)
    return r

def build():
    global C
    C=bpy.data.collections.get('STUDIO_ADDITIONS')
    if C is None:C=bpy.data.collections.new('STUDIO_ADDITIONS');bpy.context.scene.collection.children.link(C)
    M.update({
        'D_cover_blue':_mat('BlueGreyBookCloth',(.080,.124,.155),0,.79),
        'D_cover_cream':_mat('WarmGreyBookCloth',(.43,.43,.38),0,.78),
        'D_paper':_mat('BookPaper',(.60,.59,.51),0,.85),
        'D_paperline':_mat('PaperEdges',(.22,.23,.20),0,.91),
        'D_gold':_mat('SoftAnodizedGold',(.49,.32,.135),.80,.30),
        'D_smoke_glass':_mat('SpecimenSmokeGlass',(.53,.65,.69),.03,.043,1),
        'D_clear_glass':_mat('PlanterGlass',(.78,.90,.92),0,.04,1),
        'D_screen_line':_mat('SoftDisplayLine',(.15,.33,.40),.35,.30),
        'D_lens':_mat('OpticCoating',(.016,.069,.081),.60,.10),
        'D_leaf':_mat('DeepLanceLeaf',(.030,.091,.037),0,.43),
        'D_leaf_light':_mat('SageLanceLeaf',(.084,.146,.055),0,.48),
        'D_leaf_vein':_mat('PaleMidrib',(.131,.181,.067),0,.59),
        'D_soil':_mat('PlanterSoil',(.033,.024,.012),0,.93),
        'D_black_ceramic':_mat('BlackCeramic',(.014,.020,.027),.10,.23),
    })
    for name in ['D_cover_blue','D_cover_cream','D_black_ceramic']:
        mat=M[name];nt=mat.node_tree;p=nt.nodes.get('Principled BSDF')
        n=nt.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=160;n.inputs['Detail'].default_value=2
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.001;bump.inputs['Strength'].default_value=.09
        nt.links.new(n.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    assets=[]
    for fn in [studio_books,specimen,communicator,ceramic_sculpture,small_planter,floor_vase]:
        r=fn();assets.append(r['asset_id'])
    return {'collection':C.name,'assets':assets,'object_count':len(C.objects),'interactive_parts':sum(bool(o.get('interactive')) for o in C.objects)}
