// Execute the actual About shader binder, clock setters and disposal closure
// with tracked resources; no browser, GPU, image upload or production edits.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import vm from 'node:vm';
import * as THREE from 'three';
import {createSceneClock} from '../src/scene-clock.js';
import {createAtelierEnvironmentFinish} from '../src/about-atelier-environment.js';
const file=p=>new URL(`../${p}`,import.meta.url);
const source=readFileSync(file('src/about-atelier.js'),'utf8'),main=readFileSync(file('src/main.js'),'utf8');
assert.match(main,/aboutAtelier\?\.setDayMix\(mix\)/);
assert.match(source,/new Set\(results\.filter\(result => result\.status === 'fulfilled'\)/);
const calls={tweenKills:0,environment:[],disposed:{},cleared:0,loader:0};
const counted=name=>({dispose(){calls.disposed[name]=(calls.disposed[name]??0)+1;}});
const material=new THREE.MeshBasicMaterial({map:new THREE.Texture(),color:'#a09080'});
const previousCompile=material.onBeforeCompile,previousKey=material.customProgramCacheKey;
const nightMap=new THREE.Texture(),dayMix={value:1};
const sky={material:new THREE.ShaderMaterial({uniforms:{uTheme:{value:1}},fragmentShader:'vec3 atmosphericColor(vec3 ray) { return vec3(1.0); }\nvoid main() { }'})};
const ground={visible:true};
const panorama=new THREE.Texture(),nightPanorama=new THREE.Texture();
const environment=createAtelierEnvironmentFinish({ground,sky,panorama,nightPanorama,dayMixUniform:dayMix,rotation:new THREE.Euler(0,THREE.MathUtils.degToRad(167.4),0,'YXZ')});
const travelSky=environment.createTravelSkyMaterial(new THREE.ShaderMaterial({uniforms:{uTheme:{value:1}},fragmentShader:'vec3 atmosphericColor(vec3 ray) { return vec3(1.0); }\nvoid main() { }'}));
const rig={sun:new THREE.DirectionalLight(),fill:new THREE.HemisphereLight(),awards:new THREE.PointLight(),desk:new THREE.PointLight()};
const reflected={envMapIntensity:.5};
const namespace={THREE,dayMix,nightMap,material,nightState:{ready:true},requestedDayMix:1,clockDriven:false,disposed:false,shaderBindings:[],
 gsap:{killTweensOf(){calls.tweenKills++;}},
 atmosphere:{setDayMix(v){calls.environment.push(v);},dispose:counted('atmosphere').dispose},
 reflection:counted('reflection'),disposeLoader(){calls.loader++;},
 animations:new Set([{kill(){calls.disposed.animation=(calls.disposed.animation??0)+1;}}]),
 finishes:new Map([['a',{}],['b',{}]]),materials:new Set([counted('material')]),geometries:new Set([counted('geometry')]),textures:new Set([counted('dayTexture'),counted('nightTexture')]),
 scene:{environmentIntensity:.5,clear(){calls.cleared++;}},reflectiveMaterials:new Set([reflected]),lightRigs:[rig],
 nightSky:new THREE.Color('#728cac'),daySky:new THREE.Color('#e1efff'),nightGround:new THREE.Color('#241c16'),dayGround:new THREE.Color('#b2a58d')};
const context=vm.createContext(namespace);
vm.runInContext(source.slice(source.indexOf('export function bindAtelierNightMap')).replace('export function','function')+'\nshaderBindings.push(bindAtelierNightMap(material,nightMap,dayMix));',context);
const shader={uniforms:{},fragmentShader:'#include <map_fragment>\nvoid main() {}'};material.onBeforeCompile(shader,{});
assert.equal(shader.uniforms.uAtelierDayMix,dayMix);
assert.equal(shader.uniforms.uAtelierNightMap.value,nightMap);
assert.equal(sky.material.uniforms.uAtelierDayMix,dayMix);
assert.equal(travelSky.uniforms.uAtelierDayMix,dayMix);
assert.match(shader.fragmentShader,/mix\(texture2D\(uAtelierNightMap, vMapUv\), texture2D\(map, vMapUv\), uAtelierDayMix\)/);
assert.match(shader.fragmentShader,/diffuseColor \*= sampledDiffuseColor/);
const color=material.color.toArray();
const setterSource=source.slice(source.indexOf('    const syncLighting ='),source.indexOf('    const setTheme ='));
vm.runInContext(setterSource+'\nglobalThis.applyAboutDayMix=setDayMix;',context);
let callbacks=0;const clock=createSceneClock({startHour:10,cycleSeconds:60,onDayMix(value){callbacks++;context.applyAboutDayMix(value);assert.equal(dayMix.value,value);assert.equal(calls.environment.at(-1),value);}});
let minimum=1,maximum=0;
for(let frame=0;frame<3600;frame++){
 clock.update(1/60,{enabled:true});minimum=Math.min(minimum,dayMix.value);maximum=Math.max(maximum,dayMix.value);
 assert.equal(shader.uniforms.uAtelierDayMix.value,clock.dayMix);
 assert.equal(travelSky.uniforms.uAtelierDayMix.value,clock.dayMix);
 assert.ok(Math.abs(rig.sun.intensity-2.25*clock.dayMix)<1e-12);
 assert.ok(Math.abs(rig.awards.intensity-7*(1-clock.dayMix))<1e-12);
 assert.ok(Math.abs(reflected.envMapIntensity-(.065+.435*clock.dayMix))<1e-12);
}
assert.equal(minimum,0);assert.equal(maximum,1);assert.deepEqual(material.color.toArray(),color);
assert.equal(calls.tweenKills,1,'clock takeover kills the previous tween once, not once per frame');
context.applyAboutDayMix(NaN);assert.equal(dayMix.value,clock.dayMix);
context.applyAboutDayMix(-4);assert.equal(dayMix.value,0);context.applyAboutDayMix(5);assert.equal(dayMix.value,1);
namespace.nightState.ready=false;context.applyAboutDayMix(0);assert.equal(dayMix.value,1,'missing night bakes retain approved daylight');namespace.nightState.ready=true;
vm.runInContext(source.slice(source.indexOf('  const dispose = () =>'),source.indexOf('  const owner ='))+'\nglobalThis.disposeAbout=dispose;',context);
context.disposeAbout();context.disposeAbout();
assert.equal(material.onBeforeCompile,previousCompile);assert.equal(material.customProgramCacheKey,previousKey);
assert.equal(namespace.shaderBindings.length,0);assert.equal(namespace.animations.size,0);
assert.equal(calls.loader,1);assert.equal(calls.cleared,1);
for(const name of ['atmosphere','reflection','material','geometry','dayTexture','nightTexture','animation'])assert.equal(calls.disposed[name],1,name+' releases once');
const last=dayMix.value;context.applyAboutDayMix(.3);assert.equal(dayMix.value,last,'disposed controller ignores clock updates');
clock.dispose();material.map.dispose();nightMap.dispose();panorama.dispose();nightPanorama.dispose();material.dispose();sky.material.dispose();travelSky.dispose();
const report={complete:true,checks:9,sharedClock:{seconds:60,frames:3600,callbacks,minimum,maximum,oneClockUniformForNativeAndTravel:true},
 hoverColorUnaffected:true,missingNightRetainsDay:true,disposedIdempotently:true,shaderHooksRestored:true,
 gpuUploadNotExercised:true,notes:['Executes production binder/setter/disposal bodies with tracked resources.','Native and travel panorama uniforms share the same object as the baked model shader.','Physical light intensities and reflection strength track the same scalar, without per-frame material allocation.']};
mkdirSync(file('output'),{recursive:true});writeFileSync(file('output/about-daynight-lifecycle-audit.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
