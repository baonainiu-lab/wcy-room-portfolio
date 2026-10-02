import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { parseModelForCPU, introFixture } from './lib/intro-controller-fixture.mjs';
import { createRoomEntryAttachments } from '../src/room-entry-attachments.js';
import { ROOM_ENTRY_GROUPS } from '../src/room-entry.js';

const file = name => new URL(`../${name}`, import.meta.url);
const digest = name => createHash('sha256').update(readFileSync(file(name))).digest('hex');
const paths = ['src/room-entry.js', 'src/cube-intro.js', 'public/models/orbital-atelier-v16.glb', 'public/models/welcome-terminal-v1.glb'];
const sourceSha256 = Object.fromEntries(paths.map(name => [name, digest(name)]));
const [roomGltf, welcomeGltf] = await Promise.all([
  parseModelForCPU(paths[2]), parseModelForCPU(paths[3]),
]);
createRoomEntryAttachments({ THREE, room: roomGltf.scene });
const original = roomGltf.scene.clone(true); original.updateMatrixWorld(true);
const ids = new Set(ROOM_ENTRY_GROUPS.flatMap(([, group]) => group));
const originals = new Map(), supportMeshes = [];
const supportOwners = new Set(['architecture.platform', 'furniture.desk', 'furniture.coffee_table', 'furniture.rug']);
function ownerOf(node) { for (let p = node; p; p = p.parent) if (ids.has(p.userData.asset_id) || supportOwners.has(p.userData.asset_id)) return p.userData.asset_id; return null; }
original.traverse(node => {
  if (ids.has(node.userData.asset_id)) originals.set(node.userData.asset_id, new THREE.Box3().setFromObject(node, true));
  if (!node.isMesh) return;
  const owner = ownerOf(node);
  if (supportOwners.has(owner) || /room_static/.test(node.name)) {
    node.material = [].concat(node.material).map(material => { const copy = material.clone(); copy.side = THREE.DoubleSide; return copy; });
    if (node.material.length === 1) node.material = node.material[0];
    node.userData.auditOwner = owner; supportMeshes.push(node);
  }
});
const fixture = introFixture({ roomGltf, welcomeGltf });
const records = new Map();
for (const [id, node] of fixture.roots) {
  if (!ids.has(id)) continue;
  const meshes = []; node.traverse(mesh => { if (mesh.isMesh) meshes.push(mesh); });
  records.set(id, { node, meshes, box: originals.get(id), originalScale: fixture.originals.get(node).scale,
    worstBelowOriginalMinimum: null, worstReferenceSurfacePenetration: null, worstFootprintEscape: null });
}
const raycaster = new THREE.Raycaster(), down = new THREE.Vector3(0, -1, 0), point = new THREE.Vector3();
const inverseRoom = new THREE.Matrix4(), matrix = new THREE.Matrix4();
function supportAt(p, maxY, id) {
  raycaster.set(new THREE.Vector3(p.x, maxY + .06, p.z), down); raycaster.far = 20;
  return raycaster.intersectObjects(supportMeshes.filter(mesh => mesh.userData.auditOwner !== id), false)
    .find(hit => hit.point.y > maxY - .45);
}
const round = value => Number(value.toFixed(7));
fixture.ready().progress(1); const timeline = fixture.enter();
try {
  for (let step = 0; step <= Math.ceil(timeline.duration() * 24); step++) {
    const time = Math.min(step / 24, timeline.duration()); timeline.time(time, false); fixture.intro.update(); fixture.scene.updateMatrixWorld(true);
    inverseRoom.copy(fixture.room.matrixWorld).invert();
    for (const [id, record] of records) {
      const scale = Math.max(...record.node.scale.toArray().map((value, axis) => value / record.originalScale.getComponent(axis)));
      if (!fixture.room.visible || scale < .08) continue;
      let minimum = Infinity, minPoint, escape = 0, escapedPoint;
      for (const mesh of record.meshes) {
        matrix.multiplyMatrices(inverseRoom, mesh.matrixWorld);
        const positions = mesh.geometry.attributes.position;
        for (let index = 0; index < positions.count; index++) {
          point.fromBufferAttribute(positions, index).applyMatrix4(matrix);
          if (point.y < minimum) { minimum = point.y; minPoint = point.clone(); }
          const distance = Math.max(record.box.min.x - point.x, point.x - record.box.max.x, record.box.min.z - point.z, point.z - record.box.max.z, 0);
          if (distance > escape) { escape = distance; escapedPoint = point.clone(); }
        }
      }
      const depth = record.box.min.y - minimum;
      if (depth > .001 && depth > (record.worstBelowOriginalMinimum?.depth ?? 0)) {
        record.worstBelowOriginalMinimum = { time: round(time), depth: round(depth), point: minPoint.toArray().map(round), baselineMinimumY: record.box.min.y, scale: round(scale) };
      }
      if (depth > .001) {
        const hit = supportAt(minPoint, record.box.min.y, id);
        if (hit && hit.point.y - minimum > .003 && hit.point.y - minimum > (record.worstReferenceSurfacePenetration?.depth ?? 0)) {
          record.worstReferenceSurfacePenetration = { time: round(time), depth: round(hit.point.y - minimum), vertex: minPoint.toArray().map(round),
            supportingTriangleHit: hit.point.toArray().map(round), supportMesh: hit.object.name, supportFace: hit.faceIndex, supportOwner: hit.object.userData.auditOwner,
            originalLowestVertexGap: round(record.box.min.y - hit.point.y), scale: round(scale) };
        }
      }
      if (escape > .001 && escape > (record.worstFootprintEscape?.distance ?? 0)) record.worstFootprintEscape = {
        time: round(time), distance: round(escape), vertex: escapedPoint.toArray().map(round), scale: round(scale) };
    }
  }
} finally { fixture.cleanup(); }
const props = [...records].map(([id, record]) => ({ id, baselineBounds: { min: record.box.min.toArray(), max: record.box.max.toArray() },
  belowOriginalMinimum: record.worstBelowOriginalMinimum, referenceSurfacePenetration: record.worstReferenceSurfacePenetration, footprintEscape: record.worstFootprintEscape }));
const report = { checkedAt: new Date().toISOString(), sourceSha256, sampleRateHz: 24, durationSeconds: timeline.duration(),
  method: 'Actual GLTFLoader geometry and unchanged production GSAP controller. Every prop vertex is evaluated in original room coordinates, removing only the external uniform room reveal. Downward ray/triangle hits on unchanged reference floor, desk, coffee table, rug or static architecture confirm selected support crossings. Whole-scene AABB overlap is not treated as collision.',
  limitations: ['Reference support is in its final pose: a delayed or still-growing support is reported separately by choreography checks.', 'Footprint escape alone is a trajectory risk, not a triangle collision verdict.', 'This low-vertex witness scan is not exhaustive triangle/triangle intersection testing.'],
  propCount: props.length, supportCrossingCount: props.filter(p => p.referenceSurfacePenetration).length, footprintEscapeCount: props.filter(p => p.footprintEscape).length, props };
if (process.argv.includes('--baseline')) {
  try { report.handoffAndExterior = JSON.parse(readFileSync('/tmp/entry-handoff-triangle-audit.json', 'utf8')); } catch {}
  writeFileSync(file('docs/validation/entry-collision-baseline.json'), JSON.stringify(report, null, 2) + '\n');
} else if (process.argv.includes('--write-report')) writeFileSync(file('docs/validation/entry-collision-audit.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ supportCrossingCount: report.supportCrossingCount, footprintEscapeCount: report.footprintEscapeCount,
  worst: props.filter(p => p.referenceSurfacePenetration).sort((a, b) => b.referenceSurfacePenetration.depth - a.referenceSurfacePenetration.depth).slice(0, 14),
}, null, 2));
