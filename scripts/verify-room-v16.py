#!/usr/bin/env python3
"""Compare semantic mesh buffers, hierarchy and UVs to the released V15 GLB."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    b=path.read_bytes();n=struct.unpack_from('<I',b,12)[0];j=json.loads(b[20:20+n]);return j,b[28+n:]

def contents(doc,binary,accessor):
    a=doc['accessors'][accessor];v=doc['bufferViews'][a['bufferView']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]*{5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}[a['componentType']]
    stride=v.get('byteStride',width);start=v.get('byteOffset',0)+a.get('byteOffset',0)
    data=b''.join(binary[start+i*stride:start+i*stride+width] for i in range(a['count']))
    return {'count':a['count'],'componentType':a['componentType'],'type':a['type'],'sha256':hashlib.sha256(data).hexdigest()}

def geometry(doc,binary):
    return {m['name']:[{'attributes':{k:contents(doc,binary,v) for k,v in sorted(p['attributes'].items())},'indices':contents(doc,binary,p['indices'])} for p in m['primitives']] for m in doc['meshes']}

def hierarchy(doc):
    nodes=doc['nodes'];parents={child:n['name'] for n in nodes for child in n.get('children',[])}
    return {n['name']:{**{k:n[k] for k in ('translation','rotation','scale','matrix','extras') if k in n},'parent':parents.get(i),'mesh':doc['meshes'][n['mesh']]['name'] if 'mesh' in n else None} for i,n in enumerate(nodes)}

def main():
    raw=ROOT/'public/models/orbital-atelier-v16.glb'
    prepared_sha=sha(ROOT/'assets/blender/orbital-dual-bake-v16.blend')
    before,bb=read(ROOT/'public/models/orbital-atelier-v15.glb');after,ab=read(raw)
    assert geometry(before,bb)==geometry(after,ab),'Mesh attributes/indices/UVs differ from V15'
    assert hierarchy(before)==hierarchy(after),'IDs, transforms or parent hierarchy differ from V15'
    assert [m['name'] for m in before['materials']]==[m['name'] for m in after['materials']]
    preparation=json.loads((ROOT/'assets/blender/photoreal-materials-v16.json').read_text())
    for s in preparation['sources']:
        assert s['geometryBefore']==s['geometryAfter']
        assert hashlib.sha256((ROOT/s['original']).read_bytes()).hexdigest()==s['originalSha256']
        assert hashlib.sha256((ROOT/s['derivative']).read_bytes()).hexdigest()==s['sha256']
    compression=json.loads((ROOT/'assets/blender/photoreal-materials-v16-compression.json').read_text());assert compression['complete']
    legacy=json.loads((ROOT/'assets/blender/texture-precision-v15-compression.json').read_text())
    assert sha(ROOT/legacy['model']['path'])==legacy['model']['sha256']
    assert sha(ROOT/'public/models/orbital-atelier-v15.glb')==legacy['model']['sourceSha256']
    for row in legacy['textures']:
        assert sha(ROOT/row['source'])==row['sourceSha256'] and sha(ROOT/row['path'])==row['sha256']
    model=compression['model'];assert model['sourceSha256']==sha(raw)
    assert model['sha256']==sha(ROOT/model['path']) and model['bytes']==(ROOT/model['path']).stat().st_size
    compressed,cb=read(ROOT/model['path'])
    assert geometry(after,ab)==geometry(compressed,cb) and hierarchy(after)==hierarchy(compressed)
    expected={(state,slot) for state in ('day','night') for slot in [*range(12),'window']}|{('static','screen')}
    assert len(compression['textures'])==27 and {(r['state'],r['slot']) for r in compression['textures']}==expected
    for row in compression['textures']:
        assert sha(ROOT/row['source'])==row['sourceSha256'] and sha(ROOT/row['path'])==row['sha256']
        assert (ROOT/row['path']).stat().st_size==row['bytes']
    materials=json.loads((ROOT/'assets/blender/photoreal-materials-v16-comparison.json').read_text())
    assert materials['complete'] and materials['materialSlotsAndNamesUnchanged'] and materials['authoredColorsUnchanged']
    for state in materials['states']:assert hashlib.sha256((ROOT/state['source']).read_bytes()).hexdigest()==state['sha256']
    records=[]
    for state in ('day','night'):
        m=json.loads((ROOT/f'public/textures/lighting-v16/{state}-v16-manifest.json').read_text());assert m['complete'] and len(m['atlases'])==12
        assert m['preparedSha256']==prepared_sha and m['samples']==96 and m['state']==state
        assert {row['atlas'] for row in m['atlases']}==set(range(12))
        for r in m['atlases']:
            assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256'];records.append({'state':state,**r})
    report={'complete':True,'preparedSha256':prepared_sha,'sourceGeometryUvsNormalsUnchanged':True,'glbGeometryBuffersUnchanged':True,'compressedGeometryBuffersUnchanged':True,'idsHierarchyTransformsUnchanged':True,'legacySourcesUnchanged':True,'legacyModelsAndTexturesUnchanged':True,'allTextureAndModelHashesVerified':True,'roomAtlasSlots':list(range(12)),'dayNightAtlasCount':24,'samples':96,'model':compression['model'],'materials':len(after['materials']),'nodes':len(after['nodes']),'geometryMeshes':len(after['meshes'])}
    (ROOT/'assets/blender/photoreal-materials-v16-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
