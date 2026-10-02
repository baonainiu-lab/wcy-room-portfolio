import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';

export function actualFixture() {
  const main = readFileSync(new URL('../../src/main.js', import.meta.url), 'utf8');
  const modelPath = main.match(/loader\.loadAsync\('([^']+\.glb)'/)?.[1];
  assert.ok(modelPath, 'active model URL exists');
  const glb = readFileSync(new URL(`../../public${modelPath}`, import.meta.url));
  assert.equal(glb.readUInt32LE(0), 0x46546c67); assert.equal(glb.readUInt32LE(16), 0x4e4f534a);
  const jsonEnd = 20 + glb.readUInt32LE(12);
  const data = JSON.parse(glb.subarray(20, jsonEnd).toString());
  const binary = glb.subarray(jsonEnd + 8);
  const typedArrays = { 5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
  const readAccessor = index => {
    const accessor = data.accessors[index], view = data.bufferViews[accessor.bufferView];
    const width = accessor.type === 'VEC3' ? 3 : 1, ArrayType = typedArrays[accessor.componentType];
    assert.ok(ArrayType && !accessor.sparse && !view.byteStride, 'packed nonsparse model accessor');
    return new THREE.BufferAttribute(new ArrayType(binary.buffer, binary.byteOffset + (view.byteOffset || 0) + (accessor.byteOffset || 0), accessor.count * width), width);
  };
  const scene = new THREE.Scene(), room = new THREE.Group(); scene.add(room);
  const nodes = data.nodes.map(spec => {
    const node = new THREE.Group(); node.name = spec.name || ''; node.userData = { ...spec.extras };
    if (spec.matrix) { node.matrix.fromArray(spec.matrix); node.matrix.decompose(node.position, node.quaternion, node.scale); }
    else {
      if (spec.translation) node.position.fromArray(spec.translation);
      if (spec.rotation) node.quaternion.fromArray(spec.rotation);
      if (spec.scale) node.scale.fromArray(spec.scale);
    }
    if (spec.mesh !== undefined) for (const primitive of data.meshes[spec.mesh].primitives) {
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', readAccessor(primitive.attributes.POSITION));
      if (primitive.indices !== undefined) geometry.setIndex(readAccessor(primitive.indices));
      node.add(new THREE.Mesh(geometry));
    }
    return node;
  });
  data.nodes.forEach((spec, index) => spec.children?.forEach(child => nodes[index].add(nodes[child])));
  data.scenes[data.scene || 0].nodes.forEach(index => room.add(nodes[index]));
  const components = new Map(), snapshots = new WeakMap();
  scene.traverse(node => {
    if (node.userData.asset_id) {
      assert.ok(!components.has(node.userData.asset_id), `unique ID ${node.userData.asset_id}`);
      components.set(node.userData.asset_id, node);
      snapshots.set(node, { position: node.position.clone(), rotation: node.rotation.clone(), scale: node.scale.clone() });
    }
  });
  scene.updateMatrixWorld(true);
  return { scene, room, components, snapshots, nodes, modelPath, drone: components.get('v5_scout_drone') };
}
export function verticesIn(node, reference) {
  node.updateWorldMatrix(true, true); reference.updateWorldMatrix(true, false);
  const inverse = reference.matrixWorld.clone().invert(), points = [];
  node.traverse(child => {
    const positions = child.geometry?.getAttribute('position');
    if (!positions) return;
    const transform = new THREE.Matrix4().multiplyMatrices(inverse, child.matrixWorld);
    for (let index = 0; index < positions.count; index++) points.push(new THREE.Vector3().fromBufferAttribute(positions, index).applyMatrix4(transform));
  });
  return points;
}
export function floorHull(vertices) {
  const points = vertices.map(point => [point.x, point.z]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const half = sequence => {
    const result = [];
    for (const point of sequence) { while (result.length > 1 && cross(result.at(-2), result.at(-1), point) <= 0) result.pop(); result.push(point); }
    return result.slice(0, -1);
  };
  return [...half(points), ...half(points.reverse())];
}
export function separatingGap(a, b) {
  let gap = -Infinity;
  for (const hull of [a, b]) for (let i = 0; i < hull.length; i++) {
    const current = hull[i], next = hull[(i + 1) % hull.length];
    const length = Math.hypot(next[0] - current[0], next[1] - current[1]);
    const axis = [-(next[1] - current[1]) / length, (next[0] - current[0]) / length];
    const projectedA = a.map(point => point[0] * axis[0] + point[1] * axis[1]);
    const projectedB = b.map(point => point[0] * axis[0] + point[1] * axis[1]);
    gap = Math.max(gap, Math.min(...projectedA) - Math.max(...projectedB), Math.min(...projectedB) - Math.max(...projectedA));
  }
  return gap;
}
