# -*- coding: utf-8 -*-
"""Eight original, independent accessories for Orbital Atelier V5.

Append-only relative to the existing room: build() recreates ENRICHMENT_V5 only.
No camera, light, world, render, save, or export changes. Source coordinates are
Z-up metres. Geometry is consolidated per interactive pivot for cheap export.
Every design/material is original; no external imagery or personal text is used.
"""
import math
import bpy
from mathutils import Matrix, Vector

COLLECTION = 'ENRICHMENT_V5'
PREFIX = 'V5_'
C = None
M = {}
ROOTS = []
MANIFEST = []


def _material(name, color, metal=0.0, rough=.4, emission=None):
    name = PREFIX + 'MAT_' + name
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    if emission:
        p.inputs['Emission Color'].default_value = (*emission[0], 1)
        p.inputs['Emission Strength'].default_value = emission[1]
    return m


def _materials():
    M.update({
        'titanium': _material('SatinTitanium', (.42,.49,.55), .85, .27),
        'ceramic': _material('PearlCeramic', (.65,.72,.75), .18, .28),
        'graphite': _material('Graphite', (.021,.033,.048), .48, .31),
        'blue': _material('BlueGreyEnamel', (.075,.15,.205), .40, .34),
        'black': _material('RecessedOptics', (.006,.015,.022), .40, .20),
        'orange': _material('BurntOrange', (.43,.083,.024), .24, .42),
        'amber': _material('AmberSignal', (.95,.28,.047), .1, .28,
                            ((1,.34,.08), 2.5)),
        'cool': _material('IceSignal', (.31,.68,.86), .12, .24,
                           ((.28,.63,.87), 1.8)),
        'warm': _material('WarmDiffuser', (.86,.61,.32), .0, .30,
                           ((1,.73,.38), 3.0)),
    })


def group(name, loc, asset_id, parent=None, interaction='inspect'):
    o = bpy.data.objects.new(PREFIX + name, None)
    C.objects.link(o)
    o.location = loc
    o.empty_display_type = 'PLAIN_AXES'
    o.empty_display_size = .06
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = Matrix.Identity(4)
    o['asset_id'] = asset_id
    o['interactive'] = True
    o['interaction'] = interaction
    o['asset_revision'] = 5
    return o


def root(name, loc, asset_id, label, interaction, footprint):
    o = group(name + '_Root', loc, asset_id, interaction=interaction)
    ROOTS.append(o)
    MANIFEST.append({'root':o.name, 'asset_id':asset_id, 'label_zh':label,
                     'position':list(loc), 'interaction':interaction,
                     'footprint_metres':footprint})
    return o


def mesh(name, verts, faces, mat, parent, smooth=False):
    d = bpy.data.meshes.new(PREFIX + name + '_Mesh')
    d.from_pydata(verts, [], faces)
    d.update()
    o = bpy.data.objects.new(PREFIX + name, d)
    C.objects.link(o)
    o.parent = parent
    o.matrix_parent_inverse = Matrix.Identity(4)
    d.materials.append(M[mat])
    for f in d.polygons:
        f.use_smooth = smooth
    return o


def bevel(o, radius=.012, segments=2):
    b = o.modifiers.new('Precision radii', 'BEVEL')
    b.width = radius
    b.segments = segments
    b.limit_method = 'ANGLE'
    n = o.modifiers.new('Machined face normals', 'WEIGHTED_NORMAL')
    n.keep_sharp = True
    return o


def box(name, loc, dims, mat, parent, radius=.01, rotation=(0,0,0)):
    x,y,z = (v*.5 for v in dims)
    vs = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
          (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o = mesh(name, vs, fs, mat, parent)
    o.location = loc
    o.rotation_euler = rotation
    return bevel(o, radius) if radius else o


def cylinder(name, a, b, radius, mat, parent, sides=32, edge=.004):
    a,b = Vector(a),Vector(b)
    length = (b-a).length
    verts = [(radius*math.cos(i*math.tau/sides),
              radius*math.sin(i*math.tau/sides),z)
             for z in [-length*.5,length*.5] for i in range(sides)]
    faces = [tuple(reversed(range(sides))),tuple(range(sides,sides*2))]
    faces += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    o = mesh(name, verts, faces, mat, parent, True)
    o.location = (a+b)*.5
    o.rotation_euler = (b-a).to_track_quat('Z','Y').to_euler()
    o.data.polygons[0].use_smooth = False
    o.data.polygons[1].use_smooth = False
    return bevel(o,min(edge,radius*.15,length*.15)) if edge else o


def tube(name, points, radius, mat, parent, sides=8, closed=False):
    """Small direct mesh tube; predictable triangle cost, no Curve subdivision."""
    points = [Vector(p) for p in points]
    verts=[];faces=[];count=len(points)
    for i,p in enumerate(points):
        before=points[(i-1)%count] if closed or i else points[0]
        after=points[(i+1)%count] if closed or i<count-1 else points[-1]
        tangent=(after-before).normalized()
        ref=Vector((0,0,1))
        if abs(tangent.dot(ref))>.92:ref=Vector((0,1,0))
        u=tangent.cross(ref).normalized();v=tangent.cross(u).normalized()
        for j in range(sides):
            a=j*math.tau/sides
            verts.append(tuple(p+radius*(u*math.cos(a)+v*math.sin(a))))
    for i in range(count if closed else count-1):
        ni=(i+1)%count
        for j in range(sides):
            nj=(j+1)%sides
            faces.append((i*sides+j,i*sides+nj,ni*sides+nj,ni*sides+j))
    if not closed:
        faces += [tuple(reversed(range(sides))),tuple((count-1)*sides+j for j in range(sides))]
    return mesh(name, verts, faces, mat, parent, True)


def ring(name, centre, radius, wire, mat, parent, plane='XY', start=0, stop=math.tau, steps=48):
    full=abs(stop-start-math.tau)<1e-5
    pts=[]
    for i in range(steps if full else steps+1):
        t=start+(stop-start)*i/steps
        x,y,z=centre
        if plane=='XZ':pts.append((x+radius*math.cos(t),y,z+radius*math.sin(t)))
        elif plane=='YZ':pts.append((x,y+radius*math.cos(t),z+radius*math.sin(t)))
        else:pts.append((x+radius*math.cos(t),y+radius*math.sin(t),z))
    return tube(name,pts,wire,mat,parent,closed=full)


def _workstation_transform():
    scene=bpy.data.scenes.get('ORBITAL_ATELIER_V2') or bpy.context.scene
    values=scene.get('workstation_transform')
    if values and len(values)==16:
        return Matrix([list(values)[i:i+4] for i in range(0,16,4)])
    return (Matrix.Translation(Vector((-3.2,.25,.18))) @
            Matrix.Rotation(math.radians(65),4,'Z') @
            Matrix.Diagonal((1.14,1.14,1.14,1)) @
            Matrix.Translation(Vector((2.4,-1.7,-.18))))


def _on_workstation(o):
    bpy.context.view_layer.update()
    o.matrix_world=_workstation_transform() @ o.matrix_world
    bpy.context.view_layer.update()
    for item in MANIFEST:
        if item['root']==o.name:item['position']=list(o.matrix_world.translation)
    return o


def orbital_clock():
    r=root('ORBITAL_CLOCK',(-4.76,2.30,3.62),'v5_orbital_clock','左墙轨道时钟',
           'rotate_dial', [.12,.79,.79])
    r.rotation_euler.z=math.pi/2
    cylinder('Clock_Back',(0,.0,0),(0,-.055,0),.36,'graphite',r,48)
    cylinder('Clock_Face',(0,-.055,0),(0,-.072,0),.328,'blue',r,48)
    ring('Clock_OuterRim',(0,-.07,0),.354,.024,'titanium',r,'XZ')
    ring('Clock_Orbit',(0,-.084,0),.258,.0035,'cool',r,'XZ',.2,4.6,40)
    for i in range(12):
        a=i*math.tau/12
        tick=box('Clock_Tick_%02d'%i,(.294*math.sin(a),-.089,.294*math.cos(a)),
                 (.009,.008,.033 if i%3==0 else .018),'ceramic',r,.002)
        tick.rotation_euler.y=a
    p=group('CLOCK_DIAL_Pivot',(0,-.088,0),'v5_clock_dial',r,'rotate')
    for i,(a,length) in enumerate([(math.radians(-35),.19),(math.radians(71),.135)]):
        box('Clock_Hand_%d'%i,(math.sin(a)*length*.47,-.015,math.cos(a)*length*.47),
            (.012,.011,length),'amber' if i else 'ceramic',p,.004,(0,a,0))
    cylinder('Clock_Hub',(0,-.025,0),(0,-.04,0),.027,'titanium',p,24)
    return r


def projector():
    r=root('PROJECTOR',(-3.53,1.67,1.652),'v5_portable_projector','桌面便携投影仪',
           'focus_lens',[.44,.34,.27])
    box('Projector_Foot',(0,0,.018),(.34,.24,.033),'black',r,.025)
    box('Projector_Shell',(0,0,.137),(.385,.288,.216),'ceramic',r,.042)
    box('Projector_Inset',(0,-.147,.142),(.327,.012,.154),'graphite',r,.026)
    box('Projector_Top',(0,.015,.245),(.277,.198,.014),'blue',r,.025)
    for i in range(5):
        box('Projector_CoolingSlot_%d'%i,(.195,-.072+i*.035,.142),(.007,.016,.084),'graphite',r,.003)
    lens=group('PROJECTOR_LENS_Pivot',(-.063,-.162,.142),'v5_projector_lens',r,'rotate')
    cylinder('Projector_LensBarrel',(0,.005,0),(0,-.044,0),.065,'titanium',lens)
    cylinder('Projector_Optic',(0,-.044,0),(0,-.048,0),.053,'black',lens)
    ring('Projector_LensCoating',(0,-.05,0),.036,.003,'cool',lens,'XZ',steps=32)
    cylinder('Projector_LensPupil',(0,-.052,0),(0,-.054,0),.020,'blue',lens,24,0)
    box('Projector_Signal',(.101,-.155,.127),(.023,.007,.011),'amber',r,.003)
    cylinder('Projector_Power',(.104,.03,.251),(.104,.03,.258),.017,'graphite',r,20)
    return _on_workstation(r)


def magnetic_pen_dock():
    r=root('PEN_DOCK',(-2.00,1.96,1.652),'v5_magnetic_pen_dock','磁吸创作笔座',
           'tilt_stylus',[.31,.28,.40])
    box('PenDock_Foot',(0,0,.023),(.304,.256,.04),'titanium',r,.027)
    box('PenDock_OrangeInset',(0,0,.050),(.269,.219,.015),'orange',r,.022)
    # Three ceramic magnetic cradles, each a real product shape with an open centre.
    for i,(x,y,h) in enumerate([(-.078,.018,.22),(.0,.035,.27),(.078,.048,.24)]):
        cylinder('PenDock_Cradle_%d'%i,(x,y,.052),(x,y,.12),.030,'graphite',r,24)
        ring('PenDock_CradleLip_%d'%i,(x,y,.12),.027,.003,'titanium',r,steps=24)
        penparent=r
        if i==1:
            penparent=group('MAGNETIC_STYLUS_Pivot',(x,y,.107),'v5_magnetic_stylus',r,'tilt')
            a=(0,0,0);b=(.038,.011,h)
        else:a=(x,y,.10);b=(x+.028,y+.008,.10+h)
        cylinder('PenDock_Stylus_%d'%i,a,b,.010,'titanium' if i==1 else 'blue',penparent,16,.001)
        tip=Vector(b);cylinder('PenDock_Cap_%d'%i,tip,tip+Vector((.002,0,.019)),.0105,'amber' if i==1 else 'ceramic',penparent,16,.001)
    box('PenDock_Status',(0,-.111,.066),(.071,.003,.008),'cool',r,.002)
    return _on_workstation(r)


def stacked_cases():
    r=root('MODULAR_CASES',(1.30,1.52,.18),'v5_modular_equipment_cases','双层模块器材箱',
           'lift_upper_case',[.95,.65,.83])
    for i,(cx,cy,z,w,d,h) in enumerate([(0,0,.205,.91,.60,.39),(.044,.03,.615,.79,.55,.35)]):
        par=r
        if i:
            par=group('UPPER_CASE_Pivot',(cx,cy,.438),'v5_upper_equipment_case',r,'lift')
            cx=cy=0;z=.177
        box('Case_%d_Body'%i,(cx,cy,z),(w,d,h),'blue' if i else 'graphite',par,.052)
        box('Case_%d_Lid'%i,(cx,cy,z+h*.46),(w+.012,d+.008,.055),'titanium',par,.023)
        box('Case_%d_FrontInset'%i,(cx,cy-d*.5-.004,z),(w*.77,.017,h*.64),'graphite',par,.024)
        for side in [-1,1]:
            box('Case_%d_SideGuard_%d'%(i,side),(cx+side*w*.37,cy-d*.5-.018,z),(.066,.026,h*.72),
                'orange' if i else 'titanium',par,.012)
        box('Case_%d_HandleShadow'%i,(cx,cy-d*.5-.024,z+.025),(.225,.019,.060),'black',par,.016)
        tube('Case_%d_FoldingHandle'%i,[(cx-.094,cy-d*.5-.042,z+.013),
             (cx-.094,cy-d*.5-.053,z+.070),(cx+.094,cy-d*.5-.053,z+.070),
             (cx+.094,cy-d*.5-.042,z+.013)],.014,'titanium',par)
        for j in range(3):
            box('Case_%d_Readout_%d'%(i,j),(cx-.018+j*.035,cy-d*.5-.017,z-.075),
                (.021,.007,.011),'amber' if j==0 else 'cool',par,.003)
    for x in [-.35,.35]:
        for y in [-.21,.21]:box('Case_Foot',(x,y,.016),(.10,.095,.032),'black',r,.012)
    return r


def geometric_lamp():
    r=root('GEOMETRIC_LAMP',(2.28,.78,.18),'v5_geometric_floor_lamp','薄环几何落地灯',
           'tilt_light_head',[.57,.47,1.82])
    cylinder('Lamp_Foot',(0,0,.017),(0,0,.069),.246,'graphite',r,40)
    ring('Lamp_FootTrim',(0,0,.057),.231,.007,'titanium',r,steps=40)
    # Double flat rails rise through a warm lens ring, echoing the room frame.
    for x in [-.058,.058]:
        box('Lamp_Stem',(x,.03,.792),(.022,.034,1.465),'titanium',r,.006)
    box('Lamp_StemAmberSeam',(0,.012,.824),(.007,.009,1.26),'amber',r,.002)
    head=group('LAMP_HEAD_Pivot',(0,.028,1.494),'v5_floor_lamp_head',r,'tilt')
    head.rotation_euler.x=math.radians(-11)
    ring('Lamp_HeadOuter',(0,0,0),.267,.028,'titanium',head,'XZ')
    ring('Lamp_HeadRecess',(0,-.016,0),.236,.011,'graphite',head,'XZ')
    ring('Lamp_HeadDiffuser',(0,-.027,0),.238,.010,'warm',head,'XZ')
    for x in [-.083,.083]:
        cylinder('Lamp_HeadHinge',(x-.012,.004,-.239),(x+.012,.004,-.239),.029,'graphite',head,24)
    return r


def energy_capsules():
    r=root('CAPSULE_RACK',(.34,2.77,1.427),'v5_energy_capsule_rack','窗台能量胶囊架',
           'lift_capsule',[.39,.27,.33])
    box('CapsuleRack_Foot',(0,0,.015),(.387,.262,.028),'titanium',r,.026)
    box('CapsuleRack_Dock',(0,.023,.057),(.348,.197,.067),'graphite',r,.022)
    for i,x in enumerate([-.11,0,.11]):
        capsule=r
        ox=x;zbase=.076
        if i==1:
            capsule=group('ENERGY_CAPSULE_Pivot',(x,0,.076),'v5_energy_capsule',r,'lift')
            ox=0;zbase=0
        cylinder('Capsule_%d_Body'%i,(ox,0,zbase),(ox,0,zbase+.181),.040,'blue' if i==0 else 'ceramic',capsule,24)
        cylinder('Capsule_%d_Cap'%i,(ox,0,zbase+.181),(ox,0,zbase+.215),.043,'titanium',capsule,24)
        ring('Capsule_%d_StatusBand'%i,(ox,0,zbase+.161),.041,.006,'amber' if i==1 else 'cool',capsule,steps=24)
        box('Capsule_%d_Inset'%i,(ox,-.039,zbase+.084),(.028,.006,.086),'graphite',capsule,.009)
    box('CapsuleRack_Status',(0,-.112,.047),(.156,.004,.009),'cool',r,.002)
    return r


def mechanical_panel():
    r=root('MECHANICAL_PANEL',(-4.76,-1.93,2.32),'v5_mechanical_data_panel','左墙机械数据面板',
           'rotate_selector',[.13,.49,.76])
    r.rotation_euler.z=math.pi/2
    box('DataPanel_Frame',(0,0,0),(.454,.073,.698),'titanium',r,.036)
    box('DataPanel_Face',(0,-.045,0),(.399,.026,.647),'graphite',r,.025)
    box('DataPanel_OpticalDisplay',(0,-.061,.168),(.328,.011,.227),'black',r,.018)
    # Purely abstract signal chart: no fake biography, metrics, or brand symbols.
    for i,h in enumerate([.06,.10,.08,.15,.124,.067,.116]):
        box('DataPanel_Signal_%d'%i,(-.127+i*.042,-.069,.094+h*.5),(.018,.005,h),
            'amber' if i==3 else 'cool',r,.003)
    for i,z in enumerate([-.244,-.205,-.166]):
        box('DataPanel_Rib_%d'%i,(-.067,-.070,z),(.17,.011,.011),'blue',r,.002)
    dial=group('DATA_SELECTOR_Pivot',(.110,-.077,-.170),'v5_data_panel_selector',r,'rotate')
    cylinder('DataPanel_Selector',(0,0,0),(0,-.035,0),.053,'titanium',dial,24)
    box('DataPanel_SelectorMarker',(0,-.037,.031),(.007,.004,.024),'amber',dial,.002)
    for x in [-.165,.165]:
        for z in [-.293,.293]:cylinder('DataPanel_Screw',(x,-.060,z),(x,-.065,z),.009,'black',r,12,0)
    return r


def scout_display():
    r=root('SCOUT_DISPLAY',(-2.19,2.75,1.427),'v5_scout_drone_display','窗台微型探测艇',
           'rotate_scout',[.53,.34,.34])
    box('ScoutDisplay_Base',(0,0,.022),(.47,.285,.043),'graphite',r,.035)
    box('ScoutDisplay_Inlay',(0,0,.047),(.407,.232,.007),'blue',r,.026)
    cylinder('ScoutDisplay_Support',(0,.029,.046),(0,.029,.145),.014,'titanium',r,20)
    p=group('SCOUT_DRONE_Pivot',(0,0,.197),'v5_scout_drone',r,'rotate')
    body=box('Scout_CeramicHull',(0,0,0),(.243,.235,.090),'ceramic',p,.036)
    box('Scout_OpticalVisor',(0,-.122,.002),(.125,.020,.037),'black',p,.012)
    for x in [-.026,.026]:
        cylinder('Scout_OpticalEye',(x,-.134,.002),(x,-.137,.002),.010,'cool',p,16,0)
    for side in [-1,1]:
        box('Scout_Wing_%d'%side,(side*.176,.028,.006),(.177,.097,.020),'titanium',p,.010,
            (0,math.radians(side*9),math.radians(side*-12)))
        cylinder('Scout_Thruster_%d'%side,(side*.198,.039,-.038),(side*.198,.039,.038),.049,'graphite',p,24)
        ring('Scout_ThrusterLight_%d'%side,(side*.198,.039,.040),.035,.005,'amber',p,steps=24)
    box('Scout_CrownFin',(0,.026,.061),(.021,.146,.052),'blue',p,.012)
    return r


def _closest_owner(o):
    p=o.parent
    while p is not None:
        if p.get('asset_id'):return p
        p=p.parent
    return None


def _consolidate():
    """Snapshot all evaluated geometry before mutating the scene datablocks.

    Blender 5.1's dependency graph can still reference an earlier evaluated
    mesh when another owner's evaluated_get() triggers a graph update. Removing
    an original object/data pair inside that read loop can invalidate those
    references. Keep the read pass completely separate from the write pass.
    """
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    owners=[o for o in C.objects if o.get('asset_id')]
    original_meshes=[o for o in C.objects if o.type=='MESH']
    snapshots=[]
    # Phase 1: pure reads. Only plain Python geometry/material references survive
    # this phase; every temporary evaluated mesh is released immediately.
    for owner in owners:
        source=[o for o in original_meshes if _closest_owner(o)==owner]
        if not source:continue
        verts=[];faces=[];indices=[];smooth=[];materials=[]
        inv=owner.matrix_world.inverted()
        for o in source:
            ev=o.evaluated_get(deps);d=ev.to_mesh()
            try:
                xform=inv @ o.matrix_world
                off=len(verts);verts.extend(tuple(xform @ v.co) for v in d.vertices)
                slots=[]
                for m in d.materials:
                    if m not in materials:materials.append(m)
                    slots.append(materials.index(m))
                for f in d.polygons:
                    faces.append(tuple(off+i for i in f.vertices))
                    indices.append(slots[f.material_index] if slots else 0)
                    smooth.append(f.use_smooth)
            finally:
                ev.to_mesh_clear()
        snapshots.append((owner,verts,faces,indices,smooth,materials))
    # Drop Python references to evaluated IDs before creating or removing IDs.
    d=None;ev=None;deps=None
    # Phase 2: create the final meshes from the detached snapshots. No further
    # dependency-graph evaluation occurs until all old objects are unlinked.
    for owner,verts,faces,indices,smooth,materials in snapshots:
        d=bpy.data.meshes.new(owner.name+'_ConsolidatedMesh')
        d.from_pydata(verts,[],faces);d.validate(clean_customdata=False);d.update()
        for m in materials:d.materials.append(m)
        for f,idx,sm in zip(d.polygons,indices,smooth):f.material_index=idx;f.use_smooth=sm
        ob=bpy.data.objects.new(owner.name+'_Geometry',d);C.objects.link(ob)
        ob.parent=owner;ob.matrix_parent_inverse=Matrix.Identity(4)
        ob['generated_revision']=5
        # Durable base UVs; the dedicated bake stage replaces these with its atlas.
        uv=d.uv_layers.new(name='UVMap')
        for f in d.polygons:
            axis=max(range(3),key=lambda k:abs(f.normal[k]))
            axes=[i for i in range(3) if i!=axis]
            for li in f.loop_indices:
                v=d.vertices[d.loops[li].vertex_index].co
                uv.data[li].uv=(v[axes[0]],v[axes[1]])
    for original in original_meshes:
        bpy.data.objects.remove(original,do_unlink=True)
    # Do not manually delete the orphaned source mesh datablocks during graph
    # rebuilding. They have zero users and Blender excludes them on normal save.
    bpy.context.view_layer.update()


def build(consolidate=True):
    """Build in the active source scene; return an export/interaction manifest."""
    global C
    ROOTS.clear();MANIFEST.clear()
    C=bpy.data.collections.get(COLLECTION)
    if C is not None:
        for o in list(C.all_objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(C)
    C=bpy.data.collections.new(COLLECTION)
    bpy.context.scene.collection.children.link(C)
    _materials()
    for fn in [orbital_clock,projector,magnetic_pen_dock,stacked_cases,
               geometric_lamp,energy_capsules,mechanical_panel,scout_display]:
        fn()
    if consolidate:_consolidate()
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get();triangles=0
    for o in C.objects:
        if o.type!='MESH':continue
        ev=o.evaluated_get(deps);d=ev.to_mesh();d.calc_loop_triangles()
        triangles+=len(d.loop_triangles);ev.to_mesh_clear()
    for entry in MANIFEST:
        r=bpy.data.objects[entry['root']]
        entry['independent_parts']=[{'name':o.name,'asset_id':o['asset_id'],
            'interaction':o.get('interaction','inspect')} for o in r.children if o.get('asset_id')]
    return {'collection':COLLECTION,'source_scene':bpy.context.scene.name,
            'root_count':len(ROOTS),'interactive_group_count':sum(bool(o.get('asset_id')) for o in C.objects),
            'mesh_count':sum(o.type=='MESH' for o in C.objects),'triangles':triangles,
            'triangle_budget':45000,'within_budget':triangles<=45000,
            'materials':[m.name for m in M.values()],'assets':MANIFEST.copy()}


run=build
if __name__=='__main__':
    import json
    print(json.dumps(build(),ensure_ascii=False,indent=2))
