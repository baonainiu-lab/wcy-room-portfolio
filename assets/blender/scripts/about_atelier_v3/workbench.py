"""Archive atelier workbench, authored in metres with Blender Z up.

Only build() creates objects. Small props have stable independent asset roots;
all decorative drawings below are original geometry, with no borrowed artwork.
"""
import math
from mathutils import Vector
import kit as K


TABLE_TOP = 1.65
FLOOR = .36
BOARD_FRONT = 1.76
LAMP_MOUTH = (1.43, .14, 3.20)
LAMP_TARGET = (1.35, -.28, 1.66)
PREFIX = 'about.workbench.'


def asset(name, location):
    return K.root(PREFIX + name, location)


def square_bar(name, a, b, width, depth, material, parent):
    a, b = Vector(a), Vector(b)
    obj = K.box(name, (a + b) / 2, (width, depth, (b - a).length),
                material, parent, min(width, depth) * .16)
    obj.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    return obj


def axis_cylinder(name, location, radius, length, material, parent, axis='Y', vertices=48):
    obj = K.cylinder(name, location, radius, length, material, parent, vertices)
    if axis == 'Y':
        obj.rotation_euler.x = math.pi / 2
    elif axis == 'X':
        obj.rotation_euler.y = math.pi / 2
    return obj


def book(name, location, width=.45, depth=.34, height=.064, cover='navy', angle=0):
    root = asset(name, location)
    root.rotation_euler.z = angle
    K.box(name + '.pages', (0, 0, height / 2), (width - .016, depth - .018, height - .014), K.M['paper'], root, .002)
    for z in [.005, height - .005]:
        K.box(name + '.cover', (0, 0, z), (width, depth, .010), K.M[cover], root, .003)
    K.box(name + '.cloth_spine', (-width / 2 + .005, 0, height / 2), (.014, depth, height), K.M[cover], root, .003)
    for z in [.023, .033, .045]:
        if z < height - .012:
            K.tube(name + '.paper_edge', [(-width / 2 + .018, -depth / 2 + .006, z), (width / 2 - .008, -depth / 2 + .006, z)], .0006, K.M['wood_dark'], root)
    K.box(name + '.spine_label', (-width / 2 - .003, -.015, height / 2), (.002, depth * .23, height * .43), K.M['ivory'], root, .001)
    return root


def pen(name, location, length=.23, material='wood', tilt=(0, 0, 0)):
    root = asset(name, location)
    root.rotation_euler = tilt
    axis_cylinder(name + '.body', (0, 0, length * .48), .005, length * .82, K.M[material], root, 'Z', 12)
    nib = K.lathe(name + '.nib', [(0, 0), (.002, .007), (.005, .035)], K.M['wood'], root, 20)
    axis_cylinder(name + '.graphite', (0, 0, .003), .0016, .009, K.M['ink'], root, 'Z', 12)
    axis_cylinder(name + '.cap', (0, 0, length * .925), .0057, .019, K.M['brass'], root, 'Z', 20)
    return root


def table():
    root = asset('desk_structure', (1.55, -.30, FLOOR))
    top = TABLE_TOP - FLOOR
    K.box('Desk solid walnut top', (0, 0, top - .062), (3.9, 1.65, .124), K.M['wood'], root, .045)
    K.box('Inset dark leather writing surface', (0, -.005, top + .0035), (3.55, 1.33, .009), K.M['desk_leather'], root, .025)
    # A fine inset brass band terminates before the rounded walnut corner.
    for y in [-.714, .714]:
        K.box('Walnut edge brass inlay', (0, y, top - .001), (3.68, .0032, .0028), K.M['brass'], root, .001)
    for x in [-1.838, 1.838]:
        K.box('Walnut end brass inlay', (x, 0, top - .001), (.0032, 1.425, .0028), K.M['brass'], root, .001)
    # Fine stitched border is separate from the coarse material micro-normal.
    for side in [-1, 1]:
        for i in range(102):
            x = -1.72 + i * .034
            K.tube('Leather saddle stitch', [(x, side * .634, top + .009), (x + .014, side * .634, top + .009)], .00055, K.M['wood_dark'], root)
    for x in [-1.78, 1.78]:
        for y in [-.69, .69]:
            foot = (x * 1.025, y * 1.045, .027)
            upper = (x * .954, y * .90, top - .105)
            square_bar('Splayed square steel trestle', foot, upper, .125, .108, K.M['dark'], root)
            K.box('Rubber levelling foot', (foot[0], foot[1], .019), (.135, .123, .038), K.M['rubber'], root, .009)
            K.box('Leg welded top bracket', (upper[0], upper[1], top - .137), (.21, .19, .026), K.M['metal'], root, .007)
            for dx in [-.065, .065]:
                K.screw('Leg bracket bolt', (upper[0] + dx, upper[1] - .055, top - .12), K.M['brass'], root, (0, 0, 0), .009)
        square_bar('Side low stretcher', (x * 1.016, -.70, .205), (x * 1.016, .70, .205), .075, .068, K.M['dark'], root)
    K.box('Front under-top rail', (0, -.665, top - .155), (3.58, .065, .093), K.M['dark'], root, .011)
    K.box('Rear under-top rail', (0, .665, top - .155), (3.58, .065, .093), K.M['dark'], root, .011)
    # Rear-set storage leaves the front central knee space open.
    K.box('Low shelf steel perimeter', (0, .205, .277), (3.61, .79, .067), K.M['dark'], root, .014)
    K.box('Low shelf walnut deck', (0, .205, .311), (3.48, .71, .025), K.M['wood'], root, .007)
    for x in [-1.11, 1.11]:
        K.box('Shelf rear upright', (x, .566, .715), (.04, .044, .786), K.M['dark'], root, .006)
    return root


def storage():
    # All storage contents are independent roots, so drawers and books can be
    # rebound to interactions without joining them into the desk architecture.
    for i, (x, width, offset) in enumerate([(-.05, .66, 0), (.73, .68, -.15), (2.70, .68, .02)]):
        root = asset('drawer_%02d' % (i + 1), (x, -.53 + offset, 1.335))
        K.box('Drawer floor', (0, 0, -.029), (width, .68, .022), K.M['wood'], root, .006)
        for dx in [-width / 2 + .015, width / 2 - .015]:
            K.box('Drawer side joinery', (dx, 0, .024), (.028, .69, .108), K.M['wood_z'], root, .004)
        K.box('Drawer rear', (0, .321, .023), (width, .025, .106), K.M['wood'], root, .004)
        K.box('Drawer walnut front', (0, -.359, .017), (width + .025, .06, .135), K.M['wood'], root, .007)
        K.box('Drawer label inset', (0, -.391, .036), (.115, .005, .033), K.M['brass'], root, .003)
        K.tube('Drawer bent brass pull', [(-.10, -.395, -.005), (-.10, -.425, -.005), (.10, -.425, -.005), (.10, -.395, -.005)], .009, K.M['brass'], root)
        if i == 1:
            for j in range(3):
                book('drawer_sketch_pad_%02d' % j, (x - .14 + j * .125, -.52 + offset, 1.341), .112, .36, .03, ['paper', 'navy', 'leather'][j])
    for i, (x, z, cover) in enumerate([(-.03, .69, 'navy'), (-.025, .761, 'ivory'), (.0, .815, 'leather'), (.49, .69, 'wood_dark'), (.52, .768, 'navy')]):
        book('shelf_archive_book_%02d' % i, (x, -.06, z), .46, .56, [.067, .05, .074, .075, .055][i], cover)
    root = asset('shelf_archive_crate', (1.05, .0, .69))
    K.box('Archive crate base', (0, 0, .02), (.55, .55, .04), K.M['wood'], root, .006)
    for x in [-.267, .267]:
        K.box('Archive crate sides', (x, 0, .185), (.025, .55, .35), K.M['wood_z'], root, .005)
    for z in [.085, .235]:
        K.box('Archive crate front slat', (0, -.262, z), (.55, .025, .10), K.M['wood'], root, .003)
        K.box('Archive crate back slat', (0, .262, z), (.55, .025, .10), K.M['wood'], root, .003)
    K.panel_label('Archive crate blank label', '', (0, -.28, .235), .18, .052, root)
    for i in range(5):
        folder = asset('shelf_archive_folder_%02d' % i, (.87 + i * .085, .0, .735))
        folder.rotation_euler.y = -.06 + i * .025
        K.box('Folder stiff cover', (0, 0, .20), (.051, .44, .40), K.M[['navy', 'leather', 'ivory'][i % 3]], folder, .004)
        K.box('Folder paper block', (0, -.012, .20), (.039, .401, .382), K.M['paper'], folder, .002)
        K.box('Folder spine stripe', (0, -.225, .265), (.032, .004, .09), K.M['brass'], folder, .002)
    root = asset('shelf_tool_case', (2.10, -.12, .69))
    K.box('Tool case molded body', (0, 0, .205), (.85, .53, .40), K.M['dark'], root, .037)
    K.box('Tool case raised lid', (0, 0, .417), (.86, .54, .062), K.M['navy'], root, .023)
    for x in [-.33, .33]:
        K.box('Tool case reinforced corner', (x, -.252, .209), (.062, .041, .405), K.M['metal'], root, .007)
        K.box('Tool case brass latch', (x * .72, -.285, .361), (.066, .025, .087), K.M['brass'], root, .007)
        axis_cylinder('Tool case latch hinge', (x * .72, -.303, .399), .011, .061, K.M['metal'], root, 'X')
    K.tube('Tool case handle', [(-.14, -.274, .25), (-.14, -.326, .25), (.14, -.326, .25), (.14, -.274, .25)], .019, K.M['rubber'], root)
    for i in range(3):
        book('right_shelf_portfolio_%02d' % i, (2.91, .09, .69 + i * .067), .43, .55, .061, ['ivory', 'leather', 'navy'][i], -.02 + .015 * i)


def open_sketchbook():
    root = asset('open_sketchbook', (1.03, -.55, TABLE_TOP + .012))
    root.rotation_euler.z = -.075
    width, depth = .405, .51
    K.box('Open sketchbook cloth binding', (0, 0, .006), (.84, .54, .012), K.M['navy'], root, .010)
    for side in [-1, 1]:
        K.box('Visible cream page edges', (side * .207, 0, .020), (.398, .509, .024), K.M['paper'], root, .005)
    def height(x):
        return .034 + .029 * math.exp(-abs(x) / .055) + .011 * math.sin(math.pi * abs(x) / width)
    for side in [-1, 1]:
        vertices, faces = [], []
        nx, ny = 28, 12
        for iy in range(ny + 1):
            y = -depth / 2 + iy * depth / ny
            for ix in range(nx + 1):
                x = side * (.006 + ix * (width - .006) / nx)
                vertices.append((x, y, height(x) + .002 * (2 * y / depth) ** 2))
        for iy in range(ny):
            for ix in range(nx):
                a = iy * (nx + 1) + ix
                faces.append((a, a + 1, a + nx + 2, a + nx + 1) if side > 0 else (a + 1, a, a + nx + 1, a + nx + 2))
        page = K.mesh('Curved sketchbook page', vertices, faces, K.M['paper'], root)
        for f in page.data.polygons:
            f.use_smooth = True
        solid = page.modifiers.new('Actual paper thickness', 'SOLIDIFY')
        solid.thickness = .0011
        # Original isometric hard-surface construction studies, not an image.
        outlines = [
            [(.08, -.10), (.25, -.135), (.335, -.032), (.17, .023), (.08, -.10)],
            [(.08, -.10), (.085, .065), (.17, .155), (.17, .023)],
            [(.17, .155), (.332, .10), (.335, -.032)],
            [(.085, .065), (.25, .025), (.332, .10)],
            [(.25, -.135), (.25, .025)],
            [(.06, -.155), (.353, -.155)],
            [(.353, -.155), (.353, .12)],
        ]
        for index, line in enumerate(outlines):
            points = [(side * x, y, height(x) + .0034 + .002 * (2 * y / depth) ** 2) for x, y in line]
            K.tube('Original construction drawing', points, .0009 if index < 5 else .00045, K.M['ink'], root)
        for i in range(4):
            y = -.196 + .010 * i
            K.tube('Sketch annotation strokes', [(side * .08, y, height(.08) + .004), (side * (.155 + .012 * (i % 3)), y, height(.155 + .012 * (i % 3)) + .004)], .00045, K.M['ink'], root)
    K.tube('Bookmark woven ribbon', [(.027, -.20, .042), (.036, -.29, .021), (.058, -.305, .016)], .007, K.M['leather'], root)
    return root


def geometry_study():
    root = asset('paper_polyhedron_study', (.035, -.105, TABLE_TOP + .008))
    r, h = .15, .25
    vertices = [(0, 0, h)] + [(r * math.cos(i * 2 * math.pi / 5), r * math.sin(i * 2 * math.pi / 5), 0) for i in range(5)] + [(0, 0, 0)]
    faces = [(0, i + 1, (i + 1) % 5 + 1) for i in range(5)] + [(6, (i + 1) % 5 + 1, i + 1) for i in range(5)]
    K.mesh('Folded original pentagonal study', vertices, faces, K.M['paper'], root)
    return root


def lens_study():
    root = asset('machined_lens_study', (.53, -.015, TABLE_TOP + .012))
    body = K.lathe('Machined lens shell', [(.092, 0), (.154, 0), (.164, .015), (.164, .062), (.15, .075), (.15, .105), (.129, .116), (.093, .116), (.089, .099), (.089, .012), (.092, 0)], K.M['dark'], root, 80)
    for z in [.012, .067, .105]:
        K.torus('Lens engraved brass ring', (0, 0, z), .152 if z < .1 else .137, .003, K.M['brass'], root)
    for i in range(48):
        a = i * math.tau / 48
        square_bar('Lens radial grip rib', (.165 * math.cos(a), .165 * math.sin(a), .019), (.165 * math.cos(a), .165 * math.sin(a), .057), .0034, .0034, K.M['rubber'], root)
    axis_cylinder('Lens coated optical element', (0, 0, .068), .087, .009, K.M['glass'], root, 'Z')
    for i in range(6):
        a = i * math.tau / 6
        K.screw('Lens visible mounting screw', (.119 * math.cos(a), .119 * math.sin(a), .12), K.M['metal'], root, (0, 0, 0), .008)
    K.box('Lens alignment mark', (0, -.158, .083), (.013, .005, .006), K.M['orange'], root, .001)
    return root


def rolled_drawing(name, location, length, angle):
    root = asset(name, location)
    root.rotation_euler.z = angle
    tube = K.lathe('Rolled original drawing sheet', [(.029, -length / 2), (.041, -length / 2), (.042, -length / 2 + .004), (.042, length / 2 - .004), (.040, length / 2), (.029, length / 2), (.029, -length / 2)], K.M['paper'], root, 56)
    tube.rotation_euler.y = math.pi / 2
    for x in [-length * .26, length * .26]:
        K.torus('Roll leather retainer', (x, 0, 0), .043, .004, K.M['leather'], root, (0, math.pi / 2, 0))
    for x in [-length / 2 - .001, length / 2 + .001]:
        for r in [.0315, .0347, .038]:
            K.torus('Paper spiral exposed edge', (x, 0, 0), r, .0006, K.M['wood_dark'], root, (0, math.pi / 2, 0))
    return root


def swatch_fan():
    pivot = (2.12, -.66, TABLE_TOP + .019)
    colors = ['navy', 'leather', 'ivory', 'wood_dark', 'paper', 'orange']
    for i, material in enumerate(colors):
        root = asset('material_swatch_%02d' % i, (pivot[0], pivot[1], pivot[2] + i * .0025))
        root.rotation_euler.z = math.radians(-63 + i * 23)
        K.box('Material sample card', (0, .136, .002), (.09, .288, .004), K.M[material], root, .004)
        K.box('Blank sample card annotation tab', (0, .040, .0047), (.065, .031, .0015), K.M['paper'], root, .001)
    root = asset('swatch_binding_pin', (pivot[0], pivot[1], pivot[2] + .019))
    axis_cylinder('Swatch fan brass pivot', (0, 0, 0), .017, .032, K.M['brass'], root, 'Z', 32)
    K.screw('Swatch central screw', (0, 0, .019), K.M['metal'], root, (0, 0, 0), .008)


def drafting_tools():
    root = asset('desk_steel_rule', (-.03, -.635, TABLE_TOP + .019))
    root.rotation_euler.z = -.13
    K.box('Drafting steel ruler', (0, 0, .0025), (.42, .040, .005), K.M['metal'], root, .002)
    for i in range(39):
        x = -.19 + i * .01
        K.tube('Ruler engraved graduation', [(x, -.018, .0057), (x, -.005 if i % 5 == 0 else -.011, .0057)], .00055, K.M['ink'], root)
    root = asset('desk_ring_gauge', (.395, -.74, TABLE_TOP + .018))
    K.torus('Brass ring gauge', (0, 0, .020), .093, .011, K.M['brass'], root)
    for a in [.2, 2.0, 3.8]:
        K.screw('Gauge index screw', (.093 * math.cos(a), .093 * math.sin(a), .032), K.M['metal'], root, (0, 0, 0), .007)
    root = asset('desk_magnifier', (1.68, .20, TABLE_TOP + .021))
    root.rotation_euler.z = -.38
    K.torus('Loupe brass rim', (0, 0, .010), .081, .009, K.M['brass'], root)
    axis_cylinder('Loupe optical glass', (0, 0, .01), .073, .006, K.M['glass'], root, 'Z')
    K.rod('Loupe wood handle', (0, -.086, .013), (0, -.232, .013), .016, K.M['wood_dark'], root)
    axis_cylinder('Handle ferrule', (0, -.101, .013), .018, .042, K.M['brass'], root)
    root = asset('desk_eraser', (1.62, -.305, TABLE_TOP + .012))
    root.rotation_euler.z = .08
    K.box('Soft white drafting eraser', (0, 0, .015), (.076, .037, .03), K.M['rubber'], root, .009)
    K.box('Eraser paper sleeve', (-.013, 0, .015), (.034, .039, .031), K.M['paper'], root, .002)
    pen('desk_graphite_pencil', (1.58, -.64, TABLE_TOP + .021), .265, 'wood', (0, math.pi / 2, .12))
    pen('desk_mechanical_pencil', (1.70, -.54, TABLE_TOP + .021), .225, 'navy', (0, math.pi / 2, -.08))
    root = asset('desk_parts_dish', (3.13, -.67, TABLE_TOP + .012))
    K.lathe('Spun ceramic small-parts dish', [(0, .008), (.087, .008), (.123, .029), (.126, .044), (.12, .047), (.112, .035), (.082, .018), (0, .018)], K.M['ceramic'], root, 64)
    for i in range(3):
        K.torus('Small brass retaining ring', (-.041 + i * .034, -.016 + i * .019, .025), .021 + i * .002, .003, K.M['brass'], root)
    root = asset('desk_inkwell', (2.05, .27, TABLE_TOP + .012))
    K.lathe('Faceted dark ink vessel', [(0, 0), (.053, 0), (.058, .015), (.057, .080), (.035, .099), (.03, .112), (0, .112)], K.M['navy'], root, 12)
    axis_cylinder('Inkwell brass cap', (0, 0, .121), .036, .020, K.M['brass'], root, 'Z', 32)
    K.box('Inkwell ivory blank label', (0, -.058, .053), (.040, .0015, .036), K.M['paper'], root, .002)
    root = asset('desk_pen_cup', (2.33, -.065, TABLE_TOP + .012))
    K.lathe('Brass open pen vessel', [(0, .005), (.074, .005), (.078, .02), (.078, .186), (.07, .192), (.066, .181), (.066, .014), (0, .014)], K.M['brass'], root, 64)
    for i in range(6):
        angle = i * math.tau / 6
        pen('desk_pen_%02d' % i, (2.33 + .034 * math.cos(angle), -.065 + .034 * math.sin(angle), TABLE_TOP + .04), .28 + .017 * (i % 3), ['wood', 'navy', 'metal'][i % 3], (.07 * math.sin(angle), .07 * math.cos(angle), 0))


def contact_terminal():
    root = asset('contact_terminal', (2.90, .19, TABLE_TOP + .007))
    root['interaction'] = 'contact'
    K.box('Terminal low blue base', (0, -.025, .041), (.79, .29, .08), K.M['navy'], root, .030)
    K.box('Terminal brass base seam', (0, -.028, .069), (.76, .271, .014), K.M['brass'], root, .010)
    for x in [-.31, .31]:
        K.box('Terminal rubber foot', (x, -.044, .006), (.095, .185, .012), K.M['rubber'], root, .005)
    axis_cylinder('Terminal screen hinge barrel', (0, .011, .100), .043, .66, K.M['brass'], root, 'X')
    face = asset('contact_terminal_display', (0, 0, 0))
    face.parent = root
    face.location = (0, .012, .108)
    face.rotation_euler.x = math.radians(-14)
    face['interaction'] = 'contact'
    K.box('Terminal machined blue shell', (0, 0, .247), (.81, .111, .501), K.M['navy'], face, .033)
    K.box('Terminal thin brass bezel', (0, -.059, .247), (.785, .012, .477), K.M['brass'], face, .024)
    K.box('Terminal dark front panel', (-.018, -.067, .251), (.737, .013, .432), K.M['dark'], face, .021)
    K.box('Terminal recessed screen', (-.064, -.076, .265), (.574, .008, .344), K.M['navy'], face, .010)
    K.box('Terminal screen cover glass', (-.064, -.081, .265), (.581, .003, .348), K.M['glass'], face, .009)
    K.text('Contact heading', '联系', (-.064, -.084, .331), .029, K.M['paper'], face)
    K.text('Contact content placeholder', '联系方式待补充', (-.064, -.084, .251), .026, K.M['paper'], face)
    K.tube('Terminal screen divider', [(-.26, -.084, .294), (.125, -.084, .294)], .0007, K.M['brass'], face)
    axis_cylinder('Terminal orange control knob', (.304, -.083, .207), .045, .041, K.M['orange'], face)
    axis_cylinder('Terminal knob central cap', (.304, -.109, .207), .029, .009, K.M['brass'], face)
    K.box('Terminal knob engraved index', (.304, -.116, .225), (.003, .002, .013), K.M['ink'], face, .001)
    axis_cylinder('Terminal small status button', (.304, -.083, .103), .013, .014, K.M['brass'], face, vertices=24)
    for x in [-.356, .356]:
        for z in [.050, .445]:
            K.screw('Terminal bezel screw', (x, -.079, z), K.M['metal'], face, r=.0048)
    K.tube('Terminal braided power lead', [(.28, .115, .055), (.32, .19, .055), (.42, .23, .030), (.47, .27, .018)], .009, K.M['rubber'], root)
    K.box('Terminal power connector', (.46, .27, .022), (.074, .035, .028), K.M['dark'], root, .006)
    return root


def pegboard():
    root = asset('tool_pegboard_structure', (1.865, BOARD_FRONT + .042, 2.475))
    K.box('Deep navy steel tool panel', (0, 0, 0), (3.23, .084, 2.45), K.M['navy'], root, .021)
    for x in [-1.595, 1.595]:
        K.box('Pegboard brass vertical binding', (x, -.047, 0), (.018, .020, 2.433), K.M['brass'], root, .004)
    for z in [-1.205, 1.205]:
        K.box('Pegboard brass horizontal binding', (0, -.047, z), (3.185, .020, .019), K.M['brass'], root, .004)
    for x in [-1.56, 1.56]:
        for z in [-1.164, 1.164]:
            K.screw('Pegboard structural fixing', (x, -.058, z), K.M['brass'], root, r=.012)
    # Many black recessed hole mouths share only a single mesh. No repeated
    # Boolean operations, no transparent texture plane, no merged small props.
    vertices, faces = [], []
    for column in range(47):
        for row in range(35):
            cx, cz = -1.50 + column * .0652, -1.10 + row * .0647
            base = len(vertices)
            vertices.extend([(cx + .0068 * math.cos(i * math.tau / 10), -.045, cz + .0068 * math.sin(i * math.tau / 10)) for i in range(10)])
            faces.append(tuple(base + i for i in range(10)))
    K.mesh('Pegboard combined dark hole mouths', vertices, faces, K.M['ink'], root)
    for x in [-1.39, 1.39]:
        K.box('Tool wall freestanding steel post', (x, .04, -1.32), (.065, .071, 1.59), K.M['dark'], root, .009)
        K.box('Tool wall floor shoe', (x, .02, FLOOR - 2.475 + .012), (.29, .39, .024), K.M['dark'], root, .007)
    return root


def hanging_hook(root, z=0, x=0, front=-.03):
    back = BOARD_FRONT - root.location.y + .010
    K.tube('Bent pegboard hanging hook', [(x, back, z + .063), (x, -.016, z + .063), (x, front, z + .041), (x, front, z - .004)], .0055, K.M['brass'], root)


def hanging_sample(name, location, width, height, material):
    root = asset(name, location)
    hanging_hook(root, height / 2 + .024)
    K.box('Hanging material sample backing', (0, 0, 0), (width, .013, height), K.M['wood_dark'], root, .004)
    K.box('Hanging material sample face', (0, -.009, -.018), (width - .008, .008, height - .035), K.M[material], root, .003)
    K.torus('Hanging sample brass eye', (0, -.016, height / 2 - .015), .016, .003, K.M['brass'], root, (math.pi / 2, 0, 0))
    return root


def board_tools():
    hanging_sample('board_large_fabric_sample', (.67, 1.69, 3.03), .46, .62, 'fabric')
    for i, material in enumerate(['ivory', 'orange', 'navy']):
        hanging_sample('board_surface_sample_%02d' % i, (1.15 + i * .20, 1.69, 2.80), .174, .51, material)
    # Sewn leather tool roll with convex individual pocket faces.
    root = asset('board_leather_tool_roll', (1.06, 1.64, 2.055))
    K.box('Tool roll leather backing', (0, .01, 0), (1.18, .025, .48), K.M['leather'], root, .018)
    for x in [-.535, .535]:
        hanging_hook(root, .26, x, .005)
    for i in range(6):
        x = -.493 + i * .197
        verts = []
        for z in [-.213, .07]:
            for j in range(13):
                u = j / 12
                verts.append((x - .084 + .168 * u, -.008 - .068 * math.sin(math.pi * u), z + (.012 * math.sin(math.pi * u) if z > 0 else 0)))
        faces = [(j, j + 1, j + 14, j + 13) for j in range(12)]
        pocket = K.mesh('Individually curved leather pocket', verts, faces, K.M['leather'], root)
        solid = pocket.modifiers.new('Leather thickness', 'SOLIDIFY'); solid.thickness = .0035
        for f in pocket.data.polygons: f.use_smooth = True
        for side in [-1, 1]:
            for j in range(17):
                z = -.205 + j * .016
                K.tube('Tool pocket saddle stitches', [(x + side * .076, -.012, z), (x + side * .076, -.012, z + .006)], .0008, K.M['paper'], root)
        tool = asset('board_roll_tool_%02d' % i, (1.06 + x, 1.605, 2.04))
        axis_cylinder('Tool shaped wooden grip', (0, 0, .165), .015 if i % 2 else .021, .19, K.M['wood'], tool, 'Z', 24)
        axis_cylinder('Tool polished ferrule', (0, 0, .26), .016, .027, K.M['brass'], tool, 'Z', 24)
        if i % 2:
            K.box('Fine palette blade', (0, 0, .32), (.032, .005, .104), K.M['metal'], tool, .003)
        else:
            K.lathe('Sculpting tool tapered point', [(0, .364), (.008, .29), (.009, .27)], K.M['metal'], tool, 20)
    root = asset('board_vernier_caliper', (1.61, 1.65, 2.50))
    hanging_hook(root, .044, -.24)
    hanging_hook(root, .044, .20)
    K.box('Caliper graduated slide rail', (0, 0, 0), (.67, .019, .045), K.M['metal'], root, .002)
    for i in range(51):
        x = -.245 + i * .010
        K.tube('Caliper engraving', [(x, -.011, -.016), (x, -.011, -.002 if i % 5 == 0 else -.009)], .0004, K.M['ink'], root)
    for x in [-.265, -.092]:
        K.box('Caliper measuring jaw', (x, -.001, -.057), (.029, .026, .125), K.M['metal'], root, .002)
        K.box('Caliper inward jaw', (x + .011, -.001, -.116), (.046, .028, .016), K.M['metal'], root, .002)
    K.box('Caliper movable carriage', (-.092, -.014, -.002), (.11, .038, .073), K.M['metal'], root, .004)
    axis_cylinder('Caliper knurled lock', (-.092, -.041, .034), .019, .018, K.M['brass'], root)
    root = asset('board_headphones', (2.29, 1.49, 2.90))
    hanging_hook(root, .17, 0, .13)
    for depth in [0, .047]:
        points = []
        for i in range(45):
            a = math.radians(-8 + 196 * i / 44)
            points.append((.205 * math.cos(a), depth, -.02 + .237 * math.sin(a)))
        K.tube('Headphone curved metal headband', points, .011, K.M['dark'], root)
    K.tube('Headband padded leather crown', [(.208 * math.cos(math.radians(25 + 130 * i / 30)), .02, -.020 + .242 * math.sin(math.radians(25 + 130 * i / 30))) for i in range(31)], .021, K.M['leather'], root)
    for side in [-1, 1]:
        K.box('Headphone machined yoke', (side * .187, .016, -.132), (.025, .050, .153), K.M['brass'], root, .006)
        axis_cylinder('Headphone ear shell', (side * .191, .007, -.227), .101, .074, K.M['dark'], root, 'X')
        axis_cylinder('Headphone padded ear cushion', (side * .145, .007, -.227), .086, .029, K.M['rubber'], root, 'X')
        K.torus('Headphone spun trim ring', (side * .232, .007, -.227), .084, .004, K.M['brass'], root, (0, math.pi / 2, 0))
    K.tube('Headphone loosely looped lead', [(.20, .025, -.32), (.235, .022, -.44), (.30, .045, -.465), (.32, .081, -.385)], .004, K.M['rubber'], root)
    # Narrow lens shelf and open cup stay left of the right-side frame.
    root = asset('board_lens_shelf', (2.41, 1.60, 1.96))
    K.box('Small walnut tool shelf', (0, 0, 0), (.64, .34, .035), K.M['wood'], root, .007)
    for x in [-.23, .23]:
        K.box('Shelf rear brass mounting ear', (x, .165, .069), (.028, .02, .16), K.M['brass'], root, .003)
        K.rod('Shelf diagonal support', (x, .16, -.105), (x, -.125, -.022), .007, K.M['brass'], root)
    root = asset('board_spare_lens', (2.24, 1.525, 1.984))
    K.lathe('Shelf spare lens housing', [(.063, 0), (.075, .016), (.075, .16), (.064, .189), (.048, .189), (.048, .169), (.059, .16), (.059, .015), (.063, 0)], K.M['dark'], root, 64)
    for z in [.028, .128, .164]:
        K.torus('Spare lens focus ring', (0, 0, z), .076, .004, K.M['brass'], root)
    root = asset('board_brush_cup', (2.61, 1.58, 3.12))
    K.box('Hanging cup mounting clip', (0, .130, .055), (.025, .13, .16), K.M['brass'], root, .004)
    K.lathe('Tool board pen cup', [(0, 0), (.055, 0), (.059, .01), (.059, .156), (.050, .156), (.050, .012), (0, .012)], K.M['brass'], root, 48)
    for i in range(4):
        pen('board_drafting_pen_%02d' % i, (2.61 + (i - 1.5) * .019, 1.572, 3.144), .25 + .019 * (i % 2), ['wood', 'navy'][i % 2], (0, (i - 1.5) * .052, 0))


def board_art_frame():
    root = asset('board_original_geometry_frame', (3.145, 1.64, 2.645))
    K.box('Tall art frame walnut back', (0, .037, 0), (.46, .057, 1.765), K.M['wood_dark'], root, .010)
    K.box('Original geometry print paper', (0, .003, 0), (.402, .007, 1.676), K.M['paper'], root, .001)
    for x in [-.221, .221]:
        K.box('Slim brass picture frame', (x, -.006, 0), (.020, .025, 1.76), K.M['brass'], root, .004)
    for z in [-.87, .87]:
        K.box('Slim brass picture frame', (0, -.006, z), (.444, .025, .020), K.M['brass'], root, .004)
    # A restrained original ribbon sculpture study, made of flat geometric
    # facets on archival paper rather than external poster artwork.
    for index in range(10):
        t0, t1 = index / 10, (index + 1) / 10
        def point(t, side):
            return (.072 * math.sin(math.tau * t) + side * (.045 + .034 * math.sin(math.pi * t)), -.0035, -.62 + 1.25 * t)
        obj = K.mesh('Original abstract ribbon facet', [point(t0, -1), point(t0, 1), point(t1, 1), point(t1, -1)], [(0, 1, 2, 3)], K.M[['navy', 'stone', 'wood_dark'][index % 3]], root)
    K.box('Picture frame protective glass', (0, -.014, 0), (.405, .003, 1.696), K.M['glass'], root, .001)
    for z in [-.72, .72]:
        K.tube('Frame back hanging mount', [(-.10, .046, z), (0, .113, z + .024), (.10, .046, z)], .007, K.M['brass'], root)
    return root


def task_lamp():
    mount = Vector((1.55, 1.67, 3.20))
    root = asset('articulated_brass_task_lamp', mount)
    local = lambda p: Vector(p) - mount
    a = Vector((2.05, 1.16, 3.44))
    shade_axis = (Vector(LAMP_MOUTH) - Vector(LAMP_TARGET)).normalized()
    shade_top = Vector(LAMP_MOUTH) + shade_axis * .258
    b = Vector((1.62, .51, 3.60))
    axis_cylinder('Lamp round mounting plate', (0, .078, 0), .092, .044, K.M['brass'], root)
    axis_cylinder('Lamp wall bearing spacer', (0, .048, 0), .036, .07, K.M['brass'], root)
    for dx in [-.048, .048]:
        K.screw('Lamp wall mounting bolt', (dx, .052, 0), K.M['metal'], root, r=.009)
    for p, q in [(mount, a), (a, b), (b, shade_top)]:
        for offset in [-.027, .027]:
            delta = Vector((0, offset, 0))
            K.rod('Parallel articulated brass arm', local(p + delta), local(q + delta), .016, K.M['brass'], root)
    for index, p in enumerate([mount, a, b, shade_top]):
        axis_cylinder('Lamp exposed swivel joint', local(p), .055 if index < 3 else .031, .091, K.M['brass'], root)
        c = local(p); c.y -= .051
        K.screw('Lamp swivel axle screw', c, K.M['dark'], root, r=.018 if index < 3 else .011)
    # Two visible tension springs between the double-link arm members.
    start, end = local(mount.lerp(a, .18)), local(mount.lerp(a, .83))
    direction = (end - start).normalized()
    basis = direction.cross(Vector((0, 0, 1))).normalized()
    cross = direction.cross(basis).normalized()
    points = []
    for i in range(181):
        t = i / 180
        point = start.lerp(end, t) + .026 * (basis * math.cos(t * math.tau * 18) + cross * math.sin(t * math.tau * 18))
        points.append(point)
    K.tube('Articulated lamp tension spring', points, .0027, K.M['metal'], root)
    shade = asset('task_lamp_shade', (0, 0, 0))
    shade.parent = root
    shade.location = local(LAMP_MOUTH)
    shade.rotation_euler = shade_axis.to_track_quat('Z', 'Y').to_euler()
    K.lathe('Spun brass task lamp shade', [(.193, 0), (.200, .009), (.193, .022), (.084, .226), (.055, .247), (.045, .247), (.069, .218), (.180, .020), (.182, .009), (.193, 0)], K.M['brass'], shade, 96)
    K.lathe('Ivory lamp shade interior', [(.181, .013), (.070, .218), (.065, .211), (.175, .018)], K.M['ivory'], shade, 96)
    K.torus('Rolled shade lip', (0, 0, .010), .192, .006, K.M['brass'], shade)
    axis_cylinder('Small lamp diffuser', (0, 0, .117), .074, .008, K.M['light'], shade, 'Z')
    K.tube('Lamp flexible black power cord', [local(mount + Vector((-.04, .04, -.05))), local(a + Vector((0, .058, -.045))), local(b + Vector((.02, .065, -.04))), local(shade_top)], .004, K.M['rubber'], root)
    root['light_mouth_world'] = list(LAMP_MOUTH)
    root['light_target_world'] = list(LAMP_TARGET)
    return root


def build():
    """Build desk and board only; caller owns materials, scene and real lights."""
    table()
    storage()
    open_sketchbook()
    geometry_study()
    lens_study()
    rolled_drawing('drawing_roll_long', (.39, .357, TABLE_TOP + .052), .66, -.055)
    rolled_drawing('drawing_roll_short', (1.065, .357, TABLE_TOP + .052), .53, .025)
    swatch_fan()
    drafting_tools()
    contact_terminal()
    pegboard()
    board_tools()
    board_art_frame()
    task_lamp()
    return {'lamp_mouth': LAMP_MOUTH, 'lamp_target': LAMP_TARGET, 'table_top': TABLE_TOP}
