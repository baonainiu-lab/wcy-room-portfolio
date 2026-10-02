#!/usr/bin/env python3
"""Measure actual re-baked floor pixels through the unchanged mesh UVs.

This checks released numeric pixels, not material labels. It is not a substitute
for the root's source render or WebGL appearance review.
"""
import importlib.util
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v18_codec', ROOT / 'scripts/compress-linear-surface.py')
codec = importlib.util.module_from_spec(spec); spec.loader.exec_module(codec)

def accessor(doc, binary, index):
    a = doc['accessors'][index]; v = doc['bufferViews'][a['bufferView']]
    width = {'VEC2':2,'VEC3':3,'SCALAR':1}[a['type']]
    dtype = {5126:'<f4',5125:'<u4',5123:'<u2'}[a['componentType']]
    size = np.dtype(dtype).itemsize
    return np.ndarray((a['count'],width), dtype=dtype, buffer=binary,
                      offset=v.get('byteOffset',0)+a.get('byteOffset',0),
                      strides=(v.get('byteStride',width*size),size)).copy()

def measure():
    source = ROOT / 'public/models/orbital-atelier-v16.glb'
    blob = source.read_bytes(); length = struct.unpack_from('<I',blob,12)[0]
    doc = json.loads(blob[20:20+length]); binary=blob[28+length:]
    prepared=json.loads((ROOT/'assets/blender/photoreal-materials-v18-prepared.json').read_text())
    assert codec.sha(ROOT/prepared['derivative'])==prepared['sha256']
    rng = np.random.default_rng(18); rows=[]
    for node in doc['nodes']:
        extra = node.get('extras',{})
        if extra.get('owner_asset_id') != 'architecture.platform': continue
        slot = extra['bake_atlas']
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            positions=accessor(doc,binary,primitive['attributes']['POSITION'])
            normals=accessor(doc,binary,primitive['attributes']['NORMAL'])
            uv=accessor(doc,binary,primitive['attributes']['TEXCOORD_0'])
            triangles=accessor(doc,binary,primitive['indices']).reshape(-1,3)
            corners=positions[triangles]
            up=np.all(normals[triangles][:,:,1]>.99,axis=1)
            centers=np.mean(corners,axis=1)
            interior=(np.abs(centers[:,0])<4.82)&(np.abs(centers[:,2])<3.25)
            top=np.all((corners[:,:,1]>.175)&(corners[:,:,1]<.185),axis=1)
            areas=np.linalg.norm(np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0]),axis=1)/2
            usable=up & interior & top & (areas>1e-6)
            indices=np.flatnonzero(usable)
            if not len(indices): continue
            picks=rng.choice(indices,5000,p=areas[usable]/areas[usable].sum())
            r=np.sqrt(rng.uniform(.02,.98,5000));t=rng.uniform(.02,.98,5000)
            bary=np.stack((1-r,r*(1-t),r*t),axis=-1)
            world_points=np.sum(corners[picks]*bary[:,:,None],axis=1)
            inside=(np.abs(world_points[:,0])<4.6)&(np.abs(world_points[:,2])<3.1)
            points=np.sum(uv[triangles[picks]]*bary[:,:,None],axis=1)[inside]
            values={}; hashes={}
            for version in ('v17','v18'):
                for kind in ('day','specular','normal'):
                    filename=ROOT/f'public/textures/lighting-{version}/{kind}-{slot}.png'
                    if version=='v18':
                        manifest=json.loads((filename.with_name(f'day-{slot}-manifest.json') if kind=='day' else filename.with_name(f'surface-{slot}-manifest.json')).read_text())
                        assert manifest['sourceSha256']==prepared['sha256'], 'Await current-source floor bake.'
                        data=manifest if kind=='day' else manifest[kind]
                        assert codec.sha(filename)==data['sha256']
                    arr=np.asarray(Image.open(filename),dtype=np.uint8)
                    x=np.clip((points[:,0]*arr.shape[1]).astype(int),0,arr.shape[1]-1)
                    y=np.clip((points[:,1]*arr.shape[0]).astype(int),0,arr.shape[0]-1)
                    pixels=arr[y,x]
                    values[(version,kind)]=codec.decode(pixels.reshape(1,-1,4),'rgbm32')[0] if kind=='day' else pixels.astype(np.float32)/255
                    hashes[f'{version}-{kind}']=codec.sha(filename)
            before,after=values[('v17','day')],values[('v18','day')]
            lit=after.max(axis=1)>.005  # V17 metal has zero diffuse; this is physically expected.
            assert lit.sum()>100
            change=np.max(np.abs(before[lit]-after[lit]),axis=1)/np.maximum(before[lit].max(axis=1),.005)
            stats={}
            for version in ('v17','v18'):
                rgb=values[(version,'day')][lit]; specular=values[(version,'specular')][lit]
                stats[version]=dict(medianLinearRGB=np.median(rgb,axis=0).tolist(),
                                    medianRedToBlueRatio=float(np.median(rgb[:,0]/np.maximum(rgb[:,2],.001))),
                                    medianF0=np.median(specular[:,:3],axis=0).tolist(),medianRoughness=float(np.median(specular[:,3])))
            changed=float(np.mean(change>.02))
            assert changed>.5, 'Actual floor radiance barely differs from the metal version.'
            rows.append(dict(slot=slot,node=node['name'],upwardInteriorFloorAreaM2=float(areas[usable].sum()),samples=len(points),
                             litSamples=int(lit.sum()),fractionChangedMoreThanTwoPercent=changed,
                             linearDifferenceP50P95=np.percentile(change,[50,95]).tolist(),states=stats,sourceHashes=hashes))
    assert rows, 'No verified top-floor UV footprint was measured.'
    result=dict(complete=True,preparedSha256=prepared['sha256'],runtimeActivated=False,checks='Area-weighted samples on actual upward floor triangles via existing BakeUV; original RGBM32 decoded into scene radiance.',
                roomGeometrySource=str(source.relative_to(ROOT)),geometrySha256=codec.sha(source),rows=rows,
                limitations='Numerical source-bake validation; photoreal appearance, grazing reflections and warm palette still require source-render / browser review.')
    out=ROOT/'assets/blender/room-v18-warm-pixels-validation.json';out.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(measure(),indent=2))
