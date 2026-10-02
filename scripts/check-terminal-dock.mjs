import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { parseModelForCPU, introFixture, emit } from './lib/intro-controller-fixture.mjs';

const file = path => new URL(`../${path}`, import.meta.url);
// Defaults preserve the V1 regression. Explicit paths exercise a new export
// against the same production controller and unchanged motion limits.
// node scripts/check-terminal-dock.mjs --model public/models/welcome-terminal-v2.glb --report docs/validation/terminal-dock-v2.json
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const option = flag => {
  const at = process.argv.indexOf(flag);
  if (at < 0) return null;
  assert.ok(process.argv[at + 1] && !process.argv[at + 1].startsWith('--'), `${flag} requires a path`);
  return relative(project, resolve(project, process.argv[at + 1]));
};
const modelPath = option('--model') ?? 'public/models/welcome-terminal-v1.glb';
const reportPath = option('--report') ?? (process.argv.includes('--write-report') ? 'docs/validation/terminal-dock-v1.json' : null);
const results = [];
const close = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
async function check(name, fn) {
  try { results.push({ check: name, status: 'passed', ...await fn() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.stack }); }
}
async function fixture(options = {}) {
  const [welcomeGltf, roomGltf] = await Promise.all([
    parseModelForCPU(modelPath),
    parseModelForCPU('public/models/orbital-atelier-v16.glb'),
  ]);
  return introFixture({ welcomeGltf, roomGltf, resident: true, ...options });
}
const closeArray = (actual, expected, tolerance = 1e-6) => actual.forEach((value, index) => close(value, expected[index], tolerance));

await check('active resident branch uses the same actual Blender GLB in welcome and permanently on the desk', async () => {
  const f = await fixture();
  try {
    const dock = f.terminalDock, carrier = dock.carrier, root = f.roots.get('folding_drawing_terminal');
    assert.equal(dock.model, f.welcomeModel); assert.equal(dock.root, root);
    assert.equal(f.intro.getState().docking.permanent, true);
    assert.equal(f.room.visible, false); assert.equal(dock.getState().attachedHome, false);
    assert.equal(f.gpu.generations, 1, 'one reflection owner, without a second intro PMREM');
    for (const id of ['terminal_lid', 'terminal_dial', 'terminal_rail']) assert.ok(f.components.has(id), `${id} remains an independently identifiable Blender part`);
    assert.equal(f.roomEntry.getState().propCount, 36);
    const welcome = f.ready(); close(welcome.timeScale(), 1.25); welcome.progress(1); f.intro.update();
    assert.equal(carrier.visible, true); assert.equal(f.room.visible, false);
    const timeline = f.enter(); close(timeline.timeScale(), 1.25);
    close(f.intro.getState().playbackRate, timeline.timeScale());
    close(f.intro.getState().playbackDuration, timeline.duration() / timeline.timeScale());
    timeline.progress(1); f.intro.update(); f.assertRestored();
    assert.equal(carrier.parent, root); assert.equal(f.intro.getState().modelVisible, true);
    assert.ok(carrier.getObjectById(f.welcomeModel.id), 'the exact loaded model survives docking without a substitute');
    closeArray(carrier.getWorldPosition(new THREE.Vector3()).toArray(), dock.getHomeWorldPose().position.toArray());
    closeArray(carrier.getWorldScale(new THREE.Vector3()).toArray(), dock.getHomeWorldPose().scale.toArray());
    return { controllerRevision: f.intro.getState().revision, resident: dock.getState(), timelineDurationSeconds: timeline.duration(),
      playbackRate: timeline.timeScale(), playbackDurationSeconds: timeline.duration() / timeline.timeScale(),
      welcomePlaybackRate: welcome.timeScale(), welcomePlaybackDurationSeconds: welcome.duration() / welcome.timeScale(), originalSceneNodesVerified: f.originals.size };
  } finally { f.cleanup(); }
});

await check('120 Hz playback-clock desktop and compact arrival samples stay visible, retain nonzero size and have continuous world motion', async () => {
  const records = [];
  for (const [width, height, idleSeconds] of [[1440, 900, 0], [390, 844, 0], [1440, 900, 8], [390, 844, 8]]) {
    const f = await fixture({ width, height });
    try {
      let clockMilliseconds = 0;
      f.view.performance = { now: () => clockMilliseconds };
      f.ready().progress(1); f.intro.update();
      if (idleSeconds) {
        // Exercise the new floating/tilting welcome from a non-neutral pose.
        // Both the real idle update and the real GSAP arrival keep their clocks.
        emit(f.element, 'pointermove', { pointerType: width > 700 ? 'mouse' : 'touch', clientX: width * .85, clientY: height * .28 });
        for (let frame = 1; frame <= idleSeconds * 60; frame++) { clockMilliseconds = frame / 60 * 1000; f.intro.update(); }
      }
      const welcomeShowcase = f.intro.getState().showcase;
      const timeline = f.enter();
      const sampleHz = 120, playbackRate = timeline.timeScale(), playbackDuration = timeline.duration() / playbackRate;
      const carrier = f.terminalDock.carrier, home = f.terminalDock.getHomeWorldPose();
      const span = f.bounds.getSize(new THREE.Vector3()).length();
      const position = new THREE.Vector3(), scale = new THREE.Vector3(), quaternion = new THREE.Quaternion();
      let previousPosition, previousScale, previousQuaternion, maximumStep = 0, maximumScaleStep = 0, maximumAngle = 0, minimumScaleRatio = Infinity;
      let frameCount = 0, attachedAt = null, minimumClearance = Infinity, overlapsBeforeDeskSettled = 0;
      const table = f.roots.get('furniture.desk'), tableBox = new THREE.Box3(), terminalBox = new THREE.Box3();
      const violations = []; let penetrationFrames = 0;
      for (let frame = 0; frame <= Math.ceil(playbackDuration * sampleHz); frame++) {
        const wallSeconds = Math.min(frame / sampleHz, playbackDuration);
        clockMilliseconds = (idleSeconds + wallSeconds) * 1000;
        const time = Math.min(wallSeconds * playbackRate, timeline.duration());
        timeline.time(time); f.intro.update(); f.scene.updateMatrixWorld(true);
        const state = f.intro.getState();
        carrier.getWorldPosition(position); carrier.getWorldScale(scale); carrier.getWorldQuaternion(quaternion);
        assert.ok([...position, ...scale, ...quaternion].every(Number.isFinite));
        assert.equal(carrier.visible, true, `resident must not disappear at ${time}s`);
        minimumScaleRatio = Math.min(minimumScaleRatio, ...scale.toArray().map((value, axis) => value / home.scale.toArray()[axis]));
        if (previousPosition) {
          maximumStep = Math.max(maximumStep, position.distanceTo(previousPosition));
          maximumScaleStep = Math.max(maximumScaleStep, ...scale.toArray().map((value, axis) => Math.abs(value / previousScale.toArray()[axis] - 1)));
          maximumAngle = Math.max(maximumAngle, quaternion.angleTo(previousQuaternion));
        }
        if (state.docking.attached && attachedAt === null) attachedAt = wallSeconds;
        if (state.roomVisible) {
          tableBox.setFromObject(table, true); terminalBox.setFromObject(carrier, true);
          const overlapsXZ = terminalBox.min.x < tableBox.max.x && terminalBox.max.x > tableBox.min.x
            && terminalBox.min.z < tableBox.max.z && terminalBox.max.z > tableBox.min.z;
          if (overlapsXZ) {
            const clearance = terminalBox.min.y - tableBox.max.y;
            minimumClearance = Math.min(minimumClearance, clearance);
            const desk = state.assembly.assets.find(asset => asset.id === 'furniture.desk');
            if (desk.factor < 1) overlapsBeforeDeskSettled++;
            if (clearance < -.002) {
              penetrationFrames++;
              if (violations.length < 5) violations.push({ wallSeconds, timelineSeconds: time, clearance, deskFactor: desk.factor, docking: state.docking.progress });
            }
          }
        }
        previousPosition = position.clone(); previousScale = scale.clone(); previousQuaternion = quaternion.clone(); frameCount++;
      }
      // Preserve the previous velocity ceilings when moving from 60 Hz to
      // 120 Hz; faster playback is sampled rather than cancelled by seeking.
      const record = { viewport: [width, height], welcomeIdleSeconds: idleSeconds, welcomeShowcase, sampleHz, samplingClock: 'playback wall time', playbackRate,
        timelineDurationSeconds: timeline.duration(), playbackDurationSeconds: playbackDuration,
        frames: frameCount, maximumWorldStep: maximumStep,
        allowedWorldStep: span * .01 * 60 / sampleHz, maximumRelativeScaleStep: maximumScaleStep,
        allowedRelativeScaleStep: .065 * 60 / sampleHz, maximumRotationStepRadians: maximumAngle,
        allowedRotationStepRadians: .07 * 60 / sampleHz,
        minimumScaleRatioToFinal: minimumScaleRatio, attachedAtWallSeconds: attachedAt, minimumDeskClearance: minimumClearance,
        overlapFramesBeforeDeskSettled: overlapsBeforeDeskSettled, deskPenetrationFrames: penetrationFrames, firstDeskPenetrations: violations };
      records.push(record);
      f.assertRestored();
    } finally { f.cleanup(); }
  }
  for (const record of records) {
    assert.ok(record.maximumWorldStep < record.allowedWorldStep, JSON.stringify(records));
    assert.ok(record.maximumRelativeScaleStep < record.allowedRelativeScaleStep, JSON.stringify(records));
    assert.ok(record.maximumRotationStepRadians < record.allowedRotationStepRadians, JSON.stringify(records));
    assert.ok(record.minimumScaleRatioToFinal >= .99, 'the model retains at least its final usable size throughout entry');
    assert.equal(record.deskPenetrationFrames, 0, JSON.stringify(records));
    assert.ok(record.attachedAtWallSeconds > 0);
  }
  return { records, scope: 'Actual transformed Blender vertices and controller samples at 120 virtual playback-clock steps/second using timeline.time(wallSeconds * timeScale). AABB desktop surface clearance, not rendered FPS or an exhaustive mesh intersection test.' };
});

await check('the final resident underside sits above the actual desk triangles across its footprint', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); f.enter().progress(1); f.intro.update(); f.scene.updateMatrixWorld(true);
    const desk = f.roots.get('furniture.desk'), terminal = new THREE.Box3().setFromObject(f.terminalDock.carrier, true);
    const deskBox = new THREE.Box3().setFromObject(desk, true), ray = new THREE.Raycaster();
    const downward = new THREE.Vector3(0, -1, 0), samples = [];
    for (let x = 0; x < 3; x++) for (let z = 0; z < 3; z++) {
      const point = new THREE.Vector3(THREE.MathUtils.lerp(terminal.min.x, terminal.max.x, x / 2), deskBox.max.y + 2,
        THREE.MathUtils.lerp(terminal.min.z, terminal.max.z, z / 2));
      ray.set(point, downward); const hit = ray.intersectObject(desk, true)[0];
      if (hit) samples.push({ x: point.x, z: point.z, deskHeight: hit.point.y, terminalBottom: terminal.min.y, clearance: terminal.min.y - hit.point.y });
    }
    assert.ok(samples.length >= 5, 'enough footprint rays actually intersect the table');
    assert.ok(samples.every(sample => sample.clearance >= -.002), JSON.stringify(samples));
    f.assertRestored(); return { actualTriangleSamples: samples };
  } finally { f.cleanup(); }
});

await check('docking endpoint transfers ownership without a hidden frame or position, scale and orientation jump', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const timeline = f.enter();
    const end = f.intro.getState().docking.end, carrier = f.terminalDock.carrier;
    const capture = time => {
      timeline.time(time); f.intro.update(); f.scene.updateMatrixWorld(true);
      return { position: carrier.getWorldPosition(new THREE.Vector3()), scale: carrier.getWorldScale(new THREE.Vector3()),
        quaternion: carrier.getWorldQuaternion(new THREE.Quaternion()), visible: carrier.visible, attached: f.intro.getState().docking.attached };
    };
    // GSAP rounds eased factors to six decimals, so the dock can reach its
    // exact endpoint a few milliseconds early. Sample a genuinely detached
    // pose and assert both sides of the ownership change, rather than comparing
    // two already-attached frames near the nominal end time.
    const before = capture(end - .025), after = capture(end + .002);
    assert.equal(before.visible, true); assert.equal(after.visible, true);
    assert.equal(before.attached, false); assert.equal(after.attached, true);
    assert.ok(before.position.distanceTo(after.position) < .001);
    assert.ok(before.scale.distanceTo(after.scale) < .001);
    assert.ok(before.quaternion.angleTo(after.quaternion) < .001);
    timeline.progress(1); f.intro.update(); f.assertRestored();
    return { dockEnd: end, positionDifference: before.position.distanceTo(after.position), scaleDifference: before.scale.distanceTo(after.scale),
      rotationDifferenceRadians: before.quaternion.angleTo(after.quaternion), residentResourceDisposals: [...f.welcomeResources.values()].reduce((a, b) => a + b, 0) };
  } finally { f.cleanup(); }
});

await check('resident skip from welcome, unfolding, travel, landing and light settling restores the complete replacement scene exactly', async () => {
  const records = [];
  for (const at of ['welcome', .15, 1.3, 2.4, 3.3, 4.4, 5.2]) {
    const f = await fixture();
    try {
      f.ready().progress(1); f.intro.update();
      if (typeof at === 'number') { const timeline = f.enter(); timeline.time(at); f.intro.update(); }
      f.intro.skip(); f.intro.skip(); f.intro.update(); f.assertRestored();
      assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1); assert.equal(f.intro.getState().modelVisible, true);
      records.push({ at, attached: f.terminalDock.getState().attachedHome, originalSceneNodesVerified: f.originals.size });
    } finally { f.cleanup(); }
  }
  return { records };
});

await check('resident wheel, keyboard and compact up-swipe trigger once, lock interaction during arrival and preserve resize progress', async () => {
  const records = [];
  for (const input of ['wheel', 'keyboard', 'touch']) {
    const f = await fixture(input === 'touch' ? { width: 390, height: 844 } : {});
    try {
      f.ready().progress(1); f.intro.update();
      const timeline = f.enter(input); timeline.time(1.7); f.intro.update();
      assert.equal(f.intro.getState().inputSource, input);
      const progress = f.intro.getState().progress;
      for (const deltaY of [-60, 40, 400]) assert.equal(emit(f.view, 'wheel', { deltaY }).defaultPrevented, true);
      emit(f.element.querySelector('.intro-enter'), 'click'); emit(f.view, 'keydown', { key: 'ArrowDown' });
      emit(f.view, 'touchstart', { touches: [{ clientY: 400 }] }); emit(f.view, 'touchmove', { touches: [{ clientY: 250 }] });
      assert.equal(f.counts.start, 1); assert.equal(f.controls.enabled, false);
      for (const [width, height] of [[844, 390], [1440, 900], [390, 844]]) {
        f.view.innerWidth = width; f.view.innerHeight = height; f.camera.aspect = width / height; f.camera.updateProjectionMatrix();
        f.intro.resize(); f.intro.update(); close(f.intro.getState().progress, progress);
        const pose = f.intro.getState().docking;
        assert.ok([...pose.position, ...pose.scale].every(Number.isFinite)); assert.ok(pose.scale.every(value => value > 0));
      }
      timeline.progress(1); f.intro.update(); f.assertRestored();
      assert.equal(emit(f.view, 'wheel', { deltaY: 100 }).defaultPrevented, false);
      records.push({ input, start: f.counts.start, complete: f.counts.complete, resizedViewports: 3 });
    } finally { f.cleanup(); }
  }
  return { records, scope: 'Input/controller behavior with actual model transforms; real phone layout and rendered frame rate require browser/hardware checks.' };
});

await check('initial and live reduced-motion changes retain the permanent terminal and its exact final pose', async () => {
  for (const reducedMotion of [true, false]) {
    const f = await fixture({ reducedMotion });
    try {
      f.ready().progress(1); const timeline = f.enter();
      if (!reducedMotion) { timeline.time(2.4); f.intro.update(); emit(f.media, 'change', { matches: true }); }
      f.assertRestored(); assert.equal(f.counts.complete, 1); assert.equal(f.intro.getState().modelVisible, true);
      assert.equal(f.element.hidden, true); assert.equal(f.element.inert, true);
    } finally { f.cleanup(); }
  }
});

await check('after docking the same PBR material resources support day and night without changing geometry or pose', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const timeline = f.enter(); timeline.progress(1); f.intro.update(); f.assertRestored();
    const materials = new Map(), meshes = new Map();
    f.welcomeModel.traverse(node => {
      if (!node.isMesh) return;
      meshes.set(node, node.geometry);
      for (const material of [].concat(node.material)) materials.set(material, { map: material.map, envMap: material.envMap, color: material.color.clone(), emissive: material.emissiveIntensity });
    });
    const states = [];
    for (const day of [false, true]) {
      f.terminalDock.setTheme(day, 0);
      const state = f.terminalDock.getState(); states.push(state);
      assert.equal(state.day, day); close(state.environmentIntensity, day ? 1.1 : .3); close(state.screenIntensity, day ? .84 : .47);
      assert.equal(state.introLight, 0);
      for (const [mesh, geometry] of meshes) assert.equal(mesh.geometry, geometry);
      for (const [material, original] of materials) {
        assert.equal(material.map, original.map); assert.equal(material.envMap, original.envMap);
        assert.deepEqual(material.color.toArray(), original.color.toArray());
        close(material.envMapIntensity, day ? 1.1 : .3);
        close(material.emissiveIntensity, original.emissive * (day ? 1 : .47 / .84));
      }
      f.assertRestored();
    }
    f.terminalDock.setTheme(false, .8);
    gsap.globalTimeline.getChildren(false, true, false).filter(tween => tween.vars.environment === .3).forEach(tween => { tween.pause(); tween.progress(.5); });
    const middle = f.terminalDock.getState(); assert.ok(middle.environmentIntensity > .3 && middle.environmentIntensity < 1.1);
    f.terminalDock.setTheme(true, 0); f.assertRestored();
    return { materialCount: materials.size, meshCount: meshes.size, day: states[1].environmentIntensity, night: states[0].environmentIntensity, animatedMidpoint: middle.environmentIntensity };
  } finally { f.cleanup(); }
});

await check('resident lighting remains gradual and absent-prop bake shadows stay off until every asset including the arriving terminal is complete', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const timeline = f.enter();
    const sampleHz = 120, playbackRate = timeline.timeScale(), playbackDuration = timeline.duration() / playbackRate;
    const maxDelta = { environment: 0, exterior: 0, contact: 0, shadow: 0, terminalLight: 0 };
    // Bounds are per 8.33 ms of visible playback, not per timeline second.
    // The requested 0.76 s quintic shadow fade peaks at 1.875 / 0.76 / 120
    // = 0.02056 per sample. A 0.022 cap permits that faster smooth fade but
    // rejects the old abrupt 0.45 s reveal (~0.0347/sample even at 1x).
    const allowedDelta = { environment: .01, exterior: .01, contact: .014, shadow: .022, terminalLight: .025 };
    let previous, samples = 0, firstShadow = null, fullShadow = null;
    for (let frame = 0; frame <= Math.ceil(playbackDuration * sampleHz); frame++) {
      const wallSeconds = Math.min(frame / sampleHz, playbackDuration);
      const time = Math.min(wallSeconds * playbackRate, timeline.duration()); timeline.time(time); f.intro.update();
      const state = f.intro.getState(), dock = f.terminalDock.getState();
      const current = { environment: state.environmentReveal, exterior: state.exteriorReveal, contact: state.contactReveal, shadow: state.shadowReveal, terminalLight: dock.introLight };
      if (previous) for (const key of Object.keys(maxDelta)) maxDelta[key] = Math.max(maxDelta[key], Math.abs(current[key] - previous[key]));
      close(f.atmosphere.getState().introReveal, current.exterior);
      if (current.shadow > 0) {
        if (firstShadow === null) firstShadow = wallSeconds;
        if (current.shadow === 1 && fullShadow === null) fullShadow = wallSeconds;
        assert.equal(state.docking.attached, true);
        assert.ok(state.assembly.assets.every(asset => asset.factor === 1));
      }
      previous = current; samples++;
    }
    for (const [key, maximum] of Object.entries(maxDelta)) assert.ok(maximum < allowedDelta[key], `${key}: ${maximum} exceeds ${allowedDelta[key]} per 120 Hz playback sample`);
    assert.ok(fullShadow - firstShadow > .73 && fullShadow - firstShadow < .78, 'the faster shadow fade retains a continuous roughly 0.76-second visible transition');
    f.assertRestored(); return { samples, samplingHz: sampleHz, samplingClock: 'playback wall time', playbackRate,
      maxAdjacentMixDelta: maxDelta, allowedAdjacentMixDelta: allowedDelta, firstShadowWallSeconds: firstShadow,
      fullShadowWallSeconds: fullShadow, measuredShadowFadeWallSeconds: fullShadow - firstShadow,
      timelineDurationSeconds: timeline.duration(), playbackDurationSeconds: playbackDuration,
      thresholdRationale: 'Per-120-Hz-playback bounds: sky/exterior at most 1%, contact 1.4%, shorter receiver shadow 2.2%, welcome light 2.5%. These evaluate the requested faster continuous fades rather than silently sampling the previous 1x clock.' };
  } finally { f.cleanup(); }
});

await check('disposing a playing controller retains resident resources until its separate owner is disposed, without touching original room atlases', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const timeline = f.enter(); timeline.time(2.0); f.intro.update();
    f.intro.dispose(); f.intro.dispose();
    assert.equal(f.terminalDock.getState().attachedHome, true);
    assert.equal(f.terminalDock.getState().disposed, false);
    assert.ok([...f.welcomeResources.values()].every(count => count === 0));
    assert.ok([...f.resources.values()].every(count => count === 0));
    assert.equal(f.gpu.reflectionDisposals, 0);
    return { borrowedResourceCount: f.welcomeResources.size, untouchedOriginalRoomResourceCount: f.resources.size };
  } finally { f.cleanup(); }
});

const hash = path => createHash('sha256').update(readFileSync(file(path))).digest('hex');
const report = { revision: 3, activeBranch: 'resident-terminal-dock', model: modelPath, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Actual welcome and room GLBs, production resident-terminal owner, cube-intro controller and room-entry with real GSAP. Continuous motion/lighting tests sample 120 virtual wall-clock frames/second and advance timeline time by wallSeconds * real timeline.timeScale(), including the 1.25x speed-up. Browser DOM, image decoding and GPU PMREM use controlled substitutes. These are active resident-branch tests, not legacy disappearing-terminal results. No visual quality, rendered FPS or exhaustive collision claim.',
  sourceSha256: Object.fromEntries(['src/resident-terminal.js', 'src/cube-intro.js', 'src/room-entry.js', 'src/main.js', 'src/intro-input.js', 'src/exterior-atmosphere.js',
    'src/intro-backdrop.js', 'scripts/lib/intro-controller-fixture.mjs', 'scripts/check-terminal-dock.mjs', modelPath, 'public/models/orbital-atelier-v16.glb'].map(path => [path, hash(path)])),
  checks: results.length, passed: results.filter(result => result.status === 'passed').length, failed: results.filter(result => result.status === 'failed').length, results };
if (reportPath) { mkdirSync(dirname(resolve(project, reportPath)), { recursive: true }); writeFileSync(file(reportPath), JSON.stringify(report, null, 2) + '\n'); }
console.log(JSON.stringify({ model: modelPath, checks: report.checks, passed: report.passed, failed: report.failed, failures: results.filter(result => result.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
