import assert from 'node:assert/strict';
import * as THREE from 'three';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { createRoomHoverClearance, isMountedRoomPart } from '../src/room-hover-clearance.js';

const { room, components } = readRoomGeometry(process.argv[2]);
for (const [id, node] of components) if (!node.parent) components.delete(id);
const clearance = createRoomHoverClearance({ THREE, room, components });
const results = [];
for (const id of ['thermal_cup', 'compact_camera', 'studio_reference_books', 'ceramic_mobius_study', 'folding_drawing_terminal', 'table_notebook_group']) {
  const node = components.get(id);
  assert.ok(node, id);
  const original = { position: node.position.clone(), scale: node.scale.clone() };
  const before = new THREE.Box3().setFromObject(node, true);
  node.scale.copy(original.scale).multiplyScalar(1.8);
  node.position.copy(clearance.position(node, original, 1.8));
  room.updateMatrixWorld(true);
  const after = new THREE.Box3().setFromObject(node, true);
  assert.ok(after.min.y >= before.min.y - 1e-5, `${id} underside must not sink through its support`);
  node.position.copy(clearance.position(node, original, 1));
  node.scale.copy(original.scale);
  room.updateMatrixWorld(true);
  assert.ok(node.position.equals(original.position), `${id} restores exact base pose`);
  results.push({ id, bottomBefore: before.min.y, bottomAfter: after.min.y });
}
for (const id of ['flower_petal_0', 'camera_focus_lens', 'keyboard_dial']) {
  const node = components.get(id);
  assert.ok(isMountedRoomPart(node), `${id} remains attached`);
  const original = { position: node.position.clone() };
  assert.ok(clearance.position(node, original, 1.12).equals(original.position));
}
console.log(JSON.stringify({ passed: true, looseProps: results, mountedParts: 3 }, null, 2));
