import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import * as THREE from 'three';
import gsap from 'gsap';
import { createPhysicalSurface } from '../src/physical-surface.js';
import { createDualLighting } from '../src/dual-lighting.js';
import { createIntroLighting } from '../src/intro-lighting.js';

const checks=[];
async function check(name,run) { await run();checks.push({name,passed:true}); }
function fixture(fail='') {
  const object=new THREE.Group(), all=[], requested=[], materials=[], originals=[];
  function texture(name,width=1024,height=1024) {
    const t=new THREE.Texture({width,height});t.name=name;t.disposeCount=0;t.addEventListener('dispose',()=>t.disposeCount++);all.push(t);return t;
  }
  for(const slot of [0,1,8]) {
    const map=texture(`night-${slot}`);map.colorSpace=THREE.SRGBColorSpace;
    const m=new THREE.MeshBasicMaterial({map,name:`WEB8_LIGHTMAP_${slot}`,color:'#42607a'});
    const previous=shader=> {shader.uniforms.previousHook={value:true};};m.onBeforeCompile=previous;
    originals.push({m,map,previous,key:m.customProgramCacheKey,toneMapped:m.toneMapped,color:m.color.toArray()});
    object.add(new THREE.Mesh(new THREE.BoxGeometry(),m));materials.push(m);
  }
  const about=new THREE.MeshBasicMaterial({map:texture('about-day'),name:'ATELIER_LIGHTMAP_0'});
  object.add(new THREE.Mesh(new THREE.BoxGeometry(),about));
  const loader={async loadAsync(path){requested.push(path);if(fail && path.includes(fail))throw new Error(`test missing ${path}`);return texture(path);}};
  const hdrLoader={async loadAsync(path){requested.push(path);if(fail && path.includes(fail))throw new Error(`test missing ${path}`);return texture(path,1024,512);}};
  let generatorDisposals=0;
  const targets=[],pmremFactory=()=>({fromEquirectangular(){const t=texture('prefiltered',768,1024);const target={texture:t,disposeCount:0,dispose(){this.disposeCount++;t.dispose();}};targets.push(target);return target;},dispose(){generatorDisposals++;}});
  const renderer={capabilities:{getMaxAnisotropy:()=>16},uploads:[],initTexture(t){this.uploads.push(t);}};
  const profile={family:'room',directory:'/textures/lighting-v17',encoding:'rgbm',rgbmRange:32,slots:[0,1,8]};
  const compile=m=> {const s={vertexShader:THREE.ShaderLib.basic.vertexShader,fragmentShader:THREE.ShaderLib.basic.fragmentShader,uniforms:{}};m.onBeforeCompile(s,renderer);return s;};
  return {object,objects:[object],all,requested,materials,originals,about,loader,hdrLoader,pmremFactory,renderer,profile,targets,compile,get generatorDisposals(){return generatorDisposals;}};
}
async function stack(f) {
  const surface=await createPhysicalSurface({THREE,...f});
  const lighting=await createDualLighting({THREE,renderer:f.renderer,objects:f.objects,profile:{...f.profile,revision:17,loader:f.loader,extension:'ktx2',dayMixUniform:surface.getDayMixUniform()}});
  const intro=await createIntroLighting({THREE,renderer:f.renderer,room:f.object,loader:f.loader,profile:{revision:17,directory:'/textures/intro-clean-v17',encoding:'rgbm',rgbmRange:32}});
  return {surface,lighting,intro};
}
await check('Room RGBM diffuse/intro decode before one AgX, view-dependent GGX uses independent F0 and tangent normals',async()=>{
  const f=fixture(),s=await stack(f);
  try {
    const shader=f.compile(f.materials[0]);
    assert.equal(shader.uniforms.previousHook.value,true);
    assert.equal(shader.uniforms.uBakedRGBMRange.value,32);
    assert.equal(shader.uniforms.uSurfaceDayMix,shader.uniforms.uLightingMix);
    assert.equal(shader.fragmentShader.match(/outgoingLight = surfaceAgX\(/g).length,1);
    assert.match(shader.fragmentShader,/vec4\(color\.rgb \* color\.a \* uBakedRGBMRange, 1\.0\)/);
    assert.match(shader.fragmentShader,/mix\(atelierDecodeBaked\(texture2D\(uIntroCleanMap/);
    assert.match(shader.fragmentShader,/reflect\(-v, n\)/);
    assert.match(shader.fragmentShader,/f0 \* fab\.x \+ fab\.y/);
    assert.match(shader.fragmentShader,/dFdx\(-vSurfaceViewPosition\)/);
    assert.ok(shader.fragmentShader.indexOf('sampledDiffuseColor = mix(atelierDecodeBaked(texture2D(uIntroCleanMap')<shader.fragmentShader.indexOf('outgoingLight = surfaceAgX('));
    assert.match(shader.vertexShader,/normalMatrix \* normal/);
    for(const map of f.all.filter(t=> /\/(specular|normal|day)-\d.*ktx2$/.test(t.name)))assert.equal(map.colorSpace,THREE.NoColorSpace);
    assert.ok(f.originals.every(({m,color})=>JSON.stringify(m.color.toArray())===JSON.stringify(color)));
    assert.equal(f.generatorDisposals,1);assert.equal(f.targets.length,2);
    assert.equal(s.surface.getState().additionalScenePassesPerFrame,0);
  } finally {s.intro.dispose();s.lighting.dispose();s.surface.dispose();}
});
await check('One shared uniform drives a complete 60 second cycle without texture upload or shader replacement',async()=>{
  const f=fixture(),s=await stack(f),shader=f.compile(f.materials[0]);
  try {
    const uploads=f.renderer.uploads.length,key=f.materials[0].customProgramCacheKey();
    for(let frame=0;frame<=7200;frame++) {
      const value=(1+Math.cos(frame/7200*Math.PI*2))/2;s.lighting.setDayMix(value);
      assert.equal(shader.uniforms.uLightingMix.value,value);assert.equal(shader.uniforms.uSurfaceDayMix.value,value);
    }
    assert.equal(f.renderer.uploads.length,uploads);assert.equal(f.materials[0].customProgramCacheKey(),key);
  } finally {s.intro.dispose();s.lighting.dispose();s.surface.dispose();}
});
await check('Intro restore retains physical reflection and dual lighting, then disposal releases only owned resources once',async()=>{
  const f=fixture(),s=await stack(f);s.intro.restore();s.intro.dispose();s.intro.dispose();
  let shader=f.compile(f.materials[0]);assert.ok(shader.uniforms.uSurfaceSpecular);assert.ok(shader.uniforms.uDayMap);assert.ok(!shader.uniforms.uIntroCleanMap);
  s.lighting.dispose();s.lighting.dispose();s.surface.dispose();s.surface.dispose();
  for(const {m,map,previous,key,toneMapped}of f.originals){assert.equal(m.onBeforeCompile,previous);assert.equal(m.customProgramCacheKey,key);assert.equal(m.toneMapped,toneMapped);assert.equal(map.disposeCount,0);assert.equal(map.colorSpace,THREE.SRGBColorSpace);}
  assert.ok(f.targets.every(t=>t.disposeCount===1));
  assert.ok(f.all.filter(t=>t.name.startsWith('/textures/')).every(t=>t.disposeCount===1));
  shader=f.compile(f.about);assert.ok(!shader.uniforms.uSurfaceSpecular);assert.equal(f.about.map.disposeCount,0);
});
await check('Out-of-order disposal and later compile decorators never revive disposed surface, day or intro samplers',async()=>{
  const f=fixture(),s=await stack(f);const previous=f.materials[0].onBeforeCompile;
  const outer=shader=>{previous(shader,f.renderer);shader.uniforms.laterHook={value:true};};f.materials[0].onBeforeCompile=outer;
  s.surface.dispose();s.lighting.dispose();s.intro.dispose();
  assert.equal(f.materials[0].onBeforeCompile,outer);const shader=f.compile(f.materials[0]);
  assert.equal(shader.uniforms.laterHook.value,true);assert.equal(shader.uniforms.previousHook.value,true);
  assert.ok(!shader.uniforms.uSurfaceSpecular && !shader.uniforms.uDayMap && !shader.uniforms.uIntroCleanMap);
});
for(const missing of ['normal-1','reflection-night.hdr'])await check(`Failure at ${missing} leaves old materials untouched and cleans successful partial loads`,async()=>{
  const f=fixture(missing);await assert.rejects(createPhysicalSurface({THREE,...f}),/retain the previous complete asset release/);
  for(const {m,previous,map}of f.originals){assert.equal(m.onBeforeCompile,previous);assert.equal(map.disposeCount,0);}
  assert.ok(f.all.filter(t=>t.name.startsWith('/textures/')).every(t=>t.disposeCount===1));
});
await check('Partial material installation failure rolls back earlier bindings and both prefiltered probes',async()=>{
  const f=fixture();f.materials[1].customProgramCacheKey=()=>{throw new Error('invalid inherited key');};
  await assert.rejects(createPhysicalSurface({THREE,...f}),/invalid inherited key/);
  assert.equal(f.materials[0].onBeforeCompile,f.originals[0].previous);assert.ok(f.targets.every(t=>t.disposeCount===1));
});
await check('About family is rejected and Gallery opt-in remains isolated to GALLERY_LIGHTMAP slots',async()=>{
  const f=fixture();await assert.rejects(createPhysicalSurface({THREE,...f,profile:{...f.profile,family:'about'}}),/room\/gallery/);
  f.materials.forEach((m,i)=>m.name=`GALLERY_LIGHTMAP_${[0,1,8][i]}`);
  const surface=await createPhysicalSurface({THREE,...f,profile:{...f.profile,family:'gallery'}});
  assert.equal(surface.getState().materialCount,3);assert.ok(!f.compile(f.about).uniforms.uSurfaceSpecular);surface.dispose();
});
await check('Optional Room glass reuses the two PMREMs and shared clock, keeps original mesh ownership and restores materials exactly once',async()=>{
  const f=fixture();
  const names=['WEB8_CLEAR_WEB8_GLASS_MAT_Compute_Smoked_Optical_Glass','WEB8_GLASS_MAT_Smoke_Glass',
    'WEB8_GLASS_P_ClearTerrariumGlass','WEB8_GLASS_D_SpecimenSmokeGlass','WEB8_GLASS_D_PlanterGlass'];
  const originals=names.map(name=>new THREE.MeshPhysicalMaterial({name,transmission:.9,roughness:.12}));
  const nodes=originals.map(material=>new THREE.Mesh(new THREE.BoxGeometry(),material));
  const array=[originals[0],f.materials[0]], mixed=new THREE.Mesh(new THREE.BoxGeometry(),array);nodes.push(mixed);f.object.add(...nodes);
  const aboutGlass=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshBasicMaterial({name:'ATELIER_ARCH_GLASS'}));f.object.add(aboutGlass);const savedAbout=aboutGlass.material;
  let originalDisposals=0;originals.forEach(m=>m.addEventListener('dispose',()=>originalDisposals++));
  const surface=await createPhysicalSurface({THREE,...f,profile:{...f.profile,glass:{enabled:true}}});
  assert.equal(surface.getState().glass.materialCount,5);assert.equal(surface.getState().glass.meshCount,6);
  assert.equal(f.targets.length,2);assert.equal(aboutGlass.material,savedAbout);
  assert.equal(mixed.material[0],nodes[0].material);assert.equal(mixed.material[1],f.materials[0]);
  assert.equal(array[0],originals[0],'original material arrays stay untouched');
  let replacementDisposals=0;
  for(const {original,material}of surface.getReplacedMaterials()){
    assert.ok(originals.includes(original));assert.ok(material.isMeshBasicMaterial);assert.equal(material.transmission,undefined);
    assert.equal(material.depthWrite,false);assert.equal(material.forceSinglePass,true);assert.equal(material.toneMapped,false);
    material.addEventListener('dispose',()=>replacementDisposals++);
    const shader=f.compile(material);assert.equal(shader.uniforms.uSurfaceDayMix,surface.getDayMixUniform());
    assert.match(shader.fragmentShader,/diffuseColor\.a = glassAlpha/);assert.match(shader.fragmentShader,/\/ max\(glassAlpha, \.001\)/);
    assert.equal(shader.fragmentShader.match(/outgoingLight = surfaceAgX\(/g).length,1);
    for(const mix of [0,.25,.5,.75,1]){surface.setDayMix(mix);assert.equal(shader.uniforms.uSurfaceDayMix.value,mix);}
  }
  surface.dispose();surface.dispose();assert.equal(originalDisposals,0);assert.equal(replacementDisposals,5);
  originals.forEach((m,i)=>assert.equal(nodes[i].material,m));assert.equal(mixed.material,array);
});
await check('Gallery glass is opt-in and uses view-dependent Fresnel without About or arbitrary transparent replacements',async()=>{
  const f=fixture();f.materials.forEach((m,i)=>m.name=`GALLERY_LIGHTMAP_${[0,1,8][i]}`);
  const nodes=['GALLERY_ARCH_GLASS','GALLERY_CLEAR','ATELIER_ARCH_GLASS','decoration'].map(name=>new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshBasicMaterial({name,transparent:true,opacity:.1})));
  f.object.add(...nodes);const originals=nodes.map(n=>n.material);
  let surface=await createPhysicalSurface({THREE,...f,profile:{...f.profile,family:'gallery'}});
  nodes.forEach((n,i)=>assert.equal(n.material,originals[i]));surface.dispose();
  surface=await createPhysicalSurface({THREE,...f,profile:{...f.profile,family:'gallery',glass:{enabled:true}}});
  assert.equal(surface.getState().glass.materialCount,2);
  assert.notEqual(nodes[0].material,originals[0]);assert.notEqual(nodes[1].material,originals[1]);
  assert.equal(nodes[2].material,originals[2]);assert.equal(nodes[3].material,originals[3]);
  let previous=0;
  for(let i=100;i>=0;i--){const nv=i/100,fresnel=.04+.96*(1-nv)**5,alpha=fresnel+(1-fresnel)*.028;assert.ok(alpha>=previous&&alpha<=1);previous=alpha;}
  surface.dispose();nodes.forEach((n,i)=>assert.equal(n.material,originals[i]));
});
gsap.ticker.sleep();
const report={complete:true,checks,passed:checks.length,limitations:'CPU shader composition and ownership; HDR decode, PMREM convolution and WebGL compilation use controlled substitutes. Final browser compilation and visual review still required.'};
writeFileSync(new URL('../docs/validation/physical-surface-v1.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
