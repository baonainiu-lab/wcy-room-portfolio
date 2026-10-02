import * as THREE from 'three';
import { sampleTravelPose, smoothTravel, travelAperture } from './gallery-transition-path.js';

// Both spaces stay visible through the opening. The last composited pose becomes
// the ordinary camera; no opaque cover, hidden teleport or second camera reset.
export function createGalleryTransition({ renderer, camera, controls, reducedMotion = false }) {
  const sourceCamera = camera.clone(), destinationCamera = camera.clone();
  const sourceTarget = new THREE.Vector3(), destinationTarget = new THREE.Vector3();
  const size = new THREE.Vector2(), cssSize = new THREE.Vector2();
  const viewport = new THREE.Vector4(), scissor = new THREE.Vector4();
  const compositeScene = new THREE.Scene(), compositeCamera = new THREE.Camera();
  const uniforms = {
    uSource: { value: null }, uDestination: { value: null },
    uResolution: { value: new THREE.Vector2() }, uCenter: { value: new THREE.Vector2() },
    uHalfSize: { value: new THREE.Vector2(.1, .1) }, uRadius: { value: 0 },
    uProgress: { value: 0 }, uReveal: { value: 0 }, uReduced: { value: reducedMotion ? 1 : 0 },
    uDay: { value: 1 },
  };
  const material = new THREE.ShaderMaterial({
    name: 'GlassPassageComposite', depthTest: false, depthWrite: false, toneMapped: false,
    uniforms,
    vertexShader: 'varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader: `
      varying vec2 vUv;
      uniform sampler2D uSource, uDestination;
      uniform vec2 uResolution, uCenter, uHalfSize;
      uniform float uRadius, uProgress, uReveal, uReduced, uDay;
      float roundedBox(vec2 p, vec2 b, float r) {
        vec2 q=abs(p)-b+r;
        return min(max(q.x,q.y),0.)+length(max(q,0.))-r;
      }
      void main() {
        vec3 source=texture2D(uSource,vUv).rgb;
        vec3 result;
        if(uReduced>.5) {
          result=mix(source,texture2D(uDestination,vUv).rgb,uProgress);
        } else {
          vec2 halfPx=uHalfSize*uResolution;
          vec2 point=(vUv-uCenter)*uResolution;
          float d=roundedBox(point,halfPx,uRadius);
          float edge=max(fwidth(d),.7);
          float mask=(1.-smoothstep(-edge,edge,d))*uReveal;
          // Fit the incoming view without stretching, then resolve to exact
          // screen UVs before the live-scene handoff.
          vec2 local=(vUv-uCenter)/(2.*max(uHalfSize.x,uHalfSize.y))+.5;
          vec2 incoming=mix(local,vUv,smoothstep(.55,.94,uProgress));
          vec3 destination=texture2D(uDestination,clamp(incoming,vec2(.001),vec2(.999))).rgb;
          float rim=exp(-abs(d)/1.4);
          float glass=exp(-abs(d-5.)/8.);
          float envelope=uReveal*(1.-smoothstep(.74,.97,uProgress));
          vec2 normal=normalize(point+vec2(.001));
          vec2 refracted=clamp(vUv+normal*glass*envelope*1.8/uResolution,vec2(.001),vec2(.999));
          source=mix(source,texture2D(uSource,refracted).rgb,glass*envelope*.65);
          result=mix(source,destination,mask);
          float highlight=.35+.65*pow(max(0.,dot(normal,normalize(vec2(-.5,1.)))),2.);
          vec3 metal=mix(vec3(.28,.42,.49),vec3(.88,.65,.34),highlight);
          result+=metal*(rim*.5+glass*.075)*envelope*mix(.55,1.,uDay);
          if(uProgress>=.99999) result=texture2D(uDestination,vUv).rgb;
        }
        gl_FragColor=vec4(result,1.);
        #include <colorspace_fragment>
      }`,
  });
  const triangle = new THREE.BufferGeometry();
  triangle.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  triangle.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const quad = new THREE.Mesh(triangle, material); quad.frustumCulled = false; compositeScene.add(quad);
  let targets = [], active = null, prepared = false, disposed = false, lastRun = null;
  let preparation = null;

  function preserveRenderer(callback) {
    const target = renderer.getRenderTarget();
    renderer.getViewport(viewport); renderer.getScissor(scissor);
    const scissorTest = renderer.getScissorTest(), autoClear = renderer.autoClear;
    try { renderer.autoClear = true; renderer.setScissorTest(false); return callback(); }
    finally {
      renderer.setRenderTarget(target); renderer.setViewport(viewport); renderer.setScissor(scissor);
      renderer.setScissorTest(scissorTest); renderer.autoClear = autoClear;
    }
  }

  function resizeTargets() {
    renderer.getDrawingBufferSize(size); renderer.getSize(cssSize);
    if (!targets.length) {
      const type = renderer.extensions.has('EXT_color_buffer_float') ? THREE.HalfFloatType : THREE.UnsignedByteType;
      targets = [0, 1].map(() => new THREE.WebGLRenderTarget(size.x, size.y, {
        type, depthBuffer: true, stencilBuffer: false,
        // At DPR 2 retain the full buffer; at DPR 1 use 2x MSAA for thin rails.
        samples: renderer.getPixelRatio() < 1.5 ? 2 : 0,
      }));
      uniforms.uSource.value = targets[0].texture; uniforms.uDestination.value = targets[1].texture;
    }
    targets.forEach(target => { if (target.width !== size.x || target.height !== size.y) target.setSize(size.x, size.y); });
    uniforms.uResolution.value.copy(cssSize);
  }

  async function prepare({ sourceScene, destinationScene, destination }) {
    if (disposed || prepared) return;
    if (preparation) return preparation;
    preparation = (async () => {
      resizeTargets();
      sourceCamera.copy(camera);
      destinationCamera.copy(camera); destinationCamera.position.copy(destination.position); destinationCamera.lookAt(destination.target);
      // Compile linear-target variants before yielding with the canvas restored.
      const tasks = preserveRenderer(() => {
        renderer.setRenderTarget(targets[0]);
        return [renderer.compileAsync(sourceScene, sourceCamera), renderer.compileAsync(destinationScene, destinationCamera)];
      });
      await Promise.all([...tasks, renderer.compileAsync(compositeScene, compositeCamera)]);
      if (disposed) return;
      // A real offscreen draw allocates geometry/VAOs and framebuffer storage.
      // compileAsync alone does not. No pixels go to the visible canvas.
      preserveRenderer(() => {
        renderer.setRenderTarget(targets[0]); renderer.render(sourceScene, sourceCamera);
        renderer.setRenderTarget(targets[1]); renderer.render(destinationScene, destinationCamera);
        const destinationMap = uniforms.uDestination.value;
        uniforms.uDestination.value = targets[0].texture;
        try { renderer.render(compositeScene, compositeCamera); }
        finally { uniforms.uDestination.value = destinationMap; }
      });
      prepared = true;
    })().finally(() => { preparation = null; });
    return preparation;
  }

  function run({ sourceScene, destinationScene, destination, resolveDestination, anchor, returning = false, isDay = true, onHandoff, onComplete }) {
    if (active || disposed) return false;
    resizeTargets();
    const source = { position: camera.position.clone(), target: controls.target.clone() };
    const seed = projectAnchor(anchor, camera);
    active = { sourceScene, destinationScene, source, destination, resolveDestination, anchor: seed,
      returning, onHandoff, onComplete, elapsed: 0, duration: reducedMotion ? .32 : 2.35,
      frames: [], drawFrames: 0, resized: false };
    uniforms.uDay.value = isDay ? 1 : 0;
    document.body.classList.add('is-scene-travelling');
    return true;
  }

  function render(delta, beforeRender) {
    if (!active) return false;
    const run = active;
    // Hidden tabs don't advance this clock. Long frames cannot skip the passage.
    const dt = Math.max(0, Math.min(delta || 0, .05));
    if (run.drawFrames > 0 && delta > 0) run.frames.push(delta * 1000);
    run.elapsed = Math.min(run.duration, run.elapsed + dt);
    const p = run.elapsed / run.duration;
    const destination = run.resolveDestination?.() ?? run.destination;
    run.destination = destination;
    sourceCamera.copy(camera); destinationCamera.copy(camera);
    sampleTravelPose({ source: run.source, destination, progress: p, returning: run.returning, reducedMotion,
      sourceCamera, sourceTarget, destinationCamera, destinationTarget });
    const aperture = travelAperture(p, run.anchor, cssSize, reducedMotion);
    uniforms.uProgress.value = reducedMotion ? smoothTravel(p) : p;
    uniforms.uReveal.value = aperture.reveal;
    uniforms.uCenter.value.copy(aperture.center); uniforms.uHalfSize.value.copy(aperture.halfSize);
    uniforms.uRadius.value = aperture.radius;
    beforeRender?.(sourceCamera, destinationCamera);
    preserveRenderer(() => {
      renderer.setRenderTarget(targets[0]); renderer.render(run.sourceScene, sourceCamera);
      renderer.setRenderTarget(targets[1]); renderer.render(run.destinationScene, destinationCamera);
      renderer.setRenderTarget(null); renderer.render(compositeScene, compositeCamera);
    });
    run.drawFrames++;
    if (p >= 1) {
      camera.position.copy(destinationCamera.position); controls.target.copy(destinationTarget);
      camera.quaternion.copy(destinationCamera.quaternion); camera.updateMatrixWorld(true);
      lastRun = { returning: run.returning, frames: run.drawFrames, frameMs: quantiles(run.frames),
        duration: run.duration, resized: run.resized, finalPosition: camera.position.toArray(), finalTarget: controls.target.toArray() };
      active = null;
      run.onHandoff?.();
      document.body.classList.remove('is-scene-travelling');
      run.onComplete?.();
    }
    return true;
  }

  function resize() { if (targets.length) resizeTargets(); if (active) active.resized = true; }
  function cancel() { active = null; document.body.classList.remove('is-scene-travelling'); }
  function dispose() {
    cancel(); disposed = true; targets.forEach(target => target.dispose()); targets = [];
    triangle.dispose(); material.dispose();
  }
  return { prepare, run, render, resize, cancel, dispose,
    getState: () => ({ revision: 2, style: 'live-glass-passage', active: Boolean(active), prepared,
      progress: active ? active.elapsed / active.duration : 1, reducedMotion, renderTargets: targets.length,
      renderTargetSize: targets.length ? [targets[0].width, targets[0].height] : null,
      targetType: targets[0]?.texture.type, lastRun }),
  };
}

function quantiles(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return { p50: sorted[Math.floor(sorted.length * .5)], p95: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * .95))], max: sorted.at(-1), samples: sorted.length };
}

function projectAnchor(object, camera) {
  const center = new THREE.Vector2(.38, .52), halfSize = new THREE.Vector2(.08, .065);
  if (!object) return { center, halfSize };
  camera.updateMatrixWorld(true); object.updateWorldMatrix(true, true);
  const box = new THREE.Box3().setFromObject(object), projected = box.getCenter(new THREE.Vector3()).project(camera);
  if (projected.z < -1 || projected.z > 1) return { center, halfSize };
  center.set(THREE.MathUtils.clamp(projected.x * .5 + .5, .18, .82), THREE.MathUtils.clamp(projected.y * .5 + .5, .24, .76));
  const min = new THREE.Vector2(1, 1), max = new THREE.Vector2(0, 0), point = new THREE.Vector3();
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
    point.set(x, y, z).project(camera);
    min.min(new THREE.Vector2(point.x * .5 + .5, point.y * .5 + .5)); max.max(new THREE.Vector2(point.x * .5 + .5, point.y * .5 + .5));
  }
  halfSize.subVectors(max, min).multiplyScalar(.38).clamp(new THREE.Vector2(.045, .045), new THREE.Vector2(.14, .14));
  return { center, halfSize };
}
