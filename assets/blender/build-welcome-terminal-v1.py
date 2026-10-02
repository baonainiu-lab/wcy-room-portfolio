"""Blender MCP authoring record: native mesh operators, editable hinges and PBR.
Run in a new Blender scene. Never run in the original room project.
"""
import bpy, math
from mathutils import Matrix, Vector
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
assert bpy.context.scene.name == 'WELCOME_TERMINAL_V1'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for datablocks in [bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.cameras, bpy.data.lights]:
    for block in list(datablocks):
        if block.users == 0:
            datablocks.remove(block)
s = bpy.context.scene
s.render.engine = 'CYCLES'
s.cycles.samples = 32
s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1100, 850, 100
s.view_settings.view_transform = 'AgX'

def color(h):
    values = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in values) + (1,)

def mat(name, h, metal, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = color(h)
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = rough
    m.diffuse_color = color(h)
    return m

blue = mat('TERMINAL_DeepBlue_Enamel', '244F70', .42, .27)
silver = mat('TERMINAL_SatinTitanium', 'B4C4CF', .85, .24)
orange = mat('TERMINAL_Vermilion', 'F58036', .18, .30)
dark = mat('TERMINAL_DarkRubber', '101B26', .05, .43)
gold = mat('TERMINAL_WarmTrace', 'EFAD59', .55, .26)

def carrier(name, position):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=position)
    obj = bpy.context.view_layer.objects.active
    obj.name, obj.empty_display_size = name, .2
    return obj

base = carrier('seed.base', (0, 0, 0))
lid = carrier('seed.lid', (0, -.45, .285))
dial = carrier('seed.dial', (1.06, -.705, .29))
rail = carrier('seed.rail', (-1.335, 0, .24))

def finish_mesh(obj, material, parent, location):
    for face in obj.data.polygons:
        face.use_smooth = True
    normal = obj.modifiers.new('Weighted face normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=normal.name)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = location
    return obj

def box(name, location, dimensions, material, bevel=.06, parent=base):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.view_layer.objects.active
    obj.name, obj.dimensions = name, dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new('Precision rounded edges', 'BEVEL')
    mod.width, mod.segments, mod.harden_normals = bevel, 6, True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish_mesh(obj, material, parent, location)

def cylinder(name, location, radius, depth, material, parent=base):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=depth)
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    mod = obj.modifiers.new('Machined lip', 'BEVEL')
    mod.width, mod.segments = .012, 3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish_mesh(obj, material, parent, location)

box('terminal.base.navy', (0,0,.08), (2.80,1.80,.20), blue, .095)
box('terminal.base.titanium_seam', (0,0,.187), (2.81,1.81,.04), silver, .019)
box('terminal.base.upper', (0,0,.227), (2.77,1.77,.05), blue, .023)
box('terminal.base.underside', (0,0,-.035), (2.58,1.58,.045), dark, .020)
box('terminal.lid.rim', (0,.63,.02), (2.48,1.35,.13), silver, .062,lid)
box('terminal.lid.navy', (0,.63,.087), (2.39,1.26,.06), blue, .029,lid)
box('terminal.lid.screen_recess', (0,.60,.120), (2.20,1.005,.023), dark,.010,lid)
image = bpy.data.images.load(str(ROOT/'public/textures/lighting-v15/screen-art-render.png'), check_existing=True)
image.pack()
material = bpy.data.materials.new('TERMINAL_OriginalScreenArtwork')
material.use_nodes = True
nodes = material.node_tree.nodes
nodes.clear()
texture = nodes.new('ShaderNodeTexImage')
texture.image = image
emission = nodes.new('ShaderNodeEmission')
emission.inputs['Strength'].default_value = .85
output = nodes.new('ShaderNodeOutputMaterial')
material.node_tree.links.new(texture.outputs['Color'], emission.inputs['Color'])
material.node_tree.links.new(emission.outputs[0], output.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=2)
screen = bpy.context.view_layer.objects.active
screen.name, screen.scale = 'terminal.lid.artwork', (1.0575,.44,1)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
screen.data.materials.append(material)
screen.parent, screen.matrix_parent_inverse = lid, Matrix.Identity(4)
screen.location = (0,.60,.133)
box('terminal.lid.warm_indicator', (0,.055,.124), (.42,.013,.009), gold,.004,lid)
cylinder('terminal.dial.socket', (0,0,0),.159,.043,dark,dial)
cylinder('terminal.dial.titanium', (0,0,.025),.14,.058,silver,dial)
cylinder('terminal.dial.orange', (0,0,.061),.122,.035,orange,dial)
box('terminal.dial.indicator', (0,-.072,.082),(.012,.060,.005),dark,.002,dial)
box('terminal.rail.silver',(0,0,0),(.060,1.18,.065),silver,.027,rail)
box('terminal.rail.orange',(0,-.23,.042),(.036,.29,.018),orange,.008,rail)
for i in range(3):
    box('terminal.status.'+str(i),(-1.08+i*.077,-.78,.261),(.040,.022,.008),gold,.004)
for obj, destination in [(base,'floor'),(lid,'window-wall'),(rail,'side-wall'),(dial,'desktop-detail')]:
    obj['intro_destination'] = destination

s.render.fps, s.frame_start, s.frame_end = 60, 1, 97
for frame in range(1,98):
    u = (frame-1)/96
    eased = u*u*u*(10+u*(-15+6*u))
    lid.rotation_euler.x = math.radians(12+83*eased)
    lid.location.y = -.45 + 1.10*eased
    lid.keyframe_insert(data_path='location',frame=frame,group='Terminal opening')
    dial.rotation_euler.z = -.8*eased
    rail.rotation_euler.y = -.32*eased
    for obj in [lid, dial, rail]:
        obj.keyframe_insert(data_path='rotation_euler',frame=frame,group='Terminal opening')
for obj in [lid,dial,rail]:
    obj.animation_data.action.name = 'TerminalUnfold_'+obj.name
    for layer in obj.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
s.frame_set(1)

# Studio review only. No camera or light nodes are exported to the website.
bpy.ops.object.camera_add(location=(4.2,-5.4,4.6))
camera = bpy.context.view_layer.objects.active
camera.name = 'Review camera'
camera.rotation_euler = (Vector((0,0,.25))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type, camera.data.ortho_scale = 'ORTHO', 4.25
s.camera = camera
for name, position, power, size in [('Key softbox',(1,-3,6),470,5),('Rim softbox',(-4,2,3),600,4),('Warm edge',(3,3,2),280,3)]:
    bpy.ops.object.light_add(type='AREA',location=position)
    obj = bpy.context.view_layer.objects.active
    obj.name, obj.data.energy, obj.data.shape, obj.data.size = name,power,'DISK',size
    obj.rotation_euler = (Vector((0,0,0))-obj.location).to_track_quat('-Z','Y').to_euler()
    if name == 'Warm edge':
        obj.data.color = (1,.65,.36)
s['design_note'] = 'Independent portable creative terminal: existing original artwork, blue enamel, titanium and vermilion. Blender-authored geometry and hinge animation.'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/welcome-terminal-v1.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'public/models/welcome-terminal-v1.glb'),export_format='GLB',export_extras=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name='TerminalUnfold',export_current_frame=True,export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
s.frame_set(0)
s.frame_set(1)
s.render.filepath = str(ROOT/'renders/welcome-terminal-v1-blender.png')
s.render.image_settings.file_format = 'PNG'
result = {'file':bpy.data.filepath,'meshCount':sum(o.type=='MESH' for o in s.objects),'renderPath':s.render.filepath}
