"""Approved Archive Atelier: cabinet, trophy cloches and slatted oak screen.
Blender-only authoring. All dimensions in metres, Z up. Data is placeholder.
"""
import bpy
import math
from mathutils import Matrix
import kit as K


def R(name, loc, parent=None, interaction='inspect'):
    o=K.root(name,loc)
    o.parent=parent
    o.matrix_parent_inverse=Matrix.Identity(4)
    o['interaction']=interaction
    return o


def B(name,loc,dims,mat,parent,edge=.01):
    return K.box(name,loc,dims,K.M[mat],parent,edge)


def handle(name,x,y,z,width,parent):
    for dx in [-width/2,width/2]:
        B(name+'.mount',(x+dx,y+.022,z),(.044,.034,.055),'brass',parent,.007)
        K.rod(name+'.post',(x+dx,y+.009,z),(x+dx,y-.025,z),.012,K.M['brass'],parent)
    K.rod(name+'.grip',(x-width/2-.006,y-.025,z),(x+width/2+.006,y-.025,z),.017,K.M['brass'],parent)


def ribbon_spool(name,loc,ma,parent):
    o=R(name,loc,parent)
    K.cylinder(name+'.ribbon',(0,0,.025),.061,.038,K.M[ma],o,40)
    for z in [0,.05]:
        K.cylinder(name+'.rim',(0,0,z),.073,.012,K.M['paper'],o,40)
    K.cylinder(name+'.eye',(0,0,.058),.021,.009,K.M['brass'],o,24)
    return o


def sheet_bundle(name,loc,w,h,parent,cover='paper',angle=0):
    p=R(name,loc,parent)
    p.rotation_euler.z=angle
    B(name+'.paper',(0,0,.032),(w,h,.054),'paper',p,.003)
    for z in [.002,.064]:B(name+'.cover',(0,0,z),(w+.012,h+.012,.006),cover,p,.001)
    # Discrete exposed signatures retain crisp page edges at close inspection.
    for j in range(5):
        B(name+'.signature',(0,-h/2-.001,.012+j*.008),(w-.02,.0015,.0012),'ivory',p,.0002)
    return p


def cabinet_contents(drawer,index):
    if index==1:
        # Removable felt medal tray and two archive envelopes.
        tray=R('archive.medal_tray',(0,.27,.109),drawer)
        B('Medal tray recess',(0,0,0),(.64,.39,.044),'wood_dark',tray,.009)
        B('Felt tray lining',(0,0,.025),(.60,.35,.012),'fabric',tray,.004)
        for x in [-.17,.16]:
            medal=R('archive.medal.'+str(x),(x,-.025,.039),tray)
            K.cylinder('Unassigned medal',(0,0,0),.061,.012,K.M['brass'],medal,48)
            K.torus('Medal coin rim',(0,0,.007),.052,.004,K.M['brass'],medal)
            K.cylinder('Medal central insignia',(0,0,.008),.025,.006,K.M['navy'],medal,6)
            B('Ribbon tail',(0,.083,-.003),(.044,.125,.006),'navy',medal,.002)
        sheet_bundle('archive.envelope.01',(-.49,.31,.095),.17,.34,drawer,'ivory',-.035)
        sheet_bundle('archive.envelope.02',(.47,.33,.095),.20,.38,drawer,'leather',.025)
        ribbon_spool('archive.ribbon_spool',(.48,.59,.102),'navy',drawer)
    elif index==3:
        # Slot-separated wood, ceramic and fabric samples.
        for i in range(4):
            x=-.43+i*.287
            B('Materials divider',(x+.137,.35,.16),(.012,.56,.13),'wood_z',drawer,.002)
            sample=R('archive.material_sample.'+str(i),(x,.27,.107),drawer)
            ma=['ivory','ceramic','wood','navy'][i]
            if i==1:
                K.sphere('Stone reference pebble',(0,0,.060),.083,K.M[ma],sample,scale=(1.1,.80,.72))
            else:
                B('Sample slab',(0,0,.044),(.205,.20,.07),ma,sample,.008)
                B('Paper identifying band',(0,0,.081),(.035,.203,.005),'paper',sample,.001)
            B('Compartment sample card',(x,.54,.105),(.19,.16,.018),'paper',drawer,.002)
            B('Card blank line',(x,.543,.116),(.11,.004,.002),'ink',drawer,.0003)
    else:
        B('Closed drawer lining',(0,.33,.092),(1.24,.59,.006),'fabric',drawer,.001)


def cabinet():
    c=R('archive.cabinet',(-2.60,1.28,.36),interaction='cabinet')
    # Real carcass, not a solid box: open bays remain hollow.
    B('Cabinet plinth',(0,0,.075),(1.50,.90,.15),'wood_dark',c,.016)
    for x in [-.716,.716]:
        B('Solid walnut side',(x,0,1.57),(.068,.90,2.96),'wood_z',c,.009)
        B('Brass front edge',(x,-.454,1.565),(.010,.014,2.96),'brass',c,.002)
        B('Side panel raised centre',(x+(.035 if x>0 else -.035),.014,1.55),(.014,.69,2.68),'wood_z',c,.005)
    B('Walnut back',(0,.424,1.57),(1.38,.052,2.96),'wood_z',c,.007)
    B('Walnut crown',(0,0,3.017),(1.52,.94,.066),'wood',c,.015)
    B('Crown underside line',(0,-.464,2.977),(1.48,.016,.013),'brass',c,.002)
    for z in [.15,.61,1.07,1.53,1.99,2.45,2.91]:
        B('Drawer aperture crossrail',(0,-.427,z),(1.39,.058,.038),'wood',c,.004)
        B('Drawer support shelf',(0,.023,z-.005),(1.365,.80,.026),'wood_dark',c,.003)
    for index,z in enumerate([2.68,2.22,1.76,1.30,.84,.38]):
        extension={1:.25,3:.40}.get(index,0)
        d=R('archive.drawer.%02d'%(index+1),(0,-.46-extension,z-.209),c,'slide')
        d['open_distance']=extension;d['slide_axis']='-Y';d['max_extension']=.48
        B('Drawer walnut front',(0,0,.209),(1.36,.055,.452),'wood',d,.008)
        # Front panel has a restrained framed edge / lower raised field.
        for xx in [-.646,.646]:B('Drawer edge stile',(xx,-.031,.209),(.015,.010,.398),'wood_z',d,.002)
        for zz in [.015,.403]:B('Drawer field moulding',(0,-.031,zz),(1.285,.010,.012),'wood',d,.002)
        B('Drawer bottom',(0,.362,.065),(1.30,.70,.035),'wood',d,.003)
        for xx in [-.633,.633]:B('Drawer box dovetail side',(xx,.366,.196),(.034,.70,.26),'wood_z',d,.003)
        B('Drawer box rear',(0,.708,.196),(1.28,.034,.26),'wood',d,.003)
        for xx in [-.654,.654]:
            B('Drawer steel rail',(xx,.35,.12),(.012,.61,.026),'metal',d,.002)
            # Dovetail joinery is visible only at front corners of open drawers.
            if extension:
                for zz in [.10,.165,.23]:
                    B('Dovetail endgrain',(xx,.048,zz),(.010,.026,.028),'wood_dark',d,.001)
        handle('Archive drawer pull',0,-.053,.17 if index==0 else .238,.31,d)
        cabinet_contents(d,index)
        if index==0:
            K.panel_label('About cabinet plate','关于我',(0,-.061,.324),.62,.12,d)
    # Book stack on cabinet top, intentionally without author/award claims.
    for j,(w,d,ma,a) in enumerate([(.85,.46,'ivory',-.025),(.80,.48,'navy',.022),(.83,.44,'paper',-.038)]):
        b=sheet_bundle('archive.top_book.%d'%j,(.26,.02,3.052+j*.0782),w,d,c,ma,a)
        b.scale.z=1.15
    box=R('archive.keepsake_box',(.26,.06,3.280),c)
    B('Keepsake brushed metal body',(0,0,.095),(.37,.30,.18),'metal',box,.025)
    B('Keepsake lid',(0,0,.193),(.386,.316,.026),'dark',box,.012)
    return c


def screen():
    r=R('archive.walnut_screen',(-.95,1.94,.36),interaction='architecture')
    r['interactive']=False
    B('Slat screen backing',(0,.075,1.845),(1.72,.076,3.69),'wood_dark',r,.007)
    for i in range(20):
        x=-.815+i*(1.63/19)
        B('Solid vertical walnut fin %02d'%i,(x,0,1.845),(.042,.115,3.69),'wood_z',r,.004)
    for x in [-.872,.872]:
        B('Screen metal stile',(x,.032,1.845),(.025,.136,3.705),'navy',r,.004)
        for z in [.038,3.646]:K.screw('Screen corner fixing',(x,-.039,z),K.M['brass'],r,r=.012)
    for z in [.016,3.686]:B('Screen cap rail',(0,.032,z),(1.76,.137,.028),'brass',r,.004)
    for x in [-.73,.73]:B('Screen concealed base',(x,.035,.035),(.18,.25,.07),'navy',r,.012)
    return r


def glass_cloche(name,radius,height,parent):
    """Closed 4mm shell: two dome surfaces, solid annular bottom, welded poles."""
    t=.004; n=72; steps=16;side=height-radius
    verts=[]; faces=[]
    profiles=[]
    for inner in [False,True]:
        rr=radius-t if inner else radius
        profiles.append([(rr,0),(rr,.006),(rr,side*.5)]+[(rr*math.cos(math.pi*.5*j/steps),side+rr*math.sin(math.pi*.5*j/steps)) for j in range(steps)])
    nr=len(profiles[0])
    for profile in profiles:
        for rr,zz in profile:
            for i in range(n):
                a=2*math.pi*i/n;verts.append((rr*math.cos(a),rr*math.sin(a),zz))
    op=len(verts);verts.append((0,0,height))
    ip=len(verts);verts.append((0,0,height-t))
    for shell in [0,1]:
        base=shell*nr*n
        for j in range(nr-1):
            for i in range(n):
                a=base+j*n+i;b=base+j*n+(i+1)%n
                faces.append((a,b,b+n,a+n) if shell==0 else (a,a+n,b+n,b))
        pole=op if shell==0 else ip
        for i in range(n):
            a=base+(nr-1)*n+i;b=base+(nr-1)*n+(i+1)%n
            faces.append((a,b,pole) if shell==0 else (a,pole,b))
    for i in range(n):
        a=i;b=(i+1)%n;faces.append((a,nr*n+a,nr*n+b,b))
    g=K.mesh(name,verts,faces,K.M['glass'],parent)
    for p in g.data.polygons:p.use_smooth=True
    g['wall_thickness']=t;g['construction']='watertight hollow glass, open volume at foot'
    return g


def faceted_spire(name,parent):
    # Irregular crystalline trophy, not a real achievement badge.
    v=[]
    for radius,z,rotation in [(.075,.14,0),(.14,.34,math.pi/4),(.11,.61,0),(.012,.78,math.pi/4)]:
        for i in range(4):
            a=i*math.pi/2+rotation;v.append((radius*math.cos(a),radius*math.sin(a),z))
    f=[(3,2,1,0)]
    for j in range(3):
        for i in range(4):
            a=j*4+i;b=j*4+(i+1)%4
            f.extend([(a,b,a+4),(b,b+4,a+4)])
    f.append((12,13,14,15))
    K.mesh(name,v,f,K.M['brass'],parent)


def award(name,loc,radius,height,kind):
    a=R(name,loc,interaction='award_placeholder')
    a['content_status']='award information pending'
    # Thin solid stone foot seated on the display terrace.
    foot_radius=.265 if kind==0 else radius+.035
    K.cylinder(name+'.stone_foot',(0,0,.045),foot_radius,.09,K.M['stone'],a,72)
    K.cylinder(name+'.brass_seat',(0,0,.094),radius+.010,.009,K.M['brass'],a,72)
    K.torus(name+'.warm_ring',(0,0,.103),radius-.010,.006,K.M['light'],a)
    lid=R(name+'.glass_lid',(0,0,.098),a,'lift')
    glass_cloche(name+'.4mm_glass',radius,height,lid)
    K.torus(name+'.polished_glass_lip',(0,0,.014),radius-.002,.004,K.M['glass'],lid)
    prize=R(name+'.sculpture',(0,0,.107),a,'inspect')
    B(name+'.sculpture_base',(0,0,.044),(.177,.164,.083),'navy',prize,.008)
    B(name+'.base_inlay',(0,0,.090),(.187,.174,.009),'brass',prize,.002)
    if kind==0:
        faceted_spire('Faceted placeholder trophy',prize)
    elif kind==1:
        K.cylinder('Orbital trophy stem',(0,0,.148),.021,.11,K.M['brass'],prize,36)
        K.torus('Orbital trophy',(0,0,.39),.145,.028,K.M['brass'],prize,rotation=(math.pi/2,0,0))
        K.torus('Orbital inner edge',(0,-.006,.39),.111,.004,K.M['brass'],prize,rotation=(math.pi/2,0,0))
        for angle in [0,math.pi/2,math.pi,3*math.pi/2]:
            K.sphere('Orbital stud',(.145*math.cos(angle),-.006,.39+.145*math.sin(angle)),.012,K.M['metal'],prize)
    else:
        K.cylinder('Polyhedron stem',(0,0,.151),.018,.11,K.M['brass'],prize,32)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.135)
        p=bpy.context.object;K.attach(p,'Geometric placeholder trophy',(0,0,.295),K.M['brass'],prize)
        p.rotation_euler=(.15,.19,.3)
    return a


def awards_console():
    s=R('archive.awards_console',(-1.0,1.19,.36),interaction='cabinet')
    # The stone slab ends exactly at x=-1.85, flush beside the cabinet.
    B('Terrazzo trophy slab',(0,0,1.17),(1.70,1.30,.34),'stone',s,.016)
    B('Slab brass lower shadow line',(0,0,.995),(1.66,1.255,.012),'brass',s,.003)
    for x in [-.67,.67]:
        B('Display console solid leg',(x,.10,.505),(.13,.90,1.01),'wood_z',s,.010)
        B('Console brass foot',(x,.10,.027),(.143,.915,.045),'brass',s,.006)
    B('Console lower shelf',(0,.10,.20),(1.37,.87,.05),'wood',s,.006)
    B('Drawer aperture rear',(0,.48,.845),(1.40,.10,.24),'wood_dark',s,.005)
    B('Left interior rail',(-.685,-.02,.785),(.035,1.08,.04),'metal',s,.004)
    B('Right interior rail',(.685,-.02,.785),(.035,1.08,.04),'metal',s,.004)
    d=R('archive.scroll_drawer',(0,-.82,.70),s,'slide')
    d['slide_axis']='-Y';d['open_distance']=.19;d['max_extension']=.45
    B('Scroll drawer front',(0,0,.14),(1.37,.067,.28),'wood',d,.008)
    B('Scroll drawer bottom',(0,.36,.039),(1.32,.70,.035),'wood',d,.005)
    for x in [-.641,.641]:B('Scroll drawer side',(x,.35,.136),(.035,.70,.22),'wood_z',d,.004)
    B('Scroll drawer rear',(0,.695,.136),(1.30,.035,.22),'wood',d,.004)
    handle('Scroll drawer pull',0,-.056,.17,.32,d)
    for i in range(3):
        rr=R('archive.stored_scroll.%d'%i,(-.35+i*.33,.30,.12),d)
        tube=K.cylinder('Paper roll', (0,0,0),.054,.27,K.M['paper'],rr,48);tube.rotation_euler.y=math.pi/2
        for x in [-.14,.14]:
            K.torus('Scroll paper edge',(x,0,0),.043,.004,K.M['ivory'],rr,rotation=(0,math.pi/2,0))
        tie=K.cylinder('Roll brass band',(0,0,0),.055,.016,K.M['brass'],rr,48);tie.rotation_euler.y=math.pi/2
    for i in range(3):
        sheet_bundle('archive.lower_archive.%d'%i,(-.24,.09,.226+i*.068),.84,.52,s,['navy','ivory','leather'][i],.02*(-1)**i)
    K.panel_label('Awards pending','奖项待补充',(0,-.663,1.155),.66,.12,s)
    # Left trophy is raised above its neighbours on a real stone terrace.
    K.cylinder('Raised trophy stone terrace',(-.58,-.09,1.445),.268,.21,K.M['stone'],s,72)
    K.torus('Raised terrace fine brass line',(-.58,-.09,1.355),.263,.005,K.M['brass'],s)
    award('archive.award.01',(-1.58,1.10,1.91),.25,1.05,0)
    award('archive.award.02',(-.92,1.23,1.70),.235,.84,1)
    award('archive.award.03',(-.38,1.48,1.70),.21,.62,2)
    return s


def build():
    out=[cabinet(),screen(),awards_console()]
    return out
