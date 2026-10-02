"""MCP-bounded receiver partitions; original UVs and full GI scene remain intact.

Partitions change only which mesh receives the bake. Every original other object
remains available to shadow, diffuse and indirect rays. Float buffers, coverage,
and source-bound manifests permit lossless assembly outside Blender.
"""
import hashlib,json,time
from pathlib import Path
import bpy
import numpy as np
import photoreal_materials_v19 as p
import pbr_bake_channels as b

def uv_area(obj):
    m=obj.data;m.calc_loop_triangles();uv=m.uv_layers['BakeUV'].data
    a=np.array([[uv[l].uv[:] for l in t.loops] for t in m.loop_triangles],np.float64)
    return float(np.abs(np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0])).sum()/2)

def partitions(meshes,count):
    groups=[[] for _ in range(count)];areas=[0.]*count
    for obj,area in sorted(((o,uv_area(o)) for o in meshes),key=lambda row:(-row[1],row[0].name)):
        i=min(range(count),key=lambda x:(areas[x],x));groups[i].append(obj);areas[i]+=area
    assert all(groups)
    return groups,areas

def core_mask(meshes,size):
    """Pixel-center coverage in the unchanged original BakeUV; bottom-up rows."""
    mask=np.zeros((size,size),np.uint8)
    for obj in meshes:
        m=obj.data;m.calc_loop_triangles();uv=m.uv_layers['BakeUV'].data
        for tri in m.loop_triangles:
            a,c,d=np.array([uv[l].uv[:] for l in tri.loops],np.float64)*size-.5
            determinant=np.cross(c-a,d-a)
            if abs(determinant)<1e-10:continue
            lo=np.maximum(0,np.ceil(np.minimum(np.minimum(a,c),d)).astype(int))
            hi=np.minimum(size-1,np.floor(np.maximum(np.maximum(a,c),d)).astype(int))
            if np.any(hi<lo):continue
            y,x=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            qx=x-a[0];qy=y-a[1]
            u=(qx*(d-a)[1]-qy*(d-a)[0])/determinant
            v=((c-a)[0]*qy-(c-a)[1]*qx)/determinant
            mask[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=((u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7))
    return mask

def bake_part_current(slot,state,part,count=2,intro=False):
    progress=p.ROOT/f'assets/blender/room-v19-partition-progress-{state}-{slot}-{part}.json'
    call_started=time.monotonic()
    def checkpoint(stage,**extra):
        progress.write_text(json.dumps({'stage':stage,'elapsed':round(time.monotonic()-call_started,2),**extra},indent=2)+'\n')
    checkpoint('begin')
    assert not (p.ROOT/'assets/blender/room-v19-PAUSED').exists()
    p.assert_prepared();assert state in ('day','night') and 0<=part<count
    source=bpy.data.filepath;source_hash=p.sha(source)
    scene=p.configure_intro_current(slot) if intro else p.configure_current(state)
    checkpoint('configured')
    all_meshes=p.atlas_meshes(scene,slot);signature=b.mesh_signature(all_meshes)
    groups,areas=partitions(all_meshes,count);meshes=groups[part];size=p.LIGHT_SIZES[slot]
    checkpoint('partitioned',groups=[[o.name for o in g] for g in groups],areas=areas)
    out=p.ROOT/'assets/blender/linear-intermediates/lighting-v19-partitions'
    out.mkdir(parents=True,exist_ok=True);key=f'{"intro" if intro else state}-{slot}-part{part}of{count}'
    manifest=out/(key+'.json')
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old.get('complete') and old['sourceSha256']==source_hash and p.sha(old['path'])==old['sha256']:return old
    scene.render.engine='CYCLES';scene.cycles.samples=96
    image=b._image(key,size);image.generated_color=(0,0,0,0)
    materials=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name)
    target=b._target(materials,'WEB8_BAKE_TARGET',image);started=time.monotonic()
    checkpoint('image_ready')
    try:
        with b.bake_proxy(scene,meshes,key):
            checkpoint('proxy_ready')
            with b.gpu_job(key):
                checkpoint('gpu_acquired')
                bpy.ops.object.bake(type='COMBINED',pass_filter={'DIRECT','INDIRECT','COLOR','DIFFUSE','EMIT'},uv_layer='BakeUV',margin=max(8,round(size/256)),use_clear=True)
        checkpoint('bake_complete')
        pixels=b.image_pixels(image)
    finally:
        b._restore_targets(target);bpy.data.images.remove(image)
    bake_seconds=round(time.monotonic()-started,2)
    assert b.mesh_signature(all_meshes)==signature and p.sha(source)==source_hash
    assert np.isfinite(pixels).all()
    path=out/(key+'.npy');np.save(path,pixels,allow_pickle=False)
    checkpoint('float_saved')
    core=core_mask(meshes,size);corepath=out/(key+'-coverage.npz');np.savez_compressed(corepath,coverage=core)
    occupied=pixels[...,3]>.5
    record={'complete':True,'slot':slot,'state':state,'cleanIntro':intro,'receiverOnly':intro,
      'part':part,'partCount':count,'samples':96,'dimensions':[size,size],
      'sourceBlend':source,'sourceSha256':source_hash,'meshSignature':signature,
      'path':str(path),'sha256':p.sha(path),'format':'float32 RGBA .npy; Blender bottom-up, unquantized scene-linear',
      'coverage':{'path':str(corepath),'sha256':p.sha(corepath),'method':'Original BakeUV triangle pixel-center rasterization','pixels':int(core.sum())},
      'partitions':[[o.name for o in g] for g in groups],'partitionUvAreas':areas,
      'fullSceneShadowsAndGiRetained':True,'geometryUvNormalsUnchanged':True,'glossyExcluded':True,
      'passFilter':['DIRECT','INDIRECT','COLOR','DIFFUSE','EMIT'],'margin':max(8,round(size/256)),
      'alphaRange':[float(pixels[...,3].min()),float(pixels[...,3].max())],
      'alphaOccupiedPixels':int(occupied.sum()),'corePixelsWithoutAlpha':int(np.sum((core>0)&~occupied)),
      'sourceRadianceMaximum':float(pixels[...,:3].max()),'seconds':bake_seconds,
      'helperPath':str(Path(__file__).resolve()),'helperSha256':p.sha(__file__)}
    manifest.write_text(json.dumps(record,indent=2)+'\n');return record
