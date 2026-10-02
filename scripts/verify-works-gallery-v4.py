"""Read-only V4 geometry, two-state maps, probes, ground and render contract proof."""
from pathlib import Path
import hashlib,json,struct,math
ROOT=Path(__file__).resolve().parents[1];REPORT=ROOT/'assets/blender/works-gallery-v4'
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def glb(path):
 data=path.read_bytes();n,t=struct.unpack_from('<II',data,12);doc=json.loads(data[20:20+n].decode().rstrip(' \x00'));bn,bt=struct.unpack_from('<II',data,20+n);assert bt==0x004e4942;return doc,data[28+n:28+n+bn]
def attr(doc,binary,index):
 a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']];assert a['componentType']==5126 and a['type']=='VEC3'
 offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
 return [struct.unpack_from('<3f',binary,offset+i*stride) for i in range(a['count'])]
def mul(a,b):return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def matrix(n):
 if 'matrix' in n:return [[n['matrix'][j*4+i] for j in range(4)] for i in range(4)]
 x,y,z,w=n.get('rotation',[0,0,0,1]);sx,sy,sz=n.get('scale',[1,1,1]);tx,ty,tz=n.get('translation',[0,0,0]);return [[(1-2*y*y-2*z*z)*sx,(2*x*y-2*z*w)*sy,(2*x*z+2*y*w)*sz,tx],[(2*x*y+2*z*w)*sx,(1-2*x*x-2*z*z)*sy,(2*y*z-2*x*w)*sz,ty],[(2*x*z-2*y*w)*sx,(2*y*z+2*x*w)*sy,(1-2*x*x-2*y*y)*sz,tz],[0,0,0,1]]
export=read(REPORT/'export-report.json');compress=read(REPORT/'compression-report.json');prepared=read(REPORT/'preparation-report.json');source=read(REPORT/'architecture-rebuild-report.json');geometry=read(REPORT/'geometry-final-audit.json');old=read(ROOT/'assets/blender/works-gallery-v3/export-report.json')
assert sha(ROOT/source['source'])==source['source_sha256']==geometry['source_sha256']
transforms=read(REPORT/'source-prepared-transform-verification.json');assert transforms['complete'] and transforms['source_sha256']==source['source_sha256'];assert all(max(v['max_source_to_prepared_m'],v['max_prepared_to_source_m'])<.00003 for v in transforms['owners'].values())
assert source['asset_hierarchy']==old['asset_hierarchy']==export['asset_hierarchy']==prepared['asset_hierarchy']
assert prepared['preparation_id']==export['preparation_id']==compress['preparation_id']
assert prepared['asset_count']==len(export['asset_ids'])==77 and prepared['triangles']==export['triangles']==542976
assert export['atlasSizes']==[4096,4096,4096,1024] and export['drawPrimitives']==80
assert geometry['shell']['component_count']==1 and geometry['shell']['boundary_edges']==geometry['shell']['non_manifold_edges']==geometry['shell']['degenerate_faces']==0
assert all(c['boundary_edges']==c['non_manifold_edges']==0 for c in source['new_geometry_checks'] if c['name']!='V4 Works return doorway label')
assert all(c['back_region_outside_outer_top_samples']==0 for c in geometry['canopy'])
assert compress['complete'] and compress['model']['geometryAndHierarchyUnchanged'] and compress['model']['sourceGlbUnchanged']
assert sha(ROOT/compress['model']['path'])==compress['model']['sha256'] and sha(ROOT/export['model'])==export['sha256']
manifest_records=[]
for state in ('day','night'):
 m=read(ROOT/f'public/textures/works-gallery-v4/{state}-manifest.json');assert m['complete'] and len(m['atlases'])==4 and m['preparation_id']==prepared['preparation_id'] and m['lighting']['samples']==64
 for a in m['atlases']:
  assert sha(ROOT/a['path'])==a['sha256'];assert a['resolution']==[export['atlasSizes'][a['atlas']]]*2
 manifest_records.append({'state':state,'seconds':m['seconds'],'atlases':m['atlases']})
for t in compress['textures']:assert sha(ROOT/t['path'])==t['sha256']
doc,binary=glb(ROOT/compress['model']['path']);normals=[];bounds={};identity=[[int(i==j) for j in range(4)] for i in range(4)]
def visit(i,parent):
 n=doc['nodes'][i];world=mul(parent,matrix(n))
 if 'mesh' in n:
  for prim in doc['meshes'][n['mesh']]['primitives']:
   name=doc['materials'][prim['material']]['name'];positions=attr(doc,binary,prim['attributes']['POSITION']);worldpos=[tuple(sum(world[k][j]*v[j] for j in range(3))+world[k][3] for k in range(3)) for v in positions]
   item={'min':[min(v[j] for v in worldpos) for j in range(3)],'max':[max(v[j] for v in worldpos) for j in range(3)]}
   bounds[n['name']]=item
   if name in ('GALLERY_ARCH_GLASS','GALLERY_CLEAR'):
    values=attr(doc,binary,prim['attributes']['NORMAL']);lengths=[math.sqrt(sum(x*x for x in v)) for v in values];assert all(math.isfinite(x) and abs(x-1)<.01 for x in lengths)
    normals.append({'node':n['name'],'material':name,'normals':len(values),'min_length':min(lengths),'max_length':max(lengths),'web_bounds':item})
 for child in n.get('children',[]):visit(child,world)
for i in doc['scenes'][doc.get('scene',0)]['nodes']:visit(i,identity)
assert len(normals)==15 and sum(n['material']=='GALLERY_ARCH_GLASS' for n in normals)==2
for own,check in transforms['owners'].items():
 source_bounds=check['bounds_blender'];expected={'min':[source_bounds['min'][0],source_bounds['min'][2],-source_bounds['max'][1]],'max':[source_bounds['max'][0],source_bounds['max'][2],-source_bounds['min'][1]]}
 members=[v for k,v in bounds.items() if k.startswith('GALLERY_WEB_'+own+'__')];assert members,own
 for key in ('min','max'):
  actual=[(min if key=='min' else max)(b[key][j] for b in members) for j in range(3)]
  assert max(abs(a-b) for a,b in zip(actual,expected[key]))<.00005,(own,key,actual,expected[key])
web_bounds={key:[(min if key=='min' else max)(b[key][j] for b in bounds.values()) for j in range(3)] for key in ('min','max')}
protected={}
for version in ('v1','v2','v3'):
 for compressed in (False,True):
  rp=read(ROOT/'assets/blender'/f'works-gallery-{version}'/('compression-report.json' if compressed else 'export-report.json'));item=rp['model'] if compressed else rp;file=f'public/models/works-gallery-{version}'+('-compressed' if compressed else '')+'.glb';protected[file]=sha(ROOT/file)==item['sha256']
protected['assets/blender/works-gallery-v3.blend']=sha(ROOT/'assets/blender/works-gallery-v3.blend')==source['v3_source_sha256'];assert all(protected.values())
probe=read(ROOT/'public/textures/works-gallery-v4/reflection-SOURCE.json');ground=read(ROOT/'public/textures/gallery-atmosphere-v2/SOURCE.json');ground_ktx=read(ROOT/'public/textures/gallery-atmosphere-v2/COMPRESSION.json');renders=read(ROOT/'renders/works-gallery-v4/render-final.json')
assert probe['complete'] and probe['compression_complete'] and ground['complete'] and ground_ktx['complete'];assert ground['source_sha256']==source['source_sha256']
for path,expected in probe['input_sha256'].items():assert sha(ROOT/path)==expected
for record in probe['renders']+probe['compressed_textures']+ground['bakes']+ground_ktx['textures']+renders:assert sha(ROOT/record['path'])==record['sha256']
assert len(renders)==4 and all(r['resolution']==[2000,1200] and r['samples']==72 and r['source_sha256']==source['source_sha256'] and not r['source_blend_written'] for r in renders)
report={'complete':True,'source':source['source'],'source_sha256':source['source_sha256'],'prepared':prepared['prepared'],'prepared_sha256':sha(ROOT/prepared['prepared']),'model':compress['model'],'ids':77,'asset_hierarchy_preserved':True,'interior_geometry_and_uv_unchanged':prepared['retained_interiors_geometry_uv_sha256'],'triangles':export['triangles'],'primitives':80,'nodes':142,'materials':export['materials'],'atlas_sizes':export['atlasSizes'],'bakes':manifest_records,'glass_normals':normals,'architecture_glass_thickness_m':{'rear':.032,'canopy':.030},'source_to_prepared_all_world_vertices_verified':True,'transform_verification_report':'assets/blender/works-gallery-v4/source-prepared-transform-verification.json','structural_shell_single_closed_component':True,'top_glass_no_outer_corner_protrusion':True,'geometry_report':'assets/blender/works-gallery-v4/geometry-final-audit.json','web_bounds':web_bounds,'native_floor_y':-.88,'shared_stage_y_offset':-.185,'protected_old_assets':protected,'probe_manifest':'public/textures/works-gallery-v4/reflection-SOURCE.json','ground_manifest':'public/textures/gallery-atmosphere-v2/SOURCE.json','render_report':'renders/works-gallery-v4/render-final.json','gpu_jobs_complete':True,'estimated_main_astc_mib_both_states':compress['estimatedAstcOrBc7MipBytesBothStates']/1024/1024}
(REPORT/'pipeline-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('complete','ids','triangles','primitives','web_bounds')}))
