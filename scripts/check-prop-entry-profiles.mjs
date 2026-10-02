import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';
import { createRoomEntry, ROOM_ENTRY_GROUPS, ROOM_ENTRY_PROFILES } from '../src/room-entry.js';
import { createRoomEntryAttachments } from '../src/room-entry-attachments.js';

const modelPath = 'public/models/orbital-atelier-v16.glb';
const ids = ROOM_ENTRY_GROUPS.flatMap(([, list]) => list);
const checks = [], records = [], factors = [.2, .35, .5, .65, .82, .93];
const round = n => +n.toFixed(7);
async function check(name, run) {
  try { checks.push({ name, passed: true, ...await run() }); }
  catch (error) { checks.push({ name, passed: false, error: error.stack }); }
}
function actualBox(root) {
  root.updateWorldMatrix(true, true);
  const inverse = root.parent.matrixWorld.clone().invert(), matrix = new THREE.Matrix4();
  const point = new THREE.Vector3(), box = new THREE.Box3();
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    matrix.multiplyMatrices(inverse, mesh.matrixWorld);
    const attr = mesh.geometry.attributes.position;
    for (let i = 0; i < attr.count; i++) box.expandByPoint(point.fromBufferAttribute(attr, i).applyMatrix4(matrix));
  });
  return box;
}
async function fixture(externalIds = []) {
  const gltf = await parseModelForCPU(modelPath), room = gltf.scene;
  createRoomEntryAttachments({ THREE, room });
  const exterior = []; room.traverse(n => { if (['environment.orbital_dock', 'environment.warm_gallery'].includes(n.userData.asset_id)) exterior.push(n); });
  exterior.forEach(n => n.removeFromParent());
  room.updateMatrixWorld(true);
  const roots = new Map(), snapshots = new WeakMap(), originals = new Map();
  room.traverse(node => {
    if (!ids.includes(node.userData.asset_id)) return;
    roots.set(node.userData.asset_id, node);
    const original = { position: node.position.clone(), rotation: node.rotation.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone() };
    const box = actualBox(node), anchor = box.getCenter(new THREE.Vector3()); anchor.y = box.min.y;
    originals.set(node.userData.asset_id, { ...original, box, size: box.getSize(new THREE.Vector3()), anchor,
      localAnchor: anchor.clone().applyMatrix4(node.matrix.clone().invert()) });
    snapshots.set(node, original);
  });
  const bounds = new THREE.Box3().setFromObject(room), entry = createRoomEntry({ room, roots, snapshots, bounds, externalIds });
  const timeline = gsap.timeline({ paused: true });
  return { room, roots, entry, originals, timeline,
    start() { entry.appendTo(timeline, .9); },
    state(id) { return entry.getState().assets.find(a => a.id === id); },
    seek(factor, id) {
      const asset = this.state(id); let low = asset.start, high = asset.start + asset.duration;
      for (let i = 0; i < 24; i++) {
        const time = (low + high) / 2; timeline.time(time, false); entry.update();
        if (this.state(id).factor < factor) low = time; else high = time;
      }
      timeline.time((low + high) / 2, false); entry.update(); room.updateMatrixWorld(true);
      assert.ok(Math.abs(this.state(id).factor - factor) < 2e-5);
    },
    assertRestored() {
      for (const [id, node] of roots) {
        const old = originals.get(id);
        assert.deepEqual(node.position.toArray(), old.position.toArray(), `${id}: position`);
        assert.deepEqual(node.quaternion.toArray(), old.quaternion.toArray(), `${id}: quaternion`);
        assert.deepEqual(node.scale.toArray(), old.scale.toArray(), `${id}: scale`);
      }
    },
    cleanup() { timeline.kill(); gsap.ticker.sleep(); },
  };
}

await check('36 legacy roots and the optional V19 ceiling light have individually authored profiles', () => {
  assert.equal(ids.length, 36);
  const expected = [...ids, 'lighting.ceiling_warm'];
  assert.deepEqual(Object.keys(ROOM_ENTRY_PROFILES).sort(), expected.sort());
  assert.equal(new Set(Object.values(ROOM_ENTRY_PROFILES).map(p => p.name)).size, expected.length);
  assert.equal(new Set(Object.values(ROOM_ENTRY_PROFILES).map(p => JSON.stringify([p.grow, p.rotationAxis, p.rotationWindow, p.path, p.rebound, p.accent]))).size, expected.length);
  return { authoredProfiles: expected.length, uniqueNames: 37, uniqueTransformProfiles: 37 };
});

await check('all 36 real-geometry motion trajectories differ after removing size, original pose and stagger timing', async () => {
  const f = await fixture(); let worstEscape = 0, minDistance = Infinity, nearestPair;
  try {
    f.start();
    for (const id of ids) {
      const node = f.roots.get(id), old = f.originals.get(id), samples = [];
      for (const factor of factors) {
        f.seek(factor, id);
        const box = actualBox(node), q = node.quaternion.clone().normalize().multiply(old.quaternion.clone().normalize().invert()).normalize();
        if (q.w < 0) q.set(-q.x, -q.y, -q.z, -q.w);
        const offset = old.localAnchor.clone().applyMatrix4(node.matrix).sub(old.anchor).divide(old.size);
        const scale = node.scale.clone().divide(old.scale);
        const values = [...offset.toArray(), ...q.toArray(), ...scale.toArray()];
        assert.ok(values.every(Number.isFinite), `${id}: finite trajectory`);
        const escape = Math.max(old.box.min.x - box.min.x, box.max.x - old.box.max.x,
          old.box.min.y - box.min.y, box.max.y - old.box.max.y,
          old.box.min.z - box.min.z, box.max.z - old.box.max.z, 0);
        worstEscape = Math.max(worstEscape, escape);
        const state = f.state(id);
        if (state.support) assert.equal(f.state(state.support).factor, 1, `${id}: support is fully built`);
        samples.push({ factor, normalizedPose: values.map(round) });
      }
      const state = f.state(id);
      records.push({ id, motionName: state.motionName, family: state.gesture, duration: state.duration, samples });
    }
    for (let a = 0; a < records.length; a++) for (let b = a + 1; b < records.length; b++) {
      const v1 = records[a].samples.flatMap(s => s.normalizedPose), v2 = records[b].samples.flatMap(s => s.normalizedPose);
      const distance = Math.sqrt(v1.reduce((sum, n, i) => sum + (n - v2[i]) ** 2, 0));
      if (distance < minDistance) { minDistance = distance; nearestPair = [records[a].id, records[b].id]; }
      assert.ok(distance > .06, `${records[a].id} vs ${records[b].id}: motion difference must exceed numeric noise; ${distance}`);
    }
    assert.ok(worstEscape < 1e-5, `actual vertices escaped envelope by ${worstEscape}`);
    f.timeline.progress(1); f.entry.update(); f.entry.restore(); f.assertRestored();
    return { roots: records.length, factors, pairComparisons: 630, minimumNormalizedTrajectoryDistance: round(minDistance), nearestPair,
      maximumActualVertexEnvelopeEscape: worstEscape, exactFinalRestoration: true };
  } finally { f.cleanup(); }
});

await check('skip from an expressive midpoint restores all exact original transforms', async () => {
  const f = await fixture();
  try {
    f.start(); f.seek(.5, 'ceramic_mobius_study');
    assert.ok(f.roots.get('ceramic_mobius_study').quaternion.angleTo(f.originals.get('ceramic_mobius_study').quaternion) > .4);
    f.timeline.kill(); f.entry.restore(); f.entry.restore(); f.assertRestored();
    assert.ok(f.entry.getState().assets.every(a => a.factor === 1));
    return { restoredRoots: 36, repeatedRestoreIsSafe: true };
  } finally { f.cleanup(); }
});

await check('externally controlled terminal never receives a competing entry transform and still restores', async () => {
  const id = 'folding_drawing_terminal', f = await fixture([id]);
  try {
    const node = f.roots.get(id), original = f.originals.get(id);
    assert.deepEqual(node.scale.toArray(), original.scale.toArray(), 'constructor never hides externally controlled terminal');
    node.position.add(new THREE.Vector3(.12, .18, -.04)); node.scale.multiplyScalar(.72); node.rotation.y += .42;
    const pose = node.matrix.clone(); node.updateMatrix(); pose.copy(node.matrix);
    f.start();
    for (const t of [1, 2.5, 3.2, f.timeline.duration()]) {
      f.timeline.time(t, false); f.entry.setExternalProgress(id, t / f.timeline.duration()); f.entry.update(); node.updateMatrix();
      assert.deepEqual(node.matrix.toArray(), pose.toArray(), `no competing transform at ${t}`);
    }
    assert.equal(f.state(id).externalControlled, true); assert.equal(f.state(id).factor, 1);
    assert.throws(() => f.entry.setExternalProgress('thermal_cup', .5));
    assert.throws(() => f.entry.setExternalProgress(id, NaN));
    assert.throws(() => f.entry.setExternalControl(id, false));
    f.entry.restore(); f.assertRestored();
    return { constructorOwnership: true, competingTransforms: 0, externalProgressDiagnostic: true, exactRestore: true };
  } finally { f.cleanup(); }
});

await check('prepared-time external control can be assigned or withdrawn without stale hidden transforms', async () => {
  const id = 'folding_drawing_terminal', f = await fixture();
  try {
    const node = f.roots.get(id), old = f.originals.get(id);
    assert.notDeepEqual(node.scale.toArray(), old.scale.toArray());
    f.entry.setExternalControl(id); assert.deepEqual(node.scale.toArray(), old.scale.toArray());
    f.entry.setExternalControl(id, false); assert.notDeepEqual(node.scale.toArray(), old.scale.toArray());
    f.entry.setExternalControl(id); f.entry.restore(); f.assertRestored();
    return { ownershipToggles: 3, exactRestore: true };
  } finally { f.cleanup(); }
});

const paths = ['src/room-entry.js', 'src/room-entry-profiles.js', 'src/room-entry-attachments.js', 'scripts/check-prop-entry-profiles.mjs', modelPath];
const report = { checkedAt: new Date().toISOString(),
  scope: 'Actual GLTFLoader meshes, attachments and GSAP timeline. Image decoding omitted. Six equal reveal factors per root remove group stagger from the pair comparison; the vectors normalize world size and original transforms. This is a geometry/motion test, not a pixel or hardware-frame-rate claim.',
  sourceSha256: Object.fromEntries(paths.map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')])),
  passed: checks.filter(c => c.passed).length, failed: checks.filter(c => !c.passed).length, checks, records };
writeFileSync(new URL('../docs/validation/prop-entry-profiles-v7.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ passed: report.passed, failed: report.failed, checks }, null, 2));
if (report.failed) process.exitCode = 1;
