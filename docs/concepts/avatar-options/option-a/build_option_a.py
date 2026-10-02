"""Approval-only original human art-toy. No website integration."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
asset_objects=[]
def linear(hex_string):
    v = [int(hex_string[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in v)


def material(name, color, roughness=.35, metal=0, emission=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    c = (*linear(color), 1)
    bs.inputs['Base Color'].default_value = c
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Metallic'].default_value = metal
    if emission:
        bs.inputs['Emission Color'].default_value = c
        bs.inputs['Emission Strength'].default_value = emission
    m.diffuse_color = c
    return m


ceramic = material('CeramicShell', 'EEE7D8', .29, .08)
graphite = material('GraphiteJoint', '384149', .37, .35)
orange = material('SignalOrange', 'F5803D', .29, .12)
glass = material('ObsidianGlass', '172A30', .19, .12)
led = material('WarmLED', 'FFE1A8', .26, .05, .8)
metal = material('BrushedTitanium', '89918F', .3, .75)
mint = material('ScreenMint', '9EDAD2', .27, .05, .35)


def register(obj, name, parent=None):
    obj.name = name
    if parent:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
    asset_objects.append(obj)
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.location = loc
    bpy.context.view_layer.update()
    return register(obj, name, parent)


def finish(obj, name, mat, parent, bevel=None):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Manufactured edge radius', 'BEVEL')
        mod.width, mod.segments = bevel, 3 if bevel >= .05 else 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    mod = obj.modifiers.new('Weighted face normals', 'WEIGHTED_NORMAL')
    mod.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(mat)
    bpy.context.view_layer.update()
    register(obj, name, parent)
    obj.select_set(False)
    return obj


def box(name, loc, size, mat, radius=.02, parent=None, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.dimensions = size
    if rot:
        o.rotation_euler = rot
    return finish(o, name, mat, parent, radius)


def sphere(name, loc, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1, location=loc)
    o = bpy.context.object
    o.scale = scale
    return finish(o, name, mat, parent)


def cylinder(name, loc, radius, depth, mat, parent=None, axis='Z', vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    if axis == 'X':
        o.rotation_euler[1] = math.pi/2
    elif axis == 'Y':
        o.rotation_euler[0] = math.pi/2
    return finish(o, name, mat, parent, .007 if radius > .03 else .002)


def rod(name, start, end, radius, mat, parent=None):
    a, b = Vector(start), Vector(end)
    o = cylinder(name, (a+b)/2, radius, (b-a).length, mat, parent)
    # Existing parenting preserves location; rotate in world-space before parent conversion.
    rotation = (b-a).to_track_quat('Z', 'Y').to_matrix().to_4x4()
    rotation.translation = (a+b)/2
    o.matrix_world = rotation
    return o


def pill(name, loc, width, depth, height, mat, parent):
    """True rounded front silhouette, independent of the thin extrusion depth."""
    radius = width/2-.0001
    w, h = width/2, height/2
    profile = []
    for cx, cz, start in ((w-radius, h-radius, 0), (-w+radius, h-radius, 90),
                         (-w+radius, -h+radius, 180), (w-radius, -h+radius, 270)):
        for i in range(7):
            a = math.radians(start+i*90/6)
            profile.append((cx+radius*math.cos(a), cz+radius*math.sin(a)))
    n = len(profile)
    vertices = [(x, y, z) for y in (-depth/2, depth/2) for x, z in profile]
    faces = [tuple(range(n)), tuple(reversed(range(n, n*2)))]
    faces += [(i, n+i, n+(i+1)%n, (i+1)%n) for i in range(n)]
    mesh = bpy.data.meshes.new(name+'Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    o.location = loc
    return finish(o, name, mat, parent, .002)


def curve(name, pts, radius, mat, parent=None):
    c = bpy.data.curves.new(name, 'CURVE')
    c.dimensions = '3D'
    c.resolution_u = 1
    c.bevel_depth = radius
    c.bevel_resolution = 2
    c.use_fill_caps = True
    s = c.splines.new('POLY')
    s.points.add(len(pts)-1)
    for p, co in zip(s.points, pts):
        p.co = (*co, 1)
    o = bpy.data.objects.new(name, c)
    scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    o = bpy.context.object
    for poly in o.data.polygons:
        poly.use_smooth = True
    o.data.materials.append(mat)
    register(o, name, parent)
    o.select_set(False)
    return o


# Sculpture-specific smooth lofts, folded panels, and tapered hair ribbons.
def loft(name, rings, mat, parent=None, segments=32):
    verts=[]
    for x,y,z,rx,ry in rings:
        for j in range(segments):
            a=2*math.pi*j/segments
            verts.append((x+rx*math.cos(a),y+ry*math.sin(a),z))
    faces=[tuple(reversed(range(segments)))]
    for i in range(len(rings)-1):
        for j in range(segments):
            n=(j+1)%segments;a=i*segments;b=(i+1)*segments
            faces.append((a+j,a+n,b+n,b+j))
    faces.append(tuple(range((len(rings)-1)*segments,len(rings)*segments)))
    mesh=bpy.data.meshes.new(name+'Geometry');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o)
    o.data.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    sub=o.modifiers.new('Sculpted surface','SUBSURF');sub.levels=2
    bpy.context.view_layer.objects.active=o;o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=sub.name);o.select_set(False)
    register(o,name,parent);return o


def panel(name, verts, mat, thickness=.015, bevel=.007, parent=None):
    mesh=bpy.data.meshes.new(name+'Geometry');mesh.from_pydata(verts,[],[tuple(range(len(verts)))]);mesh.update()
    o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active=o;o.select_set(True)
    mod=o.modifiers.new('Fold thickness','SOLIDIFY');mod.thickness=thickness
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(o,name,mat,parent,bevel)


def hair_lock(name, control, widths, mat, parent):
    # Catmull-Rom centerline with an oval cross-section yields controlled sculptural locks.
    pts=[Vector(p) for p in control];centers=[];radii=[]
    for i in range(len(pts)-1):
        a=pts[max(0,i-1)];b=pts[i];c=pts[i+1];d=pts[min(len(pts)-1,i+2)]
        for k in range(8):
            t=k/8
            centers.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
            radii.append(widths[i]*(1-t)+widths[i+1]*t)
    centers.append(pts[-1]);radii.append(widths[-1]);verts=[];sides=12
    for i,c in enumerate(centers):
        tangent=(centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]).normalized()
        across=Vector((0,1,0)).cross(tangent).normalized()
        for j in range(sides):
            a=2*math.pi*j/sides
            v=c+across*math.cos(a)*radii[i]+Vector((0,1,0))*math.sin(a)*radii[i]*.47
            verts.append(tuple(v))
    faces=[tuple(reversed(range(sides)))]
    for i in range(len(centers)-1):
        for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    faces.append(tuple(range((len(centers)-1)*sides,len(centers)*sides)))
    mesh=bpy.data.meshes.new(name+'Geometry');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o);o.data.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    register(o,name,parent);return o


ivory=material('Ivory folded canvas','E9DFCC',.47,.03)
charcoal=material('Charcoal technical knit','30343A',.59)
skin=material('Warm porcelain skin','D6AA8A',.46)
skin_shadow=material('Inset clay detail','AD7A60',.53)
hair=material('Ink sculpted hair','171B20',.31,.04)
hair_edge=material('Ink lock highlight','242931',.34,.02)
terra=material('Terracotta folded leather','B45C43',.42,.03)
white=material('Eye porcelain','E8E1D7',.32)
pupil=material('Eye and brow ink','25262A',.27)
brass=material('Satin pale brass','B79B74',.35,.55)
sole=material('Warm graphite rubber','464643',.61)
root=empty('FoldCreator_ApprovalOnly')
root['status']='Appearance concept only, not approved, not integrated into website'
head=empty('Head',(0,0,1.49),root)
body=empty('Body',(0,0,.9),root)

# Four-head-tall adult art-toy face: tapered jaw, quiet expression, inset eyes.
face=loft('PorcelainFace',[(0,.009,1.238,.070,.083),(0,0,1.250,.115,.131),
    (0,0,1.287,.175,.168),(0,0,1.390,.224,.191),(0,0,1.510,.234,.190),
    (0,.003,1.622,.208,.165),(0,.015,1.691,.142,.121),(0,.025,1.724,.045,.05)],skin,head,48)
for sign in (-1,1):
    sphere('Ear'+str(sign),(sign*.220,.013,1.449),(.039,.035,.062),skin,head)
    sphere('EarInset'+str(sign),(sign*.241,-.009,1.446),(.017,.016,.035),skin_shadow,head)
    x=sign*.086
    curve('EyeRim'+str(sign),[(x+.045*math.cos(2*math.pi*k/32),-.183,1.512+.027*math.sin(2*math.pi*k/32)) for k in range(33)],.003,skin_shadow,head)
    sphere('EyeWhite'+str(sign),(x,-.181,1.512),(.043,.009,.025),white,head)
    sphere('Pupil'+str(sign),(x+.003,-.192,1.511),(.016,.006,.021),pupil,head)
    sphere('EyeCatchlight'+str(sign),(x-.003,-.199,1.520),(.005,.003,.006),white,head)
    curve('UpperLid'+str(sign),[(x-.043,-.190,1.519),(x-.025,-.199,1.539),(x+.010,-.200,1.544),(x+.040,-.190,1.532)],.0045,skin_shadow,head)
hair_lock('BrowLeft',[(-.134,-.180,1.570),(-.099,-.189,1.579),(-.055,-.186,1.574)],[.009,.010,.005],hair,head)
hair_lock('BrowRight',[(.047,-.187,1.582),(.080,-.192,1.590),(.132,-.179,1.584)],[.004,.010,.007],hair,head)
sphere('SculptedNose',(0,-.187,1.447),(.027,.040,.039),skin,head)
curve('QuietSmirk',[(-.061,-.184,1.366),(-.029,-.191,1.354),(.010,-.193,1.355),(.055,-.183,1.373)],.0044,skin_shadow,head)
curve('SmirkCorner',[(.050,-.183,1.371),(.058,-.180,1.379)],.003,skin_shadow,head)

# Sculpted cap follows a controlled asymmetric hairline. Five broad locks make the silhouette.
verts=[(0,.012,1.794)];faces=[];rings=18;steps=48
for i in range(1,rings+1):
    for j in range(steps):
        a=2*math.pi*j/steps
        hairline=1.515-.105*math.sin(a)
        theta=math.acos((hairline-1.505)/.289)*i/rings
        verts.append((.248*math.sin(theta)*math.cos(a),.012+.206*math.sin(theta)*math.sin(a),1.505+.289*math.cos(theta)))
for j in range(steps):faces.append((0,1+j,1+(j+1)%steps))
for i in range(rings-1):
    for j in range(steps):
        a=1+i*steps+j;b=1+i*steps+(j+1)%steps
        faces.append((a,a+steps,b+steps,b))
mesh=bpy.data.meshes.new('HairCapGeometry');mesh.from_pydata(verts,[],faces);mesh.update()
o=bpy.data.objects.new('SculptedHairCap',mesh);scene.collection.objects.link(o);o.data.materials.append(hair)
for p in mesh.polygons:p.use_smooth=True
register(o,'SculptedHairCap',head)
hair_lock('HeroDiagonalFringe',[(.194,-.108,1.697),(.099,-.193,1.753),(-.060,-.211,1.729),(-.193,-.197,1.630),(-.222,-.148,1.545)],[.025,.059,.065,.042,.004],hair,head)
hair_lock('CrownFold01',[(.187,-.037,1.717),(.082,-.100,1.798),(-.092,-.144,1.799),(-.221,-.116,1.712)],[.018,.049,.047,.004],hair_edge,head)
hair_lock('CrownFold02',[(.163,.038,1.727),(.047,-.025,1.828),(-.122,-.054,1.800),(-.218,-.055,1.696)],[.014,.040,.037,.003],hair,head)
hair_lock('TempleSweep',[(.214,-.013,1.653),(.232,-.047,1.598),(.235,-.026,1.484)],[.026,.028,.007],hair,head)
hair_lock('NapeFold',[(-.120,.164,1.638),(-.045,.210,1.600),(.119,.162,1.460)],[.018,.025,.008],hair_edge,head)

# Neck and oversize cropped outerwear. Folds create a designed diagonal silhouette.
cylinder('Neck',(0,0,1.245),.074,.120,skin,body,vertices=32)
cylinder('GraphiteHighNeck',(0,0,1.201),.092,.119,charcoal,body,vertices=32)
loft('CroppedJacket',[(0,.014,.803,.152,.121),(0,.014,.819,.194,.147),
    (0,.014,.863,.218,.156),(0,.014,1.061,.252,.164),(0,.015,1.143,.243,.150),
    (0,.016,1.203,.165,.117),(0,.018,1.222,.105,.083)],ivory,body)
panel('FoldedHighCollar',[(-.048,-.082,1.257),(-.154,-.061,1.282),(-.232,-.110,1.174),(-.159,-.205,1.067),(-.101,-.176,1.197)],ivory,.022,.012,body)
panel('HighCollarInner',[(-.052,-.085,1.257),(-.151,-.065,1.278),(-.140,-.100,1.202)],charcoal,.008,.003,body)
panel('LowFoldLapel',[(.039,-.095,1.215),(.167,-.092,1.227),(.231,-.142,1.149),(.160,-.197,1.036),(.088,-.180,1.143)],ivory,.024,.012,body)
curve('DiagonalJacketFold',[(-.133,-.168,1.190),(-.060,-.177,1.084),(.071,-.169,.883)],.005,brass,body)
panel('AsymmetricHem',[(-.199,-.138,.863),(.202,-.131,.865),(.181,-.145,.796),(-.183,-.149,.827)],ivory,.022,.009,body)
box('CroppedInnerLayer',(0,.01,.776),(.322,.254,.129),charcoal,.048,body)
# Crossbody ribbon and matching case are one functional design element.
box('WideCrossbodyFront',(.021,-.185,1.025),(.083,.028,.462),terra,.010,body,(0,.76,0))
box('WideCrossbodyBack',(.021,.180,1.025),(.083,.026,.459),terra,.010,body,(0,.76,0))
box('SashKeeper',(-.105,-.206,.912),(.095,.026,.024),brass,.004,body,(0,.76,0))
box('FoldedToolCase',(-.236,-.047,.811),(.137,.178,.214),terra,.024,body,(0,-.08,0))
panel('ToolCaseFlap',[(-.307,-.146,.862),(-.168,-.146,.862),(-.168,-.149,.818),(-.237,-.154,.784),(-.307,-.149,.818)],terra,.012,.008,body)
cylinder('ToolCaseClasp',(-.237,-.164,.810),.009,.006,brass,body,'Y',16)
# Small creator pin on the high collar.
for i,a in enumerate((0,120,240)):
    r=math.radians(a)
    p=sphere('CreatorPinPetal'+str(i),(-.152+.013*math.sin(r),-.185,1.169+.013*math.cos(r)),(.007,.004,.016),brass,body)
    p.rotation_euler[1]=-r

# Relaxed adult posing with oversized sleeves and separate human mitten hands.
for sign in (-1,1):
    par=empty('Arm'+str(sign),(sign*.226,0,1.116),body)
    elbow=(sign*.329,-.003,.972)
    wrist=(sign*.356,-.040,.820) if sign==1 else (-.308,-.186,.970)
    sphere('SleeveShoulder'+str(sign),(sign*.251,.017,1.100),(.105,.133,.134),ivory,par)
    rod('SleeveUpper'+str(sign),(sign*.260,.011,1.109),elbow,.090,ivory,par)
    sphere('ElbowFold'+str(sign),elbow,(.082,.098,.081),ivory,par)
    rod('SleeveForearm'+str(sign),elbow,wrist,.070,ivory,par)
    rod('KnitCuff'+str(sign),Vector(wrist)+Vector((0,0,.024)),Vector(wrist)+Vector((0,0,-.025)),.064,charcoal,par)
    h=Vector(wrist)+Vector((0,-.005,-.059)) if sign==1 else Vector(wrist)+Vector((.004,-.041,-.006))
    sphere('Hand'+str(sign),h,(.052,.046,.065),skin,par)
    sphere('Thumb'+str(sign),h+Vector((-sign*.038,-.018,.014)),(.024,.028,.036),skin,par)
    if sign==1:
        rod('LongCreatorStylus',(h.x-.008,h.y-.025,h.z+.032),(h.x+.057,h.y-.049,h.z-.161),.009,brass,par)
        sphere('StylusNib',(h.x+.060,h.y-.050,h.z-.170),(.007,.007,.014),charcoal,par)
    else:
        box('FoldingNotebook',(-.274,-.282,.974),(.171,.034,.202),charcoal,.015,par,(0,-.18,0))
        box('NotebookFoldPanel',(-.280,-.304,.976),(.151,.017,.181),terra,.010,par,(0,-.18,0))
        rod('NotebookFoldHinge',(-.350,-.288,.884),(-.318,-.288,1.068),.008,brass,par)

# Balloon trousers taper into shortened cuffs and monolithic split-sole boots.
for sign in (-1,1):
    x=sign*.119
    loft('BalloonTrouser'+str(sign),[(x,.018,.283,.066,.077),(x,.012,.302,.080,.092),
        (x,.013,.363,.100,.111),(x,.018,.507,.120,.132),(x,.025,.679,.130,.139),
        (x,.022,.762,.109,.118),(x,.020,.785,.079,.098)],charcoal,body)
    cylinder('TrouserTurnup'+str(sign),(x,.009,.298),.077,.052,charcoal,body,vertices=32)
    cylinder('Sock'+str(sign),(x,-.002,.235),.057,.094,ivory,body,vertices=32)
    box('SplitSoleRear'+str(sign),(x,.035,.037),(.194,.149,.074),sole,.025,body)
    box('SplitSoleFront'+str(sign),(x,-.122,.040),(.204,.173,.080),terra,.026,body)
    box('SculpturalBoot'+str(sign),(x,-.061,.132),(.196,.299,.169),ivory,.061,body)
    box('BootUpper'+str(sign),(x,.010,.208),(.154,.157,.134),ivory,.044,body)
    panel('BootDiagonalWrap'+str(sign),[(x-.087,-.220,.136),(x+.078,-.220,.089),(x+.085,-.220,.116),(x-.084,-.220,.164)],terra,.009,.005,body)
    box('BootHeelLoop'+str(sign),(x,.099,.222),(.046,.025,.072),terra,.007,body)

# Adult collectible proportion: approx 3.5 heads, keeping chin at neck base.
head.scale=(.8,.8,.8)
head.location.z=1.238+.8*(1.49-1.238)

# Approval assets only: no output to public or live website source.
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in asset_objects:o.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(HERE/'option-a-fold-creator.glb'),export_format='GLB',use_selection=True,export_extras=True,export_yup=True,export_animations=False)
backdrop=material('Approval studio backdrop','D5D0C6',.80)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));bpy.context.object.data.materials.append(backdrop)
world=bpy.data.worlds.new('Soft approval studio');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.61,.65,.70,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.32;scene.world=world
def area(name,loc,power,size,color):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector((0,0,.95))-o.location).to_track_quat('-Z','Y').to_euler()
area('Large soft key',(-3,-4,5),450,4,(1,.87,.73))
area('Cool fill',(3,-2,3),220,3,(.80,.88,1))
area('Edge separation',(1,3,4),460,2.6,(1,.93,.82))
d=bpy.data.cameras.new('ApprovalCamera');camera=bpy.data.objects.new('ApprovalCamera',d);scene.collection.objects.link(camera);scene.camera=camera
d.type='ORTHO';d.ortho_scale=2.20
def camera_at(pos):
    camera.location=pos;camera.rotation_euler=(Vector((0,-.012,.94))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_at((3,-7,2.75))
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.render.filepath=str(HERE/'option-a-front-threequarter.png')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'option-a-fold-creator.blend'))
bpy.ops.render.render(write_still=True)
camera_at((-3.8,6,2.75));scene.render.filepath=str(HERE/'option-a-back-threequarter.png')
bpy.ops.render.render(write_still=True)
print('OPTION_A_READY='+str(HERE))

