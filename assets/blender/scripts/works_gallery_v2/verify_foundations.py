"""Read-only closed-mesh, support and protected-V1 verification."""
import bpy,bmesh,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];REPORT=ROOT/'assets/blender/works-gallery-v2'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-bake-v2.blend'))
s=bpy.data.scenes['WEB_WORKS_GALLERY_V2'];bpy.context.window.scene=s
meshes=[o for o in s.objects if o.type=='MESH' and o.get('web_export')]
verts=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
lo=[min(v[i] for v in verts) for i in range(3)];hi=[max(v[i] for v in verts) for i in range(3)]
f=next(o for o in meshes if o.get('owner_asset_id')=='gallery.environment.foundation');bm=bmesh.new();bm.from_mesh(f.data)
check={'vertices':len(bm.verts),'edges':len(bm.edges),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_faces for v in bm.verts),'zero_area_faces':sum(face.calc_area()<1e-12 for face in bm.faces)}
bm.free();assert check['boundary_edges']==check['non_manifold_edges']==check['loose_vertices']==0
old=json.loads((ROOT/'assets/blender/works-gallery-v1/preparation-report.json').read_text());new=json.loads((REPORT/'preparation-report.json').read_text())
assert set(new['asset_ids'])-set(old['asset_ids'])=={'gallery.environment.foundation'}
assert all(new['asset_hierarchy'][k]==v for k,v in old['asset_hierarchy'].items())
report={'complete':True,'blender_bounds':{'min':lo,'max':hi},'web_bounds':{'min':[lo[0],lo[2],-hi[1]],'max':[hi[0],hi[2],-lo[1]]},'foundation_top':-5.82,'runtime_floor_max_web_y':lo[2],'room_stage_floor_y':-1.065,'gallery_stage_offset_y':-1.065-(-5.82),'stage_alignment':'terrain TOP aligned to room ground; stage-only old infinite ground hidden; old bottom-alignment must not be used because broad landmass overlaps room' ,'foundation_mesh_closed':check,'atlas_sizes':[4096,3072,4096,4096,2048],'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'ids':len(new['asset_ids']),'existing_ids_and_hierarchy_preserved':True,'existing_geometry_uv_sha256':new['retained_geometry_uv_sha256']}
(REPORT/'prepared-bounds.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
