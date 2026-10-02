#!/usr/bin/env python3
"""Read-only resolution and sampled pixel validation of the paired room bakes."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SIZES=[4096]*6+[3072,2048,3072,4096,4096,3072]

def image_record(path,size):
    with Image.open(path) as image:
        assert image.size==(size,size) and image.mode=='RGB',(path,image.size,image.mode)
        # Deterministic sparse readback limits memory while the GPU batch runs.
        values=np.asarray(image)[::8,::8].copy()
    occupied=np.max(values,axis=2)>3
    assert occupied.any(),f'Empty bake: {path}'
    luma=np.dot(values.astype(np.float32),[.2126,.7152,.0722])
    return values,{'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'resolution':[size,size],'sampleStride':8,'nonBlackSampleFraction':float(occupied.mean()),
        'occupiedLumaMean':float(luma[occupied].mean()),'occupiedLumaPercentiles':np.percentile(luma[occupied],[1,50,95,99]).tolist()}

def main():
    records=[]
    for slot,size in enumerate(SIZES):
        day,dr=image_record(ROOT/f'public/textures/lighting-v16/day-{slot}.png',size)
        night,nr=image_record(ROOT/f'public/textures/lighting-v16/night-{slot}.png',size)
        mask=(np.max(day,axis=2)>3)|(np.max(night,axis=2)>3)
        difference=np.abs(day.astype(np.float32)-night.astype(np.float32))
        mae=float(difference[mask].mean())
        assert mae>0,f'Day and night duplicate at slot {slot}'
        records.append({'slot':slot,'day':dr,'night':nr,'occupiedDayNightMeanAbsoluteDifference':mae})
    result={'complete':True,'method':'Original PNG readback only; deterministic stride-8 statistics in display-referred RGB. No pixel modifications.',
        'resolutionChecksPassed':True,'nonEmptyChecksPassed':True,'distinctDayNightChecksPassed':True,'slots':records}
    path=ROOT/'assets/blender/photoreal-materials-v16-pixels.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'complete':True,'slots':len(records),'report':str(path.relative_to(ROOT))}))

if __name__=='__main__':main()
