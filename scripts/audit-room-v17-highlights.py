#!/usr/bin/env python3
"""CPU audit of rare night range-32 highlights; no Blender process is launched."""
import hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
SHADER=ROOT/'node_modules/three/src/renderers/shaders/ShaderChunk/tonemapping_pars_fragment.glsl.js'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def agx(rgb):
    text=SHADER.read_text()
    def matrix(name):
        body=re.search(r'const mat3 '+name+r' = mat3\((.*?)\);',text,re.S)[1]
        return np.array([[float(v.replace(' ','')) for v in row.split(',')] for row in re.findall(r'vec3\(\s*([^)]*)\)',body)])
    color=rgb@matrix('LINEAR_SRGB_TO_LINEAR_REC2020')@matrix('AgXInsetMatrix')
    x=np.clip((np.log2(np.maximum(color,1e-10))+12.47393)/(4.026069+12.47393),0,1)
    color=15.5*x**6-40.14*x**5+31.96*x**4-6.868*x**3+.4298*x*x+.1191*x-.00232
    color=np.maximum(color@matrix('AgXOutsetMatrix'),0)**2.2
    color=np.clip(color@matrix('LINEAR_REC2020_TO_LINEAR_SRGB'),0,1)
    return np.where(color<=.0031308,color*12.92,1.055*color**(1/2.4)-.055)
def audit():
    reports=[]
    for p in sorted((ROOT/'public/textures/lighting-v17').glob('night-*-manifest.json')):
        record=json.loads(p.read_text())
        if not record['valuesAboveRangeFraction']:continue
        within_limit=record['valuesAboveRangeFraction']<=1e-5 and record['sourceRadianceMaximum']<=64
        source=Path(record['path']);assert sha(source)==record['sha256']
        image=np.asarray(Image.open(source).convert('RGBA'));h,w=image.shape[:2]
        mask=(image[...,:3]==255)&(image[...,3:4]==255)
        outliers=record.get('hdrOutliers');exact=bool(outliers)
        if exact:
            assert sha(outliers['path'])==outliers['sha256']
            with np.load(outliers['path']) as data:indices=data['indices'];values=data['values']
            x=(indices//3)%w;y=h-1-(indices//3)//w;c=indices%3
            mask=np.zeros_like(mask);mask[y,x,c]=True
        selected=mask.any(2);points=np.argwhere(selected);pixels=image[selected]
        rgb=pixels[:,:3].astype(np.float64)/255*pixels[:,3:4]/255*32;estimated=rgb.copy()
        if exact:
            lookup={(int(py),int(px)):i for i,(py,px) in enumerate(points)}
            for py,px,channel,value in zip(y,x,c,values):estimated[lookup[(int(py),int(px))],channel]=value
        else:estimated[mask[selected]]=record['sourceRadianceMaximum']
        delta=np.abs(agx(estimated)-agx(rgb))
        samples=[{'x':int(x),'y':int(y),'uv':[(float(x)+.5)/w,1-(float(y)+.5)/h]} for y,x in points]
        report={'complete':False,'withinDefaultReviewedLimit':within_limit,'slot':record['slot'],'sourceSha256':record['sourceSha256'],'rawPngSha256':record['sha256'],
            'sourceMaximum':record['sourceRadianceMaximum'],'clippedChannelFraction':record['valuesAboveRangeFraction'],
            'sourceClippedChannels':round(record['valuesAboveRangeFraction']*w*h*3),'identifiedSaturatedChannels':int(mask.sum()),
            'affectedPixels':len(points),'affectedPixelFraction':len(points)/(w*h),'exactPreEncodingFloatsAvailable':exact,
            'coordinateMethod':'Exact saved float indices' if exact else 'Saturated RGBA8 channels; may include near-32 values rounded to 32',
            'agxExposure':1,'agxShaderSha256':sha(SHADER),'agxSrgbMaxDifference':float(delta.max()),'agxSrgbMeanDifference':float(delta.mean()),
            'agxComparison':'Exact restored over-range source floats' if exact else 'Sensitivity estimate: every saturated channel raised to the observed maximum; not an exact reconstruction',
            'notLargeArea':len(points)/(w*h)<3e-5,'samples':samples}
        output=ROOT/f'assets/blender/room-v17-highlight-audit-{record["slot"]}.json'
        output.write_text(json.dumps(report,indent=2)+'\n');reports.append({k:v for k,v in report.items() if k!='samples'})
    return reports
if __name__=='__main__':print(json.dumps(audit(),indent=2))
