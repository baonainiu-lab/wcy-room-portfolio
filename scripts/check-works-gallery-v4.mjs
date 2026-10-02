import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { GALLERY_OFFSET } from '../src/gallery-transition-path.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

const file = path => new URL(`../${path}`, import.meta.url), modelUrl = '/models/works-gallery-v4-compressed.glb';
if (!existsSync(file(`public${modelUrl}`))) {
  console.log(JSON.stringify({ status: 'awaiting-v4-export', modelUrl, checksRun: 0 })); process.exit(2);
}
const hash = value => createHash('sha256').update(value).digest('hex');
const changedOwners = ['gallery.architecture', 'gallery.architecture.glazing', 'gallery.architecture.portal'].sort();
const results = [], gallerySource = readFileSync(file('src/works-gallery.js'), 'utf8');
const current = load(modelUrl), previous = load('/models/works-gallery-v3-compressed.glb');
const close = (a, b, label, epsilon = 1e-5) => assert.ok(Math.abs(a - b) <= epsilon, `${label}: ${a} != ${b}`);
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.message }); }
}
function owner(node) {
  for (let current = node; current; current = current.parent) if (current.userData.asset_id) return current.userData.asset_id;
  return null;
}
function bounds(node) { node.updateWorldMatrix(true, true); const box = new THREE.Box3().setFromObject(node, true); assert.ok(!box.isEmpty()); return box; }
const boxJson = box => ({ min: box.min.toArray(), max: box.max.toArray() });
function load(url) {
  const geometry = readRoomGeometry(url), bytes = readFileSync(file(`public${url}`)), binary = bytes.subarray(20 + bytes.readUInt32LE(12) + 8);
  const { data, nodes } = geometry, primitives = [];
  function attribute(index) {
    const accessor = data.accessors[index], view = data.bufferViews[accessor.bufferView];
    assert.ok(!accessor.sparse && !view.byteStride, 'packed nonsparse geometry accessor');
    const Type = { 5120: Int8Array, 5121: Uint8Array, 5122: Int16Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array }[accessor.componentType];
    const width = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[accessor.type]; assert.ok(Type && width);
    return new THREE.BufferAttribute(new Type(binary.buffer, binary.byteOffset + (view.byteOffset || 0) + (accessor.byteOffset || 0), accessor.count * width), width, Boolean(accessor.normalized));
  }
  data.nodes.forEach((spec, index) => {
    if (spec.mesh === undefined) return;
    const meshes = nodes[index].children.filter(child => child.isMesh);
    data.meshes[spec.mesh].primitives.forEach((primitive, part) => {
      const mesh = meshes[part], material = data.materials[primitive.material];
      if (primitive.attributes.NORMAL !== undefined) mesh.geometry.setAttribute('normal', attribute(primitive.attributes.NORMAL));
      // Match GLTFLoader's original sidedness for CPU ray intersections.
      mesh.material.side = material.doubleSided ? THREE.DoubleSide : THREE.FrontSide;
      primitives.push({ mesh, primitive, material, owner: owner(mesh) });
    });
  });
  return { ...geometry, bytes, binary, primitives, sha256: hash(bytes) };
}
function geometrySignatures(model) {
  const triangles = new Map([...model.components.keys()].map(id => [id, []]));
  for (const { mesh, owner: id } of model.primitives) {
    assert.ok(triangles.has(id), `primitive has a known logical owner: ${mesh.name}`);
    const geometry = mesh.geometry, positions = geometry.attributes.position;
    const keys = Array.from({ length: positions.count }, (_, i) => new THREE.Vector3().fromBufferAttribute(positions, i)
      .applyMatrix4(mesh.matrixWorld).toArray().map(value => Math.round(value * 1e5)).join(','));
    const indices = geometry.index?.array ?? Array.from({ length: positions.count }, (_, i) => i), list = triangles.get(id);
    for (let i = 0; i < indices.length; i += 3) {
      const points = [keys[indices[i]], keys[indices[i + 1]], keys[indices[i + 2]]];
      const start = points.indexOf([...points].sort()[0]);
      list.push([points[start], points[(start + 1) % 3], points[(start + 2) % 3]].join('|'));
    }
  }
  return Object.fromEntries([...triangles].map(([id, list]) => [id, { triangles: list.length, sha256: hash(list.sort().join('\n')) }]));
}
function glassTopology(mesh) {
  const positions = mesh.geometry.attributes.position, indices = mesh.geometry.index.array;
  const points = Array.from({ length: positions.count }, (_, i) => new THREE.Vector3().fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld));
  const welded = new Map(), weldedPoints = [], ids = points.map(point => {
    const key = point.toArray().map(value => Math.round(value * 1e6)).join(',');
    if (!welded.has(key)) { welded.set(key, weldedPoints.length); weldedPoints.push(point); }
    return welded.get(key);
  });
  const parent = weldedPoints.map((_, i) => i), find = i => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  const join = (a, b) => { parent[find(a)] = find(b); };
  const triangles = [], edges = new Map(); let degenerates = 0, minimumArea = Infinity;
  for (let i = 0; i < indices.length; i += 3) {
    const triangle = [ids[indices[i]], ids[indices[i + 1]], ids[indices[i + 2]]]; triangles.push(triangle);
    const [a, b, c] = triangle.map(id => weldedPoints[id]);
    const area = b.clone().sub(a).cross(c.clone().sub(a)).length() * .5;
    minimumArea = Math.min(minimumArea, area); if (area < 1e-12) degenerates++;
    join(triangle[0], triangle[1]); join(triangle[0], triangle[2]);
    for (let edge = 0; edge < 3; edge++) {
      const a = triangle[edge], b = triangle[(edge + 1) % 3], key = a < b ? `${a},${b}` : `${b},${a}`;
      const item = edges.get(key) ?? { count: 0, orientation: 0 }; item.count++; item.orientation += a < b ? 1 : -1; edges.set(key, item);
    }
  }
  const components = new Map();
  for (const triangle of triangles) {
    const root = find(triangle[0]); if (!components.has(root)) components.set(root, []); components.get(root).push(triangle);
  }
  const shells = [...components.values()].map(parts => {
    const box = new THREE.Box3().setFromPoints(parts.flat().map(i => weldedPoints[i])), center = box.getCenter(new THREE.Vector3());
    let signedVolume = 0, area = 0;
    for (const triangle of parts) {
      const [a, b, c] = triangle.map(id => weldedPoints[id].clone().sub(center));
      signedVolume += a.dot(b.clone().cross(c)) / 6;
      area += b.clone().sub(a).cross(c.clone().sub(a)).length() * .5;
    }
    return { triangles: parts.length, ...boxJson(box), signedVolume, surfaceArea: area, effectiveThickness: 2 * Math.abs(signedVolume) / area };
  });
  return { triangles: triangles.length, weldedVertices: weldedPoints.length, degenerates, minimumArea,
    boundaryEdges: [...edges.values()].filter(edge => edge.count === 1).length,
    nonManifoldEdges: [...edges.values()].filter(edge => edge.count !== 2).length,
    inconsistentlyOrientedEdges: [...edges.values()].filter(edge => edge.count === 2 && edge.orientation !== 0).length, shells };
}
function ktxDimensions(bytes) {
  assert.deepEqual([...bytes.subarray(0, 12)], [171, 75, 84, 88, 32, 50, 48, 187, 13, 10, 26, 10]);
  return [bytes.readUInt32LE(20), bytes.readUInt32LE(24)];
}

await check('77 IDs, six work stations and their hierarchy remain identical to V3', () => {
  const ids = current.data.nodes.flatMap(node => node.extras?.asset_id ? [node.extras.asset_id] : []);
  assert.equal(ids.length, 77); assert.equal(new Set(ids).size, 77);
  assert.deepEqual(ids.sort(), [...previous.components.keys()].sort());
  const stations = ids.filter(id => /^gallery\.work\.\d{2}$/.test(id)); assert.equal(stations.length, 6);
  const hierarchy = model => Object.fromEntries([...model.components].map(([id, node]) => [id, owner(node.parent)]));
  assert.deepEqual(hierarchy(current), hierarchy(previous));
  assert.deepEqual(ids.filter(id => id.startsWith('gallery.environment.')), ['gallery.environment.terrace']);
  return { assetCount: ids.length, stations, parentHierarchyPreserved: true };
});
await check('only the three architectural owners change world-space triangle geometry', () => {
  const before = geometrySignatures(previous), after = geometrySignatures(current);
  const changed = Object.keys(after).filter(id => before[id].sha256 !== after[id].sha256).sort();
  assert.deepEqual(changed, changedOwners);
  return { comparisonQuantizationMetres: .00001, changedOwners: changed, preservedOwners: Object.keys(after).length - changed.length,
    beforeTriangles: Object.values(before).reduce((sum, item) => sum + item.triangles, 0),
    afterTriangles: Object.values(after).reduce((sum, item) => sum + item.triangles, 0),
    ownerSignatures: Object.fromEntries(Object.keys(after).map(id => [id, { before: before[id], after: after[id] }])) };
});
await check('architectural glazing has its own transparent material and exported finite unit normals', () => {
  const arch = current.data.materials.filter(material => material.name === 'GALLERY_ARCH_GLASS');
  const ordinary = current.data.materials.filter(material => material.name === 'GALLERY_CLEAR');
  assert.equal(arch.length, 1); assert.equal(ordinary.length, 1); assert.notEqual(arch[0], ordinary[0]);
  assert.equal(arch[0].alphaMode, 'BLEND');
  const primitives = current.primitives.filter(item => item.material.name === 'GALLERY_ARCH_GLASS'); assert.ok(primitives.length);
  let normalCount = 0, minimumLength = Infinity, maximumLength = 0;
  for (const { mesh, primitive } of primitives) {
    assert.ok(primitive.attributes.NORMAL !== undefined, `${mesh.name} exports NORMAL`);
    const normal = mesh.geometry.attributes.normal; assert.equal(normal.count, mesh.geometry.attributes.position.count);
    for (let i = 0; i < normal.count; i++) {
      const length = new THREE.Vector3().fromBufferAttribute(normal, i).length(); assert.ok(Number.isFinite(length));
      close(length, 1, `${mesh.name} normal length`, 2e-3); minimumLength = Math.min(minimumLength, length); maximumLength = Math.max(maximumLength, length); normalCount++;
    }
  }
  return { material: arch[0], primitiveCount: primitives.length, owners: [...new Set(primitives.map(item => item.owner))], normalCount, minimumLength, maximumLength };
});
await check('architectural glass consists of closed thick outward shells with no degenerate faces', () => {
  const primitives = current.primitives.filter(item => item.material.name === 'GALLERY_ARCH_GLASS'), reports = [];
  assert.ok(primitives.length);
  for (const { mesh, owner: id } of primitives) {
    const topology = glassTopology(mesh);
    assert.equal(topology.degenerates, 0, `${mesh.name} degenerate triangles`);
    assert.equal(topology.boundaryEdges, 0, `${mesh.name} open boundary edges`);
    assert.equal(topology.nonManifoldEdges, 0, `${mesh.name} non-manifold edges`);
    assert.equal(topology.inconsistentlyOrientedEdges, 0, `${mesh.name} inconsistent winding`);
    for (const shell of topology.shells) {
      assert.ok(shell.signedVolume > 1e-7, `${mesh.name} outward positive volume`);
      assert.ok(shell.effectiveThickness > (id === 'gallery.architecture.glazing' ? .02 : .01), `${mesh.name} solid glass thickness`);
    }
    reports.push({ owner: id, mesh: mesh.name, ...topology });
  }
  assert.ok(reports.filter(item => item.owner === 'gallery.architecture.glazing').reduce((sum, item) => sum + item.shells.length, 0) >= 12,
    'rear and canopy glass retain independently closed panels');
  return { weldToleranceMetres: .000001, meshes: reports };
});
await check('rebuilt architecture stays above the native ground and the portal remains in its left-side berth', () => {
  const nativeFloorY = Number(gallerySource.match(/floor\.position\.y = ([-.\d]+)/)?.[1]);
  const architecture = bounds(current.components.get('gallery.architecture')), portal = bounds(current.components.get('gallery.architecture.portal'));
  assert.ok(architecture.min.y >= nativeFloorY, `architecture extends beneath ground: minY ${architecture.min.y}, ground ${nativeFloorY}`);
  assert.ok(portal.min.y >= nativeFloorY, `portal extends beneath ground: minY ${portal.min.y}, ground ${nativeFloorY}`);
  assert.ok(portal.max.x < -6 && portal.min.x > -10, `portal is outside its left-side berth: x[${portal.min.x}, ${portal.max.x}]`);
  return { nativeFloorY, architecture: boxJson(architecture), portal: boxJson(portal) };
});
await check('return portal retains visible hittable surfaces and all six stations remain nonempty', () => {
  const portal = current.components.get('gallery.architecture.portal'); assert.ok(portal);
  const box = bounds(portal), size = box.getSize(new THREE.Vector3()), target = box.getCenter(new THREE.Vector3());
  assert.ok(size.x > 1.5 && size.y > 4 && size.z > 3, 'return portal retains a substantial 3D shell');
  // Aim at actual frame surfaces, not the empty center of the doorway opening.
  const from = new THREE.Vector3(25, 21, 42), targets = [];
  portal.traverse(mesh => {
    if (!mesh.isMesh) return;
    const positions = mesh.geometry.attributes.position, indices = mesh.geometry.index.array;
    for (let i = 0; i < indices.length; i += 3) {
      const points = [0, 1, 2].map(j => new THREE.Vector3().fromBufferAttribute(positions, indices[i + j]).applyMatrix4(mesh.matrixWorld));
      const area = points[1].clone().sub(points[0]).cross(points[2].clone().sub(points[0])).length() * .5;
      if (area > .02) targets.push({ area, point: points[0].clone().add(points[1]).add(points[2]).divideScalar(3) });
    }
  });
  targets.sort((a, b) => b.area - a.area);
  const opaqueMeshes = current.primitives.filter(item => item.material.alphaMode !== 'BLEND' && !item.owner?.startsWith('gallery.environment.')).map(item => item.mesh);
  let visibleHit = null;
  for (const candidate of targets.slice(0, 128)) {
    const hits = new THREE.Raycaster(from, candidate.point.clone().sub(from).normalize()).intersectObjects(opaqueMeshes, false);
    if (owner(hits[0]?.object) === 'gallery.architecture.portal') { visibleHit = { point: hits[0].point.toArray(), distance: hits[0].distance, candidate: candidate.point.toArray() }; break; }
  }
  assert.ok(visibleHit, 'an actual portal face is the first visible opaque surface hit from the default viewing hemisphere');
  const stations = Object.fromEntries([...current.components].filter(([id]) => /^gallery\.work\.\d{2}$/.test(id)).map(([id, node]) => [id, boxJson(bounds(node))]));
  return { portalBounds: boxJson(box), testedSurfaceCandidates: Math.min(targets.length, 128), visibleHit, stations };
});
await check('atlas precision remains 4096/4096/4096/1024 in embedded and external day/night KTX2 images', () => {
  const expected = [4096, 4096, 4096, 1024]; assert.equal(current.data.images.length, 4);
  const embedded = current.data.images.map(image => {
    assert.equal(image.mimeType, 'image/ktx2'); const slot = Number(image.name.match(/_(\d+)$/)?.[1]); assert.ok(Number.isInteger(slot));
    const view = current.data.bufferViews[image.bufferView], bytes = current.binary.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength);
    const dimensions = ktxDimensions(bytes); assert.deepEqual(dimensions, [expected[slot], expected[slot]]);
    return { slot, dimensions, sha256: hash(bytes) };
  }).sort((a, b) => a.slot - b.slot);
  assert.deepEqual(embedded.map(image => image.slot), [0, 1, 2, 3]);
  const external = [];
  for (const theme of ['day', 'night']) for (let slot = 0; slot < 4; slot++) {
    const path = `public/textures/works-gallery-v4/${theme}-${slot}.ktx2`, bytes = readFileSync(file(path)), dimensions = ktxDimensions(bytes);
    assert.deepEqual(dimensions, [expected[slot], expected[slot]]); external.push({ path, dimensions, sha256: hash(bytes) });
  }
  return { embedded, external };
});
await check('thin terrace dimensions and shared-stage clearance remain unchanged', () => {
  const now = bounds(current.components.get('gallery.environment.terrace')), before = bounds(previous.components.get('gallery.environment.terrace'));
  for (const axis of ['x', 'y', 'z']) { close(now.min[axis], before.min[axis], `terrace minimum ${axis}`); close(now.max[axis], before.max[axis], `terrace maximum ${axis}`); }
  const room = readRoomGeometry();
  room.data.nodes.forEach((node, index) => node.children?.forEach(child => room.nodes[index].add(room.nodes[child])));
  room.data.scenes[room.data.scene || 0].nodes.forEach(index => room.room.add(room.nodes[index])); room.room.updateMatrixWorld(true);
  const exterior = new THREE.Group(); for (const id of ['environment.orbital_dock', 'environment.warm_gallery']) exterior.attach(room.components.get(id));
  const exteriorBounds = bounds(exterior), groundY = exteriorBounds.min.y - .025, stageTerrace = now.clone().translate(GALLERY_OFFSET);
  close(stageTerrace.min.y - groundY, .025, 'shared ground clearance'); assert.ok(stageTerrace.min.x - exteriorBounds.max.x > 3.6);
  const nativeFloorY = Number(gallerySource.match(/floor\.position\.y = ([-.\d]+)/)?.[1]); close(now.min.y - nativeFloorY, .025, 'native ground clearance');
  return { terrace: boxJson(now), stageOffset: GALLERY_OFFSET.toArray(), nativeFloorY, roomGroundY: groundY,
    verticalClearance: stageTerrace.min.y - groundY, horizontalClearance: stageTerrace.min.x - exteriorBounds.max.x };
});

const files = ['src/works-gallery.js', 'src/gallery-glass.js', 'src/gallery-transition.js', 'src/gallery-transition-path.js', 'src/gallery-floor-finish.js'];
const activeModelUrl = gallerySource.match(/loadAsync\('([^']+\.glb)'/)?.[1];
const report = { revision: 'gallery-4', checkedAt: new Date().toISOString(), runtime: process.version,
  methodology: 'Actual V3 and V4 GLB JSON/BIN geometry, Three.js transforms and CPU rays. Per-owner world triangle signatures ignore UV/normal/material changes but preserve winding. Glass topology welds coincident export seams for closed-shell, signed-volume and thickness checks. No GPU or browser, and no fixed total triangle count assertion.',
  model: { url: modelUrl, sha256: current.sha256, bytes: current.bytes.length, primitives: current.primitives.length },
  baseline: { url: previous.modelUrl, sha256: previous.sha256 }, activeModelUrl, activeEntryUsesV4: activeModelUrl === modelUrl,
  sourceSha256: Object.fromEntries(files.map(path => [path, hash(readFileSync(file(path)))])),
  checks: results.length, passed: results.filter(item => item.status === 'passed').length, failed: results.filter(item => item.status === 'failed').length, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(file('docs/validation/'), { recursive: true }); writeFileSync(file('docs/validation/works-gallery-v4.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, model: report.model,
  activeEntryUsesV4: report.activeEntryUsesV4, failures: results.filter(item => item.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
