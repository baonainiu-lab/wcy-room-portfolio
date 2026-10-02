#!/usr/bin/env python3
"""Encode only new intro-clean-v1 PNGs, preserving all V15 runtime assets."""
import argparse,importlib.util,json,struct,subprocess,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intro_ktx_common',ROOT/'scripts/compress-works-gallery.py');shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
OUT=ROOT/'public/textures/intro-clean-v1';REPORT=OUT/'compression.json'
def main():
 p=argparse.ArgumentParser();p.add_argument('--atlas',type=int,choices=[0,1,8],action='append');args=p.parse_args()
 source=json.loads((OUT/'SOURCE.json').read_text());bakes={r['atlas']:r for r in source['atlases']}
 if (OUT/'atlas-1-SOURCE.json').exists():
  extra=json.loads((OUT/'atlas-1-SOURCE.json').read_text());bakes.update({r['atlas']:r for r in extra['atlases']})
 previous=shared.read_json(REPORT);records={r['atlas']:r for r in previous.get('textures',[])}
 for atlas in args.atlas or [0,1,8]:
  assert atlas in bakes,f'Atlas {atlas} not baked yet'
  src=OUT/f'day-{atlas}.png';dst=src.with_suffix('.ktx2');blob=src.read_bytes();digest=shared.sha(blob)
  assert digest==bakes[atlas]['sha256'],'PNG differs from original bake record'
  dims=list(struct.unpack_from('>II',blob,16));assert dims==bakes[atlas]['dimensions']
  old=records.get(atlas)
  if old and old['sourceSha256']==digest and dst.exists() and shared.sha(dst.read_bytes())==old['sha256']:continue
  started=time.monotonic();pending=dst.with_name(dst.stem+'.pending.ktx2')
  command=[str(shared.TOOL),'--encode','uastc','--uastc_quality','2','--zcmp','9','--genmipmap','--threads','2','--assign_oetf','srgb',str(pending),str(src)]
  subprocess.run(command,check=True);subprocess.run([str(shared.VALIDATOR),'validate',str(pending)],check=True)
  output=pending.read_bytes();info=shared.ktx_info(output);assert info['resolution']==dims;assert shared.sha(src.read_bytes())==digest
  pending.replace(dst)
  records[atlas]={'atlas':atlas,'state':'day','source':shared.rel(src),'sourceSha256':digest,'sourceBytes':len(blob),'path':shared.rel(dst),'sha256':shared.sha(output),'bytes':len(output),**info,'seconds':round(time.monotonic()-started,2),'ktxValidate':'passed','sourcePNGUnchanged':True,'colorSpace':'sRGB','orientation':'rd'}
  shared.atomic_json(REPORT,{'complete':set(records)=={0,1,8},'encoding':'UASTC quality 2 + Zstd 9, full mip chain, sRGB','scope':'intro-only new textures; no original models/maps modified','tool':shared.rel(shared.TOOL),'toolSha256':shared.sha(shared.TOOL.read_bytes()),'authoringScript':'scripts/compress-intro-clean-v1.py','textures':[records[k] for k in sorted(records)]})
  print(json.dumps(records[atlas]),flush=True)
if __name__=='__main__':main()
