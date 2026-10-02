import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createStartupReadiness, warmSceneForStartup, waitForStartupGpu } from '../src/startup-readiness.js';

// These checks exercise production control flow with real Three.js scene,
// material and texture objects. The renderer, frame clock and GL completion
// results are explicit CPU substitutes; no browser or GPU work is claimed.
const checks = [];
async function check(name, run) {
  try { checks.push({ name, passed: true, ...await run() }); }
  catch (error) { checks.push({ name, passed: false, error: error.stack ?? String(error) }); }
}
const stages = ['room', 'gallery', 'about', 'warmup'];

await check('Every incomplete combination of stages blocks welcome and 100%', () => {
  for (let mask = 0; mask < 15; mask++) {
    const emitted = [], gate = createStartupReadiness({ onUpdate: state => emitted.push(state) });
    stages.forEach((id, index) => gate.update(id, mask & (1 << index) ? 1 : .999, id));
    assert.throws(() => gate.finish(), /must complete before welcome/);
    assert.equal(gate.getState().ready, false);
    assert.ok(gate.getState().percent < 100);
    assert.ok(emitted.every(state => state.percent < 100 && !state.ready));
  }
  return { incompleteStageCombinations: 15 };
});

await check('Completing all stages still needs explicit finish; late progress cannot undo readiness', () => {
  const emitted = [], gate = createStartupReadiness({ onUpdate: state => emitted.push(state) });
  for (const id of ['warmup', 'about', 'room', 'gallery']) gate.update(id, 1, id);
  assert.equal(gate.getState().percent, 99);
  assert.equal(gate.getState().ready, false);
  gate.finish();
  const final = gate.getState();
  assert.equal(final.percent, 100);
  assert.equal(final.ready, true);
  assert.ok(final.stages.every(stage => stage.state === 'ready'));
  gate.update('room', 0, 'late download event');
  assert.deepEqual(gate.getState(), final);
  assert.equal(emitted.filter(state => state.percent === 100).length, 1);
});

await check('Failure at any preparation stage cannot become ready after late success events', () => {
  for (const failedId of stages) {
    const gate = createStartupReadiness();
    for (const id of stages) gate.update(id, id === failedId ? .7 : 1);
    gate.fail(`controlled ${failedId} failure`);
    const failed = gate.getState();
    for (const id of stages) gate.update(id, 1, 'late success');
    assert.throws(() => gate.finish(), /must complete before welcome/);
    assert.deepEqual(gate.getState(), failed);
    assert.equal(failed.ready, false);
    assert.ok(failed.percent < 100);
  }
  const completed = createStartupReadiness();
  for (const id of stages) completed.update(id, 1);
  completed.finish(); completed.fail('late startup failure');
  assert.equal(completed.getState().ready, false);
  assert.throws(() => completed.finish(), /must complete before welcome/);
});

await check('Out-of-order and invalid progress cannot move an individual stage or total backwards', () => {
  const gate = createStartupReadiness();
  const events = [
    ['gallery', .6], ['room', .8], ['room', .1], ['about', .5], ['gallery', -.3],
    ['room', NaN], ['gallery', Infinity], ['about', undefined], ['warmup', .8],
    ['about', 3], ['about', .2], ['room', 1], ['gallery', 1], ['warmup', .3], ['warmup', 1],
  ];
  let previous = gate.getState();
  for (const [id, progress] of events) {
    gate.update(id, progress);
    const next = gate.getState();
    assert.ok(Number.isFinite(next.percent) && next.percent >= previous.percent && next.percent < 100);
    next.stages.forEach((stage, index) => {
      assert.ok(stage.progress >= previous.stages[index].progress && stage.progress <= 1);
      if (previous.stages[index].state === 'ready') assert.equal(stage.state, 'ready');
    });
    previous = next;
  }
  assert.throws(() => gate.update('unknown', .5), /Unknown startup stage/);
  const detachedSnapshot = gate.getState();
  detachedSnapshot.stages[0].progress = 0;
  assert.equal(gate.getState().stages[0].progress, 1);
  gate.finish(); assert.equal(gate.getState().ready, true);
  return { progressEvents: events.length };
});

async function withFrameClock(run, frameStep = 16) {
  const originalFrame = Object.getOwnPropertyDescriptor(globalThis, 'requestAnimationFrame');
  const originalPerformance = Object.getOwnPropertyDescriptor(globalThis, 'performance');
  const clock = { frames: 0, milliseconds: 0 };
  Object.defineProperty(globalThis, 'performance', { configurable: true, value: { now: () => clock.milliseconds } });
  Object.defineProperty(globalThis, 'requestAnimationFrame', { configurable: true, value: callback => {
    const id = ++clock.frames;
    queueMicrotask(() => { clock.milliseconds += frameStep; callback(clock.milliseconds); });
    return id;
  } });
  try { return await run(clock); }
  finally {
    for (const [key, descriptor] of [['requestAnimationFrame', originalFrame], ['performance', originalPerformance]]) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key];
    }
  }
}

function warmFixture({ failCompileAt = 0, failRenderAt = 0, failUpload = false, defaultFramebuffer = false, resizeDuringCompile = null } = {}) {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, 1.5, .1, 100);
  const map = new THREE.Texture(), normal = new THREE.Texture(), extra = new THREE.Texture();
  const renderTarget = new THREE.WebGLRenderTarget(32, 32);
  const mix = { value: .37 };
  const basic = new THREE.MeshBasicMaterial({ map, color: 0x987654, transparent: true, opacity: .71 });
  const pbr = new THREE.MeshStandardMaterial({ map, normalMap: normal, roughness: .63, metalness: .42 });
  const custom = new THREE.ShaderMaterial({ uniforms: {
    shared: { value: map }, images: { value: [normal, [extra, map]] },
    target: { value: renderTarget.texture }, dayMix: mix,
  } });
  const geometry = new THREE.BoxGeometry();
  const first = new THREE.Mesh(geometry, basic), second = new THREE.Mesh(geometry, [pbr, custom]);
  const hidden = new THREE.Mesh(geometry, custom); hidden.visible = false;
  second.frustumCulled = false;
  const nested = new THREE.Group(); nested.add(second, hidden); scene.add(first, nested);
  const meshes = [first, second, hidden];
  const meshState = meshes.map(mesh => ({ mesh, material: mesh.material, visible: mesh.visible, frustumCulled: mesh.frustumCulled }));
  const materialState = [basic, pbr, custom].map(material => ({ material, color: material.color?.toArray(),
    opacity: material.opacity, roughness: material.roughness, metalness: material.metalness,
    map: material.map, normalMap: material.normalMap, uniforms: material.uniforms,
    onBeforeCompile: material.onBeforeCompile, cacheKey: material.customProgramCacheKey, version: material.version }));
  const rendererState = { target: defaultFramebuffer ? null : renderTarget, size: new THREE.Vector2(120, 80), viewport: new THREE.Vector4(7, 9, 73, 51), scissor: new THREE.Vector4(3, 5, 41, 29), scissorTest: true, autoClear: false };
  const originalRenderer = { ...rendererState, size: rendererState.size.clone(), viewport: rendererState.viewport.clone(), scissor: rendererState.scissor.clone() };
  const uploads = [], compilations = [], renders = [], mixEvents = [];
  let disposals = 0;
  for (const resource of [map, normal, extra, basic, pbr, custom, geometry, renderTarget]) resource.addEventListener('dispose', () => disposals++);
  const assertWarmState = () => {
    assert.equal(rendererState.target, null); assert.equal(rendererState.scissorTest, false); assert.equal(rendererState.autoClear, true);
    for (const mesh of meshes) assert.equal(mesh.frustumCulled, false);
    assert.equal(hidden.visible, false, 'preparation must not rewrite authored visibility');
  };
  const renderer = {
    get autoClear() { return rendererState.autoClear; }, set autoClear(value) { rendererState.autoClear = value; },
    getSize: target => target.copy(rendererState.size),
    setSize(width, height) { rendererState.size.set(width, height); rendererState.viewport.set(0, 0, width, height); },
    getRenderTarget: () => rendererState.target,
    setRenderTarget(value) { rendererState.target = value; rendererState.viewport.set(0, 0, rendererState.size.x, rendererState.size.y); rendererState.scissor.set(0, 0, rendererState.size.x, rendererState.size.y); },
    getViewport: target => target.copy(rendererState.viewport),
    setViewport: (value, y, width, height) => value?.isVector4 ? rendererState.viewport.copy(value) : rendererState.viewport.set(value, y, width, height),
    getScissor: target => target.copy(rendererState.scissor),
    setScissor: (value, y, width, height) => value?.isVector4 ? rendererState.scissor.copy(value) : rendererState.scissor.set(value, y, width, height),
    getScissorTest: () => rendererState.scissorTest, setScissorTest: value => { rendererState.scissorTest = value; },
    initTexture(texture) { uploads.push(texture); if (failUpload && texture === normal) throw new Error('controlled upload failure'); },
    async compileAsync(currentScene, currentCamera) {
      assert.equal(currentScene, scene); assert.equal(currentCamera, camera); assertWarmState(); compilations.push(mix.value);
      if (resizeDuringCompile && compilations.length === 1) {
        // Model a resize event arriving while the compile promise is pending.
        // Resolving it afterwards exercises restoration across that await.
        await new Promise(resolve => queueMicrotask(() => { renderer.setSize(...resizeDuringCompile); resolve(); }));
      }
      if (compilations.length === failCompileAt) throw new Error('controlled compile failure');
    },
    render(currentScene, currentCamera) {
      assert.equal(currentScene, scene); assert.equal(currentCamera, camera); assertWarmState(); renders.push(mix.value);
      if (renders.length === failRenderAt) throw new Error('controlled render failure');
    },
  };
  const setDayMix = value => { mix.value = value; mixEvents.push(value); };
  const assertRestored = (expectedRendererChanges = {}) => {
    assert.deepEqual(rendererState, { ...originalRenderer, ...expectedRendererChanges });
    assert.equal(mix.value, .37);
    for (const saved of meshState) {
      assert.equal(saved.mesh.material, saved.material); assert.equal(saved.mesh.visible, saved.visible); assert.equal(saved.mesh.frustumCulled, saved.frustumCulled);
    }
    for (const saved of materialState) {
      const { material } = saved;
      assert.deepEqual(material.color?.toArray(), saved.color);
      for (const property of ['opacity', 'roughness', 'metalness', 'map', 'normalMap', 'uniforms', 'onBeforeCompile', 'version']) assert.equal(material[property], saved[property]);
      assert.equal(material.customProgramCacheKey, saved.cacheKey);
    }
    assert.equal(disposals, 0, 'the warmer must not dispose borrowed scene resources');
  };
  const run = () => warmSceneForStartup({ THREE, renderer, scene, camera, setDayMix, restoreMix: .37 });
  const dispose = () => { [map, normal, extra, basic, pbr, custom, geometry, renderTarget].forEach(resource => resource.dispose()); };
  return { run, assertRestored, dispose, uploads, compilations, renders, mixEvents, expectedTextures: new Set([map, normal, extra]), renderTarget };
}

await check('Warmer finds native maps and nested uniform arrays once, skips render targets, renders both endpoints and restores all borrowed state', () => withFrameClock(async clock => {
  const f = warmFixture();
  try {
    await f.run(); f.assertRestored();
    assert.deepEqual(new Set(f.uploads), f.expectedTextures);
    assert.equal(f.uploads.length, f.expectedTextures.size);
    assert.ok(!f.uploads.includes(f.renderTarget.texture));
    assert.deepEqual(f.compilations, [1, 0]); assert.deepEqual(f.renders, [1, 0]);
    assert.deepEqual(f.mixEvents, [1, 0, .37]); assert.equal(clock.frames, 2);
    return { uniqueTextureUploads: f.uploads.length, renderedDayMix: f.renders };
  } finally { f.dispose(); }
}));

for (const compileAt of [1, 2]) await check(`Compilation failure at endpoint ${compileAt} restores renderer, frustum flags, material identity and day/night mix`, () => withFrameClock(async () => {
  const f = warmFixture({ failCompileAt: compileAt });
  try {
    await assert.rejects(f.run(), /controlled compile failure/); f.assertRestored();
    assert.equal(f.renders.length, compileAt - 1);
    assert.equal(f.mixEvents.at(-1), .37);
  } finally { f.dispose(); }
}));

for (const failure of ['upload', 'render']) await check(`${failure} failure also restores borrowed scene and renderer state`, () => withFrameClock(async () => {
  const f = warmFixture(failure === 'upload' ? { failUpload: true } : { failRenderAt: 2 });
  try { await assert.rejects(f.run(), new RegExp(`controlled ${failure} failure`)); f.assertRestored(); }
  finally { f.dispose(); }
}));

for (const failed of [false, true]) await check(`Resize during pending compilation restores the new default-framebuffer viewport and scissor after ${failed ? 'failure' : 'success'}`, () => withFrameClock(async () => {
  const newSize = [860, 560];
  const f = warmFixture({ defaultFramebuffer: true, resizeDuringCompile: newSize, failCompileAt: failed ? 1 : 0 });
  try {
    if (failed) await assert.rejects(f.run(), /controlled compile failure/); else await f.run();
    f.assertRestored({ size: new THREE.Vector2(...newSize), viewport: new THREE.Vector4(0, 0, ...newSize), scissor: new THREE.Vector4(0, 0, ...newSize) });
    assert.deepEqual(f.compilations, failed ? [1] : [1, 0]);
    assert.equal(f.mixEvents.at(-1), .37);
    return { framebuffer: 'default', newViewport: [0, 0, ...newSize], resizedWhileCompilePending: true };
  } finally { f.dispose(); }
}));

await check('Resize during compilation retains a borrowed offscreen target and its saved viewport/scissor', () => withFrameClock(async () => {
  const f = warmFixture({ resizeDuringCompile: [860, 560] });
  try {
    await f.run();
    f.assertRestored({ size: new THREE.Vector2(860, 560) });
  } finally { f.dispose(); }
}));

function glFixture(statuses, { contextLost = false, nullFence = false, pollThrows = false } = {}) {
  const fence = {}, events = [];
  const gl = {
    SYNC_GPU_COMMANDS_COMPLETE: 0x9117, ALREADY_SIGNALED: 0x911a, CONDITION_SATISFIED: 0x911c,
    TIMEOUT_EXPIRED: 0x911b, WAIT_FAILED: 0x911d,
    fenceSync(condition, flags) { assert.equal(condition, this.SYNC_GPU_COMMANDS_COMPLETE); assert.equal(flags, 0); events.push('create'); return nullFence ? null : fence; },
    flush() { events.push('flush'); },
    clientWaitSync(value, flags, timeout) {
      assert.equal(value, fence); assert.equal(flags, 0); assert.equal(timeout, 0);
      events.push('poll'); if (pollThrows) throw new Error('controlled fence polling failure');
      return statuses.length ? statuses.shift() : this.TIMEOUT_EXPIRED;
    },
    isContextLost: () => contextLost,
    deleteSync(value) { assert.equal(value, fence); events.push('delete'); },
  };
  return { gl, events, renderer: { getContext: () => gl } };
}

for (const endpoint of ['ALREADY_SIGNALED', 'CONDITION_SATISFIED']) await check(`GPU fence ${endpoint} waits across unsignalled frames and deletes its handle once`, () => withFrameClock(async clock => {
  const statuses = [], f = glFixture(statuses);
  statuses.push(f.gl.TIMEOUT_EXPIRED, f.gl.TIMEOUT_EXPIRED, f.gl[endpoint]);
  await waitForStartupGpu(f.renderer);
  assert.deepEqual(f.events, ['create', 'flush', 'poll', 'poll', 'poll', 'delete']);
  assert.equal(clock.frames, 2);
}));

await check('GPU WAIT_FAILED aborts welcome and always releases the fence', () => withFrameClock(async clock => {
  const statuses = [], f = glFixture(statuses); statuses.push(f.gl.WAIT_FAILED);
  await assert.rejects(waitForStartupGpu(f.renderer), /GPU preparation failed/);
  assert.deepEqual(f.events, ['create', 'flush', 'poll', 'delete']); assert.equal(clock.frames, 0);
}));

for (const kind of ['context-loss', 'poll-exception', 'timeout']) await check(`GPU ${kind} rejects and releases the completion fence`, () => withFrameClock(async () => {
  const f = glFixture([], { contextLost: kind === 'context-loss', pollThrows: kind === 'poll-exception' });
  const expected = kind === 'timeout' ? /timed out/ : kind === 'poll-exception' ? /controlled fence polling failure/ : /GPU preparation failed/;
  await assert.rejects(waitForStartupGpu(f.renderer), expected);
  assert.equal(f.events.filter(event => event === 'delete').length, 1);
  assert.equal(f.events.at(-1), 'delete');
}, kind === 'timeout' ? 31000 : 16));

await check('Unavailable GPU fence fails immediately without flushing or deleting a nonexistent handle', async () => {
  const f = glFixture([], { nullFence: true });
  await assert.rejects(waitForStartupGpu(f.renderer), /could not create/);
  assert.deepEqual(f.events, ['create']);
});

await check('Contexts without fenceSync use the explicit finish fallback exactly once', async () => {
  let finishes = 0;
  await waitForStartupGpu({ getContext: () => ({ finish() { finishes++; } }) });
  assert.equal(finishes, 1);
});

const failed = checks.filter(result => !result.passed);
console.log(JSON.stringify({ complete: failed.length === 0, passed: checks.length - failed.length, failed: failed.length, checks,
  scope: 'CPU execution of the production startup gate and restoration/fence control flow, with real Three.js scene/material/texture objects and explicit fake renderer, GL statuses and frame clock. No actual WebGL compilation, texture upload, GPU timing, browser layout, visual acceptance or smooth-transition guarantee is claimed. No report files are written.' }, null, 2));
if (failed.length) process.exitCode = 1;
