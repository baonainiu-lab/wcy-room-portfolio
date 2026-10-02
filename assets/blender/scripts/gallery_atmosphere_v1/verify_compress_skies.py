"""Calibrate world panorama directions, validate physical sun alignment, compress KTX2."""
from pathlib import Path
import json,hashlib,subprocess,struct,math,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'public/textures/gallery-atmosphere-v1';SOURCE=OUT/'SKY_SOURCE.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def srgb_to_linear(a):
    c=a/255.;return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
def uv_to_web(u,v):
    lon=(u-.5)*2*math.pi;lat=(.5-v)*math.pi;return np.array([math.sin(lon)*math.cos(lat),math.sin(lat),-math.cos(lon)*math.cos(lat)])
r=json.loads(SOURCE.read_text());cal=np.array(Image.open(ROOT/r['calibration']).convert('RGB'));height,width=cal.shape[:2];calibration={}
masks={'blender_plus_x_web_plus_x':(cal[:,:,0]>200)&(cal[:,:,1]<50)&(cal[:,:,2]<50),'blender_plus_y_web_minus_z':(cal[:,:,0]<50)&(cal[:,:,1]>200)&(cal[:,:,2]<50),'blender_minus_x_web_minus_x':(cal[:,:,0]>200)&(cal[:,:,1]<50)&(cal[:,:,2]>200),'blender_minus_y_web_plus_z':(cal[:,:,0]>200)&(cal[:,:,1]>200)&(cal[:,:,2]<50)}
for name,mask in masks.items():
    y,x=np.where(mask);assert len(x)>3;u=((np.angle(np.exp(2j*math.pi*(x+.5)/width).mean())/(2*math.pi))%1);v=((y+.5)/height).mean();calibration[name]={'uv_top_down':[float(u),float(v)],'pixels':len(x),'web_direction_measured':uv_to_web(u,v).tolist()}
day=np.array(Image.open(OUT/'day-sky.png').convert('RGB'));h,w=day.shape[:2];mask=np.all(day>=254,axis=2);yy,xx=np.where(mask);assert len(xx)>3
u=float(np.mean((xx+.5)/w));v=float(np.mean((yy+.5)/h));actual=uv_to_web(u,v);target=np.array(r['sun_web_direction']);target/=np.linalg.norm(target);error=math.degrees(math.acos(float(np.clip(actual@target,-1,1))));assert error<.25,(actual.tolist(),target.tolist(),error)
expected=[.5+math.atan2(target[0],-target[2])/(2*math.pi),.5-math.asin(target[1])/math.pi]
records=[]
for image in r['renders']:
    state=image['state'];src=ROOT/image['path'];assert sha(src)==image['sha256'];a=np.array(Image.open(src).convert('RGB'));h,w=a.shape[:2]
    colors={}
    for name,sample in [('upper_hemisphere',a[:h//2]),('zenith',a[:60]),('upper_horizon',a[495:505]),('lower_horizon',a[520:530]),('lower_hemisphere',a[h//2:])]:
        lin=srgb_to_linear(sample.astype(np.float64));colors[name]={'srgb8_mean':sample.mean(axis=(0,1)).tolist(),'srgb8_min':sample.min(axis=(0,1)).tolist(),'srgb8_max':sample.max(axis=(0,1)).tolist(),'linear_mean':lin.mean(axis=(0,1)).tolist()}
    output=OUT/f'{state}-sky.ktx2';pending=OUT/f'.{state}-sky.pending.ktx2'
    if not (state=='night' and '--day-only' in sys.argv and output.exists()):
        subprocess.run([str(ROOT/'tools/ktx-software/bin/toktx'),'--encode','uastc','--uastc_quality','2','--zcmp','9','--genmipmap','--threads','2','--assign_oetf','srgb',str(pending),str(src)],check=True);subprocess.run([str(ROOT/'tools/ktx-software/bin/ktx'),'validate',str(pending)],check=True);pending.replace(output)
    else:
        subprocess.run([str(ROOT/'tools/ktx-software/bin/ktx'),'validate',str(output)],check=True)
    data=output.read_bytes();assert struct.unpack_from('<II',data,20)==(2048,1024);kvstart,kvlen=struct.unpack_from('<II',data,56);kv=data[kvstart:kvstart+kvlen];assert b'KTXorientation\x00rd' in kv
    records.append({'state':state,'path':str(output.relative_to(ROOT)),'sha256':sha(output),'bytes':output.stat().st_size,'resolution':[2048,1024],'mip_levels':12,'orientation':'rd','source_png_sha256':image['sha256'],'encoding':'UASTC quality2 + Zstd9, sRGB','color_ranges':colors,'validated':True})
r.update(direction_verification={'complete':True,'cardinal_calibration':calibration,'sun_expected_web_direction':target.tolist(),'sun_measured_web_direction':actual.tolist(),'sun_expected_uv_top_down':expected,'sun_measured_uv_top_down':[u,v],'sun_core_pixels':len(xx),'angular_error_degrees':error},runtime_uv_contract={'direction':'normalized world Web direction, Y up','u':'fract(0.5 + atan(direction.x, -direction.z) / (2*PI))','v_ktx2_or_png_flipY_false':'0.5 - asin(clamp(direction.y,-1,1)) / PI','v_png_flipY_true':'0.5 + asin(clamp(direction.y,-1,1)) / PI','yaw_rotation_radians':0,'cardinals':{'web_minus_z':[.5,.5],'web_plus_x':[.75,.5],'web_plus_z':[0,.5],'web_minus_x':[.25,.5],'web_plus_y':[None,0]},'texture_color_space':'sRGB','tone_mapped':False,'wrap_s':'Repeat','wrap_t':'ClampToEdge'},compressed_textures=records,lower_hemisphere_note='Day physical atmosphere has black lower hemisphere because no ground exists in this empty-world render. Runtime must blend view directions below horizon toward measured upper-horizon fog color, not sample black lower day sky into far ground. Night contains a quiet symmetric gradient but should share the same fog handling.',gpu_jobs_complete=True)
SOURCE.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'complete':True,'sun_error_degrees':error,'sun_uv':[u,v],'expected':expected,'ktx2':[{k:t[k] for k in ('state','sha256','bytes')} for t in records]}))
