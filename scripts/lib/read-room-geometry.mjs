import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';

// Read the actual GLB geometry without a browser, GPU, textures, or decoder.
export function readRoomGeometry(modelUrl) {
  if (!modelUrl) {
    const main = readFileSync(new URL('../../src/main.js', import.meta.url), 'utf8');
    modelUrl = main.match(/loader\.loadAsync\('([^']+\.glb)'/)?.[1];
  }
  assert.ok(modelUrl, 'active room model URL exists');
  const glb = readFileSync(new URL(`../../public${modelUrl}`, import.meta.url));
  assert.equal(glb.readUInt32LE(0), 0x46546c67, 'GLB magic');
  assert.equal(glb.readUInt32LE(16), 0x4e4f534a, 'GLB JSON chunk');
  const jsonEnd = 20 + glb.readUInt32LE(12);
  const data = JSON.parse(glb.subarray(20, jsonEnd).toString());
  const binary = glb.subarray(jsonEnd + 8);
  const types = { 5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
  const widths = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
  function accessor(index) {
    const spec = data.accessors[index], view = data.bufferViews[spec.bufferView];
    const Type = types[spec.componentType], width = widths[spec.type];
    assert.ok(Type && width && !spec.sparse && !view.byteStride, 'packed nonsparse GLB accessor');
    return new THREE.BufferAttribute(new Type(binary.buffer,
      binary.byteOffset + (view.byteOffset || 0) + (spec.byteOffset || 0), spec.count * width), width);
  }
  const nodes = data.nodes.map(spec => {
    const node = new THREE.Group(); node.name = spec.name || ''; node.userData = { ...spec.extras };
    if (spec.matrix) {
      node.matrix.fromArray(spec.matrix); node.matrix.decompose(node.position, node.quaternion, node.scale);
    } else {
      if (spec.translation) node.position.fromArray(spec.translation);
      if (spec.rotation) node.quaternion.fromArray(spec.rotation);
      if (spec.scale) node.scale.fromArray(spec.scale);
    }
    if (spec.mesh !== undefined) for (const primitive of data.meshes[spec.mesh].primitives) {
      assert.ok(primitive.mode === undefined || primitive.mode === 4, 'triangle primitive');
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', accessor(primitive.attributes.POSITION));
      if (primitive.indices !== undefined) geometry.setIndex(accessor(primitive.indices));
      const material = new THREE.MeshBasicMaterial();
      material.name = data.materials?.[primitive.material]?.name || '';
      const mesh = new THREE.Mesh(geometry, material); mesh.name = spec.name || '';
      node.add(mesh);
    }
    return node;
  });
  data.nodes.forEach((spec, index) => spec.children?.forEach(child => nodes[index].add(nodes[child])));
  const room = new THREE.Group(); room.name = 'OrbitalAtelier';
  data.scenes[data.scene || 0].nodes.forEach(index => room.add(nodes[index]));
  const components = new Map(), excluded = [];
  room.traverse(node => {
    if (['environment.orbital_dock', 'environment.warm_gallery'].includes(node.userData.asset_id)) excluded.push(node);
    if (node.userData.asset_id) components.set(node.userData.asset_id, node);
  });
  excluded.forEach(node => node.removeFromParent());
  room.updateMatrixWorld(true);
  return { room, components, modelUrl, data, nodes };
}
