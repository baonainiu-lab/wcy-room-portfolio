"""Read-only CPU geometry audit of V3 architecture for the V4 rebuild."""
import bpy, bmesh, json, hashlib, time
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[4]
SOURCE=ROOT/'assets/blender/works-gallery-v3.blend'
OUT=ROOT/'assets/blender/works-gallery-v4/topology-audit-v3.json'
OWNERS={'gallery.architecture','gallery.architecture.portal','gallery.architecture.glazing'}
def owner(obj):
    while obj:
        if obj.get('asset_id'):return str(obj['asset_id'])
        obj=obj.parent
    return None
def bounds(points):
    return {'min':[round(min(p[i] for p in points),6) for i in range(3)],'max':[round(max(p[i] for p in points),6) for i in range(3)]} if points else None
start=time.time();before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.data.scenes['WORKS_GALLERY_V3'];bpy.context.window.scene=scene
scene.cycles.device='CPU';dg=bpy.context.evaluated_depsgraph_get();records=[]
for o in sorted(scene.objects,key=lambda x:x.name):
    own=owner(o)
    if own not in OWNERS or o.type not in {'MESH','CURVE','FONT'}:continue
    ev=o.evaluated_get(dg);me=ev.to_mesh(preserve_all_data_layers=True,depsgraph=dg);me.calc_loop_triangles()
    points=[ev.matrix_world@v.co for v in me.vertices]
    bm=bmesh.new();bm.from_mesh(me);bm.verts.ensure_lookup_table();bm.edges.ensure_lookup_table();bm.faces.ensure_lookup_table()
    edges=list(bm.edges);verts=list(bm.verts);components=[];seen=set()
    for v in verts:
        if v in seen:continue
        stack=[v];vs=set()
        while stack:
            q=stack.pop()
            if q in seen:continue
            seen.add(q);vs.add(q)
            stack.extend(e.other_vert(q) for e in q.link_edges)
        es={e for q in vs for e in q.link_edges};fs={f for q in vs for f in q.link_faces}
        components.append({'vertices':len(vs),'faces':len(fs),'boundary_edges':sum(e.is_boundary for e in es),'non_manifold_edges':sum(not e.is_manifold for e in es),'bounds':bounds([ev.matrix_world@q.co for q in vs])})
    boundarypoints=[ev.matrix_world@v.co for e in edges if e.is_boundary for v in e.verts]
    rec={'name':o.name,'owner':own,'type':o.type,'bounds':bounds(points),'vertices':len(verts),'faces':len(bm.faces),'triangles':len(me.loop_triangles),'boundary_edges':sum(e.is_boundary for e in edges),'non_manifold_edges':sum(not e.is_manifold for e in edges),'wire_edges':sum(e.is_wire for e in edges),'zero_length_edges':sum(e.calc_length()<1e-7 for e in edges),'degenerate_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'boundary_bounds':bounds(boundarypoints),'components':components,'materials':[m.name if m else None for m in me.materials],'modifiers':[{'name':m.name,'type':m.type} for m in o.modifiers]}
    if o.type=='CURVE':
        rec['curve']={'bevel_depth':o.data.bevel_depth,'bevel_resolution':o.data.bevel_resolution,'use_fill_caps':o.data.use_fill_caps,'resolution_u':o.data.resolution_u,'splines':[]}
        for sp in o.data.splines:
            pp=[o.matrix_world@p.co.xyz for p in sp.points] if sp.type!='BEZIER' else [o.matrix_world@p.co for p in sp.bezier_points]
            rec['curve']['splines'].append({'cyclic':sp.use_cyclic_u,'control_count':len(pp),'start':list(pp[0]) if pp else None,'end':list(pp[-1]) if pp else None,'bounds':bounds(pp)})
    # Geometry signature identifies coincident duplicate objects, independent of names.
    geo={'positions':sorted(tuple(round(x,6) for x in p) for p in points),'triangles':len(me.loop_triangles)}
    rec['position_signature']=hashlib.sha256(json.dumps(geo,separators=(',',':')).encode()).hexdigest()
    records.append(rec);bm.free();ev.to_mesh_clear()
by={}
for r in records:by.setdefault(r['position_signature'],[]).append(r['name'])
report={'source':str(SOURCE.relative_to(ROOT)),'source_sha256':before,'read_only_source_unchanged':before==hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'rendered':False,'owners':{},'exact_duplicate_position_sets':[x for x in by.values() if len(x)>1],'objects':records,'seconds':time.time()-start}
for own in sorted(OWNERS):
    rr=[r for r in records if r['owner']==own];report['owners'][own]={'objects':len(rr),'triangles':sum(r['triangles'] for r in rr),'boundary_edges':sum(r['boundary_edges'] for r in rr),'non_manifold_edges':sum(r['non_manifold_edges'] for r in rr),'open_object_names':[r['name'] for r in rr if r['boundary_edges']],'bounds':{'min':[min(r['bounds']['min'][i] for r in rr) for i in range(3)],'max':[max(r['bounds']['max'][i] for r in rr) for i in range(3)]}}
# Nearest-surface probes distinguish visible aperture gaps from bounding-box overlap.
probes=[]
for object_name,point,label in [
 ('Back structural blue core',(6.34,3.46,2.69),'right_glass_to_outer_arch_midheight'),
 ('Back structural blue core',(-6.34,3.46,2.69),'left_glass_to_outer_arch_midheight'),
 ('Back structural blue core',(0,3.46,4.85),'glass_head_to_outer_arch'),
 ('Back structural blue core',(0,3.39,5.035),'central_mullion_head_to_outer_arch'),
 ('Silver roof rib 6',(7.28,1.75,4.999),'right_column_top_to_edge_roof_rib'),
 ('Front canopy continuous rail',(7.28,1.75,4.999),'right_column_top_to_front_rail'),
]:
    obj=scene.objects.get(object_name);ev=obj.evaluated_get(dg);me=ev.to_mesh();tree=BVHTree.FromPolygons([ev.matrix_world@v.co for v in me.vertices],[tuple(f.vertices) for f in me.polygons]);hit=tree.find_nearest(Vector(point))
    probes.append({'label':label,'object':object_name,'probe':list(point),'nearest_surface':list(hit[0]) if hit[0] else None,'distance':hit[3]});ev.to_mesh_clear()
report['surface_gap_probes']=probes
report['interpretation']={
 'units':'Blender meters, Z up. Boundaries are topological boundaries, not automatically visually open holes.',
 'caps':'Seven silver ribs and front rail have caps but each evaluated curve cap is a disconnected component with coincident boundary edges. They are visually capped; do not describe 96 edges as missing end faces. Welded rebuild should give zero boundaries.',
 'unsealed_tubes':'Two corner columns and seven blue rib insets are genuinely uncapped open tubes; ten stone seams are also uncapped but tiny decorative inlays.',
 'rear_glass':'Six rear panes end at X +/-6.34, Z0.53..4.85. They fill the center only and leave broad outer apertures. No perimeter infill closes them to the outer rounded arch. Seven mullions end at Z5.035 without a continuous head bar.',
 'corner_column_feet':'Feet at Z0.22 exceed terrazzo top Z0.1735 by 0.0465m, or silver/base top Z0.15 by 0.07m where outside the terrazzo rounded border.',
 'glass_roof':'Six single-face canopy panes have zero thickness by design and 24 total boundary edges; source thin_glass=True. A precision shell rebuild can use shallow solids or a deliberately documented two-sided glass contract.',
 'portal':'There are 6 independent rounded tube rings on two gate faces and 2 extra full-passage tube rings. None are exact duplicates, but they read as overlapping nested piping; a closed extruded ring section would communicate a single structural doorway.',
 'inside_preservation':'Audit reads only the 3 assigned architectural owners, no exhibits or furnishings.',
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(OUT),'summary':report['owners'],'duplicate_objects':report['exact_duplicate_position_sets'],'read_only':report['read_only_source_unchanged'],'seconds':report['seconds']}))
