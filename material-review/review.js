import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createWorksGallery } from '../src/works-gallery.js';
import { resolveMaterialRelease } from '../src/material-release.js';
const renderer = new THREE.WebGLRenderer({canvas:document.querySelector('canvas'),antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.NoToneMapping;
const camera=new THREE.PerspectiveCamera(35,innerWidth/innerHeight,.05,1000);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
let gallery,cycle=false,last=0,frames=[],compileErrors=[],surfaceUniforms=new Set();
renderer.debug.onShaderError=(gl,program,vs,fs)=>{compileErrors.push({program:gl.getProgramInfoLog(program),vertex:gl.getShaderInfoLog(vs),fragment:gl.getShaderInfoLog(fs)});console.error('MATERIAL_SHADER_ERROR',JSON.stringify(compileErrors.at(-1)));};
function fit(){if(!gallery)return;const pose=gallery.pose(camera.aspect);camera.position.copy(pose.position);controls.target.copy(pose.target);controls.update();}
function resize(){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();fit();}
addEventListener('resize',resize);resize();
function mix(value){cycle=false;gallery?.setDayMix(value);}
document.querySelector('#day').onclick=()=>mix(1);document.querySelector('#dusk').onclick=()=>mix(.5);document.querySelector('#night').onclick=()=>mix(0);
document.querySelector('#cycle').onclick=()=>{cycle=true;};document.querySelector('#reset').onclick=fit;
document.querySelector('#close').onclick=()=>{camera.position.set(6,5.8,10);controls.target.set(.2,1.1,2.1);controls.update();};
document.querySelector('#spec').onclick=()=>{for(const u of new Set([...surfaceUniforms].map(u=>u.uSurfaceReflectionStrength).filter(Boolean)))u.value=1-u.value;};
document.querySelector('#raw').onclick=async()=>{const loader=new THREE.TextureLoader();for(const u of surfaceUniforms){if(!u.uDayMap)continue;const slot=Number(u.uDayMap.value.name.split('_').at(-1));const tex=await loader.loadAsync(`/textures/works-gallery-v6/day-${slot}.logrgb.png`);tex.flipY=false;tex.colorSpace=THREE.NoColorSpace;tex.minFilter=THREE.LinearFilter;tex.generateMipmaps=false;u.uDayMap.value=tex;}document.querySelector('#status').textContent='白天无压缩 LogRGB 原图';};
try{gallery=await createWorksGallery({renderer,isDay:true,reducedMotion:false,materialRelease:resolveMaterialRelease(location.search),backdrop:{dayUrl:'/media/scene-backdrops-v1/gallery-day.png',nightUrl:'/media/scene-backdrops-v1/gallery-night.png',yawDegrees:31.4,forwardDetailFactor:4,latitudeDetailFactor:1.7,latitudeOffsetDegrees:8,groundFadeNear:18,groundFadeFar:36}});const seen=new Set();gallery.model.traverse(n=>{if(!n.isMesh)return;for(const m of [].concat(n.material)){if(seen.has(m))continue;seen.add(m);const hook=m.onBeforeCompile;m.onBeforeCompile=function(shader,r){hook.call(this,shader,r);surfaceUniforms.add(shader.uniforms);};}});fit();renderer.compile(gallery.scene,camera);document.querySelector('#status').textContent=gallery.getState().physicalSurface?'新材质已载入':'旧材质对照';}
catch(error){document.querySelector('#status').textContent=error.message;console.error(error);}
let diagAt=0;
renderer.setAnimationLoop(t=>{if(!gallery)return;if(last&&t-last<200)frames.push(t-last);last=t;if(frames.length>240)frames.shift();
 if(cycle)gallery.setDayMix((Math.cos(t/60000*Math.PI*2)+1)/2);controls.update();gallery.update(t,camera);renderer.render(gallery.scene,camera);
 if(t-diagAt>600){diagAt=t;const state=gallery.getState();document.querySelector('#diagnostics').textContent=JSON.stringify({ready:true,assets:state.assetCount,physical:state.physicalSurface,lighting:state.lighting,glass:state.glass,formats:state.textureFormats,shaderErrors:compileErrors,frameMs:frames.length?frames.reduce((a,b)=>a+b,0)/frames.length:null,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles},null,2);}
});
addEventListener('pagehide',()=>{gallery?.dispose();controls.dispose();renderer.dispose();},{once:true});
