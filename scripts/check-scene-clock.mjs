import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { compile } from 'sass';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { createSceneClock, daylightAtHour, SCENE_DAY_SECONDS } from '../src/scene-clock.js';
import { createSceneTimeTheme } from '../src/scene-time-theme.js';
import { createDualLighting } from '../src/dual-lighting.js';
import { createExteriorAtmosphere } from '../src/exterior-atmosphere.js';
import { createResidentTerminal } from '../src/resident-terminal.js';
import { createLiveRoomSurfaces } from '../src/live-room-surfaces.js';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';

const checks = [], close = (a,b,e=1e-8) => assert.ok(Math.abs(a-b)<e, `${a} != ${b}`);
async function check(name,run) { try { checks.push({name,passed:true,...await run()}); } catch(e) { checks.push({name,passed:false,error:e.stack}); } }
await check('a complete real-time cycle visits day, dusk, night and dawn, then returns continuously', () => {
  let samples = 0, last = 1, maximumStep = 0;
  const clock = createSceneClock({onDayMix: mix => {maximumStep=Math.max(maximumStep,Math.abs(mix-last));last=mix;samples++;}});
  assert.equal(SCENE_DAY_SECONDS,60);assert.equal(clock.getState().cycleSeconds,60);assert.equal(clock.getState().transitionSeconds,15);
  const checkpoints = new Map();
  for(let i=1;i<=7200;i++) { clock.update(1/120); if(i%600===0) checkpoints.set(i/120, clock.getState()); }
  close(clock.hour,10,1e-8); close(clock.dayMix,1);
  close(checkpoints.get(20).hour,18,1e-8); close(checkpoints.get(30).hour,22,1e-8);
  close(checkpoints.get(30).dayMix,0); close(checkpoints.get(55).hour,8,1e-8);
  assert.ok(maximumStep<.0014); assert.ok(samples>3500);
  return {seconds:60,samples,maximumStep,sunsetSeconds:15,sunriseSeconds:15};
});
await check('pauses do not accumulate time and reduced-motion stays at daylight 10:00', () => {
  const clock=createSceneClock();clock.update(1/60);const state=clock.getState();
  for(let i=0;i<600;i++) clock.update(1/60,{enabled:false});
  close(clock.hour,state.hour);clock.update(1/60);close(clock.hour,state.hour+.4/60);
  clock.update(500);close(clock.hour,state.hour+.4/60+.1);
  for(const invalid of [NaN,Infinity,-1]) {const before=clock.hour;clock.update(invalid);close(clock.hour,before);}
  clock.dispose();const final=clock.hour;clock.update(1);close(clock.hour,final);
  const reduced=createSceneClock({reducedMotion:true,startHour:22});for(let i=0;i<14400;i++) reduced.update(1/60);
  close(reduced.hour,10);close(reduced.dayMix,1);assert.equal(reduced.getState().paused,true);
});
await check('every opening including old night QA links starts at 10:00; only completed entry starts the automatic cycle', () => {
  const main=readFileSync('src/main.js','utf8');
  const initialization=main.match(/sceneClock = createSceneClock\(\{[\s\S]*?\}\);/)[0];
  assert.match(initialization,/startHour: 10/);
  assert.ok(!main.includes(".get('sceneHour')")&&!main.includes(".has('timeHold')"));
  const updateStatement=main.match(/sceneClock\?\.update\(delta, \{ enabled: state\.introComplete[^;]*;/)[0];
  const initialize=new Function('createSceneClock','reducedMotion','$','applySceneDayMix','location',`let sceneClock; ${initialization} return sceneClock;`);
  const update=new Function('sceneClock','delta','state',updateStatement);
  const oldUrls=['','?qa&sceneHour=22&timeHold','?qa&sceneHour=18.5','?qa&timeHold'];
  for(const search of oldUrls) {
    let appliedMix=-1;
    const clock=initialize(createSceneClock,false,()=>null,mix=>{appliedMix=mix;},{search});
    const state={introComplete:false,modal:null,transitioning:false,galleryLoading:false};
    close(clock.hour,10);close(appliedMix,1);
    for(let i=0;i<120*10;i++) update(clock,1/120,state);
    close(clock.hour,10);close(clock.dayMix,1);assert.equal(clock.getState().paused,true);
    state.introComplete=true;update(clock,1/120,state);
    close(clock.hour,10+.4/120);close(clock.dayMix,1);assert.equal(clock.getState().paused,false);
    for(let i=1;i<120*30;i++) update(clock,1/120,state);
    close(clock.hour,22,1e-8);close(clock.dayMix,0);
    assert.equal(clock.getState().cycleSeconds,60);
  }
  return {testedUrlQueries:oldUrls,startHour:10,dayMixAtEntry:1,clockHeldThroughoutIntro:true,automaticCycleStillRuns:true};
});
await check('morning and evening have zero endpoint speed, and accessible clock is not a live announcement', () => {
  for(const h of [4,10,16,22]) assert.ok(Math.abs(daylightAtHour(h+.0001)-daylightAtHour(h-.0001))<1e-9);
  const html=readFileSync('index.html','utf8');assert.ok(!html.includes('data-theme='));
  assert.match(html,/class="scene-clock"[^>]*role="timer"[^>]*aria-live="off"/);
  const main=readFileSync('src/main.js','utf8');assert.ok(!main.includes("button.addEventListener('click', () => setTheme"));
  assert.match(main,/enabled: state.introComplete && !state.modal && !state.transitioning && !state.galleryLoading/);
});
await check('longer perceptual ramps reduce visible brightness steps without changing either baked endpoint', () => {
  const smoother=x=>x*x*x*(x*(x*6-15)+10);
  const previous=h=>h<5||h>=20?0:h<8?smoother((h-5)/3):h<=17?1:1-smoother((h-17)/3);
  const srgb=v=>v<=.0031308?12.92*v:1.055*v**(1/2.4)-.055;
  const channels=[[0,1],[.004,.5],[.02,.65],[.12,.7],[.7,.2]];
  const comparisons=channels.map(([night,day])=>{
    let oldMax=0,newMax=0,lastOld=srgb(day),lastNew=lastOld;
    for(let i=0;i<=7200;i++) {
      const hour=(10+i/300)%24, oldWeight=previous(hour), newWeight=daylightAtHour(hour);
      const oldValue=srgb(night+(day-night)*oldWeight),newValue=srgb(night+(day-night)*newWeight);
      oldMax=Math.max(oldMax,Math.abs(oldValue-lastOld));newMax=Math.max(newMax,Math.abs(newValue-lastNew));
      lastOld=oldValue;lastNew=newValue;
    }
    assert.ok(newMax<oldMax*.7);close(daylightAtHour(10),1);close(daylightAtHour(22),0);
    return {nightLinear:night,dayLinear:day,oldMaximumDisplayStep:oldMax,newMaximumDisplayStep:newMax,reduction:1-newMax/oldMax};
  });
  for(const fps of [24,30,60,120]) {
    const clock=createSceneClock();let previousMix=1,previousBrightness=1,maxMixStep=0,maxBrightnessStep=0;
    for(let frame=0;frame<60*fps;frame++) {
      clock.update(1/fps);const state=clock.getState();
      maxMixStep=Math.max(maxMixStep,Math.abs(state.dayMix-previousMix));
      maxBrightnessStep=Math.max(maxBrightnessStep,Math.abs(state.brightnessMix-previousBrightness));
      previousMix=state.dayMix;previousBrightness=state.brightnessMix;
    }
    close(clock.hour,10,1e-7);assert.ok(maxMixStep*fps<.17);assert.ok(maxBrightnessStep*fps<.126);
  }
  return {scope:'sRGB output response for representative linear-light channels, not a GPU benchmark',comparisons,frameRates:[24,30,60,120]};
});
await check('UI wash and theme metadata blend continuously with no half-mix CSS class switch', () => {
  const values=new Map(),classes=new Set(),meta={content:''};
  const body={classList:{add(name){classes.add(name);}},style:{setProperty(name,value){values.set(name,value);}}};
  const theme=createSceneTimeTheme({body,themeMeta:meta});
  theme.apply(0);close(parseFloat(values.get('--scene-day-percent')),0);assert.equal(meta.content,'#10171c');
  theme.apply(1);close(parseFloat(values.get('--scene-day-percent')),100);assert.equal(meta.content,'#e3e8e5');
  let last=0,maxStep=0;
  for(let i=0;i<=1800;i++) {
    const dayMix=daylightAtHour(4+i/300);theme.apply(dayMix);
    const brightness=parseFloat(values.get('--scene-day-percent'))/100;
    assert.ok(brightness>=last-1e-10);maxStep=Math.max(maxStep,brightness-last);last=brightness;
    close(theme.getState().dayMix,dayMix);close(theme.getState().backgroundMix,brightness);
  }
  assert.ok(maxStep<.00105);assert.deepEqual([...classes],['scene-time-colors']);
  const main=readFileSync('src/main.js','utf8');
  const apply=main.slice(main.indexOf('function applySceneDayMix('),main.indexOf('function setupGalleryNavigation('));
  assert.ok(!apply.includes('classList.toggle'));assert.ok(!apply.includes("meta[name="));assert.match(apply,/sceneTimeTheme\.apply\(mix\)/);
  const css=compile('src/scene-time-theme.scss').css;assert.ok(!/\bdisplay\s*:/.test(css));
  assert.match(css,/body\.scene-time-colors/);assert.match(css,/in-works-gallery::before/);
  return {backgroundMaximumStep:maxStep,metaEndpoints:['#10171c','#e3e8e5'],classChangesPerCycle:0,introOverlayDisplayRuleUntouched:true};
});

const roomGltf=await parseModelForCPU('public/models/orbital-atelier-v16.glb');
const welcomeGltf=await parseModelForCPU('public/models/welcome-terminal-v2.glb');
let uploads=0;
const renderer={capabilities:{getMaxAnisotropy:()=>16},initTexture(){uploads++;}};
const textureLoader={async loadAsync(){return new THREE.Texture();}};
const lighting=await createDualLighting({THREE,renderer,objects:[roomGltf.scene],profile:{revision:16,slots:[...Array(12).keys(),'window'],directory:'/textures/lighting-v16',loader:textureLoader,interiorNightReadability:1}});
const scene=new THREE.Scene();scene.add(roomGltf.scene);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial());scene.add(ground);
const exterior=createExteriorAtmosphere({THREE,scene,ground,roomBounds:new THREE.Box3().setFromObject(roomGltf.scene)});
class Generator {fromScene(){return {texture:new THREE.Texture(),dispose(){}};} dispose(){}}
const terminal=createResidentTerminal({THREE:{...THREE,PMREMGenerator:Generator},renderer,room:roomGltf.scene,welcomeGltf});terminal.attachHome();
const oldDetect=KTX2Loader.prototype.detectSupport, oldLoad=KTX2Loader.prototype.loadAsync;
KTX2Loader.prototype.detectSupport=function(){return this;};KTX2Loader.prototype.loadAsync=async()=>new THREE.Texture();
const surfaces=await createLiveRoomSurfaces({THREE,renderer,room:roomGltf.scene});
KTX2Loader.prototype.detectSupport=oldDetect;KTX2Loader.prototype.loadAsync=oldLoad;
const materialShaders=new Map();
roomGltf.scene.traverse(n=>{if(n.isMesh) for(const m of [].concat(n.material)) if(!materialShaders.has(m)) {
  const shader={uniforms:{},fragmentShader:THREE.ShaderLib.basic.fragmentShader,vertexShader:THREE.ShaderLib.basic.vertexShader};
  m.onBeforeCompile(shader,renderer);materialShaders.set(m,shader);
}});
await check('actual room materials, window, screens, environment and resident terminal follow exactly one fractional mix', () => {
  let count=0;
  for(const mix of [1,.999,.81,.5,.2,.001,0,.35,1]) {
    lighting.setDayMix(mix);exterior.setDayMix(mix);terminal.setDayMix(mix);surfaces.setDayMix(mix);
    close(lighting.getState().dayMix,mix);close(exterior.getState().dayMix,mix);close(surfaces.getState().screenDayMix,mix);
    close(terminal.getState().environmentIntensity,.3+.8*mix);close(terminal.getState().screenIntensity,.47+.37*mix);
    for(const [material,shader] of materialShaders) if(shader.uniforms.uLightingMix) {close(shader.uniforms.uLightingMix.value,mix);count++;}
  }
  const windowShader=[...materialShaders].find(([m])=>/^WEB8_WINDOW_CITY/.test(m.name))[1];
  assert.ok(windowShader.fragmentShader.includes('atelierDecodeBaked(texture2D(map, liveWindowCityUv(vMapUv)))'));
  assert.equal(windowShader.uniforms.uBakedRGBMRange.value,0,'window imagery remains sRGB rather than RGBM radiance');
  assert.ok(windowShader.fragmentShader.includes('liveWindowAtmosphere(sampledDiffuseColor.rgb'));
  return {boundMaterialSamples:count,materialCount:materialShaders.size};
});
await check('clock writes do not allocate GSAP tweens, change material versions, or upload new textures',()=>{
  const count=gsap.globalTimeline.getChildren().length, versions=new Map([...materialShaders.keys()].map(m=>[m,m.version])), oldUploads=uploads;
  for(let i=0;i<=1000;i++) {const mix=i/1000;lighting.setDayMix(mix);exterior.setDayMix(mix);terminal.setDayMix(mix);surfaces.setDayMix(mix);}
  assert.equal(gsap.globalTimeline.getChildren().length,count);assert.equal(uploads,oldUploads);
  for(const [m,version] of versions) assert.equal(m.version,version);
  return {writes:1001,textureUploadsAdded:0,materialRecompilesAdded:0,tweensAdded:0};
});
await check('night readability only grades interior shadows, preserving outdoor/window night and fixture highlights',()=>{
  let interiors=0, excluded=0;
  for(const [material,shader] of materialShaders) if(shader.uniforms.uNightReadability) {
    const excludedSlot=/^WEB8_LIGHTMAP_(5|6)(?:\D|$)/.test(material.name)||/^WEB8_WINDOW_CITY/.test(material.name);
    assert.equal(shader.uniforms.uNightReadability.value,excludedSlot?0:1);excludedSlot?excluded++:interiors++;
    assert.ok(shader.fragmentShader.includes('color.rgb *= 1.0 + uNightReadability * 2.4 * shoulder * shoulder;'));
    assert.ok(!shader.fragmentShader.includes('color.rgb += uNightReadability'));
  }
  assert.ok(interiors>=10);assert.ok(excluded>=3);
  const grade=(v,readability=1)=>{const shoulder=1-Math.min(1,Math.max(0,v/.45));return v*(1+readability*2.4*shoulder*shoulder);};
  const gradeColor=(rgb,readability=1)=>{const peak=Math.max(...rgb),gain=peak>0?grade(peak,readability)/peak:1;return rgb.map(v=>v*gain);};
  close(grade(0),0);close(grade(.5),.5);close(grade(1),1);close(grade(.02,0),.02);assert.ok(grade(.02)>.04);
  let previous=grade(0);for(let i=1;i<=10000;i++){const next=grade(i/10000);assert.ok(next>=previous);previous=next;}
  for(const rgb of [[0,0,0],[.08,.035,.012],[.016,.04,.06],[.7,.2,.035],[.85,.65,.42]]) {
    const output=gradeColor(rgb);
    if(Math.max(...rgb)>=.45 || Math.max(...rgb)===0) assert.deepEqual(output,rgb);
    if(rgb[0]>0 && rgb[1]>0) close(output[0]/output[1],rgb[0]/rgb[1]);
    if(rgb[1]>0 && rgb[2]>0) close(output[1]/output[2],rgb[1]/rgb[2]);
    assert.ok(output.every(v=>v>=0&&v<=1));
  }
  return {interiorMaterials:interiors,excludedMaterials:excluded,nightGrayBefore:.02,nightGrayAfter:grade(.02),
    interiorNightGrade:{method:'black-preserving peak-channel exposure shoulder',maximumGain:3.4,constantRGBOffset:[0,0,0],highlightsUnchangedAbove:.45},
    trueBlackPreserved:true,bakedHueRatiosPreserved:true,saturatedWarmEmittersPreserved:true,dayEndpointUnchanged:true};
});
surfaces.dispose();terminal.dispose();lighting.dispose();exterior.dispose();gsap.ticker.sleep();
const files=['src/scene-clock.js','src/scene-time-theme.js','src/scene-time-theme.scss','src/dual-lighting.js','src/exterior-atmosphere.js','src/resident-terminal.js','src/live-room-surfaces.js','src/works-gallery.js','src/main.js','index.html','src/style.scss'];
const report={createdAt:new Date().toISOString(),scope:'CPU clock + real GLTF material hooks; GPU compilation and visual output checked separately in browser',checks,passed:checks.every(c=>c.passed),sourceSha256:Object.fromEntries(files.map(f=>[f,createHash('sha256').update(readFileSync(f)).digest('hex')]))};
writeFileSync('docs/validation/scene-clock-v1.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));if(!report.passed)process.exitCode=1;
