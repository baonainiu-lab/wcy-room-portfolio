import assert from 'node:assert/strict';
import { writeFileSync, readFileSync } from 'node:fs';
import * as THREE from 'three';
import { createTerminalToneMapping } from '../src/terminal-tone.js';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';

const checks=[];
async function check(name,fn){checks.push({name,passed:true,...await fn()});}
const snapshot=m=>({color:m.color.toArray(),emissive:m.emissive.toArray(),emissiveIntensity:m.emissiveIntensity,
  roughness:m.roughness,metalness:m.metalness,clearcoat:m.clearcoat,clearcoatRoughness:m.clearcoatRoughness,
  specularIntensity:m.specularIntensity,ior:m.ior,envMap:m.envMap,envMapIntensity:m.envMapIntensity,
  map:m.map,normalMap:m.normalMap,metalnessMap:m.metalnessMap,roughnessMap:m.roughnessMap,emissiveMap:m.emissiveMap});
async function fixture(){
  const gltf=await parseModelForCPU('public/models/welcome-terminal-v3-compressed.glb');
  const materials=new Set();gltf.scene.traverse(n=>{if(n.isMesh)[].concat(n.material).forEach(m=>materials.add(m));});
  const original=new Map([...materials].map(m=>[m,{snapshot:snapshot(m),compile:m.onBeforeCompile,key:m.customProgramCacheKey,toneMapped:m.toneMapped}]));
  const compile=m=>{const shader={vertexShader:THREE.ShaderLib.physical.vertexShader,fragmentShader:THREE.ShaderLib.physical.fragmentShader,uniforms:{}};m.onBeforeCompile(shader,{});return shader;};
  return{model:gltf.scene,materials,original,compile};
}
await check('Actual V3 native PBR keeps all textures and BRDF values, with one AgX after lighting and before sRGB',async()=>{
  const f=await fixture(),tone=createTerminalToneMapping({THREE,model:f.model});
  assert.equal(tone.getState().materialCount,7);assert.equal(tone.getState().exposure,1);
  for(const material of f.materials){
    assert.deepEqual(snapshot(material),f.original.get(material).snapshot);assert.equal(material.toneMapped,false);
    const shader=f.compile(material),code=shader.fragmentShader;
    assert.equal(shader.uniforms.uTerminalExposure.value,1);
    assert.equal(code.match(/gl_FragColor\.rgb = terminalAgX\(/g).length,1);
    assert.ok(!code.includes('#include <tonemapping_fragment>'));
    assert.ok(code.indexOf('#include <lights_fragment_end>')<code.indexOf('gl_FragColor.rgb = terminalAgX('));
    assert.ok(code.indexOf('gl_FragColor.rgb = terminalAgX(')<code.indexOf('#include <colorspace_fragment>'));
    assert.ok(code.includes('#include <opaque_fragment>'),'native alpha/output assignment remains');
    assert.ok(!code.includes('gl_FragColor.a ='),'tone mapping does not rewrite alpha');
  }
  tone.dispose();tone.dispose();
  for(const material of f.materials){const old=f.original.get(material);assert.equal(material.onBeforeCompile,old.compile);assert.equal(material.customProgramCacheKey,old.key);assert.equal(material.toneMapped,old.toneMapped);assert.deepEqual(snapshot(material),old.snapshot);}
});
await check('About and other scene materials are excluded, with no renderer or light changes',async()=>{
  const f=await fixture(),about=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshPhysicalMaterial({name:'ATELIER_ARCH_GLASS',transmission:.9}));
  const room=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshBasicMaterial({name:'WEB8_LIGHTMAP_0'}));
  f.model.add(about,room);const oldAbout=about.material.onBeforeCompile,oldRoom=room.material.onBeforeCompile;
  const light=new THREE.DirectionalLight(0xffffff,3.1),fill=new THREE.HemisphereLight(0xffffff,0x687888,2.1);f.model.add(light,fill);
  const tone=createTerminalToneMapping({THREE,model:f.model});
  assert.equal(about.material.onBeforeCompile,oldAbout);assert.equal(room.material.onBeforeCompile,oldRoom);
  assert.equal(light.intensity,3.1);assert.equal(fill.intensity,2.1);assert.equal(tone.getState().additionalPassesPerFrame,0);tone.dispose();
});
await check('Outer decorators survive disposal and cannot reactivate a disposed terminal AgX hook',async()=>{
  const f=await fixture(),material=[...f.materials][0];
  material.onBeforeCompile=shader=>{shader.uniforms.original={value:1};};
  const tone=createTerminalToneMapping({THREE,model:f.model}),previous=material.onBeforeCompile;
  const outer=shader=>{previous.call(material,shader,{});shader.uniforms.outer={value:2};};material.onBeforeCompile=outer;
  assert.throws(()=>createTerminalToneMapping({THREE,model:f.model}),/already installed/);
  tone.dispose();assert.equal(material.onBeforeCompile,outer);
  const shader=f.compile(material);assert.equal(shader.uniforms.original.value,1);assert.equal(shader.uniforms.outer.value,2);
  assert.ok(!shader.uniforms.uTerminalExposure);assert.ok(shader.fragmentShader.includes('#include <tonemapping_fragment>'));
});
await check('Failed partial installation restores earlier materials without disposing model resources',async()=>{
  const f=await fixture(),list=[...f.materials],first=list[0],old=f.original.get(first);
  let disposals=0;for(const material of list)material.addEventListener('dispose',()=>disposals++);
  list[1].customProgramCacheKey=()=>{throw new Error('invalid inherited key');};
  assert.throws(()=>createTerminalToneMapping({THREE,model:f.model}),/invalid inherited key/);
  assert.equal(first.onBeforeCompile,old.compile);assert.equal(first.toneMapped,old.toneMapped);assert.equal(disposals,0);
});
await check('AgX retains increasing highlight distinctions that unmapped sRGB output clips to white; exposure remains one',()=>{
  const matrix=values=>new THREE.Matrix3().fromArray(values);
  const to2020=matrix([.6274,.0691,.0164,.3293,.9195,.088,.0433,.0113,.8956]);
  const inset=matrix([.856627153315983,.137318972929847,.11189821299995,.0951212405381588,.761241990602591,.0767994186031903,.0482516061458583,.101439036467562,.811302368396859]);
  const outset=matrix([1.1271005818144368,-.1413297634984383,-.14132976349843826,-.11060664309660323,1.157823702216272,-.11060664309660294,-.016493938717834573,-.016493938717834257,1.2519364065950405]);
  const toSRGB=matrix([1.6605,-.1246,-.0182,-.5876,1.1329,-.1006,-.0728,-.0083,1.1187]);
  const contrast=x=>15.5*x**6-40.14*x**5+31.96*x**4-6.868*x**3+.4298*x*x+.1191*x-.00232;
  const agx=value=>{
    const v=new THREE.Vector3(value,value,value).applyMatrix3(to2020).applyMatrix3(inset);
    v.fromArray(v.toArray().map(x=>contrast(THREE.MathUtils.clamp((Math.log2(Math.max(x,1e-10))+12.47393)/16.499999,0,1))));
    v.applyMatrix3(outset);v.fromArray(v.toArray().map(x=>Math.max(x,0)**2.2));v.applyMatrix3(toSRGB);
    return new THREE.Color(...v.toArray().map(x=>THREE.MathUtils.clamp(x,0,1))).convertLinearToSRGB().r;
  };
  const samples=[0,.18,1,4,8,16].map(linear=>({linear,unmappedDisplay:Math.min(1,new THREE.Color(linear,linear,linear).convertLinearToSRGB().r),agxDisplay:agx(linear)}));
  for(let i=1;i<samples.length;i++)assert.ok(samples[i].agxDisplay>samples[i-1].agxDisplay);
  assert.ok(samples[2].agxDisplay<samples[3].agxDisplay && samples[3].agxDisplay<samples[4].agxDisplay);
  assert.equal(samples[3].unmappedDisplay,1);assert.equal(samples[4].unmappedDisplay,1);
  return{samples,method:'CPU evaluation of the installed Three AgX equations for neutral radiance, not a measured framebuffer result'};
});
const residentSource=readFileSync(new URL('../src/resident-terminal.js',import.meta.url),'utf8');
assert.match(residentSource,/fill\.intensity = 2\.1 \* progress; sun\.intensity = 3\.1 \* progress;/);
const report={complete:true,passed:checks.length,checks,
  existingLightAnalysis:{welcome:{hemisphere:2.1,directional:3.1,environmentIntensity:.9},docked:{hemisphere:0,directional:0,environmentDay:1.1,environmentNight:.3},
    explanation:'Native PBR can produce radiance above 1 from existing lights and RoomEnvironment reflections. NoToneMapping only applies sRGB conversion and clips that range in display. Local AgX compresses that radiance without reducing lights or exposure.'},
  limitations:'CPU shader composition and real GLB material preservation only; webpage WebGL compilation and visual acceptance are still pending.'};
writeFileSync(new URL('../docs/validation/terminal-tone-v1.json',import.meta.url),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
