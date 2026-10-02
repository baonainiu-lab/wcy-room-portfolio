"""Package MCP-baked physical atlases without touching geometry or About files."""
import argparse,copy,importlib.util,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
codec=module('linear_codec',ROOT/'scripts/compress-linear-surface.py')
gltf=module('gallery_glb',ROOT/'scripts/compress-works-gallery.py')
OUT=ROOT/'public/textures/works-gallery-v6'
REPORT=ROOT/'assets/blender/works-gallery-v6/release.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def encode_ready():
    count=0
    for kind in ('day','night','specular','normal'):
        for slot in range(4):
            p=OUT/f'{kind}-{slot}.png';target=p.with_suffix('.ktx2')
            manifest=OUT/(f'surface-{slot}-manifest.json' if kind in ('specular','normal') else f'{kind}-{slot}-manifest.json')
            if not manifest.exists() or not p.exists():continue
            record=json.loads(manifest.read_text());part=record[kind] if kind in ('specular','normal') else record
            assert sha(p)==part['sha256'],f'Stale bake {p}'
            previous=target.with_suffix('.ktx2.json')
            output_kind='logrgb32-k256' if kind in ('day','night') else kind
            if target.exists() and previous.exists():
                old=json.loads(previous.read_text())
                if old['sourceSha256']==sha(p) and old['sha256']==sha(target) and old['kind']==output_kind:
                    if output_kind!='logrgb32-k256' or old.get('codecRevision')=='linear-surface-v2-logrgb256':count+=1;continue
            result=codec.compress(p,target,output_kind)
            print(f'Encoded {kind}-{slot}: {result["bytes"]} bytes',flush=True);count+=1
    return count

def release():
    assert encode_ready()==16
    assert all((OUT/f'reflection-{state}.hdr').exists() for state in ('day','night'))
    src=ROOT/'public/models/works-gallery-v5-compressed.glb';blob=src.read_bytes();original,chunks=gltf.parse_glb(blob);doc=copy.deepcopy(original)
    binary=next(data for kind,data in chunks if kind==gltf.BIN_CHUNK);replacements={};slots=set()
    for mat in doc['materials']:
        name=mat.get('name','')
        if not name.startswith('GALLERY_LIGHTMAP_'):continue
        slot=int(name.split('_')[-1]);slots.add(slot)
        texture=doc['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]
        image=doc['images'][texture['extensions']['KHR_texture_basisu']['source']]
        assert image['mimeType']=='image/ktx2';replacements[image['bufferView']]=(OUT/f'night-{slot}.ktx2').read_bytes()
        image.setdefault('extras',{}).update(sha256=sha(OUT/f'night-{slot}.ktx2'),
            source_png_sha256=sha(OUT/f'night-{slot}.logrgb.png'),raw_rgbm_sha256=sha(OUT/f'night-{slot}.png'),encoding='LogRGB32 k256 alpha1')
        mat.setdefault('extras',{})['physical_encoding']='LogRGB32 k256 diffuse + emission; F0/roughness and normal companions'
    assert slots=={0,1,2,3};rebuilt=bytearray();preserved={}
    for index,view in enumerate(doc['bufferViews']):
        old=gltf.view_bytes(original,binary,original['bufferViews'][index]);data=replacements.get(index,old)
        rebuilt.extend(b'\0'*(-len(rebuilt)%4));view['byteOffset']=len(rebuilt);view['byteLength']=len(data);rebuilt.extend(data)
        if index not in replacements:preserved[index]=hashlib.sha256(old).hexdigest()
    doc['buffers'][0]['byteLength']=len(rebuilt)
    doc['asset'].setdefault('extras',{})['physicalMaterialRevision']='Gallery V6, actual MCP/Cycles, LogRGB32 k256 encoded linear radiance'
    doc['asset']['extras'].update(export_kind='works_gallery_physical_v6',
        preparation_id=json.loads((ROOT/'assets/blender/works-gallery-v6/prepared-materials.json').read_text())['preparation_id'],
        day_lightmaps=[{'atlas':slot,'uri':f'../textures/works-gallery-v6/day-{slot}.ktx2',
            'resolution':4096 if slot<3 else 1024,'sha256':sha(OUT/f'day-{slot}.ktx2'),
            'png_fallback':f'../textures/works-gallery-v6/day-{slot}.logrgb.png','png_sha256':sha(OUT/f'day-{slot}.logrgb.png'),
            'encoding':'LogRGB32 k256 alpha1'} for slot in range(4)])
    output=gltf.pack_glb(doc,[(kind,bytes(rebuilt) if kind==gltf.BIN_CHUNK else data) for kind,data in chunks])
    check,outchunks=gltf.parse_glb(output);outbin=next(data for kind,data in outchunks if kind==gltf.BIN_CHUNK)
    for key in ('nodes','meshes','accessors','scenes'):assert check[key]==original[key],key
    for i,digest in preserved.items():assert hashlib.sha256(gltf.view_bytes(check,outbin,check['bufferViews'][i])).hexdigest()==digest
    assert src.read_bytes()==blob
    target=ROOT/'public/models/works-gallery-v6-compressed.glb';target.write_bytes(output)
    manifests=[json.loads(p.read_text()) for p in sorted(OUT.glob('*.ktx2.json'))]
    report={'complete':True,'model':str(target.relative_to(ROOT)),'sha256':sha(target),'bytes':len(output),'geometryHierarchyUvsUnchanged':True,'preservedNonAtlasBufferViews':len(preserved),'atlasSlots':sorted(slots),'textures':manifests,'sourceModel':str(src.relative_to(ROOT)),'sourceModelSha256':sha(src),'production':'Blender MCP material authoring and Cycles bake; CPU linear-data compression and GLB texture packaging','aboutUntouched':True}
    REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('complete','model','bytes','geometryHierarchyUvsUnchanged')}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--textures-only',action='store_true');a=p.parse_args()
    if a.watch:
        started=time.monotonic()
        while encode_ready()<16 and time.monotonic()-started<14400:time.sleep(8)
    if a.textures_only:print('Ready textures',encode_ready())
    else:release()
