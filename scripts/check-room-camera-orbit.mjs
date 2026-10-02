import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import * as THREE from 'three';
import { OrbitControls } from '../src/utils/OrbitControls.js';
import { createRoomCameraGuard } from '../src/room-camera-guard.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

const { room, modelUrl } = readRoomGeometry(process.argv.find(value => value.startsWith('/models/')));
const camera = new THREE.PerspectiveCamera(35, 16 / 9, .1, 500);
const controls = new OrbitControls(camera, null);
Object.assign(controls, { enableDamping: true, dampingFactor: .05, minDistance: 5, maxDistance: 45,
  minPolarAngle: 0, maxPolarAngle: Math.PI / 2, minAzimuthAngle: 0, maxAzimuthAngle: Math.PI / 2,
  panSpeed: .6, zoomSpeed: .8 });
controls.minPan.set(-3, -1, -4); controls.maxPan.set(2, 8, 8);
const guard = createRoomCameraGuard({ THREE, room, camera, controls });
const triangle = new THREE.Triangle(), closest = new THREE.Vector3(), point = new THREE.Vector3();
// Independent world-space brute force oracle. Store transformed source triangles
// once; each sample scans mesh/triangle bounds linearly, without the guard's BVH.
const surfaces = [];
room.updateMatrixWorld(true);
room.traverse(mesh => {
  if (!mesh.isMesh) return;
  const position = mesh.geometry.getAttribute('position'), index = mesh.geometry.getIndex();
  const count = (index?.count ?? position.count) / 3, vertices = new Float64Array(count * 9), bounds = new Float64Array(count * 6);
  const box = new THREE.Box3();
  for (let face = 0; face < count; face++) {
    const localBox = new THREE.Box3();
    for (let corner = 0; corner < 3; corner++) {
      point.fromBufferAttribute(position, index ? index.getX(face * 3 + corner) : face * 3 + corner).applyMatrix4(mesh.matrixWorld);
      vertices.set(point.toArray(), face * 9 + corner * 3); localBox.expandByPoint(point);
    }
    bounds.set([...localBox.min.toArray(), ...localBox.max.toArray()], face * 6); box.union(localBox);
  }
  surfaces.push({ name: mesh.name, vertices, bounds, count, box });
});
function clearance(radius) {
  let distance = Infinity, name = null;
  const p = camera.position;
  for (const surface of surfaces) {
    if (surface.box.distanceToPoint(p) > radius + .001) continue;
    for (let face = 0; face < surface.count; face++) {
      const b = face * 6, bounds = surface.bounds;
      if (bounds[b] > p.x + radius || bounds[b + 3] < p.x - radius || bounds[b + 1] > p.y + radius ||
        bounds[b + 4] < p.y - radius || bounds[b + 2] > p.z + radius || bounds[b + 5] < p.z - radius) continue;
      const v = face * 9;
      triangle.a.fromArray(surface.vertices, v); triangle.b.fromArray(surface.vertices, v + 3); triangle.c.fromArray(surface.vertices, v + 6);
      triangle.closestPointToPoint(p, closest); const next = closest.distanceTo(p);
      if (next < distance) { distance = next; name = surface.name; }
    }
  }
  return { distance, name };
}
function start(position, target) {
  camera.position.fromArray(position); controls.target.fromArray(target);
  controls._panOffset.set(0, 0, 0); controls._sphericalDelta.set(0, 0, 0); controls._scale = 1;
  controls.update(1 / 120); guard.reset(); guard.update();
}
const cases = [
  { name: 'rear wall: damped pan at minimum target X', position: [2, 4.5, 0], target: [-3, 4.5, 0], pan: [0, 0, -.12], inputFrames: 180, mustHit: /room_static/ },
  { name: 'window frame: repeated pan into narrow frame', position: [3.15, 3, 2], target: [-1.85, 3, 2], pan: [0, 0, -.1], inputFrames: 150, mustHit: /room_static/ },
  { name: 'chair: dolly from the minimum pan corner', position: [-.6, 2.75, 2.15], target: [-3, -1, -4], zoom: .97, inputFrames: 180, mustHit: /work_chair/ },
  { name: 'chair: oblique dolly and pan-clamp contact', position: [0, 3.5, 2.3], target: [-3, -1, -4], zoom: .97, inputFrames: 180, mustHit: /work_chair/ },
  { name: 'chair side: pan into chair while dolly reaches minimum distance', position: [.2, 1.5, .2], target: [-1.8, -1, -4], pan: [-.08, 0, 0], zoom: .997, inputFrames: 140, mustHit: /work_chair/ },
  { name: 'normal close-up: full distance-5 view stays available', position: [4.5, 4.5, Math.sqrt(12)], target: [-1.5, .5, -Math.sqrt(12)], zoom: .97, inputFrames: 150, mustStayFree: true },
];
const results = [];
for (const spec of cases) {
  start(spec.position, spec.target);
  let correctedFrames = 0, maxStepAfterSettling = 0, lateCorrections = 0, lateTriangleTests = 0, lateNodeTests = 0, maxTargetOutsideAfterSettling = 0;
  let minimumClearance = Infinity, sourceSamples = 0, maxReleaseAdvance = 0;
  const contacts = new Set(), costs = [], lastFrame = new THREE.Vector3(), firstSettledPosition = new THREE.Vector3();
  // 800 frames after release deliberately exceeds damping decay at 120 Hz;
  // the last 120 frames must be an actual fixed point, including target clamps.
  for (let frame = 0; frame < spec.inputFrames + 800; frame++) {
    if (frame < spec.inputFrames) {
      // These are the same world pan accumulator and dolly methods used by the
      // template's mouse/touch handlers; no replacement controls are involved.
      if (spec.pan) controls._panOffset.add(point.fromArray(spec.pan));
      if (spec.zoom) controls._dollyIn(spec.zoom);
    }
    lastFrame.copy(camera.position);
    const started = performance.now(); controls.update(1 / 120); guard.update(); costs.push(performance.now() - started);
    const state = guard.getState();
    if (state.corrected) correctedFrames++;
    if (state.lastContact) contacts.add(state.lastContact);
    const sample = clearance(state.radius); sourceSamples++;
    minimumClearance = Math.min(minimumClearance, sample.distance);
    assert.ok(sample.distance >= state.radius - .0008,
      `${spec.name}, frame ${frame}: near plane sphere penetrates ${sample.name}: ${sample.distance}`);
    assert.ok(camera.position.distanceTo(controls.target) >= controls.minDistance - 1e-7, 'minimum dolly distance preserved');
    assert.ok(point.copy(controls.target).clamp(controls.minPan, controls.maxPan).distanceTo(controls.target) < 1e-7, 'target remains within the template pan bounds');
    if (frame === spec.inputFrames + 680) firstSettledPosition.copy(camera.position);
    if (frame >= spec.inputFrames + 680) {
      maxStepAfterSettling = Math.max(maxStepAfterSettling, camera.position.distanceTo(lastFrame));
      maxReleaseAdvance = Math.max(maxReleaseAdvance, camera.position.distanceTo(firstSettledPosition));
      maxTargetOutsideAfterSettling = Math.max(maxTargetOutsideAfterSettling, point.copy(controls.target).clamp(controls.minPan, controls.maxPan).distanceTo(controls.target));
      if (state.corrected) lateCorrections++;
      lateTriangleTests += state.triangleTests; lateNodeTests += state.nodeTests;
    }
  }
  assert.ok(maxStepAfterSettling < 1e-7, `${spec.name}: collision/target clamp causes post-release jitter`);
  assert.ok(maxReleaseAdvance < 1e-7, `${spec.name}: camera continues advancing after settling`);
  assert.ok(maxTargetOutsideAfterSettling < 1e-7, `${spec.name}: camera correction leaves target outside pan bounds`);
  assert.equal(lateCorrections, 0, `${spec.name}: collision correction keeps fighting pan clamp after release`);
  assert.equal(lateTriangleTests, 0, `${spec.name}: idle state must restore zero triangle tests`);
  assert.equal(lateNodeTests, 0, `${spec.name}: idle state must restore zero BVH queries`);
  if (spec.mustHit) assert.ok([...contacts].some(name => spec.mustHit.test(name)), `${spec.name}: replay must reach actual obstacle`);
  if (spec.mustStayFree) {
    assert.equal(correctedFrames, 0, 'normal close-up must remain unchanged');
    assert.ok(Math.abs(camera.position.distanceTo(controls.target) - 5) < 1e-7);
    assert.ok(camera.position.distanceTo(new THREE.Vector3(1.5, 2.5, 0)) < 1e-7);
  }
  costs.sort((a, b) => a - b);
  results.push({ check: spec.name, status: 'passed', frames: spec.inputFrames + 800, sourceSamples, correctedFrames,
    contacts: [...contacts], finalCamera: camera.position.toArray(), finalTarget: controls.target.toArray(),
    finalDistance: camera.position.distanceTo(controls.target), minimumClearance: Number.isFinite(minimumClearance) ? minimumClearance : null,
    lateCorrections, lateTriangleTests, lateNodeTests, maxStepAfterSettling, maxReleaseAdvance, maxTargetOutsideAfterSettling,
    loopMedianMs: costs[Math.floor(costs.length * .5)], loopP95Ms: costs[Math.floor(costs.length * .95)] });
}
const report = { modelUrl, controls: 'src/utils/OrbitControls.js (real instance, null DOM)', fps: 120,
  checks: results.length, parameters: { minDistance: 5, maxDistance: 45, dampingFactor: .05,
    polar: [0, Math.PI / 2], azimuth: [0, Math.PI / 2], minPan: [-3, -1, -4], maxPan: [2, 8, 8] }, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(new URL('../docs/validation/', import.meta.url), { recursive: true });
  writeFileSync(new URL('../docs/validation/room-camera-orbit.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report, null, 2));
