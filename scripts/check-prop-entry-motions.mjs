import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { parseModelForCPU, introFixture } from './lib/intro-controller-fixture.mjs';
import { createRoomEntryAttachments } from '../src/room-entry-attachments.js';

const roomPath = 'public/models/orbital-atelier-v16.glb';
const terminalPath = 'public/models/welcome-terminal-v1.glb';
const families = {
  spin: ['ceramic_mobius_study', 'ceramic_ring_speaker', 'v8_reading_puck'],
  hop: ['thermal_cup', 'robot_companion'],
  drift: ['geometric_specimen_cloche', 'v5_scout_drone_display'],
  flip: ['folding_drawing_terminal', 'portable_fold_communicator', 'compact_camera'],
  dock: ['studio_reference_books', 'v5_energy_capsule_rack', 'v5_portable_projector'],
  spring: ['v5_magnetic_pen_dock', 'headphones_on_stand', 'v8_desk_glow_lamp'],
};
const visibleFactors = [.35, .5, .65], sampleFactors = [.15, ...visibleFactors, .85];
const checks = [], measurements = new Map();
const radiansToDegrees = value => value * 180 / Math.PI;
const round = value => Number(value.toFixed(7));
async function check(name, fn) {
  try { checks.push({ name, passed: true, ...await fn() }); }
  catch (error) { checks.push({ name, passed: false, error: error.stack }); }
}

// Calculate bounds from every actual source vertex in the root's parent space.
// Removing the controller's room transform prevents its global reveal from
// being mistaken for an independently animated small prop.
function actualBounds(node) {
  node.updateWorldMatrix(true, true);
  const inverse = node.parent.matrixWorld.clone().invert();
  const matrix = new THREE.Matrix4(), vertex = new THREE.Vector3(), box = new THREE.Box3();
  node.traverse(mesh => {
    if (!mesh.isMesh) return;
    matrix.multiplyMatrices(inverse, mesh.matrixWorld);
    const position = mesh.geometry.attributes.position;
    for (let i = 0; i < position.count; i++) box.expandByPoint(vertex.fromBufferAttribute(position, i).applyMatrix4(matrix));
  });
  assert.ok(!box.isEmpty(), `${node.userData.asset_id}: real mesh vertices exist`);
  return box;
}
async function fixture(options = {}) {
  const [roomGltf, welcomeGltf] = await Promise.all([parseModelForCPU(roomPath), parseModelForCPU(terminalPath)]);
  createRoomEntryAttachments({ THREE, room: roomGltf.scene });
  roomGltf.scene.updateMatrixWorld(true);
  const baselines = new Map(), ids = new Set(Object.values(families).flat());
  roomGltf.scene.traverse(node => {
    if (!ids.has(node.userData.asset_id)) return;
    const box = actualBounds(node), support = box.getCenter(new THREE.Vector3()); support.y = box.min.y;
    baselines.set(node.userData.asset_id, { box, size: box.getSize(new THREE.Vector3()), support,
      anchorLocal: support.clone().applyMatrix4(node.matrix.clone().invert()),
      quaternion: node.quaternion.clone().normalize(), scale: node.scale.clone() });
  });
  return { ...introFixture({ roomGltf, welcomeGltf, ...options }), baselines };
}

// Seek the real production tween until its publicly exposed factor reaches the
// requested value. Do not reproduce production easing or set animation state.
function seekFactor(f, timeline, id, requested) {
  const state = () => f.roomEntry.getState().assets.find(asset => asset.id === id);
  const asset = state(); assert.ok(asset, `${id}: animated root exists`);
  let lower = asset.start, upper = asset.start + asset.duration;
  for (let i = 0; i < 24; i++) {
    const time = (lower + upper) / 2; timeline.time(time, false); f.intro.update();
    if (state().factor < requested) lower = time; else upper = time;
  }
  timeline.time((lower + upper) / 2, false); f.intro.update(); f.scene.updateMatrixWorld(true);
  assert.ok(Math.abs(state().factor - requested) < 2e-5, `${id}: sampled actual factor ${requested}`);
  return state();
}
function measure(f, id, state) {
  const node = f.roots.get(id), original = f.baselines.get(id), box = actualBounds(node), size = box.getSize(new THREE.Vector3());
  const rotation = node.quaternion.clone().normalize().multiply(original.quaternion.clone().invert()).normalize();
  if (rotation.w < 0) rotation.set(-rotation.x, -rotation.y, -rotation.z, -rotation.w);
  const anchor = original.anchorLocal.clone().applyMatrix4(node.matrix).sub(original.support);
  const horizontalSize = Math.max(original.size.x, original.size.z, 1e-8);
  const scale = node.scale.clone().divide(original.scale);
  const result = {
    factor: round(state.factor), rotationDegrees: round(radiansToDegrees(2 * Math.acos(THREE.MathUtils.clamp(rotation.w, -1, 1)))),
    yawDegrees: round(radiansToDegrees(2 * Math.atan2(Math.abs(rotation.y), Math.abs(rotation.w)))),
    tiltDegrees: round(radiansToDegrees(2 * Math.atan2(Math.hypot(rotation.x, rotation.z), Math.abs(rotation.w)))),
    liftMetres: round(box.min.y - original.box.min.y), liftHeightFraction: round((box.min.y - original.box.min.y) / original.size.y),
    horizontalAnchorMetres: round(Math.hypot(anchor.x, anchor.z)),
    horizontalAnchorFraction: round(Math.hypot(anchor.x, anchor.z) / horizontalSize),
    anchorOffset: anchor.toArray().map(round), scaleRatios: scale.toArray().map(round),
    heightLead: round(scale.y - Math.max(scale.x, scale.z)),
    visibleExtentFraction: round(size.length() / original.size.length()),
  };
  assert.ok(Object.values(result).flat().every(Number.isFinite), `${id}: finite real transform and geometry measurements`);
  return result;
}
function records(id, visibleOnly = true) {
  const samples = measurements.get(id); assert.ok(samples, `${id}: measurements available`);
  return samples.filter(sample => !visibleOnly || visibleFactors.some(value => Math.abs(value - sample.factor) < 2e-5));
}
function familyRecords(kind) { return families[kind].map(id => ({ id, samples: records(id) })); }

await check('all six motion families move substantial real geometry at 35%, 50% and 65% reveal', async () => {
  const f = await fixture();
  try {
    f.ready().progress(1); const timeline = f.enter();
    for (const [kind, ids] of Object.entries(families)) {
      for (const id of ids) {
        const samples = [];
        for (const factor of sampleFactors) {
          const state = seekFactor(f, timeline, id, factor);
          assert.equal(state.gesture, kind, `${id}: requested authored gesture is present`);
          const sample = measure(f, id, state); samples.push(sample);
          if (visibleFactors.includes(factor)) assert.ok(sample.visibleExtentFraction > .1,
            `${id} at ${factor}: the rotated mesh must already have a substantial extent, got ${sample.visibleExtentFraction}`);
        }
        measurements.set(id, samples);
      }
    }
    timeline.progress(1); f.intro.update(); f.assertRestored();
    assert.equal(f.roomEntry.getState().phase, 'complete');
    return { families: Object.keys(families), measuredRoots: measurements.size, samplesPerRoot: sampleFactors.length,
      exactNormalCompletionRestore: true, note: 'Visibility here means geometric extent; pixel appearance still requires browser review.' };
  } finally { f.cleanup(); }
});

await check('spin props retain and release a clear yaw while already visibly grown', () => {
  for (const id of families.spin) {
    const samples = records(id);
    assert.ok(samples.every(sample => sample.yawDegrees > 4), `${id}: yaw remains readable through 65% reveal`);
    assert.ok(samples[0].yawDegrees - samples[2].yawDegrees > 12, `${id}: at least 12 degrees of turning occurs between 35% and 65% reveal`);
    assert.ok(samples[1].yawDegrees > 12, `${id}: halfway pose has at least 12 degrees of visible yaw`);
  }
  return { records: familyRecords('spin') };
});

await check('hop props leave their support and return along a peaked vertical path', () => {
  for (const id of families.hop) {
    const samples = records(id, false), middle = records(id);
    const peak = Math.max(...middle.map(sample => sample.liftHeightFraction));
    assert.ok(middle.every(sample => sample.liftMetres > .001), `${id}: actual mesh bottom has positive support clearance at visible samples`);
    assert.ok(peak > .025, `${id}: hop rises by more than 2.5% of its height`);
    assert.ok(peak > samples[0].liftHeightFraction + .005 && peak > samples.at(-1).liftHeightFraction + .005,
      `${id}: real support clearance rises and then falls, rather than being a static offset`);
  }
  return { records: families.hop.map(id => ({ id, samples: records(id, false) })) };
});

await check('drift props float while travelling laterally within their available envelope', () => {
  for (const id of families.drift) {
    const samples = records(id);
    assert.ok(samples.some(sample => sample.liftMetres > .001), `${id}: drift has positive support clearance`);
    assert.ok(samples.some(sample => sample.horizontalAnchorFraction > .015), `${id}: drift carries the physical anchor sideways by at least 1.5% of its footprint`);
    const path = new THREE.Vector3().fromArray(samples[0].anchorOffset).distanceTo(new THREE.Vector3().fromArray(samples[2].anchorOffset));
    assert.ok(path > .003, `${id}: drift changes real position between visible samples`);
  }
  return { records: familyRecords('drift') };
});

await check('flip props tilt upright instead of only spinning around the vertical axis', () => {
  for (const id of families.flip) {
    const samples = records(id);
    assert.ok(samples[1].tiltDegrees > 3, `${id}: halfway pose visibly tips from its final upright orientation`);
    assert.ok(samples[0].tiltDegrees - samples[2].tiltDegrees > 4, `${id}: visible tilt returns toward upright`);
    assert.ok(samples[1].tiltDegrees > samples[1].yawDegrees, `${id}: flip is dominated by pitch or roll`);
  }
  return { records: familyRecords('flip') };
});

await check('dock props traverse a visible lateral path before fitting their final positions', () => {
  for (const id of families.dock) {
    const samples = records(id);
    assert.ok(samples.some(sample => sample.horizontalAnchorFraction > .02), `${id}: docking translates at least 2% of its physical footprint`);
    const path = new THREE.Vector3().fromArray(samples[0].anchorOffset).distanceTo(new THREE.Vector3().fromArray(samples[2].anchorOffset));
    assert.ok(path > .003, `${id}: docking moves the real anchor between 35% and 65% reveal`);
  }
  return { records: familyRecords('dock') };
});

await check('spring props extend vertically before widening, with a visible settling tilt', () => {
  for (const id of families.spring) {
    const samples = records(id);
    assert.ok(samples.some(sample => sample.heightLead > .045), `${id}: vertical extension leads horizontal scale by at least 4.5 percentage points`);
    assert.ok(samples.some(sample => sample.rotationDegrees > 2), `${id}: spring also has a visible angular settling motion`);
  }
  return { records: familyRecords('spring') };
});

await check('skipping halfway through every new motion family restores exact original transforms once', async () => {
  const results = [];
  for (const [kind, ids] of Object.entries(families)) {
    const f = await fixture(), id = ids[0];
    try {
      f.ready().progress(1); const timeline = f.enter(); const state = seekFactor(f, timeline, id, .5);
      const before = measure(f, id, state);
      assert.ok(before.visibleExtentFraction < 1, `${id}: skip targets an intermediate pose`);
      f.intro.skip(); f.intro.skip(); f.intro.update(); f.assertRestored();
      assert.equal(f.roomEntry.getState().phase, 'complete');
      assert.ok(f.roomEntry.getState().assets.every(asset => asset.factor === 1));
      assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1);
      results.push({ kind, id, factorBeforeSkip: state.factor, exactRestore: true, completionCount: f.counts.complete });
    } finally { f.cleanup(); }
  }
  return { records: results };
});

await check('reduced motion restores every new gesture without a partial reveal', async () => {
  const f = await fixture({ reducedMotion: true });
  try {
    f.ready().progress(1); f.enter(); f.intro.update(); f.assertRestored();
    assert.equal(f.roomEntry.getState().phase, 'complete');
    assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1);
    return { exactRestore: true, completionCount: f.counts.complete };
  } finally { f.cleanup(); }
});

const paths = ['src/room-entry.js', 'src/cube-intro.js', 'src/room-entry-attachments.js', 'scripts/lib/intro-controller-fixture.mjs',
  'scripts/check-prop-entry-motions.mjs', roomPath, terminalPath];
const report = { checkedAt: new Date().toISOString(),
  scope: 'Unchanged production controller, real GSAP timeline/easing and GLTFLoader mesh vertices. Original room reveal is removed from measurements. Tests measure visible-stage geometry and exact restoration, not rendered pixels, hardware FPS or exhaustive collision freedom.',
  method: 'Seek actual factor values via public start/duration/factor state; normalize source GLB quaternions only for angle measurement; measure physical source-geometry support clearances and anchor trajectories.',
  sourceSha256: Object.fromEntries(paths.map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')])),
  passed: checks.filter(item => item.passed).length, failed: checks.filter(item => !item.passed).length, checks };
writeFileSync(new URL('../docs/validation/prop-entry-motions.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
if (report.failed) process.exitCode = 1;
