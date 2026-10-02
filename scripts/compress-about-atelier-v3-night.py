#!/usr/bin/env python3
"""Encode the five true night maps; validate immutable day/model/UV provenance."""
import argparse,importlib.util,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('about_compression',ROOT/'scripts/compress-about-atelier-v3.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
OUT=ROOT/'public/textures/about-atelier-v3'
REPORT=ROOT/'assets/blender/about-atelier-v3-web/night-validation.json'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    prepared=json.loads((ROOT/'assets/blender/about-atelier-v3-web/night-preparation.json').read_text());assert prepared['complete']
    records=[]
    for index in [0,1,2,3,'architecture']:
        png=OUT/(f'night-{index}.png' if isinstance(index,int) else 'architecture/night.png');manifest=OUT/('night-manifest.json' if isinstance(index,int) else 'architecture/night-manifest.json')
        def ready():
            if not png.exists() or not manifest.exists():return False
            data=json.loads(manifest.read_text())
            row=next((r for r in data['atlases'] if r['atlas']==index),None) if isinstance(index,int) else data
            return row and H.sha(png.read_bytes())==row['sha256']
        while not ready():
            if not args.wait:raise RuntimeError('Night bake not ready: '+str(png))
            time.sleep(2)
        ktx=png.with_suffix('.ktx2');pending=ktx.with_suffix('.pending.ktx2');started=time.monotonic()
        subprocess.run([str(H.ENCODER),'--encode','uastc','--uastc_quality','2','--uastc_rdo_l','3','--zcmp','9','--genmipmap','--threads','2','--assign_oetf','srgb',str(pending),str(png)],check=True)
        subprocess.run([str(H.VALIDATOR),'validate',str(pending)],check=True)
        blob=pending.read_bytes();info=H.ktx_info(blob);assert info['resolution']==[4096,4096];pending.replace(ktx)
        records.append({'atlas':index,'source':H.rel(png),'sourceSha256':H.sha(png.read_bytes()),'path':H.rel(ktx),'sha256':H.sha(blob),'bytes':len(blob),'seconds':round(time.monotonic()-started,2),**info})
        H.atomic_json(REPORT,{'complete':False,'textures':records});print('NIGHT_COMPRESSED '+str(index),flush=True)
    for path,digest in prepared['protected'].items():assert H.sha((ROOT/path).read_bytes())==digest,'Protected day/source changed '+path
    assert prepared['main']['before']==prepared['main']['after']
    assert prepared['architecture']['uvValidation']['shippedUvsRecovered']
    assert prepared['architecture']['before']==prepared['architecture']['after']
    report={'complete':True,'state':'night','samples':64,'trueCyclesCombinedNightBake':True,'dayMapsAndModelsUnchanged':True,'mainGeometryAndUvsUnchanged':True,'architectureGeometryAndPublishedUvsMatch':True,'mainPreparationId':prepared['main']['preparation_id'],'textureCount':5,'textures':records,'encoding':'UASTC quality 2, RDO lambda 3, Zstd 9, sRGB, full mip chain','panorama':'Owned separately; this report gates only the five mesh textures.'}
    H.atomic_json(REPORT,report);print(json.dumps({k:v for k,v in report.items() if k!='textures'},indent=2))

if __name__=='__main__':main()
