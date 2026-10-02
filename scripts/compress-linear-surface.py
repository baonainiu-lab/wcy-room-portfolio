#!/usr/bin/env python3
"""Encode linear radiance/data textures with physically meaningful mipmaps.

Run with bundled Python (NumPy/Pillow). Also importable by Room/Gallery release
drivers as compress(source, output, kind). No Blender process is launched.
"""
import argparse,hashlib,json,math,struct,subprocess,tempfile,time
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/'tools/ktx-software/bin/toktx'
VALIDATOR=ROOT/'tools/ktx-software/bin/ktx'
KINDS=('rgbm32','logrgb32-k256','specular','normal')
CODEC_REVISION='linear-surface-v2-logrgb256'
LOGRGB_K=256.0
RADIANCE_RANGE=32.0
LOGRGB_DENOM=math.log2(1+LOGRGB_K*RADIANCE_RANGE)
SCALING_REVISION='linear-radiance-overflow-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reduce_float(values):
    h,w=values.shape[:2];size=(max(1,w//2),max(1,h//2))
    return np.stack([np.asarray(Image.fromarray(values[...,c].astype(np.float32)).resize(size,Image.Resampling.BOX)) for c in range(values.shape[2])],axis=2)
def normalize(v):
    length=np.linalg.norm(v,axis=2,keepdims=True);unit=v/np.maximum(length,1e-8)
    unit[length[...,0]<1e-8]=(0,0,1);return unit
def rgbm_encode(rgb):
    m=np.clip(np.ceil(np.max(rgb,axis=2)/32*255),1,255)
    colors=np.rint(np.clip(rgb/(m[...,None]/255*32),0,1)*255)
    return np.concatenate((colors,m[...,None]),axis=2).astype(np.uint8)
def logrgb_encode(rgb):
    # Alpha is deliberately constant: UASTC can quantize small RGBM multipliers
    # to zero, destroying otherwise nonzero radiance in complete 4x4 blocks.
    colors=np.log2(1+LOGRGB_K*np.clip(rgb,0,RADIANCE_RANGE))/LOGRGB_DENOM
    colors=np.rint(np.clip(colors,0,1)*255).astype(np.uint8)
    return np.concatenate((colors,np.full((*colors.shape[:2],1),255,np.uint8)),axis=2)
def decode(arr,kind):
    assert kind in KINDS
    values=arr.astype(np.float32)/255
    if kind=='rgbm32':return values[...,:3]*values[...,3:4]*32
    if kind=='logrgb32-k256':return np.expm1(values[...,:3]*math.log(1+LOGRGB_K*RADIANCE_RANGE))/LOGRGB_K
    if kind=='normal':return normalize(values[...,:3]*2-1)
    # GGX alpha = perceptual roughness squared. Filter this alpha, then recover
    # perceptual roughness; RGB F0 is already scene-linear reflectance.
    values[...,3]**=2;return values
def encode(values,kind):
    assert kind in KINDS
    if kind=='rgbm32':return rgbm_encode(values)
    if kind=='logrgb32-k256':return logrgb_encode(values)
    if kind=='normal':
        rgb=normalize(values)*.5+.5;values=np.concatenate((rgb,np.ones((*rgb.shape[:2],1),np.float32)),axis=2)
    else:
        values=values.copy();values[...,3]=np.sqrt(np.maximum(values[...,3],0))
    return np.rint(np.clip(values,0,1)*255).astype(np.uint8)

def project_path(path):
    path=Path(path)
    return path.resolve() if path.is_absolute() else (ROOT/path).resolve()

def restored_radiance(original,source,radiance_scale=1,radiance_overflow=None):
    """Recover known >32 source channels before normalizing one atlas.

    NPZ indices address Blender's bottom-up flat RGB buffer, while PNG arrays
    are top-down. The neighboring bake manifest must bind both immutable files.
    This never estimates highlights that were not retained in the sidecar.
    """
    scale=float(radiance_scale)
    if not math.isfinite(scale) or scale<1:raise ValueError('radiance_scale must be finite and at least 1.')
    source=Path(source).resolve();values=decode(original,'rgbm32');metadata=None
    if radiance_overflow is not None:
        if not isinstance(radiance_overflow,dict) or not {'path','sha256'}<=radiance_overflow.keys():
            raise ValueError('radiance_overflow requires path and sha256.')
        path=project_path(radiance_overflow['path']);digest=sha(path)
        if digest!=radiance_overflow['sha256']:raise ValueError('Radiance overflow SHA mismatch.')
        manifest_path=project_path(radiance_overflow.get('sourceManifest',source.with_name(f'{source.stem}-manifest.json')))
        if radiance_overflow.get('sourceManifestSha256') and sha(manifest_path)!=radiance_overflow['sourceManifestSha256']:
            raise ValueError('Overflow bake manifest SHA changed since compression.')
        manifest=json.loads(manifest_path.read_text());bound=manifest.get('hdrOutliers',{})
        if manifest.get('sha256')!=sha(source):raise ValueError('Overflow bake manifest does not match source PNG.')
        if bound.get('sha256')!=digest or project_path(bound.get('path',''))!=path:
            raise ValueError('Overflow sidecar is not bound to the source bake manifest.')
        with np.load(path,allow_pickle=False) as saved:
            if set(saved.files)!={'indices','values','shape'}:raise ValueError('Unexpected overflow NPZ schema.')
            indices=saved['indices'];highlights=saved['values'];shape=saved['shape']
        if indices.dtype!=np.uint32 or highlights.dtype!=np.float32 or shape.dtype!=np.int64:
            raise ValueError('Overflow requires uint32 indices, float32 values and int64 shape.')
        if shape.shape!=(3,) or tuple(shape)!=values.shape:raise ValueError('Overflow dimensions differ from source PNG.')
        if indices.ndim!=1 or highlights.shape!=indices.shape or not len(indices):raise ValueError('Overflow arrays must be nonempty matching vectors.')
        if int(indices.max())>=values.size or len(np.unique(indices))!=len(indices):raise ValueError('Overflow indices must be unique and in range.')
        if not np.isfinite(highlights).all() or not np.all(highlights>RADIANCE_RANGE):raise ValueError('Overflow values must be finite and above 32.')
        if bound.get('count')!=len(indices):raise ValueError('Overflow count differs from source bake manifest.')
        if 'bottom-up' not in bound.get('indexConvention','') or 'RGB' not in bound.get('indexConvention',''):
            raise ValueError('Overflow index convention must explicitly identify bottom-up RGB.')
        height,width=values.shape[:2];pixel=indices.astype(np.int64)//3
        y_top=height-1-pixel//width;x=pixel%width;channel=indices%3
        if not np.allclose(values[y_top,x,channel],RADIANCE_RANGE,rtol=0,atol=1e-4):
            raise ValueError('Overflow indices do not address clipped source PNG channels; row orientation or source is wrong.')
        values[y_top,x,channel]=highlights
        metadata={'path':str(path),'sha256':digest,'count':len(indices),
            'indexConvention':'flattened bottom-up Blender RGB float buffer; convert yTop=height-1-yBottom before PNG restoration',
            'sourceManifest':str(manifest_path),'sourceManifestSha256':sha(manifest_path),
            'restoredMaximum':float(highlights.max())}
    peak=float(values.max())
    if peak>RADIANCE_RANGE*scale+1e-4:
        suggested=2**math.ceil(math.log2(peak/RADIANCE_RANGE))
        raise ValueError(f'Restored radiance {peak} exceeds 32 * scale {scale}; use at least power-of-two scale {suggested}.')
    return values,scale,metadata

def compress(source,output,kind,quality=2,*,radiance_scale=1,radiance_overflow=None):
    assert kind in KINDS
    source=Path(source);output=Path(output);digest=sha(source);started=time.monotonic()
    with Image.open(source) as image:
        assert image.mode=='RGBA',f'Alpha is data, source must be RGBA: {source}'
        original=np.asarray(image).copy()
    # The authoring source remains the unchanged linear RGBM32 bake. Only the
    # web representation changes; decoding a source as LogRGB would be wrong.
    source_kind='rgbm32' if kind=='logrgb32-k256' else kind
    source_alpha=original[...,3];mip_stats=[];overflow=None;scale=1.;scene_peak=None
    if kind=='logrgb32-k256':
        values,scale,overflow=restored_radiance(original,source,radiance_scale,radiance_overflow)
        scene_peak=float(values.max());values=values/scale
    else:
        if radiance_scale!=1 or radiance_overflow is not None:raise ValueError('Radiance scale/overflow are only supported for logrgb32-k256.')
        values=decode(original,source_kind)
    source_encoding={'rgbm32':'RGBM32','specular':'Linear F0 RGB + perceptual roughness alpha','normal':'Tangent GL XYZ encoded in RGB, alpha1'}[source_kind]
    encoded_path=source
    if kind=='logrgb32-k256':
        encoded_path=source.with_suffix('.logrgb.png')
        assert encoded_path!=source
        packed=encode(values,kind)
        # Write a permanent same-encoding PNG fallback, including the base mip.
        # Do not pass the original RGBM PNG as level0 to the KTX encoder.
        pending_png=encoded_path.with_suffix('.pending.png')
        Image.fromarray(packed,'RGBA').save(pending_png);pending_png.replace(encoded_path)
        mip_stats.append({'level':0,'dimensions':[values.shape[1],values.shape[0]],'encodingQuantizationMAE':float(np.mean(np.abs(decode(packed,kind)-values)))})
    encoded_digest=sha(encoded_path)
    with tempfile.TemporaryDirectory(prefix='linear-texture-mips-') as temp:
        files=[str(encoded_path)];level=0
        while max(values.shape[:2])>1:
            values=reduce_float(values);level+=1;packed=encode(values,kind)
            path=Path(temp)/f'mip-{level}.png';Image.fromarray(packed,'RGBA').save(path);files.append(str(path))
            decoded=decode(packed,kind)
            reference=normalize(values) if kind=='normal' else values
            mip_stats.append({'level':level,'dimensions':[values.shape[1],values.shape[0]],'encodingQuantizationMAE':float(np.mean(np.abs(decoded-reference)))})
        output.parent.mkdir(parents=True,exist_ok=True);pending=output.with_suffix('.pending.ktx2')
        command=[str(TOOL),'--encode','uastc','--uastc_quality',str(quality),'--zcmp','9','--threads','2',
                 '--assign_oetf','linear','--assign_primaries','none','--target_type','RGBA','--mipmap',str(pending),*files]
        subprocess.run(command,check=True,capture_output=True,text=True)
        subprocess.run([str(VALIDATOR),'validate',str(pending)],check=True,capture_output=True,text=True)
        blob=pending.read_bytes();assert blob[:12]==b'\xabKTX 20\xbb\r\n\x1a\n'
        level_count=struct.unpack_from('<I',blob,40)[0];assert level_count==len(files)
        dfd=struct.unpack_from('<I',blob,48)[0]
        assert blob[dfd+14]==1,'KTX DFD transfer function must be linear'
        assert not blob[dfd+15]&1,'Data alpha must never be premultiplied'
        assert sha(source)==digest,'Source changed during compression'
        assert sha(encoded_path)==encoded_digest,'Encoded fallback changed during compression'
        if overflow:
            assert sha(overflow['path'])==overflow['sha256'],'Overflow source changed during compression'
            assert sha(overflow['sourceManifest'])==overflow['sourceManifestSha256'],'Overflow binding manifest changed during compression'
        pending.replace(output)
    result={'complete':True,'source':str(source),'sourceSha256':digest,'path':str(output),'sha256':sha(output),'bytes':output.stat().st_size,
        'codecRevision':CODEC_REVISION,'sourceEncoding':source_encoding,
        'encodedSource':{'path':str(encoded_path),'sha256':encoded_digest,'encoding':'LogRGB32 k256 alpha1' if kind=='logrgb32-k256' else source_encoding},
        'kind':kind,'dimensions':[original.shape[1],original.shape[0]],'mipLevels':level_count,'quality':quality,'ktxValidate':'passed',
        'transferFunction':'linear','targetType':'RGBA','premultipliedAlpha':False,'sourceAlphaRange':[int(source_alpha.min()),int(source_alpha.max())],
        'mipMethod':{'rgbm32':'Decode RGBM32 to linear radiance, box-filter floating radiance, then re-encode each level; never average encoded RGBM channels.',
            'logrgb32-k256':'Decode unchanged source RGBM32 to linear radiance; encode level0 and every floating-radiance BOX-filtered mip as LogRGB32 k256 with constant alpha1. Never filter encoded LogRGB values.',
            'specular':'Box-filter linear F0 and GGX alpha (roughness squared), then sqrt alpha to perceptual roughness.',
            'normal':'Box-filter decoded XYZ vectors, renormalize each encoded normal mip; alpha remains one.'}[kind],
        'mipStatistics':mip_stats,'seconds':round(time.monotonic()-started,2)}
    if kind=='logrgb32-k256':
        result.update(radianceScale=scale,radianceOverflow=overflow,scalingRevision=SCALING_REVISION,
            sourceSceneRadiancePeak=scene_peak,encodedRadiancePeak=scene_peak/scale,sceneRadianceRange=RADIANCE_RANGE*scale,
            sceneRadianceReconstruction='((exp2(encodedRGB * log2(8193)) - 1) / 256) * radianceScale; restore each endpoint before mixing')
        result['encodedSource']['radianceScale']=scale
        for row in mip_stats:row['sceneRadianceQuantizationMAE']=row['encodingQuantizationMAE']*scale
    output.with_suffix('.ktx2.json').write_text(json.dumps(result,indent=2)+'\n');return result

def radiance_statistics(reference,decoded,threshold=.005):
    peak=np.max(reference,axis=2);mask=peak>threshold
    if not np.any(mask):return {'pixelsAboveThreshold':0,'blackoutBelow10Percent':0,'blackoutPercent':0.0}
    r=reference[mask];d=decoded[mask];p=peak[mask];error=np.abs(d-r)
    relative=np.max(error,axis=1)/p
    weights=np.array([.2126,.7152,.0722],np.float32);rl=r@weights;dl=d@weights
    chrom_r=r/np.maximum(np.sum(r,axis=1,keepdims=True),1e-9)
    chrom_d=d/np.maximum(np.sum(d,axis=1,keepdims=True),1e-9)
    blackout=np.max(d,axis=1)<.1*p
    return {'pixelsAboveThreshold':int(mask.sum()),'linearAbsoluteMeanRGB':error.mean(axis=0).tolist(),
        'linearAbsoluteMean':float(error.mean()),'linearAbsoluteP99':float(np.percentile(error,99)),
        'linearAbsoluteMax':float(error.max()),'relativeMaxChannelError':dict(zip(
            ['p50','p90','p95','p99','p999','max'],[float(x) for x in np.percentile(relative,[50,90,95,99,99.9,100])])),
        'blackoutBelow10Percent':int(blackout.sum()),'blackoutPercent':float(100*np.mean(blackout)),
        'signedLuminanceMeanBiasPercent':float(100*np.mean((dl-rl)/np.maximum(rl,threshold))),
        'signedRGBMeanBias':(d-r).mean(axis=0).tolist(),
        'chromaticityAbsoluteMeanRGB':np.abs(chrom_d-chrom_r).mean(axis=0).tolist()}

def audit_compressed(source,output,kind,levels=(0,2,4,8)):
    """CPU UASTC->RGBA8 evidence, not a claim of an ASTC/WebGL pixel test."""
    assert kind in ('rgbm32','logrgb32-k256')
    source=Path(source);output=Path(output)
    original=np.asarray(Image.open(source).convert('RGBA')).copy()
    scale=1.;overflow=None
    if kind=='logrgb32-k256':
        manifest=json.loads(output.with_suffix('.ktx2.json').read_text())
        if manifest.get('sourceSha256')!=sha(source) or manifest.get('sha256')!=sha(output) or manifest.get('kind')!=kind:
            raise ValueError('Compressed audit manifest does not bind current source/output/kind.')
        values,scale,overflow=restored_radiance(original,source,manifest.get('radianceScale',1),manifest.get('radianceOverflow'))
    else:values=decode(original,'rgbm32')
    rows=[];level=0
    with tempfile.TemporaryDirectory(prefix='linear-texture-audit-') as temp:
        while True:
            if level in levels:
                decoded_path=Path(temp)/f'{level}.png'
                subprocess.run([str(VALIDATOR),'extract','--transcode','rgba8','--level',str(level),str(output),str(decoded_path)],check=True,capture_output=True,text=True)
                rgba=np.asarray(Image.open(decoded_path).convert('RGBA')).copy()
                assert rgba.shape[:2]==values.shape[:2]
                unpacked=decode(rgba,kind)*scale;assert np.isfinite(unpacked).all()
                packed=encode(values/scale,kind)
                rows.append({'level':level,'dimensions':[values.shape[1],values.shape[0]],
                    'encodingOnly':radiance_statistics(values,decode(packed,kind)*scale),
                    'compressedEndToEnd':radiance_statistics(values,unpacked),
                    'referenceScenePeak':float(values.max()),'decodedScenePeak':float(unpacked.max()),
                    'alphaCompressedRange':[int(rgba[...,3].min()),int(rgba[...,3].max())]})
            if max(values.shape[:2])<=1:break
            values=reduce_float(values);level+=1
    return {'complete':True,'codecRevision':CODEC_REVISION,'kind':kind,'source':str(source),'sourceSha256':sha(source),
        'path':str(output),'sha256':sha(output),'radianceThreshold':.005,'relativeErrorDefinition':'max(abs(decoded-reference) RGB) / max(reference RGB)',
        'radianceScale':scale,'radianceOverflow':overflow,'errorUnits':'actual scene-linear radiance after restoring endpoint scale',
        'decoder':'ktx extract --transcode rgba8','levels':rows,
        'limitations':['ASTC/BC7 GPU decoding and browser appearance require separate WebGL validation.',
            'LogRGB hardware bilinear interpolation is an approximation in encoded space; every authored mip is generated in linear radiance.',
            'Low-resolution sparse UV islands and strong contrast retain lossy block-compression error; alpha1 removes RGBM multiplier collapse, not all quantization.']}

def selfcheck():
    radiance=np.zeros((2,2,3),np.float32);radiance[0,0]=32
    packed=rgbm_encode(radiance);decoded=decode(packed,'rgbm32');mip=reduce_float(decoded)
    assert np.allclose(mip,8)
    wrong=decode(np.rint(packed.astype(np.float32).mean((0,1),keepdims=True)).astype(np.uint8),'rgbm32')
    assert float(np.max(np.abs(wrong-mip)))>5
    n=normalize(np.array([[[1.,0,0],[0,0,1]]],np.float32));m=normalize(reduce_float(n));assert np.allclose(np.linalg.norm(m,axis=2),1)
    values=np.array([0,1e-5,.001,.005,.01,.1,1,8,32],np.float32)
    ramp=np.repeat(values[None,:,None],3,axis=2);logpacked=encode(ramp,'logrgb32-k256');logdecoded=decode(logpacked,'logrgb32-k256')
    assert np.all(logpacked[...,3]==255) and np.isfinite(logdecoded).all()
    assert np.all(np.diff(logdecoded[0,:,0])>=0) and np.all(logdecoded[:,0]==0)
    assert np.allclose(logdecoded[0,-1],32,rtol=1e-5)
    selected=ramp>.005;relative=float(np.max(np.abs(logdecoded[selected]-ramp[selected])/ramp[selected]));assert relative<.035
    logmip=decode(encode(mip,'logrgb32-k256'),'logrgb32-k256');assert np.allclose(logmip,8,rtol=.02)
    wrong_log=decode(np.rint(encode(radiance,'logrgb32-k256').astype(np.float32).mean((0,1),keepdims=True)).astype(np.uint8),'logrgb32-k256')
    assert float(np.max(np.abs(wrong_log-mip)))>5
    spec=np.array([[[.04,.04,.04,.2],[.8,.5,.2,.8]]],np.float32)
    filtered=decode(encode(reduce_float(decode(np.rint(spec*255).astype(np.uint8),'specular')),'specular'),'specular')
    assert np.allclose(filtered[0,0,:3],(.42,.27,.12),atol=.004)
    assert abs(float(filtered[0,0,3])-(.2**2+.8**2)/2)<.004
    with tempfile.TemporaryDirectory(prefix='linear-codec-selfcheck-') as temp:
        source=Path(temp)/'source.png';output=Path(temp)/'test.ktx2'
        test=np.zeros((64,64,3),np.float32)
        for index,v in enumerate([0,.0005,.005,.02,.1,1,8,32]):test[:,index*8:(index+1)*8]=v*np.array([1,.75,.5])
        Image.fromarray(rgbm_encode(test),'RGBA').save(source);original_sha=sha(source)
        manifest=compress(source,output,'logrgb32-k256')
        assert sha(source)==original_sha and manifest['mipLevels']==7
        assert manifest['sourceEncoding']=='RGBM32' and manifest['codecRevision']==CODEC_REVISION
        fallback=Path(manifest['encodedSource']['path']);assert fallback!=source and sha(fallback)==manifest['encodedSource']['sha256']
        fallback_rgba=np.asarray(Image.open(fallback));assert np.all(fallback_rgba[...,3]==255)
        audit=audit_compressed(source,output,'logrgb32-k256',(0,2,4))
        assert all(row['alphaCompressedRange']==[255,255] and row['compressedEndToEnd']['blackoutBelow10Percent']==0 for row in audit['levels'])
        base=audit['levels'][0]['compressedEndToEnd'];assert base['relativeMaxChannelError']['p99']<.12
        # Independent bright patches at opposite PNG edges catch row-flip,
        # channel-stride and scale-order errors rather than only testing shape.
        hdr=test.copy();hdr[:4,:4,0]=139.899;hdr[-4:,:4,2]=64;hdr[:4,16:20,1]=40
        hdr_source=Path(temp)/'hdr.png';hdr_output=Path(temp)/'hdr.ktx2';sidecar=Path(temp)/'outliers.npz'
        Image.fromarray(rgbm_encode(hdr),'RGBA').save(hdr_source);hdr_digest=sha(hdr_source)
        flat=np.flipud(hdr).reshape(-1);indices=np.flatnonzero(flat>32).astype(np.uint32)
        np.savez_compressed(sidecar,indices=indices,values=flat[indices].astype(np.float32),shape=np.array(hdr.shape,dtype=np.int64))
        overflow={'path':str(sidecar),'sha256':sha(sidecar)}
        bake={'sha256':hdr_digest,'hdrOutliers':{**overflow,'count':len(indices),'indexConvention':'flattened bottom-up Blender RGB float buffer'}}
        hdr_source.with_name('hdr-manifest.json').write_text(json.dumps(bake))
        original=np.asarray(Image.open(hdr_source));restored,scale,metadata=restored_radiance(original,hdr_source,8,overflow)
        assert scale==8 and metadata['count']==48
        np.testing.assert_array_equal(restored[:4,:4,0],hdr[:4,:4,0]);np.testing.assert_array_equal(restored[-4:,:4,2],hdr[-4:,:4,2])
        np.testing.assert_array_equal(restored[:4,16:20,1],hdr[:4,16:20,1])
        rejected=0
        for invalid_scale,invalid_overflow in [(4,overflow),(float('nan'),overflow),(0,overflow),(8,{**overflow,'sha256':'0'*64})]:
            try:restored_radiance(original,hdr_source,invalid_scale,invalid_overflow)
            except ValueError:rejected+=1
        assert rejected==4
        scaled_manifest=compress(hdr_source,hdr_output,'logrgb32-k256',radiance_scale=8,radiance_overflow=overflow)
        assert sha(hdr_source)==hdr_digest and scaled_manifest['radianceScale']==8 and scaled_manifest['radianceOverflow']['sha256']==sha(sidecar)
        scaled_audit=audit_compressed(hdr_source,hdr_output,'logrgb32-k256',(0,2,4))
        assert scaled_audit['radianceScale']==8 and scaled_audit['levels'][0]['decodedScenePeak']>130
        assert all(row['alphaCompressedRange']==[255,255] for row in scaled_audit['levels'])
    return {'complete':True,'codecRevision':CODEC_REVISION,'checks':16,'rgbmMipExpectedRadiance':8,
        'correctRadiance':mip.ravel().tolist(),'wrongEncodedAverageRadiance':wrong.ravel().tolist(),
        'normalMipUnitLength':True,'specularFiltersGGXAlpha':True,'logRGBRangeAndMonotonicity':True,
        'logRGBAlphaConstant':True,'logRGBRepresentativeRelativeErrorMax':relative,
        'logRGBMipRadiance':logmip.ravel().tolist(),'wrongLogEncodedAverageRadiance':wrong_log.ravel().tolist(),
        'sourcePreserved':True,'fallbackAndKTXBaseMipMatchEncoding':True,'syntheticKTXMipCount':7,
        'syntheticCompressedAudit':audit,'overflowBottomUpRGBRestored':True,'overflowSourcePreserved':True,
        'overflowInvalidScaleAndHashRejected':rejected,'overflowRestorationAudit':scaled_audit}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source');parser.add_argument('--output');parser.add_argument('--kind',choices=KINDS);parser.add_argument('--selfcheck',action='store_true');parser.add_argument('--audit',action='store_true')
    parser.add_argument('--radiance-scale',type=float,default=1);parser.add_argument('--radiance-overflow');parser.add_argument('--radiance-overflow-sha256');args=parser.parse_args()
    if bool(args.radiance_overflow)!=bool(args.radiance_overflow_sha256):parser.error('Overflow path and SHA256 must be provided together.')
    overflow={'path':args.radiance_overflow,'sha256':args.radiance_overflow_sha256} if args.radiance_overflow else None
    result=selfcheck() if args.selfcheck else audit_compressed(args.source,args.output,args.kind) if args.audit else compress(args.source,args.output,args.kind,radiance_scale=args.radiance_scale,radiance_overflow=overflow)
    print(json.dumps(result,indent=2))
