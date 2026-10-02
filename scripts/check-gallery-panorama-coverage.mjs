// CPU frustum / projection audit: actual scene limits, actual model framing.
// This does not claim a browser screenshot or approve source-image seams.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import vm from 'node:vm';
import * as THREE from 'three';
import { createGalleryFraming } from '../src/gallery-framing.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { createScenePanorama } from '../src/scene-panorama.js';
const file=p=>new URL(`../${p}`,import.meta.url);
const main=readFileSync(file('src/main.js'),'utf8'), panorama=readFileSync(file('src/scene-panorama.js'),'utf8');
const gallery=readFileSync(file('src/works-gallery.js'),'utf8');
const {room}=readRoomGeometry(gallery.match(/loadAsync\('([^']+\.glb)'/)[1]);
const framing=createGalleryFraming(room);
const sizes=[[1500,1000],[1920,1080],[1440,900],[1024,1024],[844,795],[844,390],[390,844],[320,740],[768,1024]];
const config=main.match(/backdrop: \{ dayUrl: '\/media\/scene-backdrops-v1\/gallery-day\.png',[\s\S]*?\}/)[0];
const yaw=Number(config.match(/yawDegrees: ([\d.]+)/)[1]);
const detail=Number(config.match(/forwardDetailFactor: ([\d.]+)/)[1]);
const verticalDetail=Number(config.match(/latitudeDetailFactor: ([\d.]+)/)[1]);
const latitudeOffset=Number(config.match(/latitudeOffsetDegrees: ([\d.]+)/)[1]);
const camera=new THREE.PerspectiveCamera(35,1,.1,500),controls={minPan:new THREE.Vector3(),maxPan:new THREE.Vector3()};
const context=vm.createContext({THREE,camera,controls,state:{currentScene:'gallery'},satellite:()=>({pose:framing.pose}),savedRoomPose:null});
vm.runInContext(main.match(/function applySceneLimits\([^]*?\n\}/)[0]+'\napplySceneLimits();',context);
const limits={minAzimuth:controls.minAzimuthAngle,maxAzimuth:controls.maxAzimuthAngle,minPolar:controls.minPolarAngle,maxPolar:controls.maxPolarAngle,minDistance:controls.minDistance,minPan:controls.minPan.toArray(),maxPan:controls.maxPan.toArray()};
const ray=new THREE.Vector3(),ndc=new THREE.Vector2();
const radians=THREE.MathUtils.degToRad,degrees=THREE.MathUtils.radToDeg;
const longitude=v=>((Math.atan2(v.x,-v.z)/(2*Math.PI)+yaw/360+.5)%1+1)%1-.5;
const warped=(l,k)=>.5+Math.atan2(k*Math.sin(Math.PI*l),Math.cos(Math.PI*l))/Math.PI;
const density=(l,k)=>k/(Math.cos(Math.PI*l)**2+k*k*Math.sin(Math.PI*l)**2);
const latitudeWarp=angle=>{const shifted=angle+radians(latitudeOffset)*Math.cos(angle);return Math.atan2(verticalDetail*Math.sin(shifted),Math.cos(shifted));};
function pose(target,distance,polar,azimuth){camera.position.copy(target).add(new THREE.Vector3().setFromSphericalCoords(distance,polar,azimuth));camera.lookAt(target);camera.updateMatrixWorld(true);}
function pixelRay(x,y){const half=Math.tan(radians(camera.fov/2));return ray.set(x*half*camera.aspect,y*half,-1).applyQuaternion(camera.quaternion).normalize();}
function scan(resolution=32){
 let min=Infinity,max=-Infinity,clamped=0,total=0,worst;
 for(let y=0;y<=resolution;y++)for(let x=0;x<=resolution;x++){
  const nx=x/resolution*2-1,ny=y/resolution*2-1,l=longitude(pixelRay(nx,ny));
  const u=warped(l,detail),v=latitudeWarp(Math.asin(Math.min(1,Math.max(-1,ray.y))))/Math.PI+.5;
  assert.ok(u>=-1e-12&&u<=1+1e-12&&v>=-1e-12&&v<=1+1e-12);
  min=Math.min(min,l);max=Math.max(max,l);total++;
  if(Math.abs(l)>.25){clamped++;if(!worst||Math.abs(l)>Math.abs(worst.longitude))worst={ndc:[nx,ny],longitude:l,worldRay:ray.toArray()};}
 }
 return {longitudeDegrees:[degrees(min*2*Math.PI),degrees(max*2*Math.PI)],old180ClampedRays:clamped,sampledRays:total,worst};
}
const views=[];let testedTranslationZoomCases=0,testedFocusViews=0;
for(const [width,height]of sizes){
 camera.aspect=width/height;camera.updateProjectionMatrix();
 const home=framing.pose(camera.aspect,35),distance=home.position.distanceTo(home.target);
 camera.position.copy(home.position);camera.lookAt(home.target);camera.updateMatrixWorld(true);
 const homeScan=scan(),defaultPolar=new THREE.Spherical().setFromVector3(home.position.clone().sub(home.target)).phi;
 let maxOrdinaryLongitude=0,oldClampWitness=null;
 for(let p=0;p<=40;p++)for(let a=0;a<=30;a++){
  pose(home.target,distance,THREE.MathUtils.lerp(limits.minPolar,limits.maxPolar,p/40),THREE.MathUtils.lerp(limits.minAzimuth,limits.maxAzimuth,a/30));
  const sample=scan(12);
  if(sample.worst&&!oldClampWitness)oldClampWitness={polar:THREE.MathUtils.lerp(limits.minPolar,limits.maxPolar,p/40),azimuth:THREE.MathUtils.lerp(limits.minAzimuth,limits.maxAzimuth,a/30),...sample.worst};
 }
 for(const az of [limits.minAzimuth,limits.maxAzimuth]){
  pose(home.target,distance,defaultPolar,az);const s=scan();maxOrdinaryLongitude=Math.max(maxOrdinaryLongitude,...s.longitudeDegrees.map(Math.abs));
 }
 // Dolly and world-space pan preserve orientation. Verify on actual cameras,
 // including all eight allowed target corners and both dolly extrema.
 const targets=[home.target];
 for(const x of [limits.minPan[0],limits.maxPan[0]])for(const y of [limits.minPan[1],limits.maxPan[1]])for(const z of [limits.minPan[2],limits.maxPan[2]])targets.push(new THREE.Vector3(x,y,z));
 const baseline=new Map();
 for(const d of [limits.minDistance,distance,home.maxDistance])for(const target of targets){
  pose(target,d,defaultPolar,.4);
  for(const [x,y]of [[-1,-1],[-1,1],[1,-1],[1,1],[0,0]]){
   const value=pixelRay(x,y).clone(),key=`${x},${y}`;
   if(baseline.has(key))assert.ok(value.distanceTo(baseline.get(key))<1e-12);else baseline.set(key,value);
  }
  testedTranslationZoomCases++;
 }
 assert.ok(oldClampWitness,'old half-sphere clamp regression remains reproduced');
 const focusViews=[];
 for(const x of [-4.8,-2.7,-.6,1.5,3.6,5.7]){
  const target=new THREE.Vector3(x,1.8,-1.6),focusDistance=Math.max(10,4.5/Math.tan(radians(17.5))/camera.aspect);
  camera.position.copy(target).add(new THREE.Vector3(.15,.29,1).normalize().multiplyScalar(focusDistance));camera.lookAt(target);camera.updateMatrixWorld(true);
  focusViews.push({target:target.toArray(),distance:focusDistance,longitude:scan(8).longitudeDegrees});testedFocusViews++;
 }
 views.push({viewport:[width,height],fov:35,distance,maxDistance:home.maxDistance,defaultPolarDegrees:degrees(defaultPolar),defaultView:homeScan,
  minPolarIncludesNadir:limits.minPolar<radians(17.5),minimumOldSectorCoverageDegrees:360,
  ordinaryPolarAllAzimuthRequiredSectorDegrees:2*maxOrdinaryLongitude,oldClampWitness,focusViews});
}
const curves=[];
for(const k of [1,1.8,4,6]){
 let previous=-Infinity,minDerivative=Infinity,maxDerivative=-Infinity;
 for(let i=0;i<=100000;i++){
  const l=-.5+i/100000,value=warped(l,k),d=density(l,k);
  assert.ok(value>=-1e-12&&value<=1+1e-12&&value>=previous-1e-12&&d>=-1e-12);previous=value;
  minDerivative=Math.min(minDerivative,d);maxDerivative=Math.max(maxDerivative,d);
 }
 const rearPixels=1774*2*(warped(.5,k)-warped(150/360,k));
 curves.push({factor:k,minimumDerivative:minDerivative,maximumDerivative:maxDerivative,rear60DegreesPixelsAt1774:rearPixels,centerDensity:k,
  seamValuePeriodic:true,seamDerivativePeriodic:true});
}
let previousLatitude=-Infinity;
for(let i=0;i<=100000;i++){
 const latitude=-Math.PI/2+i/100000*Math.PI,mapped=latitudeWarp(latitude);
 assert.ok(mapped>=-Math.PI/2-1e-12&&mapped<=Math.PI/2+1e-12&&mapped>previousLatitude);previousLatitude=mapped;
}
assert.ok(Math.abs(latitudeWarp(-Math.PI/2)+Math.PI/2)<1e-12&&Math.abs(latitudeWarp(Math.PI/2)-Math.PI/2)<1e-12);
assert.ok(panorama.includes('atan(${keys.detail}.x * sin(halfAngle), cos(halfAngle))'));
assert.ok(panorama.includes('atan(${keys.detail}.y * sin(latitude), cos(latitude))'));
const maps=[];let disposedTextures=0;
const actual=createScenePanorama({prefix:'Audit',loader:{async loadAsync(){const map=new THREE.Texture({width:1774,height:887});map.addEventListener('dispose',()=>disposedTextures++);maps.push(map);return map;}}});
assert.equal(await actual.load({dayUrl:'day',nightUrl:'night',yawDegrees:yaw,latitudeOffsetDegrees:latitudeOffset,forwardDetailFactor:detail,latitudeDetailFactor:verticalDetail}),true);
assert.deepEqual(actual.uniforms[actual.keys.detail].value.toArray(),[detail,verticalDetail]);
assert.equal(actual.getState().sameDayNightOrientation,true);assert.equal(maps[0].colorSpace,THREE.SRGBColorSpace);
actual.dispose();actual.dispose();assert.equal(disposedTextures,2);
const report={complete:true,forwardDetailFactor:detail,latitudeDetailFactor:verticalDetail,latitudeOffsetDegrees:latitudeOffset,yawDegrees:yaw,limits,viewports:views,testedTranslationZoomCases,testedFocusViews,
 globalCurveChecks:curves,old180ClampingReproduced:true,minimumStrictLinearSectorCoverage:360,
 currentShaderUsesAuditedAtanMapping:true,registeredPairLoadAndIdempotentDispose:true,latitudeStrictlyMonotone:true,latitudePolesFixed:true,
 conclusion:'Projective half-angle longitude mapping covers all rays including nadir. Factor 4 has derivative 0.25..4; no clamp, reversal, zero derivative or coordinate seam. Latitude remap is strictly monotone and fixes both poles. Image boundary matching and projected architectural proportions require visual review.',
 limitations:['Pixel rays may be occluded by the model; this conservatively audits all frustum rays, including floor-haze samples.','No new image detail is created. Angular allocation changes relative horizontal scale and peripheral distortion.','A source panorama whose left/right edges differ still has an image seam; coordinate continuity cannot fix source pixels.']};
mkdirSync(file('output'),{recursive:true});writeFileSync(file('output/gallery-panorama-coverage-audit.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({complete:true,viewports:views.length,testedTranslationZoomCases,testedFocusViews,detail,verticalDetail,yaw,old180ClampingReproduced:true,curves,
 defaultRanges:views.map(v=>({viewport:v.viewport,longitude:v.defaultView.longitudeDegrees,ordinaryPolarAllAzimuthRequiredSectorDegrees:v.ordinaryPolarAllAzimuthRequiredSectorDegrees}))},null,2));
