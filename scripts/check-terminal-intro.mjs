import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import * as THREE from 'three';
import { parseModelForCPU, introFixture, emit } from './lib/intro-controller-fixture.mjs';

const file = path => new URL(`../${path}`, import.meta.url);
const modelPath = 'public/models/welcome-terminal-v1.glb';
const roomPath = 'public/models/orbital-atelier-v16.glb';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const source = readFileSync(file('src/cube-intro.js'), 'utf8');
const main = readFileSync(file('src/main.js'), 'utf8');
const checks = [];
const close = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
async function check(name, fn) {
  try { checks.push({ check: name, status: 'passed', ...await fn() }); }
  catch (error) { checks.push({ check: name, status: 'failed', error: error.stack }); }
}
async function fixture(options = {}) {
  const [welcomeGltf, roomGltf] = await Promise.all([parseModelForCPU(modelPath), parseModelForCPU(roomPath)]);
  return introFixture({ welcomeGltf, roomGltf, ...options });
}
const model = await parseModelForCPU(modelPath);
const authored = new Map(); model.scene.traverse(node => authored.set(node.userData.name ?? node.name, node));

await check('real Blender GLB has independent seed groups, a real opening clip and colored PBR materials', () => {
  assert.equal(model.bytes.readUInt32LE(0), 0x46546c67); assert.equal(model.bytes.length, model.bytes.readUInt32LE(8));
  for (const name of ['seed.base', 'seed.lid', 'seed.dial']) assert.ok(authored.has(name), `${name}: authored group survives GLTFLoader`);
  const clips = model.animations.filter(clip => clip.name === 'TerminalUnfold'); assert.equal(clips.length, 1);
  assert.ok(clips[0].duration > 0 && clips[0].tracks.length > 0);
  const meshes = [], materials = new Set(); model.scene.traverse(node => {
    if (node.isMesh) { meshes.push(node); [].concat(node.material).forEach(material => materials.add(material)); }
  });
  const triangles = meshes.reduce((sum, node) => sum + (node.geometry.index?.count ?? node.geometry.attributes.position.count) / 3, 0);
  assert.ok(triangles > 0 && triangles < 60000); assert.ok(model.bytes.length < 8 * 1024 * 1024);
  assert.ok([...materials].some(material => material.color.r > material.color.b * 1.4), 'warm orange exists in the actual material palette');
  assert.ok([...materials].some(material => material.color.b > material.color.r * 1.25), 'navy blue exists in the actual material palette');
  assert.ok([...materials].some(material => material.map || material.emissiveMap), 'screen artwork is mapped instead of an untextured gray placeholder');
  return { bytes: model.bytes.length, meshes: meshes.length, triangles, clipDuration: clips[0].duration,
    tracks: clips[0].tracks.map(track => track.name), materials: [...materials].map(material => ({ name: material.name, color: material.color.toArray(), metalness: material.metalness, mapped: !!(material.map || material.emissiveMap) })) };
});

await check('welcome keeps the whole room hidden and never rewrites its bake colors, maps or compile hooks', async () => {
  const roomGltf = await parseModelForCPU(roomPath), welcomeGltf = await parseModelForCPU(modelPath);
  const original = new Map(); roomGltf.scene.traverse(node => {
    if (node.isMesh) for (const material of [].concat(node.material)) original.set(material, {
      color: material.color?.clone(), map: material.map, opacity: material.opacity, transparent: material.transparent,
      compile: material.onBeforeCompile, cache: material.customProgramCacheKey,
    });
  });
  const f = introFixture({ welcomeGltf, roomGltf });
  try {
    assert.equal(f.room.visible, false, 'no complete room flashes through the welcome stage');
    const welcome = f.ready(); welcome.progress(1); f.intro.update(); assert.equal(f.room.visible, false);
    for (const [material, expected] of original) {
      if (expected.color) assert.deepEqual(material.color.toArray(), expected.color.toArray());
      assert.equal(material.map, expected.map); assert.equal(material.opacity, expected.opacity);
      assert.equal(material.transparent, expected.transparent); assert.equal(material.onBeforeCompile, expected.compile);
      assert.equal(material.customProgramCacheKey, expected.cache);
    }
    const entry = f.enter(); entry.time(.1); f.intro.update(); assert.equal(f.room.visible, false, 'entry begins with the small terminal, not the room');
    f.intro.skip(); f.assertRestored();
    return { materialsPreserved: original.size, welcomeRoomVisible: false };
  } finally { f.cleanup(); }
});

await check('actual production controller and GSAP accept first down-wheel once and release scroll lock after completion', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); f.intro.update();
    for (const deltaY of [-50, 0]) assert.equal(emit(f.view, 'wheel', { deltaY }).defaultPrevented, true);
    assert.equal(f.intro.getState().phase, 'welcome');
    const entry = f.enter('wheel');
    for (const deltaY of [5, 500, -800]) assert.equal(emit(f.view, 'wheel', { deltaY }).defaultPrevented, true);
    emit(f.element.querySelector('.intro-enter'), 'click');
    for (const key of ['ArrowDown', 'PageDown', ' ']) emit(f.view, 'keydown', { key });
    assert.equal(f.counts.start, 1); assert.equal(f.controls.enabled, false);
    for (const time of [.2, .6, 1.3, 2.1, 3.2, 4.1]) { entry.time(Math.min(time, entry.duration() - .01)); f.intro.update(); }
    entry.progress(1); f.intro.update();
    assert.equal(f.counts.complete, 1); f.assertRestored();
    assert.equal(emit(f.view, 'wheel', { deltaY: 300 }).defaultPrevented, false);
    assert.equal(f.intro.getState().phase, 'complete');
    return { startCount: f.counts.start, completeCount: f.counts.complete, duration: entry.duration() };
  } finally { f.cleanup(); }
});

await check('the production controller samples the real sliding hinge clip and keeps both models uniformly scaled', async () => {
  const f = await fixture();
  try {
    const clip = f.welcomeClips.find(item => item.name === 'TerminalUnfold');
    const floorAnchor = f.bounds.getCenter(new THREE.Vector3()); floorAnchor.y = f.bounds.min.y;
    const original = f.originals.get(f.room);
    const inverseOriginal = new THREE.Matrix4().compose(original.position, original.quaternion, original.scale).invert();
    const pivot = floorAnchor.clone().applyMatrix4(inverseOriginal);
    f.ready().progress(1); const entry = f.enter();
    const records = [];
    for (const time of [.5, .9, 1.3, 1.7, 2.1, 2.35, 3.0]) {
      entry.time(time); f.intro.update();
      const opening = f.intro.getState().opening.progress;
      for (const track of clip.tracks) {
        const path = THREE.PropertyBinding.parseTrackName(track.name), node = THREE.PropertyBinding.findNode(f.welcomeModel, path.nodeName);
        const expected = track.createInterpolant().evaluate(opening * clip.duration);
        node[path.propertyName].toArray().forEach((value, index) => close(value, expected[index], 2e-6));
      }
      const terminal = f.scene.getObjectByName('Blender creative terminal');
      assert.ok(terminal); close(terminal.scale.x, terminal.scale.y); close(terminal.scale.x, terminal.scale.z);
      const ratio = f.room.scale.clone().divide(original.scale); close(ratio.x, ratio.y); close(ratio.x, ratio.z);
      close(f.room.localToWorld(pivot.clone()).distanceTo(floorAnchor), 0, 1e-5);
      if (!terminal.visible) { assert.equal(f.room.visible, true); assert.ok(ratio.x > .5, 'room has substantially grown before the terminal disappears'); }
      const before = [...f.room.position.toArray(), ...f.room.scale.toArray()];
      f.intro.update(); f.intro.update();
      assert.deepEqual([...f.room.position.toArray(), ...f.room.scale.toArray()], before, 'repeated updates cannot accumulate pivot drift');
      records.push({ time, opening, roomVisible: f.room.visible, roomScale: ratio.x, terminalVisible: terminal.visible });
    }
    f.intro.skip(); f.assertRestored();
    return { tracks: clip.tracks.length, records, floorAnchor: floorAnchor.toArray() };
  } finally { f.cleanup(); }
});

await check('terminal handoff retracts above the growing platform with no translucent material or color changes', async () => {
  const welcomeGltf = await parseModelForCPU(modelPath), roomGltf = await parseModelForCPU(roomPath);
  const materials = new Map(); welcomeGltf.scene.traverse(node => {
    if (node.isMesh) for (const material of [].concat(node.material)) materials.set(material, {
      color: material.color.clone(), opacity: material.opacity, depthWrite: material.depthWrite, transparent: material.transparent,
    });
  });
  const modelBox = new THREE.Box3().setFromObject(welcomeGltf.scene), modelSize = modelBox.getSize(new THREE.Vector3());
  const modelSpan = Math.max(...modelSize.toArray());
  const f = introFixture({ welcomeGltf, roomGltf });
  try {
    f.ready().progress(1); const entry = f.enter();
    const anchor = f.bounds.getCenter(new THREE.Vector3()); anchor.y = f.bounds.min.y;
    const records = [];
    for (const time of [1.7, 1.9, 2.1, 2.3, 2.35, 2.6, 2.92]) {
      entry.time(time); f.intro.update();
      const terminal = f.scene.getObjectByName('Blender creative terminal');
      for (const [material, original] of materials) {
        assert.equal(material.opacity, original.opacity, 'opacity stays solid'); assert.equal(material.transparent, original.transparent, 'no alpha queue');
        assert.equal(material.depthWrite, original.depthWrite, 'solid depth remains enabled'); assert.deepEqual(material.color.toArray(), original.color.toArray());
      }
      close(terminal.scale.x, terminal.scale.y); close(terminal.scale.x, terminal.scale.z);
      if (time >= 1.9) {
        close(terminal.position.x, anchor.x); close(terminal.position.z, anchor.z);
        const platform = new THREE.Box3().setFromObject(f.roots.get('architecture.platform'));
        const terminalBox = new THREE.Box3().setFromObject(terminal);
        if (terminal.visible) assert.ok(terminalBox.min.y >= platform.max.y, 'the authored underside remains above the growing platform');
      }
      const width = terminal.scale.x / modelSpan * modelSize.x;
      if (time === 2.1) assert.ok(width < f.bounds.getSize(new THREE.Vector3()).x * .2, 'the 2.1-second terminal is small, not a giant ghost panel');
      records.push({ time, terminalWidth: width, visible: terminal.visible });
    }
    assert.equal(records.find(record => record.time === 2.35).visible, true, 'the shared handoff no longer removes the terminal early');
    assert.equal(records.at(-1).visible, false);
    for (let index = 2; index < records.length; index++) assert.ok(records[index].terminalWidth < records[index - 1].terminalWidth, 'the settled terminal retracts continuously');
    f.intro.skip(); f.assertRestored(); f.intro.dispose(); f.intro.dispose();
    assert.ok([...f.welcomeResources.values()].every(count => count === 1), 'temporary geometry, materials and image textures release exactly once');
    assert.equal(f.gpu.reflectionDisposals, 1); assert.ok([...f.resources.values()].every(count => count === 0));
    return { records, untouchedMaterials: materials.size, disposedTemporaryResources: f.welcomeResources.size };
  } finally { f.cleanup(); }
});

await check('room growth and terminal retraction share one continuous handoff while the camera keeps settling after model arrival', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const entry = f.enter();
    const anchor = f.bounds.getCenter(new THREE.Vector3()); anchor.y = f.bounds.min.y;
    const records = []; let previousHandoff = 0, previousRoomScale = .025, overlapSamples = 0;
    for (let frame = 0; frame <= 216; frame++) {
      const time = 1.12 + frame / 120;
      entry.time(time); f.intro.update();
      const state = f.intro.getState(), terminal = f.scene.getObjectByName('Blender creative terminal');
      assert.ok(state.handoff >= previousHandoff - 1e-7 && state.roomScale >= previousRoomScale - 1e-7);
      close(state.roomScale, .025 + .975 * state.handoff, 1e-6);
      assert.ok(state.roomScale - previousRoomScale < .009, 'room growth has no scale step at 120 Hz');
      close(terminal.scale.x, terminal.scale.y); close(terminal.scale.x, terminal.scale.z);
      if (time >= 1.8) {
        close(terminal.position.x, anchor.x); close(terminal.position.z, anchor.z);
      }
      if (state.roomVisible && terminal.visible) overlapSamples++;
      if ([0, 96, 144, 180, 216].includes(frame)) records.push({ time, handoff: state.handoff,
        roomScale: state.roomScale, terminalScale: terminal.scale.x, terminalVisible: terminal.visible,
        cameraDistanceToEnd: f.camera.position.distanceTo(f.endPose.position) });
      previousHandoff = state.handoff; previousRoomScale = state.roomScale;
    }
    assert.ok(overlapSamples > 180, 'room and terminal exchange scale together for more than 1.5 seconds');
    assert.ok(records.find(record => record.time > 1.8).cameraDistanceToEnd > .01, 'camera continues settling after the model reaches its floor anchor');
    assert.equal(records.at(-1).terminalVisible, false); close(records.at(-1).roomScale, 1);
    entry.time(2.94); f.intro.update(); close(f.camera.position.distanceTo(f.endPose.position), 0);
    f.intro.skip(); f.assertRestored();
    return { samplingHz: 120, samples: 217, overlapSeconds: overlapSamples / 120, records };
  } finally { f.cleanup(); }
});

await check('clean receiver bakes stay free of absent-prop shadows while exterior contact light fades independently, then both restore', async () => {
  const state = { progress: 0, restores: 0, disposals: 0 };
  const lighting = { setProgress(value) { state.progress = value; }, restore() { state.progress = 1; state.restores++; },
    dispose() { state.disposals++; }, getState: () => ({ ...state }) };
  const f = await fixture({ introLighting: lighting });
  try {
    f.ready().progress(1); const entry = f.enter();
    const records = []; let lastHidden = null;
    for (let time = 1.3; time <= entry.duration(); time += .05) {
      entry.time(time); f.intro.update();
      const current = f.intro.getState(), remaining = current.assembly.groups.reduce((sum, group) => sum + group.count - group.revealed, 0);
      if (remaining) {
        assert.equal(current.shadowReveal, 0); assert.equal(state.progress, 0);
        lastHidden = time;
      }
      if (current.shadowReveal > 0) assert.equal(remaining, 0, 'all furniture must exist before its baked shadows appear');
      if (current.contactReveal > 0) assert.ok(current.roomScale >= .999 && current.exteriorReveal > .35, 'contact shadow only grounds an established room and exterior');
      close(f.contactShadow.material.opacity, .42 * current.contactReveal);
      close(f.atmosphere.getState().introReveal, current.exteriorReveal);
      records.push({ time, remaining, shadowReveal: current.shadowReveal, contactReveal: current.contactReveal, exteriorReveal: current.exteriorReveal });
    }
    assert.ok(lastHidden > 4, 'checked through the last individual prop');
    assert.ok(records.some(record => record.shadowReveal > 0 && record.shadowReveal < 1));
    assert.ok(records.some(record => record.remaining > 0 && record.contactReveal > 0 && record.contactReveal < 1 && record.shadowReveal === 0), 'large exterior contact grounding precedes prop-shadow bake restoration');
    entry.progress(1); f.intro.update(); f.assertRestored();
    assert.equal(state.progress, 1); assert.ok(state.restores > 0); assert.equal(state.disposals, 0); close(f.contactShadow.material.opacity, .42);
    assert.equal(f.intro.getState().cleanLighting.progress, 1);
    return { lastFrameWithIncompleteProps: lastHidden, firstShadowFrame: records.find(record => record.shadowReveal > 0),
      firstContactFrame: records.find(record => record.contactReveal > 0), cleanTextureDisposalsByController: 0 };
  } finally { f.cleanup(); }
  assert.equal(state.disposals, 0);
});

await check('120 Hz production timeline samples show staggered, gradual sky, fixture, contact and prop-shadow reveals with no final snap', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); f.intro.update();
    assert.equal(f.atmosphere.getState().introReveal, 0, 'welcome fixture halos begin clear');
    assert.equal(f.atmosphere.getState().warmLightsVisible, true, 'existing halo visibility is not toggled to implement fading');
    const entry = f.enter(), fps = 120;
    // Quintic smoothstep has maximum slope 1.875. The approved accelerated
    // receiver fade is .95 seconds; bound each sampled step analytically.
    const limits = { environment: .008, exterior: .008, contact: .011, baked: 1.875 / (.95 * fps) + 2e-6 };
    const maxDelta = Object.fromEntries(Object.keys(limits).map(key => [key, 0]));
    const intervals = Object.fromEntries(Object.keys(limits).map(key => [key, { firstPositive: null, lastIncomplete: null, full: null }]));
    let previous = { environment: 0, exterior: 0, contact: 0, baked: 0 }, samples = 0;
    const frames = Math.ceil(entry.duration() * fps);
    for (let frame = 0; frame <= frames; frame++) {
      const time = Math.min(frame / fps, entry.duration());
      entry.time(time); f.intro.update();
      const state = f.intro.getState();
      const current = { environment: state.environmentReveal, exterior: state.exteriorReveal, contact: state.contactReveal, baked: state.shadowReveal };
      close(f.atmosphere.getState().introReveal, current.exterior);
      assert.equal(f.atmosphere.getState().warmLightsVisible, true, 'the alpha fade does not hide/show halo geometry at the final frame');
      close(f.contactShadow.material.opacity, .42 * current.contact);
      for (const [key, value] of Object.entries(current)) {
        assert.ok(value >= 0 && value <= 1 && value >= previous[key] - 1e-7, `${key}: monotonic bounded reveal`);
        maxDelta[key] = Math.max(maxDelta[key], value - previous[key]);
        if (value > 0 && intervals[key].firstPositive === null) intervals[key].firstPositive = time;
        if (value < 1) intervals[key].lastIncomplete = time;
        else if (intervals[key].full === null) intervals[key].full = time;
      }
      if (current.baked > 0) assert.ok(state.assembly.assets.every(asset => asset.factor === 1), 'no prop-shadow bake before every independent asset is at its exact endpoint');
      previous = current; samples++;
    }
    for (const [key, limit] of Object.entries(limits)) assert.ok(maxDelta[key] <= limit, `${key}: ${maxDelta[key]} exceeds the 120 Hz change limit ${limit}`);
    assert.ok(intervals.environment.firstPositive < intervals.contact.firstPositive);
    assert.ok(intervals.contact.full < intervals.baked.firstPositive, 'receiver shadows follow exterior grounding instead of one global light switch');
    const bakedSpan = intervals.baked.full - intervals.baked.firstPositive;
    assert.ok(Math.abs(bakedSpan - .95) <= 2 / fps, 'receiver shadows retain the approved .95 second continuous fade');
    assert.ok(intervals.contact.lastIncomplete - intervals.contact.firstPositive > 1.4);
    assert.ok(entry.duration() > 5 && entry.duration() < 7, 'accelerated lighting settles in a bounded final overlap');
    f.assertRestored(); assert.equal(f.counts.complete, 1);
    return { samplingHz: fps, samples, duration: entry.duration(), maxAdjacentFrameDelta: maxDelta, allowedAdjacentFrameDelta: limits, intervals,
      scope: 'CPU evaluation of real GSAP uniform curves at 120 samples/second; this does not measure rendered FPS or visual luminance.' };
  } finally { f.cleanup(); }
});

await check('skip and reduced motion restore optional clean lighting and contact shadow immediately', async () => {
  for (const reducedMotion of [false, true]) {
    const state = { value: 0, restored: false, disposed: 0 };
    const introLighting = { setProgress(value) { state.value = value; }, restore() { state.value = 1; state.restored = true; }, dispose() { state.disposed++; }, getState: () => ({ ...state }) };
    const f = await fixture({ reducedMotion, introLighting });
    try {
      f.ready().progress(1); const entry = f.enter();
      if (!reducedMotion) { entry.time(2.1); f.intro.update(); assert.equal(state.value, 0); f.intro.skip(); }
      f.assertRestored(); assert.equal(state.restored, true); assert.equal(state.value, 1); assert.equal(f.intro.getState().shadowReveal, 1);
      close(f.contactShadow.material.opacity, .42); f.intro.dispose(); assert.equal(state.disposed, 0);
    } finally { f.cleanup(); }
  }
});

await check('every prop has its original precise local transform after normal completion, including nonunit GLB quaternions', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const entry = f.enter();
    let evolving = 0;
    for (let time = 0; time < entry.duration(); time += .083) {
      entry.time(time); f.intro.update();
      for (const root of f.roots.values()) {
        assert.ok([...root.position.toArray(), ...root.scale.toArray(), ...root.quaternion.toArray()].every(Number.isFinite));
        if (root.scale.distanceTo(f.originals.get(root).scale) > 1e-6) evolving++;
      }
    }
    assert.ok(evolving > 36); entry.progress(1); f.intro.update(); f.assertRestored();
    assert.equal(f.roomEntry.getState().propCount, 36); assert.equal(f.roomEntry.getState().phase, 'complete');
    return { independentRoots: f.roots.size, components: f.components.size, allSceneNodes: f.originals.size, intermediateGrowthSamples: evolving };
  } finally { f.cleanup(); }
});

await check('C reveal keeps skip locked; welcome and all entry stages restore the same exact scene', async () => {
  const records = [];
  for (const at of ['welcome', 'appearance', .15, .8, 1.8, 2.6, 3.7]) {
    const f = await fixture();
    try {
      const welcome = f.ready(); welcome.time(at === 'appearance' ? .13 : welcome.duration()); f.intro.update();
      if (at === 'appearance') {
        assert.equal(f.intro.getState().loadingReveal, true);
        f.intro.skip(); assert.equal(f.counts.start, 0); assert.equal(f.counts.complete, 0);
        welcome.progress(1); f.intro.update();
        assert.equal(f.intro.getState().loadingReveal, false);
      }
      if (typeof at === 'number') { const entry = f.enter(); entry.time(at); f.intro.update(); }
      f.intro.skip(); f.intro.skip(); f.intro.update(); f.assertRestored();
      assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1);
      records.push({ at, startCount: f.counts.start, completeCount: f.counts.complete });
    } finally { f.cleanup(); }
  }
  return { records };
});

await check('mobile up swipe triggers once and repeated viewport changes preserve timeline progress', async () => {
  const f = await fixture({ width: 390, height: 844 });
  try {
    f.ready().progress(1); f.intro.update();
    emit(f.view, 'touchstart', { touches: [{ clientY: 100 }] }); emit(f.view, 'touchmove', { touches: [{ clientY: 180 }] });
    assert.equal(f.intro.getState().phase, 'welcome');
    emit(f.view, 'touchend', { touches: [] });
    const entry = f.enter('touch'); entry.time(1.25); f.intro.update();
    const progress = f.intro.getState().progress;
    for (const [width, height] of [[844, 390], [1440, 900], [390, 844], [844, 795]]) {
      f.view.innerWidth = width; f.view.innerHeight = height; f.camera.aspect = width / height; f.camera.updateProjectionMatrix();
      f.intro.resize(); f.intro.update();
      close(f.intro.getState().progress, progress); assert.equal(f.intro.getState().startCount, 1);
      assert.ok(f.camera.position.toArray().every(Number.isFinite));
      for (const root of f.roots.values()) assert.ok(root.scale.toArray().every(Number.isFinite));
    }
    entry.progress(1); f.intro.update(); f.assertRestored();
    return { inputSource: f.intro.getState().inputSource, checkedViewports: 4, preservedProgress: progress,
      scope: 'Controller transform and timeline checks; DOM layout and visual framing still require browser verification.' };
  } finally { f.cleanup(); }
});

await check('reduced motion and a live reduction change both finish without a stuck overlay or controls', async () => {
  for (const initial of [true, false]) {
    const f = await fixture({ reducedMotion: initial });
    try {
      f.ready().progress(1); const entry = f.enter();
      if (!initial) { entry.time(1.35); f.intro.update(); emit(f.media, 'change', { matches: true }); }
      assert.equal(f.intro.getState().phase, 'complete'); assert.equal(f.element.hidden, true); assert.equal(f.element.inert, true);
      assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1); f.assertRestored();
    } finally { f.cleanup(); }
  }
});

await check('dispose is idempotent and never disposes persistent room geometry or materials', async () => {
  const f = await fixture();
  f.ready().progress(1); const entry = f.enter(); entry.time(1.75); f.intro.update();
  f.intro.dispose(); f.intro.dispose(); f.intro.update();
  assert.equal(f.intro.getState().phase, 'disposed');
  assert.ok([...f.resources.values()].every(count => count === 0));
  assert.equal(emit(f.view, 'wheel', { deltaY: 80 }).defaultPrevented, false);
  emit(f.element.querySelector('.intro-enter'), 'click'); assert.equal(f.counts.start, 1);
  assert.equal(f.doc.body.style.overflow, 'auto'); assert.equal(f.room.visible, true);
  f.cleanup();
  return { persistentResourceCount: f.resources.size, disposedPersistentResources: 0 };
});

await check('QA inspection freezes the unchanged production timeline at 1.6, 2.1 and 2.8 seconds, then skip restores exactly', async () => {
  const records = [];
  for (const seconds of [1.6, 2.1, 2.8]) {
    const f = await fixture(), production = await fixture();
    try {
      f.ready();
      for (const invalid of [-1, NaN, Infinity]) assert.equal(f.intro.inspectAt(invalid), false);
      assert.equal(f.intro.getState().phase, 'welcome'); assert.equal(f.counts.start, 0);
      assert.equal(f.intro.inspectAt(seconds), true);
      const state = f.intro.getState();
      assert.equal(state.inputSource, 'qa'); assert.equal(state.phase, 'playing'); assert.equal(state.paused, true);
      close(state.elapsedTime, seconds); assert.equal(f.element.dataset.inspectAt, String(seconds));
      assert.equal(f.counts.start, 1); assert.equal(f.intro.inspectAt(seconds + .1), false, 'inspection cannot retrigger or rewind one-shot entry');
      production.ready().progress(1); const timeline = production.enter(); timeline.time(seconds); production.intro.update();
      assert.deepEqual(f.room.position.toArray(), production.room.position.toArray());
      assert.deepEqual(f.room.scale.toArray(), production.room.scale.toArray());
      assert.equal(f.room.visible, production.room.visible);
      for (const [id, root] of f.roots) {
        const reference = production.roots.get(id);
        assert.deepEqual(root.position.toArray(), reference.position.toArray(), `${id}: frozen position differs from production`);
        assert.deepEqual(root.quaternion.toArray(), reference.quaternion.toArray(), `${id}: frozen quaternion differs from production`);
        assert.deepEqual(root.scale.toArray(), reference.scale.toArray(), `${id}: frozen scale differs from production`);
      }
      const before = JSON.stringify(f.intro.getState());
      for (let frame = 0; frame < 20; frame++) f.intro.update();
      assert.equal(JSON.stringify(f.intro.getState()), before, 'render frames cannot advance a frozen timeline');
      f.intro.skip(); f.assertRestored();
      assert.equal(f.counts.complete, 1); records.push({ seconds, roomVisible: state.roomVisible, roomScale: state.roomScale, opening: state.opening.progress });
    } finally { f.cleanup(); production.cleanup(); }
  }
  return { records, method: 'Production timeline equivalence, not a substitute scene or altered animation.' };
});

await check('the automatic inspection gate needs DEV, qa and introAt together; normal qa and production are unchanged', () => {
  const gate = main.match(/    if \(import\.meta\.env\.DEV && previewQA\) \{\n      const inspectionParams[\s\S]*?\n    \}/)?.[0];
  assert.ok(gate, 'explicit DEV and QA gate exists after ready');
  assert.ok(main.indexOf(gate) > main.indexOf('cubeIntro.ready()'));
  for (const [DEV, previewQA, search, expected] of [[false, true, '?qa&introAt=1.6', []], [true, false, '?introAt=1.6', []],
    [true, true, '?qa', []], [true, true, '?qa&introAt=2.1', [2.1]]]) {
    const called = [];
    vm.runInNewContext(gate.replace('import.meta.env.DEV', 'DEV'), { DEV, previewQA, URLSearchParams, location: { search }, cubeIntro: { inspectAt: value => called.push(value) } });
    assert.deepEqual(called, expected);
  }
});

await check('main loads the selected release and compiles/fences the terminal before exposing welcome', () => {
  assert.match(main, /loader\.loadAsync\(materialRelease\.roomModel/);
  const load = main.indexOf('loadAsync(materialRelease.terminalModel'), create = main.indexOf('cubeIntro = createCubeIntro('), ready = main.indexOf('cubeIntro.ready()');
  assert.ok(load >= 0 && create > load && ready > create);
  assert.match(main.slice(create, ready), /welcomeClips: welcomeGltf\.animations/);
  assert.match(main.slice(create, ready), /renderer\.compileAsync\(scene, camera\)/);
  const fence = main.indexOf('await waitForStartupGpu(renderer)', create), finished = main.indexOf('startupReadiness.finish()', create);
  assert.ok(fence > create && finished > fence && ready > finished);
  assert.doesNotMatch(source, /uIntroRoomFinish|max\(diffuseColor\.rgb/);
  assert.doesNotMatch(source, /createFoldedRoomMotion/);
  return { cpuFixture: { modelPath, roomPath }, runtimeAssets: 'Resolved from materialRelease', shaderAppearance: 'Original room colors and baked texture hooks preserved.' };
});

const report = { revision: 2, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Actual Blender GLBs loaded by GLTFLoader; unchanged production intro controller with real GSAP and real room-entry, manually advanced time. Browser DOM, image decoding and GPU PMREM are controlled substitutes. No browser rendering, visual quality, frame-rate or mobile layout claim.',
  model: { path: modelPath, bytes: model.bytes.length, sha256: hash(model.bytes) },
  sourceSha256: Object.fromEntries(['src/cube-intro.js', 'src/main.js', 'src/room-entry.js', 'src/intro-input.js', 'src/intro-lighting.js', 'src/exterior-atmosphere.js', modelPath].map(path => [path, hash(readFileSync(file(path)))])),
  verificationSourceSha256: Object.fromEntries(['scripts/check-terminal-intro.mjs', 'scripts/lib/intro-controller-fixture.mjs'].map(path => [path, hash(readFileSync(file(path)))])),
  checks: checks.length, passed: checks.filter(check => check.status === 'passed').length, failed: checks.filter(check => check.status === 'failed').length, results: checks };
if (process.argv.includes('--write-report')) writeFileSync(file('docs/validation/terminal-intro-v1.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, failures: checks.filter(check => check.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
