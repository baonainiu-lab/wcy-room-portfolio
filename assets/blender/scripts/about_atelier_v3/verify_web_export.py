"""Read-only source-to-GLB hierarchy, transform, bounds and atlas validation.
Run with background Blender after web_export.py completes.
"""
import bpy, hashlib, json, math, struct
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector

ROOT=Path(__file__).resolve().parents[4]
SOURCE=ROOT/'assets/blender/about-atelier-v3.blend'
MODEL=ROOT/'public/models/about-atelier-v3.glb'
OUT=ROOT/'assets/blender/about-atelier-v3-web/validation-report.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
blob=MODEL.read_bytes();magic,version,total=struct.unpack_from('<III',blob)
assert magic==0x46546c67 and version==2 and total==len(blob)
jlen,jtype=struct.unpack_from('<II',blob,12);assert jtype==0x4e4f534a
doc=json.loads(blob[20:20+jlen]);blen,btype=struct.unpack_from('<II',blob,20+jlen)
assert btype==0x004e4942
binary=blob[28+jlen:28+jlen+blen]
assert len(binary)==blen
parents={c:i for i,n in enumerate(doc['nodes']) for c in n.get('children',[])}
def local(n):
    if 'matrix' in n:return Matrix([n['matrix'][i::4] for i in range(4)])
    x,y,z,w=n.get('rotation',[0,0,0,1])
    return Matrix.Translation(Vector(n.get('translation',[0,0,0])))@Quaternion((w,x,y,z)).to_matrix().to_4x4()@Matrix.Diagonal((*n.get('scale',[1,1,1]),1))
worlds={}
def world(i):
    if i not in worlds:worlds[i]=(world(parents[i]) if i in parents else Matrix.Identity(4))@local(doc['nodes'][i])
    return worlds[i]
def ancestor_id(i):
    while i in parents:
        i=parents[i];identity=doc['nodes'][i].get('extras',{}).get('asset_id')
        if identity:return identity
    return None
ids={n.get('extras',{}).get('asset_id'):i for i,n in enumerate(doc['nodes']) if n.get('extras',{}).get('asset_id')}
assert len(ids)==128
assert len([n for n in doc['nodes'] if n.get('extras',{}).get('asset_id')])==128
assert all(n.get('extras',{}).get('web_export') for n in doc['nodes'])
assert not any('context.' in n.get('name','') for n in doc['nodes'])
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));source=bpy.context.scene;bpy.context.view_layer.update()
source_objects={o for c in source.collection.children if c.name.startswith(('01_','02_','03_','04_')) for o in c.all_objects}
roots={o['asset_id']:o for o in source_objects if o.get('asset_id')};assert set(roots)==set(ids)
conversion=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
transform_errors={};hierarchy_errors=[];interactions={}
for identity,o in roots.items():
    expected=conversion@o.matrix_world@conversion.inverted();actual=world(ids[identity])
    error=max(abs(expected[r][c]-actual[r][c]) for r in range(4) for c in range(4));transform_errors[identity]=error
    assert error<.00003,(identity,error)
    ancestor=o.parent
    while ancestor and not ancestor.get('asset_id'):ancestor=ancestor.parent
    assert ancestor_id(ids[identity])==(ancestor['asset_id'] if ancestor else None),identity
    extras=doc['nodes'][ids[identity]]['extras']
    for key in ('interaction','interactive','content_status'):
        if key in o:assert extras.get(key)==o[key],(identity,key)
    interactions[identity]={key:extras[key] for key in ('interaction','interactive','content_status') if key in extras}
mins=[math.inf]*3;maxs=[-math.inf]*3;triangles=0
for i,n in enumerate(doc['nodes']):
    if 'mesh' not in n:continue
    matrix=world(i)
    for p in doc['meshes'][n['mesh']]['primitives']:
        triangles+=doc['accessors'][p['indices']]['count']//3
        a=doc['accessors'][p['attributes']['POSITION']];view=doc['bufferViews'][a['bufferView']]
        assert a['componentType']==5126 and a['type']=='VEC3'
        offset=view.get('byteOffset',0)+a.get('byteOffset',0);stride=view.get('byteStride',12)
        for j in range(a['count']):
            v=matrix@Vector(struct.unpack_from('<3f',binary,offset+j*stride))
            assert all(math.isfinite(x) for x in v)
            for k in range(3):mins[k]=min(mins[k],v[k]);maxs[k]=max(maxs[k],v[k])
atlas_checks=[]
for m in doc['materials']:
    if not m['name'].startswith('ATELIER_LIGHTMAP_'):continue
    atlas=int(m['name'].rsplit('_',1)[1]);assert 'KHR_materials_unlit' in m.get('extensions',{})
    texture=doc['textures'][m['pbrMetallicRoughness']['baseColorTexture']['index']]
    image=doc['images'][texture['source']];assert image['mimeType']=='image/png'
    view=doc['bufferViews'][image['bufferView']];start=view.get('byteOffset',0);payload=binary[start:start+view['byteLength']]
    png=ROOT/('public/textures/about-atelier-v3/day-%d.png'%atlas)
    assert hashlib.sha256(payload).hexdigest()==sha(png)
    assert struct.unpack_from('>II',payload,16)==(4096,4096)
    atlas_checks.append({'atlas':atlas,'sha256':sha(png),'embeddedMatchesPng':True,'unlit':True})
assert len(atlas_checks)==4
prep=json.loads((ROOT/'assets/blender/about-atelier-v3-web/preparation-report.json').read_text())
assert sha(SOURCE)==prep['sourceSha256']
report={'complete':True,'sourceUnchanged':True,'sourceSha256':sha(SOURCE),'modelSha256':sha(MODEL),'assetCount':len(ids),'interactiveRoots':sum(bool(x.get('interactive')) for x in interactions.values()),'hierarchyPreserved':True,'interactionExtrasPreserved':True,'sourceToGltfRootWorldMatrixMaxError':max(transform_errors.values()),'boundsGltfFromActualVertices':{'min':mins,'max':maxs,'dimensions':[maxs[i]-mins[i] for i in range(3)]},'triangles':triangles,'offlineContextExcluded':True,'atlasValidation':atlas_checks,'assetInterfaces':interactions,'method':'Source loaded in independent background Blender; every original asset world matrix compared to recursively evaluated glTF node matrix after the Z-up/Y-up basis conversion; all exported POSITION vertices inspected; every embedded PNG hash compared.'}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='assetInterfaces'},indent=2))
