# -*- coding: utf-8 -*-
"""CPU-only V11 repair of the upper-right window / cap / display junction.

Entry point: build_and_save(). The V10 source file remains unchanged.
Lift only the header valley and its supporting wall profile; cut an actual rear
return relief into the display frame/back. Window, shelves, and assets stay put.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri


ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE = ROOT / 'assets/blender/orbital-atelier-v10.blend'
OUTPUT = ROOT / 'assets/blender/orbital-atelier-v11.blend'
REPORT = ROOT / 'assets/blender/window-junction-v11-report.json'
EDITED = {'A_SweepingTopBand', 'A_BackWall_Graphite', 'A_DisplayTowerFrame', 'A_DisplayTowerBack'}
PROTECTED = ('A_Window_CityPanel', 'A_PanoramaTitaniumBezel', 'A_WindowRecessLight',
             'A_WindowDisplayLedge', 'A_WindowDisplayInlay', 'A_WindowDisplayRecessGlow')


def _sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def _activate(scene):
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.view_layers[0].update()


def _name(obj):
    return obj.get('v8_original_object_name', obj.name)


def _find(scene, name):
    return next(o for o in scene.objects if _name(o) == name)


def _containers(scene):
    queue, found = [scene.collection], []
    while queue:
        c = queue.pop()
        if c not in found:
            found.append(c)
            queue.extend(c.children)
    return found


def _independent(scene, obj):
    if len(obj.users_scene) > 1:
        new = obj.copy()
        new.name = 'V11__' + obj.name
        new['v8_original_object_name'] = _name(obj)
        for c in _containers(scene):
            if obj.name in c.objects:
                if c != scene.collection and c.users > 1:
                    raise RuntimeError('Unexpected shared source collection: ' + c.name)
                c.objects.link(new)
                c.objects.unlink(obj)
        obj = new
    obj.data = obj.data.copy()
    return obj


def _mesh(scene, obj):
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        faces = [tuple(face.vertices) for face in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()
    return {'points': points, 'faces': faces,
            'tree': BVHTree.FromPolygons(points, faces, all_triangles=True),
            'bounds': {'min': [min(p[k] for p in points) for k in range(3)],
                       'max': [max(p[k] for p in points) for k in range(3)]}}


def _assets(scene):
    _activate(scene)
    return sorted([{'id': str(o['asset_id']), 'matrix': [list(r) for r in o.matrix_world]}
                   for o in scene.objects if o.get('asset_id')], key=lambda o: o['id'])


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t*t*(3-2*t)


def _lift(x):
    if x <= 1.1 or x >= 3.3:
        return 0.0
    if x < 2.1:
        return .16*_smooth((x-1.1)/1.0)
    if x <= 2.65:
        return .16
    return .16*_smooth((3.3-x)/.65)


def _raise_valley(obj, only_top=False):
    matrix, inverse = obj.matrix_world.copy(), obj.matrix_world.inverted()
    count = 0
    for vertex in obj.data.vertices:
        point = matrix @ vertex.co
        if only_top and point.z <= .19:
            continue
        amount = _lift(point.x)
        if only_top:
            # The wall profile has a long sparse edge from x=-.4 to x=2.3.
            # Raising its endpoint by the full cap lift linearly lifts even the
            # part before the cap's smooth ramp and creates a visible fin.
            # A 4cm supporting rise keeps that edge safely inside the cap while
            # maintaining real overlap beneath the lifted valley.
            amount *= .25
        if amount > 0:
            point.z += amount
            vertex.co = inverse @ point
            count += 1
    obj.data.update()
    return count


def _cutter(scene):
    lo, hi = Vector((2.75, 3.045, 3.36)), Vector((3.43, 3.60, 4.45))
    vertices = [(x,y,z) for x,y,z in [(lo.x,lo.y,lo.z),(hi.x,lo.y,lo.z),
                (hi.x,hi.y,lo.z),(lo.x,hi.y,lo.z),(lo.x,lo.y,hi.z),
                (hi.x,lo.y,hi.z),(hi.x,hi.y,hi.z),(lo.x,hi.y,hi.z)]]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    data = bpy.data.meshes.new('V11_Temporary_Return_Relief_Mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new('V11_Temporary_Return_Relief', data)
    scene.collection.objects.link(obj)
    return obj


def _cut_return(scene, obj, cutter):
    # Retain the already rounded original visible surfaces by freezing their
    # evaluated mesh before the exact CSG. A small new bevel rounds cut edges.
    scene.view_layers[0].update()
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    data = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
    obj.modifiers.clear()
    obj.data = data
    modifier = obj.modifiers.new('Rear left window clearance - exact solid cut', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bevel = obj.modifiers.new('Soft return relief edges 8mm', 'BEVEL')
    bevel.width = .008
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(44)
    bevel.harden_normals = True
    normal = obj.modifiers.new('Weighted return relief normals', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True
    obj['window_corner_relief_v11'] = True


def _intersection(a, b, upper_right=True):
    points = []
    for ia, ib in a['tree'].overlap(b['tree']):
        first = [a['points'][k] for k in a['faces'][ia]]
        second = [b['points'][k] for k in b['faces'][ib]]
        for left, right in ((first, second), (second, first)):
            for k in range(3):
                start, end = left[k], left[(k+1)%3]
                vector = end-start
                if vector.length < 1e-10:
                    continue
                hit = intersect_ray_tri(right[0],right[1],right[2],vector.normalized(),start,True)
                if hit is not None and (hit-start).dot(vector)>=-1e-8 and (hit-start).length<=vector.length+1e-7:
                    if not upper_right or (hit.x>1.0 and hit.z>=3.4):
                        points.append(hit)
    nearest = None
    # Include triangle edge midpoints as well as all vertices to measure close
    # returns whose nearest approach is not located at an original mesh corner.
    for first, second in ((a,b),(b,a)):
        samples = list(first['points'])
        for face in first['faces']:
            tri = [first['points'][k] for k in face]
            samples.extend(((tri[0]+tri[1])*.5, (tri[1]+tri[2])*.5, (tri[2]+tri[0])*.5))
        for point in samples:
            if upper_right and not (point.x>1.0 and point.z>=3.4):
                continue
            hit = second['tree'].find_nearest(point)
            if hit[0] is not None and (nearest is None or hit[3]<nearest[0]):
                nearest = (hit[3], point.copy(), hit[0].copy())
    return {'confirmed_edge_triangle_intersections': len(points),
            'sampled_minimum_surface_clearance': nearest[0] if nearest else None,
            'closest_points': [list(p) for p in nearest[1:]] if nearest else [],
            'verification_region': 'upper-right x>1 / z>=3.4' if upper_right else 'entire mesh'}


def _minimum_z_in_x_slab(mesh, minimum_x, maximum_x):
    # Clip every triangle against the window's expanded horizontal span. The
    # far-left wall cap lies lower but is almost two metres from the window;
    # counting that unrelated endpoint would give a false clearance failure.
    lowest = float('inf')
    for face in mesh['faces']:
        polygon = [mesh['points'][i].copy() for i in face]
        for edge, positive in ((minimum_x,True),(maximum_x,False)):
            clipped = []
            if not polygon:
                break
            for index, current in enumerate(polygon):
                previous = polygon[index-1]
                current_inside = current.x>=edge if positive else current.x<=edge
                previous_inside = previous.x>=edge if positive else previous.x<=edge
                if current_inside != previous_inside:
                    t = (edge-previous.x)/(current.x-previous.x)
                    clipped.append(previous+(current-previous)*t)
                if current_inside:
                    clipped.append(current)
            polygon = clipped
        if polygon:
            lowest = min(lowest,min(p.z for p in polygon))
    return lowest


def _verify_wall_under_cap(header, wall):
    minimum_cover = float('inf')
    minimum_embed = float('inf')
    samples = 0
    for index in range(75):
        x = -.4 + index*.05
        for y in (3.35,3.40,3.45,3.50,3.55,3.60,3.65,3.70):
            cap = header['tree'].ray_cast(Vector((x,y,6)),Vector((0,0,-1)))[0]
            body = wall['tree'].ray_cast(Vector((x,y,6)),Vector((0,0,-1)))[0]
            if cap is None or body is None:
                continue
            samples += 1
            minimum_cover = min(minimum_cover, cap.z-body.z)
        # The central load-bearing section must still enter the cap underside.
        bottom = header['tree'].ray_cast(Vector((x,3.525,3.8)),Vector((0,0,1)))[0]
        body = wall['tree'].ray_cast(Vector((x,3.525,6)),Vector((0,0,-1)))[0]
        if bottom is not None and body is not None:
            minimum_embed = min(minimum_embed,body.z-bottom.z)
    if minimum_cover < .01:
        raise RuntimeError('Supporting wall protrudes or sits too close to cap surface: '+str(minimum_cover))
    if minimum_embed < .01:
        raise RuntimeError('Header lacks a continuous supporting wall overlap: '+str(minimum_embed))
    return {'vertical_envelope_samples':samples,'minimum_cap_cover_over_wall':minimum_cover,
            'minimum_wall_embed_into_cap':minimum_embed,'protruding_wall_fin':False,
            'wall_lift_max':.04,'header_lift_max':.16}


def _modify(scene):
    _activate(scene)
    before_assets = _assets(scene)
    transforms = {_name(o): [list(r) for r in o.matrix_world] for o in scene.objects}
    protected = {n: _mesh(scene,_find(scene,n))['bounds'] for n in PROTECTED}
    before_bounds = {n: _mesh(scene,_find(scene,n))['bounds'] for n in EDITED}
    original = {n: _independent(scene,_find(scene,n)) for n in EDITED}
    scene.view_layers[0].update()
    top_changed = _raise_valley(original['A_SweepingTopBand'])
    wall_changed = _raise_valley(original['A_BackWall_Graphite'], only_top=True)
    cutter = _cutter(scene)
    for name in ('A_DisplayTowerFrame','A_DisplayTowerBack'):
        _cut_return(scene, original[name], cutter)
    bpy.data.objects.remove(cutter, do_unlink=True)
    scene.view_layers[0].update()
    all_names = list(EDITED) + list(PROTECTED)
    evaluated = {n: _mesh(scene,_find(scene,n)) for n in all_names}
    cap_envelope = _verify_wall_under_cap(evaluated['A_SweepingTopBand'],evaluated['A_BackWall_Graphite'])
    if {n:evaluated[n]['bounds'] for n in PROTECTED} != protected:
        raise RuntimeError('A protected window/sill changed.')
    if _assets(scene) != before_assets:
        raise RuntimeError('Furniture/asset IDs or world transforms changed.')
    after_transforms = {_name(o): [list(r) for r in o.matrix_world] for o in scene.objects}
    if any(after_transforms.get(name)!=matrix for name,matrix in transforms.items()):
        raise RuntimeError('An existing scene object transform changed.')
    window_bounds = evaluated['A_PanoramaTitaniumBezel']['bounds']
    top_gap = _minimum_z_in_x_slab(evaluated['A_SweepingTopBand'],window_bounds['min'][0]-.10,
                                  window_bounds['max'][0]+.10)-window_bounds['max'][2]
    if top_gap < .10:
        raise RuntimeError('Header/window vertical clearance below 10cm: ' + str(top_gap))
    comparisons = {}
    for first, second in [('A_SweepingTopBand','A_PanoramaTitaniumBezel'),
                          ('A_SweepingTopBand','A_Window_CityPanel'),
                          ('A_DisplayTowerFrame','A_PanoramaTitaniumBezel'),
                          ('A_DisplayTowerBack','A_PanoramaTitaniumBezel'),
                          ('A_DisplayTowerFrame','A_Window_CityPanel'),
                          ('A_DisplayTowerBack','A_Window_CityPanel')]:
        item = _intersection(evaluated[first], evaluated[second], upper_right=first!='A_SweepingTopBand')
        comparisons[first+' / '+second] = item
        if item['confirmed_edge_triangle_intersections']:
            raise RuntimeError('Window corner still intersects: ' + first + ' / ' + second)
        minimum = .10 if first=='A_SweepingTopBand' else .02
        if item['sampled_minimum_surface_clearance'] < minimum:
            raise RuntimeError('Window corner clearance below target: ' + first + ' / ' + second)
    scene['window_junction_revision'] = 11
    return {'scene':scene.name, 'header_lift_max':.16, 'header_affected_x':[1.1,3.3],
            'header_lift_plateau_x':[2.1,2.65], 'lifted_header_vertices':top_changed,
            'lifted_wall_vertices':wall_changed, 'top_gap_exact_z_lower_bound':top_gap,
            'wall_cap_envelope_verification':cap_envelope,
            'top_gap_verified_x_slab':[window_bounds['min'][0]-.10,window_bounds['max'][0]+.10],
            'relief_box':{'min':[2.75,3.045,3.36],'max':[3.43,3.60,4.45]},
            'new_relief_edge_bevel':.008,
            'bounds_before':before_bounds, 'bounds_after':{n:evaluated[n]['bounds'] for n in EDITED},
            'checks':comparisons, 'protected_window_and_sill_bounds_unchanged':True,
            'all_asset_ids_and_transforms_unchanged':True, 'all_object_transforms_unchanged':True,
            'asset_count':len(before_assets), 'new_asset_ids':0}


def build_and_save():
    original_sha = _sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    reports = {}
    for name in ('ORBITAL_ATELIER_V2','ORIGINAL_DAY_V10','ORIGINAL_NIGHT_V10'):
        scene = bpy.data.scenes[name]
        record = _modify(scene)
        if name != 'ORBITAL_ATELIER_V2':
            scene.name = name.replace('_V10','_V11')
        record['scene'] = scene.name
        reports[scene.name] = record
    _activate(bpy.data.scenes['ORIGINAL_DAY_V11'])
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True,check_existing=False)
    if _sha(SOURCE) != original_sha:
        raise RuntimeError('Protected V10 file changed.')
    report = {'source':str(SOURCE),'output':str(OUTPUT),'source_sha256':original_sha,
              'source_file_unchanged':True,'bytes':OUTPUT.stat().st_size,'sha256':_sha(OUTPUT),
              'scenes':reports,'renders_executed':0,'active_scene':'ORIGINAL_DAY_V11'}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
