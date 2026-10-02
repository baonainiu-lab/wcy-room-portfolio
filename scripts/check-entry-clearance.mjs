import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { parseModelForCPU, introFixture } from './lib/intro-controller-fixture.mjs';
import { createRoomEntryAttachments } from '../src/room-entry-attachments.js';
import { ROOM_ENTRY_GROUPS } from '../src/room-entry.js';

const roomPath = process.argv[2] ?? 'public/models/orbital-atelier-v16.glb';
const terminalPath = 'public/models/welcome-terminal-v1.glb';
const checks = [];
async function check(name, fn) {
  try { checks.push({ name, passed: true, ...await fn() }); }
  catch (error) { checks.push({ name, passed: false, error: error.stack }); }
}
const ids = new Set(ROOM_ENTRY_GROUPS.flatMap(([, ids]) => ids));
ids.add('lighting.ceiling_warm');

await check('hardware extraction preserves every triangle corner attribute byte and final world position', async () => {
  const gltf = await parseModelForCPU(roomPath), room = gltf.scene;
  room.updateMatrixWorld(true);
  const source = room.getObjectByName('WEB8_room_static__baked__A0');
  const original = source.geometry, sourceMatrix = source.matrixWorld.clone(), originalMaterial = source.material;
  const originalIds = []; room.traverse(n => { if (n.userData.asset_id) originalIds.push(n.userData.asset_id); });
  const binding = createRoomEntryAttachments({ THREE, room });
  assert.equal(createRoomEntryAttachments({ THREE, room }), binding, 'binding is idempotent');
  room.updateMatrixWorld(true);
  const segments = [[source, 0], ...binding.meshes.map((mesh, i) => [mesh, binding.getState().attachments[i].sourceTriangles[0]])];
  let corners = 0, attributeBytes = 0, maxPositionError = 0;
  const a = new THREE.Vector3(), b = new THREE.Vector3();
  for (const [mesh, first] of segments) {
    assert.equal(mesh.material, originalMaterial, 'day/night and clean-map hooks retain shared ownership');
    for (let corner = 0; corner < mesh.geometry.index.count; corner++) {
      const oldIndex = original.index.getX(first * 3 + corner), newIndex = mesh.geometry.index.getX(corner);
      for (const [name, attr] of Object.entries(original.attributes)) {
        const next = mesh.geometry.getAttribute(name), bytes = attr.itemSize * attr.array.BYTES_PER_ELEMENT;
        assert.deepEqual(new Uint8Array(next.array.buffer, next.array.byteOffset + newIndex * bytes, bytes),
          new Uint8Array(attr.array.buffer, attr.array.byteOffset + oldIndex * bytes, bytes), `${mesh.name}: ${name}`);
        attributeBytes += bytes;
      }
      a.fromBufferAttribute(original.attributes.position, oldIndex).applyMatrix4(sourceMatrix);
      b.fromBufferAttribute(mesh.geometry.attributes.position, newIndex).applyMatrix4(mesh.matrixWorld);
      maxPositionError = Math.max(maxPositionError, a.distanceTo(b)); corners++;
    }
    const used = new Set(mesh.geometry.index.array);
    assert.equal(used.size, mesh.geometry.attributes.position.count, 'precise Box3 cannot include unrelated unused vertices');
  }
  assert.equal(corners, original.index.count); assert.ok(maxPositionError < 1e-12);
  const afterIds = []; room.traverse(n => { if (n.userData.asset_id) afterIds.push(n.userData.asset_id); });
  assert.deepEqual(afterIds.sort(), originalIds.sort());
  const disposed = binding.meshes.map(mesh => { const count = { value: 0 }; mesh.geometry.addEventListener('dispose', () => count.value++); return count; });
  binding.dispose(); binding.dispose(); assert.equal(source.geometry, original); assert.ok(disposed.every(n => n.value === 1));
  return { corners, attributeBytes, maxPositionError, retainedInteractiveIds: afterIds.length, addedDraws: 2 };
});

await check('all visible prop vertices stay within final envelopes; support furniture settles before mounted props', async () => {
  const roomGltf = await parseModelForCPU(roomPath), welcomeGltf = await parseModelForCPU(terminalPath);
  createRoomEntryAttachments({ THREE, room: roomGltf.scene }); roomGltf.scene.updateMatrixWorld(true);
  const boxes = new Map(); roomGltf.scene.traverse(n => { if (ids.has(n.userData.asset_id)) boxes.set(n.userData.asset_id, new THREE.Box3().setFromObject(n, true)); });
  const f = introFixture({ roomGltf, welcomeGltf });
  const inverse = new THREE.Matrix4(), transform = new THREE.Matrix4(), point = new THREE.Vector3();
  let samples = 0, vertexChecks = 0, maxEnvelopeEscape = 0, supportChecks = 0;
  try {
    f.ready().progress(1); const timeline = f.enter();
    for (let time = 1.35; time < timeline.duration(); time += 1 / 60) {
      timeline.time(time); f.intro.update(); f.scene.updateMatrixWorld(true); inverse.copy(f.room.matrixWorld).invert();
      const state = new Map(f.roomEntry.getState().assets.map(asset => [asset.id, asset]));
      for (const [id, box] of boxes) {
        const node = f.roots.get(id), asset = state.get(id);
        if (asset.factor < .001) continue;
        if (asset.support) { assert.equal(state.get(asset.support).factor, 1, `${id}: never appear above an unfinished support`); supportChecks++; }
        node.traverse(mesh => {
          if (!mesh.isMesh) return;
          transform.multiplyMatrices(inverse, mesh.matrixWorld);
          const position = mesh.geometry.attributes.position;
          for (let i = 0; i < position.count; i++) {
            point.fromBufferAttribute(position, i).applyMatrix4(transform);
            const escape = Math.max(box.min.x - point.x, point.x - box.max.x, box.min.y - point.y, point.y - box.max.y, box.min.z - point.z, point.z - box.max.z, 0);
            maxEnvelopeEscape = Math.max(maxEnvelopeEscape, escape); vertexChecks++;
          }
        });
      }
      samples++;
    }
    assert.ok(maxEnvelopeEscape < 1e-5, `envelope escape: ${maxEnvelopeEscape}`);
    timeline.progress(1); f.intro.update(); f.assertRestored();
    return { samples, vertexChecks, maxEnvelopeEscape, supportChecks, finalExactTransformRestore: true };
  } finally { f.cleanup(); }
});

await check('exterior fade holds final geometry fixed and releases only temporary material copies', async () => {
  const roomGltf = await parseModelForCPU(roomPath), welcomeGltf = await parseModelForCPU(terminalPath);
  const originals = new Map(); roomGltf.scene.traverse(n => { if (n.isMesh) originals.set(n, n.material); });
  const f = introFixture({ roomGltf, welcomeGltf });
  const poses = new Map(), copies = new Map(); f.exteriorModel.updateMatrixWorld(true);
  f.exteriorModel.traverse(n => {
    poses.set(n, n.matrixWorld.clone());
    if (!n.isMesh) return;
    const material = n.material, original = originals.get(n);
    assert.notEqual(material, original); assert.equal(material.map, original.map);
    assert.equal(material.transparent, original.transparent); assert.equal(material.depthWrite, original.depthWrite);
    const shader = { fragmentShader: THREE.ShaderLib.basic.fragmentShader, uniforms: {} };
    material.onBeforeCompile(shader, {});
    assert.ok(shader.uniforms.uEntryExteriorReveal); assert.match(material.customProgramCacheKey(), /entry-exterior-reveal/);
    if (!copies.has(material)) { copies.set(material, 0); material.addEventListener('dispose', () => copies.set(material, copies.get(material) + 1)); }
  });
  try {
    f.ready().progress(1); const timeline = f.enter();
    for (const time of [1.8, 2.3, 2.6, 2.8, 3.2, 3.65]) {
      timeline.time(time); f.intro.update(); f.exteriorModel.updateMatrixWorld(true);
      f.exteriorModel.traverse(n => assert.deepEqual(n.matrixWorld.toArray(), poses.get(n).toArray()));
    }
    f.intro.skip(); f.assertRestored(); f.cleanup();
    f.exteriorModel.traverse(n => { if (n.isMesh) assert.equal(n.material, originals.get(n)); });
    assert.ok([...copies.values()].every(n => n === 1));
    return { fixedNodes: poses.size, releasedMaterialCopies: copies.size, persistentTexturesUnchanged: true };
  } finally { f.cleanup(); }
});

const paths = ['src/main.js', 'src/cube-intro.js', 'src/room-entry.js', 'src/room-entry-attachments.js', roomPath, terminalPath];
const report = { checkedAt: new Date().toISOString(), scope: 'Real GLTF vertices, attributes, hierarchy and production GSAP transforms; CPU tests, not rendered pixels or exhaustive pairwise triangle collision proof.',
  sourceSha256: Object.fromEntries(paths.map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')])),
  passed: checks.filter(x => x.passed).length, failed: checks.filter(x => !x.passed).length, checks };
const revision = Number(roomPath.match(/orbital-atelier-v(\d+)/)?.[1] ?? 0);
const suffix = revision >= 19 ? `-v${revision}` : '';
writeFileSync(new URL(`../docs/validation/entry-clearance${suffix}.json`, import.meta.url), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2)); if (report.failed) process.exitCode = 1;
