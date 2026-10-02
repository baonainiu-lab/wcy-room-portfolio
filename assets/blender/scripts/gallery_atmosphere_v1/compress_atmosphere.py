"""Compress real baked PNGs losslessly in resolution; record edge colors for shader blending."""
from pathlib import Path
import time,json,hashlib,subprocess,struct,math
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'public/textures/gallery-atmosphere-v1';TOOL=ROOT/'tools/ktx-software/bin/toktx';VALIDATE=ROOT/'tools/ktx-software/bin/ktx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');q.replace(p)
def linear(c):
 c=c/255;return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
def rgb_sample(im,wx,wz,radius=3):
 x=round((wx/64+.5)*(im.width-1));y=round((wz/64+.5)*(im.height-1))
 pixels=[im.getpixel((i,j)) for j in range(max(0,y-radius),min(im.height,y+radius+1)) for i in range(max(0,x-radius),min(im.width,x+radius+1))]
 return {'world_xz':[wx,wz],'png_center_xy':[x,y],'srgb8':[round(sum(p[c] for p in pixels)/len(pixels),3) for c in range(3)],'linear_rgb':[sum(linear(p[c]) for p in pixels)/len(pixels) for c in range(3)]}
records={};started=time.monotonic()
while time.monotonic()-started<240:
 try:source=json.loads((OUT/'SOURCE.json').read_text())
 except (FileNotFoundError,json.JSONDecodeError):time.sleep(2);continue
 for rec in source['bakes']:
  state=rec['state']
  if state in records:continue
  p=ROOT/rec['path'];assert sha(p)==rec['sha256'];q=OUT/f'{state}.pending.ktx2';target=OUT/f'{state}.ktx2'
  subprocess.run([str(TOOL),'--encode','uastc','--uastc_quality','2','--zcmp','9','--genmipmap','--threads','2','--assign_oetf','srgb',str(q),str(p)],check=True)
  subprocess.run([str(VALIDATE),'validate',str(q)],check=True);q.replace(target)
  im=Image.open(p).convert('RGB');assert im.size==(2048,2048)
  samples=[rgb_sample(im,x,z) for x,z in [(-26,-26),(26,-26),(-26,26),(26,26),(0,-28),(0,28),(-28,0),(28,0),(-14,8),(-8,8),(9,7),(0,10)]]
  far=samples[:8];mean=[sum(s['linear_rgb'][c] for s in far)/len(far) for c in range(3)]
  data=target.read_bytes();assert data[:12]==b'\xabKTX 20\xbb\r\n\x1a\n';fields=struct.unpack_from('<9I',data,12);assert fields[2:4]==(2048,2048) and fields[7]==12 and fields[8]==2
  kvoffset,kvlength=struct.unpack_from('<II',data,56);kv=data[kvoffset:kvoffset+kvlength];orientation='rd' if b'KTXorientation\x00rd' in kv else str(kv)
  records[state]={'state':state,'path':str(target.relative_to(ROOT)),'sha256':sha(target),'bytes':target.stat().st_size,'source_png_sha256':sha(p),'resolution':[2048,2048],'mip_levels':12,'encoding':'UASTC quality2 + Zstd9; sRGB','ktx_orientation':orientation,'samples':samples,'typical_far_linear_rgb':mean,'validated':True};print(json.dumps({'state':state,'ktx2_ready':True,'far_linear':mean}),flush=True)
  write(OUT/'COMPRESSION.json',{'complete':False,'textures':list(records.values())})
 if len(records)==2 and source['complete']:
  write(OUT/'COMPRESSION.json',{'complete':True,'textures':list(records.values()),'seconds':round(time.monotonic()-started,2),'gpu_decode':'Use SRGBColorSpace; colors are already tone-mapped display-referred; do not tone map again.','ktx2_sampler_world_uv':['u=webX/64+.5','v=webZ/64+.5'],'fade_recommendation':'Use core fully through radius23 and fade to measured far linear color by radius32.'});break
 time.sleep(2)
else:raise RuntimeError('Bake did not complete within 240 seconds')
