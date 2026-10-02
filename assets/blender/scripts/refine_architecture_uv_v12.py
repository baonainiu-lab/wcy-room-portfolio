"""Reweight V12 architectural BakeUV without changing geometry or saving files.

EXPERIMENTAL, NOT RECOMMENDED FOR THE CURRENT V12 RELEASE: CPU proofs show
strict 16px packing plus whole-wall weighting reduces visible platform density
more than it improves walls. Keep this opt-in; do not enable it automatically.

Hook signature for prepare_dual_bake_v8: refine(atlas, group, size).
Flat platform caps are separated from visible bevels in UV space only. Hidden
cap islands are reduced; uncertain caps retain density. Large bevel rings become
four continuous strips with their original UV area preserved before packing.
"""
import math
import time
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PADDING_PX = 16
HIDDEN_LINEAR_SCALE = .20
ARCHITECTURE_LINEAR_WEIGHT = 1.6


def _islands(obj, face_classes=None):
    mesh = obj.data
    uv = mesh.uv_layers['BakeUV'].data
    parent = list(range(len(mesh.polygons)))
    edge_faces = {}

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for face in mesh.polygons:
        loops = list(face.loop_indices)
        for a, b in zip(loops, loops[1:] + loops[:1]):
            va, vb = mesh.loops[a].vertex_index, mesh.loops[b].vertex_index
            ua = tuple(round(v, 7) for v in uv[a].uv)
            ub = tuple(round(v, 7) for v in uv[b].uv)
            key = (va, vb, ua, ub) if va < vb else (vb, va, ub, ua)
            if face_classes is not None:
                key = (face_classes[face.index], key)
            if key in edge_faces:
                parent[root(edge_faces[key])] = root(face.index)
            else:
                edge_faces[key] = face.index
    islands = {}
    for face in mesh.polygons:
        island = islands.setdefault(root(face.index), {'faces': [], 'loops': [], 'triangles': [],
                                   'visibility_class': face_classes[face.index] if face_classes else None})
        island['faces'].append(face.index)
        island['loops'].extend(face.loop_indices)
    mesh.calc_loop_triangles()
    for triangle in mesh.loop_triangles:
        islands[root(triangle.polygon_index)]['triangles'].append(triangle.index)
    return list(islands.values())


def _uv_area(mesh, triangle):
    uv = mesh.uv_layers['BakeUV'].data
    a, b, c = (uv[i].uv for i in triangle.loops)
    return abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) * .5


def _metrics(group, size):
    rows = []
    for obj in group:
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv_area = 0.0
        area = 0.0
        for triangle in mesh.loop_triangles:
            a, b, c = (obj.matrix_world @ mesh.vertices[i].co for i in triangle.vertices)
            area += (b-a).cross(c-a).length * .5
            uv_area += _uv_area(mesh, triangle)
        rows.append({'owner': obj.get('owner_asset_id', obj.name),
                     'islands': len(_islands(obj)), 'world_surface_area_m2': round(area, 5),
                     'uv_area': round(uv_area, 7),
                     'texels_per_m_all_faces': round(size * math.sqrt(uv_area/area), 3) if area else 0})
    return {'objects': rows, 'total_uv_area': round(sum(row['uv_area'] for row in rows), 7)}


def _face_metrics(obj, faces, size):
    area, uv_area = 0.0, 0.0
    faces = set(faces)
    for triangle in obj.data.loop_triangles:
        if triangle.polygon_index not in faces:
            continue
        a, b, c = (obj.matrix_world @ obj.data.vertices[i].co for i in triangle.vertices)
        area += (b-a).cross(c-a).length * .5
        uv_area += _uv_area(obj.data, triangle)
    return {'world_area_m2': round(area, 5), 'uv_area': round(uv_area, 7),
            'texels_per_m': round(size*math.sqrt(uv_area/area), 3) if area else 0}


def _directions():
    # All azimuths, deliberately wider than the actual quarter-turn camera range.
    directions = [Vector((0, 0, 1))]
    for elevation in (2, 20, 45, 70):
        elevation = math.radians(elevation)
        for step in range(16):
            azimuth = step * math.tau / 16
            directions.append(Vector((math.cos(azimuth)*math.cos(elevation),
                                      math.sin(azimuth)*math.cos(elevation), math.sin(elevation))))
    return directions


def _hidden_island(obj, island, tree, vertices, directions):
    mesh = obj.data
    # Center, near all three corners and near each edge. No face-center-only test.
    barycentrics = ((1/3, 1/3, 1/3), (.98, .01, .01), (.01, .98, .01), (.01, .01, .98),
                    (.499, .499, .002), (.499, .002, .499), (.002, .499, .499))
    tested = 0
    for index in island['triangles']:
        triangle = mesh.loop_triangles[index]
        a, b, c = (vertices[i] for i in triangle.vertices)
        normal = (b-a).cross(c-a)
        if normal.length < 1e-12:
            continue
        normal.normalize()
        # Mixed side-wall islands must never be downweighted.
        if abs(normal.z) < .68:
            return False, tested, 'mixed_or_vertical_faces'
        front_directions = [direction for direction in directions if normal.dot(direction) > .0001]
        if not front_directions:
            # Exactly horizontal downward faces cannot face the upper hemisphere.
            continue
        for wa, wb, wc in barycentrics:
            origin = a*wa + b*wb + c*wc + normal * .00002
            for direction in front_directions:
                tested += 1
                hit = tree.ray_cast(origin, direction, 100)
                if hit[0] is None:
                    return False, tested, 'visible_or_uncertain_sample'
    return True, tested, 'all_front_facing_upper_hemisphere_samples_occluded'


def _scale_island(mesh, island, scale):
    uv = mesh.uv_layers['BakeUV'].data
    loops = island['loops']
    center = sum((uv[i].uv.copy() for i in loops), Vector((0, 0))) / len(loops)
    for index in loops:
        uv[index].uv = center + (uv[index].uv-center) * scale


def _strip_ring(obj, island, vertices):
    """Open a full, convex platform rim into four strips; preserve its UV area."""
    mesh = obj.data
    uv = mesh.uv_layers['BakeUV'].data
    ids = {mesh.loops[i].vertex_index for i in island['loops']}
    points = sorted({(round(vertices[i].x, 6), round(vertices[i].y, 6)) for i in ids})
    if len(points) < 8:
        return {'applied': False, 'reason': 'not_a_full_ring'}
    width = points[-1][0]-points[0][0]
    height = max(p[1] for p in points)-min(p[1] for p in points)
    zmin, zmax = min(vertices[i].z for i in ids), max(vertices[i].z for i in ids)
    if width < 5 or height < 4 or zmax-zmin < 1e-5:
        return {'applied': False, 'reason': 'not_a_large_platform_rim'}

    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = [Vector(p) for p in lower[:-1] + upper[:-1]]
    hull_area = abs(sum(a.x*b.y-b.x*a.y for a, b in zip(hull, hull[1:]+hull[:1]))) * .5
    if hull_area < width*height*.6:
        return {'applied': False, 'reason': 'partial_ring_kept_unchanged'}
    edges, circumference = [], 0.0
    for a, b in zip(hull, hull[1:]+hull[:1]):
        direction = b-a
        length = direction.length
        edges.append((a, direction, length, circumference))
        circumference += length
    parameters = {}
    for index in ids:
        point = vertices[index].xy
        best = None
        for origin, direction, length, distance in edges:
            t = max(0, min(1, (point-origin).dot(direction) / (length*length)))
            error = (point-origin-direction*t).length_squared
            if best is None or error < best[0]:
                best = (error, distance+length*t)
        parameters[index] = best[1]
    previous = {i: uv[i].uv.copy() for i in island['loops']}
    original_area = sum(_uv_area(mesh, mesh.loop_triangles[i]) for i in island['triangles'])
    strip_sections = 4
    for face_index in island['faces']:
        loops = list(mesh.polygons[face_index].loop_indices)
        us = [parameters[mesh.loops[i].vertex_index] for i in loops]
        wraps = max(us)-min(us) > circumference*.5
        us = [u+circumference if wraps and u < circumference*.5 else u for u in us]
        section = math.floor(sum(us)/len(us) / (circumference/strip_sections))
        # Four continuous strips avoid a 33m-long UV island dictating the whole
        # atlas scale. Each polygon remains intact; only three extra UV seams.
        for index, u in zip(loops, us):
            uv[index].uv = (u-section*circumference/strip_sections,
                           vertices[mesh.loops[index].vertex_index].z-zmin+section*(zmax-zmin)*2)
    signed_areas = []
    for index in island['triangles']:
        a, b, c = (uv[i].uv for i in mesh.loop_triangles[index].loops)
        signed_areas.append(((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5)
    positive = sum(a > 1e-12 for a in signed_areas)
    negative = sum(a < -1e-12 for a in signed_areas)
    degenerate = sum(abs(a) <= 1e-12 for a in signed_areas)
    if positive and negative or degenerate or not original_area:
        for i, coordinate in previous.items():
            uv[i].uv = coordinate
        return {'applied': False, 'reason': 'fold_or_degenerate_guard',
                'positive': positive, 'negative': negative, 'degenerate': degenerate}
    new_area = sum(abs(a) for a in signed_areas)
    _scale_island(mesh, island, math.sqrt(original_area/new_area))
    return {'applied': True, 'triangles': len(signed_areas), 'strip_sections': strip_sections,
            'uv_area_preserved': round(original_area, 7), 'circumference_m': round(circumference, 5),
            'inverted_triangles': 0, 'degenerate_triangles': 0}


def refine(atlas, group, size):
    if atlas != 0:
        return None
    if any(obj.data.get('architecture_uv_v12_refined') for obj in group):
        raise RuntimeError('V12 architectural UV refinement has already been applied; do not scale twice.')
    started = time.monotonic()
    before = _metrics(group, size)
    directions = _directions()
    reduced, skipped, strips, visible_groups = [], [], [], []
    total_rays = 0
    for obj in group:
        owner = obj.get('owner_asset_id', '')
        islands = _islands(obj)
        mesh = obj.data
        if owner == 'room_static':
            for island in islands:
                _scale_island(mesh, island, ARCHITECTURE_LINEAR_WEIGHT)
        if owner != 'architecture.platform':
            continue
        vertices = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        tree = BVHTree.FromPolygons(vertices, [tuple(t.vertices) for t in mesh.loop_triangles], all_triangles=True)
        # The large cap islands also contain visible 45-degree bevels. Partition
        # only the UV loops at flat-cap/bevel boundaries, never the solid mesh.
        # Down-facing exactly horizontal caps cannot face an above-floor camera.
        # Upward caps are classified only when every near-corner/edge ray is blocked.
        face_classes = ['side_or_bevel'] * len(mesh.polygons)
        face_triangles = {}
        for triangle in mesh.loop_triangles:
            face_triangles.setdefault(triangle.polygon_index, []).append(triangle.index)
        for face in mesh.polygons:
            triangles = face_triangles.get(face.index, [])
            if not triangles:
                continue
            normals = []
            for index in triangles:
                a, b, c = (vertices[i] for i in mesh.loop_triangles[index].vertices)
                normals.append((b-a).cross(c-a).normalized().z)
            if all(z < -.9999 for z in normals):
                face_classes[face.index] = 'horizontal_downward'
            elif all(z > .9999 for z in normals):
                face_classes[face.index] = 'horizontal_upward_visible'
                hidden, rays, _ = _hidden_island(obj, {'triangles': triangles}, tree, vertices, directions)
                total_rays += rays
                if hidden:
                    face_classes[face.index] = 'horizontal_upward_occluded'
        islands = _islands(obj, face_classes)
        for label in ('horizontal_upward_visible', 'side_or_bevel'):
            faces = [i for i, category in enumerate(face_classes) if category == label]
            visible_groups.append((obj, label, faces, _face_metrics(obj, faces, size)))
        for index, island in enumerate(islands):
            hidden = island['visibility_class'] in {'horizontal_downward', 'horizontal_upward_occluded'}
            rays = 0
            reason = island['visibility_class']
            area_before = sum(_uv_area(mesh, mesh.loop_triangles[t]) for t in island['triangles'])
            entry = {'island': index, 'triangles': len(island['triangles']),
                     'uv_area_before': round(area_before, 7), 'reason': reason, 'rays': rays}
            if hidden:
                _scale_island(mesh, island, HIDDEN_LINEAR_SCALE)
                entry['linear_scale'] = HIDDEN_LINEAR_SCALE
                entry['uv_area_after_reweight_before_pack'] = round(area_before * HIDDEN_LINEAR_SCALE**2, 7)
                reduced.append(entry)
            else:
                if island['visibility_class'] == 'side_or_bevel':
                    strip = _strip_ring(obj, island, vertices)
                    strip['island'] = index
                    strips.append(strip)
                skipped.append(entry)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in group:
        obj.select_set(True)
        obj.data.uv_layers.active = obj.data.uv_layers['BakeUV']
    bpy.context.view_layer.objects.active = group[0]
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        # A uniform pack scale preserves the intentionally changed relative areas.
        bpy.ops.uv.pack_islands(rotate=True, rotate_method='ANY', scale=True,
                               merge_overlap=False, margin_method='FRACTION',
                               margin=PADDING_PX / size, shape_method='CONCAVE', pin=False)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    after = _metrics(group, size)
    coordinates = [tuple(loop.uv) for obj in group for loop in obj.data.uv_layers['BakeUV'].data]
    if any(not math.isfinite(value) or value < -1e-5 or value > 1.00001
           for point in coordinates for value in point):
        raise RuntimeError('Packed architectural UVs are non-finite or outside the 0–1 atlas.')
    for obj in group:
        obj.data['architecture_uv_v12_refined'] = True
    old_arch = next(row for row in before['objects'] if row['owner'] == 'room_static')
    new_arch = next(row for row in after['objects'] if row['owner'] == 'room_static')
    common_pack_scale = math.sqrt(new_arch['uv_area']/old_arch['uv_area'])/ARCHITECTURE_LINEAR_WEIGHT
    return {'method': 'flat_cap_uv_seam_split_conservative_occlusion_reweight_and_pixel_pack',
            'before': before, 'after': after, 'hidden_islands_reduced': reduced,
            'platform_retained_visible_surface_density': [
                {'group': label, 'before': values, 'after': _face_metrics(obj, faces, size)}
                for obj, label, faces, values in visible_groups],
            'platform_rim_strips': strips,
            'platform_islands_retained': skipped, 'total_visibility_rays': total_rays,
            'visibility_directions': len(directions), 'samples_per_triangle': 7,
            'hidden_linear_scale': HIDDEN_LINEAR_SCALE,
            'architecture_linear_weight': ARCHITECTURE_LINEAR_WEIGHT,
            'pack_margin_method': 'FRACTION', 'pack_margin_fraction': PADDING_PX / size,
            'pack_padding_px_setting': PADDING_PX,
            'common_pack_scale': round(common_pack_scale, 6),
            'retained_platform_visible_density_factor': round(common_pack_scale, 6),
            'uv_finite_and_in_bounds': True,
            'overlap_policy': 'Blender CONCAVE pack_islands with merge_overlap=False and FRACTION margin; no cross-island overlap intentionally allowed',
            'geometry_modified': False, 'saved': False,
            'seconds': round(time.monotonic() - started, 3)}
