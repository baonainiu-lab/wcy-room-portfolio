import * as THREE from 'three';
import { GALLERY_OFFSET, sampleTravelPose, smoothTravel } from './gallery-transition-path.js';

// A temporary shared 3D stage, with the gallery physically beside the room.
// Geometry/materials are shared, while cloned transforms leave interaction
// pivots untouched. The scene handoff uses the exact final native-camera pose.
export function createGalleryTransition({ renderer, camera, controls, reducedMotion = false }) {
  const sourceCamera = camera.clone(), destinationCamera = camera.clone(), stageCamera = camera.clone();
  const sourceTarget = new THREE.Vector3(), destinationTarget = new THREE.Vector3();
  const size = new THREE.Vector2(), viewport = new THREE.Vector4(), scissor = new THREE.Vector4();
  const compositeScene = new THREE.Scene(), compositeCamera = new THREE.Camera();
  const uniforms = { uStage: { value: null }, uNative: { value: null }, uBlend: { value: 0 } };
  const material = new THREE.ShaderMaterial({
    name: 'SpatialPassageComposite', depthTest: false, depthWrite: false, toneMapped: false, uniforms,
    vertexShader: 'varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader: `varying vec2 vUv; uniform sampler2D uStage,uNative; uniform float uBlend;
      void main(){ gl_FragColor=vec4(mix(texture2D(uStage,vUv).rgb,texture2D(uNative,vUv).rgb,uBlend),1.);
      #include <colorspace_fragment>
      }`,
  });
  const triangle = new THREE.BufferGeometry();
  triangle.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  triangle.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const quad = new THREE.Mesh(triangle, material); quad.frustumCulled = false; compositeScene.add(quad);
  let targets = [], active = null, prepared = false, disposed = false, lastRun = null, preparation = null;
  let stage, roomScene, galleryClone, travelEnvironment;
  const transformPairs = [];
  const stageOffset = GALLERY_OFFSET.clone();
  const stageMaterials = new Set();

  function releaseStage() {
    // The optional travel finish owns only its material, never the shared maps
    // or model resources. Clearing this reference also makes retries safe.
    stageMaterials.forEach(owned => owned.dispose()); stageMaterials.clear();
    stage?.clear(); stage = null; galleryClone = null; travelEnvironment = null; transformPairs.length = 0;
  }

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
    renderer.getDrawingBufferSize(size);
    if (!targets.length) {
      const type = renderer.extensions.has('EXT_color_buffer_float') ? THREE.HalfFloatType : THREE.UnsignedByteType;
      targets = [0, 1].map(() => new THREE.WebGLRenderTarget(size.x, size.y, {
        type, depthBuffer: true, stencilBuffer: false, samples: renderer.getPixelRatio() < 1.5 ? 2 : 0,
      }));
      uniforms.uStage.value = targets[0].texture; uniforms.uNative.value = targets[1].texture;
    }
    targets.forEach(target => { if (target.width !== size.x || target.height !== size.y) target.setSize(size.x, size.y); });
  }
  function pairTransforms(original, clone) {
    // Stable asset IDs cover independent hover, furniture and mechanism motion.
    if (original.userData.asset_id) transformPairs.push([original, clone]);
    original.children.forEach((child, index) => pairTransforms(child, clone.children[index]));
  }
  function syncStage() {
    for (const [original, clone] of transformPairs) {
      clone.position.copy(original.position); clone.quaternion.copy(original.quaternion); clone.scale.copy(original.scale);
      clone.visible = original.visible;
    }
    if (stage.background?.isColor && roomScene.background?.isColor) stage.background.copy(roomScene.background);
    if (stage.fog && roomScene.fog) { stage.fog.color.copy(roomScene.fog.color); stage.fog.near = roomScene.fog.near; stage.fog.far = roomScene.fog.far; }
  }
  async function prepare({ sourceScene, destinationScene, destinationModel, destination, destinationEnvironment, offset }) {
    if (disposed || prepared) return;
    if (preparation) return preparation;
    preparation = (async () => {
      if (offset) stageOffset.copy(offset);
      resizeTargets(); roomScene = sourceScene;
      if (!stage) {
        travelEnvironment = destinationEnvironment;
        stage = sourceScene.clone(true); stage.name = 'RoomAndGalleryTravelStage';
        destinationEnvironment?.configureTravelStage?.(stage, stageOffset.clone());
        pairTransforms(sourceScene, stage);
        galleryClone = destinationModel.clone(true); pairTransforms(destinationModel, galleryClone);
        const berth = new THREE.Group(); berth.position.copy(stageOffset); berth.add(galleryClone); stage.add(berth);
        if (destinationEnvironment?.createTravelFloorMaterial) {
          let floor;
          stage.traverse(node => {
            if (node.isMesh && node.material?.name === 'Exterior · continuous satin floor') floor = node;
          });
          if (!floor) throw new Error('Shared travel stage is missing its continuous floor.');
          const finish = destinationEnvironment.createTravelFloorMaterial(floor.material, stageOffset.clone());
          if (!finish?.isShaderMaterial || finish === floor.material) {
            throw new Error('Travel floor finish must return its own ShaderMaterial.');
          }
          stageMaterials.add(finish); floor.material = finish;
        }
        if (destinationEnvironment?.createTravelSkyMaterial) {
          let sky;
          stage.traverse(node => {
            if (node.isMesh && node.material?.name === 'Exterior · enclosing atmospheric dome') sky = node;
          });
          if (!sky) throw new Error('Shared travel stage is missing its atmospheric dome.');
          const finish = destinationEnvironment.createTravelSkyMaterial(sky.material, stageOffset.clone());
          if (!finish?.isShaderMaterial || finish === sky.material) {
            throw new Error('Travel sky finish must return its own ShaderMaterial.');
          }
          stageMaterials.add(finish); sky.material = finish;
        }
      }
      travelEnvironment?.updateTravelEnvironment?.(0, false);
      syncStage(); sourceCamera.copy(camera); stageCamera.copy(camera);
      destinationCamera.copy(camera); destinationCamera.position.copy(destination.position); destinationCamera.lookAt(destination.target);
      const tasks = preserveRenderer(() => {
        renderer.setRenderTarget(targets[0]);
        return [renderer.compileAsync(stage, stageCamera), renderer.compileAsync(sourceScene, sourceCamera), renderer.compileAsync(destinationScene, destinationCamera)];
      });
      await Promise.all([...tasks, renderer.compileAsync(compositeScene, compositeCamera)]);
      if (disposed) return;
      preserveRenderer(() => {
        renderer.setRenderTarget(targets[0]); renderer.render(stage, stageCamera);
        renderer.setRenderTarget(targets[1]); renderer.render(destinationScene, destinationCamera);
        const nativeMap = uniforms.uNative.value; uniforms.uNative.value = targets[0].texture;
        try { renderer.render(compositeScene, compositeCamera); }
        finally { uniforms.uNative.value = nativeMap; }
      });
      prepared = true;
    })().catch(error => {
      // The loader disposes a failed gallery. A retry must clone the replacement
      // model rather than retain nodes pointing at the discarded resources.
      releaseStage();
      throw error;
    }).finally(() => { preparation = null; });
    return preparation;
  }
  function run({ sourceScene, destinationScene, destination, resolveDestination, returning = false, onHandoff, onComplete }) {
    if (active || disposed || !prepared) return false;
    resizeTargets(); travelEnvironment?.updateTravelEnvironment?.(0, returning); syncStage();
    active = { sourceScene, destinationScene, source: { position: camera.position.clone(), target: controls.target.clone() },
      destination, resolveDestination, returning, onHandoff, onComplete, elapsed: 0,
      duration: reducedMotion ? .32 : 2.15, frames: [], drawFrames: 0, resized: false };
    document.body.classList.add('is-scene-travelling'); return true;
  }
  function render(delta, beforeRender) {
    if (!active) return false;
    const run = active;
    if (run.drawFrames > 0 && delta > 0) run.frames.push(delta * 1000);
    run.elapsed = Math.min(run.duration, run.elapsed + Math.max(0, Math.min(delta || 0, .05)));
    const p = run.elapsed / run.duration;
    const destination = run.resolveDestination?.() ?? run.destination; run.destination = destination;
    sourceCamera.copy(camera); destinationCamera.copy(camera); stageCamera.copy(camera);
    sampleTravelPose({ source: run.source, destination, progress: p, returning: run.returning, reducedMotion, offset: stageOffset,
      sourceCamera, sourceTarget, destinationCamera, destinationTarget, stageCamera });
    beforeRender?.(sourceCamera, destinationCamera);
    travelEnvironment?.updateTravelEnvironment?.(p, run.returning); syncStage();
    preserveRenderer(() => {
      if (reducedMotion) {
        renderer.setRenderTarget(targets[0]); renderer.render(run.sourceScene, sourceCamera);
        renderer.setRenderTarget(targets[1]); renderer.render(run.destinationScene, destinationCamera);
        uniforms.uBlend.value = smoothTravel(p);
      } else {
        renderer.setRenderTarget(targets[0]); renderer.render(stage, stageCamera);
        // Only the peripheral environment differs at each end. Both real model
        // projections already align; this soft handoff never masks or crops them.
        const departing = p < .18;
        const blend = departing ? 1 - smoothTravel(p / .18) : smoothTravel((p - .76) / .24);
        uniforms.uBlend.value = blend;
        if (blend > 0) {
          renderer.setRenderTarget(targets[1]);
          renderer.render(departing ? run.sourceScene : run.destinationScene, departing ? sourceCamera : destinationCamera);
        }
      }
      renderer.setRenderTarget(null); renderer.render(compositeScene, compositeCamera);
    });
    run.drawFrames++;
    if (p >= 1) {
      camera.position.copy(destinationCamera.position); controls.target.copy(destinationTarget);
      camera.quaternion.copy(destinationCamera.quaternion); camera.updateMatrixWorld(true);
      lastRun = { returning: run.returning, frames: run.drawFrames, frameMs: quantiles(run.frames), duration: run.duration,
        resized: run.resized, finalPosition: camera.position.toArray(), finalTarget: controls.target.toArray() };
      active = null; run.onHandoff?.(); document.body.classList.remove('is-scene-travelling'); run.onComplete?.();
    }
    return true;
  }
  function resize() { if (targets.length) resizeTargets(); if (active) active.resized = true; }
  function cancel() { active = null; document.body.classList.remove('is-scene-travelling'); }
  function dispose() {
    if (disposed) return;
    cancel(); disposed = true; targets.forEach(target => target.dispose()); targets = [];
    // Stage meshes share live resources; only the finish and fullscreen pass
    // belong to the transition itself.
    releaseStage(); triangle.dispose(); material.dispose();
  }
  return { prepare, run, render, resize, cancel, dispose,
    getState: () => ({ revision: 4, style: 'shared-stage-camera-tracking', active: Boolean(active), prepared,
      progress: active ? active.elapsed / active.duration : 1, reducedMotion, renderTargets: targets.length,
      renderTargetSize: targets.length ? [targets[0].width, targets[0].height] : null,
      targetType: targets[0]?.texture.type, stageOffset: stageOffset.toArray(), transformPairs: transformPairs.length, lastRun }),
  };
}
function quantiles(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return { p50: sorted[Math.floor(sorted.length * .5)], p95: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * .95))], max: sorted.at(-1), samples: sorted.length };
}
