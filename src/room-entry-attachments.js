// V15 contains ten device details in its otherwise architectural A0 mesh.
// Move their existing triangles into the device hierarchies in memory only.
// The source GLB, corner normals, UVs and shared lighting material stay intact.
export const ROOM_ENTRY_ATTACHMENT_SOURCE = Object.freeze({
  meshName: 'WEB8_room_static__baked__A0',
  materialName: 'WEB8_LIGHTMAP_0',
  vertices: 21635,
  triangles: 23712,
  compressedSha256: '3787d233559af32f2e3ababb21b71c56c5805e7c7f2e286f87634efe8cd6bffd',
  originalSha256: '5e919bbc24ccbf0b097a9c4c1b181d48b538d6ff25c0899d1f5cb8d949e15c15',
  fingerprints: Object.freeze({ position: 0xa5f2e5b1, normal: 0x62323b93, uv: 0x0c09e6ae, index: 0xfbe633cd }),
  ranges: Object.freeze([
    Object.freeze({ id: 'main_display', first: 8364, end: 13860 }),
    Object.freeze({ id: 'compute_core', first: 13860, end: 23712 }),
  ]),
});

// V19 removes only the first 180 floor-grid triangles. The surviving corner
// attributes were compared with V18; device hardware itself is unchanged.
const SOURCES = Object.freeze([
  ROOM_ENTRY_ATTACHMENT_SOURCE,
  Object.freeze({
    meshName: 'WEB8_room_static__baked__A0', materialName: 'WEB8_LIGHTMAP_0',
    vertices: 21373, triangles: 23532,
    removedTrianglePrefix: 180,
    fingerprints: Object.freeze({ position: 0x828a2610, normal: 0x4966c1bb, uv: 0xc065ff4f, index: 0xb9813701 }),
    ranges: Object.freeze([
      Object.freeze({ id: 'main_display', first: 8184, end: 13680 }),
      Object.freeze({ id: 'compute_core', first: 13680, end: 23532 }),
    ]),
  }),
]);
const prepared = new WeakMap();
const fail = message => { throw new Error(`Room entry attachments: ${message}`); };

function fingerprint(attribute) {
  if (!attribute || attribute.isInterleavedBufferAttribute) fail('expected packed audited attributes');
  const array = attribute.array;
  const bytes = new Uint8Array(array.buffer, array.byteOffset, array.byteLength);
  let hash = 0x811c9dc5;
  for (const value of bytes) hash = Math.imul(hash ^ value, 0x01000193);
  return hash >>> 0;
}

// Compact both the remaining architecture and attachments: precise Box3,
// hover clearance and framing also inspect unindexed position attributes.
function subset(THREE, source, firstTriangle, endTriangle) {
  const index = source.index.array;
  const oldVertices = [], remap = new Map();
  const nextIndex = new index.constructor((endTriangle - firstTriangle) * 3);
  for (let i = firstTriangle * 3, out = 0; i < endTriangle * 3; i++, out++) {
    const old = index[i];
    if (!remap.has(old)) { remap.set(old, oldVertices.length); oldVertices.push(old); }
    nextIndex[out] = remap.get(old);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.name = `${source.name || 'A0'}_triangles_${firstTriangle}_${endTriangle}`;
  for (const [name, attribute] of Object.entries(source.attributes)) {
    const array = attribute.array;
    const width = attribute.itemSize * array.BYTES_PER_ELEMENT;
    const copy = new array.constructor(oldVertices.length * attribute.itemSize);
    const originalBytes = new Uint8Array(array.buffer, array.byteOffset, array.byteLength);
    const copiedBytes = new Uint8Array(copy.buffer);
    oldVertices.forEach((old, current) => copiedBytes.set(originalBytes.subarray(old * width, (old + 1) * width), current * width));
    const next = new THREE.BufferAttribute(copy, attribute.itemSize, attribute.normalized);
    next.name = attribute.name; next.setUsage(attribute.usage); next.gpuType = attribute.gpuType;
    geometry.setAttribute(name, next);
  }
  geometry.setIndex(new THREE.BufferAttribute(nextIndex, 1));
  geometry.setDrawRange(0, nextIndex.length);
  geometry.computeBoundingBox(); geometry.computeBoundingSphere();
  return geometry;
}

/** Call once before mesh registration, bounds, hitboxes and lighting setup.
 * Bindings remain for the room lifetime, including later device interaction.
 * dispose() is for room teardown, not for completing or skipping the intro.
 */
export function createRoomEntryAttachments({ THREE, room, roots }) {
  if (prepared.has(room)) return prepared.get(room);
  const matches = [], owners = new Map();
  room.traverse(node => {
    if (node.isMesh && node.name === ROOM_ENTRY_ATTACHMENT_SOURCE.meshName) matches.push(node);
    if (ROOM_ENTRY_ATTACHMENT_SOURCE.ranges.some(range => range.id === node.userData?.asset_id)) {
      if (owners.has(node.userData.asset_id)) fail(`duplicate owner ${node.userData.asset_id}`);
      owners.set(node.userData.asset_id, node);
    }
  });
  if (matches.length !== 1) fail('expected one original A0 mesh');
  const source = matches[0], original = source.geometry, material = source.material;
  if (source.isSkinnedMesh || Array.isArray(material) || material?.name !== ROOM_ENTRY_ATTACHMENT_SOURCE.materialName) fail('unexpected source mesh or material');
  const specification = SOURCES.find(item => original.attributes.position?.count === item.vertices && original.index?.count === item.triangles * 3);
  if (!specification) fail('unexpected geometry counts; re-audit triangle ranges');
  const ranges = specification.ranges;
  if (Object.keys(original.morphAttributes).length || original.groups.length > 1) fail('unexpected morphs or primitive groups');
  for (const [name, attribute] of Object.entries(original.attributes)) {
    if (attribute.isInterleavedBufferAttribute || attribute.count !== specification.vertices) fail(`unexpected ${name} attribute layout`);
  }
  for (const [name, expected] of Object.entries(specification.fingerprints)) {
    if (fingerprint(name === 'index' ? original.index : original.getAttribute(name)) !== expected) fail(`source ${name} fingerprint changed; re-audit triangle ranges`);
  }
  for (const { id } of ranges) {
    if (!owners.has(id) || (roots && roots.get(id) !== owners.get(id))) fail(`missing or mismatched owner ${id}`);
  }
  room.updateWorldMatrix(true, true);
  for (const { id } of ranges) {
    if (Math.abs(owners.get(id).matrixWorld.determinant()) < 1e-12) fail(`owner ${id} is already collapsed; attach before animation`);
  }
  const sourceWorld = source.matrixWorld.clone();
  const owned = [subset(THREE, original, 0, ranges[0].first)];
  const meshes = [];
  for (const { id, first, end } of ranges) {
    const owner = owners.get(id);
    const mesh = source.clone(false);
    mesh.name = `WEB8_${id}__entry_hardware__A0`;
    mesh.geometry = subset(THREE, original, first, end); owned.push(mesh.geometry);
    mesh.userData = { ...mesh.userData, owner_asset_id: id, entry_attachment: true, source_triangles: [first, end] };
    // Keep the inverse as a matrix instead of decomposing/recomposing floats.
    mesh.matrix.copy(owner.matrixWorld).invert().multiply(sourceWorld);
    mesh.matrix.decompose(mesh.position, mesh.quaternion, mesh.scale);
    mesh.matrixAutoUpdate = false;
    owner.add(mesh); meshes.push(mesh);
  }
  source.geometry = owned[0];
  source.geometry.userData.entryRemovedTrianglePrefix = specification.removedTrianglePrefix ?? 0;
  room.updateWorldMatrix(true, true);
  let disposed = false;
  const binding = {
    meshes,
    getState: () => ({ revision: 2, disposed, source: source.name, retainedTriangles: ranges[0].first,
      attachments: meshes.map((mesh, i) => ({ owner: ranges[i].id, mesh: mesh.name,
        triangles: ranges[i].end - ranges[i].first, vertices: mesh.geometry.attributes.position.count,
        sourceTriangles: [ranges[i].first, ranges[i].end] })) }),
    dispose() {
      if (disposed) return;
      source.geometry = original; meshes.forEach(mesh => mesh.removeFromParent());
      owned.forEach(geometry => geometry.dispose());
      prepared.delete(room); disposed = true;
    },
  };
  prepared.set(room, binding);
  return binding;
}
