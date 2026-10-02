"""Sunlit gallery B: independently addressable furniture and small objects.

Only procedural geometry is used.  Call build() after gallery_common has set up
the scene and shared materials.  All primitive positions are world coordinates;
the imported helpers preserve those positions while assigning their parent.
"""

import math
import random

from mathutils import Vector

from gallery_common import (
    M as MATERIALS, group, box, cyl, sphere, tube, torus, mesh, label,
    rounded_rect as _rounded_rect,
)


PI = math.pi
ROOTS = []


def M(key):
    return MATERIALS[key]


def rounded_rect(name, center, width, height, depth, radius, mat,
                 parent=None, plane="XY"):
    return _rounded_rect(name, center, width, height, depth, radius, mat,
                         parent=parent, plane=plane)


def asset(asset_id, loc, interaction="inspect", parent=None):
    obj = group(asset_id, loc=loc, parent=parent, atlas=3)
    obj["stableAssetId"] = asset_id
    obj["asset_id"] = asset_id
    obj["interactive"] = interaction != "none"
    obj["interaction"] = interaction
    obj["asset_source"] = "original procedural geometry"
    ROOTS.append(obj)
    return obj


def lathe(name, center, profile, material, parent, segments=40):
    """A closed, beveled silhouette using a small rotational profile."""
    x, y, z = center
    verts = [(x + r * math.cos(2 * PI * i / segments),
              y + r * math.sin(2 * PI * i / segments), z + h)
             for r, h in profile for i in range(segments)]
    faces = []
    for j in range(len(profile) - 1):
        for i in range(segments):
            k = j * segments + i
            n = j * segments + (i + 1) % segments
            faces.append((k, n, n + segments, k + segments))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple((len(profile) - 1) * segments + i
                       for i in range(segments)))
    return mesh(name, verts, faces, material, parent=parent)


def capsule_path(x, y, width, depth, z, steps=20):
    radius = depth / 2
    dx = width / 2 - radius
    return [(x + dx + radius * math.cos(-PI / 2 + PI * i / steps),
             y + radius * math.sin(-PI / 2 + PI * i / steps), z)
            for i in range(steps + 1)] + [
        (x - dx + radius * math.cos(PI / 2 + PI * i / steps),
         y + radius * math.sin(PI / 2 + PI * i / steps), z)
        for i in range(steps + 1)]


def leaf(name, start, end, width, parent, phase=0.0):
    """Curved, ridged lanceolate leaf: ten quads rather than a ball canopy."""
    a, b = Vector(start), Vector(end)
    d = b - a
    side = Vector((-d.y, d.x, 0))
    if side.length < 0.001:
        side = Vector((math.cos(phase), math.sin(phase), 0))
    side.normalize()
    vertices = []
    steps = (0.0, 0.16, 0.38, 0.62, 0.84, 1.0)
    for t in steps:
        p = a + d * t
        p.z += math.sin(t * PI) * width * 0.28
        w = width * math.sin(t * PI) ** 0.82
        edge = Vector((0, 0, -math.sin(t * PI) * width * 0.16))
        vertices.extend((tuple(p - side * w + edge), tuple(p),
                         tuple(p + side * w + edge)))
    faces = []
    for i in range(len(steps) - 1):
        k = i * 3
        faces.extend(((k, k + 3, k + 4, k + 1),
                      (k + 1, k + 4, k + 5, k + 2)))
    return mesh(name, vertices, faces, M("leaf"), parent=parent)


def planter(asset_id, x, y, height, radius, seed, tabletop=False):
    root = asset(asset_id, (x, y, .15 if not tabletop else 1.1), "inspect")
    base = 1.1 if tabletop else 0.15
    pot_h = height * (0.40 if tabletop else 0.35)
    lathe(asset_id + ".pot", (x, y, base),
          [(radius * .72, 0), (radius * .88, .025),
           (radius, pot_h - .022), (radius * .96, pot_h),
           (radius * .86, pot_h), (radius * .82, pot_h - .05)],
          M("silver"), root)
    torus(asset_id + ".rim", (x, y, base + pot_h - .007),
          radius * .93, .012 if tabletop else .019, M("bronze"), parent=root)
    cyl(asset_id + ".soil", (x, y, base + pot_h - .035),
        radius * .83, .014, M("soil"), parent=root, vertices=32)
    rng = random.Random(seed)
    count = 15 if tabletop else 24
    # Leaves fan from staggered stalks, with an open silhouette and visible soil.
    for i in range(count):
        angle = i * 2.399963 + rng.uniform(-.13, .13)
        tier = i % 3
        reach = height * (.33 if tabletop else .39) * rng.uniform(.58, 1.05)
        rise = height * (.30 + .14 * tier) * rng.uniform(.83, 1.05)
        sx = x + math.cos(angle) * radius * .15
        sy = y + math.sin(angle) * radius * .15
        stem_base = (sx, sy, base + pot_h - .03)
        leaf_start = (x + math.cos(angle) * reach * .25,
                      y + math.sin(angle) * reach * .25,
                      base + pot_h + rise * .54)
        end = (x + math.cos(angle) * reach, y + math.sin(angle) * reach,
               base + pot_h + rise * (.78 if tier == 0 else 1.0))
        tube(asset_id + ".stem.%02d" % i, [stem_base, leaf_start, end],
             .004 if tabletop else .006, M("leaf"), parent=root)
        leaf(asset_id + ".leaf.%02d" % i, leaf_start, end,
             height * (.052 if tabletop else .075), root, angle)
    return root


def make_table():
    x, y = .35, -.55
    root = asset("gallery.table.main", (x, y, 0), "none")
    root["surface_height"] = 1.10
    rounded_rect("gallery.table.lower_plinth", (x, y, .215), 7.36, 1.04,
                 .13, .51, M("silver"), parent=root)
    rounded_rect("gallery.table.lower_body", (x, y, .30), 7.32, 1.02,
                 .15, .50, M("navy"), parent=root)
    # End drums, narrow rear wall, shelf and dividers leave the front recess open.
    for side in (-1, 1):
        cyl("gallery.table.end.%s" % side, (x + side * 3.18, y, .6625),
            .505, .745, M("navy"), parent=root, vertices=64)
        tube("gallery.table.end_seam.%s" % side,
             [(x + side * 3.18, y - .506, .315),
              (x + side * 3.18, y - .506, 1.00)],
             .005, M("silver"), parent=root)
    box("gallery.table.back", (x, -.17, .65), (6.35, .20, .78),
        M("navy"), parent=root, radius=.025)
    box("gallery.table.recess", (x, -.282, .63), (6.18, .025, .64),
        M("black"), parent=root, radius=.012)
    box("gallery.table.shelf", (x, -.66, .385), (6.28, .78, .045),
        M("silver"), parent=root, radius=.014)
    for i, dx in enumerate((-2.66, -1.59, -.53, .53, 1.59, 2.66)):
        box("gallery.table.divider.%02d" % i, (x + dx, -.65, .65),
            (.035, .74, .58), M("navy"), parent=root, radius=.008)
    box("gallery.table.warm_recess", (x, -.35, .97), (6.11, .042, .025),
        M("warm"), parent=root, radius=.009)
    rounded_rect("gallery.table.silver_top", (x, y, 1.053), 7.50, 1.12,
                 .094, .55, M("silver"), parent=root)
    rounded_rect("gallery.table.stone_inlay", (x, y, 1.091), 7.34, .96,
                 .018, .47, M("terrazzo"), parent=root)
    tube("gallery.table.bronze_fillet", capsule_path(x, y, 7.45, 1.07, 1.075),
         .006, M("bronze"), parent=root, closed=True)


def shelf_library():
    for i, x in enumerate((-1.78, -.72, .35, 1.41, 2.48), 1):
        root = asset("gallery.library.%02d" % i, (x, -.76, .415), "inspect")
        root["content_status"] = "待补充"
        if i in (1, 3, 5):
            for j in range(3):
                z = .43 + j * .095
                width = .75 - .07 * (j % 2)
                box(root.name + ".pages.%02d" % j, (x, -.70, z + .031),
                    (width - .025, .46, .054), M("paper"), parent=root, radius=.006)
                for dz in (0, .064):
                    box(root.name + ".cover.%02d.%d" % (j, dz * 1000),
                        (x, -.70, z + dz), (width, .49, .013),
                        M("bronze" if j == 1 else "navy"), parent=root, radius=.006)
                box(root.name + ".spine.%02d" % j, (x, -.948, z + .032),
                    (width, .014, .071), M("bronze" if j == 1 else "navy"),
                    parent=root, radius=.004)
                box(root.name + ".spine_rule.%02d" % j, (x, -.957, z + .036),
                    (width * .45, .004, .004), M("silver"), parent=root, radius=.001)
        else:
            for j in range(7):
                xx = x - .34 + j * .103
                h = .47 + .07 * math.sin(j * 1.6)
                mat = M(("ivory", "navy", "bronze", "navy")[j % 4])
                box(root.name + ".book.%02d" % j, (xx, -.68, .415 + h / 2),
                    (.075, .46, h), mat, parent=root, radius=.009)
                box(root.name + ".pages.%02d" % j, (xx, -.664, .42 + h / 2),
                    (.051, .445, h - .027), M("paper"), parent=root, radius=.003)
                box(root.name + ".spine.%02d" % j, (xx, -.919, .415 + h / 2),
                    (.076, .016, h), mat, parent=root, radius=.004)
                for zz in (.475, .53):
                    box(root.name + ".band.%02d.%03d" % (j, zz * 1000),
                        (xx, -.929, zz), (.052, .004, .007), M("silver"),
                        parent=root, radius=.001)


def album(index, x):
    y, z = -.68, 1.12
    root = asset("gallery.album.%02d" % index, (x, y, z), "tilt")
    root["content_status"] = "待补充"
    root["interaction_axis"] = "X"
    root["interaction_angle_min"] = -35.0
    root["interaction_angle_max"] = -5.0
    w, h = 1.05, .83
    rounded_rect(root.name + ".cover", (x, y, z + h / 2), w, h, .067,
                 .025, M("navy"), parent=root, plane="XZ")
    rounded_rect(root.name + ".page_block", (x, y - .040, z + h / 2),
                 w - .055, h - .055, .030, .013, M("paper"), parent=root, plane="XZ")
    rounded_rect(root.name + ".front_sheet", (x, y - .06, z + h / 2),
                 w - .105, h - .10, .006, .006, M("ivory"), parent=root, plane="XZ")
    for j in range(4):
        box(root.name + ".page_edge.%d" % j, (x + w / 2 - .022, y - .021 - j * .008, z + h / 2),
            (.007, .002, h - .075), M("bronze"), parent=root, radius=.001)
    # Flat original shapes are modeled into the cover, never external artwork.
    cy = y - .066
    if index == 1:
        torus(root.name + ".art.ring", (x, cy, z + .47), .187, .014,
              M("bronze"), parent=root, rotation=(PI / 2, 0, 0))
        box(root.name + ".art.rule", (x + .05, cy - .006, z + .44),
            (.01, .007, .48), M("navy"), parent=root, radius=.001)
        cyl(root.name + ".art.orbit", (x + .15, cy - .014, z + .64),
            .039, .009, M("silver"), parent=root, rotation=(PI / 2, 0, 0), vertices=32)
    elif index == 2:
        cyl(root.name + ".art.disc", (x, cy - .01, z + .47),
            .185, .012, M("silver"), parent=root, rotation=(PI / 2, 0, 0), vertices=48)
        cyl(root.name + ".art.eclipse", (x + .075, cy - .02, z + .49),
            .142, .013, M("navy"), parent=root, rotation=(PI / 2, 0, 0), vertices=48)
        box(root.name + ".art.line", (x, cy - .03, z + .29),
            (.47, .007, .007), M("bronze"), parent=root, radius=.001)
    else:
        for a in range(3):
            for b in range(3):
                if (a, b) != (0, 2):
                    box(root.name + ".art.tile.%d.%d" % (a, b),
                        (x + (a - 1) * .15, cy - .009, z + .47 + (b - 1) * .13),
                        (.125, .012, .105), M("bronze" if (a + b) % 3 == 0 else "silver"),
                        parent=root, radius=.002)
    label(root.name + ".number", "%02d" % index, (x - .37, cy - .023, z + .105),
          .057, M("ink"), parent=root)
    box(root.name + ".caption_rule", (x + .13, cy - .009, z + .13),
        (.37, .006, .006), M("bronze"), parent=root, radius=.001)
    # The lower edge is the hinge origin, and all book parts follow it.
    root.rotation_euler.x = math.radians(-18)
    return root


def ring_sculpture():
    x, y, z = -2.70, -.53, 1.10
    root = asset("gallery.sculpture.ring", (x, y, z + .35), "spin")
    cyl(root.name + ".foot", (x, y, z + .025), .255, .047, M("silver"), parent=root)
    cyl(root.name + ".foot_recess", (x, y, z + .054), .204, .013, M("navy"), parent=root)
    cyl(root.name + ".stem", (x, y, z + .16), .023, .22, M("bronze"), parent=root, vertices=24)
    for i, rot in enumerate(((PI / 2, 0, 0), (PI / 2, 0, .92), (PI / 2, .76, -.4))):
        torus(root.name + ".orbit.%d" % i, (x, y, z + .42), .265 - i * .035,
              .014, M("silver" if i != 1 else "bronze"), parent=root, rotation=rot)
    sphere(root.name + ".core", (x, y, z + .42), (.055, .055, .055), M("bronze"), parent=root)


def task_lamp():
    x, y, z = 2.83, -.26, 1.10
    base = asset("gallery.lamp.base", (x, y, z), "inspect")
    cyl(base.name + ".foot", (x, y, z + .023), .135, .046, M("silver"), parent=base)
    box(base.name + ".switch", (x, y - .055, z + .05), (.048, .025, .012),
        M("navy"), parent=base, radius=.007)
    joint = (x - .10, y, z + .58)
    tube(base.name + ".arm", [(x, y, z + .045), (x + .015, y, z + .28), joint],
         .018, M("silver"), parent=base)
    cyl(base.name + ".hinge", joint, .046, .070, M("bronze"), parent=base,
        rotation=(PI / 2, 0, 0), vertices=32)
    head = asset("gallery.lamp.head", joint, "tilt", parent=base)
    head["interaction_axis"] = "X"
    rounded_rect(head.name + ".shade", (joint[0] - .10, y - .04, joint[2] + .006),
                 .35, .15, .065, .07, M("navy"), parent=head)
    rounded_rect(head.name + ".reflector", (joint[0] - .10, y - .04, joint[2] - .030),
                 .29, .11, .008, .05, M("warm"), parent=head)
    head.rotation_euler.x = math.radians(-15)


def tabletop_items():
    root = asset("gallery.cup", (-2.1, -.79, 1.1), "inspect")
    x, y, z = -2.1, -.79, 1.1
    cyl(root.name + ".saucer", (x, y, z + .012), .125, .022, M("silver"), parent=root, vertices=40)
    lathe(root.name + ".body", (x, y, z + .025),
          [(.055, 0), (.074, .13), (.070, .15), (.059, .15), (.053, .13), (.043, .03)],
          M("ivory"), root, segments=32)
    cyl(root.name + ".coffee", (x, y, z + .142), .057, .005, M("soil"), parent=root, vertices=32)
    torus(root.name + ".handle", (x + .086, y, z + .10), .044, .010,
          M("ivory"), parent=root, rotation=(PI / 2, 0, 0))
    planter("gallery.planter.table", 3.43, -.47, .43, .135, 103, tabletop=True)
    root = asset("gallery.tool.pencil", (2.87, -.90, 1.117), "inspect")
    tube(root.name + ".barrel", [(2.65, -.91, 1.117), (3.03, -.85, 1.117)],
         .013, M("bronze"), parent=root)
    tube(root.name + ".graphite", [(2.61, -.916, 1.117), (2.65, -.91, 1.117)],
         .005, M("ink"), parent=root)
    root = asset("gallery.tool.caliper", (3.08, -.67, 1.12), "inspect")
    box(root.name + ".rail", (3.06, -.69, 1.12), (.35, .025, .023), M("silver"), parent=root, radius=.004)
    for i, xx in enumerate((2.91, 3.09)):
        box(root.name + ".jaw.%d" % i, (xx, -.64, 1.12), (.028, .12, .025), M("silver"), parent=root, radius=.004)
    box(root.name + ".slider", (3.08, -.69, 1.135), (.072, .045, .032), M("navy"), parent=root, radius=.007)
    root = asset("gallery.tool.measure_disc", (-3.13, -.55, 1.12), "spin")
    cyl(root.name + ".body", (-3.13, -.55, 1.126), .082, .044, M("bronze"), parent=root, vertices=40)
    torus(root.name + ".rim", (-3.13, -.55, 1.153), .067, .006, M("silver"), parent=root)
    for i in range(8):
        theta = i * PI / 4
        tube(root.name + ".tick.%d" % i,
             [(-3.13 + math.cos(theta) * .051, -.55 + math.sin(theta) * .051, 1.152),
              (-3.13 + math.cos(theta) * .061, -.55 + math.sin(theta) * .061, 1.152)],
             .0015, M("ink"), parent=root)


def bench():
    x, y = .3, -2.35
    root = asset("gallery.bench", (x, y, 0), "inspect")
    rounded_rect(root.name + ".base", (x, y, .324), 4.44, .61, .095,
                 .29, M("navy"), parent=root)
    rounded_rect(root.name + ".welt", (x, y, .375), 4.50, .67, .046,
                 .325, M("leather"), parent=root)
    rounded_rect(root.name + ".cushion", (x, y, .454), 4.49, .665, .192,
                 .320, M("leather"), parent=root)
    tube(root.name + ".lower_piping", capsule_path(x, y, 4.48, .657, .394),
         .0045, M("bronze"), parent=root, closed=True)
    # Fine dark seams and sparse stitches convey upholstery without a texture file.
    for i, xx in enumerate((x - 1.32, x + 1.32)):
        tube(root.name + ".cushion_seam.%d" % i,
             [(xx, y - .324, .435), (xx, y - .28, .532),
              (xx, y - .20, .551), (xx, y + .20, .551),
              (xx, y + .28, .532), (xx, y + .324, .435)],
             .003, M("soil"), parent=root)
        for j in range(12):
            yy = y - .24 + j * .043
            tube(root.name + ".stitch.%d.%02d" % (i, j),
                 [(xx - .012, yy, .553), (xx - .012, yy + .019, .553)],
                 .001, M("bronze"), parent=root)
    for i, xx in enumerate((x - 1.71, x + 1.71)):
        # Bent sled legs present a believable floor contact and silver return.
        tube(root.name + ".leg.%d" % i,
             [(xx, y - .25, .32), (xx, y - .25, .195),
              (xx, y + .25, .195), (xx, y + .25, .32)],
             .031, M("silver"), parent=root)
        for j, yy in enumerate((y - .22, y + .22)):
            box(root.name + ".pad.%d.%d" % (i, j), (xx, yy, .164),
                (.11, .12, .028), M("black"), parent=root, radius=.014)


def archive_cart():
    x, y = 6.1, -1.3
    root = asset("gallery.archive.cart", (x, y, .12), "move")
    root["content_status"] = "待补充"
    w, d = .68, .57
    for i, xx in enumerate((x - w / 2, x + w / 2)):
        for j, yy in enumerate((y - d / 2, y + d / 2)):
            tube(root.name + ".upright.%d.%d" % (i, j),
                 [(xx, yy, .18), (xx, yy, 1.11)], .018, M("silver"), parent=root)
    for i, z in enumerate((.23, .54, .84, 1.08)):
        rounded_rect(root.name + ".frame.%d" % i, (x, y, z), w + .04, d + .04,
                     .035, .035, M("silver"), parent=root)
        rounded_rect(root.name + ".tray.%d" % i, (x, y, z + .02), w - .025, d - .025,
                     .012, .022, M("glass") if i in (2, 3) else M("navy"), parent=root)
    # Top guard rail and push handle are intentionally separate mesh pieces.
    tube(root.name + ".guard", [(x - .34, y - .285, 1.20),
         (x - .34, y + .285, 1.20), (x + .34, y + .285, 1.20),
         (x + .34, y - .285, 1.20)], .013, M("bronze"), parent=root)
    tube(root.name + ".handle", [(x + .34, y - .27, 1.08),
         (x + .47, y - .27, 1.16), (x + .47, y + .27, 1.16),
         (x + .34, y + .27, 1.08)], .017, M("silver"), parent=root)
    for i, z in enumerate((.38, .69), 1):
        drawer = asset("gallery.archive.drawer.%02d" % i, (x, y - .275, z), "slide", parent=root)
        drawer["interaction_axis"] = "Y"
        drawer["interaction_distance"] = -.27
        box(drawer.name + ".body", (x, y, z), (.62, .49, .245),
            M("navy"), parent=drawer, radius=.025)
        box(drawer.name + ".front", (x, y - .267, z), (.65, .035, .247),
            M("navy"), parent=drawer, radius=.019)
        box(drawer.name + ".label_plate", (x, y - .29, z + .06), (.17, .010, .045),
            M("silver"), parent=drawer, radius=.004)
        tube(drawer.name + ".handle", [(x - .09, y - .299, z - .025),
             (x - .09, y - .327, z - .025), (x + .09, y - .327, z - .025),
             (x + .09, y - .299, z - .025)], .007, M("bronze"), parent=drawer)
    for i, xx in enumerate((x - .30, x + .30)):
        for j, yy in enumerate((y - .24, y + .24)):
            wheel = asset("gallery.archive.wheel.%d%d" % (i, j), (xx, yy, .10), "spin", parent=root)
            wheel["interaction_axis"] = "X"
            cyl(wheel.name + ".rubber", (xx, yy, .10), .071, .041, M("black"),
                parent=wheel, rotation=(0, PI / 2, 0), vertices=32)
            cyl(wheel.name + ".hub", (xx, yy, .10), .040, .046, M("silver"),
                parent=wheel, rotation=(0, PI / 2, 0), vertices=24)
            tube(wheel.name + ".fork", [(xx - .032, yy, .105),
                 (xx - .032, yy, .188), (xx + .032, yy, .188),
                 (xx + .032, yy, .105)], .009, M("silver"), parent=root)
    # Neutral archive folios in the exposed transparent top tray.
    for i in range(3):
        box(root.name + ".folio.%d" % i, (x - .14 + i * .13, y + .025, 1.12 + i * .01),
            (.27, .35, .018), M("paper" if i == 1 else "navy"), parent=root, radius=.003)
    # Original tire bottom is .029; the gallery floor is at .15.
    root.location.z += .121


def lantern(index, x, y):
    root = asset("gallery.lantern.%02d" % index, (x, y, 0), "toggle")
    cyl(root.name + ".foot", (x, y, .06), .18, .105, M("navy"), parent=root, vertices=40)
    cyl(root.name + ".base", (x, y, .12), .156, .04, M("bronze"), parent=root, vertices=40)
    cyl(root.name + ".diffuser", (x, y, .405), .083, .52, M("warm"), parent=root, vertices=32)
    cyl(root.name + ".glass", (x, y, .405), .13, .53, M("glass"), parent=root, vertices=40)
    for i in range(4):
        theta = PI / 4 + i * PI / 2
        xx, yy = x + .139 * math.cos(theta), y + .139 * math.sin(theta)
        tube(root.name + ".rib.%d" % i, [(xx, yy, .135), (xx, yy, .70)],
             .009, M("bronze"), parent=root)
    cyl(root.name + ".cap", (x, y, .705), .16, .032, M("bronze"), parent=root, vertices=40)
    torus(root.name + ".handle", (x, y, .79), .073, .008, M("bronze"),
          parent=root, rotation=(PI / 2, 0, 0))
    root.location.z += .1425


def build():
    """Create 31 independent stable asset groups; return them for QA/export."""
    ROOTS.clear()
    make_table()
    shelf_library()
    for i, x in enumerate((-1.15, .35, 1.85), 1):
        album(i, x)
    ring_sculpture()
    task_lamp()
    tabletop_items()
    bench()
    archive_cart()
    for i, (x, y, height, radius) in enumerate((
            (-6.0, -2.8, 1.15, .28), (-5.8, 1.4, 1.48, .31),
            (6.6, 1.4, 1.34, .29), (6.5, -3.2, .98, .27)), 1):
        planter("gallery.planter.floor.%02d" % i, x, y, height, radius, 280 + i)
    lantern(1, -6.4, -2.5)
    lantern(2, 6.8, -2.6)
    return list(ROOTS)
