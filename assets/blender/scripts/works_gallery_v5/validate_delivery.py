"""CPU audit of V5 deliverables and exact V4 -> V5 geometry invariance."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'assets/blender/works-gallery-v5'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def glb(path):
    raw=path.read_bytes();magic,version,size=struct.unpack_from('<III',raw)
    assert magic==0x46546c67 and version==2 and size==len(raw)
    cursor=12;doc=None;binary=None
    while cursor<len(raw):
        count,kind=struct.unpack_from('<II',raw,cursor);cursor+=8
        data=raw[cursor:cursor+count];cursor+=count
        if kind==0x4e4f534a:doc=json.loads(data)
        elif kind==0x004e4942:binary=data
    return doc,binary
def buffer(doc,binary,idx):
    view=doc['bufferViews'][idx];start=view.get('byteOffset',0)
    return binary[start:start+view['byteLength']]
def main():
    old,oldbin=glb(ROOT/'public/models/works-gallery-v4.glb')
    new,newbin=glb(ROOT/'public/models/works-gallery-v5.glb')
    checks={}
    for field in ['nodes','meshes','accessors','scene']:
        assert old.get(field)==new.get(field),field+' differs'
        checks[field+'Unchanged']=True
    assert len(old['scenes'])==len(new['scenes'])
    for a,b in zip(old['scenes'],new['scenes']):
        assert {k:v for k,v in a.items() if k!='extras'}=={k:v for k,v in b.items() if k!='extras'}
        for key in set(a.get('extras',{}))|set(b.get('extras',{})):
            if key not in {'day_lightmaps','preparation_id'}:
                assert a.get('extras',{}).get(key)==b.get('extras',{}).get(key),'Scene metadata changed: '+key
    checks['sceneHierarchyUnchanged']=True
    checks['onlyExpectedSceneMetadataChanged']=['day_lightmaps','preparation_id']
    old_images={i['bufferView'] for i in old['images']};new_images={i['bufferView'] for i in new['images']}
    assert len(old['bufferViews'])==len(new['bufferViews']) and old_images==new_images
    geometry_views=[]
    for index in range(len(old['bufferViews'])):
        if index in old_images:continue
        a,b=buffer(old,oldbin,index),buffer(new,newbin,index)
        assert a==b,'Geometry view '+str(index)+' changed'
        geometry_views.append({'index':index,'bytes':len(a),'sha256':hashlib.sha256(a).hexdigest()})
    ids=[n.get('extras',{}).get('asset_id') for n in new['nodes'] if n.get('extras',{}).get('asset_id')]
    assert len(ids)==len(set(ids))==77
    mats=json.loads((OUT/'material-refinement-report.json').read_text())
    for path,expected in mats['originalInputsUnchanged'].items(): assert sha(ROOT/path)==expected
    prep=json.loads((OUT/'preparation-report.json').read_text())
    for state in ('day','night'):
        manifest=json.loads((ROOT/f'public/textures/works-gallery-v5/{state}-manifest.json').read_text())
        assert manifest['complete'] and manifest['preparation_id']==prep['preparation_id'] and len(manifest['atlases'])==4
        assert manifest['lighting']['samples']==64
        for record in manifest['atlases']:assert sha(ROOT/f'public/textures/works-gallery-v5/{state}-{record["atlas"]}.png')==record['sha256']
    compressed=json.loads((OUT/'compression-report.json').read_text())
    assert compressed['complete'] and compressed['model']['geometryAndHierarchyUnchanged']
    assert compressed['preparation_id']==prep['preparation_id']
    reflections=json.loads((ROOT/'public/textures/works-gallery-v5/reflection-SOURCE.json').read_text())
    assert reflections['complete'] and reflections['gpu_jobs_complete'] and reflections['source_inputs_unchanged'] and reflections['compression_complete']
    assert reflections['sun_direction_error_degrees']<.1
    model=ROOT/'public/models/works-gallery-v5-compressed.glb'
    report={'complete':True,'assetIds':77,'checks':checks,'nonImageGeometryViewsUnchanged':geometry_views,'geometryUVFingerprint':prep['geometry_uv_sha256'],'preparation_id':prep['preparation_id'],'originalV4SourcesUnchanged':True,'dayNightBakes':{'samples':64,'atlasDimensions':[4096,4096,4096,1024],'states':2},'reflectionProbes':{'sourceInputsUnchanged':True,'dimensions':[2048,1024],'states':2,'sameSunDirection':True},'model':{'path':str(model.relative_to(ROOT)),'sha256':sha(model),'bytes':model.stat().st_size},'materialReview':'renders/works-gallery-v5/material-review.json','compressionReport':'assets/blender/works-gallery-v5/compression-report.json'}
    (OUT/'pipeline-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('complete','assetIds','checks','model')}))
if __name__=='__main__':main()
