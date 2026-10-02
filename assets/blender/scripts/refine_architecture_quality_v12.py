# -*- coding: utf-8 -*-
"""Repair local architecture geometry and normals; CPU only, V11 stays intact.

Run build_and_save() through Blender MCP. No scene-wide subdivision, material
replacement, object movement, rendering, baking, or export is performed.
"""
import importlib.util
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SOURCE = ROOT / 'assets/blender/orbital-atelier-v11.blend'
OUTPUT = ROOT / 'assets/blender/orbital-atelier-v12.blend'
REPORT = ROOT / 'assets/blender/architecture-quality-v12-report.json'
NAMES = ('A_SweepingTopBand', 'A_LeftTopRail', 'A_LeftFrontRail',
         'A_BackWall_Graphite', 'A_LeftWallInner', 'A_PanoramaTitaniumBezel',
         'A_DisplayTowerFrame', 'A_DisplayTowerBack')
spec = importlib.util.spec_from_file_location('junction_v11_helpers',
    str(ROOT / 'assets/blender/scripts/fix_window_junction_v11.py'))
v11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v11)


def _mesh_stats(scene, obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        result = {
            'raw_vertices': len(obj.data.vertices),
            'evaluated_vertices': len(mesh.vertices),
            'triangles': len(mesh.loop_triangles),
            'smooth_faces': sum(p.use_smooth for p in mesh.polygons),
            'faces': len(mesh.polygons),
            'boundary_edges': sum(e.is_boundary for e in bm.edges),
            'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
            'wire_edges': sum(e.is_wire for e in bm.edges),
            'degenerate_faces': sum(f.calc_area() < 1e-12 for f in bm.faces),
            'signed_volume': bm.calc_volume(signed=True),
            'bevels': [{'width': m.width, 'segments': m.segments,
                        'harden_normals': m.harden_normals}
                       for m in obj.modifiers if m.type == 'BEVEL'],
            'bounds': v11._mesh(scene,obj)['bounds'],
        }
        bm.free()
        return result
    finally:
        evaluated.to_mesh_clear()


def _center_metrics(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    centers = [sum(verts[i:i+4],Vector())/4 for i in range(0,len(verts),4)]
    differences = [b-a for a,b in zip(centers,centers[1:])]
    angles = [math.degrees(a.angle(b)) for a,b in zip(differences,differences[1:])
              if a.length>1e-8 and b.length>1e-8]
    return {'sections':len(centers),
            'maximum_segment_length':max(d.length for d in differences),
            'maximum_tangent_turn_degrees':max(angles,default=0)}


def _replace_mesh(obj, world_vertices, faces):
    old = obj.data
    mesh = bpy.data.meshes.new(old.name + '_quality_v12')
    inverse = obj.matrix_world.inverted()
    mesh.from_pydata([inverse @ p for p in world_vertices], [], faces)
    mesh.update()
    for material in old.materials:
        mesh.materials.append(material)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    # Match the source helper's box projection for its procedural metal grain.
    # Bake UVs are generated later, independently by the export pipeline.
    uv = mesh.uv_layers.new(name='UVMap')
    lo = [min(v.co[i] for v in mesh.vertices) for i in range(3)]
    span = [max(max(v.co[i] for v in mesh.vertices)-lo[i],.0001) for i in range(3)]
    for polygon in mesh.polygons:
        axes = sorted(range(3),key=lambda i:abs(polygon.normal[i]))[:2]
        for loop in polygon.loop_indices:
            point = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = [(point[i]-lo[i])/span[i] for i in axes]
    obj.data = mesh


def _catmull(a,b,c,d,t):
    return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)


def _refine_band(obj):
    """Interpolate existing sections locally, preserving the V11 shape/valley."""
    old = [obj.matrix_world @ v.co for v in obj.data.vertices]
    rings = [old[i:i+4] for i in range(0,len(old),4)]
    # The tight concave return in the source folds its normal-offset upper
    # edge backwards at x=2.49. Locally transition to vertical sections: both
    # boundaries remain monotone in x, with their original heights untouched.
    # This fixes actual penetration; adding samples alone cannot fix that fold.
    for ring in rings:
        x = sum(p.x for p in ring)/4
        if x <= 2.18 or x >= 2.90:
            continue
        weight = min(v11._smooth((x-2.18)/.17),v11._smooth((2.90-x)/.20))
        for point in ring:
            point.x = point.x*(1-weight)+x*weight
    centers = [sum(ring,Vector())/4 for ring in rings]
    directions = [b-a for a,b in zip(centers,centers[1:])]
    turns = [math.degrees(a.angle(b)) for a,b in zip(directions,directions[1:])]
    result = []
    for i in range(len(rings)-1):
        turn = max(turns[max(0,i-1):min(len(turns),i+1)],default=0)
        divisions = 3 if turn > 5 else 2 if directions[i].length > .16 else 1
        a,b,c,d = rings[max(0,i-1)],rings[i],rings[i+1],rings[min(len(rings)-1,i+2)]
        for step in range(divisions):
            t = step/divisions
            result.extend(_catmull(a[k],b[k],c[k],d[k],t) for k in range(4))
    result.extend(rings[-1])
    # Prevent tiny interpolation overshoot from changing the established peaks
    # or the outward wall-thickness envelope.
    lo = [min(p[i] for p in old) for i in range(3)]
    hi = [max(p[i] for p in old) for i in range(3)]
    for point in result:
        for axis in range(3):
            point[axis] = min(hi[axis],max(lo[axis],point[axis]))
    count = len(result)//4
    faces = [(i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4,(i+1)*4+k)
             for i in range(count-1) for k in range(4)]
    faces += [(3,2,1,0),tuple((count-1)*4+k for k in range(4))]
    _replace_mesh(obj,result,faces)


def _rebuild_front_post(scene,obj):
    """Remove the original spline's reversing 88-degree terminal hook."""
    bounds = v11._mesh(scene,obj)['bounds']
    lo,hi = bounds['min'],bounds['max']
    # Its foot/width/depth stay fixed. The end seats below the transverse cap's
    # top surface, inside their real overlap rather than protruding above it.
    top = 3.92
    vertices = [Vector((x,y,z)) for x,y,z in
        [(lo[0],lo[1],lo[2]),(hi[0],lo[1],lo[2]),
         (hi[0],hi[1],lo[2]),(lo[0],hi[1],lo[2]),
         (lo[0],lo[1],top),(hi[0],lo[1],top),
         (hi[0],hi[1],top),(lo[0],hi[1],top)]]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    _replace_mesh(obj,vertices,faces)
    return {'old_top_z':hi[2],'new_top_z':top,
            'unchanged_foot_z':lo[2],'source_of_spike':'reversing Catmull-Rom endpoint'}


def _finish_normals(obj):
    # These source meshes previously had every polygon flat-shaded, making
    # their existing Weighted Normal modifiers ineffective on the curved faces.
    mesh = obj.data
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    sharp = 0
    for edge in bm.edges:
        hard = edge.is_manifold and edge.calc_face_angle() > math.radians(60)
        edge.smooth = not hard
        sharp += bool(hard)
    bm.to_mesh(mesh)
    bm.free()
    for modifier in obj.modifiers:
        if modifier.type == 'BEVEL':
            modifier.segments = max(modifier.segments,6)
            modifier.harden_normals = True
            modifier.affect = 'EDGES'
    if v11._name(obj) == 'A_SweepingTopBand':
        # The source's closing profile meets the endpoint bevel at coincident
        # vertices. A 2-micron weld removes the zero-area closing sliver while
        # leaving the visible cap and the editable bevel intact.
        for modifier in list(obj.modifiers):
            if modifier.type == 'WEIGHTED_NORMAL':
                obj.modifiers.remove(modifier)
        weld = obj.modifiers.new('Clean coincident terminal bevel seam','WELD')
        weld.merge_threshold = .000002
    normal = next((m for m in obj.modifiers if m.type=='WEIGHTED_NORMAL'),None)
    if normal is None:
        normal = obj.modifiers.new('Continuous curves and stable planar normals','WEIGHTED_NORMAL')
    normal.keep_sharp = True
    normal.mode = 'FACE_AREA_WITH_ANGLE'
    normal.weight = 50
    mesh.update()
    obj['geometry_quality_revision'] = 12
    return sharp


def _self_crossings(mesh):
    """Strict nonadjacent triangle penetration; shared edges are not defects."""
    confirmed = set()
    candidates = 0
    for ia,ib in mesh['tree'].overlap(mesh['tree']):
        if ia >= ib:
            continue
        fa,fb = mesh['faces'][ia],mesh['faces'][ib]
        if set(fa)&set(fb):
            continue
        candidates += 1
        first = [mesh['points'][i] for i in fa]
        second = [mesh['points'][i] for i in fb]
        for left,right in ((first,second),(second,first)):
            for i in range(3):
                start,end = left[i],left[(i+1)%3]
                direction = end-start
                length = direction.length
                if length < 1e-8:
                    continue
                hit = intersect_ray_tri(*right,direction.normalized(),start,True)
                if hit is None:
                    continue
                distance = (hit-start).dot(direction.normalized())
                if not 1e-6 < distance < length-1e-6:
                    continue
                a,b,p = right[1]-right[0],right[2]-right[0],hit-right[0]
                aa,ab,bb,pa,pb = a.dot(a),a.dot(b),b.dot(b),p.dot(a),p.dot(b)
                denom = aa*bb-ab*ab
                if abs(denom)<1e-15:
                    continue
                u,v = (bb*pa-ab*pb)/denom,(aa*pb-ab*pa)/denom
                if u>1e-5 and v>1e-5 and u+v<1-1e-5:
                    confirmed.add((ia,ib))
    return {'nonadjacent_bvh_candidates':candidates,
            'strict_triangle_penetrations':len(confirmed)}


def _modify(scene):
    v11._activate(scene)
    before_assets = v11._assets(scene)
    matrices = {v11._name(o):[list(row) for row in o.matrix_world] for o in scene.objects}
    before = {n:_mesh_stats(scene,v11._find(scene,n)) for n in NAMES}
    mesh_checks_before = {n:_self_crossings(v11._mesh(scene,v11._find(scene,n)))
                          for n in NAMES}
    metrics_before = {n:_center_metrics(v11._find(scene,n))
                      for n in NAMES[:3]}
    window = v11._mesh(scene,v11._find(scene,'A_Window_CityPanel'))['bounds']
    objects = {n:v11._independent(scene,v11._find(scene,n)) for n in NAMES}
    _refine_band(objects['A_SweepingTopBand'])
    front = _rebuild_front_post(scene,objects['A_LeftFrontRail'])
    sharp = {n:_finish_normals(obj) for n,obj in objects.items()}
    scene.view_layers[0].update()
    after = {n:_mesh_stats(scene,obj) for n,obj in objects.items()}
    meshes = {n:v11._mesh(scene,obj) for n,obj in objects.items()}
    mesh_checks = {n:_self_crossings(mesh) for n,mesh in meshes.items()}
    for n,record in after.items():
        if record['nonmanifold_edges'] or record['degenerate_faces']:
            raise RuntimeError('Invalid mesh after local refinement: '+n+' '+str(record))
        if mesh_checks[n]['strict_triangle_penetrations']:
            raise RuntimeError('Self-crossing mesh after local refinement: '+n+' '+str(mesh_checks[n]))
    cap = v11._verify_wall_under_cap(meshes['A_SweepingTopBand'],meshes['A_BackWall_Graphite'])
    bezel = meshes['A_PanoramaTitaniumBezel']
    gap = v11._minimum_z_in_x_slab(meshes['A_SweepingTopBand'],
        bezel['bounds']['min'][0]-.1,bezel['bounds']['max'][0]+.1)-bezel['bounds']['max'][2]
    if gap < .12:
        raise RuntimeError('V11 window clearance was compromised: '+str(gap))
    intersections = {}
    for name in ('A_SweepingTopBand','A_DisplayTowerFrame','A_DisplayTowerBack'):
        record = v11._intersection(meshes[name],bezel,upper_right=name!='A_SweepingTopBand')
        if record['confirmed_edge_triangle_intersections'] or record['sampled_minimum_surface_clearance']<(.12 if name=='A_SweepingTopBand' else .02):
            raise RuntimeError('Window junction clearance regressed: '+name+' '+str(record))
        intersections[name] = record
    if window != v11._mesh(scene,v11._find(scene,'A_Window_CityPanel'))['bounds']:
        raise RuntimeError('Window image geometry moved.')
    if v11._assets(scene) != before_assets:
        raise RuntimeError('Asset IDs or world transforms changed.')
    after_matrices = {v11._name(o):[list(row) for row in o.matrix_world] for o in scene.objects}
    if matrices != after_matrices:
        raise RuntimeError('Scene object transforms changed.')
    total_triangles = 0
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type not in {'MESH','CURVE','FONT'}:
            continue
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        if mesh:
            mesh.calc_loop_triangles()
            total_triangles += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    scene['architecture_quality_revision'] = 12
    return {'objects_before':before,'objects_after':after,
            'centerline_metrics_before':metrics_before,
            'centerline_metrics_after':{n:_center_metrics(objects[n]) for n in NAMES[:2]},
            'sharp_source_edges_retained':sharp,'front_post':front,
            'valley_fold_repair_x':[2.18,2.90],
            'top_gap_exact_z_lower_bound':gap,'wall_cap_envelope':cap,
            'self_intersection_checks_before':mesh_checks_before,
            'self_intersection_checks':mesh_checks,'window_junction_checks':intersections,
            'source_scene_total_triangles':total_triangles,
            'edited_objects_triangles_before':sum(r['triangles'] for r in before.values()),
            'edited_objects_triangles_after':sum(r['triangles'] for r in after.values()),
            'asset_count':len(before_assets),'asset_ids_and_world_transforms_unchanged':True,
            'all_object_transforms_unchanged':True,'window_image_unchanged':True}


def build_and_save():
    sha = v11._sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scenes = {}
    for name in ('ORBITAL_ATELIER_V2','ORIGINAL_DAY_V11','ORIGINAL_NIGHT_V11'):
        scene = bpy.data.scenes[name]
        record = _modify(scene)
        if name != 'ORBITAL_ATELIER_V2':
            scene.name = name.replace('_V11','_V12')
        scenes[scene.name] = record
    v11._activate(bpy.data.scenes['ORIGINAL_DAY_V12'])
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True,check_existing=False)
    if v11._sha(SOURCE) != sha:
        raise RuntimeError('Protected source V11 changed.')
    report = {'source':str(SOURCE),'source_sha256':sha,'source_file_unchanged':True,
              'output':str(OUTPUT),'bytes':OUTPUT.stat().st_size,'sha256':v11._sha(OUTPUT),
              'scenes':scenes,'renders_executed':0,'exports_executed':0}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
