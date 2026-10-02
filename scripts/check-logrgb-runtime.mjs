import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import * as THREE from 'three';
import gsap from 'gsap';
import { createPhysicalSurface } from '../src/physical-surface.js';
import { createDualLighting } from '../src/dual-lighting.js';
import { createIntroLighting } from '../src/intro-lighting.js';
import { resolveMaterialRelease } from '../src/material-release.js';

const checks=[];
async function check(name,fn){const details=await fn();checks.push({name,passed:true,...details});}
const radiance=resolveMaterialRelease('?physicalPreview').radiance;
const encode=value=>Math.log2(1+256*value)/Math.log2(8193);
const mix=(a,b,t)=>a.map((v,i)=>v*(1-t)+b[i]*t);
const near=(a,b,tolerance=1e-10)=>{assert.equal(a.length,b.length);a.forEach((v,i)=>assert.ok(Math.abs(v-b[i])<=tolerance,`${v} != ${b[i]}`));};

function fixture({failLoad='',failUpload='',nightRadianceScale={}}={}){
  const room=new THREE.Group(),textures=[],requests=[],materials=new Map(),snapshots=[],targets=[];
  const texture=(name,width=64,height=64)=>{const t=new THREE.Texture({width,height});t.name=name;t.isCompressedTexture=true;t.disposeCount=0;t.addEventListener('dispose',()=>t.disposeCount++);textures.push(t);return t;};
  for(const slot of [0,1,8,'window','about']){
    const map=texture(`original-${slot}`);map.colorSpace=THREE.SRGBColorSpace;
    const name=slot==='window'?'WEB8_WINDOW_CITY':slot==='about'?'ATELIER_LIGHTMAP_0':`WEB8_LIGHTMAP_${slot}`;
    const m=new THREE.MeshBasicMaterial({name,map});m.onBeforeCompile=shader=>{shader.uniforms.inheritedHook={value:true};};
    snapshots.push({material:m,map,compile:m.onBeforeCompile,key:m.customProgramCacheKey,toneMapped:m.toneMapped});
    materials.set(slot,m);room.add(new THREE.Mesh(new THREE.BoxGeometry(),m));
  }
  const loader={async loadAsync(path){requests.push(path);if(failLoad&&path.includes(failLoad))throw new Error(`controlled missing ${path}`);return texture(path);}};
  const hdrLoader={async loadAsync(path){requests.push(path);if(failLoad&&path.includes(failLoad))throw new Error(`controlled missing ${path}`);return texture(path,1024,512);}};
  const renderer={capabilities:{getMaxAnisotropy:()=>16},uploads:[],initTexture(t){this.uploads.push(t);if(failUpload&&t.name.includes(failUpload))throw new Error(`controlled upload ${t.name}`);}};
  const pmremFactory=()=>({fromEquirectangular(){const t=texture('pmrem',768,1024),target={texture:t,disposeCount:0,dispose(){this.disposeCount++;t.dispose();}};targets.push(target);return target;},dispose(){}});
  const compile=slot=>{const shader={vertexShader:THREE.ShaderLib.basic.vertexShader,fragmentShader:THREE.ShaderLib.basic.fragmentShader,uniforms:{}};materials.get(slot).onBeforeCompile(shader,renderer);return shader;};
  const surface=()=>createPhysicalSurface({THREE,renderer,objects:[room],loader,hdrLoader,pmremFactory,
    profile:{family:'room',directory:'/textures/lighting-v17',...radiance,slots:[0,1,8]}});
  const lighting=surface=>createDualLighting({THREE,renderer,objects:[room],profile:{revision:17,directory:'/textures/lighting-v17',extension:'ktx2',loader,
    ...radiance,slots:[0,1,8,'window'],nightRadianceScale,exteriorNightExposure:{},interiorNightReadability:0,dayMixUniform:surface?.getDayMixUniform()}});
  const intro=()=>createIntroLighting({THREE,renderer,room,loader,profile:{revision:17,directory:'/textures/intro-clean-v17',...radiance}});
  const assertUnmodified=()=>{for(const s of snapshots){assert.equal(s.material.onBeforeCompile,s.compile);assert.equal(s.material.customProgramCacheKey,s.key);assert.equal(s.material.toneMapped,s.toneMapped);assert.equal(s.map.colorSpace,THREE.SRGBColorSpace);assert.equal(s.map.disposeCount,0);}};
  const assertOwnedDisposed=()=>{for(const t of textures.filter(t=>!t.name.startsWith('original-')))assert.equal(t.disposeCount,1,`dispose exactly once: ${t.name}`);for(const t of targets)assert.equal(t.disposeCount,1);};
  return {room,textures,requests,materials,snapshots,targets,renderer,loader,compile,surface,lighting,intro,assertUnmodified,assertOwnedDisposed};
}

// Evaluate the scalar form of the *actual composed shader expression*, rather
// than testing a second handwritten decoder. This does not emulate GPU texture
// filtering, floating-point precision or GLSL compilation; browser QA does that.
function actualLogDecoder(shader){
  const expression=shader.fragmentShader.match(/if \(uBakedLogGain > 0\.0\) return vec4\(([^;]+), 1\.0\);/)?.[1];
  assert.ok(expression,'LogRGB branch must exist in composed production shader');
  assert.ok(!expression.includes('color.a'),'LogRGB alpha must not multiply radiance');
  const scalar=new Function('component','uBakedLogGain','exp2','log2',`return ${expression.replaceAll('color.rgb','component')};`);
  return color=>color.slice(0,3).map(c=>scalar(c,shader.uniforms.uBakedLogGain.value,x=>2**x,Math.log2));
}

await check('Actual LogRGB GLSL branch recovers zero through HDR32 and ignores alpha; window and About retain sRGB',async()=>{
  const f=fixture(),surface=await f.surface(),lighting=await f.lighting(surface);
  try{
    const shader=f.compile(0),decode=actualLogDecoder(shader);
    assert.equal(shader.uniforms.uBakedLogGain.value,256);assert.equal(shader.uniforms.uBakedRGBMRange.value,0);
    for(const value of [0,.00001,.001,.005,.01,.1,1,8,32])for(const alpha of [0,.004,.5,1])near(decode([encode(value),encode(value),encode(value),alpha]),[value,value,value],1e-11);
    let previous=-1;for(let code=0;code<=255;code++){const d=decode([code/255,0,0,1])[0];assert.ok(Number.isFinite(d)&&d>=previous);previous=d;}
    assert.ok(Math.abs(previous-32)<1e-11);
    const window=f.compile('window');assert.equal(window.uniforms.uBakedLogGain.value,0);assert.equal(window.uniforms.uBakedRGBMRange.value,0);
    assert.equal(window.uniforms.uDayMap.value.colorSpace,THREE.SRGBColorSpace);assert.equal(f.materials.get('window').map.colorSpace,THREE.SRGBColorSpace);
    assert.equal(shader.uniforms.uDayMap.value.colorSpace,THREE.NoColorSpace);assert.equal(f.materials.get(0).map.colorSpace,THREE.NoColorSpace);
    const about=f.compile('about');assert.ok(!about.uniforms.uBakedLogGain&&!about.uniforms.uSurfaceSpecular);
  }finally{lighting.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();}
});

await check('Day/night decode before linear mixing, with one clock uniform and no reupload at fractional time',async()=>{
  const f=fixture(),surface=await f.surface(),lighting=await f.lighting(surface),shader=f.compile(0),decode=actualLogDecoder(shader);
  try{
    assert.match(shader.fragmentShader,/nightColor = atelierReadableNight\(atelierDecodeBaked\(texture2D\(map, vMapUv\)\)\)/);
    assert.match(shader.fragmentShader,/mix\(nightColor, atelierDecodeBaked\(texture2D\(uDayMap, vMapUv\)\), uLightingMix\)/);
    assert.equal(shader.uniforms.uNightExposure.value,1);assert.equal(shader.uniforms.uNightReadability.value,0);
    assert.equal(shader.uniforms.uLightingMix,shader.uniforms.uSurfaceDayMix);
    const night=[.008,.04,.15],day=[12,4,.5],n=night.map(encode),d=day.map(encode),uploads=f.renderer.uploads.length,key=f.materials.get(0).customProgramCacheKey();
    for(const t of [0,.037,.25,.5,.683,.999,1]){lighting.setDayMix(t);near(mix(decode([...n,1]),decode([...d,1]),shader.uniforms.uLightingMix.value),mix(night,day,t),1e-11);assert.equal(shader.uniforms.uSurfaceDayMix.value,t);}
    const wrong=decode([...mix(n,d,.5),1]),right=mix(night,day,.5);assert.ok(Math.abs(wrong[0]-right[0])>5,'mixing encoded data must be observably wrong for this fixture');
    const current=lighting.getState().dayMix;lighting.setDayMix(NaN);assert.equal(lighting.getState().dayMix,current);
    lighting.setDayMix(-2);assert.equal(shader.uniforms.uLightingMix.value,0);lighting.setDayMix(2);assert.equal(shader.uniforms.uLightingMix.value,1);
    assert.equal(f.renderer.uploads.length,uploads);assert.equal(f.materials.get(0).customProgramCacheKey(),key);
    return {wrongEncodedMidpoint:wrong,correctLinearMidpoint:right};
  }finally{lighting.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();}
});

await check('A normalized HDR night atlas restores x8 before mixing while daylight, clean intro and unscaled slots retain their original energy',async()=>{
  const f=fixture({nightRadianceScale:{0:8}}),surface=await f.surface(),lighting=await f.lighting(surface),intro=await f.intro();
  try{
    const shader=f.compile(0),decode=actualLogDecoder(shader),night=[139.899,64,40],day=[.2,.4,1];
    assert.equal(shader.uniforms.uNightExposure.value,8);assert.equal(shader.uniforms.uNightReadability.value,0);
    assert.match(shader.fragmentShader,/vec4 atelierReadableNight\(vec4 color\)\s*\{\s*color\.rgb \*= uNightExposure;/);
    assert.match(shader.fragmentShader,/else if \(uLightingMix >= 1\.0\)\s*\{\s*sampledDiffuseColor = atelierDecodeBaked\(texture2D\(uDayMap, vMapUv\)\);/);
    assert.match(shader.fragmentShader,/nightColor = atelierReadableNight\(atelierDecodeBaked\(texture2D\(map, vMapUv\)\)\)/);
    const restoredNight=decode([...night.map(v=>encode(v/8)),1]).map(v=>v*shader.uniforms.uNightExposure.value);
    const decodedDay=decode([...day.map(encode),1]);near(restoredNight,night);near(decodedDay,day);
    for(const t of [0,.13,.5,.81,1]){lighting.setDayMix(t);near(mix(restoredNight,decodedDay,shader.uniforms.uLightingMix.value),mix(night,day,t));}
    assert.equal(f.compile(1).uniforms.uNightExposure.value,1);assert.equal(f.compile('window').uniforms.uNightExposure.value,1);
    assert.ok(shader.fragmentShader.includes('mix(atelierDecodeBaked(texture2D(uIntroCleanMap, vMapUv)), sampledDiffuseColor, uIntroShadowMix)'));
    intro.setProgress(0);const clean=[1,.5,.1];near(decode([...clean.map(encode),1]),clean);
    assert.deepEqual(lighting.getState().nightRadianceScale,{0:8});
  }finally{intro.dispose();lighting.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();}
  const invalid=fixture();
  for(const scale of [0,-1,NaN,Infinity])await assert.rejects(createDualLighting({THREE,renderer:invalid.renderer,objects:[invalid.room],
    profile:{...radiance,nightRadianceScale:{0:scale}}}),/LogRGB and positive finite scales/);
  await assert.rejects(createDualLighting({THREE,renderer:invalid.renderer,objects:[invalid.room],profile:{encoding:'rgbm',rgbmRange:32,nightRadianceScale:{0:8}}}),/LogRGB and positive finite scales/);
  assert.equal(invalid.requests.length,0);invalid.assertUnmodified();
  return {sourceNightPeak:139.899,normalizationScale:8,dayEnergyUnchanged:true,invalidScaleAndEncodingCases:5};
});

await check('Clean intro uses the same LogRGB decoder before scene blending and one AgX, then removes only its own layer',async()=>{
  const f=fixture(),surface=await f.surface(),lighting=await f.lighting(surface),intro=await f.intro();
  try{
    lighting.setDayMix(.37);const shader=f.compile(0),decode=actualLogDecoder(shader);
    const introStatement='sampledDiffuseColor = mix(atelierDecodeBaked(texture2D(uIntroCleanMap, vMapUv)), sampledDiffuseColor, uIntroShadowMix);';
    assert.ok(shader.fragmentShader.includes(introStatement));assert.equal(shader.fragmentShader.match(/outgoingLight = surfaceAgX\(/g).length,1);
    assert.ok(shader.fragmentShader.indexOf(introStatement)<shader.fragmentShader.indexOf('outgoingLight = surfaceAgX('));
    assert.equal(shader.uniforms.uIntroCleanMap.value.colorSpace,THREE.NoColorSpace);assert.equal(shader.uniforms.uIntroCleanMap.value.generateMipmaps,false);
    const clean=[.5,.2,.01],scene=mix([.01,.02,.04],[2,4,8],.37);
    for(const t of [0,.1,.5,.83,1]){intro.setProgress(t);near(mix(decode([...clean.map(encode),1]),scene,shader.uniforms.uIntroShadowMix.value),mix(clean,scene,t));}
    intro.setProgress(Infinity);assert.equal(intro.getState().progress,1);intro.setProgress(-.5);assert.equal(intro.getState().progress,0);
    intro.restore();intro.setProgress(0);assert.equal(intro.getState().progress,1);
    const restored=f.compile(0);assert.ok(!restored.uniforms.uIntroCleanMap);assert.ok(restored.uniforms.uDayMap&&restored.uniforms.uSurfaceSpecular);
    assert.equal(restored.uniforms.uBakedLogGain.value,256);assert.equal(restored.uniforms.uLightingMix.value,.37);
  }finally{intro.dispose();intro.dispose();lighting.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();}
});

await check('Invalid LogRGB range/gain are rejected before any texture request or material mutation',async()=>{
  const f=fixture();
  for(const bad of [{radianceRange:16,logGain:256},{radianceRange:32,logGain:64}]){
    const profile={...radiance,...bad};
    await assert.rejects(createPhysicalSurface({THREE,renderer:f.renderer,objects:[f.room],loader:f.loader,profile:{family:'room',directory:'/textures/lighting-v17',...profile}}),/supported linear-radiance/);
    await assert.rejects(createDualLighting({THREE,renderer:f.renderer,objects:[f.room],profile}),/LogRGB range 32 and gain 256/);
    await assert.rejects(createIntroLighting({THREE,renderer:f.renderer,room:f.room,loader:f.loader,profile}),/LogRGB range 32 and gain 256/);
  }
  assert.equal(f.requests.length,0);f.assertUnmodified();
});

await check('Missing physical data disposes parallel partial loads and leaves original materials intact',async()=>{
  const f=fixture({failLoad:'normal-1.ktx2'});await assert.rejects(f.surface(),/controlled missing/);f.assertUnmodified();f.assertOwnedDisposed();
});

await check('Missing LogRGB day map releases its successful siblings; caller can dispose the prior physical layer without leaked ownership',async()=>{
  const f=fixture({failLoad:'/lighting-v17/day-1.ktx2'}),surface=await f.surface();
  await assert.rejects(f.lighting(surface),/Day lighting textures could not load/);
  const shader=f.compile(0);assert.ok(shader.uniforms.uSurfaceSpecular);assert.ok(!shader.uniforms.uDayMap);
  surface.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();
});

await check('A night texture upload failure rolls back partially installed LogRGB day hooks and source color spaces',async()=>{
  const f=fixture({failUpload:'original-1'}),surface=await f.surface();
  await assert.rejects(f.lighting(surface),/controlled upload original-1/);
  for(const slot of [0,1,8,'window']){const shader=f.compile(slot);assert.ok(!shader.uniforms.uDayMap);assert.equal(f.materials.get(slot).map.colorSpace,THREE.SRGBColorSpace);}
  surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();
});

await check('Missing clean receiver releases only intro textures and retains a usable LogRGB day/night material until caller cleanup',async()=>{
  const f=fixture({failLoad:'/intro-clean-v17/day-1.ktx2'}),surface=await f.surface(),lighting=await f.lighting(surface);
  await assert.rejects(f.intro(),/Clean opening textures could not load/);
  const shader=f.compile(0);assert.ok(!shader.uniforms.uIntroCleanMap);assert.equal(shader.uniforms.uBakedLogGain.value,256);assert.ok(shader.uniforms.uDayMap&&shader.uniforms.uSurfaceSpecular);
  lighting.setDayMix(.23);assert.equal(shader.uniforms.uSurfaceDayMix.value,.23);
  lighting.dispose();surface.dispose();f.assertUnmodified();f.assertOwnedDisposed();
});

await check('Disposal through a later wrapper cannot revive deleted LogRGB, intro, or reflection resources',async()=>{
  const f=fixture(),surface=await f.surface(),lighting=await f.lighting(surface),intro=await f.intro(),material=f.materials.get(0),previous=material.onBeforeCompile;
  const outer=shader=>{previous(shader,f.renderer);shader.uniforms.lastDecorator={value:true};};material.onBeforeCompile=outer;
  surface.dispose();lighting.dispose();intro.dispose();const shader=f.compile(0);
  assert.equal(material.onBeforeCompile,outer);assert.ok(shader.uniforms.lastDecorator&&shader.uniforms.inheritedHook);
  assert.ok(!shader.uniforms.uBakedLogGain&&!shader.uniforms.uDayMap&&!shader.uniforms.uIntroCleanMap&&!shader.uniforms.uSurfaceSpecular);
  assert.equal(material.map.colorSpace,THREE.SRGBColorSpace);f.assertOwnedDisposed();
});

gsap.ticker.sleep();
const report={complete:true,passed:checks.length,checks,encoding:radiance,
  scope:'Actual production shader composition and ownership, scalar evaluation extracted from the compiled-hook GLSL expression, controlled network/texture-decode/PMREM substitutes. No GPU, browser or ASTC verification is claimed. About remains unchanged.'};
writeFileSync(new URL('../docs/validation/logrgb-runtime.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
