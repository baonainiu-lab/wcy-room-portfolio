"""Original award-placeholder capsules for the open About Nexus.

Authoring module only: the caller supplies Blender helpers and materials, then
places the returned root. All coordinates are local metres; Z is up and -Y is
the presentation side. No existing room, gallery or V1 award asset is reused.
"""

import math


def build_award_capsules(api):
    """Build a grounded 2.48 x 1.99 x 2.535 m collection with three assets."""
    root = api["root"]
    box = api["box"]
    cylinder = api["cylinder"]
    tube = api["tube"]
    mesh = api["mesh"]
    text = api["text"]
    mats = api["mats"]
    tau = math.tau

    def group(asset_id, parent=None, loc=(0, 0, 0), interactive=False):
        obj = root(asset_id, (0, 0, 0))
        obj.parent = parent
        obj.location = loc
        obj["asset_id"] = asset_id
        obj["interactive"] = interactive
        obj["placeholder"] = True
        obj["content_status"] = "pending_user_information"
        obj["display_label"] = "待补充"
        obj["content_kind"] = "award_placeholder"
        obj["design_note"] = "Original display sculpture; no real award is claimed."
        if parent is not None:
            obj["owner_asset_id"] = parent["asset_id"]
        return obj

    def finish(obj, bevel=0.004, segments=3):
        if bevel:
            mod = obj.modifiers.new("Machined edge radius", "BEVEL")
            mod.width = bevel
            mod.segments = segments
            mod.limit_method = "ANGLE"
            mod.use_clamp_overlap = True
            mod.harden_normals = True
            normals = obj.modifiers.new("Face weighted normals", "WEIGHTED_NORMAL")
            normals.keep_sharp = True
            normals.weight = 40
        return obj

    def convex_hull(points):
        points = sorted(set(points))

        def cross(o, a, b):
            return ((a[0] - o[0]) * (b[1] - o[1])
                    - (a[1] - o[1]) * (b[0] - o[0]))

        lower, upper = [], []
        for p in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-10:
                lower.pop()
            lower.append(p)
        for p in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-10:
                upper.pop()
            upper.append(p)
        return lower[:-1] + upper[:-1]

    centres = [(-0.66, -0.30), (0.66, -0.30), (0.0, 0.53)]

    def cluster_outline(radius):
        return convex_hull([
            (x + radius * math.cos(tau * i / 64),
             y + radius * math.sin(tau * i / 64))
            for x, y in centres for i in range(64)
        ])

    def horizontal_prism(name, outline, z0, z1, mat, parent, bevel=0.006):
        n = len(outline)
        verts = [(x, y, z0) for x, y in outline]
        verts += [(x, y, z1) for x, y in outline]
        faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n)
                  for i in range(n)]
        return finish(mesh(name, verts, faces, mat, parent), bevel)

    def front_prism(name, outline, y_front, y_back, mat, parent, bevel=0.004):
        # CCW X/Z outlines face -Y. The rear face and side walls close the solid.
        area = sum(outline[i][0] * outline[(i + 1) % len(outline)][1]
                   - outline[(i + 1) % len(outline)][0] * outline[i][1]
                   for i in range(len(outline)))
        outline = outline if area > 0 else list(reversed(outline))
        n = len(outline)
        verts = [(x, y_front, z) for x, z in outline]
        verts += [(x, y_back, z) for x, z in outline]
        faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
        faces += [(i, i + n, (i + 1) % n + n, (i + 1) % n)
                  for i in range(n)]
        return finish(mesh(name, verts, faces, mat, parent), bevel)

    def annulus(name, outer, inner, z0, z1, mat, parent, segments=64,
                bevel=0.0, smooth=True):
        verts = []
        for radius, z in ((outer, z0), (outer, z1), (inner, z0), (inner, z1)):
            verts += [(radius * math.cos(tau * i / segments),
                       radius * math.sin(tau * i / segments), z)
                      for i in range(segments)]
        faces = []
        for i in range(segments):
            j, n = (i + 1) % segments, segments
            faces.extend([(i, j, n + j, n + i),
                          (2*n + i, 3*n + i, 3*n + j, 2*n + j),
                          (i, 2*n + i, 2*n + j, j),
                          (n + i, n + j, 3*n + j, 3*n + i)])
        obj = mesh(name, verts, faces, mat, parent)
        for i, poly in enumerate(obj.data.polygons):
            poly.use_smooth = smooth and i % 4 < 2
        return finish(obj, bevel)

    def disk_facing_front(name, x, y, z, radius, depth, mat, parent, vertices=48):
        obj = cylinder(name, (x, y, z), radius, depth, mat, parent, vertices=vertices)
        obj.rotation_euler.x = math.pi / 2
        return obj

    def sector_outline(inner, outer, angle0, angle1, centre_z, steps=5):
        outer_arc = [(outer * math.cos(angle0 + (angle1-angle0) * i / steps),
                      centre_z + outer * math.sin(angle0 + (angle1-angle0) * i / steps))
                     for i in range(steps + 1)]
        inner_arc = [(inner * math.cos(angle0 + (angle1-angle0) * i / steps),
                      centre_z + inner * math.sin(angle0 + (angle1-angle0) * i / steps))
                     for i in reversed(range(steps + 1))]
        return outer_arc + inner_arc

    main = group("about.award_capsules")
    main["dimensions_nominal"] = [2.48, 1.99, 2.535]
    main["pivot_hint"] = "Floor level at the centre of the shared pedestal"
    main["glass_wall_thickness_m"] = 0.004

    # One structural plinth: the convex rounded triangle joins all three pods.
    horizontal_prism("capsules.shared.navy_casting", cluster_outline(0.580),
                     0.054, 0.177, mats["navy"], main, 0.018)
    horizontal_prism("capsules.shared.metal_reveal", cluster_outline(0.578),
                     0.177, 0.195, mats["metal"], main, 0.004)
    horizontal_prism("capsules.shared.ivory_deck", cluster_outline(0.557),
                     0.195, 0.235, mats["ivory"], main, 0.012)
    for i, (x, y) in enumerate(centres, 1):
        cylinder(f"capsules.foot.{i}.rubber", (x, y, 0.014), 0.345, 0.028,
                 mats["rubber"], main)
        cylinder(f"capsules.foot.{i}.metal", (x, y, 0.046), 0.302, 0.046,
                 mats["metal"], main)
    box("capsules.shared.label_recess", (0, -0.848, 0.113), (0.68, 0.035, 0.085),
        mats["dark"], main, bevel=0.012)
    text("capsules.shared.pending", "奖项资料待补充", (0, -0.868, 0.098),
         0.037, mats["ivory"], main, rotation=(math.pi / 2, 0, 0))

    def build_capsule(index, centre, height, radius):
        asset_id = f"about.award.{index:02d}"
        pod = group(asset_id, main, (*centre, 0.235), interactive=True)
        pod["hover_scale"] = 1.025
        pod["pivot_hint"] = "Capsule base centre; child sculpture may turn independently"
        pod["display_height_m"] = height
        cylinder(f"{asset_id}.lower_drum", (0, 0, 0.066), radius+0.022, 0.132,
                 mats["navy"], pod)
        cylinder(f"{asset_id}.lower_shoulder", (0, 0, 0.143), radius+0.024, 0.030,
                 mats["metal"], pod)
        cylinder(f"{asset_id}.tray_lift", (0, 0, 0.183), 0.124, 0.070,
                 mats["dark"], pod)
        # The front plaque sits on the drum; it does not claim an achievement.
        box(f"{asset_id}.nameplate", (0, -radius-0.012, 0.076), (0.25, 0.023, 0.075),
            mats["brass"], pod, bevel=0.009)
        text(f"{asset_id}.pending", "待补充", (0, -radius-0.025, 0.065),
             0.030, mats["dark"], pod, rotation=(math.pi/2, 0, 0))

        glass_root = group(asset_id+".glass", pod, (0, 0, 0.158))
        glass = annulus(f"{asset_id}.closed_4mm_glass", radius, radius-0.004,
                        0, height-0.268, mats["glass"], glass_root, segments=96)
        glass["physical_thickness_m"] = 0.004
        glass["closed_volume"] = True

        # A rear spine fastens the cover to its pedestal and hides the seam.
        box(f"{asset_id}.rear_spine", (0, radius+0.007, height/2),
            (0.036, 0.030, height-0.146), mats["metal"], pod, bevel=0.008)
        lid = group(asset_id+".lid", pod, (0, 0, height-0.110))
        cylinder(f"{asset_id}.lid.lower_seal", (0, 0, 0.007), radius+0.003, 0.014,
                 mats["rubber"], lid)
        cylinder(f"{asset_id}.lid.machined_cover", (0, 0, 0.050), radius+0.025, 0.086,
                 mats["metal"], lid)
        cylinder(f"{asset_id}.lid.ceramic_insert", (0, 0, 0.100), radius-0.008, 0.020,
                 mats["ivory"], lid)
        annulus(f"{asset_id}.lid.underside_light", radius-0.014, radius-0.041,
                -0.006, 0.0, mats["light"], lid)
        # Retaining tabs contact rubber pads, rather than cutting through glass.
        latches = group(asset_id+".latches", pod)
        for k, angle in enumerate((-math.pi*0.28, -math.pi*0.72)):
            for suffix, z in (("bottom", 0.184), ("top", height-0.096)):
                radial = radius+0.006
                pad = box(f"{asset_id}.clamp.{k}.{suffix}.pad",
                          (radial*math.cos(angle), radial*math.sin(angle), z),
                          (0.057, 0.012, 0.043), mats["rubber"], latches, bevel=0.003)
                pad.rotation_euler.z = angle+math.pi/2
                radial = radius+0.020
                clamp = box(f"{asset_id}.clamp.{k}.{suffix}.metal",
                            (radial*math.cos(angle), radial*math.sin(angle), z),
                            (0.067, 0.020, 0.079), mats["metal"], latches, bevel=0.006)
                clamp.rotation_euler.z = angle+math.pi/2
        tray = group(asset_id+".tray", pod, (0, 0, 0.215))
        cylinder(f"{asset_id}.tray.rim", (0, 0, 0.014), radius-0.045, 0.028,
                 mats["brass"], tray)
        cylinder(f"{asset_id}.tray.insert", (0, 0, 0.034), radius-0.065, 0.012,
                 mats["dark"], tray)
        sculpture = group(asset_id+".sculpture", pod, (0, 0, 0.255), interactive=True)
        sculpture["interaction_hint"] = "Rotate around local Z; retain capsule position"
        return sculpture

    # 01 — a fan medal with seven separated, machined leaves and a visible hub.
    fan = build_capsule(1, centres[0], 1.62, 0.440)
    fan["sculpture_form"] = "seven_leaf_folded_fan"
    cylinder("award.fan.foot", (0, 0, 0.035), 0.188, 0.070, mats["navy"], fan)
    cylinder("award.fan.foot_cap", (0, 0, 0.076), 0.166, 0.014, mats["brass"], fan)
    front_prism("award.fan.split_stem",
                [(-0.043, 0.079), (0.043, 0.079), (0.034, 0.485),
                 (0.067, 0.591), (0.054, 0.652), (-0.054, 0.652),
                 (-0.067, 0.591), (-0.034, 0.485)],
                0.026, 0.084, mats["metal"], fan, 0.006)
    disk_facing_front("award.fan.rear_hub", 0, 0.032, 0.630,
                      0.088, 0.088, mats["navy"], fan)
    for i in range(7):
        a = math.radians(22 + i*19.5)
        outline = sector_outline(0.063, 0.365, a, a+math.radians(17), 0.630)
        front_prism(f"award.fan.leaf.{i}", outline, -0.061 + 0.004*(i % 2),
                    0.025, mats[("brass", "ivory", "metal")[i % 3]], fan, 0.004)
    disk_facing_front("award.fan.central_lock", 0, -0.071, 0.630,
                      0.064, 0.027, mats["orange"], fan)

    # 02 — stepped, cantilevered plates on a load-bearing central tower.
    tower = build_capsule(2, centres[1], 1.95, 0.445)
    tower["sculpture_form"] = "eleven_layer_stepped_tower"
    cylinder("award.tower.foot", (0, 0, 0.038), 0.205, 0.076, mats["navy"], tower)
    box("award.tower.structural_spine", (0, 0, 0.601), (0.104, 0.104, 1.096),
        mats["brass"], tower, bevel=0.012)
    for i in range(11):
        w, d = 0.485-0.023*i, 0.335-0.014*i
        z = 0.153+0.091*i
        x, y = 0.038*math.sin(i*0.57), 0.023*math.sin(i*0.39)
        tile = box(f"award.tower.terrace.{i}", (x, y, z), (w, d, 0.054),
                   mats[("metal", "ivory", "navy")[i % 3]], tower, bevel=0.012)
        tile.rotation_euler.z = i*0.145
        if i in (0, 4, 8):
            # The coloured edge is inset into the front face of its own plate.
            a = i*0.145
            cx, cy = x+(d/2-0.002)*math.sin(a), y-(d/2-0.002)*math.cos(a)
            edge = box(f"award.tower.edge_mark.{i}", (cx, cy, z),
                       (w*0.44, 0.008, 0.018), mats["orange"], tower, bevel=0.003)
            edge.rotation_euler.z = a
    crown = box("award.tower.crown", (0, 0, 1.155), (0.123, 0.123, 0.096),
                mats["ivory"], tower, bevel=0.017)
    crown.rotation_euler.z = 0.45

    # 03 — a segmented hexagonal seal, supported by a solid bifurcated stalk.
    emblem = build_capsule(3, centres[2], 2.30, 0.425)
    emblem["sculpture_form"] = "six_segment_geometric_seal"
    cylinder("award.seal.foot", (0, 0, 0.038), 0.196, 0.076, mats["navy"], emblem)
    cylinder("award.seal.foot_inlay", (0, 0, 0.079), 0.171, 0.012,
             mats["brass"], emblem)
    front_prism("award.seal.fork_support",
                [(-0.041, 0.084), (0.041, 0.084), (0.041, 0.52),
                 (0.13, 0.73), (0.11, 0.79), (0.07, 0.77), (0, 0.62),
                 (-0.07, 0.77), (-0.11, 0.79), (-0.13, 0.73), (-0.041, 0.52)],
                0.051, 0.108, mats["metal"], emblem, 0.007)
    # The backing hexagon joins all leaves and intersects the support below it.
    hexagon = [(0.308*math.cos(tau*i/6), 1.04+0.308*math.sin(tau*i/6))
               for i in range(6)]
    front_prism("award.seal.structural_back", hexagon, 0.047, 0.100,
                mats["navy"], emblem, 0.008)
    for i in range(6):
        a, b = tau*i/6+0.075, tau*(i+1)/6-0.075
        outline = [(0.103*math.cos(a), 1.04+0.103*math.sin(a)),
                   (0.363*math.cos(a), 1.04+0.363*math.sin(a)),
                   (0.390*math.cos((a+b)/2), 1.04+0.390*math.sin((a+b)/2)),
                   (0.363*math.cos(b), 1.04+0.363*math.sin(b)),
                   (0.103*math.cos(b), 1.04+0.103*math.sin(b))]
        front_prism(f"award.seal.segment.{i}", outline,
                    -0.045-(i % 2)*0.014, 0.052,
                    mats[("ivory", "metal", "brass")[i % 3]], emblem, 0.006)
    hub = [(0.091*math.cos(tau*i/6), 1.04+0.091*math.sin(tau*i/6))
           for i in range(6)]
    front_prism("award.seal.centre", hub, -0.072, 0.051,
                mats["orange"], emblem, 0.009)

    def tag_descendants(parent):
        for child in parent.children:
            child["owner_asset_id"] = parent["asset_id"]
            if child.get("asset_id"):
                tag_descendants(child)

    tag_descendants(main)
    return main
