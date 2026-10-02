import assert from 'node:assert/strict';
import { writeFileSync, mkdirSync } from 'node:fs';
import * as THREE from 'three';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { createRoomCameraGuard } from '../src/room-camera-guard.js';

const results = [], fixture = readRoomGeometry(process.argv.find(value => value.startsWith('/models/')));
const { room, components, modelUrl } = fixture;
const camera = new THREE.PerspectiveCamera(35, 16 / 9, .1, 500);
const controls = { target: new THREE.Vector3(-3, -1, -4), minDistance: 5, maxDistance: 45,
  minPolarAngle: 0, maxPolarAngle: Math.PI / 2, minAzimuthAngle: 0, maxAzimuthAngle: Math.PI / 2,
  minPan: new THREE.Vector3(-3, -1, -4), maxPan: new THREE.Vector3(2, 8, 8), enableDamping: true };
camera.position.set(11, 10.4, 18);
const builtAt = performance.now();
const guard = createRoomCameraGuard({ THREE, room, camera, controls });
const buildMs = performance.now() - builtAt;
const meshes = []; room.traverse(node => { if (node.isMesh) { meshes.push(node); node.material.side = THREE.DoubleSide; } });
const triangle = new THREE.Triangle(), point = new THREE.Vector3(), nearest = new THREE.Vector3(), bounds = new THREE.Box3();

// Independent brute-force geometric oracle, deliberately separate from guard BVH.
// It checks actual GLB triangles in world coordinates near the returned eye point.
function surfaceClearance(position, searchRadius = .5) {
  let distance = Infinity, meshName = null;
  room.updateMatrixWorld(true);
  for (const mesh of meshes) {
    if (!mesh.visible) continue;
    mesh.geometry.computeBoundingBox();
    bounds.copy(mesh.geometry.boundingBox).applyMatrix4(mesh.matrixWorld);
    if (bounds.distanceToPoint(position) > searchRadius) continue;
    const vertices = mesh.geometry.getAttribute('position'), indices = mesh.geometry.getIndex();
    const count = indices?.count ?? vertices.count;
    for (let index = 0; index < count; index += 3) {
      for (let corner = 0; corner < 3; corner++) {
        point.fromBufferAttribute(vertices, indices ? indices.getX(index + corner) : index + corner).applyMatrix4(mesh.matrixWorld);
        [triangle.a, triangle.b, triangle.c][corner].copy(point);
      }
      triangle.closestPointToPoint(position, nearest);
      const current = nearest.distanceTo(position);
      if (current < distance) { distance = current; meshName = mesh.name; }
    }
  }
  return { distance, meshName };
}
function check(name, run) { const detail = run() || {}; results.push({ check: name, status: 'passed', ...detail }); }
function pose(position, target = [-3, -1, -4]) {
  camera.position.fromArray(position); controls.target.fromArray(target); camera.lookAt(controls.target); guard.reset(); guard.update();
}
function move(position) {
  camera.position.fromArray(position); const intendedOffset = camera.position.clone().sub(controls.target);
  guard.update();
  const state = guard.getState();
  if (state.panLimited) {
    assert.ok(controls.target.clone().clamp(controls.minPan, controls.maxPan).distanceTo(controls.target) < 1e-8, 'a blocked slide keeps the target in range');
    assert.ok(camera.position.distanceTo(controls.target) >= controls.minDistance - 1e-8, 'a blocked slide retains a legal dolly distance');
  } else assert.ok(camera.position.clone().sub(controls.target).distanceTo(intendedOffset) < 1e-8, 'free collision slide preserves camera-target offset and zoom distance');
  const clearance = surfaceClearance(camera.position);
  assert.ok(clearance.distance >= state.radius - 8e-4,
    `near-plane sphere intersects ${clearance.meshName}: ${clearance.distance} < ${state.radius}`);
  return { intended: position, resolved: camera.position.toArray(), corrected: state.corrected,
    contact: state.lastContact, panLimited: state.panLimited, clearance: Number(clearance.distance.toFixed(6)), triangleTests: state.triangleTests };
}
function rayHit(origin, direction) {
  const ray = new THREE.Raycaster(new THREE.Vector3(...origin), new THREE.Vector3(...direction).normalize());
  const hit = ray.intersectObject(room, true)[0]; assert.ok(hit, 'actual GLB surface exists'); return hit;
}

check('rear wall: high-speed movement cannot tunnel through a finite thickness wall', () => {
  const origin = [0, 4.5, 0], hit = rayHit(origin, [0, 0, -1]);
  assert.match(hit.object.name, /room_static.*baked/);
  pose(origin); const result = move([0, 4.5, -6]);
  assert.equal(result.corrected, true); assert.ok(camera.position.z > hit.point.z);
  assert.ok(camera.position.z >= hit.point.z + guard.getState().radius - .002);
  return { ...result, actualSurfaceZ: hit.point.z };
});
check('window right frame: real frame geometry blocks the camera', () => {
  const origin = [3.15, 3, 2], hit = rayHit(origin, [0, 0, -1]);
  assert.match(hit.object.name, /room_static.*baked/);
  pose(origin); const result = move([3.15, 3, -4]);
  assert.equal(result.corrected, true); assert.ok(camera.position.z > hit.point.z);
  return { ...result, actualSurfaceZ: hit.point.z };
});
check('chair close-up: preserves fine chair shape and near-plane clearance', () => {
  const origin = [-1.35, 1.5, 2], hit = rayHit(origin, [0, 0, -1]);
  assert.match(hit.object.name, /work_chair/);
  pose(origin); const result = move([-1.35, 1.5, -.35]);
  assert.equal(result.corrected, true); assert.match(result.contact, /work_chair/);
  return result;
});
check('chair gap: empty space inside the furniture AABB stays accessible', () => {
  pose([-1.35, 2.3, 1.1]);
  const result = move([-1.35, 2.3, .7]);
  assert.equal(result.corrected, false); return result;
});
check('normal near view: camera-target distance 5 remains available', () => {
  const target = [-1.5, .5, -Math.sqrt(12)];
  pose([1.5, 2.5, .1], target);
  const result = move([1.5, 2.5, 0]);
  assert.equal(result.corrected, false); assert.ok(Math.abs(camera.position.distanceTo(controls.target) - 5) < 1e-8);
  return result;
});
check('merged architecture bounds do not fill the open room', () => {
  pose([-.8, 3, -.5]); const result = move([-.8, 3, -1.5]);
  assert.equal(result.corrected, false); return result;
});
check('tangential wall pan slides smoothly and moving away releases immediately', () => {
  pose([0, 3, -2.8]); const touched = move([0, 3, -3.5]);
  assert.equal(touched.corrected, true);
  const z = camera.position.z, slide = move([.8, 3, z - .2]);
  assert.ok(Math.abs(camera.position.x - .8) < .002, 'retains tangential movement');
  const release = move([.8, 3, -2.5]); assert.equal(release.corrected, false);
  return { slide, release };
});
check('current furniture transforms update collision geometry without rebuilding BVH', () => {
  const chair = components.get('furniture.work_chair'), scale = chair.scale.clone(), rotation = chair.quaternion.clone();
  chair.rotateY(.12); chair.scale.multiplyScalar(1.08); room.updateMatrixWorld(true);
  pose([-1.35, 1.5, 2]); const result = move([-1.35, 1.5, -.3]);
  assert.equal(result.corrected, true); assert.match(result.contact, /work_chair/);
  chair.scale.copy(scale); chair.quaternion.copy(rotation); room.updateMatrixWorld(true);
  return result;
});
check('wide viewport: sphere covers every near-plane corner after aspect change', () => {
  pose([0, 4.5, -2.8]); camera.aspect = 4; camera.updateProjectionMatrix();
  const result = move([0, 4.5, -3.4]);
  const nearHalfHeight = camera.near * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const cornerDistance = Math.hypot(camera.near, nearHalfHeight, nearHalfHeight * camera.aspect);
  assert.ok(guard.getState().radius >= cornerDistance + .034);
  camera.aspect = 16 / 9; camera.updateProjectionMatrix(); return result;
});
check('homepage, gallery, and scripted camera poses are untouched while disabled', () => {
  const position = [0, 4.5, -3.5], target = [3, 1, -8];
  camera.position.fromArray(position); controls.target.fromArray(target);
  assert.equal(guard.update({ enabled: false }), false);
  assert.deepEqual(camera.position.toArray(), position); assert.deepEqual(controls.target.toArray(), target);
  assert.equal(guard.getState().active, false);
  pose([11, 10.4, 18]);
});
check('idle camera: no triangle queries; nearby animation still invalidates the cached result', () => {
  pose([0, 3, 0]); guard.update();
  assert.equal(guard.getState().triangleTests, 0); assert.equal(guard.getState().nodeTests, 0);
  const chair = components.get('furniture.work_chair'), original = chair.position.clone();
  pose([-1.35, 1.5, .3]);
  const before = camera.position.clone(); chair.position.z += .18; room.updateMatrixWorld(true); guard.update();
  assert.ok(guard.getState().nodeTests > 0, 'moving nearby geometry invalidates the idle view');
  const clearance = surfaceClearance(camera.position);
  assert.ok(clearance.distance >= guard.getState().radius - 8e-4);
  chair.position.copy(original); room.updateMatrixWorld(true);
  return { correctedAfterPropMotion: camera.position.distanceTo(before) > 0 };
});
check('render mesh raycast is never called by guard; 120 Hz idle budget', () => {
  const saved = meshes.map(mesh => mesh.raycast); meshes.forEach(mesh => { mesh.raycast = () => { throw new Error('render mesh raycast used'); }; });
  pose([11, 10.4, 18]); const idle = [], navigation = [];
  for (let i = 0; i < 240; i++) {
    const time = performance.now(); guard.update(); idle.push(performance.now() - time);
  }
  pose([0, 3, 0]);
  for (let i = 0; i < 240; i++) {
    camera.position.x = Math.sin(i * .025) * .25;
    const time = performance.now(); guard.update(); navigation.push(performance.now() - time);
  }
  meshes.forEach((mesh, index) => { mesh.raycast = saved[index]; });
  const percentile = (values, fraction) => +values.sort((a, b) => a - b)[Math.floor(values.length * fraction)].toFixed(4);
  return { idleMedianMs: percentile(idle, .5), idleP95Ms: percentile(idle, .95),
    navigationMedianMs: percentile(navigation, .5), navigationP95Ms: percentile(navigation, .95) };
});
assert.equal(controls.minDistance, 5); assert.equal(controls.maxDistance, 45);
assert.equal(controls.minPolarAngle, 0); assert.equal(controls.maxPolarAngle, Math.PI / 2);
assert.equal(controls.minAzimuthAngle, 0); assert.equal(controls.maxAzimuthAngle, Math.PI / 2);
assert.deepEqual(controls.minPan.toArray(), [-3, -1, -4]); assert.deepEqual(controls.maxPan.toArray(), [2, 8, 8]);
assert.equal(controls.enableDamping, true);
const report = { modelUrl, buildMs: +buildMs.toFixed(3), colliderCount: guard.getState().colliderCount,
  triangleCount: guard.getState().triangleCount, checks: results.length, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(new URL('../docs/validation/', import.meta.url), { recursive: true });
  writeFileSync(new URL('../docs/validation/room-camera-guard.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report, null, 2));
