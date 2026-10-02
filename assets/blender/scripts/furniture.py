"""Sculptural furniture for the approved orbital studio concept.

Standalone Blender build module. All dimensions are meters; components remain
separate and are parented to stable asset roots for interaction/export.
Only common.M is imported so this module does not alter shared scene state.
"""
import bpy
import math
from mathutils import Vector
from common import M

TAU = math.tau
COL = None


def _link(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    COL.objects.link(obj)
    return obj


def _root(name, asset_id, location=(0, 0, 0), angle=0):
    obj = bpy.data.objects.new('F_' + name, None)
    COL.objects.link(obj)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .15
    obj.location = location
    obj.rotation_euler.z = angle
    obj['asset_id'] = asset_id
    obj['interactive'] = True
    obj['design_reference'] = 'Approved orbital creator studio V2'
    return obj


def _material(key):
    return M[key] if isinstance(key, str) else key


def _mesh(name, verts, faces, mat, parent=None, uv=None, bevel=0, sub=0):
    me = bpy.data.meshes.new('F_' + name + '_mesh')
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new('F_' + name, me)
    COL.objects.link(ob)
    if parent:
        ob.parent = parent
    if mat:
        me.materials.append(_material(mat))
    for poly in me.polygons:
        poly.use_smooth = len(poly.vertices) <= 4
    layer = me.uv_layers.new(name='UVMap')
    if uv is None:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        dx = max(max(xs) - min(xs), .001)
        dy = max(max(ys) - min(ys), .001)
        uv = [((v[0] - min(xs))/dx, (v[1] - min(ys))/dy) for v in verts]
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uv[me.loops[li].vertex_index]
    if bevel:
        mod = ob.modifiers.new('Soft manufactured edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.harden_normals = True
    if sub:
        mod = ob.modifiers.new('Surface refinement', 'SUBSURF')
        mod.levels = sub
        mod.render_levels = sub
    return ob


def _solidify(ob, thickness):
    mod = ob.modifiers.new('Shell thickness', 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = -1
    mod.use_even_offset = True


def _cylinder(name, center, radius, depth, mat, parent=None, vertices=80, scale_y=1, bevel=.01):
    verts=[]
    uv=[]
    for z in [-depth/2, depth/2]:
        for i in range(vertices):
            t=TAU*i/vertices
            verts.append((center[0]+radius*math.cos(t), center[1]+radius*scale_y*math.sin(t), center[2]+z))
            uv.append((.5+.5*math.cos(t), .5+.5*math.sin(t)))
    faces=[tuple(reversed(range(vertices))),tuple(range(vertices,2*vertices))]
    for i in range(vertices):
        j=(i+1)%vertices
        faces.append((i,j,j+vertices,i+vertices))
    return _mesh(name,verts,faces,mat,parent,uv,bevel)


def _tube(name, points, radius, mat, parent=None, sides=12, closed=False):
    # Parallel transport approximation; local frame remains continuous on these
    # deliberately gently curved paths. Duplicate end vertices make UVs explicit.
    verts=[]; faces=[]; uvs=[]
    n=len(points)
    for i,p in enumerate(points):
        p=Vector(p)
        if closed:
            tangent=(Vector(points[(i+1)%n])-Vector(points[(i-1)%n])).normalized()
        elif i == 0:
            tangent=(Vector(points[1])-p).normalized()
        elif i == n-1:
            tangent=(p-Vector(points[i-1])).normalized()
        else:
            tangent=(Vector(points[i+1])-Vector(points[i-1])).normalized()
        guide=Vector((0,0,1))
        if abs(tangent.dot(guide)) > .95:
            guide=Vector((0,1,0))
        normal=tangent.cross(guide).normalized()
        binormal=tangent.cross(normal).normalized()
        for j in range(sides):
            t=TAU*j/sides
            q=p+radius*(normal*math.cos(t)+binormal*math.sin(t))
            verts.append(tuple(q)); uvs.append((i/max(n-1,1),j/sides))
    for i in range(n if closed else n-1):
        ni=(i+1)%n
        for j in range(sides):
            nj=(j+1)%sides
            faces.append((i*sides+j,ni*sides+j,ni*sides+nj,i*sides+nj))
    if not closed:
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple((n-1)*sides+j for j in range(sides)))
    return _mesh(name,verts,faces,mat,parent,uvs)


def _ellipse_tube(name, center, rx, ry, tube_r, mat, parent, n=160):
    pts=[(center[0]+rx*math.cos(TAU*i/n),center[1]+ry*math.sin(TAU*i/n),center[2]) for i in range(n)]
    return _tube(name,pts,tube_r,mat,parent,closed=True)


def _superellipsoid(name, center, scale, mat, parent=None, power=.65, rotation=(0,0,0), nu=72, nv=36):
    def spow(a,p): return math.copysign(abs(a)**p,a)
    verts=[];uv=[];faces=[]
    # Avoid degenerate poles while capping with nearly point-sized rings.
    for j in range(nv+1):
        ph=-math.pi/2+.0001+(math.pi-.0002)*j/nv
        cp=spow(math.cos(ph),power); sp=spow(math.sin(ph),power)
        for i in range(nu+1):
            th=TAU*i/nu
            verts.append((scale[0]*cp*spow(math.cos(th),power),scale[1]*cp*spow(math.sin(th),power),scale[2]*sp))
            uv.append((i/nu,j/nv))
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i
            faces.append((a,a+1,a+nu+2,a+nu+1))
    ob=_mesh(name,verts,faces,mat,parent,uv)
    ob.location=center;ob.rotation_euler=rotation
    return ob


def _spline_closed(control, steps=12):
    out=[];n=len(control)
    for i in range(n):
        a=Vector(control[(i-1)%n]);b=Vector(control[i]);c=Vector(control[(i+1)%n]);d=Vector(control[(i+2)%n])
        for k in range(steps):
            t=k/steps
            p=.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
            out.append(tuple(p))
    return out


def _outline_slab(name, outline, zlow, zhigh, mat, parent=None, bevel=.012):
    n=len(outline)
    verts=[(p[0],p[1],z) for z in (zlow,zhigh) for p in outline]
    # Outline supplied counterclockwise.
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    return _mesh(name,verts,faces,mat,parent,bevel=bevel)


def _ribbon(name, centerline, width, thickness, mat, parent, side=(1,0,0)):
    # A continuously curved rectangular metal ribbon, capped and beveled.
    s=Vector(side).normalized();verts=[];faces=[]
    for i,p in enumerate(centerline):
        p=Vector(p)
        tangent=Vector(centerline[min(i+1,len(centerline)-1)])-Vector(centerline[max(i-1,0)])
        tangent.normalize()
        n=s.cross(tangent).normalized()
        for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]:
            verts.append(tuple(p+s*a*width/2+n*b*thickness/2))
    for i in range(len(centerline)-1):
        for k in range(4):faces.append((i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4,(i+1)*4+k))
    faces.extend([(3,2,1,0),tuple((len(centerline)-1)*4+k for k in range(4))])
    return _mesh(name,verts,faces,mat,parent,bevel=min(thickness*.2,.012))


def _annulus(name, rx, ry, width, z, thickness, mat, parent):
    verts=[];faces=[];n=144
    for zz in [z-thickness/2,z+thickness/2]:
        for rxx,ryy in [(rx,ry),(rx-width,ry-width)]:
            for i in range(n):
                t=TAU*i/n;verts.append((rxx*math.cos(t),ryy*math.sin(t),zz))
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,j,2*n+j,2*n+i),(n+i,3*n+i,3*n+j,n+j),(2*n+i,2*n+j,3*n+j,3*n+i),(i,n+i,n+j,j)])
    return _mesh(name,verts,faces,mat,parent,bevel=.012)


def _tone_material(name, source, color, roughness=None):
    mat=bpy.data.materials.get(name)
    if not mat:
        mat=_material(source).copy();mat.name=name
        if mat.use_nodes:
            bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bsdf:
                # Linked procedural color survives for upholstery, seam gets
                # its own small-scale surface detail but a reliable dark tint.
                for link in list(bsdf.inputs['Base Color'].links):mat.node_tree.links.remove(link)
                bsdf.inputs['Base Color'].default_value=(*color,1)
                if roughness is not None:bsdf.inputs['Roughness'].default_value=roughness
    return mat


def _desk():
    root=_root('Cantilever_Desk','furniture.desk')
    # An asymmetrical river-stone plan follows the panoramic workspace.
    controls=[(-4.32,1.25),(-4.38,1.68),(-4.20,2.24),(-3.55,2.40),(-2.65,2.34),(-1.55,2.28),(-.72,2.16),(-.47,1.86),(-.53,1.53),(-.87,1.27),(-1.70,1.19),(-2.65,1.07),(-3.52,1.01),(-4.08,1.07)]
    outline=_spline_closed(list(reversed(controls)),10)
    _outline_slab('Desk_Titanium_Edge',outline,1.535,1.637,'titanium',root,.025)
    # Inset dark tactile top, retaining an uninterrupted polished perimeter.
    centroid=Vector((-2.42,1.71))
    inner=[]
    for p in outline:
        q=Vector(p); v=q-centroid
        q=centroid+v*(1-.042/max(v.length,.1));inner.append(tuple(q))
    _outline_slab('Desk_Graphite_Surface',inner,1.631,1.652,'graphite',root,.011)
    _tube('Desk_Underlit_Front',[(*p,1.573) for p in outline],.0055,'cool_light',root,sides=8,closed=True)
    # Broad slanted blade, softened in two axes, reproduces the single
    # cantilever foot instead of substituting rectangular table legs.
    line=[]
    for i in range(36):
        t=i/35
        line.append((-4.03+.59*t,1.61+.02*math.sin(math.pi*t),.245+1.295*t))
    _ribbon('Desk_Swept_Support',line,.53,.235,'titanium',root,side=(0,1,0))
    # Front edge illumination is narrow enough to read as an inset light seam.
    pts=[(-4.092+.59*(i/35),1.329,.25+1.285*(i/35)) for i in range(36)]
    _tube('Desk_Support_Light_Seam',pts,.008,'cool_light',root,sides=10)
    _superellipsoid('Desk_Foot_Damper',(-4.00,1.61,.209),(.25,.32,.028),'black',root,power=.4)
    # A discreet rear stabilizing spar remains behind the work surface.
    _ribbon('Desk_Rear_Mount',[(-1.08,2.20,1.47),(-1.07,2.38,1.43),(-1.04,2.58,1.37),(-1.04,2.65,1.32)],.18,.065,'graphite',root)
    return root


def _chair_profile(t):
    # One C2-continuous seat-to-back sweep; the narrow shoulder and reclined
    # upper silhouette replace the earlier broad, near-planar white slab.
    knots=[(.54,1.025,.44),(.29,.998,.46),(-.06,1.02,.46),
           (-.29,1.12,.43),(-.38,1.38,.395),(-.43,1.72,.368),
           (-.53,2.04,.344),(-.61,2.31,.305)]
    u=max(0,min(.999999,t))*(len(knots)-1)
    i=int(u);q=u-i
    a=Vector(knots[max(0,i-1)]);b=Vector(knots[i]);c=Vector(knots[min(len(knots)-1,i+1)]);d=Vector(knots[min(len(knots)-1,i+2)])
    v=.5*(2*b+(-a+c)*q+(2*a-5*b+4*c-d)*q*q+(-a+3*b-3*c+d)*q*q*q)
    return v.x,v.y,v.z


def _chair_surface(name, root, mat, inset=0, offset=0, t0=0, t1=1, solid=.024):
    nu=36;nv=68;verts=[];faces=[];uv=[]
    for j in range(nv+1):
        t=t0+(t1-t0)*j/nv
        y,z,width=_chair_profile(t)
        ya,za,_=_chair_profile(max(t-.001,0));yb,zb,_=_chair_profile(min(t+.001,1))
        normal=Vector((0,zb-za,-(yb-ya))).normalized()
        for i in range(nu+1):
            u=-1+2*i/nu
            side_lift=.19*(abs(u)**3)*(1-.68*max(0,(t-.40)/.60))
            # Rolled white wings cradle the seat, tapering into the back.
            xx=u*(width-inset)
            yy=y+.13*abs(u)**2*max(0,(t-.34)/.66)
            zz=z+side_lift-.055*(abs(u)**3)*max(0,(t-.84)/.16)
            p=Vector((xx,yy,zz))+normal*offset
            verts.append(tuple(p));uv.append((i/nu,j/nv))
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i;faces.append((a,a+nu+1,a+nu+2,a+1))
    ob=_mesh(name,verts,faces,mat,root,uv)
    if solid:_solidify(ob,solid)
    return ob


def _chair():
    root=_root('Sculptural_Work_Chair','furniture.work_chair',(-2.25,.25,0))
    _cylinder('Chair_Floating_Base',(0,0,.255),.395,.115,'titanium',root,scale_y=.91,bevel=.025)
    _cylinder('Chair_Base_Shadow_Ring',(0,0,.199),.346,.023,'black',root,scale_y=.91,bevel=.008)
    _ellipse_tube('Chair_Base_Polish',(0,0,.296),.356,.323,.013,'titanium',root)
    # Vase-shaped polished pedestal, a lathed spline instead of a thin rod.
    profile=[(.12,.305),(.14,.33),(.15,.37),(.125,.42),(.087,.48),(.072,.60),(.083,.73),(.13,.79),(.17,.82)]
    verts=[];faces=[];uv=[];ns=88
    for j,(r,z) in enumerate(profile):
        for i in range(ns+1):
            a=TAU*i/ns;verts.append((r*math.cos(a),r*math.sin(a),z));uv.append((i/ns,j/(len(profile)-1)))
    for j in range(len(profile)-1):
        for i in range(ns):
            a=j*(ns+1)+i;faces.append((a,a+1,a+ns+2,a+ns+1))
    _mesh('Chair_Sculpted_Pedestal',verts,faces,'titanium',root,uv,sub=1)
    _superellipsoid('Chair_Underside_Mechanism',(0,-.04,.89),(.32,.32,.105),'black',root,power=.6)
    _chair_surface('Chair_Continuous_Ceramic_Shell',root,'ceramic',offset=-.020,solid=.028)
    _chair_surface('Chair_Contoured_Back_Upholstery',root,'charcoal_fabric',inset=.033,offset=.045,t0=.40,t1=.986,solid=.033)
    # Independently padded seat emphasizes the tailored shell profile.
    _superellipsoid('Chair_Seat_Cushion',(0,.125,1.095),(.409,.386,.075),'charcoal_fabric',root,power=.58)
    seam=_tone_material('F_Chair_Seam','charcoal_fabric',(.036,.040,.047),.78)
    for side in [-1,1]:
        pts=[]
        for j in range(75):
            t=j/74;y,z,w=_chair_profile(t)
            pts.append((side*(w-.014),y+.116*max(0,(t-.34)/.66),z+.177*(1-.68*max(0,(t-.40)/.60))-.049*max(0,(t-.84)/.16)))
        _tube('Chair_Shell_Edge_'+str(side),pts,.0045,'titanium',root,sides=10)
        pts=[]
        for j in range(65):
            t=.425+.55*j/64;y,z,w=_chair_profile(t)
            pts.append((side*(w-.066),y+.118,z+.11*(1-.48*t)))
        _tube('Chair_Tailored_Back_Welt_'+str(side),pts,.0048,seam,root,sides=8)
    # A horizontal lumbar division follows the cushion's actual curvature.
    y,z,w=_chair_profile(.59)
    pts=[((-.88+1.76*i/48)*(w-.05),y+.059,z+.072+.03*((-.88+1.76*i/48)**2)) for i in range(49)]
    _tube('Chair_Lumbar_Stitch',pts,.0038,seam,root,sides=8)
    return root


def _lounge_section(theta, v):
    # Upholstery is a single closed bean/boat surface, not a tube on top of a
    # separate disk. The front edge is a low continuous rolled lip; the rear
    # rises naturally into a shallow, asymmetric crescent back.
    sn=math.sin(theta)
    # The forward third is completely open: no raised rim above the seat.
    activation=max(0,min(1,(sn+.40)/1.40))
    rear=(activation*activation*(3-2*activation))**.68
    h=.642+.730*rear+.092*math.cos(theta)*rear*(1-.55*rear)
    # Long left sweep and slightly shorter right shoulder break torus symmetry.
    rx=1.17*(1-.105*math.cos(theta))
    yy=.685*sn+.055*math.sin(2*theta)
    # Cross-sectional control points travel from seat center over the rim,
    # around the upholstered outside, then back underneath the seat.
    controls=[(.00015,.665),(.25,.665),(.48,.663),(.64,.662+.072*rear),
              (.76,.660+.30*rear),(.85,h-.020),(.923,h),
              (.981,h-.037),(1.012,h-.105),(1.005,.487+.30*rear),
              (.960,.448+.075*rear),(.830,.432),(.55,.449),(.20,.470),(.00015,.474)]
    q=max(0,min(.999999,v))*(len(controls)-1);i=int(q);t=q-i
    a=Vector(controls[max(i-1,0)]);b=Vector(controls[i]);c=Vector(controls[min(i+1,len(controls)-1)]);d=Vector(controls[min(i+2,len(controls)-1)])
    p=.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
    r,z=p
    # Very subtle cushion compression where the person sits; unlike the
    # earlier exaggerated separate oval cushion there is no raised center.
    # Fan the upper back outward. Its crown is displaced behind the seat,
    # creating a reclined crescent sheet instead of a vertical bathtub wall.
    rise=max(0,min(1,(z-.69)/.66))
    flare=.13*rear*rise
    x=rx*math.cos(theta)*(r+flare*.42)
    y=yy*r-.035*(1-r)+.215*rear*rise
    z-=.008*math.exp(-((r-.46)/.27)**2)
    return (x,y,z)


def _lounge():
    root=_root('Crescent_Orange_Lounge','furniture.lounge',(2.05,-1.50,0),math.radians(-34))
    _annulus('Lounge_Polished_Cantilever_Foot',1.035,.635,.09,.255,.067,'titanium',root)
    _annulus('Lounge_Foot_Shadow_Pad',.966,.577,.060,.206,.020,'black',root)
    # Slender swept rear risers leave the broad front lip floating visibly.
    for side in [-1,1]:
        pts=[]
        for i in range(58):
            t=i/57
            pts.append((side*(.846+.025*math.sin(math.pi*t)),.12+.38*t,.274+.325*t*t*(3-2*t)))
        _ribbon('Lounge_Cantilever_Riser_'+str(side),pts,.155,.048,'titanium',root)
    _superellipsoid('Lounge_Underseat_Carrier',(0,-.015,.445),(.83,.48,.043),'graphite',root,power=.64)
    verts=[];faces=[];uv=[];nu=176;nv=98
    for j in range(nv+1):
        v=j/nv
        for i in range(nu+1):
            theta=TAU*i/nu
            verts.append(_lounge_section(theta,v));uv.append((i/nu,v))
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i;faces.append((a,a+nu+1,a+nu+2,a+1))
    faces.append(tuple(range(nu+1)))
    faces.append(tuple(nv*(nu+1)+i for i in reversed(range(nu+1))))
    body=_mesh('Lounge_One_Piece_Sculpted_Upholstery',verts,faces,'orange_fabric',root,uv)
    body['construction']='Continuous low asymmetrical crescent, integrated seat and back'
    seam=_tone_material('F_Orange_Upholstery_Stitch','orange_fabric',(.22,.041,.008),.83)
    # Only the back has a short contour seam. The open front has no inner
    # ring or piping, preserving its continuous flat upholstered seat edge.
    pts=[]
    for i in range(116):
        th=math.radians(-3+186*i/115)
        p=Vector(_lounge_section(th,4.7/14));p.z+=.0020;pts.append(tuple(p))
    _tube('Lounge_Back_Stitched_Contour',pts,.0019,seam,root,sides=6,closed=False)
    # Radial tailoring is confined to the back/outer shell: front seat remains
    # a visually calm, unbroken surface with no truncated bolster endpoints.
    for idx,deg in enumerate([3,31,60,89,117,146,176]):
        pts=[]
        for j in range(46):
            v=(4.85+5.65*j/45)/14
            p=Vector(_lounge_section(math.radians(deg),v));p.z+=.0016;pts.append(tuple(p))
        _tube('Lounge_Back_Tailored_Seam_%02d'%idx,pts,.0019,seam,root,sides=6)
    # Broad tilted cushion rests inside the new back rather than standing
    # vertically like a peg in the seat.
    pillow=_superellipsoid('Lounge_Charcoal_Pillow',(.28,.315,.864),(.330,.093,.258),'charcoal_fabric',root,power=.56,rotation=(math.radians(31),math.radians(-9),math.radians(-21)))
    edge=[]
    for i in range(140):
        a=TAU*i/140
        xx=.323*math.copysign(abs(math.cos(a))**.57,math.cos(a))
        zz=.25*math.copysign(abs(math.sin(a))**.57,math.sin(a))
        edge.append((xx,-.078,zz))
    _tube('Lounge_Pillow_Welt',edge,.0033,'graphite',pillow,closed=True,sides=8)
    return root


def _coffee():
    root=_root('Smoked_Glass_Coffee_Table','furniture.coffee_table',(.70,-.95,0))
    _cylinder('Coffee_Low_Oval_Base',(0,0,.276),.43,.086,'titanium',root,scale_y=.74,bevel=.023)
    _cylinder('Coffee_Recessed_Base_Pad',(0,0,.216),.363,.025,'black',root,scale_y=.73,bevel=.007)
    # Two inverse curved ribbons form a sculptural double wishbone pedestal.
    for side in [-1,1]:
        pts=[]
        for i in range(48):
            t=i/47
            pts.append((side*(.27-.17*math.sin(math.pi*t)),.055*math.sin(TAU*t),.31+.49*t))
        _ribbon('Coffee_Twisted_Metal_Pedestal_'+str(side),pts,.20,.065,'titanium',root,side=(0,1,0))
    _cylinder('Coffee_Under_Glass_Carrier',(0,0,.821),.565,.028,'graphite',root,scale_y=.64,bevel=.009)
    _cylinder('Coffee_Smoked_Glass_Top',(0,0,.863),.76,.047,'glass',root,scale_y=.67,bevel=.014)
    # Smoked backing ensures the glass reads dark in a brightly lit room.
    _cylinder('Coffee_Graphite_Underlay',(0,0,.838),.733,.008,'graphite',root,scale_y=.667,bevel=.003)
    _ellipse_tube('Coffee_Thin_Chrome_Edge',(0,0,.860),.754,.505,.011,'titanium',root)
    return root


def _rug():
    root=_root('Charcoal_Inlaid_Rug','furniture.rug',(1.25,-1.20,0))
    shape=[];n=192;power=.64
    for i in range(n):
        t=TAU*i/n
        shape.append((2.15*math.copysign(abs(math.cos(t))**power,math.cos(t)),1.85*math.copysign(abs(math.sin(t))**power,math.sin(t))))
    _outline_slab('Rug_Rounded_Textile_Slab',shape,.185,.212,'rug',root,.008)
    line_mat=_tone_material('F_Rug_Embossed_Grooves','rug',(.105,.119,.132),.91)
    # Three fine pressed concentric ellipses are intentionally low contrast.
    for k,scale in enumerate([.70,.79,.88]):
        pts=[(2.15*scale*math.cos(TAU*i/192),1.85*scale*math.sin(TAU*i/192),.213) for i in range(192)]
        _tube('Rug_Concentric_Pressed_Seam_%d'%k,pts,.0033,line_mat,root,sides=6,closed=True)
    edge=[(x*.991,y*.991,.213) for x,y in shape]
    _tube('Rug_Tailored_Outer_Binding',edge,.0042,'rug',root,sides=6,closed=True)
    return root


def build():
    global COL
    COL=bpy.data.collections.get('FURNITURE')
    if COL is None:
        COL=bpy.data.collections.new('FURNITURE')
        bpy.context.scene.collection.children.link(COL)
    # Idempotence is confined to this module's own objects and collection.
    for ob in list(COL.objects):
        if ob.name.startswith('F_'):
            bpy.data.objects.remove(ob,do_unlink=True)
    roots=[_desk(),_chair(),_lounge(),_coffee(),_rug()]
    for ob in COL.objects:
        if ob.type=='MESH':
            ob['component'] = ob.name
            ob['uv_ready'] = True
    return {'collection':'FURNITURE','assets':[ob['asset_id'] for ob in roots], 'objects':len(COL.objects),'mesh_count':sum(ob.type=='MESH' for ob in COL.objects)}
