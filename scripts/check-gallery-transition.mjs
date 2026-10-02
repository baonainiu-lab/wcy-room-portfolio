import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import * as THREE from 'three';
import { OrbitControls } from '../src/utils/OrbitControls.js';
import { createGalleryTransition } from '../src/gallery-transition.js';
import { sampleTravelPose, smoothTravel, GALLERY_OFFSET } from '../src/gallery-transition-path.js';
import { createExteriorAtmosphere } from '../src/exterior-atmosphere.js';
import { createGalleryFloorFinish } from '../src/gallery-floor-finish.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { createGalleryFraming } from '../src/gallery-framing.js';
import { createAboutFraming } from '../src/about-framing.js';

const mainSource = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
const gallerySource = readFileSync(new URL('../src/works-gallery.js', import.meta.url), 'utf8');
const galleryModelUrl = gallerySource.match(/loadAsync\('([^']+\.glb)'/)?.[1];
assert.ok(galleryModelUrl, 'production gallery model path exists');
const actualGalleryFraming = createGalleryFraming(readRoomGeometry(galleryModelUrl).room);
const originalDocument = globalThis.document;
const results = [], EPS = 1e-9;
function close(actual, expected, label, epsilon = EPS) {
  const a = actual.toArray ? actual.toArray() : actual, b = expected.toArray ? expected.toArray() : expected;
  assert.equal(a.length, b.length, label);
  for (let i = 0; i < a.length; i++) assert.ok(Math.abs(a[i] - b[i]) <= epsilon, `${label}[${i}]: ${a[i]} != ${b[i]}`);
}
function extractFunction(name) {
  const match = mainSource.match(new RegExp(`function ${name}\\([^]*?\\n\\}`, 'm'));
  assert.ok(match, `production ${name} function found`); return match[0];
}
function dom() {
  const classes = new Set(), elements = new Map();
  const classList = { add: (...names) => names.forEach(name => classes.add(name)), remove: (...names) => names.forEach(name => classes.delete(name)),
    contains: name => classes.has(name), toggle(name, force) { if (force ?? !classes.has(name)) classes.add(name); else classes.delete(name); } };
  const document = { body: { classList } };
  const $ = selector => {
    if (!elements.has(selector)) elements.set(selector, { inert: false, attributes: {}, setAttribute(name, value) { this.attributes[name] = value; } });
    return elements.get(selector);
  };
  return { document, $, classes };
}
class MockRenderer {
  constructor({ ratio = 2, float = true } = {}) {
    this.ratio = ratio; this.width = 1440; this.height = 900; this.autoClear = false;
    this.target = new THREE.WebGLRenderTarget(231, 117);
    this.viewport = new THREE.Vector4(9, 13, 701, 411); this.scissor = new THREE.Vector4(17, 23, 193, 127); this.scissorTest = true;
    this.extensions = { has: name => name === 'EXT_color_buffer_float' && float };
    this.calls = []; this.compiles = []; this.pendingCompiles = []; this.deferCompiles = false;
    this.throwOn = null; this.targets = new Set(); this.feedbackChecks = 0;
  }
  getRenderTarget() { return this.target; }
  getViewport(out) { return out.copy(this.viewport); }
  getScissor(out) { return out.copy(this.scissor); }
  getScissorTest() { return this.scissorTest; }
  getDrawingBufferSize(out) { return out.set(Math.floor(this.width * this.ratio), Math.floor(this.height * this.ratio)); }
  getSize(out) { return out.set(this.width, this.height); }
  getPixelRatio() { return this.ratio; }
  setViewport(value) { this.viewport.copy(value); }
  setScissor(value) { this.scissor.copy(value); }
  setScissorTest(value) { this.scissorTest = value; }
  setRenderTarget(target) {
    this.target = target;
    if (target) { this.targets.add(target); this.viewport.copy(target.viewport); this.scissor.copy(target.scissor); }
    else { this.viewport.set(0, 0, this.width * this.ratio, this.height * this.ratio); this.scissor.copy(this.viewport); }
  }
  compileAsync(scene, camera) {
    this.compiles.push({ scene, camera, target: this.target });
    if (this.deferCompiles) return new Promise(resolve => this.pendingCompiles.push(resolve));
    return Promise.resolve(scene);
  }
  releaseCompiles() { this.pendingCompiles.splice(0).forEach(resolve => resolve()); }
  render(scene, camera) {
    scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    let composite = null;
    scene.traverse(node => {
      if (!node.material?.uniforms?.uStage) return;
      const uniforms = node.material.uniforms;
      assert.ok(uniforms.uStage.value?.isTexture && uniforms.uNative.value?.isTexture, 'both sampled targets exist');
      assert.notEqual(uniforms.uStage.value, this.target?.texture, 'source sampler must never alias current color attachment');
      assert.notEqual(uniforms.uNative.value, this.target?.texture, 'destination sampler must never alias current color attachment');
      this.feedbackChecks++;
      composite = { stage: uniforms.uStage.value, native: uniforms.uNative.value, blend: uniforms.uBlend.value,
        uniformNames: Object.keys(uniforms), fragmentShader: node.material.fragmentShader };
    });
    const type = composite ? 'composite' : scene.name;
    this.calls.push({ type, scene, camera, cameraSnapshot: camera.clone(), position: camera.position.clone(), quaternion: camera.quaternion.clone(),
      aspect: camera.aspect, target: this.target, autoClear: this.autoClear, scissorTest: this.scissorTest, composite });
    if (this.throwOn === type) { this.throwOn = null; throw new Error(`injected ${type} draw failure`); }
  }
  snapshot() { return { target: this.target, viewport: this.viewport.clone(), scissor: this.scissor.clone(), scissorTest: this.scissorTest, autoClear: this.autoClear }; }
  assertRestored(before) {
    assert.equal(this.target, before.target, 'render target restored'); close(this.viewport, before.viewport, 'viewport restored');
    close(this.scissor, before.scissor, 'scissor restored'); assert.equal(this.scissorTest, before.scissorTest, 'scissor test restored');
    assert.equal(this.autoClear, before.autoClear, 'autoClear restored');
  }
}
function limits(controls, gallery, maxDistance = gallery ? 140 : 45) {
  controls.minPan.set(...(gallery ? [-8.3, .3, -4] : [-3, -1, -4])); controls.maxPan.set(...(gallery ? [7.3, 5, 6] : [2, 8, 8]));
  Object.assign(controls, { minDistance: gallery ? 10 : 5, maxDistance, minPolarAngle: gallery ? .28 : 0,
    maxPolarAngle: gallery ? 1.43 : Math.PI / 2, minAzimuthAngle: gallery ? -.55 : 0, maxAzimuthAngle: gallery ? .95 : Math.PI / 2 });
}
function fixture(options = {}) {
  const documentState = dom(); globalThis.document = documentState.document;
  const camera = new THREE.PerspectiveCamera(35, 1.6, .1, 500); camera.position.set(11, 10.4, 18);
  const controls = new OrbitControls(camera, null); controls.target.set(0, 2.03, -.4);
  Object.assign(controls, { enableDamping: true, dampingFactor: .05, panSpeed: .6, zoomSpeed: .8 }); limits(controls, false); controls.update();
  const sourceScene = new THREE.Scene(); sourceScene.name = 'room';
  const destinationScene = new THREE.Scene(); destinationScene.name = 'gallery';
  const anchor = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1, .1), new THREE.MeshBasicMaterial()); anchor.position.set(-3, 3, 0); sourceScene.add(anchor);
  anchor.name = 'RoomFixtureMesh'; anchor.userData.asset_id = 'main_display';
  const texture = new THREE.Texture(); anchor.material.map = texture;
  const roomPart = new THREE.Mesh(new THREE.BoxGeometry(.8, .6, .9), new THREE.MeshBasicMaterial({ map: texture }));
  roomPart.name = 'RoomAnimatedFixture'; roomPart.userData.asset_id = 'furniture.work_chair'; roomPart.position.set(-1.5, 1.4, .4); sourceScene.add(roomPart);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(150, 150), new THREE.ShaderMaterial({
    uniforms: { uTheme: { value: 0 }, uBreathing: { value: 1 }, uSharedTexture: { value: texture } },
  }));
  floor.name = 'RoomContinuousFloorFixture'; floor.material.name = 'Exterior · continuous satin floor';
  floor.rotation.x = -Math.PI / 2; floor.position.y = -1.065; sourceScene.add(floor);
  sourceScene.background = new THREE.Color('#aaccee'); sourceScene.fog = new THREE.Fog('#aaccee', 30, 150);
  const destinationModel = new THREE.Group(); destinationModel.name = 'GalleryFixtureModel';
  destinationModel.position.set(.3, .1, -.4); destinationModel.rotation.y = .06; destinationScene.add(destinationModel);
  const galleryPart = new THREE.Mesh(new THREE.BoxGeometry(2, 3, .4), new THREE.MeshBasicMaterial({ map: texture }));
  galleryPart.name = 'GalleryFixtureMesh'; galleryPart.userData.asset_id = 'gallery.work.01'; galleryPart.position.set(2, 1.5, -1); destinationModel.add(galleryPart);
  const portal = new THREE.Object3D(); portal.name = 'portal'; portal.userData.asset_id = 'gallery.architecture.portal'; destinationModel.add(portal);
  const galleryPose = options.pose ?? actualGalleryFraming.pose;
  const renderer = new MockRenderer(options);
  const transition = createGalleryTransition({ renderer, camera, controls, reducedMotion: options.reducedMotion ?? false });
  const context = vm.createContext({ camera, controls, renderer, galleryTransition: transition, scene: sourceScene,
    state: { currentScene: 'room', transitioning: false, introComplete: true, modal: null, galleryRequested: true, isDay: true },
    worksGallery: { scene: destinationScene, model: destinationModel, pose: galleryPose, components: new Map([['gallery.architecture.portal', portal]]) },
    roots: new Map([['main_display', anchor]]), savedRoomPose: null, cameraResetting: false,
    clearHover() {}, activePointers: new Set([1]), pointerDown: {}, pendingPointer: {}, dragging: true, multiTouch: true,
    cameraTimeline: { kill() {} }, gsap: { killTweensOf() {} }, galleryNavigation: { states: [], setState(next) { this.states.push(next); } },
    roomCameraGuard: { resets: 0, reset() { this.resets++; } }, updateNavigation() {},
    document: documentState.document, $: documentState.$, canvas: { focused: 0, focus() { this.focused++; } },
  });
  context.nextSceneAfterReturn = null;
  context.activeSceneTransition = transition;
  context.aboutTransition = null;
  context.satellite = (kind = context.state.currentScene) => kind === 'gallery' ? context.worksGallery : kind === 'about' ? context.aboutAtelier : null;
  vm.runInContext([extractFunction('setTravelBusy'), extractFunction('applySceneLimits'), extractFunction('travelToScene')].join('\n'), context);
  const source = { position: camera.position.clone(), target: controls.target.clone(), maxDistance: controls.maxDistance, aspect: camera.aspect };
  const destination = galleryPose(camera.aspect, camera.fov);
  const prepare = (destinationEnvironment = options.destinationEnvironment) => transition.prepare({ sourceScene, destinationScene, destinationModel, destination, destinationEnvironment });
  const step = (delta, beforeRender) => { const saved = renderer.snapshot(); const rendered = transition.render(delta, beforeRender); renderer.assertRestored(saved); return rendered; };
  function finish(delta = 1 / 120) { let count = 0; while (transition.getState().active && count++ < 2000) step(delta); assert.ok(count < 2000, 'transition finishes'); return count; }
  function stability() {
    const position = camera.position.clone(), target = controls.target.clone(), quaternion = camera.quaternion.clone();
    for (let i = 0; i < 120; i++) controls.update(1 / 120);
    close(camera.position, position, 'post-completion camera stays still', 1e-8); close(controls.target, target, 'post-completion target stays still', 1e-8);
    assert.ok(camera.quaternion.angleTo(quaternion) < 1e-7, 'post-completion orientation stays still');
  }
  return { ...documentState, camera, controls, renderer, transition, context, sourceScene, destinationScene, destinationModel, roomPart, galleryPart, texture, source, destination, anchor, floor,
    galleryPose, prepare, step, finish, stability };
}
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...(await run() ?? {}) }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.message, stack: error.stack.split('\n').slice(0, 4).join('\n') }); }
}
function poseSample(source, destination, progress, extra = {}) {
  const sourceCamera = new THREE.PerspectiveCamera(35, 1.6, .1, 500), destinationCamera = sourceCamera.clone(), stageCamera = sourceCamera.clone();
  const sourceTarget = new THREE.Vector3(), destinationTarget = new THREE.Vector3();
  sampleTravelPose({ source, destination, progress, sourceCamera, destinationCamera, stageCamera, sourceTarget, destinationTarget, ...extra });
  return { sourceCamera, destinationCamera, stageCamera, sourceTarget, destinationTarget };
}

function getStage(f) {
  const call = f.renderer.calls.find(call => call.type === 'RoomAndGalleryTravelStage');
  assert.ok(call, 'shared 3D stage was rendered'); return call.scene;
}
function transformSnapshot(root) {
  const values = new Map(); root.traverse(node => values.set(node, { position: node.position.toArray(), quaternion: node.quaternion.toArray(),
    scale: node.scale.toArray(), visible: node.visible, parent: node.parent })); return values;
}
function unchanged(snapshot, label) {
  for (const [node, pose] of snapshot) {
    close(node.position, pose.position, `${label}: ${node.name} position`, 0); close(node.quaternion, pose.quaternion, `${label}: ${node.name} rotation`, 0);
    close(node.scale, pose.scale, `${label}: ${node.name} scale`, 0); assert.equal(node.visible, pose.visible); assert.equal(node.parent, pose.parent);
  }
}
function projectedVertex(node, local, camera) { return node.localToWorld(local.clone()).project(camera); }
function floorFinishProvider() {
  const calls = [];
  return { calls, createTravelFloorMaterial(baseMaterial, offset) {
    const material = new THREE.ShaderMaterial({ name: 'Fixture local gallery travel finish',
      vertexShader: baseMaterial.vertexShader, fragmentShader: baseMaterial.fragmentShader,
      uniforms: { ...baseMaterial.uniforms, uGalleryOffset: { value: offset.clone() } } });
    const call = { baseMaterial, offset, material, disposals: 0 };
    material.addEventListener('dispose', () => call.disposals++); calls.push(call);
    return material;
  } };
}
function addFixtureSky(f) {
  const sky = new THREE.Mesh(new THREE.SphereGeometry(100, 8, 4), new THREE.ShaderMaterial({
    name: 'Exterior · enclosing atmospheric dome', uniforms: { uTheme: f.floor.material.uniforms.uTheme },
  }));
  sky.name = 'Fixture enclosing sky'; f.sourceScene.add(sky); return sky;
}
function skyFinishProvider() {
  const floorProvider = floorFinishProvider(), mix = { value: .77 }, skyCalls = [], updates = [];
  return { calls: floorProvider.calls, skyCalls, mix, updates,
    createTravelFloorMaterial(base, offset) {
      const material = floorProvider.createTravelFloorMaterial(base, offset); material.uniforms.uSkyMix = mix; return material;
    },
    createTravelSkyMaterial(base, offset) {
      const material = new THREE.ShaderMaterial({ name: 'Fixture gallery travel sky',
        uniforms: { ...base.uniforms, uSkyMix: mix, uGalleryOffset: { value: offset.clone() } } });
      const call = { baseMaterial: base, offset, material, disposals: 0 };
      material.addEventListener('dispose', () => call.disposals++); skyCalls.push(call); return material;
    },
    updateTravelEnvironment(progress, returning) {
      const weight = smoothTravel((progress - .18) / (.76 - .18)); mix.value = returning ? 1 - weight : weight;
      updates.push({ progress, returning, mix: mix.value });
    },
  };
}

await check('shared camera path: exact endpoints, consistent native frames and smooth terminal velocity', () => {
  const f = fixture(); let maximumProjectionError = 0;
  for (const returning of [false, true]) {
    const source = returning ? f.destination : f.source, destination = returning ? f.source : f.destination;
    const start = poseSample(source, destination, 0, { returning }), end = poseSample(source, destination, 1, { returning });
    close(start.sourceCamera.position, source.position, 'exact native source endpoint', 0);
    close(end.destinationCamera.position, destination.position, 'exact native destination endpoint', 0);
    close(start.stageCamera.position, source.position.clone().add(returning ? GALLERY_OFFSET : new THREE.Vector3()), 'stage source endpoint');
    close(end.stageCamera.position, destination.position.clone().add(returning ? new THREE.Vector3() : GALLERY_OFFSET), 'stage destination endpoint');
    close(start.sourceTarget, source.target, 'exact source target', 0); close(end.destinationTarget, destination.target, 'exact destination target', 0);
    for (const which of ['sourceCamera', 'destinationCamera', 'stageCamera']) {
      const coarse = end[which].position.distanceTo(poseSample(source, destination, .99, { returning })[which].position) / .01;
      const fine = end[which].position.distanceTo(poseSample(source, destination, .999, { returning })[which].position) / .001;
      assert.ok(fine < coarse * .03 && fine < .003, `${which}: terminal velocity converges to zero`);
    }
    for (const progress of [0, .05, .18, .5, .76, .95, 1]) {
      const sample = poseSample(source, destination, progress, { returning });
      for (const [nativeCamera, offset] of [[sample.sourceCamera, returning ? GALLERY_OFFSET : new THREE.Vector3()],
        [sample.destinationCamera, returning ? new THREE.Vector3() : GALLERY_OFFSET]]) {
        for (const point of [new THREE.Vector3(0, 1, 0), new THREE.Vector3(-3, 2, -1), new THREE.Vector3(3, 3, 2)]) {
          const native = point.clone().project(nativeCamera), stage = point.clone().add(offset).project(sample.stageCamera);
          const error = native.distanceTo(stage); maximumProjectionError = Math.max(maximumProjectionError, error);
          assert.ok(error < 1e-10, 'native and offset stage geometry have matching perspective projections');
        }
      }
    }
  }
  assert.equal(smoothTravel(-1), 0); assert.equal(smoothTravel(2), 1); f.transition.dispose();
  return { directions: 2, maximumProjectionError, nativeEndpointTolerance: 0 };
});
await check('stage contains independent model transforms and shares only geometry/material resources', async () => {
  const f = fixture(), roomBefore = transformSnapshot(f.sourceScene), galleryBefore = transformSnapshot(f.destinationScene);
  await f.prepare(); const stage = getStage(f), roomClone = stage.getObjectByName(f.roomPart.name), galleryClone = stage.getObjectByName(f.galleryPart.name);
  assert.ok(roomClone && galleryClone && roomClone !== f.roomPart && galleryClone !== f.galleryPart);
  assert.equal(roomClone.geometry, f.roomPart.geometry); assert.equal(roomClone.material, f.roomPart.material);
  assert.equal(galleryClone.geometry, f.galleryPart.geometry); assert.equal(galleryClone.material, f.galleryPart.material);
  close(roomClone.getWorldPosition(new THREE.Vector3()), f.roomPart.getWorldPosition(new THREE.Vector3()), 'room stays in original physical berth');
  close(galleryClone.getWorldPosition(new THREE.Vector3()), f.galleryPart.getWorldPosition(new THREE.Vector3()).add(GALLERY_OFFSET), 'gallery occupies physical offset');
  const vertices = [new THREE.Vector3(-1, -1.5, -.2), new THREE.Vector3(1, 1.5, .2)]; let maxEndpointError = 0;
  for (const returning of [false, true]) {
    const source = returning ? f.destination : f.source, destination = returning ? f.source : f.destination;
    for (const progress of [0, 1]) {
      const sample = poseSample(source, destination, progress, { returning });
      const galleryEnd = returning ? progress === 0 : progress === 1;
      const original = galleryEnd ? f.galleryPart : f.roomPart, clone = galleryEnd ? galleryClone : roomClone;
      const nativeCamera = progress === 0 ? sample.sourceCamera : sample.destinationCamera;
      for (const vertex of vertices) {
        const error = projectedVertex(original, vertex, nativeCamera).distanceTo(projectedVertex(clone, vertex, sample.stageCamera));
        maxEndpointError = Math.max(maxEndpointError, error); assert.ok(error < 1e-11, 'cloned real geometry and native endpoint project identically');
      }
    }
  }
  unchanged(roomBefore, 'prepare room'); unchanged(galleryBefore, 'prepare gallery'); f.transition.dispose();
  unchanged(roomBefore, 'dispose room'); unchanged(galleryBefore, 'dispose gallery');
  return { berthOffset: GALLERY_OFFSET.toArray(), maxEndpointError, sharedGeometry: true, sharedMaterials: true };
});
await check('clean gallery berth preserves the shared continuous floor and native floor visibility', async () => {
  close(GALLERY_OFFSET, [34, -.185, 1.5], 'current clean gallery berth', 0);
  const f = fixture(), before = transformSnapshot(f.sourceScene);
  await f.prepare(); const stage = getStage(f), clone = stage.getObjectByName(f.floor.name);
  assert.ok(clone && clone !== f.floor, 'continuous floor is independently cloned');
  assert.equal(clone.material, f.floor.material); assert.equal(clone.geometry, f.floor.geometry);
  const assertFloor = () => {
    assert.equal(clone.visible, true, 'stage ground stays visible after the city terrain was removed');
    assert.equal(f.floor.visible, true, 'native room ground remains visible');
    close(clone.getWorldPosition(new THREE.Vector3()), [0, -1.065, 0], 'shared ground datum');
  };
  assertFloor();
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  for (let i = 0; i < 30; i++) f.step(1 / 60);
  assertFloor(); f.renderer.width = 844; f.transition.resize(); f.step(1 / 60); assertFloor();
  f.transition.cancel(); unchanged(before, 'clean gallery room'); f.transition.dispose(); unchanged(before, 'disposed clean gallery room');
  return { stageOffset: GALLERY_OFFSET.toArray(), stageFloorVisible: clone.visible, nativeFloorVisible: f.floor.visible, floorY: -1.065 };
});
await check('optional gallery finish replaces only one existing stage floor, preserving source uniforms and sky', async () => {
  const f = fixture(), provider = floorFinishProvider(), originalMaterial = f.floor.material;
  const uniforms = originalMaterial.uniforms, originalEntries = { ...uniforms };
  const sky = new THREE.Mesh(new THREE.SphereGeometry(100, 8, 4), new THREE.ShaderMaterial());
  sky.name = 'Fixture enclosing sky'; f.sourceScene.add(sky);
  let sharedDisposals = 0;
  for (const resource of [originalMaterial, f.floor.geometry, f.texture, sky.material, sky.geometry]) {
    resource.addEventListener('dispose', () => sharedDisposals++);
  }
  await f.prepare(provider);
  assert.equal(provider.calls.length, 1);
  const call = provider.calls[0], stage = getStage(f), floor = stage.getObjectByName(f.floor.name);
  assert.equal(call.baseMaterial, originalMaterial); close(call.offset, GALLERY_OFFSET, 'provider receives fixed gallery offset');
  assert.notEqual(call.offset, GALLERY_OFFSET, 'provider cannot mutate the exported shared offset');
  assert.equal(floor.material, call.material); assert.equal(floor.geometry, f.floor.geometry);
  let floorCopies = 0; stage.traverse(node => { if (node.geometry === f.floor.geometry) floorCopies++; });
  assert.equal(floorCopies, 1, 'finish creates no additional floor plane');
  assert.equal(stage.getObjectByName(sky.name).material, sky.material, 'existing sky is untouched');
  assert.equal(f.floor.material, originalMaterial); assert.equal(originalMaterial.uniforms, uniforms);
  assert.deepEqual(originalMaterial.uniforms, originalEntries); assert.equal(uniforms.uTheme.value, 0); assert.equal(uniforms.uBreathing.value, 1);
  assert.equal(uniforms.uSharedTexture.value, f.texture); assert.equal(uniforms.uGalleryOffset, undefined);
  for (const [key, value] of Object.entries(originalEntries)) assert.equal(call.material.uniforms[key], value, `${key} shares a read-only uniform reference`);
  assert.equal(f.renderer.compiles.length, 4); assert.equal(f.renderer.calls.length, 3, 'finish adds no warmup pass');
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  for (let i = 0; i < 20; i++) f.step(.05);
  const drawStart = f.renderer.calls.length;
  f.step(1 / 120, () => { uniforms.uTheme.value = 1; uniforms.uBreathing.value = .99; });
  assert.equal(f.renderer.calls.length - drawStart, 2, 'stage plus existing composite only');
  assert.equal(call.material.uniforms.uTheme.value, 1); assert.equal(call.material.uniforms.uBreathing.value, .99);
  assert.equal(f.floor.material, originalMaterial); assert.equal(floor.visible, true); assert.equal(f.floor.visible, true);
  f.transition.dispose(); assert.equal(call.disposals, 1); assert.equal(sharedDisposals, 0);
  return { stageFloorCount: floorCopies, sourceUniformEntries: Object.keys(originalEntries), stageDrawsPerMiddleFrame: 2,
    ownedMaterialDisposals: call.disposals, sharedDisposals };
});
await check('cancel and resize reuse the prepared finish; repeated dispose releases it exactly once', async () => {
  const f = fixture(), provider = floorFinishProvider(); await f.prepare(provider);
  const first = provider.calls[0];
  const run = () => f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  assert.equal(run(), true); f.step(.05); f.transition.cancel();
  assert.equal(first.disposals, 0); f.renderer.width = 844; f.transition.resize(); await f.prepare(provider);
  assert.equal(provider.calls.length, 1); assert.equal(getStage(f).getObjectByName(f.floor.name).material, first.material);
  assert.equal(run(), true); f.step(.05); f.transition.cancel();
  assert.equal(first.disposals, 0); f.transition.dispose(); f.transition.dispose();
  assert.equal(first.disposals, 1); return { providerCalls: provider.calls.length, disposalsAfterCancel: 0, finalOwnedMaterialDisposals: first.disposals };
});
await check('failed prepare releases the owned finish, then retry constructs and releases a fresh one', async () => {
  const f = fixture(), provider = floorFinishProvider(), sourceMaterial = f.floor.material;
  let sourceDisposals = 0, textureDisposals = 0;
  sourceMaterial.addEventListener('dispose', () => sourceDisposals++); f.texture.addEventListener('dispose', () => textureDisposals++);
  f.renderer.throwOn = 'composite'; await assert.rejects(f.prepare(provider), /injected composite draw failure/);
  assert.equal(provider.calls.length, 1); assert.equal(provider.calls[0].disposals, 1); assert.equal(f.transition.getState().prepared, false);
  const callStart = f.renderer.calls.length; await f.prepare(provider);
  assert.equal(provider.calls.length, 2); assert.notEqual(provider.calls[0].material, provider.calls[1].material);
  const freshStage = f.renderer.calls.slice(callStart).find(call => call.type === 'RoomAndGalleryTravelStage').scene;
  assert.equal(freshStage.getObjectByName(f.floor.name).material, provider.calls[1].material);
  assert.equal(f.floor.material, sourceMaterial); f.transition.dispose(); f.transition.dispose();
  assert.deepEqual(provider.calls.map(call => call.disposals), [1, 1]); assert.equal(sourceDisposals, 0); assert.equal(textureDisposals, 0);
  return { attemptOwnedMaterialDisposals: provider.calls.map(call => call.disposals), sourceDisposals, textureDisposals };
});
await check('provider failure or invalid shared return cannot dispose the source material and can be retried', async () => {
  const f = fixture(), sourceMaterial = f.floor.material;
  let sourceDisposals = 0; sourceMaterial.addEventListener('dispose', () => sourceDisposals++);
  await assert.rejects(f.prepare({ createTravelFloorMaterial() { throw new Error('injected provider failure'); } }), /injected provider failure/);
  await assert.rejects(f.prepare({ createTravelFloorMaterial(base) { return base; } }), /own ShaderMaterial/);
  assert.equal(sourceDisposals, 0); assert.equal(f.floor.material, sourceMaterial);
  const provider = floorFinishProvider(); await f.prepare(provider); f.transition.dispose();
  assert.equal(provider.calls[0].disposals, 1); assert.equal(sourceDisposals, 0);
});
await check('disposing during asynchronous preparation releases both finishes once without drawing disposed resources', async () => {
  const f = fixture(), provider = skyFinishProvider(); addFixtureSky(f); f.renderer.deferCompiles = true;
  const first = f.prepare(provider), second = f.prepare(provider);
  assert.equal(provider.calls.length, 1); assert.equal(f.renderer.compiles.length, 4);
  f.transition.dispose(); f.transition.dispose(); assert.equal(provider.calls[0].disposals, 1); assert.equal(provider.skyCalls[0].disposals, 1);
  f.renderer.releaseCompiles(); await Promise.all([first, second]);
  assert.equal(f.renderer.calls.length, 0); assert.equal(provider.calls[0].disposals, 1); assert.equal(provider.skyCalls[0].disposals, 1);
  assert.equal(f.transition.getState().prepared, false);
  return { providerCalls: [1, 1], ownedMaterialDisposals: [1, 1], lateDraws: 0 };
});
await check('optional sky replaces the existing dome and updates the shared environment before each draw in both directions', async () => {
  const f = fixture(), sky = addFixtureSky(f), sourceSkyMaterial = sky.material, provider = skyFinishProvider();
  let sourceDisposals = 0; sourceSkyMaterial.addEventListener('dispose', () => sourceDisposals++);
  const originalCompile = f.renderer.compileAsync.bind(f.renderer);
  f.renderer.compileAsync = (scene, camera) => { assert.equal(provider.mix.value, 0, 'warmup resets travel sky before compilation'); return originalCompile(scene, camera); };
  await f.prepare(provider);
  assert.deepEqual(provider.updates, [{ progress: 0, returning: false, mix: 0 }]);
  assert.equal(provider.skyCalls.length, 1); const call = provider.skyCalls[0], stage = getStage(f), clone = stage.getObjectByName(sky.name);
  assert.equal(call.baseMaterial, sourceSkyMaterial); assert.equal(clone.material, call.material); assert.equal(clone.geometry, sky.geometry);
  assert.equal(sky.material, sourceSkyMaterial); assert.equal(sourceSkyMaterial.uniforms.uSkyMix, undefined);
  assert.equal(call.material.uniforms.uSkyMix, provider.calls[0].material.uniforms.uSkyMix);
  close(call.offset, GALLERY_OFFSET, 'sky provider receives the gallery offset'); assert.notEqual(call.offset, GALLERY_OFFSET);
  let domes = 0; stage.traverse(node => { if (node.geometry === sky.geometry) domes++; }); assert.equal(domes, 1);
  let callbackCalls = 0, middleDraws = 0;
  const originalRender = f.renderer.render.bind(f.renderer); let expectedUpdateCount = null;
  f.renderer.render = (scene, camera) => {
    if (expectedUpdateCount !== null) assert.equal(provider.updates.length, expectedUpdateCount, 'environment hook must finish before renderer draws');
    return originalRender(scene, camera);
  };
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  assert.equal(provider.mix.value, 0);
  while (f.transition.getState().active) {
    const beforeUpdates = provider.updates.length, beforeDraws = f.renderer.calls.length;
    expectedUpdateCount = beforeUpdates + 1;
    f.step(.05, () => { callbackCalls++; assert.equal(provider.updates.length, beforeUpdates, 'environment update follows beforeRender'); });
    assert.equal(provider.updates.length, beforeUpdates + 1);
    const update = provider.updates.at(-1); assert.equal(update.returning, false);
    assert.equal(call.material.uniforms.uSkyMix.value, update.mix);
    if (update.progress > .2 && update.progress < .74) { assert.equal(f.renderer.calls.length - beforeDraws, 2); middleDraws++; }
  }
  assert.equal(provider.mix.value, 1, 'arrival finishes at gallery sky');
  expectedUpdateCount = null;
  f.transition.run({ sourceScene: f.destinationScene, destinationScene: f.sourceScene, destination: f.source, returning: true });
  assert.deepEqual(provider.updates.at(-1), { progress: 0, returning: true, mix: 1 }, 'return starts with gallery sky before first render');
  f.step(.05); assert.equal(provider.updates.at(-1).returning, true); f.finish(.05);
  assert.equal(provider.mix.value, 0, 'return finishes at original room sky');
  f.transition.dispose(); f.transition.dispose(); assert.equal(call.disposals, 1); assert.equal(provider.calls[0].disposals, 1); assert.equal(sourceDisposals, 0);
  return { stageDomeCount: domes, updateAfterCallbackFrames: callbackCalls, middleFramesWithTwoDraws: middleDraws,
    stageMaterialDisposals: [provider.calls[0].disposals, call.disposals], sourceSkyDisposals: sourceDisposals };
});
await check('sky preparation failure releases both owned finishes and rebuilds them safely on retry', async () => {
  const f = fixture(), sky = addFixtureSky(f), provider = skyFinishProvider();
  let sharedDisposals = 0; for (const material of [sky.material, f.floor.material]) material.addEventListener('dispose', () => sharedDisposals++);
  f.renderer.throwOn = 'composite'; await assert.rejects(f.prepare(provider), /injected composite/);
  assert.deepEqual([provider.calls[0].disposals, provider.skyCalls[0].disposals], [1, 1]);
  await f.prepare(provider); assert.equal(provider.calls.length, 2); assert.equal(provider.skyCalls.length, 2);
  f.transition.cancel(); assert.deepEqual([provider.calls[1].disposals, provider.skyCalls[1].disposals], [0, 0]);
  f.transition.dispose(); f.transition.dispose();
  assert.deepEqual(provider.calls.map(call => call.disposals), [1, 1]); assert.deepEqual(provider.skyCalls.map(call => call.disposals), [1, 1]);
  assert.equal(sharedDisposals, 0);
  const missing = fixture(), missingProvider = skyFinishProvider();
  await assert.rejects(missing.prepare(missingProvider), /missing its atmospheric dome/);
  assert.equal(missingProvider.calls[0].disposals, 1, 'floor material releases if the sky cannot be found');
  addFixtureSky(missing); await missing.prepare(missingProvider); missing.transition.dispose();
  assert.deepEqual(missingProvider.calls.map(call => call.disposals), [1, 1]); assert.equal(missingProvider.skyCalls[0].disposals, 1);
});
await check('production environment provider preserves real atmosphere uniforms, local texture coordinates and ownership', async () => {
  const f = fixture(), roomBounds = new THREE.Box3(new THREE.Vector3(-8, -1, -7), new THREE.Vector3(8, 7, 7));
  const roomAtmosphere = createExteriorAtmosphere({ THREE, scene: f.sourceScene, ground: f.floor, roomBounds, reducedMotion: false });
  const nativeFloor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial());
  nativeFloor.rotation.x = -Math.PI / 2; nativeFloor.position.y = -.88; f.destinationScene.add(nativeFloor);
  const galleryAtmosphere = createExteriorAtmosphere({ THREE, scene: f.destinationScene, ground: nativeFloor, roomBounds, reducedMotion: true });
  const textures = Object.fromEntries(['day', 'night', 'day-sky', 'night-sky'].map(key => [key, new THREE.Texture()]));
  const { day, night } = textures, mapReleases = [0, 0, 0, 0], releases = { room: 0, travel: 0, travelSky: 0 };
  Object.values(textures).forEach((texture, index) => texture.addEventListener('dispose', () => mapReleases[index]++));
  const sourceMaterial = f.floor.material, sourceShader = sourceMaterial.fragmentShader, sourceUniforms = { ...sourceMaterial.uniforms };
  const sourceSky = roomAtmosphere.sky, sourceSkyShader = sourceSky.material.fragmentShader, sourceSkyUniforms = { ...sourceSky.material.uniforms };
  sourceMaterial.addEventListener('dispose', () => releases.room++);
  const requested = [];
  const environment = await createGalleryFloorFinish({ ground: nativeFloor, sky: galleryAtmosphere.sky,
    loader: { async loadAsync(url) { requested.push(url); return textures[url.match(/\/([^/]+)\.ktx2$/)[1]]; } },
    renderer: { capabilities: { getMaxAnisotropy: () => 16 } } });
  assert.deepEqual(requested, Object.keys(textures).map(key => `/textures/gallery-atmosphere-v1/${key}.ktx2`));
  await f.prepare(environment);
  const stage = getStage(f), stageFloor = stage.getObjectByName(f.floor.name), travelMaterial = stageFloor.material;
  const travelSky = stage.getObjectByName(sourceSky.name).material;
  travelMaterial.addEventListener('dispose', () => releases.travel++);
  travelSky.addEventListener('dispose', () => releases.travelSky++);
  assert.notEqual(travelMaterial, sourceMaterial); assert.equal(f.floor.material, sourceMaterial);
  assert.equal(sourceMaterial.fragmentShader, sourceShader); assert.deepEqual(sourceMaterial.uniforms, sourceUniforms);
  assert.equal(sourceSky.material.fragmentShader, sourceSkyShader); assert.deepEqual(sourceSky.material.uniforms, sourceSkyUniforms);
  assert.notEqual(travelSky, sourceSky.material);
  for (const [key, value] of Object.entries(sourceUniforms)) assert.equal(travelMaterial.uniforms[key], value, `real ${key} uniform remains shared by reference`);
  for (const [key, value] of Object.entries(sourceSkyUniforms)) assert.equal(travelSky.uniforms[key], value, `real sky ${key} uniform remains shared by reference`);
  for (const shader of [nativeFloor.material, travelMaterial]) {
    assert.equal(shader.uniforms.uGalleryFloorDay.value, day); assert.equal(shader.uniforms.uGalleryFloorNight.value, night);
    assert.match(shader.fragmentShader, /vec2 galleryUv = galleryPoint \/ 64\.0 \+ 0\.5;/, 'actual KTX top-down mapping uses positive web Z');
  }
  assert.equal(day.colorSpace, THREE.SRGBColorSpace); assert.equal(night.colorSpace, THREE.SRGBColorSpace);
  assert.equal(day.anisotropy, 8); assert.equal(night.anisotropy, 8);
  assert.equal(textures['day-sky'].wrapS, THREE.RepeatWrapping); assert.equal(textures['night-sky'].wrapS, THREE.RepeatWrapping);
  for (const shader of [nativeFloor.material, galleryAtmosphere.sky.material, travelMaterial, travelSky]) {
    assert.equal(shader.uniforms.uGallerySkyDay.value, textures['day-sky']);
    assert.equal(shader.uniforms.uGallerySkyNight.value, textures['night-sky']);
  }
  assert.equal(travelMaterial.uniforms.uGallerySkyMix, travelSky.uniforms.uGallerySkyMix, 'stage floor and dome share their mix');
  assert.notEqual(travelMaterial.uniforms.uGallerySkyMix, nativeFloor.material.uniforms.uGallerySkyMix, 'native environment owns a separate mix');
  for (const returning of [false, true]) for (const progress of [0, .18, .47, .76, 1]) {
    environment.updateTravelEnvironment(progress, returning);
    const expected = smoothTravel((progress - .18) / .58);
    close([travelSky.uniforms.uGallerySkyMix.value], [returning ? 1 - expected : expected], 'actual directional sky mix');
    assert.equal(nativeFloor.material.uniforms.uGallerySkyMix.value, 1);
    assert.equal(galleryAtmosphere.sky.material.uniforms.uGallerySkyMix.value, 1);
  }
  close(nativeFloor.material.uniforms.uGalleryFloorOrigin.value, [0, 0], 'native baked floor origin');
  close(travelMaterial.uniforms.uGalleryFloorOrigin.value, [34, 1.5], 'stage baked floor origin');
  for (const point of [new THREE.Vector2(-11.1, -8.1), new THREE.Vector2(0, 0), new THREE.Vector2(11.1, 6.1)]) {
    const stagePoint = point.clone().add(new THREE.Vector2(GALLERY_OFFSET.x, GALLERY_OFFSET.z));
    const nativeUv = point.clone().sub(nativeFloor.material.uniforms.uGalleryFloorOrigin.value).divideScalar(64).addScalar(.5);
    const stageUv = stagePoint.sub(travelMaterial.uniforms.uGalleryFloorOrigin.value).divideScalar(64).addScalar(.5);
    close(stageUv, nativeUv, 'native and shared-stage baked texture coordinates');
  }
  roomAtmosphere.setTheme(true, 0); roomAtmosphere.update(10);
  assert.equal(sourceMaterial.uniforms.uTheme.value, 1, 'native theme changes immediately with zero duration');
  assert.equal(travelMaterial.uniforms.uTheme.value, 1, 'stage follows native theme without writing source uniforms');
  assert.equal(travelMaterial.uniforms.uBreathing.value, sourceMaterial.uniforms.uBreathing.value);
  let floorCount = 0, domeCount = 0;
  stage.traverse(node => { if (node.geometry === f.floor.geometry) floorCount++; if (node.geometry === sourceSky.geometry) domeCount++; });
  assert.equal(floorCount, 1); assert.equal(domeCount, 1); f.transition.dispose(); f.transition.dispose();
  assert.deepEqual(releases, { room: 0, travel: 1, travelSky: 1 }); assert.deepEqual(mapReleases, [0, 0, 0, 0]);
  environment.dispose(); environment.dispose(); assert.deepEqual(mapReleases, [1, 1, 1, 1]);
  roomAtmosphere.dispose(); galleryAtmosphere.dispose(); assert.equal(releases.room, 1);
  return { actualProvider: 'src/gallery-floor-finish.js', actualAtmosphere: 'src/exterior-atmosphere.js',
    stageFloorCount: floorCount, stageDomeCount: domeCount, mappedFixturePoints: 3, travelMaterialDisposals: [releases.travel, releases.travelSky], bakedTextureDisposals: mapReleases };
});
await check('production provider failure paths release loaded textures and unpublished travel materials', async () => {
  const renderer = { capabilities: { getMaxAnisotropy: () => 16 } };
  function maps() {
    const textures = Object.fromEntries(['day', 'night', 'day-sky', 'night-sky'].map(key => [key, new THREE.Texture()])), released = [0, 0, 0, 0];
    Object.values(textures).forEach((texture, index) => texture.addEventListener('dispose', () => released[index]++));
    return { ...textures, released, loader: { async loadAsync(url) { return textures[url.match(/\/([^/]+)\.ktx2$/)[1]]; } } };
  }
  const partial = maps();
  await assert.rejects(createGalleryFloorFinish({ ground: null, renderer,
    loader: { async loadAsync(url) { if (url.includes('/night.')) throw new Error('injected missing night map'); return partial.loader.loadAsync(url); } } }), /missing night map/);
  assert.deepEqual(partial.released, [1, 0, 1, 1], 'only successfully loaded textures are owned on partial load failure');
  const invalidGround = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShaderMaterial({ fragmentShader: 'void main() {}' }));
  const invalid = maps();
  await assert.rejects(createGalleryFloorFinish({ ground: invalidGround, sky: invalidGround, renderer, loader: invalid.loader }), /continuous atmosphere shader/);
  assert.deepEqual(invalid.released, [1, 1, 1, 1], 'native decoration failure releases all unpublished maps');
  const valid = maps(), scene = new THREE.Scene();
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial()); scene.add(ground);
  const atmosphere = createExteriorAtmosphere({ THREE, scene, ground,
    roomBounds: new THREE.Box3(new THREE.Vector3(-1, -1, -1), new THREE.Vector3(1, 1, 1)), reducedMotion: true });
  const environment = await createGalleryFloorFinish({ ground, sky: atmosphere.sky, renderer, loader: valid.loader });
  const base = invalidGround.material; let baseDisposals = 0, cloneDisposals = 0;
  base.addEventListener('dispose', () => baseDisposals++);
  const originalClone = base.clone;
  base.clone = function () { const clone = originalClone.call(this); clone.addEventListener('dispose', () => cloneDisposals++); return clone; };
  assert.throws(() => environment.createTravelFloorMaterial(base, GALLERY_OFFSET), /continuous atmosphere shader/);
  assert.throws(() => environment.createTravelSkyMaterial(base, GALLERY_OFFSET), /requires the atmosphere shader/);
  assert.equal(cloneDisposals, 2, 'both failed factories dispose their unpublished clones'); assert.equal(baseDisposals, 0);
  assert.deepEqual(valid.released, [0, 0, 0, 0], 'valid environment keeps its maps after failed travel materials');
  environment.dispose(); environment.dispose(); atmosphere.dispose();
  assert.deepEqual(valid.released, [1, 1, 1, 1]);
  return { partialLoadTextureDisposals: partial.released, nativeFailureTextureDisposals: invalid.released,
    travelFailureCloneDisposals: cloneDisposals, invalidBaseDisposals: baseDisposals };
});
await check('same-frame live transform synchronization follows room and gallery asset IDs without mutating originals', async () => {
  const f = fixture(); await f.prepare(); const stage = getStage(f);
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  let expectedRoom, expectedGallery;
  f.step(1 / 120, () => {
    f.roomPart.position.x += .15; f.roomPart.rotation.y += .2; f.roomPart.scale.set(1.2, 1.1, .9);
    f.galleryPart.position.z -= .2; f.galleryPart.rotation.x -= .3; f.galleryPart.visible = false;
    expectedRoom = transformSnapshot(f.sourceScene); expectedGallery = transformSnapshot(f.destinationScene);
    f.sourceScene.background.set('#9988aa'); f.sourceScene.fog.color.set('#887799'); f.sourceScene.fog.near = 40;
  });
  for (const original of [f.roomPart, f.galleryPart]) {
    const clone = stage.getObjectByName(original.name);
    close(clone.position, original.position, 'current position synchronized'); close(clone.quaternion, original.quaternion, 'current rotation synchronized');
    close(clone.scale, original.scale, 'current scale synchronized'); assert.equal(clone.visible, original.visible);
  }
  assert.equal(stage.background.getHex(), f.sourceScene.background.getHex()); assert.equal(stage.fog.near, 40);
  unchanged(expectedRoom, 'sync room'); unchanged(expectedGallery, 'sync gallery'); f.transition.dispose();
});
await check('full lifecycle never disposes shared model geometry, materials or textures', async () => {
  const f = fixture(), roomBefore = transformSnapshot(f.sourceScene), galleryBefore = transformSnapshot(f.destinationScene);
  const shared = new Set([f.texture]);
  for (const root of [f.sourceScene, f.destinationScene]) root.traverse(node => { if (node.isMesh) { shared.add(node.geometry); shared.add(node.material); } });
  let released = 0; shared.forEach(resource => resource.addEventListener('dispose', () => released++));
  await f.prepare();
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
  for (let i = 0; i < 40; i++) f.step(1 / 120);
  f.renderer.width = 800; f.transition.resize(); f.transition.cancel(); f.transition.dispose();
  assert.equal(released, 0, 'transition owns neither native geometry nor native material/texture disposal');
  unchanged(roomBefore, 'final room'); unchanged(galleryBefore, 'final gallery'); return { sharedResourcesObserved: shared.size, sharedDisposals: released };
});
await check('prepare: four compile passes, offscreen real stage warmup, restored renderer and no feedback', async () => {
  const f = fixture(), saved = f.renderer.snapshot(); await f.prepare(); f.renderer.assertRestored(saved);
  assert.equal(f.transition.getState().prepared, true); assert.equal(f.renderer.compiles.length, 4);
  assert.deepEqual(f.renderer.calls.map(call => call.type), ['RoomAndGalleryTravelStage', 'gallery', 'composite']);
  assert.ok(f.renderer.calls.every(call => call.target !== null), 'preparation never draws to canvas');
  const count = f.renderer.calls.length; await f.prepare(); assert.equal(f.renderer.calls.length, count);
  const composite = f.renderer.calls.at(-1); assert.notEqual(composite.composite.stage, composite.target.texture);
  f.transition.dispose(); return { compiledPasses: 4, offscreenDraws: 3, feedbackChecks: f.renderer.feedbackChecks };
});
await check('failed composite warmup restores samplers and allows same-model retry', async () => {
  const f = fixture(), saved = f.renderer.snapshot(); f.renderer.throwOn = 'composite';
  await assert.rejects(f.prepare(), /injected composite draw failure/); f.renderer.assertRestored(saved); assert.equal(f.transition.getState().prepared, false);
  await f.prepare(); f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination }); f.step(0);
  const composite = f.renderer.calls.at(-1).composite; assert.notEqual(composite.stage, composite.native); f.transition.dispose();
});
await check('gallery load retry rebuilds stage around replacement model instead of disposed old assets', async () => {
  const f = fixture(); f.renderer.throwOn = 'composite'; await assert.rejects(f.prepare(), /injected/);
  f.galleryPart.geometry.dispose(); f.galleryPart.material.dispose();
  const replacementScene = new THREE.Scene(); replacementScene.name = 'replacement-gallery';
  const replacementModel = new THREE.Group(); replacementModel.name = 'ReplacementGalleryModel'; replacementScene.add(replacementModel);
  const replacementMesh = new THREE.Mesh(new THREE.BoxGeometry(3, 2, 1), new THREE.MeshBasicMaterial());
  replacementMesh.name = 'ReplacementGalleryMesh'; replacementMesh.userData.asset_id = 'gallery.work.01'; replacementMesh.position.set(-2, 1, 2); replacementModel.add(replacementMesh);
  const callStart = f.renderer.calls.length;
  await f.transition.prepare({ sourceScene: f.sourceScene, destinationScene: replacementScene, destinationModel: replacementModel, destination: f.destination });
  const stage = f.renderer.calls.slice(callStart).find(call => call.type === 'RoomAndGalleryTravelStage').scene;
  assert.ok(stage.getObjectByName(replacementMesh.name), 'retry stage contains newly loaded gallery model');
  assert.equal(stage.getObjectByName(replacementMesh.name).geometry, replacementMesh.geometry);
  assert.equal(stage.getObjectByName(f.galleryPart.name), undefined, 'retry stage discards old disposed model'); f.transition.dispose();
});
await check('concurrent preparation is deduplicated and disposal before compilation finishes prevents draws', async () => {
  const f = fixture(); assert.equal(f.transition.run({}), false, 'unprepared stage cannot run');
  f.renderer.deferCompiles = true; const first = f.prepare(), second = f.prepare();
  assert.equal(f.renderer.compiles.length, 4); f.transition.dispose(); f.renderer.releaseCompiles(); await Promise.all([first, second]);
  assert.equal(f.renderer.calls.length, 0); assert.equal(f.transition.getState().renderTargets, 0); assert.equal(f.transition.getState().prepared, false);
  assert.equal(f.transition.run({}), false);
});
await check('30, 60 and 120 Hz use genuine shared-stage frames and commit one exact final view', async () => {
  const frameCounts = [];
  for (const fps of [30, 60, 120]) {
    const f = fixture(); await f.prepare(); vm.runInContext('setTravelBusy(true)', f.context);
    let handoffs = 0, completions = 0, middleFrames = 0; const initial = f.camera.position.clone();
    const run = { sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination,
      onHandoff() {
        handoffs++; assert.equal(f.renderer.calls.at(-1).type, 'composite'); assert.equal(f.renderer.calls.at(-1).composite.blend, 1);
        assert.equal(f.renderer.calls.at(-2).scene, f.destinationScene);
        close(f.camera.position, f.renderer.calls.at(-2).position, 'commit exactly matches last native destination', 0);
        limits(f.controls, true, f.destination.maxDistance);
      }, onComplete() { completions++; vm.runInContext('setTravelBusy(false)', f.context); } };
    assert.equal(f.transition.run(run), true); assert.equal(f.transition.run(run), false); f.step(0);
    close(f.renderer.calls.at(-2).position, initial, 'first native source frame matches visible camera', 0);
    while (f.transition.getState().active) {
      const start = f.renderer.calls.length; f.step(1 / fps);
      const calls = f.renderer.calls.slice(start), progress = f.transition.getState().progress;
      assert.equal(calls[0].type, 'RoomAndGalleryTravelStage'); assert.equal(calls.at(-1).type, 'composite');
      if (progress > .2 && progress < .74) {
        middleFrames++; assert.equal(calls.length, 2, 'middle travel draws shared 3D stage and final pass only');
        assert.equal(calls.at(-1).composite.blend, 0, 'native environment blend is zero in middle');
        assert.deepEqual(calls.at(-1).composite.uniformNames.sort(), ['uBlend', 'uNative', 'uStage']);
      }
      if (f.transition.getState().active) { assert.equal(handoffs, 0); close(f.camera.position, initial, 'main camera is not committed early', 0); }
    }
    assert.ok(middleFrames > 0); assert.equal(handoffs, 1); assert.equal(completions, 1); assert.equal(f.step(1 / fps), false);
    assert.equal(f.classes.has('is-scene-travelling'), false); f.stability();
    assert.equal(f.transition.getState().lastRun.duration, 2.15, 'quicker passage keeps one shared timeline');
    frameCounts.push({ fps, frames: f.transition.getState().lastRun.frames, sharedStageOnlyFrames: middleFrames }); f.transition.dispose();
  }
  return { frameCounts, postCommitControlFrames: 120 };
});
await check('production return keeps saved near-room pose and hands off controls with no movement', async () => {
  const f = fixture(); await f.prepare();
  const saved = { position: new THREE.Vector3(1.5, 2.5, 0), target: new THREE.Vector3(-1.5, .5, -Math.sqrt(12)), maxDistance: 45, aspect: f.camera.aspect };
  f.camera.position.copy(f.destination.position); f.controls.target.copy(f.destination.target); limits(f.controls, true, f.destination.maxDistance); f.controls.update();
  f.context.state.currentScene = 'gallery'; f.context.savedRoomPose = saved; f.context.requestedPose = saved;
  vm.runInContext("travelToScene('room', requestedPose)", f.context); f.finish();
  close(f.camera.position, saved.position, 'saved near room pose'); close(f.controls.target, saved.target, 'saved room target');
  assert.equal(f.context.state.currentScene, 'room'); assert.equal(f.context.state.transitioning, false); assert.equal(f.context.canvas.focused, 1);
  assert.equal(f.context.roomCameraGuard.resets, 1); assert.ok(Math.abs(f.camera.position.distanceTo(f.controls.target) - 5) < EPS); f.stability(); f.transition.dispose();
  return { finalDistance: 5, guardResets: 1, commitCount: 1 };
});
await check('production mid-travel resize updates destination once and final native pose remains stable', async () => {
  const f = fixture(); await f.prepare(); f.context.requestedPose = f.destination; vm.runInContext("travelToScene('gallery', requestedPose)", f.context);
  for (let i = 0; i < 80; i++) f.step(1 / 120); const before = f.transition.getState().progress;
  f.camera.aspect = .65; f.camera.updateProjectionMatrix(); f.renderer.width = 650; f.renderer.height = 1000; f.transition.resize();
  assert.equal(f.transition.getState().progress, before); f.step(0); assert.equal(f.transition.getState().progress, before);
  close(f.transition.getState().renderTargetSize, [1300, 2000], 'drawing buffer targets resized'); f.finish();
  close(f.camera.position, f.galleryPose(.65).position, 'newly fitted destination'); assert.equal(f.transition.getState().lastRun.resized, true);
  assert.equal(f.context.canvas.focused, 1); assert.equal(f.context.roomCameraGuard.resets, 1); f.stability(); f.transition.dispose();
});
await check('return adapts to viewport changed before travel starts, with exact offset projection', async () => {
  const f = fixture(); await f.prepare(); const saved = { ...f.source, position: f.source.position.clone(), target: f.source.target.clone(), aspect: 1.6 };
  f.camera.aspect = .8; f.camera.updateProjectionMatrix(); const gallery = f.galleryPose(.8);
  f.camera.position.copy(gallery.position); f.controls.target.copy(gallery.target); limits(f.controls, true, gallery.maxDistance); f.controls.update();
  f.context.state.currentScene = 'gallery'; f.context.savedRoomPose = saved; f.context.requestedPose = saved;
  vm.runInContext("travelToScene('room', requestedPose)", f.context); f.finish();
  close(f.camera.position, saved.position.clone().sub(saved.target).multiplyScalar(2).add(saved.target), 'saved room framing adapts on first resolve');
  f.stability(); f.transition.dispose();
});
await check('atelier uses its own floor offset, keeps assets grounded, and restores room controls', async () => {
  const model = readRoomGeometry('/models/about-atelier-v3-compressed.glb').room;
  const framing = createAboutFraming(model);
  const f = fixture({ pose: framing.pose });
  const offset = new THREE.Vector3(-34, -1.055, 1.5);
  await f.transition.prepare({ sourceScene: f.sourceScene, destinationScene: f.destinationScene,
    destinationModel: f.destinationModel, destination: f.destination, offset });
  f.context.aboutAtelier = f.context.worksGallery;
  f.context.aboutTransition = f.transition;
  f.context.requestedPose = f.destination;
  f.context.savedRoomPose = f.source;
  vm.runInContext("travelToScene('about', requestedPose)", f.context);
  f.finish();
  assert.equal(f.context.state.currentScene, 'about');
  assert.equal(f.controls.enablePan, false);
  assert.equal(f.controls.enabled, true);
  close(f.camera.position, f.destination.position, 'atelier authored framing');
  close(f.transition.getState().stageOffset, offset, 'atelier dock height');
  const stage = getStage(f), berth = stage.children.find(node => node.children.includes(node.getObjectByName('GalleryFixtureModel')));
  assert.ok(berth); close(berth.position, offset, 'stage berth on matching floor');
  const view = poseSample(f.source, f.destination, 1, { offset });
  close(view.stageCamera.position, f.destination.position.clone().add(offset), 'stage arrival matches translated model');
  close(view.destinationCamera.position, f.destination.position, 'native arrival has no camera jump');
  f.stability();
  f.context.requestedPose = f.source;
  vm.runInContext("travelToScene('room', requestedPose)", f.context);
  f.finish();
  assert.equal(f.context.state.currentScene, 'room');
  assert.equal(f.controls.enablePan, true);
  close(f.camera.position, f.source.position, 'saved room framing restored');
  f.stability(); f.transition.dispose();
  return { independentAssets: 128, offset: offset.toArray(), nativeHandoff: 'exact', panRestored: true };
});
await check('cancel early, mid-flight and late prevents commits and allows a fresh run', async () => {
  for (const fraction of [.05, .5, .95]) {
    const f = fixture(); await f.prepare(); let callbacks = 0;
    const run = { sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination,
      onHandoff: () => callbacks++, onComplete: () => callbacks++ };
    f.transition.run(run); while (f.transition.getState().progress < fraction) f.step(1 / 120);
    f.transition.cancel(); f.transition.cancel(); assert.equal(f.step(.05), false); assert.equal(callbacks, 0);
    close(f.camera.position, f.source.position, 'cancel retains native source pose'); assert.equal(f.classes.has('is-scene-travelling'), false);
    assert.equal(f.transition.run(run), true); f.finish(); assert.equal(callbacks, 2); f.transition.dispose();
  }
});
await check('reduced motion renders stationary native views and one short dissolve commit', async () => {
  const f = fixture({ reducedMotion: true }); await f.prepare(); let handoffs = 0, completes = 0;
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination,
    onHandoff() { handoffs++; limits(f.controls, true, f.destination.maxDistance); }, onComplete() { completes++; } });
  while (f.transition.getState().active) {
    const start = f.renderer.calls.length; f.step(1 / 120); const calls = f.renderer.calls.slice(start);
    assert.deepEqual(calls.map(call => call.type), ['room', 'gallery', 'composite']);
    close(calls[0].position, f.source.position, 'reduced source stationary', 0); close(calls[1].position, f.destination.position, 'reduced destination stationary', 0);
  }
  assert.equal(handoffs, 1); assert.equal(completes, 1); assert.equal(f.transition.getState().lastRun.duration, .32); f.stability(); f.transition.dispose();
});
await check('long and invalid deltas cannot skip passage or reverse elapsed time', async () => {
  const f = fixture(); await f.prepare(); let commits = 0;
  f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination, onHandoff: () => commits++ });
  for (const delta of [0, -1, NaN]) { const p = f.transition.getState().progress; f.step(delta); assert.equal(f.transition.getState().progress, p); }
  f.step(10); assert.ok(f.transition.getState().progress < .024); assert.equal(commits, 0);
  f.finish(10); assert.equal(commits, 1); assert.ok(f.transition.getState().lastRun.frames >= 43); f.transition.dispose();
});
await check('renderer state restores after shared-stage, native or composite render exceptions', async () => {
  for (const type of ['RoomAndGalleryTravelStage', 'room', 'composite']) {
    const f = fixture(); await f.prepare(); f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination });
    const saved = f.renderer.snapshot(); f.renderer.throwOn = type;
    assert.throws(() => f.transition.render(1 / 120), /injected/); f.renderer.assertRestored(saved); f.transition.dispose();
  }
});
await check('target formats match capabilities and disposal releases only owned render targets', async () => {
  const choices = [];
  for (const [float, ratio] of [[true, 2], [false, 1]]) {
    const f = fixture({ float, ratio }); await f.prepare(); const target = f.renderer.calls[0].target, other = f.renderer.calls[1].target;
    assert.equal(target.texture.type, float ? THREE.HalfFloatType : THREE.UnsignedByteType); assert.equal(target.samples, ratio < 1.5 ? 2 : 0);
    let disposed = 0; target.addEventListener('dispose', () => disposed++); other.addEventListener('dispose', () => disposed++);
    f.transition.run({ sourceScene: f.sourceScene, destinationScene: f.destinationScene, destination: f.destination }); f.step(0); f.transition.dispose();
    assert.equal(disposed, 2); assert.equal(f.transition.getState().renderTargets, 0); assert.equal(f.transition.getState().active, false); assert.equal(f.step(.05), false);
    choices.push({ float, ratio, samples: target.samples });
  }
  return { choices };
});
await check('actual production inertia flush clears residual orbit, pan and dolly without moving visible pose', () => {
  const f = fixture(); f.controls._sphericalDelta.theta = .12; f.controls._sphericalDelta.phi = -.04;
  f.controls._panOffset.set(.15, .03, -.2); f.controls._dollyIn(.97);
  const position = f.camera.position.clone(), target = f.controls.target.clone(), quaternion = f.camera.quaternion.clone();
  vm.runInContext('setTravelBusy(true)', f.context);
  close(f.camera.position, position, 'camera preserved', 0); close(f.controls.target, target, 'target preserved', 0);
  assert.ok(f.camera.quaternion.angleTo(quaternion) < 1e-7); assert.equal(f.controls._sphericalDelta.theta, 0); assert.equal(f.controls._sphericalDelta.phi, 0);
  assert.equal(f.controls._panOffset.lengthSq(), 0); assert.equal(f.controls._scale, 1); assert.equal(f.controls.enabled, false);
  vm.runInContext('setTravelBusy(false)', f.context); f.stability(); close(f.camera.position, position, 'release without jump', 1e-8);
  assert.equal(f.controls.enabled, true); assert.equal(f.controls.enableDamping, true); f.transition.dispose(); return { cameraJump: 0 };
});

await check('closer gallery arrival fits the real corridor on desktop and portrait with camera clearance', () => {
  const f = fixture(), { room, components } = readRoomGeometry('/models/works-gallery-v4-compressed.glb');
  // The surrounding terrace is a background apron. Fit the complete corridor,
  // including its own base, return portal and all exhibit assets.
  const excludedBackground = [];
  for (const [id, node] of components) if (id.startsWith('gallery.environment.')) {
    excludedBackground.push(id); node.removeFromParent();
  }
  const realBounds = new THREE.Box3().setFromObject(room, true);
  const actualVertices = [];
  room.traverse(node => {
    if (!node.isMesh) return;
    const positions = node.geometry.attributes.position;
    for (let index = 0; index < positions.count; index++) actualVertices.push(new THREE.Vector3().fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld));
  });
  const results = [];
  for (const [width, height] of [[1920, 1080], [1440, 900], [844, 795], [390, 844], [320, 740]]) {
    const pose = f.galleryPose(width / height), camera = new THREE.PerspectiveCamera(35, width / height, .1, 500);
    camera.position.copy(pose.position); camera.lookAt(pose.target); camera.updateMatrixWorld(true);
    const projected = new THREE.Box3();
    // The new fit deliberately omits unoccupied box corners. Check every real
    // authored vertex instead of requiring imaginary roof-front corners to fit.
    for (const vertex of actualVertices) projected.expandByPoint(vertex.clone().project(camera));
    assert.ok(projected.min.x > -1 && projected.max.x < 1, 'full real model fits horizontally');
    assert.ok(projected.min.y >= -.82001 && projected.max.y <= .82001, 'real geometry leaves the requested vertical UI space');
    assert.ok(projected.min.z > -1 && projected.max.z < 1, 'near/far planes do not cut the model');
    const clearance = realBounds.distanceToPoint(camera.position);
    assert.ok(clearance > 10, 'arrival camera stays outside the model');
    results.push({ viewport: [width, height], cameraDistance: camera.position.distanceTo(pose.target), clearance,
      projectedBounds: { min: projected.min.toArray(), max: projected.max.toArray() } });
  }
  f.transition.dispose(); return { model: galleryModelUrl, actualVertices: actualVertices.length, excludedBackground, views: results };
});

if (originalDocument === undefined) delete globalThis.document; else globalThis.document = originalDocument;
const files = ['src/gallery-transition.js', 'src/gallery-transition-path.js', 'src/gallery-framing.js', 'src/gallery-floor-finish.js', 'src/exterior-atmosphere.js', 'src/main.js', 'src/works-gallery.js', 'src/utils/OrbitControls.js'];
const sha256 = Object.fromEntries(files.map(file => [file, createHash('sha256').update(readFileSync(new URL(`../${file}`, import.meta.url))).digest('hex')]));
const report = { revision: 4, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Real Three.js objects, production shared-stage/path modules, actual custom OrbitControls, production atmosphere/floor-finish modules, and production main lifecycle functions isolated in VM. DOM, renderer and texture loading are simulated; controlled provider fixtures supplement a real provider check. Tests validate physical model offsets, perspective projection equivalence, resource ownership, optional material replacement, lifecycle, renderer state, and sampler separation. No GPU performance or rendered image-quality claim is made.',
  sourceSha256: sha256, checks: results.length, passed: results.filter(result => result.status === 'passed').length,
  failed: results.filter(result => result.status === 'failed').length, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(new URL('../docs/validation/', import.meta.url), { recursive: true });
  writeFileSync(new URL('../docs/validation/gallery-transition-v4.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed,
  failures: results.filter(result => result.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
