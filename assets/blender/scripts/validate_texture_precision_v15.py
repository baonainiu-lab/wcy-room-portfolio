"""Read-only final validation of V15 GLB, stable hierarchy and native image data."""
import hashlib,json,math,struct,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def glb(path):
    data=path.read_bytes();magic,version,length=struct.unpack_from('<III',data)
    assert magic==0x46546c67 and version==2 and length==len(data)
    n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);offset=20+n
    size=struct.unpack_from('<I',data,offset)[0];binary=data[offset+8:offset+8+size]
    return doc,binary
def png(path):
    data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
    offset=8;parts=[];dims=None;end=False
    while offset<len(data):
        n=struct.unpack_from('>I',data,offset)[0];kind=data[offset+4:offset+8];body=data[offset+8:offset+8+n]
        crc=struct.unpack_from('>I',data,offset+8+n)[0]
        assert zlib.crc32(kind+body)&0xffffffff==crc,(path.name,kind)
        if kind==b'IHDR':dims=list(struct.unpack_from('>II',body))
        if kind==b'IDAT':parts.append(body)
        if kind==b'IEND':end=True
        offset+=n+12
    assert end and offset==len(data);assert zlib.decompress(b''.join(parts))
    return {'path':str(path.relative_to(ROOT)),'resolution':dims,'bytes':len(data),'sha256':sha(path),'allChunksCrcValid':True}
def structure(doc):
    nodes=doc['nodes'];parents={child:i for i,n in enumerate(nodes) for child in n.get('children',[])}
    return {n['extras']['asset_id']:{'node':n['name'],'parent':nodes[parents[i]]['name'] if i in parents else None,
            'matrix':n.get('matrix'),'translation':n.get('translation'),'rotation':n.get('rotation'),'scale':n.get('scale')}
            for i,n in enumerate(nodes) if n.get('extras',{}).get('asset_id')}
def stats(doc):return {'nodes':len(doc['nodes']),'meshes':len(doc['meshes']),'materials':len(doc['materials']),
    'triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives']),
    'drawPrimitives':sum(len(m['primitives']) for m in doc['meshes'])}
def run():
    old,b14=glb(ROOT/'public/models/orbital-atelier-v14.glb');new,b15=glb(ROOT/'public/models/orbital-atelier-v15.glb')
    exported=json.loads((ROOT/'assets/blender/dual-lighting-v15-export-report.json').read_text())
    assert structure(old)==structure(new),'Stable ID hierarchy or object transforms changed'
    assert len(structure(new))==95
    oldstats,newstats=stats(old),stats(new)
    assert oldstats['triangles']==373203
    assert newstats['triangles']==exported['triangles']==413855
    assert oldstats['drawPrimitives']==newstats['drawPrimitives']
    material_names=[m['name'] for m in new['materials']]
    assert all(f'WEB8_LIGHTMAP_{i}' in material_names for i in range(12))
    assert 'WEB8_WINDOW_CITY' in material_names
    for a in new['accessors']:
        if a['componentType']!=5126:continue
        view=new['bufferViews'][a['bufferView']];start=view.get('byteOffset',0)+a.get('byteOffset',0)
        count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}.get(a['type'])
        if count is None:continue
        stride=view.get('byteStride',4*count)
        for i in range(a['count']):
            assert all(math.isfinite(x) for x in struct.unpack_from('<'+'f'*count,b15,start+i*stride))
    sizes=exported['atlasSizes'];assert sizes==[4096]*6+[3072,2048,3072,4096,4096,3072];images=[]
    for state in ('day','night'):
        for atlas,size in enumerate(sizes):
            record=png(ROOT/f'public/textures/lighting-v15/{state}-{atlas}.png')
            assert record['resolution']==[size,size];images.append(record)
        record=png(ROOT/f'public/textures/lighting-v15/window-{state}.png');assert record['resolution']==[3072,1344];images.append(record)
    record=png(ROOT/'public/textures/lighting-v15/screen-art-render.png');assert record['resolution']==[2880,1200];images.append(record)
    protected={'assets/blender/orbital-dual-bake-v14.blend':'c27fbb08d5b55a6d32ec681bd97a6ba4b33b8fb301a0aa8325ccfda593255b4d',
               'public/models/orbital-atelier-v14.glb':'a933ce1ba865c5ad5293e11bfac51ad082f8c1522ff828ad89d45aa17bd5e232'}
    for path,expected in protected.items():assert sha(ROOT/path)==expected,path
    report={'revision':15,'complete':True,'stableAssetIds':95,'stableHierarchyAndTransforms':True,'before':oldstats,'after':newstats,
            'materials':material_names,'images':images,'protectedV14Hashes':protected,
            'modelSha256':sha(ROOT/'public/models/orbital-atelier-v15.glb'),
            'workChairGeometryRestored':True,'workChairValidation':'assets/blender/work-chair-v15-validation.json','atlasCount':len(sizes)}
    assert len(images)==27
    (ROOT/'assets/blender/texture-precision-v15-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='images'},indent=2))
    return report
if __name__=='__main__':run()
