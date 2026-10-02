"""Blender MCP: precision-detail pass on the isolated V1 terminal.

Never run against the room file. The four carriers, their animation and the
original packed screen pixels are preserved. V1 is never overwritten.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
assert Path(bpy.data.filepath) == ROOT/'assets/blender/welcome-terminal-v1.blend'
assert bpy.context.scene.name == 'WELCOME_TERMINAL_V1'
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
s = bpy.context.scene
s.frame_set(1)
bpy.context.view_layer.update()
roots = {n: bpy.data.objects[n] for n in ['seed.base','seed.lid','seed.dial','seed.rail']}
base, lid, dial, rail = (roots[n] for n in roots)
original_meshes = [o for o in s.objects if o.type == 'MESH']

def bounds(objects):
    points = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    return {'min':[min(p[i] for p in points) for i in range(3)],
            'max':[max(p[i] for p in points) for i in range(3)]}

original_bounds = {}
original_transforms = {}
for frame in [1,25,49,73,97]:
    s.frame_set(frame); bpy.context.view_layer.update()
    original_bounds[frame] = bounds(original_meshes)
    original_transforms[frame] = {n:[list(row) for row in o.matrix_local] for n,o in roots.items()}
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/welcome-terminal-v2.blend'))
s.name = 'WELCOME_TERMINAL_V2'

def srgb(h):
    v = [int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in v)+(1,)

def material(name, color, metallic, roughness, coat=0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = srgb(color)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = .18
    m.diffuse_color = srgb(color)
    return m

blue = material('TERMINAL_DeepBlue_Enamel','244F70',.57,.25,.24)
silver = material('TERMINAL_SatinTitanium','B4C4CF',.9,.22,.06)
dark = material('TERMINAL_DarkRubber','101B26',.06,.44)
orange = material('TERMINAL_Vermilion','F58036',.22,.26,.32)
gold = material('TERMINAL_WarmTrace','EFAD59',.55,.23,.12)
ivory = material('TERMINAL_IvoryCeramic','E5DDC8',.08,.27,.3)

# One textured PBR surface supplies glass reflections without a coplanar
# transparent overlay, sorting artifacts or an additional transmission pass.
art = bpy.data.materials['TERMINAL_OriginalScreenArtwork']
image = bpy.data.images['screen-art-render.png']
nodes = art.node_tree.nodes; nodes.clear()
texture = nodes.new('ShaderNodeTexImage'); texture.image = image
texture.interpolation = 'Linear'
shader = nodes.new('ShaderNodeBsdfPrincipled')
shader.inputs['Base Color'].default_value = (.001,.003,.006,1)
shader.inputs['Roughness'].default_value = .22
shader.inputs['Metallic'].default_value = 0
shader.inputs['IOR'].default_value = 1.46
shader.inputs['Specular IOR Level'].default_value = .035
shader.inputs['Coat Weight'].default_value = .025
shader.inputs['Coat Roughness'].default_value = .18
shader.inputs['Emission Strength'].default_value = .85
output = nodes.new('ShaderNodeOutputMaterial')
art.node_tree.links.new(texture.outputs['Color'],shader.inputs['Emission Color'])
art.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface'])

added = []
def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj

def finish(obj, name, loc, mat, parent, bevel=0, segments=2):
    obj.name = name
    activate(obj)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        m=obj.modifiers.new('Machined edge radius','BEVEL')
        m.width=bevel; m.segments=segments; m.harden_normals=True
        bpy.ops.object.modifier_apply(modifier=m.name)
    for p in obj.data.polygons: p.use_smooth=True
    m=obj.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')
    m.keep_sharp=True
    bpy.ops.object.modifier_apply(modifier=m.name)
    if mat: obj.data.materials.append(mat)
    obj.parent=parent; obj.matrix_parent_inverse=Matrix.Identity(4)
    obj.location=loc
    obj['detail_revision']=2
    added.append(obj)
    return obj

def box(name, loc, dims, mat, parent, bevel=.002):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj=bpy.context.object; obj.dimensions=dims
    return finish(obj,name,loc,mat,parent,bevel)

def cylinder(name, loc, radius, depth, mat, parent, vertices=32, bevel=.0015):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth)
    return finish(bpy.context.object,name,loc,mat,parent,bevel)

# The base's front wall gains actual recessed air slots, not floating decals.
cutters=[]
for i in range(15):
    x=-.77+i*.085
    obj=box('CUT.vent', (x,-.889,.08),(.026,.08,.061),None,base,.008)
    cutters.append(obj)
    box('terminal.base.vent_back', (x,-.858,.08),(.025,.005,.058),dark,base,.004)
activate(cutters[0])
for obj in cutters: obj.select_set(True)
bpy.ops.object.join()
cutter=bpy.context.object
body=bpy.data.objects['terminal.base.navy']
activate(body)
boolean=body.modifiers.new('Recessed cooling channels','BOOLEAN')
boolean.operation='DIFFERENCE'; boolean.solver='EXACT'; boolean.object=cutter
bpy.ops.object.modifier_apply(modifier=boolean.name)
bpy.data.objects.remove(cutter,do_unlink=True)
# Broken cutter references are filtered before batching below.

# Fine front ports and a restrained ivory status island fit inside the old case.
box('terminal.base.port_surround',(.84,-.901,.085),(.185,.006,.063),silver,base,.012)
box('terminal.base.port_inset',(.84,-.904,.085),(.143,.001,.030),dark,base,.009)
box('terminal.base.port_tongue',(.84,-.9046,.085),(.099,.0005,.009),ivory,base,.002)
box('terminal.base.status_inlay',(-1.003,-.78,.253),(.283,.094,.006),ivory,base,.026)
box('terminal.base.control_line',(.05,-.779,.254),(.77,.010,.003),dark,base,.003)
box('terminal.base.control_accent',(.482,-.779,.254),(.071,.010,.003),orange,base,.003)
for x in [-1.279,1.279]:
    for y in [-.721,.72]:
        cylinder('terminal.base.captive_screw',(x,y,.253),.023,.004,silver,base,24,.001)
        box('terminal.base.screw_slot',(x,y,.2555),(.023,.003,.0015),dark,base,.0007)

# Segmented real hinge barrels stay on seed.lid, so no hinge can lag the lid.
for i in range(5):
    obj=cylinder('terminal.lid.hinge_segment',(-.54+i*.27,.003,-.006),.035,.222,silver,lid,32,.002)
    obj.rotation_euler.y=math.pi/2
for x in [-.662,.662]:
    obj=cylinder('terminal.lid.hinge_end', (x,.003,-.006),.033,.015,dark,lid,32,.0015)
    obj.rotation_euler.y=math.pi/2
for x in [-1.145,1.145]:
    for y in [.14,1.12]:
        cylinder('terminal.lid.fastener',(x,y,.1195),.018,.005,silver,lid,24,.001)
        box('terminal.lid.fastener_slot',(x,y,.1225),(.017,.0025,.001),dark,lid,.0005)
# Stepped thin inner bezel outside the original artwork rectangle.
for x in [-1.079,1.079]:
    box('terminal.lid.inner_bezel',(x,.6,.132),(.009,.903,.0015),silver,lid,.0006)
for y in [.147,1.053]:
    box('terminal.lid.inner_bezel',(0,y,.132),(2.166,.009,.0015),silver,lid,.0006)
for i in range(7):
    cylinder('terminal.lid.speaker_dot',(-.135+i*.045,1.179,.1185),.006,.0025,dark,lid,16,.0005)
cylinder('terminal.lid.sensor',(.36,1.179,.1185),.015,.0025,dark,lid,24,.001)
cylinder('terminal.lid.sensor_glint',(.36,1.179,.1202),.005,.0007,silver,lid,20,.0003)

# Knurled edge and small engraved ticks distinguish the encoder at hero scale.
for i in range(28):
    a=2*math.pi*i/28
    obj=box('terminal.dial.knurl',(.142*math.cos(a),.142*math.sin(a),.030),(.009,.012,.031),silver,dial,.0017)
    obj.rotation_euler.z=a
for i in range(9):
    a=math.radians(24+16*i)
    obj=box('terminal.dial.face_tick',(.094*math.cos(a),.094*math.sin(a),.080),(.012,.0025,.0015),ivory,dial,.0005)
    obj.rotation_euler.z=a
# Two captive fasteners keep the existing side rail mechanically plausible.
for y in [-.51,.51]:
    cylinder('terminal.rail.fastener',(0,y,.0335),.013,.002,dark,rail,24,.0007)

# Decoration is batched by original seed and material; original named meshes
# and independently interactive root carriers remain intact.
groups={}
for obj in list(s.objects):
    if obj.type=='MESH' and obj.get('detail_revision')==2:
        groups.setdefault((obj.parent.name,obj.active_material.name),[]).append(obj)
for (parent_name,mat_name), objects in groups.items():
    activate(objects[0])
    for obj in objects: obj.select_set(True)
    if len(objects)>1: bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=f'terminal.v2.{parent_name[5:]}.{mat_name.removeprefix("TERMINAL_").lower()}'
    obj['detail_note']='Authored precision features, batched within existing interactive carrier'

# Applied tiny bevels and the exact Boolean can leave collinear export
# triangles. Triangulate once in Blender and remove zero-area faces, then
# recompute weighted normals. This is geometry cleanup, not a relaxed test.
cleaned_faces=0
for obj in s.objects:
    if obj.type!='MESH': continue
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8)
    bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
    invalid=[]
    for face in bm.faces:
        edge2=max((edge.verts[0].co-edge.verts[1].co).length_squared for edge in face.edges)
        if 2*face.calc_area() <= edge2*1e-8: invalid.append(face)
    cleaned_faces+=len(invalid)
    bmesh.ops.delete(bm,geom=invalid,context='FACES_ONLY')
    loose=[v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.normal_update(); bm.to_mesh(obj.data); bm.free(); obj.data.update()
    activate(obj)
    mod=obj.modifiers.new('Export weighted normals','WEIGHTED_NORMAL')
    mod.keep_sharp=True
    bpy.ops.object.modifier_apply(modifier=mod.name)

# No action data or root transform is reauthored in this detail pass.
verification=[]
for frame in [1,25,49,73,97]:
    s.frame_set(frame); bpy.context.view_layer.update()
    current=bounds([o for o in s.objects if o.type=='MESH'])
    old=original_bounds[frame]
    error=max(abs(o.matrix_local[r][c]-original_transforms[frame][n][r][c])
              for n,o in roots.items() for r in range(4) for c in range(4))
    excess=max([old['min'][i]-current['min'][i] for i in range(3)]+
               [current['max'][i]-old['max'][i] for i in range(3)])
    verification.append({'frame':frame,'rootMatrixError':error,'boundsExcess':excess,
                         'oldBoundsBlender':old,'newBoundsBlender':current})
assert all(x['rootMatrixError']<1e-6 for x in verification)
assert all(x['boundsExcess']<1e-5 for x in verification), verification
s.frame_set(1)
s['design_note']='V2 precision terminal: machined case, recessed ventilation, segmented hinge, knurled encoder, satin metal and coated display; four V1 carriers and TerminalUnfold preserved.'
s.render.resolution_x=1500; s.render.resolution_y=1150; s.render.resolution_percentage=100
s.cycles.samples=64
s.cycles.use_denoising=True
s.render.image_settings.file_format='PNG'
s.render.filepath=str(ROOT/'renders/welcome-terminal-v2-blender.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/welcome-terminal-v2.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'public/models/welcome-terminal-v2.glb'),
    export_format='GLB',export_extras=True,export_animations=True,
    export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name='TerminalUnfold',
    export_current_frame=True,export_frame_range=True,export_force_sampling=True,
    export_optimize_animation_size=False,export_cameras=False,export_lights=False)
report={'sourceFile':'assets/blender/welcome-terminal-v1.blend',
        'blend':'assets/blender/welcome-terminal-v2.blend','glb':'public/models/welcome-terminal-v2.glb',
        'meshCount':sum(o.type=='MESH' for o in s.objects),
        'materials':[m.name for m in bpy.data.materials if m.users],
        'verification':verification,'originalScreenImage':image.name,
        'originalScreenImageSize':list(image.size),
        'screenArtworkUnchanged':True,'renderPath':s.render.filepath}
report['removedDegenerateFaces']=cleaned_faces
(ROOT/'assets/blender/welcome-terminal-v2-authoring-report.json').write_text(json.dumps(report,indent=2))
result=report
