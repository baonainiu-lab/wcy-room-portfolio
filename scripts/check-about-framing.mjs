import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { createAboutFraming } from '../src/about-framing.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

const modelUrl = process.argv.find(value => value.endsWith('.glb')) ?? '/models/about-atelier-v3-compressed.glb';
const { room: model, components, data } = readRoomGeometry(modelUrl);
const framing = createAboutFraming(model), sourceTransforms = new Map(), vertices = [];
const point = new THREE.Vector3();
model.traverse(node => {
  sourceTransforms.set(node, { position: node.position.toArray(), quaternion: node.quaternion.toArray(), scale: node.scale.toArray(), parent: node.parent });
  if (!node.isMesh) return;
  const positions = node.geometry.attributes.position;
  for (let index = 0; index < positions.count; index++) {
    point.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld);
    vertices.push(point.x, point.y, point.z);
  }
});
const close = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} differs from ${expected}`);
const results = [];
const check = (name, run) => {
  try { results.push({ check: name, status: 'passed', ...run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.stack }); }
};

check('web derivative retains all 128 source identities, the real return button and four baked material slots', () => {
  const source = JSON.parse(readFileSync(new URL('../assets/blender/about-atelier-v3-audit.json', import.meta.url)));
  assert.equal(components.size, 128);
  assert.deepEqual([...components.keys()].sort(), source.assetIds.slice().sort());
  assert.ok(components.get('atelier.return.interface'));
  assert.equal(components.get('atelier.return.interface').userData.interaction, 'return_room');
  for (let index = 0; index < 4; index++) assert.ok(data.materials.find(material => material.name === `ATELIER_LIGHTMAP_${index}`));
  assert.ok(data.materials.find(material => material.name === 'ATELIER_GLASS'));
  assert.ok(data.materials.some(material => material.name.startsWith('ATELIER_METAL_')));
  return { assetCount: components.size, materials: data.materials.map(material => material.name) };
});

check('complete authored silhouette remains visible and centred across desktop, tablet and phone', () => {
  const views = [];
  for (const [width, height, fov] of [[1500, 1000, 35], [1920, 1080, 35], [1440, 900, 35], [1024, 1024, 35], [844, 390, 35], [390, 844, 35], [320, 740, 35], [768, 1024, 35], [390, 844, 45]]) {
    const aspect = width / height, pose = framing.pose(aspect, fov);
    const camera = new THREE.PerspectiveCamera(fov, aspect, .1, 500);
    camera.position.copy(pose.position); camera.lookAt(pose.target); camera.updateMatrixWorld(true);
    const projected = new THREE.Box3();
    let radiusSquared = 0;
    for (let index = 0; index < vertices.length; index += 3) {
      point.fromArray(vertices, index);
      radiusSquared = Math.max(radiusSquared, point.distanceToSquared(pose.target));
      projected.expandByPoint(point.project(camera));
    }
    assert.ok(projected.min.x >= -.88001 && projected.max.x <= .88001, 'all left/right edges retained');
    assert.ok(projected.min.y >= -.89001 && projected.max.y <= .89001, 'plant crown and platform retained');
    assert.ok(projected.min.z > -1 && projected.max.z < 1, 'no near/far clipping');
    assert.ok(Math.abs(projected.min.x + projected.max.x) < .001 && Math.abs(projected.min.y + projected.max.y) < .001, 'projected silhouette centred');
    const distance = pose.position.distanceTo(pose.target);
    close(pose.maxDistance, distance * 1.12);
    assert.ok(pose.minDistance <= distance && pose.minDistance > Math.sqrt(radiusSquared) + .69, 'all orbit directions remain outside the model at minimum zoom');
    views.push({ viewport: [width, height], fov, distance, minDistance: pose.minDistance, maxDistance: pose.maxDistance,
      widthPercent: (projected.max.x - projected.min.x) * 50, heightPercent: (projected.max.y - projected.min.y) * 50,
      vertexRadius: Math.sqrt(radiusSquared), target: pose.target.toArray() });
  }
  return { vertices: vertices.length / 3, views };
});

check('framing preserves authored parentage, transforms, cache isolation and reference camera direction', () => {
  const first = framing.pose(1.5, 35), position = first.position.clone(), target = first.target.clone();
  const direction = first.position.clone().sub(first.target).normalize();
  close(direction.distanceTo(new THREE.Vector3(8, 3.25, 12.5).normalize()), 0);
  first.position.set(999, 999, 999); first.target.set(999, 999, 999);
  framing.getState().silhouette.minX = -900;
  const second = framing.pose(1.5, 35);
  close(second.position.distanceTo(position), 0); close(second.target.distanceTo(target), 0);
  assert.ok(framing.getState().silhouette.minX > -1);
  for (const [node, transform] of sourceTransforms) {
    assert.deepEqual(node.position.toArray(), transform.position);
    assert.deepEqual(node.quaternion.toArray(), transform.quaternion);
    assert.deepEqual(node.scale.toArray(), transform.scale);
    assert.equal(node.parent, transform.parent);
  }
  for (const [aspect, fov] of [[0, 35], [-1, 35], [Infinity, 35], [NaN, 35], [1, 0], [1, 180], [1, Infinity]]) {
    assert.throws(() => framing.pose(aspect, fov));
  }
  return { preservedNodes: sourceTransforms.size, sourceCameraBlender: [8, -12.3, 5.2], sourceTargetBlender: [0, .2, 1.95] };
});

const files = ['src/about-framing.js', 'src/about-atelier.js', 'scripts/check-about-framing.mjs', `public${modelUrl}`];
const report = { checkedAt: new Date().toISOString(), model: modelUrl, runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Real exported GLB vertices and production framing. Complete projection and conservative all-direction minimum orbit radius. No GPU performance or visual rendering claim.',
  sourceSha256: Object.fromEntries(files.map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')])),
  passed: results.filter(result => result.status === 'passed').length, failed: results.filter(result => result.status === 'failed').length, results };
if (process.argv.includes('--write-report')) {
  const directory = new URL('../docs/validation/', import.meta.url);
  mkdirSync(directory, { recursive: true });
  writeFileSync(new URL('about-framing-v3.json', directory), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report, null, 2));
if (report.failed) process.exitCode = 1;
