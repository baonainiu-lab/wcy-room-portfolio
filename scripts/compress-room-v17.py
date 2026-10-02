#!/usr/bin/env python3
"""CPU-only watcher for completed MCP room bakes, explicit linear-data mipmaps."""
import argparse,hashlib,importlib.util,json,math,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TEX=ROOT/'public/textures/lighting-v17';INTRO=ROOT/'public/textures/intro-clean-v17'
REPORT=ROOT/'assets/blender/photoreal-materials-v17-compression.json'
CODEC_REVISION='linear-surface-v2-logrgb256'
LIGHT_KIND='logrgb32-k256'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
linear=module('linear_surface_compression',ROOT/'scripts/compress-linear-surface.py')
legacy=module('legacy_model_compression',ROOT/'scripts/compress-room-v15.py')
legacy.MODEL=ROOT/'public/models/orbital-atelier-v17.glb';legacy.OUTPUT=ROOT/'public/models/orbital-atelier-v17-compressed.glb'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    try:return json.loads(Path(path).read_text())
    except (FileNotFoundError,json.JSONDecodeError):return {}
def write(path,data):
    temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def ready(path,prepared):
    r=read(path)
    return r if r.get('sourceSha256')==prepared else None
def main(watch=False):
    TEX.mkdir(parents=True,exist_ok=True);prepared=read(ROOT/'assets/blender/photoreal-materials-v17-prepared.json')['sha256']
    assert sha(ROOT/'assets/blender/orbital-dual-bake-v17.blend')==prepared
    old=read(REPORT);records={r['key']:r for r in old.get('textures',[])};started=time.monotonic()
    for name in ('window-day.png','window-night.png','screen-art-render.png','day-window.ktx2','night-window.ktx2','static-screen.ktx2'):
        source=ROOT/'public/textures/lighting-v16'/name;target=TEX/name
        if not target.exists():shutil.copy2(source,target)
        assert sha(source)==sha(target)
    for state,slot,png in [('day','window','window-day.png'),('night','window','window-night.png'),('static','screen','screen-art-render.png')]:
        path=TEX/f'{state}-{slot}.ktx2';records[f'{state}-{slot}']={'key':f'{state}-{slot}','state':state,'slot':slot,'source':str(TEX/png),'sourceSha256':sha(TEX/png),'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'colorSpace':'sRGB, byte-identical to V16'}
    while True:
        candidates=[]
        for slot in range(12):
            surface=ready(TEX/f'surface-{slot}-manifest.json',prepared)
            if surface and surface.get('complete'):
                for kind in ('normal','specular'):candidates.append((f'{kind}-{slot}',kind,slot,Path(surface[kind]['path']),surface[kind]['sha256'],kind))
            for state in ('day','night'):
                r=ready(TEX/f'{state}-{slot}-manifest.json',prepared)
                if r and r.get('encoding')=='RGBM32' and r.get('glossyExcluded'):candidates.append((f'{state}-{slot}',state,slot,Path(r['path']),r['sha256'],LIGHT_KIND))
        for slot in (0,1,8):
            r=ready(INTRO/f'day-{slot}-manifest.json',prepared)
            if r and r.get('cleanIntro') and r.get('receiverOnly'):candidates.append((f'intro-{slot}','intro',slot,Path(r['path']),r['sha256'],LIGHT_KIND))
        for key,state,slot,source,digest,kind in candidates:
            assert source.exists() and sha(source)==digest
            previous=records.get(key);output=source.with_suffix('.ktx2');scale=1;overflow=None
            if state=='night':
                raw=read(source.with_name(source.stem+'-manifest.json'))
                if raw.get('hdrOutliers'):
                    scale=2**math.ceil(math.log2(raw['sourceRadianceMaximum']/32));overflow=raw['hdrOutliers']
            scale_matches=previous and previous.get('radianceScale',1)==scale and (previous.get('radianceOverflow') or {}).get('sha256')==(overflow or {}).get('sha256')
            if previous and scale_matches and previous.get('sourceSha256')==digest and output.exists() and sha(output)==previous['sha256']:
                if kind!=LIGHT_KIND or (previous.get('kind')==LIGHT_KIND and previous.get('codecRevision')==CODEC_REVISION and previous.get('encodedSource') and Path(previous['encodedSource']['path']).exists() and sha(previous['encodedSource']['path'])==previous['encodedSource']['sha256']):continue
            record=linear.compress(source,output,kind,**({'radiance_scale':scale,'radiance_overflow':overflow} if kind==LIGHT_KIND else {}));record.update(key=key,state=state,slot=slot,preparedSha256=prepared);records[key]=record
            write(REPORT,{'complete':False,'preparedSha256':prepared,'textures':list(records.values())})
            print(json.dumps({'key':key,'bytes':record['bytes'],'seconds':record['seconds'],'completed':len(records),'expected':54}),flush=True)
        export=read(ROOT/'assets/blender/dual-lighting-v17-export-report.json')
        if len(records)==54 and export.get('complete') and legacy.MODEL.exists() and export['sha256']==sha(legacy.MODEL):
            assert sha(ROOT/'assets/blender/orbital-dual-bake-v17.blend')==prepared
            model_records={}
            for key,row in records.items():
                embedded=dict(row)
                if row.get('encodedSource'):
                    embedded['source']=row['encodedSource']['path'];embedded['sourceSha256']=row['encodedSource']['sha256']
                model_records[key]=embedded
            model=legacy.compress_model(model_records)
            result={'complete':True,'preparedSha256':prepared,'model':model,'textures':list(records.values()),'runtimeTextureCount':54,'nightRadianceScale':{str(r['slot']):r['radianceScale'] for r in records.values() if r['state']=='night' and r.get('radianceScale',1)!=1},
                'mipPolicy':'Raw RGBM decoded to linear radiance; LogRGB32 gain256 encoded each mip with constant alpha1; normalized normal mips; F0 plus GGX-alpha filtering','codecRevision':CODEC_REVISION,'encoding':'LogRGB32 gain256 opaque UASTC quality2 + Zstd9, explicit full mip chain, NoColorSpace except window/screen'}
            write(REPORT,result);print(json.dumps({'complete':True,'model':model,'textures':54}),flush=True);return
        if not watch:print(json.dumps({'complete':False,'readyTextures':len(records),'expected':54}));return
        if time.monotonic()-started>14400:raise TimeoutError('Room V17 completion exceeded four hours')
        time.sleep(3)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');args=p.parse_args();main(args.watch)
