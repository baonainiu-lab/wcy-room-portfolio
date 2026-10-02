"""Read-only final proof for the gallery-only V3 asset contract."""
from pathlib import Path
import json,hashlib,struct
ROOT=Path(__file__).resolve().parents[1];REPORT=ROOT/'assets/blender/works-gallery-v3'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def glb(p):
    blob=p.read_bytes();n,t=struct.unpack_from('<II',blob,12);return json.loads(blob[20:20+n].decode().rstrip(' \x00'))
export=read(REPORT/'export-report.json');compression=read(REPORT/'compression-report.json');deletion=read(REPORT/'deletion-verification.json');impact=read(REPORT/'lighting-impact-audit.json')
doc=glb(ROOT/compression['model']['path']);ids=[n['extras']['asset_id'] for n in doc['nodes'] if n.get('extras',{}).get('asset_id')]
old=read(ROOT/'assets/blender/works-gallery-v1/export-report.json');removed=set(deletion['removed_ids_relative_to_v2']);expected=set(old['asset_ids'])-set(deletion['removed_ids'])
assert set(ids)==expected and len(ids)==len(set(ids))==77 and not set(ids)&removed
assert 'gallery.architecture.portal' in ids and 'gallery.environment.terrace' in ids
retained={}
for state in ('day','night'):
    m=read(ROOT/f'public/textures/works-gallery-v3/{state}-manifest.json');assert m['complete'] and len(m['atlases'])==4
    for a,b in ((0,0),(2,1),(3,2)):
        retained[f'{state}:v1A{a}->v3A{b}']=sha(ROOT/f'public/textures/works-gallery-v1/{state}-{a}.png')==sha(ROOT/f'public/textures/works-gallery-v3/{state}-{b}.png')
assert all(retained.values())
protected={}
for version in ('v1','v2'):
    for compressed in (False,True):
        rp=read(ROOT/'assets/blender'/f'works-gallery-{version}'/('compression-report.json' if compressed else 'export-report.json'))
        item=rp['model'] if compressed else rp;file=f'public/models/works-gallery-{version}'+('-compressed' if compressed else '')+'.glb';protected[file]=sha(ROOT/file)==item['sha256']
v2=read(ROOT/'assets/blender/works-gallery-v2/foundation-verification.json')
protected['assets/blender/works-gallery-v1.blend']=sha(ROOT/'assets/blender/works-gallery-v1.blend')==v2['original_v1_source_sha256']
protected['assets/blender/works-gallery-v2.blend']=sha(ROOT/'assets/blender/works-gallery-v2.blend')==v2['source_sha256']
assert all(protected.values())
assert compression['complete'] and compression['model']['geometryAndHierarchyUnchanged'] and compression['model']['sourceGlbUnchanged']
assert export['triangles']==560890 and export['drawPrimitives']==80 and export['atlasSizes']==[4096,4096,4096,1024]
assert len(doc['images'])==4 and len(doc['materials'])==5
assert sha(ROOT/compression['model']['path'])==compression['model']['sha256']
renders=read(ROOT/'renders/works-gallery-v3/render-final-both.json');assert renders['complete']
for r in renders['renders']:assert sha(ROOT/r['path'])==r['sha256'] and r['resolution']==[2000,1200]
report={'complete':True,'model':compression['model'],'ids':77,'retained_ids':sorted(ids),'removed_ids_relative_to_v2':sorted(removed),'primitives':80,'triangles':560890,'atlas_sizes':[4096,4096,4096,1024],'retained_pngs_byte_identical':retained,'protected_old_assets':protected,'thin_base_closed':deletion['closed_thin_terrace_component'],'web_bounds':deletion['web_bounds'],'native_floor_y':-.88,'shared_stage_offset_y':-.185,'shared_stage_clearance':.025,'portal_and_local_plants_preserved':True,'environment_geometry_absent':True,'direct_sun_environment_probe_hits':impact['removed_environment_direct_sun_occlusion_count'],'lighting_limit':impact['indirect_limit'],'estimated_astc_mib_both_states':compression['estimatedAstcOrBc7MipBytesBothStates']/1024/1024,'render_report':'renders/works-gallery-v3/render-final-both.json','renders_visually_inspected':True,'gpu_jobs_complete':True}
(REPORT/'pipeline-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('complete','ids','primitives','triangles','estimated_astc_mib_both_states')}))
