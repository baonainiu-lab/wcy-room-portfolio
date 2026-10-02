import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { GALLERY_OFFSET } from '../src/gallery-transition-path.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

const file = path => new URL(`../${path}`, import.meta.url);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const gallerySource = readFileSync(file('src/works-gallery.js'), 'utf8');
const modelUrl = gallerySource.match(/loadAsync\('([^']+\.glb)'/)?.[1];
assert.ok(modelUrl, 'production gallery URL is readable');
const modelBytes = readFileSync(file(`public${modelUrl}`));
const geometry = readRoomGeometry(modelUrl);
const { data, room: model, components } = geometry;
const prior = readRoomGeometry('/models/works-gallery-v2-compressed.glb');
const rawIds = data.nodes.flatMap(node => node.extras?.asset_id ? [node.extras.asset_id] : []);
const expectedRemoved = ['gallery.environment.city', 'gallery.environment.foundation',
  ...Array.from({ length: 8 }, (_, index) => `gallery.environment.plant.${String(index).padStart(2, '0')}`)].sort();
const results = [];
const close = (a, b, label, epsilon = 1e-5) => assert.ok(Math.abs(a - b) <= epsilon, `${label}: ${a} != ${b}`);
const box = node => {
  node.updateWorldMatrix(true, true);
  const bounds = new THREE.Box3().setFromObject(node, true);
  assert.ok(!bounds.isEmpty(), `${node.userData.asset_id || node.name} has actual geometry`);
  return bounds;
};
const serializeBox = bounds => ({ min: bounds.min.toArray(), max: bounds.max.toArray() });
const meshCount = node => { let count = 0; node.traverse(child => { if (child.isMesh) count++; }); return count; };
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.message }); }
}
function ktxDimensions(bytes) {
  assert.deepEqual([...bytes.subarray(0, 12)], [171, 75, 84, 88, 32, 50, 48, 187, 13, 10, 26, 10], 'actual KTX2 signature');
  return [bytes.readUInt32LE(20), bytes.readUInt32LE(24)];
}

await check('production entry selects clean V3 model, 77 IDs and four day/night atlas slots', () => {
  assert.equal(modelUrl, '/models/works-gallery-v3-compressed.glb');
  assert.match(gallerySource, /components\.size !== 77/);
  assert.match(gallerySource, /revision: 'gallery-3'/);
  assert.match(gallerySource, /slots: \[0, 1, 2, 3\]/);
  assert.match(gallerySource, /directory: '\/textures\/works-gallery-v3'/);
  assert.doesNotMatch(gallerySource, /loadAsync\('\/models\/works-gallery-v[12]-/);
  return { modelUrl, lightingRevision: 'gallery-3', atlasSlots: [0, 1, 2, 3] };
});
await check('actual GLB contains 77 unique IDs, 80 primitives and 560890 triangles', () => {
  assert.equal(rawIds.length, 77); assert.equal(new Set(rawIds).size, 77); assert.equal(components.size, 77);
  let triangles = 0, primitives = 0;
  model.traverse(node => {
    if (!node.isMesh) return;
    primitives++; triangles += (node.geometry.index?.count ?? node.geometry.attributes.position.count) / 3;
  });
  assert.equal(primitives, 80); assert.equal(triangles, 560890);
  return { uniqueAssetIds: components.size, meshDefinitions: data.meshes.length, primitives, triangles, bytes: modelBytes.length };
});
await check('city, foundation and all eight outer plants are physically deleted from the GLB', () => {
  const removed = [...prior.components.keys()].filter(id => !components.has(id)).sort();
  const added = [...components.keys()].filter(id => !prior.components.has(id)).sort();
  assert.deepEqual(removed, expectedRemoved); assert.deepEqual(added, []);
  assert.deepEqual([...components.keys()].filter(id => id.startsWith('gallery.environment.')).sort(), ['gallery.environment.terrace']);
  for (const id of expectedRemoved) assert.ok(!rawIds.includes(id));
  // Runtime visibility changes cannot satisfy this test: it compares the on-disk node IDs.
  return { comparedTo: '/models/works-gallery-v2-compressed.glb', removedAssetIds: removed, addedAssetIds: added,
    retainedEnvironmentIds: ['gallery.environment.terrace'], physicalDeletion: true };
});
await check('six stations and the complete return portal retain real geometry', () => {
  const stations = [...components.keys()].filter(id => /^gallery\.work\.\d{2}$/.test(id)).sort();
  assert.deepEqual(stations, Array.from({ length: 6 }, (_, index) => `gallery.work.${String(index + 1).padStart(2, '0')}`));
  const stationBounds = Object.fromEntries(stations.map(id => [id, { ...serializeBox(box(components.get(id))), primitives: meshCount(components.get(id)) }]));
  const portal = components.get('gallery.architecture.portal'); assert.ok(portal);
  const portalBounds = box(portal), size = portalBounds.getSize(new THREE.Vector3());
  assert.ok(size.x > 2 && size.y > 4 && size.z > 4, 'return doorway retains its full 3D frame');
  assert.match(gallerySource, /returnPortalId = 'gallery\.architecture\.portal'/);
  assert.match(gallerySource, /returnToRoom: true/);
  assert.match(gallerySource, /kind: 'return-room'/);
  return { stations: stationBounds, returnPortal: { assetId: portal.userData.asset_id, ...serializeBox(portalBounds), primitives: meshCount(portal) } };
});
await check('four embedded atlas images and eight external lighting textures use current dimensions', () => {
  const binary = modelBytes.subarray(20 + modelBytes.readUInt32LE(12) + 8);
  const expected = [4096, 4096, 4096, 1024];
  assert.equal(data.images.length, 4);
  const embedded = data.images.map(image => {
    assert.equal(image.mimeType, 'image/ktx2');
    const slot = Number(image.name.match(/_(\d+)$/)?.[1]); assert.ok(Number.isInteger(slot));
    const view = data.bufferViews[image.bufferView];
    const imageBytes = binary.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength);
    const dimensions = ktxDimensions(imageBytes); assert.deepEqual(dimensions, [expected[slot], expected[slot]]);
    return { slot, dimensions, bytes: imageBytes.length, sha256: hash(imageBytes) };
  }).sort((a, b) => a.slot - b.slot);
  assert.deepEqual(embedded.map(image => image.slot), [0, 1, 2, 3]);
  const materialSlots = data.materials.flatMap(material => {
    const match = material.name.match(/^GALLERY_LIGHTMAP_(\d+)$/); return match ? [Number(match[1])] : [];
  }).sort();
  assert.deepEqual(materialSlots, [0, 1, 2, 3]);
  const external = [];
  for (const theme of ['day', 'night']) for (let slot = 0; slot < 4; slot++) {
    const path = `public/textures/works-gallery-v3/${theme}-${slot}.ktx2`;
    const bytes = readFileSync(file(path)), dimensions = ktxDimensions(bytes);
    assert.deepEqual(dimensions, [expected[slot], expected[slot]]);
    external.push({ path, dimensions, bytes: bytes.length, sha256: hash(bytes) });
  }
  return { embedded, external, materialSlots };
});
await check('thin terrace clears native and shared ground and stays apart from the room exterior', () => {
  assert.deepEqual(GALLERY_OFFSET.toArray(), [34, -.185, 1.5]);
  const terrace = box(components.get('gallery.environment.terrace'));
  const nativeFloorY = Number(gallerySource.match(/floor\.position\.y = ([-.\d]+)/)?.[1]);
  close(nativeFloorY, -.88, 'native gallery ground'); close(terrace.min.y, -.855, 'thin terrace underside');
  close(terrace.min.y - nativeFloorY, .025, 'native terrace ground clearance');
  const actualRoom = readRoomGeometry();
  // Reconstruct original parent links before reproducing main.js's exterior extraction.
  actualRoom.data.nodes.forEach((node, index) => node.children?.forEach(child => actualRoom.nodes[index].add(actualRoom.nodes[child])));
  actualRoom.data.scenes[actualRoom.data.scene || 0].nodes.forEach(index => actualRoom.room.add(actualRoom.nodes[index]));
  actualRoom.room.updateMatrixWorld(true);
  const exterior = new THREE.Group();
  for (const id of ['environment.orbital_dock', 'environment.warm_gallery']) {
    const root = actualRoom.components.get(id); assert.ok(root); exterior.attach(root);
  }
  const exteriorBounds = box(exterior), roomGroundY = exteriorBounds.min.y - .025;
  const stageTerrace = terrace.clone().translate(GALLERY_OFFSET);
  const groundClearance = stageTerrace.min.y - roomGroundY;
  const horizontalClearance = stageTerrace.min.x - exteriorBounds.max.x;
  close(roomGroundY, -1.065, 'room ground derived from real exterior');
  close(groundClearance, .025, 'shared terrace ground clearance');
  assert.ok(horizontalClearance > 3.6, `actual exterior/terrace gap must exceed 3.6 units; got ${horizontalClearance}`);
  assert.ok(groundClearance > 0);
  return { nativeFloorY, terrace: serializeBox(terrace), stageOffset: GALLERY_OFFSET.toArray(),
    stageTerrace: serializeBox(stageTerrace), roomModelUrl: actualRoom.modelUrl, roomExterior: serializeBox(exteriorBounds),
    roomGroundY, groundClearance, horizontalClearance };
});

const sources = ['src/works-gallery.js', 'src/gallery-transition.js', 'src/gallery-transition-path.js', 'src/main.js'];
const report = { revision: 'clean-gallery-3', checkedAt: new Date().toISOString(), runtime: process.version,
  methodology: 'Read production entry and actual GLB JSON/BIN geometry with real Three.js matrix transforms. Validate physical deletion against the prior V2 GLB, primitive/index counts, real bounding boxes, and embedded/external KTX2 headers. No browser, GPU render or performance claims.',
  model: { url: modelUrl, sha256: hash(modelBytes), bytes: modelBytes.length },
  sourceSha256: Object.fromEntries(sources.map(path => [path, hash(readFileSync(file(path)))])),
  assetIds: rawIds.sort(), checks: results.length, passed: results.filter(result => result.status === 'passed').length,
  failed: results.filter(result => result.status === 'failed').length, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(file('docs/validation/'), { recursive: true });
  writeFileSync(file('docs/validation/works-gallery-v3-clean.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, model: report.model,
  failures: results.filter(result => result.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
