import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import * as THREE from 'three';
import gsap from 'gsap';
import { resolveMaterialRelease, PHYSICAL_MATERIALS_DEFAULT } from '../src/material-release.js';
import { createPhysicalSurface } from '../src/physical-surface.js';
import { createDualLighting } from '../src/dual-lighting.js';
import { createGalleryFraming } from '../src/gallery-framing.js';
import { createGalleryGlass } from '../src/gallery-glass.js';
import { FIRST_GALLERY_WORK } from '../src/gallery-exhibit-cover.js';
import { getGalleryExhibit } from '../src/gallery-catalog.js';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';

const checks=[];
async function check(name,fn){const details=await fn();checks.push({name,passed:true,...details});}
await check('The selected release restores Gallery V5 independently while retaining physical Room V20 and Terminal V3',()=>{
  for(const query of ['', '?qa','?sceneHour=22'])assert.equal(resolveMaterialRelease(query).physical,PHYSICAL_MATERIALS_DEFAULT);
  for(const query of ['?physicalPreview=0','?physicalPreview=false','?physicalPreview=OFF']){
    const release=resolveMaterialRelease(query);assert.equal(release.physical,false);
    assert.equal(release.roomRevision,16);assert.equal(release.galleryRevision,'gallery-5');assert.equal(release.terminalRevision,2);assert.equal(release.galleryPhysical,false);
  }
  for(const query of ['?physicalPreview','?qa&physicalPreview=1','?physicalPreview=true']){
    const release=resolveMaterialRelease(query);assert.equal(release.physical,true);
    assert.equal(release.roomRevision,20);assert.equal(release.galleryRevision,'gallery-5');assert.equal(release.terminalRevision,3);assert.equal(release.galleryPhysical,false);
    assert.equal(release.name,'room20-gallery5-terminal3');
    assert.equal(release.galleryModel,'/models/works-gallery-v5-compressed.glb');assert.equal(release.galleryDirectory,'/textures/works-gallery-v5');
    assert.equal(release.aboutApprovedUnchanged,true);assert.ok(Object.isFrozen(release));
    assert.deepEqual(release.radiance,{encoding:'logrgb',radianceRange:32,logGain:256});assert.ok(Object.isFrozen(release.radiance));
  }
  assert.equal(resolveMaterialRelease('',true).physical,true);
  assert.equal(resolveMaterialRelease('?physicalPreview=0',true).physical,false);
});

await check('Actual V5 and V6 GLBs preserve every geometry accessor byte, node transform/hierarchy and 77 interaction IDs',()=>{
  const read=version=>{
    const bytes=readFileSync(new URL(`../public/models/works-gallery-v${version}-compressed.glb`,import.meta.url));
    const jsonLength=bytes.readUInt32LE(12),data=JSON.parse(bytes.subarray(20,20+jsonLength).toString());
    return{bytes,data,bin:bytes.subarray(28+jsonLength)};
  };
  const before=read(5),after=read(6);
  for(const key of ['nodes','meshes','accessors','scenes','scene'])assert.deepEqual(before.data[key],after.data[key]);
  const components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4},componentBytes={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4};
  const accessorBytes=(gltf,accessor)=>{
    assert.ok(!accessor.sparse,'the actual gallery uses dense accessors');
    const view=gltf.data.bufferViews[accessor.bufferView],width=components[accessor.type]*componentBytes[accessor.componentType];
    assert.ok(Number.isFinite(width));
    const start=(view.byteOffset??0)+(accessor.byteOffset??0),stride=view.byteStride??width;
    return Buffer.concat(Array.from({length:accessor.count},(_,index)=>gltf.bin.subarray(start+index*stride,start+index*stride+width)));
  };
  before.data.accessors.forEach((accessor,index)=>assert.deepEqual(accessorBytes(before,accessor),accessorBytes(after,after.data.accessors[index]),`accessor ${index}`));
  const ids=before.data.nodes.flatMap(node=>node.extras?.asset_id?[node.extras.asset_id]:[]);
  assert.equal(new Set(ids).size,77);assert.equal(ids.length,77);
  return{nodes:before.data.nodes.length,meshes:before.data.meshes.length,matchedAccessors:before.data.accessors.length,independentIDs:ids.length,
    v5Sha256:createHash('sha256').update(before.bytes).digest('hex'),v6Sha256:createHash('sha256').update(after.bytes).digest('hex')};
});

// Retain the historical V6 helper/asset coverage without exposing it through
// the user-facing release selector after the requested Gallery lighting revert.
const archivedV6=Object.freeze({...resolveMaterialRelease('?physicalPreview'),name:'archived-room18-gallery6-terminal3',galleryPhysical:true,
  galleryModel:'/models/works-gallery-v6-compressed.glb',galleryRevision:'gallery-6',galleryDirectory:'/textures/works-gallery-v6'});

async function fixture(queryOrRelease,fail=''){
  // Execute the production factory with the actual selected GLB, including V6
  // embedded LogRGB KTX bytes. Texture decode and GPU work alone are mocked.
  // Network image decode, cover Canvas rendering, PMREM GPU and environment
  // rendering are mocked; cover ownership/readiness are checked explicitly.
  const source=readFileSync(new URL('../src/works-gallery.js',import.meta.url),'utf8');
  const release=typeof queryOrRelease==='string'?resolveMaterialRelease(queryOrRelease):queryOrRelease;
  const gltf=await parseModelForCPU(`public${release.galleryModel}`);
  if(release.galleryPhysical??release.physical){
    const binOffset=20+gltf.bytes.readUInt32LE(12)+8,sha=b=>createHash('sha256').update(b).digest('hex');
    assert.equal(gltf.data.asset.extras.export_kind,'works_gallery_physical_v6');
    const days=gltf.data.asset.extras.day_lightmaps;assert.equal(days.length,4);
    for(const day of days){
      assert.equal(day.encoding,'LogRGB32 k256 alpha1');
      assert.equal(day.uri,`../textures/works-gallery-v6/day-${day.atlas}.ktx2`);
      assert.equal(day.png_fallback,`../textures/works-gallery-v6/day-${day.atlas}.logrgb.png`);
      const prefix='../public/textures/works-gallery-v6/';
      assert.equal(sha(readFileSync(new URL(`${prefix}day-${day.atlas}.ktx2`,import.meta.url))),day.sha256);
      assert.equal(sha(readFileSync(new URL(`${prefix}day-${day.atlas}.logrgb.png`,import.meta.url))),day.png_sha256);
    }
    const images=gltf.data.images.filter(image=>image.extras?.state==='night');assert.equal(images.length,4);
    for(const image of images){
      assert.equal(image.extras.encoding,'LogRGB32 k256 alpha1');
      const view=gltf.data.bufferViews[image.bufferView],bytes=gltf.bytes.subarray(binOffset+(view.byteOffset??0),binOffset+(view.byteOffset??0)+view.byteLength);
      const external=readFileSync(new URL(`../public/textures/works-gallery-v6/night-${image.extras.atlas}.ktx2`,import.meta.url));
      assert.equal(sha(bytes),sha(external));assert.equal(sha(bytes),image.extras.sha256);
    }
  }
  const modelResources=new Set();gltf.scene.traverse(n=>{if(n.isMesh)for(const r of [n.geometry,...[].concat(n.material),...[].concat(n.material).flatMap(m=>Object.values(m).filter(v=>v?.isTexture))])modelResources.add(r);});
  const disposals=new Map([...modelResources].map(r=>[r,0]));for(const r of modelResources){if(r.isTexture)r.image={width:4096,height:4096};r.addEventListener('dispose',()=>disposals.set(r,disposals.get(r)+1));}
  const requests=[],owned=[],calls={legacyGlass:0,pmrem:0,loaderDisposed:0,exhibitCover:0,coverReadyReads:0,coverDisposed:0},theme={value:1};
  const texture=(path,w=1024,h=1024)=>{const t=new THREE.Texture({width:w,height:h});t.name=path;t.disposeCount=0;t.addEventListener('dispose',()=>t.disposeCount++);owned.push(t);return t;};
  class Loader{
    setTranscoderPath(){return this;}setWorkerLimit(){return this;}detectSupport(){return this;}
    async loadAsync(path){this.transcoderPending??=Promise.resolve();requests.push(path);if(fail&&path.includes(fail))throw new Error('controlled missing '+path);return texture(path);}
    dispose(){calls.loaderDisposed++;}
  }
  class ModelLoader{
    setKTX2Loader(loader){this.textureLoader=loader;return this;}
    async loadAsync(path){
      requests.push(path);
      if(fail==='model-uninitialized')throw new Error('controlled model failure before decoder init');
      this.textureLoader.transcoderPending=Promise.resolve();
      if(fail==='model-initialized')throw new Error('controlled model failure after decoder init');
      return gltf;
    }
  }
  const renderer={capabilities:{getMaxAnisotropy:()=>8},initTexture(){}};
  const factory=vm.runInNewContext(source.replace(/^import .*;\n/gm,'').replace('export async function createWorksGallery','async function createWorksGallery')+'\ncreateWorksGallery;',{
    THREE,gsap,resolveMaterialRelease,FIRST_GALLERY_WORK,getGalleryExhibit,KTX2Loader:Loader,GLTFLoader:ModelLoader,createDualLighting,createGalleryFraming,
    createGalleryExhibitCover:args=>{
      calls.exhibitCover++;
      assert.equal(args.model,gltf.scene);assert.equal(args.renderer,renderer);
      let exhibit;
      args.model.traverse(node=>{if(node.userData.asset_id==='gallery.work.01.art')exhibit=node;});
      assert.ok(exhibit,'cover is installed on the actual first art asset');
      const meshes=[];exhibit.traverse(node=>{if(node.isMesh)meshes.push(node);});
      assert.ok(meshes.length>0,'the cover target retains real GLB geometry');
      let status='loading';
      return {
        get ready(){calls.coverReadyReads++;status='ready';return Promise.resolve(true);},
        getState:()=>({status,assetId:exhibit.userData.asset_id,title:FIRST_GALLERY_WORK.title,mockCanvas:true}),
        dispose(){calls.coverDisposed++;status='disposed';},
      };
    },
    createPhysicalSurface:args=>createPhysicalSurface({...args,hdrLoader:{async loadAsync(path){requests.push(path);if(fail&&path.includes(fail))throw new Error('controlled missing '+path);return texture(path,1024,512);}},
      pmremFactory:()=>({fromEquirectangular(){calls.pmrem++;const t=texture('pmrem',768,1024);return{texture:t,dispose(){t.dispose();}};},dispose(){}})}),
    createExteriorAtmosphere:()=>({sky:new THREE.Mesh(),setDayMix(value){theme.value=value;},setTheme(day){theme.value=day?1:0;},update(){},dispose(){}}),
    createGalleryFloorFinish:async()=>({getThemeUniform:()=>theme,getState:()=>({mockGPU:true}),dispose(){}}),
    createGalleryGlass:async args=>{calls.legacyGlass++;return createGalleryGlass(args);},
  });
  return {run:()=>factory({renderer,isDay:true,reducedMotion:true,materialRelease:release}),requests,owned,calls,disposals,renderer};
}
await check('Archived V6 Gallery factory still loads one physical family and shares fractional day/night without changing 77 IDs',async()=>{
  const f=await fixture(archivedV6),gallery=await f.run();
  const state=gallery.getState();assert.equal(state.assetCount,77);assert.equal(state.lighting.revision,'gallery-6');
  assert.equal(f.calls.exhibitCover,1);assert.equal(f.calls.coverReadyReads,1);assert.equal(state.firstExhibit.status,'ready');
  assert.equal(state.firstExhibit.assetId,'gallery.work.01.art');assert.equal(state.firstExhibit.title,FIRST_GALLERY_WORK.title);
  assert.equal(state.lighting.encoding,'logrgb');assert.equal(state.lighting.rgbmRange,0);assert.equal(state.lighting.radianceRange,32);assert.equal(state.lighting.logGain,256);assert.equal(state.lighting.interiorNightReadability,0);
  assert.equal(state.physicalSurface.encoding,'logrgb');assert.equal(state.physicalSurface.radianceRange,32);assert.equal(state.physicalSurface.logGain,256);
  assert.equal(state.glass.materialCount,2);assert.equal(f.calls.legacyGlass,0);assert.equal(f.calls.pmrem,2);
  assert.equal(f.requests[0],'/models/works-gallery-v6-compressed.glb');
  assert.ok(f.requests.filter(p=>p.includes('/textures/')).every(p=>p.startsWith('/textures/works-gallery-v6/')));
  const shaders=[];gallery.model.traverse(node=>{if(!node.isMesh)return;for(const material of [].concat(node.material)){
    if(!/^GALLERY_LIGHTMAP_/.test(material.name))continue;
    const shader={vertexShader:THREE.ShaderLib.basic.vertexShader,fragmentShader:THREE.ShaderLib.basic.fragmentShader,uniforms:{}};
    material.onBeforeCompile(shader,f.renderer);shaders.push(shader);
    assert.equal(shader.uniforms.uBakedLogGain.value,256);assert.equal(shader.uniforms.uBakedRGBMRange.value,0);
    assert.equal(material.map.colorSpace,THREE.NoColorSpace);assert.equal(shader.uniforms.uDayMap.value.colorSpace,THREE.NoColorSpace);
    assert.equal(shader.uniforms.uSurfaceDayMix,shader.uniforms.uLightingMix);
    assert.match(shader.fragmentShader,/mix\(nightColor, atelierDecodeBaked\(texture2D\(uDayMap/);
    assert.equal(shader.fragmentShader.match(/outgoingLight = surfaceAgX\(/g).length,1);
  }});assert.ok(shaders.length>=4);
  for(const mix of [0,.037,.37,.683,1]){gallery.setDayMix(mix);const s=gallery.getState();assert.equal(s.lighting.dayMix,mix);assert.equal(s.physicalSurface.dayMix,mix);for(const shader of shaders)assert.equal(shader.uniforms.uLightingMix.value,mix);}
  const bounds=gallery.pose(16/9,35);assert.ok(bounds.position.toArray().every(Number.isFinite));
  assert.equal(f.calls.loaderDisposed,1,'ready releases initialized decoder');
  gallery.dispose();gallery.dispose();assert.equal(f.calls.coverDisposed,1,'gallery owns and disposes its cover exactly once');assert.equal(f.calls.loaderDisposed,1,'gallery disposal must not decrement active decoder count twice');assert.ok([...f.disposals.values()].every(n=>n===1));
  assert.ok(f.owned.every(t=>t.disposeCount===1));assert.equal(gallery.getState().ready,false);
  return {materialCount:state.physicalSurface.materialCount,glassMaterialCount:state.glass.materialCount,independentIDs:state.assetCount};
});
await check('Current and fallback releases use the same actual V5 sRGB lighting, original glass, 77 IDs and fractional theme path',async()=>{
  const observed=[];
  for(const query of ['?qa','?physicalPreview=0']){
    const f=await fixture(query),gallery=await f.run(),state=gallery.getState();
    assert.equal(f.calls.exhibitCover,1);assert.equal(f.calls.coverReadyReads,1);assert.equal(state.firstExhibit.status,'ready');
    assert.equal(state.firstExhibit.assetId,'gallery.work.01.art');assert.equal(state.firstExhibit.title,FIRST_GALLERY_WORK.title);
    const art=gallery.components.get('gallery.work.01.art');assert.ok(art);
    assert.equal(gallery.activate(art).station,1);assert.equal(gallery.callout(art).label,FIRST_GALLERY_WORK.title);
    assert.equal(gallery.callout(art).action,`${FIRST_GALLERY_WORK.category} · 点击观看`);
    assert.equal(state.lighting.revision,'gallery-5');assert.equal(state.lighting.encoding,'srgb');assert.equal(state.physicalSurface,null);assert.equal(state.physicalMaterials,false);
    assert.equal(state.assetCount,77);assert.equal(state.glass.reflection,'local Blender day/night captures with box projection');
    assert.equal(f.calls.legacyGlass,1);assert.equal(f.calls.pmrem,0);assert.equal(f.requests[0],'/models/works-gallery-v5-compressed.glb');
    assert.ok(!f.requests.some(p=>/specular-|normal-|\.hdr$/.test(p)));
    assert.ok(f.requests.includes('/textures/works-gallery-v5/reflection-day.ktx2'));assert.ok(f.requests.includes('/textures/works-gallery-v5/reflection-night.ktx2'));
    const shaders=[],glasses=new Set();
    gallery.model.traverse(node=>{if(!node.isMesh)return;for(const material of [].concat(node.material)){
      if(material.name==='GALLERY_ARCH_GLASS · local reflections')glasses.add(material);
      if(!/^GALLERY_LIGHTMAP_/.test(material.name))continue;
      const shader={vertexShader:THREE.ShaderLib.basic.vertexShader,fragmentShader:THREE.ShaderLib.basic.fragmentShader,uniforms:{}};
      material.onBeforeCompile(shader,f.renderer);shaders.push(shader);
      assert.equal(material.map.colorSpace,THREE.SRGBColorSpace);assert.equal(shader.uniforms.uDayMap.value.colorSpace,THREE.SRGBColorSpace);
      assert.equal(shader.uniforms.uBakedLogGain.value,0);assert.equal(shader.uniforms.uBakedRGBMRange.value,0);
      assert.equal(shader.uniforms.uNightExposure.value,1);assert.equal(shader.uniforms.uNightReadability.value,0);
      assert.ok(!shader.uniforms.uSurfaceSpecular);assert.ok(!shader.fragmentShader.includes('surfaceAgX'));
    }});
    assert.ok(shaders.length>=4);assert.equal(glasses.size,1);
    for(const material of glasses){assert.equal(material.toneMapped,false);assert.equal(material.uniforms.uReflectionDay.value.colorSpace,THREE.SRGBColorSpace);assert.equal(material.uniforms.uReflectionNight.value.colorSpace,THREE.SRGBColorSpace);}
    for(const mix of [0,.037,.37,.683,1]){
      gallery.setDayMix(mix);assert.equal(gallery.getState().lighting.dayMix,mix);
      for(const shader of shaders)assert.equal(shader.uniforms.uLightingMix.value,mix);
      for(const material of glasses)assert.equal(material.uniforms.uTheme.value,mix);
    }
    observed.push({requests:[...f.requests],ids:[...gallery.components.keys()].sort(),shaders:shaders.map(shader=>shader.fragmentShader)});
    gallery.dispose();gallery.dispose();assert.equal(f.calls.coverDisposed,1);assert.equal(gallery.getState().firstExhibit.status,'disposed');assert.equal(f.calls.loaderDisposed,1);assert.ok([...f.disposals.values()].every(n=>n===1));assert.ok(f.owned.every(texture=>texture.disposeCount===1));
  }
  assert.deepEqual(observed[0],observed[1],'current physical room release must not alter the restored Gallery lighting path');
  return{independentIDs:77,galleryRevision:'gallery-5',encoding:'srgb',glass:'original local day/night reflections',currentAndFallbackGalleryPathsIdentical:true};
});
for(const missing of ['normal-1','day-2'])await check(`Gallery failure at ${missing} releases both imported and new resources without falling back to mixed encodings`,async()=>{
  const f=await fixture(archivedV6,missing);await assert.rejects(f.run(),/controlled missing/);
  assert.ok([...f.disposals.values()].every(n=>n===1));assert.ok(f.owned.every(t=>t.disposeCount===1));
  assert.equal(f.calls.legacyGlass,0);assert.equal(f.calls.loaderDisposed,1);
  assert.equal(f.calls.exhibitCover,missing==='normal-1'?0:1);assert.equal(f.calls.coverDisposed,f.calls.exhibitCover);assert.equal(f.calls.coverReadyReads,0);
});
for(const missing of ['day-2','reflection-night.ktx2'])await check(`Restored V5 failure at ${missing} releases partial resources without enabling the physical Gallery path`,async()=>{
  const f=await fixture('?qa',missing);await assert.rejects(f.run(),/could not load|controlled missing/);
  assert.ok([...f.disposals.values()].every(n=>n===1));assert.ok(f.owned.every(texture=>texture.disposeCount===1));
  assert.equal(f.calls.pmrem,0);assert.equal(f.calls.loaderDisposed,1);
  assert.equal(f.calls.exhibitCover,1);assert.equal(f.calls.coverDisposed,1);assert.equal(f.calls.coverReadyReads,0);
});
for(const [failure,expectedDisposals]of [['model-uninitialized',0],['model-initialized',1]])await check(`Model failure ${failure} releases exactly the decoder ownership that was acquired`,async()=>{
  const f=await fixture('?physicalPreview',failure);await assert.rejects(f.run(),/controlled model failure/);
  assert.equal(f.calls.loaderDisposed,expectedDisposals);assert.equal(f.owned.length,0);assert.equal(f.calls.legacyGlass,0);
  assert.equal(f.calls.exhibitCover,0);assert.equal(f.calls.coverDisposed,0);assert.equal(f.calls.coverReadyReads,0);
  assert.ok([...f.disposals.values()].every(n=>n===0),'factory never acquired the mocked model on load failure');
});
gsap.ticker.sleep();
const report={complete:true,passed:checks.length,checks,scope:'CPU production Gallery factory with actual current V5 and archived V6 GLBs, actual V5 glass helper, V6 embedded LogRGB KTX hashes, real 77-ID geometry and composed shader uniforms. Current and fallback V5 requests/IDs/shaders match; physical Room20/Terminal3 selection remains independent. First-exhibit cover installation, readiness, station-1 callout/activation and disposal are checked with an explicit Canvas substitute. Explicit texture-decode/GPU substitutes; cover rendering, WebGL compilation and restored appearance require separate main-page browser verification. About is excluded.'};
writeFileSync(new URL('../docs/validation/material-preview-integration.json',import.meta.url),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
