"""Original radial skill-study machine for the About Nexus V2 approval model.

Only build_skill_engine(api) creates objects. The caller owns the Blender scene,
materials, lights, camera, placement, rendering and export. The returned main
root is at (0, 0, 0), with its feet on Z=0; front is -Y and up is +Z.

The three instruments are symbolic display containers, not claims about the
owner's skills. They share a mechanical turntable instead of separate plinths.
"""

from math import atan2, cos, sin, pi, radians

from mathutils import Vector


def build_skill_engine(api):
    root, box, cylinder = api['root'], api['box'], api['cylinder']
    tube, mesh, text = api['tube'], api['mesh'], api['text']
    mats = api['mats']
    for key in ('navy', 'metal', 'dark', 'ivory', 'orange', 'brass',
                'glass', 'light', 'wood', 'rubber'):
        if key not in mats:
            raise KeyError('Skill engine needs material: ' + key)

    def assembly(asset_id, parent=None, location=(0, 0, 0), kind='mechanical-part'):
        obj = root(asset_id, location)
        obj.parent = parent
        obj['asset_id'] = asset_id
        obj['component_kind'] = kind
        obj['content_status'] = '技能资料待补充'
        return obj

    def finish_mesh(name, vertices, faces, material, parent, bevel=0, smooth=False):
        obj = mesh(name, vertices, faces, material, parent)
        for polygon in obj.data.polygons:
            polygon.use_smooth = smooth
        if bevel:
            modifier = obj.modifiers.new('Machined edge radius', 'BEVEL')
            modifier.width = bevel
            modifier.segments = 3
            modifier.use_clamp_overlap = True
            modifier.harden_normals = True
            normal = obj.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
            normal.keep_sharp = True
        return obj

    def lathe(name, levels, material, parent, sides=64, phase=0, smooth=True):
        vertices, rings, faces = [], [], []
        for z, radius in levels:
            if radius == 0:
                rings.append([len(vertices)])
                vertices.append((0, 0, z))
            else:
                rings.append(list(range(len(vertices), len(vertices) + sides)))
                vertices.extend((radius * cos(phase + i * 2 * pi / sides),
                                 radius * sin(phase + i * 2 * pi / sides), z)
                                for i in range(sides))
        for bottom, top in zip(rings, rings[1:]):
            for i in range(sides):
                j = (i + 1) % sides
                if len(bottom) == 1:
                    faces.append((bottom[0], top[j], top[i]))
                elif len(top) == 1:
                    faces.append((bottom[i], bottom[j], top[0]))
                else:
                    faces.append((bottom[i], bottom[j], top[j], top[i]))
        if len(rings[0]) > 1:
            faces.append(tuple(reversed(rings[0])))
        if len(rings[-1]) > 1:
            faces.append(tuple(rings[-1]))
        return finish_mesh(name, vertices, faces, material, parent, smooth=smooth)

    def annulus(name, outer, inner, depth, material, parent, loc=(0, 0, 0), sides=64):
        vertices = [(r * cos(i * 2 * pi / sides), r * sin(i * 2 * pi / sides), z)
                    for z in (-depth / 2, depth / 2) for r in (outer, inner)
                    for i in range(sides)]
        faces = []
        for i in range(sides):
            j = (i + 1) % sides
            faces.extend(((i, j, 2 * sides + j, 2 * sides + i),
                          (sides + j, sides + i, 3 * sides + i, 3 * sides + j),
                          (2 * sides + i, 2 * sides + j, 3 * sides + j, 3 * sides + i),
                          (j, i, sides + i, sides + j)))
        obj = finish_mesh(name, vertices, faces, material, parent, bevel=.0015)
        obj.location = loc
        return obj

    def rod(name, start, end, radius, material, parent, vertices=32):
        a, b = Vector(start), Vector(end)
        obj = cylinder(name, tuple((a + b) / 2), radius, (b - a).length,
                       material, parent, vertices=vertices)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = (b - a).to_track_quat('Z', 'Y')
        return obj

    def beam(name, start, end, width, depth, material, parent, bevel=.012):
        a, b = Vector(start), Vector(end)
        obj = box(name, tuple((a + b) / 2), (width, depth, (b - a).length),
                  material, parent, bevel=bevel)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = (b - a).to_track_quat('Z', 'Y')
        return obj

    def ring_line(name, radius, z, thickness, material, parent, sx=1, sy=1, segments=72):
        return tube(name, [(sx * radius * cos(i * 2 * pi / segments),
                            sy * radius * sin(i * 2 * pi / segments), z)
                           for i in range(segments + 1)], thickness, material, parent)

    def screw(name, loc, parent, radius=.016, direction=(0, 0, 1), material=None):
        material = material or mats['metal']
        a = Vector(loc)
        d = Vector(direction).normalized()
        bolt = rod(name, a - d * .004, a + d * .004, radius, material, parent, vertices=6)
        return bolt

    def contour(width, height, radius, cy=0, steps=8):
        points = []
        for x, y, angle in ((width / 2 - radius, height / 2 - radius, 0),
                            (-width / 2 + radius, height / 2 - radius, pi / 2),
                            (-width / 2 + radius, -height / 2 + radius, pi),
                            (width / 2 - radius, -height / 2 + radius, 3 * pi / 2)):
            for i in range(steps + 1):
                a = angle + i * pi / (2 * steps)
                points.append((x + radius * cos(a), cy + y + radius * sin(a)))
        return points

    def swatch_leaf(name, material, parent):
        # A closed plate with a real axle hole, not intersecting stacked cubes.
        outside = contour(.188, .55, .04, cy=.22)
        inside = [(.026 * cos(atan2(z, x)), .026 * sin(atan2(z, x)))
                  for x, z in outside]
        count = len(outside)
        vertices = [(x, y, z) for y in (-.009, .009)
                    for loop in (outside, inside) for x, z in loop]
        faces = []
        for i in range(count):
            j = (i + 1) % count
            # Reverse the usual XY extrusion winding for the XZ plane.
            faces.extend(tuple(reversed(f)) for f in (
                (i, j, 2 * count + j, 2 * count + i),
                (count + j, count + i, 3 * count + i, 3 * count + j),
                (2 * count + i, 2 * count + j, 3 * count + j, 3 * count + i),
                (j, i, count + i, count + j)))
        # The rounded contour already defines the edge. A bevel at the narrow
        # pivot creates collapsed slivers; keep this thin closed frame explicit.
        return finish_mesh(name, vertices, faces, material, parent, bevel=0)

    engine = assembly('about.nexus.skill.engine', kind='radial-skill-workstation')
    engine['design_revision'] = 'about-nexus-v2'
    engine['module_origin'] = 'bottom-centre'
    engine['placeholder'] = True
    engine['motion_hint'] = 'Turn the upper carriage slowly; preserve every tool pivot.'

    # Three grounded feet and angled cast struts support the complete machine.
    for index, angle in enumerate((pi / 6, 5 * pi / 6, 3 * pi / 2)):
        x, y = .69 * cos(angle), .69 * sin(angle)
        pad = cylinder(f'nexus.skill.foot.{index}', (x, y, .038), .13, .076,
                       mats['rubber'], engine, vertices=48)
        pad.scale.x = 1.5
        pad.rotation_euler.z = angle
        shoe = cylinder(f'nexus.skill.foot_cap.{index}', (x, y, .082), .135, .023,
                        mats['metal'], engine, vertices=48)
        shoe.scale.x = 1.5
        shoe.rotation_euler.z = angle
        beam(f'nexus.skill.cast_leg.{index}', (x, y, .099),
             (.12 * cos(angle), .12 * sin(angle), .317), .13, .18,
             mats['navy'], engine, bevel=.021)
        rod(f'nexus.skill.leg_inlay.{index}', (.58 * cos(angle), .58 * sin(angle), .147),
            (.18 * cos(angle), .18 * sin(angle), .302), .011, mats['metal'], engine)
        screw(f'nexus.skill.foot_fastener.{index}', (x, y, .098), engine, radius=.019)
    lathe('nexus.skill.central_pedestal', ((.078, .16), (.118, .22), (.196, .244),
                                        (.354, .187), (.405, .245), (.425, .245)),
          mats['navy'], engine)
    cylinder('nexus.skill.pedestal_collar', (0, 0, .327), .207, .044, mats['brass'], engine)
    cylinder('nexus.skill.turntable_bearing', (0, 0, .425), .32, .047, mats['dark'], engine)

    carriage = assembly('about.nexus.skill.carriage', engine, kind='turntable-carriage')
    carriage['motion_hint'] = 'Local Z yaw; all three radial tool bases travel together.'
    undertray = cylinder('nexus.skill.underside_casting', (0, 0, .452), 1, .068,
                         mats['navy'], carriage, vertices=96)
    undertray.scale = (1.255, .962, 1)
    perimeter = annulus('nexus.skill.continuous_metal_rim', 1, .951, .102, mats['metal'], carriage,
                        loc=(0, 0, .505), sides=96)
    perimeter.scale = (1.280, .995, 1)
    tabletop = cylinder('nexus.skill.warm_wood_inlay', (0, 0, .505), 1, .100,
                        mats['wood'], carriage, vertices=96)
    tabletop.scale = (1.218, .946, 1)
    # Two fine inlay paths and edge fasteners follow the single shared tabletop.
    ring_line('nexus.skill.wood_brass_inlay', 1, .556, .0025, mats['brass'], carriage, 1.137, .865)
    ring_line('nexus.skill.rim_shadow_reveal', 1, .470, .003, mats['dark'], carriage, 1.279, .994)
    for index in range(18):
        a = index * 2 * pi / 18
        screw(f'nexus.skill.rim_bolt.{index:02d}', (1.247 * cos(a), .970 * sin(a), .559),
              carriage, radius=.011)
    cylinder('nexus.skill.central_hub_seal', (0, 0, .563), .198, .016, mats['rubber'], carriage)
    cylinder('nexus.skill.central_hub', (0, 0, .592), .173, .044, mats['navy'], carriage)
    cylinder('nexus.skill.central_hub_cap', (0, 0, .621), .127, .015, mats['brass'], carriage)
    for index in range(8):
        a = index * 2 * pi / 8
        screw(f'nexus.skill.hub_bolt.{index}', (.104 * cos(a), .104 * sin(a), .632),
              carriage, radius=.008)
    anchors = ((-.72, .26), (-.06, -.46), (.68, .23))
    for index, (x, y) in enumerate(anchors):
        length = (x * x + y * y) ** .5
        direction = (x / length, y / length)
        a = (.15 * direction[0], .15 * direction[1], .573)
        b = (x, y, .573)
        rail = box(f'nexus.skill.radial_rail.{index}',
                   tuple((a[k] + b[k]) / 2 for k in range(3)),
                   (length - .15, .065, .036), mats['dark'], carriage, bevel=.008)
        rail.rotation_euler.z = atan2(y, x)
        for j in range(3):
            t = .42 + .18 * j
            screw(f'nexus.skill.rail_pin.{index}.{j}',
                  (x * t, y * t, .595), carriage, radius=.009, material=mats['brass'])

    # Left rear: an exploded polyhedral sample held by a working gimbal fork.
    geometry = assembly('about.nexus.skill.geometry', carriage, (*anchors[0], .555), 'geometry-instrument')
    geometry.rotation_euler.z = radians(-8)
    cylinder('nexus.skill.geometry.mount', (0, 0, .018), .191, .036, mats['metal'], geometry)
    cylinder('nexus.skill.geometry.yaw_joint', (0, 0, .064), .117, .064, mats['navy'], geometry)
    lathe('nexus.skill.geometry.column', ((.096, .077), (.120, .073), (.253, .055), (.278, .09)),
          mats['metal'], geometry, sides=48)
    box('nexus.skill.geometry.crossmember', (0, 0, .269), (.54, .106, .07), mats['navy'], geometry, bevel=.025)
    for index, side in enumerate((-1, 1)):
        beam(f'nexus.skill.geometry.fork.{index}', (side * .23, 0, .269),
             (side * .331, 0, .859), .061, .078, mats['navy'], geometry)
        rod(f'nexus.skill.geometry.bearing.{index}', (side * .224, 0, .858),
            (side * .387, 0, .858), .052, mats['brass'], geometry, vertices=48)
        screw(f'nexus.skill.geometry.lock.{index}', (side * .391, 0, .858), geometry,
              radius=.026, direction=(side, 0, 0), material=mats['orange'])
    geo_head = assembly('about.nexus.skill.geometry.head', geometry, (0, 0, .858), 'gimballed-sample')
    geo_head['motion_hint'] = 'Local X tilt about the paired bearings.'
    rod('nexus.skill.geometry.central_guide', (0, 0, -.283), (0, 0, .330),
        .021, mats['dark'], geo_head)
    cap_specs = (
        ('lower', ((-.280, .055), (-.255, .087), (-.120, .235)), 'ivory'),
        ('band', ((-.050, .270), (.050, .270)), 'metal'),
        ('upper', ((.120, .235), (.310, .065), (.350, 0)), 'navy'),
    )
    for label, levels, material_name in cap_specs:
        component = assembly('about.nexus.skill.geometry.' + label, geo_head, kind='removable-polyhedral-component')
        component['motion_hint'] = 'Short axial separation; return to its authored transform.'
        lathe('nexus.skill.geometry.' + label + '.faceted_shell', levels, mats[material_name],
              component, sides=6, phase=pi / 6, smooth=False)
        z, radius = levels[0] if label == 'upper' else levels[-1]
        tube('nexus.skill.geometry.' + label + '.edge_trace',
             [(radius * cos(pi / 6 + i * pi / 3), radius * sin(pi / 6 + i * pi / 3), z)
              for i in range(7)], .0027, mats['brass'], component)
    for index, a in enumerate((pi / 6, 5 * pi / 6, 3 * pi / 2)):
        for lo, hi in ((-.124, -.046), (.046, .124)):
            rod(f'nexus.skill.geometry.registration_pin.{index}.{lo}',
                (.12 * cos(a), .12 * sin(a), lo), (.12 * cos(a), .12 * sin(a), hi),
                .007, mats['brass'], geo_head, vertices=16)

    # Foreground: a genuine five-leaf material fan around a shared horizontal
    # axle. The leaf roots differ in depth, so the fan opens without coplanar
    # fighting; each leaf has a real 52 mm diameter pivot hole.
    swatches = assembly('about.nexus.skill.swatches', carriage, (*anchors[1], .555), 'material-sample-fan')
    swatches.rotation_euler.z = radians(-15)
    cylinder('nexus.skill.swatches.mount', (0, 0, .018), .195, .036, mats['metal'], swatches)
    beam('nexus.skill.swatches.stem', (0, .02, .035), (0, .02, .232),
         .061, .095, mats['navy'], swatches)
    for index, y in enumerate((-.108, .108)):
        beam(f'nexus.skill.swatches.fork.{index}', (0, y * .20, .190),
             (0, y, .320), .080, .047, mats['navy'], swatches, bevel=.018)
    rod('nexus.skill.swatches.common_axle', (0, -.142, .321), (0, .142, .321),
        .022, mats['brass'], swatches, vertices=48)
    for index, y in enumerate((-.148, .148)):
        rod(f'nexus.skill.swatches.axle_cap.{index}', (0, y - .006, .321), (0, y + .006, .321),
            .040, mats['orange'], swatches, vertices=32)
    for index, (angle, material_name) in enumerate(zip((-50, -25, 0, 25, 50),
                                                     ('ivory', 'wood', 'metal', 'navy', 'glass'))):
        leaf = assembly(f'about.nexus.skill.swatch.{index + 1:02d}', swatches,
                        (0, -.062 + index * .031, .321), 'rotating-material-leaf')
        leaf.rotation_euler.y = radians(angle)
        leaf['motion_hint'] = 'Local Y rotation around the common axle; keep its depth layer.'
        swatch_leaf(f'nexus.skill.swatch.{index}.frame', mats['metal'], leaf)
        box(f'nexus.skill.swatch.{index}.sample', (0, -.014, .276), (.143, .008, .325),
            mats[material_name], leaf, bevel=.006)
        # A tiny neutral index notch gives the fan a tool-like, machined edge.
        box(f'nexus.skill.swatch.{index}.index', (0, -.014, .470), (.046, .008, .009),
            mats['orange'] if index == 2 else mats['dark'], leaf, bevel=.002)
        if material_name == 'metal':
            for j in range(3):
                tube(f'nexus.skill.swatch.{index}.finish_groove.{j}',
                     [(-.052, -.019, .247 + j * .030), (.052, -.019, .247 + j * .030)],
                     .0015, mats['dark'], leaf)

    # Right rear: a hollow optical barrel, layered glass, iris and independently
    # hinged shading blades. Bearings hold it above the table at an X-axis pivot.
    optics = assembly('about.nexus.skill.optics', carriage, (*anchors[2], .555), 'optical-instrument')
    optics.rotation_euler.z = radians(8)
    cylinder('nexus.skill.optics.mount', (0, 0, .018), .205, .036, mats['metal'], optics)
    cylinder('nexus.skill.optics.swivel', (0, 0, .076), .117, .080, mats['navy'], optics)
    lathe('nexus.skill.optics.column', ((.116, .075), (.130, .065), (.233, .065), (.260, .090)),
          mats['metal'], optics, sides=48)
    box('nexus.skill.optics.crossmember', (0, 0, .262), (.655, .12, .08), mats['navy'], optics, bevel=.024)
    for index, side in enumerate((-1, 1)):
        beam(f'nexus.skill.optics.fork.{index}', (side * .279, 0, .263),
             (side * .347, 0, .790), .066, .090, mats['navy'], optics)
        rod(f'nexus.skill.optics.bearing.{index}', (side * .279, 0, .790),
            (side * .394, 0, .790), .056, mats['brass'], optics, vertices=48)
        screw(f'nexus.skill.optics.tilt_lock.{index}', (side * .399, 0, .790), optics,
              radius=.030, direction=(side, 0, 0), material=mats['orange'])
    optic_head = assembly('about.nexus.skill.optics.head', optics, (0, 0, .790), 'tilting-lens-head')
    optic_head.rotation_euler.x = pi / 2
    optic_head['motion_hint'] = 'Local X pitch about the paired side bearings.'
    annulus('nexus.skill.optics.hollow_barrel', .285, .210, .280, mats['navy'], optic_head)
    cylinder('nexus.skill.optics.rear_cap', (0, 0, -.149), .269, .020, mats['dark'], optic_head)
    for z in (-.114, -.068):
        annulus('nexus.skill.optics.focus_ring', .299, .279, .020, mats['metal'], optic_head, loc=(0, 0, z))
    for index in range(20):
        a = index * 2 * pi / 20
        grip = box(f'nexus.skill.optics.focus_knurl.{index:02d}',
                   (.294 * cos(a), .294 * sin(a), -.069), (.013, .029, .042),
                   mats['dark'], optic_head, bevel=.003)
        grip.rotation_euler.z = a
    annulus('nexus.skill.optics.internal_baffle', .209, .050, .014, mats['dark'], optic_head, loc=(0, 0, .080))
    for index in range(7):
        a = index * 2 * pi / 7
        verts = [(.052 * cos(a), .052 * sin(a), .090),
                 (.184 * cos(a + .20), .184 * sin(a + .20), .090),
                 (.181 * cos(a + .82), .181 * sin(a + .82), .090),
                 (.065 * cos(a + .92), .065 * sin(a + .92), .090)]
        blade = finish_mesh(f'nexus.skill.optics.iris_leaf.{index}', verts, [(0, 1, 2, 3)],
                            mats['metal'], optic_head)
        solidify = blade.modifiers.new('Iris leaf gauge', 'SOLIDIFY')
        solidify.thickness = .002
    cylinder('nexus.skill.optics.aperture_core', (0, 0, .077), .046, .010, mats['light'], optic_head)
    cylinder('nexus.skill.optics.front_glass', (0, 0, .120), .207, .022, mats['glass'], optic_head, vertices=96)
    annulus('nexus.skill.optics.front_retainer', .296, .214, .027, mats['metal'], optic_head,
            loc=(0, 0, .154), sides=80)
    annulus('nexus.skill.optics.amber_gasket', .303, .288, .013, mats['orange'], optic_head,
            loc=(0, 0, .143), sides=64)
    for index in range(8):
        a = index * pi / 4
        screw(f'nexus.skill.optics.face_bolt.{index}', (.254 * cos(a), .254 * sin(a), .171),
              optic_head, radius=.010, material=mats['brass'])
    for index in range(4):
        a = index * pi / 2
        # Local +Y is each leaf's outward direction; local +Z faces the viewer.
        door = assembly(f'about.nexus.skill.optics.shade.{index + 1:02d}', optic_head,
                        (-.306 * sin(a), .306 * cos(a), .178), 'hinged-shading-leaf')
        door.rotation_euler = (radians(18), 0, a)
        door['motion_hint'] = 'Local X hinge, opening away from the optical aperture.'
        vertices = [(x, y, z) for z in (-.007, .007)
                    for x, y in ((-.158, 0), (.158, 0), (.217, .230), (-.217, .230))]
        faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        finish_mesh(f'nexus.skill.optics.shade.{index}.blade', vertices, faces,
                    mats['dark'], door, bevel=.004)
        rod(f'nexus.skill.optics.shade.{index}.hinge', (-.153, 0, 0), (.153, 0, 0),
            .012, mats['brass'], door)
        tube(f'nexus.skill.optics.shade.{index}.edge_trim',
             [(-.213, .225, .009), (.213, .225, .009)], .0025, mats['metal'], door)
        # Short fixed lug connects every hinge to the retainer; no floating doors.
        lug = box(f'nexus.skill.optics.shade_lug.{index}',
                  (-.291 * sin(a), .291 * cos(a), .174), (.125, .044, .026),
                  mats['navy'], optic_head, bevel=.007)
        lug.rotation_euler.z = a

    # Routed service cable is held by the optical column, then returns to its
    # own radial carriage. It does not cross the fan or the geometry instrument.
    tube('nexus.skill.optics.service_cable', [(.084, 0, .228), (.086, 0, .163),
         (.148, .140, .095), (.094, .178, .062), (.038, .145, .042)],
         .011, mats['rubber'], optics)
    for index, z in enumerate((.174, .219)):
        box(f'nexus.skill.optics.cable_clip.{index}', (.068, 0, z), (.028, .035, .014),
             mats['metal'], optics, bevel=.004)

    # A single factual placeholder sits on the machine's front edge. No score,
    # named software, occupation or invented personal proficiency is implied.
    plaque = assembly('about.nexus.skill.label', carriage, kind='pending-skill-caption')
    for x in (-.280, .280):
        beam('nexus.skill.caption_support', (x, -.870, .554), (x, -.906, .648),
             .022, .025, mats['metal'], plaque, bevel=.006)
    box('nexus.skill.caption_plate', (0, -.910, .650), (.780, .035, .130), mats['navy'], plaque, bevel=.013)
    box('nexus.skill.caption_orange_tick', (-.342, -.930, .650), (.014, .006, .065),
        mats['orange'], plaque, bevel=.003)
    caption = text('nexus.skill.pending_caption', '技能资料待补充', (.022, -.931, .650),
                   .077, mats['ivory'], plaque, rotation=(pi / 2, 0, 0))
    if hasattr(caption.data, 'align_x'):
        caption.data.align_x = 'CENTER'
    if hasattr(caption.data, 'align_y'):
        caption.data.align_y = 'CENTER'
    assert tuple(engine.location) == (0, 0, 0), 'Skill engine root must remain at the origin.'
    return engine
