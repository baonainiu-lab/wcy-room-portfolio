"""Original upholstered chair, portfolio rack and foliage for approved atelier."""
import bpy, math, random
from mathutils import Vector
import kit as K

def plant(name,loc,height=.65,radius=.18,trailing=False):
    rng=random.Random(name);p=K.root(name,loc);p['interaction']='sway'
    profile=[(0,0),(radius*.8,0),(radius,.04),(radius,height*.29),(radius*.92,height*.31),(radius*.83,height*.31),(radius*.80,height*.27),(radius*.70,.035),(0,.035)]
    K.lathe(name+'.pot',profile,K.M['ceramic'],p)
    K.cylinder(name+'.soil',(0,0,height*.27),radius*.79,.02,K.M['soil'],p)
    verts=[];faces=[]
    for branch in range(18 if trailing else 13):
        a=rng.uniform(0,math.tau); reach=rng.uniform(.5,1)*height*.5
        endz=height*rng.uniform(.64,1.10)
        if trailing and branch<10:
            endz=-height*rng.uniform(.10,.62);a=rng.uniform(-1.95,-1.20);reach=rng.uniform(.50,.60)
        points=[]
        for j in range(14):
            t=j/13; z=height*.28+(endz-height*.28)*t+math.sin(math.pi*t)*height*.20
            x=math.cos(a)*reach*t;y=math.sin(a)*reach*t
            points.append((x,y,z))
            if j<2:continue
            for side in [-1,1]:
                base=Vector((x,y,z));aa=a+side*1.10
                le=min(.15,height*rng.uniform(.09,.17));wid=le*rng.uniform(.28,.41)
                axis=Vector((math.cos(aa),math.sin(aa),rng.uniform(-.08,.36))).normalized()
                sidevec=Vector((-math.sin(aa),math.cos(aa),rng.uniform(-.25,.25))).normalized()
                start=len(verts);steps=8
                for k in range(steps+1):
                    t=k/steps;spine=base+axis*le*t+Vector((0,0,le*.085*math.sin(math.pi*t)))
                    w=wid*math.sin(math.pi*t)**.82
                    edge_drop=Vector((0,0,-le*.025*math.sin(math.pi*t)))
                    verts.extend([spine-sidevec*w+edge_drop,spine,spine+sidevec*w+edge_drop])
                for k in range(steps):
                    q=start+k*3;r=q+3
                    faces.extend([(q,r,r+1,q+1),(q+1,r+1,r+2,q+2)])
        K.tube(name+'.stem.%02d'%branch,points,height*.004,K.M['leaf'],p)
    leaves=K.mesh(name+'.leaves',verts,faces,K.M['leaf'],p);leaves.data.materials.append(K.M['leaf_light'])
    for f in leaves.data.polygons:f.material_index=rng.randint(0,1);f.use_smooth=True
    return p

def chair():
    p=K.root('atelier.chair',(1.02,-1.64,.36));p.rotation_euler.z=math.radians(-14);p['interaction']='swivel';p['pivot_note']='Vertical gas-lift axis, original posture retained.'
    K.cylinder('chair.gaslift',(0,0,.31),.06,.49,K.M['metal'],p)
    K.cylinder('chair.gaslift.sleeve',(0,0,.43),.085,.28,K.M['navy'],p)
    K.cylinder('chair.base.hub',(0,0,.14),.115,.11,K.M['metal'],p)
    for i in range(5):
        a=i*math.tau/5+.32;end=(.51*math.cos(a),.51*math.sin(a),.075)
        K.rod('chair.base.spoke',(0,0,.17),end,.035,K.M['metal'],p)
        caster=K.root('atelier.chair.caster.%d'%i,end);caster.parent=p;caster.rotation_euler.z=a
        K.rod('caster.yoke',(0,0,0),(0,0,-.013),.028,K.M['metal'],caster)
        for sx in [-.036,.036]:
            wh=K.cylinder('caster.rubber',(sx,0,-.015),.060,.038,K.M['rubber'],caster,32);wh.rotation_euler.y=math.pi/2
    K.box('chair.underseat.mechanism',(0,0,.59),(.50,.46,.12),K.M['dark'],p,.035)
    K.rod('chair.height.lever',(.12,-.1,.59),(.46,-.1,.57),.016,K.M['metal'],p)
    K.box('chair.height.handle',(.46,-.1,.57),(.10,.09,.038),K.M['rubber'],p,.016)
    seat=K.box('chair.seat.cushion',(0,.01,.747),(.89,.84,.195),K.M['leather'],p,.09)
    for m in seat.modifiers:
        if m.type=='BEVEL':m.segments=8
    for f in seat.data.polygons:f.use_smooth=True
    # Closed padded back with real lateral curvature, front and rear surfaces.
    nx,nz=28,20;verts=[];faces=[]
    for layer in [0,1]:
        for j in range(nz+1):
            t=j/nz;z=.77+t*.80
            for i in range(nx+1):
                u=i/nx*2-1;w=.425*(.96+.08*math.sin(math.pi*t))
                x=u*w;y=-.32-.17*t+.11*u*u
                # Tapered edges create a tailored upholstered outline.
                zc=z-.065*(abs(u)**7)*max(0,(t-.7)/.3)
                y+=(-.053 if layer else .053)*max(.35,(1-u*u)**.22)
                verts.append((x,y,zc))
    count=(nx+1)*(nz+1)
    for layer in [0,1]:
        for j in range(nz):
            for i in range(nx):
                a=layer*count+j*(nx+1)+i;quad=(a,a+1,a+nx+2,a+nx+1)
                faces.append(quad if layer==0 else tuple(reversed(quad)))
    boundary=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,nz+1)]+[nz*(nx+1)+i for i in range(nx-1,-1,-1)]+[j*(nx+1) for j in range(nz-1,0,-1)]
    for i,a in enumerate(boundary):b=boundary[(i+1)%len(boundary)];faces.append((a,b,b+count,a+count))
    back=K.mesh('chair.back.upholstery',verts,faces,K.M['leather'],p)
    sub=back.modifiers.new('Tailored cushion smoothing','SUBSURF');sub.levels=1;sub.render_levels=1
    for f in back.data.polygons:f.use_smooth=True
    # Stitched edge piping and short dash stitches along the visible back.
    for side in [-1,1]:
        line=[]
        for j in range(24):
            t=j/23;line.append((side*.407,-.32-.17*t+.101-.036,.80+t*.70))
        K.tube('chair.back.edge.piping',line,.004,K.M['wood_dark'],p)
        for j in range(78):
            t=j/79;z=.82+t*.66
            K.tube('chair.back.saddle.stitch',[(side*.390,-.32-.17*t+.095-.047,z),(side*.390,-.32-.17*t+.095-.047,z+.004)],.0007,K.M['ivory'],p)
        # Sweeping arms mounted into back and side frame, no detached cushions.
        controls=[Vector(v) for v in [(side*.42,-.30,.86),(side*.49,-.13,1.02),(side*.51,.13,1.025),(side*.47,.32,.98)]]
        pts=[]
        for j in range(33):
            t=j/32;u=1-t
            pts.append(tuple(u**3*controls[0]+3*u*u*t*controls[1]+3*u*t*t*controls[2]+t**3*controls[3]))
        arm=K.tube('chair.arm.leather',pts,.064,K.M['leather'],p)
        arm.data.use_fill_caps=True;arm.data.bevel_resolution=5
        for end in (pts[0],pts[-1]):K.sphere('chair.arm.padded.end',end,.064,K.M['leather'],p)
        K.rod('chair.arm.support',(side*.35,.26,.64),(side*.47,.28,.95),.022,K.M['metal'],p)
    for yy in [-.20,.18]:
        line=[(-.38,yy,.839),(0,yy,.847),(.38,yy,.839)];K.tube('chair.seat.seam',line,.0022,K.M['wood_dark'],p)
    return p

def portfolio_rack():
    p=K.root('atelier.portfolio.rack',(-1.35,-1.13,.36));p['interaction']='browse_archive';p.rotation_euler.z=-.13
    for xx in [-.30,.30]:
        K.rod('folio.stand.leg',(xx,-.22,0),(xx,.16,1.00),.018,K.M['brass'],p)
        K.rod('folio.stand.brace',(xx,.25,0),(xx,.10,.93),.016,K.M['brass'],p)
    for zz,yy in [(.045,-.20),(.065,.23),(.36,.06),(.96,.145)]:K.rod('folio.crossbar',(-.32,yy,zz),(.32,yy,zz),.015,K.M['brass'],p)
    K.box('folio.support.tray',(-.05,.07,.366),(.62,.24,.025),K.M['brass'],p,.006)
    K.box('folio.support.front_lip',(-.05,-.05,.394),(.62,.018,.042),K.M['brass'],p,.004)
    for i in range(3):
        b=K.root('atelier.portfolio.book.%d'%i,(-.10+i*.048,.078+i*.043,.66));b.parent=p;b.rotation_euler=(math.radians(-13),0,math.radians(-8+i*7))
        K.box('folio.leather.cover',(0,0,0),(.43,.053,.56),K.M['leather'] if i==0 else K.M['wood_dark'],b,.008)
        K.box('folio.paper.block',(.007,-.001,0),(.405,.040,.53),K.M['paper'],b,.004)
        for yy in [-.030,.030]:K.box('folio.board',(0,yy,0),(.44,.005,.56),K.M['leather'] if i==0 else K.M['wood_dark'],b,.002)
        K.text('folio.generic.title','ARCHIVE',(0,-.034,.15),.025,K.M['brass'],b)
    return p

def floor_art():
    p=K.root('atelier.floor.art',(-3.00,.691,.812));p.rotation_euler=(math.radians(-10),0,0)
    K.box('floor.art.frame',(0,0,0),(.61,.045,.91),K.M['wood_dark'],p,.008)
    K.box('floor.art.mount',(0,-.026,0),(.55,.015,.85),K.M['paper'],p,.001)
    # Original three-dimensional abstract folded-paper shapes, not a borrowed poster.
    K.mesh('floor.art.original',[(-.19,-.037,-.32),(.19,-.037,-.32),(-.09,-.037,.28),(.13,-.042,.12),(-.04,-.050,-.04)],[(0,1,4),(1,3,4),(3,2,4),(2,0,4)],K.M['ivory'],p)
    K.tube('floor.art.graphic',[(-.18,-.052,-.25),(.14,-.052,-.13),(-.06,-.052,.27)],.006,K.M['ink'],p)

def build():
    chair();portfolio_rack();floor_art()
    plant('atelier.plant.foreground',(-.68,-1.30,.36),.72,.20)
    plant('atelier.plant.cabinet',(-3.12,1.04,3.41),.66,.19,True)
