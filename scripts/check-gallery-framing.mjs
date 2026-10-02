import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import * as THREE from 'three';
import { createGalleryFraming } from '../src/gallery-framing.js';
import { sampleTravelPose, GALLERY_OFFSET } from '../src/gallery-transition-path.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

const file = path => new URL(`../${path}`, import.meta.url);
const gallerySource = readFileSync(file('src/works-gallery.js'), 'utf8');
const mainSource = readFileSync(file('src/main.js'), 'utf8');
const modelUrl = gallerySource.match(/loadAsync\('([^']+\.glb)'/)?.[1];
const { room: model, components } = readRoomGeometry(modelUrl);
const sourcePose = new Map();
model.traverse(node => sourcePose.set(node, { position: node.position.toArray(), quaternion: node.quaternion.toArray(), scale: node.scale.toArray(), parent: node.parent, visible: node.visible }));
const framing = createGalleryFraming(model), vertices = [], excluded = new Map();
const point = new THREE.Vector3();
model.traverse(node => {
  if (!node.isMesh) return;
  let excludedOwner = null, visible = true;
  for (let parent = node; parent; parent = parent.parent) {
    if (!parent.visible) visible = false;
    if (parent.userData.asset_id?.startsWith('gallery.environment.')) excludedOwner = parent.userData.asset_id;
  }
  const positions = node.geometry.attributes.position;
  if (!visible || excludedOwner) { if (excludedOwner) excluded.set(excludedOwner, (excluded.get(excludedOwner) ?? 0) + positions.count); return; }
  for (let index = 0; index < positions.count; index++) vertices.push(point.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld).clone());
});
const realBounds = new THREE.Box3().setFromPoints(vertices), results = [];
const close = (a, b, tolerance = 1e-7) => assert.ok(Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
const sameVector = (a, b, tolerance = 1e-7) => a.toArray().forEach((value, index) => close(value, b.toArray()[index], tolerance));
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.stack }); }
}

await check('framing excludes the retained terrace without moving, hiding or deleting any runtime assets', () => {
  framing.pose(1.6);
  assert.equal(framing.getState().vertices, vertices.length);
  assert.ok(excluded.has('gallery.environment.terrace'), 'actual runtime still contains its surrounding terrace');
  for (const [node, original] of sourcePose) {
    assert.deepEqual(node.position.toArray(), original.position); assert.deepEqual(node.quaternion.toArray(), original.quaternion);
    assert.deepEqual(node.scale.toArray(), original.scale); assert.equal(node.parent, original.parent); assert.equal(node.visible, original.visible);
  }
  assert.ok(components.get('gallery.environment.terrace').parent, 'background remains in the scene');
  return { vertices: vertices.length, retainedAssets: components.size, excludedFramingVertices: Object.fromEntries(excluded) };
});

await check('every authored corridor vertex fits desktop, square and portrait views with the requested margins', () => {
  const views = [];
  for (const [width, height, fov] of [[1920, 1080, 35], [1440, 900, 35], [844, 795, 35], [844, 390, 35], [390, 844, 35], [320, 740, 35], [768, 1024, 35], [390, 844, 45]]) {
    const aspect = width / height, pose = framing.pose(aspect, fov), distance = pose.position.distanceTo(pose.target);
    const camera = new THREE.PerspectiveCamera(fov, aspect, .1, 500);
    camera.position.copy(pose.position); camera.lookAt(pose.target); camera.updateMatrixWorld(true);
    const projected = new THREE.Box3(); for (const vertex of vertices) projected.expandByPoint(point.copy(vertex).project(camera));
    const horizontalLimit = aspect < .8 ? .88 : .92;
    assert.ok(projected.min.x >= -horizontalLimit - 1e-5 && projected.max.x <= horizontalLimit + 1e-5, 'both corridor ends remain visible');
    assert.ok(projected.min.y >= -.82001 && projected.max.y <= .82001, 'upper glass and front plinth remain visible');
    assert.ok(projected.min.z > -1 && projected.max.z < 1, 'no near/far clipping');
    assert.ok(Math.abs(projected.min.x + projected.max.x) < .004 && Math.abs(projected.min.y + projected.max.y) < .004, 'silhouette is visually centred');
    assert.ok(realBounds.distanceToPoint(camera.position) > 10, 'home camera remains outside the corridor');
    close(pose.maxDistance, distance * 1.12); assert.ok(pose.maxDistance > 10);
    views.push({ viewport: [width, height], fov, distance, maxDistance: pose.maxDistance, cameraClearance: realBounds.distanceToPoint(camera.position),
      widthPercent: (projected.max.x - projected.min.x) * 50, heightPercent: (projected.max.y - projected.min.y) * 50,
      projected: { min: projected.min.toArray(), max: projected.max.toArray() }, target: pose.target.toArray() });
  }
  return { views };
});

await check('cached poses and diagnostic copies cannot be mutated by callers, and projection changes refit deterministically', () => {
  const first = framing.pose(1.6, 35), expected = { position: first.position.clone(), target: first.target.clone(), maxDistance: first.maxDistance };
  const second = framing.pose(1.6, 35);
  assert.notEqual(first.position, second.position); assert.notEqual(first.target, second.target);
  first.position.set(999, 999, 999); first.target.set(-999, -999, -999); first.maxDistance = 0;
  const stateCopy = framing.getState(); stateCopy.silhouette.minX = -500;
  const third = framing.pose(1.6, 35); sameVector(third.position, expected.position); sameVector(third.target, expected.target); close(third.maxDistance, expected.maxDistance);
  const portrait = framing.pose(390 / 844, 35); assert.ok(portrait.position.distanceTo(portrait.target) > expected.position.distanceTo(expected.target));
  const wideFov = framing.pose(390 / 844, 45); assert.ok(wideFov.position.distanceTo(wideFov.target) < portrait.position.distanceTo(portrait.target));
  const restored = framing.pose(1.6, 35); sameVector(restored.position, expected.position); sameVector(restored.target, expected.target);
  for (const [aspect, fov] of [[0, 35], [-1, 35], [NaN, 35], [1, 0], [1, 180], [1, NaN]]) assert.throws(() => framing.pose(aspect, fov));
});

await check('gallery zoom bounds retain work focus while returning restores separate room bounds', () => {
  const body = mainSource.match(/function applySceneLimits\([^]*?\n\}/)?.[0]; assert.ok(body);
  const controls = { minPan: new THREE.Vector3(), maxPan: new THREE.Vector3() };
  const camera = { aspect: 1.6, fov: 35 }, state = { currentScene: 'gallery' };
  const context = vm.createContext({ controls, camera, state, worksGallery: { pose: framing.pose }, savedRoomPose: { maxDistance: 63 } });
  vm.runInContext(body, context);
  const views = [];
  for (const aspect of [1.6, 390 / 844]) {
    camera.aspect = aspect; vm.runInContext('applySceneLimits()', context);
    const focusDistance = Math.max(10, 4.5 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / aspect);
    close(controls.minDistance, 10); close(controls.maxDistance, framing.pose(aspect, 35).maxDistance);
    assert.ok(focusDistance >= controls.minDistance && focusDistance <= controls.maxDistance, 'existing work-focus view remains attainable');
    views.push({ aspect, minDistance: controls.minDistance, maxDistance: controls.maxDistance, workFocusDistance: focusDistance });
  }
  state.currentScene = 'room'; vm.runInContext('applySceneLimits()', context);
  close(controls.minDistance, 5); close(controls.maxDistance, 63);
  assert.deepEqual(controls.minPan.toArray(), [-3, -1, -4]); assert.deepEqual(controls.maxPan.toArray(), [2, 8, 8]);
  return { galleryViews: views, room: { minDistance: controls.minDistance, maxDistance: controls.maxDistance } };
});

await check('tail push approaches the exact framed endpoint, never overshoots it, and preserves returning and reduced-motion endpoints', () => {
  const views = [];
  for (const aspect of [1920 / 1080, 1.6, 390 / 844, 320 / 740]) {
    const roomPose = { position: new THREE.Vector3(12, 10, 16), target: new THREE.Vector3(0, 2, 0) }, galleryPose = framing.pose(aspect, 35);
    const sourceCamera = new THREE.PerspectiveCamera(35, aspect, .1, 500), destinationCamera = sourceCamera.clone(), stageCamera = sourceCamera.clone();
    const sourceTarget = new THREE.Vector3(), destinationTarget = new THREE.Vector3();
    const sample = (progress, returning = false, reducedMotion = false) => sampleTravelPose({ source: returning ? galleryPose : roomPose, destination: returning ? roomPose : galleryPose,
      progress, returning, reducedMotion, sourceCamera, destinationCamera, sourceTarget, destinationTarget, stageCamera });
    sample(0); sameVector(sourceCamera.position, roomPose.position); sameVector(sourceTarget, roomPose.target);
    let previousDistance = Infinity, lastStep = 0, previousPosition;
    const distance = galleryPose.position.distanceTo(galleryPose.target);
    for (let step = 0; step <= 120; step++) {
      const progress = .7 + step / 120 * .3; sample(progress);
      const currentDistance = destinationCamera.position.distanceTo(destinationTarget);
      assert.ok(currentDistance >= distance - 1e-7, 'arrival never passes the fitted camera radius');
      assert.ok(currentDistance <= previousDistance + 1e-7, 'final approach continuously moves forward');
      if (previousPosition) lastStep = previousPosition.distanceTo(destinationCamera.position);
      previousDistance = currentDistance; previousPosition = destinationCamera.position.clone();
      sameVector(stageCamera.position, destinationCamera.position.clone().add(GALLERY_OFFSET), 1e-6);
    }
    sameVector(destinationCamera.position, galleryPose.position); sameVector(destinationTarget, galleryPose.target);
    assert.ok(lastStep < .001, 'final step settles without a snap');
    sample(0, true); sameVector(sourceCamera.position, galleryPose.position); sameVector(sourceTarget, galleryPose.target);
    sample(1, true); sameVector(destinationCamera.position, roomPose.position); sameVector(destinationTarget, roomPose.target);
    for (const returning of [false, true]) for (const progress of [0, .5, 1]) {
      sample(progress, returning, true);
      sameVector(sourceCamera.position, returning ? galleryPose.position : roomPose.position);
      sameVector(destinationCamera.position, returning ? roomPose.position : galleryPose.position);
    }
    views.push({ aspect, finalDistance: distance, lastStepDistance: lastStep, forwardSamples: 121, returningEndpointPreserved: true, reducedMotionEndpointsPreserved: true });
  }
  return { views };
});

const sourceFiles = ['src/gallery-framing.js', 'src/works-gallery.js', 'src/gallery-transition-path.js', 'src/main.js', 'scripts/check-gallery-framing.mjs', `public${modelUrl}`];
const report = { checkedAt: new Date().toISOString(), model: modelUrl, runtime: process.version, threeRevision: THREE.REVISION,
  sourceSha256: Object.fromEntries(sourceFiles.map(path => [path, createHash('sha256').update(readFileSync(file(path))).digest('hex')])),
  methodology: 'Actual runtime GLB vertices and production framing, travel path and scene-limit function. Real mathematical camera projection, cache isolation and endpoint checks. No GPU render, visual quality, FPS or exhaustive free-orbit collision claim.',
  passed: results.filter(item => item.status === 'passed').length, failed: results.filter(item => item.status === 'failed').length, results };
if (process.argv.includes('--write-report')) { mkdirSync(file('docs/validation/'), { recursive: true }); writeFileSync(file('docs/validation/gallery-framing-v2.json'), JSON.stringify(report, null, 2) + '\n'); }
console.log(JSON.stringify({ checks: results.length, passed: report.passed, failed: report.failed, failures: results.filter(item => item.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
