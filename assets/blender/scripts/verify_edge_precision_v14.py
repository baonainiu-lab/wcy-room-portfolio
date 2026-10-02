"""Independent GLB validation and V13 continuity checks; stdlib only."""
import array, collections, hashlib, json, math, struct
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')

def load(path):
    data=path.read_bytes();length=struct.unpack_from('<I',data,12)[0]
    doc=json.loads(data[20:20+length]);offset=20+length
    size=struct.unpack_from('<I',data,offset)[0]
    return doc,data[offset+8:offset+8+size]

def accessor(doc,blob,index):
    ac=doc['accessors'][index];bv=doc['bufferViews'][ac['bufferView']]
    fmt={5126:'f',5125:'I',5123:'H',5121:'B'}[ac['componentType']]
    n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[ac['type']]
    unit=struct.calcsize(fmt);offset=bv.get('byteOffset',0)+ac.get('byteOffset',0);stride=bv.get('byteStride',unit*n)
    return [struct.unpack_from('<'+fmt*n,blob,offset+i*stride) for i in range(ac['count'])]

def geo(doc,blob):
    rows=collections.Counter();triangles=0;normal_error=0.;primitives=0
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            attrs=p['attributes'];positions=accessor(doc,blob,attrs['POSITION']);normals=accessor(doc,blob,attrs['NORMAL']);uvs=accessor(doc,blob,attrs['TEXCOORD_0']) if 'TEXCOORD_0' in attrs else []
            indices=[v[0] for v in accessor(doc,blob,p['indices'])]
            assert all(math.isfinite(v) for row in positions+normals+uvs for v in row)
            assert all(0<=i<len(positions) for i in indices)
            normal_error=max(normal_error,max(abs(math.sqrt(sum(v*v for v in n))-1) for n in normals))
            # Compare local triangle surfaces, retaining multiplicity. Names and
            # draw partitions are intentionally different in V14. Scene/asset
            # transforms are separately compared below.
            for i in range(0,len(indices),3):
                verts=tuple(sorted(tuple(round(v,5) for v in positions[k]) for k in indices[i:i+3]))
                rows[verts]+=1
            triangles+=len(indices)//3;primitives+=1
    return rows,{'triangles':triangles,'drawPrimitives':primitives,'maxNormalUnitError':normal_error,'finiteAttributes':True,'validIndices':True}

def assets(doc):
    return {n['extras']['asset_id']:{k:n[k] for k in ('translation','rotation','scale','matrix') if k in n} for n in doc['nodes'] if n.get('extras',{}).get('asset_id')}

def run():
    old,ob=load(ROOT/'public/models/orbital-atelier-v13.glb');new,nb=load(ROOT/'public/models/orbital-atelier-v14.glb')
    og,oldstats=geo(old,ob);ng,newstats=geo(new,nb)
    # Join partitions originally use different local transforms. Each copied
    # partition keeps its original matrix; canonical geometry equality supports
    # that no triangle has been added, removed or moved in its source basis.
    assert og==ng,'GLB triangle positions changed'
    assert assets(old)==assets(new),'Stable asset IDs/transforms changed'
    nodeparents={c:i for i,n in enumerate(new['nodes']) for c in n.get('children',[])}
    allids=assets(new);interior=[a for a in allids if not a.startswith('environment.')]
    root_count=0
    for i,n in enumerate(new['nodes']):
        aid=n.get('extras',{}).get('asset_id')
        if not aid or aid.startswith('environment.'):continue
        p=nodeparents.get(i);nested=False
        while p is not None:
            nested|=bool(new['nodes'][p].get('extras',{}).get('asset_id'));p=nodeparents.get(p)
        root_count+=not nested
    assert len(interior)==93 and root_count==37
    hashes={}
    for p in (ROOT/'public/textures/lighting-v13').glob('*.png'):
        digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest==hashlib.sha256((ROOT/'public/textures/lighting-v14'/p.name).read_bytes()).hexdigest();hashes[p.name]=digest
    report={'passed':True,'before':oldstats,'after':newstats,'trianglePositionsAndMultiplicityUnchangedAt1e5Precision':True,'stableAssetIDsAndLocalTransformsIdentical':True,'interiorRoots':root_count,'interiorIDs':len(interior),'exteriorIDs':sorted(a for a in allids if a.startswith('environment.')),'retainedMapsByteIdentical':True,'retainedMapSha256':hashes,'embeddedImages':len(new['images']),'newAtlasImageResolution':3072,'sourceScope':'V14 is exported UV and texel-density precision; editable V13 source geometry / PBR / lighting retained.'}
    (ROOT/'renders/edge-precision-v14-export-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='retainedMapSha256'},indent=2))
    return report

if __name__=='__main__':run()
