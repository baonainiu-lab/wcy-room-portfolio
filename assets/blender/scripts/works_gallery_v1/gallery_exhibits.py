"""Six independent museum bays for concept B, the sunlit glass gallery.

All imagery and display objects are original procedural placeholder studies.
There are no imported images, biographical claims, or third-party assets.
Coordinates are world-space, Z-up.  Front faces point toward negative Y.
"""

from math import cos, sin, pi, radians

from gallery_common import (
    M, group, box, cyl, sphere, tube, torus, mesh, label, rounded_rect,
)


STATION_X = (-4.8, -2.7, -0.6, 1.5, 3.6, 5.7)
STATION_Y = 2.45
FLOOR_Z = 0.15


def _asset(name, location, parent=None, kind="placeholder-study"):
    root = group(name, loc=location, parent=parent, atlas=2)
    root["asset_id"] = name
    root["content_status"] = "待补充"
    root["placeholder"] = True
    root["asset_kind"] = kind
    return root


def _mark(obj, name, kind="exhibit-component"):
    obj["asset_id"] = name
    obj["asset_kind"] = kind
    return obj


def _poly_relief(name, points, x, y, z, material, parent, depth=0.008):
    """Extrude an original XZ polygon, with its visible face at y."""
    count = len(points)
    verts = [(x + u, y, z + v) for u, v in points]
    verts += [(x + u, y + depth, z + v) for u, v in points]
    faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count)
              for i in range(count)]
    return mesh(name, verts, faces, material, parent=parent)


def _ellipse(cx, cz, rx, rz, start=0, end=2*pi, count=72, sector=False):
    pts = [(cx + rx*cos(start + (end-start)*i/count),
            cz + rz*sin(start + (end-start)*i/count)) for i in range(count + 1)]
    if abs(end-start - 2*pi) < 0.00001:
        pts.pop()
    if sector:
        pts.append((cx, cz))
    return pts


def _screw(name, position, parent, radius=0.013, front=True):
    rotation = (pi/2, 0, 0) if front else None
    return cyl(name, position, radius, 0.008, M["silver"], parent=parent,
               rotation=rotation, vertices=20)


def _card(name, x, y, z, parent, number, width=0.70, height=0.40):
    """A real inclined museum label; type follows the card plane."""
    card = _asset(name, (x, y, z), parent, "museum-label")
    tilt = radians(24)
    normal = (0, -sin(tilt), cos(tilt))

    def point(u, v, elevation=0):
        return (x + u, y + v*cos(tilt) + normal[1]*elevation,
                z + v*sin(tilt) + normal[2]*elevation)

    backing = box(name + ".rim", point(0, 0), (width, height, 0.025),
                  M["bronze"], parent=card, radius=0.018)
    backing.rotation_euler = (tilt, 0, 0)
    paper = box(name + ".paper", point(0, 0, 0.020),
                (width-0.038, height-0.038, 0.014), M["paper"],
                parent=card, radius=0.009)
    paper.rotation_euler = (tilt, 0, 0)
    label(name + ".number", number, point(-width/2+0.045, 0.065, 0.031),
          0.064, M["ink"], parent=card, rotation=(tilt, 0, 0))
    label(name + ".type", "ABSTRACT STUDY", point(-width/2+0.045, -0.018, 0.031),
          0.029, M["ink"], parent=card, rotation=(tilt, 0, 0))
    label(name + ".pending", "CONTENT PENDING", point(-width/2+0.045, -0.071, 0.031),
          0.025, M["ink"], parent=card, rotation=(tilt, 0, 0))
    stripe = box(name + ".rule", point(0.115, 0.082, 0.031),
                 (0.23, 0.008, 0.002), M["bronze"], parent=card, radius=0.001)
    stripe.rotation_euler = (tilt, 0, 0)
    return card


def _backboard(index, x):
    name = "gallery.work.%02d" % index
    bay = _asset(name, (x, STATION_Y, FLOOR_Z), kind="work-display-station")
    bay["display_number"] = "%02d" % index
    bay["presentation"] = "Original abstract placeholder; real work pending"
    # The three nested solids meet at their faces, leaving precise metal rims.
    rounded_rect(name + ".silver_shell", (x, 2.45, 1.915),
                 1.68, 3.07, 0.24, 0.17, M["silver"], parent=bay)
    rounded_rect(name + ".champagne_reveal", (x, 2.308, 1.915),
                 1.566, 2.956, 0.044, 0.135, M["bronze"], parent=bay)
    rounded_rect(name + ".navy_inset", (x, 2.266, 1.915),
                 1.494, 2.884, 0.040, 0.103, M["navy"], parent=bay)
    # Small architectural feet keep the boards physically rooted in the floor.
    for side in (-1, 1):
        box(name + ".foot.%s" % side, (x + side*0.55, 2.45, 0.264),
            (0.20, 0.48, 0.228), M["navy"], parent=bay, radius=0.045)
        box(name + ".shoe.%s" % side, (x + side*0.55, 2.45, 0.174),
            (0.26, 0.53, 0.048), M["silver"], parent=bay, radius=0.023)
    label(name + ".number", "%02d" % index, (x-0.61, 2.220, 3.174),
          0.172, M["ivory"], parent=bay)
    # Fine warm edge lines, not additional light sources.
    for side in (-1, 1):
        tube(name + ".warm_edge.%s" % side,
             [(x+side*0.713, 2.239, 0.535),
              (x+side*0.713, 2.239, 3.251)],
             0.0065, M["warm"], parent=bay)
    box(name + ".header_rule", (x+0.285, 2.235, 3.211),
        (0.59, 0.009, 0.009), M["bronze"], parent=bay, radius=0.003)
    return bay


def _art(index, x, bay):
    """Three bespoke compositions, all real relief geometry."""
    name = "gallery.work.%02d.art" % index
    art = _asset(name, (x, 2.18, 2.12), bay, "original-geometric-relief")
    art["source"] = "Original procedural geometry; no image textures"
    box(name + ".outer_moulding", (x, 2.208, 2.12),
        (1.238, 0.074, 1.78), M["silver"], parent=art, radius=0.028)
    box(name + ".inner_moulding", (x, 2.158, 2.12),
        (1.15, 0.026, 1.692), M["bronze"], parent=art, radius=0.014)
    box(name + ".mat", (x, 2.135, 2.12),
        (1.092, 0.020, 1.634), M["ivory"], parent=art, radius=0.005)
    box(name + ".paper", (x, 2.119, 2.12),
        (0.896, 0.012, 1.442), M["paper"], parent=art, radius=0.002)
    # Two or three millimetres of separation create fine, legible relief shadows.
    def shape(suffix, points, material, layer=0):
        return _poly_relief(name + "." + suffix, points, x,
                            2.102-layer*0.011, 2.12, M[material], art)
    if index == 1:
        shape("upper_sweep", _ellipse(0.352, 0.197, 0.62, 0.518,
                                      pi/2, 3*pi/2, 56, True), "navy")
        shape("lower_sweep", _ellipse(-0.352, -0.326, 0.64, 0.385,
                                      -pi/2, pi/2, 56, True), "bronze", 1)
        shape("counterform", [(-0.43, 0.68), (-0.23, 0.68),
                              (-0.11, 0.285), (-0.43, 0.065)], "ivory", 2)
        shape("horizon", [(-0.40, -0.592), (0.395, -0.592),
                           (0.395, -0.605), (-0.40, -0.605)], "ink", 3)
    elif index == 3:
        shape("field", [(-0.393, -0.647), (0.392, -0.647),
                        (0.392, 0.647), (-0.393, 0.647)], "ivory")
        shape("upper_half_disc", _ellipse(0.014, 0.288, 0.356, 0.375,
                                           -pi/2, pi/2, 60, True), "navy", 1)
        shape("warm_disc", _ellipse(-0.058, -0.173, 0.322, 0.359), "bronze", 2)
        shape("dark_overlap", _ellipse(0.134, -0.321, 0.229, 0.284), "ink", 3)
        shape("fine_axis", [(-0.335, -0.62), (-0.327, -0.62),
                            (-0.327, 0.61), (-0.335, 0.61)], "bronze", 4)
    else:
        # A broad arch and an off-centre oval, distinct from both preceding works.
        arch = [(-0.382, -0.602), (0.382, -0.602)]
        arch += _ellipse(0, 0.184, 0.382, 0.449, 0, pi, 60)
        shape("terracotta_arch", arch, "bronze")
        inner = [(-0.273, -0.534), (0.273, -0.534)]
        inner += _ellipse(0, 0.174, 0.273, 0.318, 0, pi, 56)
        shape("ivory_arch", inner, "ivory", 1)
        shape("oval", _ellipse(0.109, -0.163, 0.278, 0.321), "navy", 2)
        shape("small_counterweight", _ellipse(-0.276, -0.508, 0.046, 0.046,
                                                count=36), "ink", 3)
    for side in (-1, 1):
        _screw(name + ".mount.%s" % side, (x+side*0.575, 2.165, 2.12), art, 0.012)
    return art


def _art_shelf(index, x, bay):
    name = "gallery.work.%02d.console" % index
    console = _asset(name, (x, 1.905, 0.835), bay, "display-console")
    for side in (-1, 1):
        box(name + ".leg.%s" % side, (x+side*0.645, 2.057, 0.455),
            (0.105, 0.355, 0.610), M["navy"], parent=console, radius=0.028)
        box(name + ".leg_trim.%s" % side, (x+side*0.645, 1.877, 0.455),
            (0.107, 0.010, 0.582), M["silver"], parent=console, radius=0.008)
    box(name + ".underside", (x, 1.905, 0.785), (1.65, 0.65, 0.054),
        M["navy"], parent=console, radius=0.045)
    box(name + ".silver_top", (x, 1.905, 0.842), (1.67, 0.67, 0.06),
        M["silver"], parent=console, radius=0.052)
    box(name + ".leather_pad", (x, 1.905, 0.881), (1.51, 0.51, 0.018),
        M["navy"], parent=console, radius=0.028)
    tube(name + ".front_light", [(x-0.71, 1.574, 0.824),
                                  (x+0.71, 1.574, 0.824)],
         0.006, M["warm"], parent=console)
    _card("gallery.work.%02d.label" % index, x+0.165, 1.837, 0.985,
          bay, "%02d" % index)
    # A tiny freestanding geometry study beside each angled label.
    detail_name = "gallery.work.%02d.maquette" % index
    detail = _asset(detail_name, (x-0.48, 1.846, 0.92), bay, "abstract-maquette")
    cyl(detail_name + ".base", (x-0.49, 1.848, 0.910), 0.145, 0.040,
        M["bronze"], parent=detail, vertices=64)
    cyl(detail_name + ".inset", (x-0.49, 1.848, 0.936), 0.117, 0.012,
        M["navy"], parent=detail, vertices=64)
    if index == 1:
        torus(detail_name + ".orbit", (x-0.49, 1.848, 1.078), 0.119, 0.011,
              M["bronze"], parent=detail, rotation=(radians(74), 0, radians(14)))
        sphere(detail_name + ".pearl", (x-0.49, 1.848, 1.070),
               (0.043, 0.043, 0.043), M["silver"], parent=detail)
        cyl(detail_name + ".stem", (x-0.49, 1.848, 0.989), 0.009, 0.10,
            M["bronze"], parent=detail, vertices=24)
    elif index == 3:
        _poly_relief(detail_name + ".fold", [(-0.072, 0), (0.075, 0),
                      (0.087, 0.192), (0.016, 0.228)],
                     x-0.49, 1.82, 0.944, M["silver"], detail, depth=0.045)
        tube(detail_name + ".seam", [(x-0.491, 1.812, 0.947),
                                     (x-0.474, 1.812, 1.165)],
             0.006, M["bronze"], parent=detail)
    else:
        torus(detail_name + ".standing_ring", (x-0.49, 1.848, 1.065),
              0.116, 0.014, M["silver"], parent=detail, rotation=(pi/2, 0, 0))
        sphere(detail_name + ".counterweight", (x-0.44, 1.838, 0.983),
               (0.045, 0.035, 0.045), M["bronze"], parent=detail)


def _glass_case(index, x, bay):
    name = "gallery.work.%02d.vitrine" % index
    cabinet = _asset(name, (x, 1.69, 0.15), bay, "independent-glass-vitrine")
    # A solid, shallow plinth with a recessed toe and individually framed glass.
    box(name + ".toe", (x, 1.69, 0.213), (1.135, 0.853, 0.126),
        M["black"], parent=cabinet, radius=0.035)
    box(name + ".base_band", (x, 1.69, 0.291), (1.26, 0.972, 0.046),
        M["silver"], parent=cabinet, radius=0.038)
    box(name + ".pedestal", (x, 1.69, 0.632), (1.228, 0.94, 0.636),
        M["navy"], parent=cabinet, radius=0.035)
    box(name + ".cap", (x, 1.69, 0.981), (1.30, 1.012, 0.062),
        M["silver"], parent=cabinet, radius=0.042)
    box(name + ".display_pad", (x, 1.69, 1.023), (1.134, 0.845, 0.022),
        M["ivory"], parent=cabinet, radius=0.016)
    for side in (-1, 1):
        box(name + ".base_reveal.%s" % side, (x+side*0.593, 1.69, 0.623),
            (0.012, 0.903, 0.588), M["bronze"], parent=cabinet, radius=0.006)
    bottom, top = 1.047, 2.615
    cy, halfw, halfd = 1.69, 0.568, 0.419
    midz = (bottom+top)/2
    height = top-bottom
    # Four separate panes.  Corner posts cover the intentionally open edge joints.
    for side in (-1, 1):
        _mark(box(name + ".glass.side.%s" % side,
                  (x+side*halfw, cy, midz), (0.012, 0.813, height-0.05),
                  M["glass"], parent=cabinet, radius=0.004),
              name + ".glass.side.%s" % side, "glass-panel")
        _mark(box(name + ".glass.face.%s" % side,
                  (x, cy+side*halfd, midz), (1.111, 0.012, height-0.05),
                  M["glass"], parent=cabinet, radius=0.004),
              name + ".glass.face.%s" % side, "glass-panel")
    _mark(box(name + ".glass.roof", (x, cy, top-0.015),
              (1.104, 0.806, 0.012), M["glass"], parent=cabinet, radius=0.004),
          name + ".glass.roof", "glass-panel")
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(name + ".post.%s.%s" % (sx, sy),
                (x+sx*halfw, cy+sy*halfd, midz), 0.016, height,
                M["bronze"], parent=cabinet, vertices=32)
    for level, zz in (("lower", bottom), ("upper", top)):
        tube(name + ".rim." + level,
             [(x-halfw, cy-halfd, zz), (x+halfw, cy-halfd, zz),
              (x+halfw, cy+halfd, zz), (x-halfw, cy+halfd, zz)],
             0.022, M["silver"], parent=cabinet, closed=True)
    tube(name + ".light_strip", [(x-0.46, cy+0.385, top-0.032),
                                  (x+0.46, cy+0.385, top-0.032)],
         0.008, M["warm"], parent=cabinet)
    # Small mounting ledge for the label stays clear of the glass front.
    box(name + ".label_bracket", (x, 1.136, 0.936),
        (0.79, 0.215, 0.038), M["silver"], parent=cabinet, radius=0.022)
    _card("gallery.work.%02d.label" % index, x, 1.09, 1.036, bay,
          "%02d" % index, width=0.72, height=0.34)
    return cabinet


def _case_two(x, bay, cabinet):
    name = "gallery.work.02.geometry"
    study = _asset(name, (x, 1.69, 1.045), bay, "sphere-and-fold-study")
    box(name + ".low_plinth", (x-0.22, 1.69, 1.090), (0.38, 0.45, 0.112),
        M["navy"], parent=study, radius=0.012)
    box(name + ".high_plinth", (x+0.195, 1.76, 1.177), (0.40, 0.43, 0.286),
        M["silver"], parent=study, radius=0.012)
    cyl(name + ".sphere_stem", (x-0.23, 1.69, 1.331), 0.010, 0.37,
        M["bronze"], parent=study, vertices=28)
    _mark(sphere(name + ".sphere", (x-0.23, 1.69, 1.690),
                  (0.179, 0.179, 0.179), M["silver"], parent=study),
          name + ".sphere", "abstract-display-object")
    # Three triangular facets join at an off-centre peak above a folded base.
    verts = [(x-0.012, 1.532, 1.320), (x+0.398, 1.557, 1.320),
             (x+0.310, 1.954, 1.320), (x+0.08, 1.908, 1.320),
             (x+0.166, 1.745, 1.918)]
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)]
    _mark(mesh(name + ".folded_form", verts, faces, M["ivory"], parent=study),
          name + ".folded_form", "abstract-display-object")
    tube(name + ".gold_fold", [verts[0], verts[4], verts[2]], 0.007,
         M["bronze"], parent=study)
    return study


def _case_five(x, bay, cabinet):
    name = "gallery.work.05.geometry"
    study = _asset(name, (x, 1.69, 1.034), bay, "faceted-equilibrium-study")
    cyl(name + ".puck", (x, 1.69, 1.063), 0.31, 0.058,
        M["bronze"], parent=study, vertices=64)
    cyl(name + ".inset", (x, 1.69, 1.100), 0.274, 0.016,
        M["navy"], parent=study, vertices=64)
    cyl(name + ".support", (x, 1.69, 1.230), 0.013, 0.244,
        M["bronze"], parent=study, vertices=28)
    # An elongated irregular octahedron with metal edge inlays.
    verts = [(x, 1.69, 2.198), (x, 1.69, 1.346),
             (x-0.33, 1.69, 1.771), (x+0.33, 1.69, 1.771),
             (x, 1.429, 1.735), (x, 1.951, 1.815)]
    faces = [(0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2),
             (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5)]
    _mark(mesh(name + ".faceted_core", verts, faces, M["navy"], parent=study),
          name + ".faceted_core", "abstract-display-object")
    for i, j in ((0, 2), (0, 4), (0, 3), (0, 5), (1, 2), (1, 4),
                 (1, 3), (1, 5), (2, 4), (4, 3), (3, 5), (5, 2)):
        tube(name + ".inlay.%s.%s" % (i, j), [verts[i], verts[j]],
             0.006, M["bronze"], parent=study)
    return study


def _ribbon(name, x, y, parent, phase, material):
    """Smooth elliptical ribbon section swept along a sculptural spiral."""
    samples, sides = 120, 10
    verts = []
    for i in range(samples + 1):
        t = i/samples
        angle = phase + t*2*pi*1.24
        r = 0.035 + 0.282*sin(pi*t)**0.83
        center = (x+r*cos(angle), y+0.64*r*sin(angle), 1.322+1.565*t)
        # Radial width produces the broad, rotating face; a much slimmer tangent
        # section prevents a wire-like appearance and keeps the two ribbons apart.
        width = 0.055*(0.30 + 0.70*sin(pi*t)**0.45)
        thickness = 0.015
        for j in range(sides):
            a = 2*pi*j/sides
            u, v = width*cos(a), thickness*sin(a)
            verts.append((center[0]+u*cos(angle)-v*sin(angle),
                          center[1]+u*sin(angle)+v*cos(angle), center[2]))
    faces = []
    for i in range(samples):
        for j in range(sides):
            a, b = i*sides+j, i*sides+(j+1)%sides
            faces.append((a, b, b+sides, a+sides))
    faces += [tuple(reversed(range(sides))),
              tuple(samples*sides+j for j in range(sides))]
    obj = mesh(name, verts, faces, material, parent=parent)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return _mark(obj, name, "sculpture-ribbon")


def _sculpture(x, bay):
    name = "gallery.work.04.sculpture"
    display = _asset(name, (x, 1.69, FLOOR_Z), bay, "ribbon-sculpture-display")
    cyl(name + ".toe", (x, 1.69, 0.20), 0.506, 0.10,
        M["navy"], parent=display, vertices=96)
    cyl(name + ".pedestal", (x, 1.69, 0.702), 0.584, 0.904,
        M["silver"], parent=display, vertices=96)
    torus(name + ".lower_band", (x, 1.69, 0.276), 0.575, 0.010,
          M["bronze"], parent=display)
    torus(name + ".upper_band", (x, 1.69, 1.143), 0.582, 0.012,
          M["bronze"], parent=display)
    cyl(name + ".black_cap", (x, 1.69, 1.190), 0.604, 0.072,
        M["black"], parent=display, vertices=96)
    cyl(name + ".top_plate", (x, 1.69, 1.242), 0.557, 0.032,
        M["silver"], parent=display, vertices=96)
    cyl(name + ".sculpture_socket", (x, 1.69, 1.290), 0.148, 0.064,
        M["navy"], parent=display, vertices=64)
    model = _asset(name + ".model", (x, 1.69, 1.322), display,
                   "original-double-ribbon-sculpture")
    _ribbon(name + ".model.silver_ribbon", x, 1.69, model, 0, M["silver"])
    _ribbon(name + ".model.champagne_ribbon", x, 1.69, model, pi, M["bronze"])
    # Independent small engineering details remain individually selectable.
    for i in range(4):
        a = i*pi/2+pi/4
        _screw(name + ".cap_bolt.%d" % i,
               (x+0.472*cos(a), 1.69+0.472*sin(a), 1.262), display, 0.014, False)
    box(name + ".label_mount", (x, 0.930, 0.879),
        (0.72, 0.354, 0.04), M["bronze"], parent=display, radius=0.025)
    _card("gallery.work.04.label", x, 0.925, 0.977, bay, "04",
          width=0.68, height=0.34)
    return display


def build():
    """Build all six bays, returning plain metadata for the scene manifest."""
    metadata = []
    for index, x in enumerate(STATION_X, 1):
        bay = _backboard(index, x)
        if index in (1, 3, 6):
            _art(index, x, bay)
            _art_shelf(index, x, bay)
            exhibit = "original-geometric-relief"
        elif index in (2, 5):
            cabinet = _glass_case(index, x, bay)
            if index == 2:
                _case_two(x, bay, cabinet)
            else:
                _case_five(x, bay, cabinet)
            exhibit = "independent-glass-vitrine"
        else:
            _sculpture(x, bay)
            exhibit = "original-double-ribbon-sculpture"
        metadata.append({
            "asset_id": "gallery.work.%02d" % index,
            "position": [x, STATION_Y, FLOOR_Z],
            "display_number": "%02d" % index,
            "exhibit_type": exhibit,
            "content_status": "待补充",
            "original_geometry": True,
        })
    return metadata
