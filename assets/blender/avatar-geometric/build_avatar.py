"""Deterministic original mascot. Run with Blender --background --python build_avatar.py.

The preview and web export use the exact same mesh hierarchy and materials.
Only presentation lights, world and camera differ in a web renderer.
No external geometry, images, fonts, or generative-image references are required.
"""
import bpy
import math
import json
from pathlib import Path
from mathutils import Vector

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
OUT = PROJECT / 'public/models/avatar'
RENDERS = PROJECT / 'renders/avatar-geometric'
OUT.mkdir(parents=True, exist_ok=True)
RENDERS.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
asset_objects = []


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


root = empty('GeometricCreator')
root['asset_id'] = 'avatar.creator'
root['design_version'] = 'geometric-creator-v1'
root['design_name'] = '小轨 / Orbit'
root['source'] = 'Original procedural Blender geometry; no third-party assets'
body = empty('AvatarBody', (0, 0, .82), root)
head = empty('AvatarHead', (0, 0, 1.40), body)
arm_l = empty('AvatarArmL', (.257, 0, 1.17), body)
arm_r = empty('AvatarArmR', (-.257, 0, 1.17), body)
terminal = empty('AvatarTerminal', (-.16, -.30, 1.00), body)
terminal['asset_id'] = 'avatar.terminal'
terminal['action'] = 'portfolio'

# Large readable head: warm ceramic shell / charcoal gasket / recessed visor.
box('HeadCeramic', (0, .006, 1.427), (.575, .418, .46), ceramic, .094, head)
box('HeadFaceGasket', (0, -.196, 1.423), (.523, .059, .372), graphite, .069, head)
box('HeadGlassFace', (0, -.228, 1.431), (.482, .041, .323), glass, .061, head)
pill('EyeL', (.100, -.251, 1.470), .071, .018, .123, led, head)
pill('EyeR', (-.100, -.251, 1.470), .071, .018, .123, led, head)
smile = []
for i in range(25):
    x = -.065 + .130*i/24
    smile.append((x, -.253, 1.370 - .028*(1-(x/.065)**2)))
curve('Smile', smile, .0085, led, head)
# One quiet asymmetric cheek signal; cheek pips visually echo the terminal controls.
for i in range(3):
    cylinder('FaceStatus' + str(i), (.165, -.251, 1.370+i*.019), .004, .005, orange, head, 'Y', 12)
for sign in (-1, 1):
    cylinder('TempleGasket' + str(sign), (sign*.284, .015, 1.430), .082, .042, graphite, head, 'X')
    cylinder('TempleCap' + str(sign), (sign*.309, .015, 1.430), .060, .018, ceramic, head, 'X')
    cylinder('TempleHub' + str(sign), (sign*.319, .015, 1.430), .021, .010, orange, head, 'X')
    # Rear shell seam and service dots are intentionally functional, not ornament noise.
    box('RearShellSeam' + str(sign), (sign*.183, .214, 1.425), (.012, .007, .227), graphite, .003, head)
box('HeadRearPlate', (0, .216, 1.390), (.205, .013, .096), graphite, .020, head)
for i in range(3):
    box('RearVent'+str(i), ((i-1)*.046, .226, 1.390), (.023, .007, .055), metal, .007, head)
rod('AntennaStem', (.185, .014, 1.619), (.220, .014, 1.739), .011, graphite, head)
sphere('AntennaSignal', (.222, .014, 1.752), (.036, .033, .037), orange, head)

# Main shell has articulated neck, collar, orange chest cassette and creation emblem.
cylinder('NeckBall', (0, 0, 1.234), .072, .092, graphite, body)
cylinder('OrangeCollar', (0, 0, 1.217), .116, .038, orange, body, vertices=32)
cylinder('CollarTopLip', (0, 0, 1.241), .089, .014, metal, body, vertices=32)
box('TorsoCore', (0, .016, .995), (.409, .286, .411), graphite, .080, body)
box('TorsoCeramicShell', (0, -.006, 1.030), (.431, .316, .362), ceramic, .084, body)
box('ChestRecess', (0, -.162, 1.065), (.249, .024, .221), graphite, .042, body)
box('OrangeChestCassette', (0, -.179, 1.065), (.221, .023, .193), orange, .035, body)
# Three separated teardrop-ish ellipsoids: simple reproducible making/flower motif.
for idx, angle in enumerate((0, 120, 240)):
    a = math.radians(angle)
    o = sphere('CreatorPetal'+str(idx), (.024*math.sin(a), -.196, 1.073+.024*math.cos(a)), (.013, .0055, .031), ceramic, body)
    o.rotation_euler[1] = -a
cylinder('CreatorMarkCore', (0, -.204, 1.073), .010, .003, led, body, 'Y', 16)
box('ChestIndicator', (0, -.198, 1.006), (.066, .006, .010), led, .004, body)
for sign in (-1, 1):
    cylinder('ChestFastener'+str(sign), (sign*.084, -.195, 1.116), .007, .005, metal, body, 'Y', 12)
box('AbdomenBelt', (0, .009, .823), (.318, .270, .089), graphite, .035, body)
box('AbdomenClasp', (0, -.138, .828), (.091, .028, .047), metal, .012, body)
box('PelvisShell', (0, .015, .716), (.315, .252, .169), ceramic, .057, body)
box('PelvisCenterInset', (0, -.116, .724), (.048, .018, .077), graphite, .014, body)
# Slim battery pack establishes rear silhouette without a backpack-like visual load.
box('BackUtilityPack', (0, .176, 1.020), (.273, .099, .269), graphite, .037, body)
box('BackUtilityCover', (0, .225, 1.026), (.240, .024, .228), ceramic, .029, body)
box('BackPackSignal', (0, .242, 1.069), (.085, .008, .019), orange, .005, body)
for i in range(3):
    box('BackPackVent'+str(i), ((i-1)*.045, .242, .994), (.021, .008, .052), graphite, .006, body)

# Arms are rigid-child mechanisms. Right hand holds the slate; left hand waves.
for sign, par, suffix in ((1, arm_l, 'L'), (-1, arm_r, 'R')):
    cylinder('ShoulderAxle'+suffix, (sign*.247, 0, 1.157), .079, .103, graphite, par, 'X')
    cylinder('ShoulderCap'+suffix, (sign*.304, 0, 1.157), .070, .030, ceramic, par, 'X')
    cylinder('ShoulderAccent'+suffix, (sign*.323, 0, 1.157), .042, .009, orange, par, 'X')
    if sign == 1:
        elbow = (.326, -.008, .966)
        wrist = (.335, -.038, .799)
        rod('UpperArmL', (.280, 0, 1.114), elbow, .050, graphite, par)
        box('UpperArmShellL', (.309, -.012, 1.049), (.098, .108, .165), ceramic, .033, par, (0, -.13, 0))
        sphere('ElbowL', elbow, (.052, .054, .054), graphite, par)
        rod('ForearmL', elbow, wrist, .035, graphite, par)
        box('ForearmCuffL', (.334, -.033, .843), (.088, .090, .082), orange, .021, par)
        box('HandL', (.335, -.047, .752), (.108, .103, .117), ceramic, .035, par)
        sphere('ThumbL', (.288, -.064, .766), (.035, .037, .045), ceramic, par)
        for i in range(2):
            box('FingerDivisionL'+str(i), (.322+i*.029, -.099, .736), (.005, .006, .046), graphite, .002, par)
    else:
        elbow = (-.335, -.048, .988)
        wrist = (-.291, -.270, .968)
        rod('UpperArmR', (-.28, 0, 1.113), elbow, .048, graphite, par)
        box('UpperArmShellR', (-.308, -.022, 1.049), (.098, .108, .159), ceramic, .033, par, (0, .17, 0))
        sphere('ElbowR', elbow, (.052, .054, .054), graphite, par)
        rod('ForearmR', elbow, wrist, .036, graphite, par)
        cylinder('ForearmCuffR', (-.297, -.235, .971), .049, .065, orange, par, 'Y')
        box('HandR', (-.290, -.287, .966), (.107, .113, .082), ceramic, .027, par)
        sphere('ThumbR', (-.267, -.319, .998), (.033, .034, .028), ceramic, par)

# Leg construction: short ceramic shin armor over dark hinges, broad grounded boots.
for sign, suffix in ((-1, 'R'), (1, 'L')):
    x = sign*.104
    sphere('Hip'+suffix, (x, .012, .658), (.067, .071, .069), graphite, body)
    rod('ThighCore'+suffix, (x, .012, .632), (x, .010, .453), .046, graphite, body)
    box('ThighShell'+suffix, (x, -.002, .540), (.115, .139, .174), ceramic, .039, body)
    cylinder('Knee'+suffix, (x, .005, .432), .060, .130, graphite, body, 'X')
    box('KneeCap'+suffix, (x, -.067, .429), (.090, .033, .076), orange, .022, body)
    rod('ShinCore'+suffix, (x, .005, .398), (x, -.005, .200), .045, graphite, body)
    box('ShinShell'+suffix, (x, -.008, .295), (.122, .140, .173), ceramic, .034, body)
    box('ShinInset'+suffix, (x, -.080, .295), (.031, .010, .097), graphite, .009, body)
    cylinder('Ankle'+suffix, (x, -.005, .170), .049, .076, graphite, body)
    box('BootSole'+suffix, (x, -.054, .041), (.174, .273, .082), graphite, .030, body)
    box('BootShell'+suffix, (x, -.060, .116), (.170, .273, .133), ceramic, .046, body)
    box('BootToeTrim'+suffix, (x, -.189, .099), (.113, .017, .033), orange, .008, body)
    box('BootHeelTab'+suffix, (x, .068, .111), (.061, .022, .055), metal, .009, body)

# Drawing slate: deterministic mesh graphics, no texture or external font dependency.
box('TerminalCase', (-.136, -.296, 1.014), (.310, .034, .222), graphite, .022, terminal)
box('TerminalCeramicBack', (-.136, -.274, 1.014), (.281, .013, .197), ceramic, .017, terminal)
box('TerminalScreen', (-.131, -.316, 1.028), (.262, .012, .173), glass, .012, terminal)
box('TerminalOrangeGrip', (-.290, -.296, 1.014), (.025, .050, .157), orange, .009, terminal)
cylinder('TerminalButton', (-.137, -.317, .917), .010, .007, orange, terminal, 'Y', 16)
# A little mint wireframe cubic sketch echoes the user's 3D portfolio work.
cube_lines = [
    ((-.184, 1.028), (-.143, 1.049)), ((-.143, 1.049), (-.102, 1.028)),
    ((-.102, 1.028), (-.143, 1.007)), ((-.143, 1.007), (-.184, 1.028)),
    ((-.184, 1.028), (-.184, .976)), ((-.143, 1.007), (-.143, .955)),
    ((-.102, 1.028), (-.102, .976)), ((-.184, .976), (-.143, .955)),
    ((-.143, .955), (-.102, .976)),
]
for i, (a, b) in enumerate(cube_lines):
    curve('TerminalSketch'+str(i), [(a[0], -.324, a[1]), (b[0], -.324, b[1])], .002, mint, terminal)
box('TerminalUIHeader', (-.143, -.324, 1.092), (.145, .003, .006), mint, .001, terminal)
for i in range(3):
    box('TerminalUITool'+str(i), (-.030, -.324, 1.065-i*.031), (.016, .003, .016), orange if i == 1 else mint, .003, terminal)
# Fold hinge and stylus rail are visible from the three-quarter angle.
cylinder('TerminalHinge', (-.136, -.271, .907), .013, .235, metal, terminal, 'X')
rod('TerminalStylus', (.037, -.296, .937), (.037, -.296, 1.112), .007, orange, terminal)
sphere('TerminalStylusTip', (.037, -.296, 1.115), (.005, .005, .010), metal, terminal)

# Optimize ONLY a temporary export copy. Original named parts stay editable in .blend.
# Joining within a rigid pivot and a shared material changes draw grouping, not geometry.
bpy.context.view_layer.update()
source_names = {o: o.name for o in asset_objects}
source_world = {o: o.matrix_world.copy() for o in asset_objects}
export_collection = bpy.data.collections.new('TEMP_AVATAR_EXPORT')
scene.collection.children.link(export_collection)
copies = {}
for o in asset_objects:
    o.name = source_names[o] + '_EDITABLE'
for o in asset_objects:
    copy = o.copy()
    if o.type == 'MESH':
        copy.data = o.data.copy()
    export_collection.objects.link(copy)
    copy.name = source_names[o]
    copies[o] = copy
for o, copy in copies.items():
    copy.parent = copies.get(o.parent)
    copy.matrix_world = source_world[o]
bpy.context.view_layer.update()
groups = {}
for copy in copies.values():
    if copy.type == 'MESH' and copy.name not in ('EyeL', 'EyeR'):
        key = (copy.parent.name, copy.data.materials[0].name)
        groups.setdefault(key, []).append(copy)
for (parent_name, material_name), meshes in groups.items():
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    bpy.context.object.name = parent_name + '__' + material_name
bpy.ops.object.select_all(action='DESELECT')
export_objects = list(export_collection.objects)
for copy in export_objects:
    copy.select_set(True)
bpy.context.view_layer.objects.active = copies[root]
glb = OUT / 'geometric-creator-v1.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
    export_extras=True, export_yup=True, export_apply=True, export_animations=False,
    export_cameras=False, export_lights=False, export_materials='EXPORT')
export_mesh_count = sum(o.type == 'MESH' for o in export_objects)
export_node_count = len(export_objects)
for copy in export_objects:
    data = copy.data if copy.type == 'MESH' else None
    bpy.data.objects.remove(copy, do_unlink=True)
    if data and data.users == 0:
        bpy.data.meshes.remove(data)
bpy.data.collections.remove(export_collection)
for o, name in source_names.items():
    o.name = name

mesh_objects = [o for o in asset_objects if o.type == 'MESH']
tris = sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in mesh_objects)
world_points = [o.matrix_world @ vertex.co for o in mesh_objects for vertex in o.data.vertices]
lo = [min(p[i] for p in world_points) for i in range(3)]
hi = [max(p[i] for p in world_points) for i in range(3)]
manifest = {
    'name': '小轨 / Orbit', 'version': 1, 'root': 'GeometricCreator',
    'source': 'Original deterministic Blender geometry and materials',
    'glb': '/models/avatar/geometric-creator-v1.glb',
    'blend': 'assets/blender/avatar-geometric/geometric-creator-v1.blend',
    'generator': 'assets/blender/avatar-geometric/build_avatar.py',
    'axis': {'blender_up': '+Z', 'blender_front': '-Y', 'gltf_up': '+Y', 'gltf_front': '+Z'},
    'gltf_bounds': {'min': [lo[0], lo[2], -hi[1]], 'max': [hi[0], hi[2], -lo[1]]},
    'dimensions_m': {'width': hi[0]-lo[0], 'height': hi[2]-lo[2], 'depth': hi[1]-lo[1]},
    'triangles': tris, 'mesh_nodes': export_mesh_count, 'total_nodes': export_node_count,
    'editable_mesh_nodes': len(mesh_objects),
    'optimization': 'Export-only duplicate joins static meshes by rigid parent and shared material; animated boundaries and eyes stay independent.',
    'material_count': 7, 'bytes': glb.stat().st_size,
    'materials': {'CeramicShell': '#EEE7D8', 'GraphiteJoint': '#384149', 'SignalOrange': '#F5803D',
                  'ObsidianGlass': '#172A30', 'WarmLED': '#FFE1A8', 'BrushedTitanium': '#89918F', 'ScreenMint': '#9EDAD2'},
    'rig': {
        'AvatarBody': {'pivot_blender': [0, 0, .82], 'idle_axis_gltf': 'Y'},
        'AvatarHead': {'pivot_blender': [0, 0, 1.4], 'yaw_axis_gltf': 'Y', 'nod_axis_gltf': 'X', 'suggested_yaw_limit_rad': .35},
        'AvatarArmL': {'pivot_blender': [.257, 0, 1.17], 'free_for_wave': True, 'wave_axis_gltf': 'Z', 'lift_axis_gltf': 'X'},
        'AvatarArmR': {'pivot_blender': [-.257, 0, 1.17], 'free_for_wave': False, 'note': 'Right hand supports slate; leave relaxed'},
        'EyeL': {'blink_scale_axis_gltf': 'Y', 'rest_scale': [1, 1, 1]},
        'EyeR': {'blink_scale_axis_gltf': 'Y', 'rest_scale': [1, 1, 1]},
        'AvatarTerminal': {'pivot_blender': [-.16, -.30, 1.00], 'asset_id': 'avatar.terminal'},
    },
    'identity_guarantee': 'Studio reference and website load the same exported mesh hierarchy; lighting, camera, tone mapping and display affect rendered pixels.',
    'limitations': 'Rigid segmented character; no organic skin, no skinned skeleton, no embedded animation clips.',
}
(OUT / 'geometric-creator-v1.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
(HERE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

# Studio presentation is separate from the export collection.
ground = material('StudioBackdropOnly', 'D9D5CB', .76)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.002))
bpy.context.object.name = 'StudioGround_EXCLUDED_FROM_GLB'
bpy.context.object.data.materials.append(ground)
world = bpy.data.worlds.new('StudioWorld')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.60, .65, .68, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .32
scene.world = world


def area(name, loc, power, size, color):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy, d.shape, d.size, d.color = power, 'DISK', size, color
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, .90))-o.location).to_track_quat('-Z', 'Y').to_euler()


area('StudioKey', (-3, -4, 5), 430, 4.0, (1, .88, .76))
area('StudioFill', (3, -1, 3), 240, 3.0, (.76, .87, 1))
area('StudioRim', (1, 3, 4), 480, 2.4, (1, .91, .77))
d = bpy.data.cameras.new('AvatarStudioCamera')
camera = bpy.data.objects.new('AvatarStudioCamera', d)
scene.collection.objects.link(camera)
scene.camera = camera
d.type = 'ORTHO'
d.ortho_scale = 2.25
camera.location = (3, -6, 3.05)
target = Vector((0, -.015, .91))
camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1200
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.render.film_transparent = False
scene.render.filepath = str(RENDERS / 'geometric-creator-v1-studio.png')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'geometric-creator-v1.blend'))
print('AVATAR_MANIFEST=' + json.dumps(manifest, ensure_ascii=False))
bpy.ops.render.render(write_still=True)
print('AVATAR_COMPLETE=' + str(glb))
