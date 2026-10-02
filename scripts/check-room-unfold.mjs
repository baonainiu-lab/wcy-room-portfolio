#!/usr/bin/env node
/** CPU-only, whole-scene final-pose conservation test. No renderer, texture
 * decoder, Blender, browser, GPU, or application module is imported. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import * as THREE from 'three';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OLD = path.join(ROOT, 'public/models/orbital-atelier-v15.glb');
const NEW = path.join(ROOT, 'public/models/room-unfold-v1.glb');
const OUTPUT = path.join(ROOT, 'docs/validation/room-unfold-v1.json');
const TOL = { positionMetres: 1e-5, uv: 1e-5, normalizedNormal: 2e-4, worldMatrix: 1e-5, quaternionLength: 2e-3 };
const sha = b => createHash('sha256').update(b).digest('hex');
const finite = (a, label) => { for (const n of a) assert.ok(Number.isFinite(n), `${label}: non-finite value`); };
const COMPONENT = { 5120: ['getInt8', 1], 5121: ['getUint8', 1], 5122: ['getInt16', 2], 5123: ['getUint16', 2], 5125: ['getUint32', 4], 5126: ['getFloat32', 4] };
const WIDTH = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };

function loadGLB(filename) {
  const bytes = fs.readFileSync(filename);
  assert.equal(bytes.readUInt32LE(0), 0x46546c67, 'GLB magic');
  assert.equal(bytes.readUInt32LE(4), 2, 'glTF 2');
  assert.equal(bytes.readUInt32LE(8), bytes.length, 'GLB declared length');
  let json, binary;
  for (let offset = 12; offset < bytes.length;) {
    const size = bytes.readUInt32LE(offset), type = bytes.readUInt32LE(offset + 4);
    const chunk = bytes.subarray(offset + 8, offset + 8 + size);
    assert.equal(chunk.length, size, 'complete GLB chunk');
    if (type === 0x4e4f534a) json = JSON.parse(chunk.toString());
    if (type === 0x004e4942) binary = chunk;
    offset += 8 + size;
  }
  assert.ok(json && binary, 'embedded JSON and binary');
  assert.ok(!json.extensionsRequired?.includes('KHR_draco_mesh_compression'), 'raw geometry required; Draco unsupported');
  return { filename, bytes, json, binary };
}
function modelFrom(raw, json = raw.json) {
  const cache = new Map();
  function access(index) {
    if (cache.has(index)) return cache.get(index);
    const a = json.accessors[index]; assert.ok(a, `accessor ${index}`);
    const comp = COMPONENT[a.componentType], width = WIDTH[a.type];
    assert.ok(comp && width, `supported accessor ${index}`);
    const out = new Float64Array(a.count * width);
    const read = (viewIndex, byteOffset, count, component, itemWidth, target) => {
      const bv = json.bufferViews[viewIndex]; assert.ok(bv && (!bv.buffer || bv.buffer === 0), 'embedded bufferView');
      const [method, bytes] = COMPONENT[component], stride = bv.byteStride || bytes * itemWidth;
      const start = (bv.byteOffset || 0) + (byteOffset || 0);
      const dv = new DataView(raw.binary.buffer, raw.binary.byteOffset, raw.binary.length);
      assert.ok(start + (count - 1) * stride + itemWidth * bytes <= raw.binary.length, 'accessor inside binary');
      for (let i = 0; i < count; i++) for (let k = 0; k < itemWidth; k++) target[i * itemWidth + k] = dv[method](start + i * stride + k * bytes, true);
    };
    if (a.bufferView !== undefined) read(a.bufferView, a.byteOffset, a.count, a.componentType, width, out);
    if (a.sparse) {
      const s = a.sparse, ids = new Float64Array(s.count), values = new Float64Array(s.count * width);
      read(s.indices.bufferView, s.indices.byteOffset, s.count, s.indices.componentType, 1, ids);
      read(s.values.bufferView, s.values.byteOffset, s.count, a.componentType, width, values);
      for (let i = 0; i < ids.length; i++) {
        assert.ok(ids[i] >= 0 && ids[i] < a.count, 'sparse accessor index');
        out.set(values.subarray(i * width, (i + 1) * width), ids[i] * width);
      }
    }
    if (a.normalized && a.componentType !== 5126) {
      const divisor = { 5120: 127, 5121: 255, 5122: 32767, 5123: 65535, 5125: 4294967295 }[a.componentType];
      for (let i = 0; i < out.length; i++) out[i] = Math.max(-1, out[i] / divisor);
    }
    finite(out, `accessor ${index}`); cache.set(index, out); return out;
  }
  const objects = json.nodes.map((n, index) => {
    const o = new THREE.Object3D(); o.name = n.name || `node_${index}`; o.userData = { ...n.extras };
    if (n.matrix) { assert.equal(n.matrix.length, 16, 'node matrix width'); finite(n.matrix, o.name); o.matrix.fromArray(n.matrix); o.matrixAutoUpdate = false; }
    else {
      if (n.translation) { assert.equal(n.translation.length, 3, 'node translation width'); finite(n.translation, o.name); o.position.fromArray(n.translation); }
      if (n.rotation) { assert.equal(n.rotation.length, 4, 'node quaternion width'); finite(n.rotation, o.name); o.quaternion.fromArray(n.rotation); assert.ok(Math.abs(o.quaternion.length() - 1) <= TOL.quaternionLength, `${o.name}: rest quaternion is unit`); }
      if (n.scale) { assert.equal(n.scale.length, 3, 'node scale width'); finite(n.scale, o.name); o.scale.fromArray(n.scale); }
    }
    return o;
  });
  const parents = new Map();
  json.nodes.forEach((n, i) => n.children?.forEach(child => {
    assert.ok(objects[child] && child !== i && !parents.has(child), 'valid unique parent');
    parents.set(child, i);
  }));
  for (const id of parents.keys()) {
    const seen = new Set([id]); let p = parents.get(id);
    while (p !== undefined) { assert.ok(!seen.has(p), 'acyclic glTF hierarchy'); seen.add(p); p = parents.get(p); }
  }
  for (const [child, p] of parents) objects[p].add(objects[child]);
  const scene = new THREE.Group();
  const sceneSpec = json.scenes[json.scene || 0]; assert.ok(sceneSpec, 'active scene');
  sceneSpec.nodes.forEach(i => { assert.ok(!parents.has(i), 'scene roots have no parent'); scene.add(objects[i]); });
  scene.updateMatrixWorld(true);
  scene.traverse(o => finite(o.matrixWorld.elements, 'finite rest world matrix'));
  const active = new Set(); scene.traverse(o => active.add(o));
  const assets = new Map(), globalIds = new Set();
  objects.forEach((o, i) => {
    if (o.userData.asset_id) { assert.ok(!globalIds.has(o.userData.asset_id), `asset_id globally unique: ${o.userData.asset_id}`); globalIds.add(o.userData.asset_id); }
    if (!active.has(o) || !o.userData.asset_id) return;
    const id = o.userData.asset_id;
    assert.equal(typeof id, 'string', 'string asset_id');
    assert.ok(!assets.has(id), `asset_id unique: ${id}`); assets.set(id, { object: o, index: i });
  });
  return { raw, json, access, objects, scene, active, assets };
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
  return typeof value === 'number' ? Math.round(value * 1e6) / 1e6 : value;
}
function materialKey(j, index) {
  if (index === undefined) return 'DEFAULT_MATERIAL';
  const m = j.materials[index]; assert.ok(m, 'material index');
  const textureInfo = info => {
    if (!info) return null;
    assert.ok(j.textures?.[info.index], 'material texture exists');
    // PNG byte encodings may change; image-pixel integrity is checked by the
    // independent compression verifier. Material assignment still compares its
    // stable original name, PBR values, texture slots, UV set and transforms.
    return { texCoord: info.texCoord || 0, scale: info.scale ?? 1, strength: info.strength ?? 1, extensions: info.extensions || {} };
  };
  const ext = structuredClone(m.extensions || {});
  for (const e of Object.values(ext)) for (const [k, v] of Object.entries(e)) if (/Texture$/.test(k)) e[k] = textureInfo(v);
  const p = m.pbrMetallicRoughness || {}, unlit = Boolean(m.extensions?.KHR_materials_unlit);
  // KHR_materials_unlit ignores metallic and roughness, so Blender changing
  // their inert defaults does not change the material's rendering semantics.
  return JSON.stringify(canonical({ name: m.name || '', doubleSided: m.doubleSided || false, alphaMode: m.alphaMode || 'OPAQUE', alphaCutoff: m.alphaCutoff ?? .5,
    baseColorFactor: p.baseColorFactor || [1, 1, 1, 1], metallicFactor: unlit ? null : p.metallicFactor ?? 1, roughnessFactor: unlit ? null : p.roughnessFactor ?? 1,
    baseColorTexture: textureInfo(p.baseColorTexture), metallicRoughnessTexture: textureInfo(p.metallicRoughnessTexture),
    normalTexture: textureInfo(m.normalTexture), occlusionTexture: textureInfo(m.occlusionTexture), emissiveTexture: textureInfo(m.emissiveTexture), emissiveFactor: m.emissiveFactor || [0, 0, 0], extensions: ext }));
}
function channels(model, requireClip = true) {
  const clips = (model.json.animations || []).filter(a => a.name === 'RoomUnfold');
  if (!requireClip && clips.length === 0) return null;
  assert.equal(clips.length, 1, 'exactly one RoomUnfold animation');
  const clip = clips[0], parsed = [], seen = new Set(); let duration = 0;
  for (const ch of clip.channels) {
    const node = ch.target?.node, kind = ch.target?.path;
    assert.ok(model.objects[node] && model.active.has(model.objects[node]), 'animation target is in active scene');
    assert.ok(['translation', 'rotation', 'scale'].includes(kind), 'RoomUnfold contains only TRS channels');
    assert.ok(!model.json.nodes[node].matrix, 'animated node uses TRS instead of matrix');
    assert.ok(!seen.has(`${node}/${kind}`), 'one animation channel per node/TRS'); seen.add(`${node}/${kind}`);
    const sampler = clip.samplers[ch.sampler]; assert.ok(sampler, 'animation sampler');
    const interpolation = sampler.interpolation || 'LINEAR'; assert.ok(['LINEAR', 'STEP', 'CUBICSPLINE'].includes(interpolation), 'legal interpolation');
    const times = model.access(sampler.input), values = model.access(sampler.output), width = kind === 'rotation' ? 4 : 3;
    assert.equal(model.json.accessors[sampler.input].type, 'SCALAR', 'scalar animation time');
    assert.equal(model.json.accessors[sampler.input].componentType, 5126, 'float animation time');
    assert.equal(model.json.accessors[sampler.output].type, `VEC${width}`, 'TRS sampler width');
    assert.equal(model.json.accessors[sampler.output].componentType, 5126, 'float animation TRS output');
    assert.ok(times.length > 0 && times[0] >= 0, 'nonempty nonnegative animation time');
    for (let i = 1; i < times.length; i++) assert.ok(times[i] > times[i - 1], 'strictly increasing animation time');
    assert.equal(values.length, times.length * width * (interpolation === 'CUBICSPLINE' ? 3 : 1), 'animation output count');
    if (kind === 'rotation') for (let i = 0; i < times.length; i++) {
      const offset = (interpolation === 'CUBICSPLINE' ? i * 3 + 1 : i) * 4;
      const length = Math.hypot(...values.subarray(offset, offset + 4));
      assert.ok(Math.abs(length - 1) <= TOL.quaternionLength, 'animation quaternion is unit');
    }
    duration = Math.max(duration, times.at(-1)); parsed.push({ node, kind, interpolation, times, values, width });
  }
  assert.ok(parsed.length > 0 && duration > 0, 'RoomUnfold has positive duration');
  return { name: clip.name, duration, channels: parsed };
}
function sample(channel, t) {
  const { times, values, width, interpolation } = channel;
  let i = 0; while (i + 1 < times.length && times[i + 1] <= t) i++;
  const valueAt = k => values.slice((interpolation === 'CUBICSPLINE' ? 3 * k + 1 : k) * width, (interpolation === 'CUBICSPLINE' ? 3 * k + 1 : k) * width + width);
  const a = valueAt(i);
  if (t <= times[0]) return valueAt(0);
  if (i === times.length - 1 || interpolation === 'STEP') return a;
  const b = valueAt(i + 1), dt = times[i + 1] - times[i], u = (t - times[i]) / dt;
  if (interpolation === 'CUBICSPLINE') {
    const u2 = u * u, u3 = u2 * u;
    for (let k = 0; k < width; k++) a[k] = (2 * u3 - 3 * u2 + 1) * a[k] + (u3 - 2 * u2 + u) * dt * values[(i * 3 + 2) * width + k] + (-2 * u3 + 3 * u2) * b[k] + (u3 - u2) * dt * values[((i + 1) * 3) * width + k];
    if (channel.kind === 'rotation') { const length = Math.hypot(...a); assert.ok(length > 1e-12, 'sampled cubic quaternion nonzero'); for (let k = 0; k < 4; k++) a[k] /= length; }
  } else if (channel.kind === 'rotation') new THREE.Quaternion().fromArray(a).slerp(new THREE.Quaternion().fromArray(b), u).toArray(a);
  else for (let k = 0; k < width; k++) a[k] += (b[k] - a[k]) * u;
  finite(a, 'sampled TRS'); return a;
}
function seek(model, clip, t) {
  for (const ch of clip.channels) {
    const o = model.objects[ch.node], value = sample(ch, t);
    ({ translation: o.position, rotation: o.quaternion, scale: o.scale }[ch.kind]).fromArray(value);
  }
  model.scene.updateMatrixWorld(true);
  for (const o of model.objects) if (model.active.has(o)) finite(o.matrixWorld.elements, 'animated world matrix');
}
function validateAssets(old, next) {
  assert.equal(old.assets.size, 95, 'reference has all 95 assets');
  for (const id of old.assets.keys()) assert.ok(next.assets.has(id), `preserved asset_id: ${id}`);
  const added = [...next.assets.keys()].filter(id => !old.assets.has(id));
  for (const id of added) assert.ok(id.startsWith('fold.'), `only fold.* asset IDs may be introduced: ${id}`);
  return { referenceCount: 95, preservedCount: 95, addedFoldAssetIds: added };
}
function compareAssetMatrices(old, next) {
  let maxDelta = 0; const mismatches = [];
  for (const [id, { object }] of old.assets) {
    const a = object.matrixWorld.elements, b = next.assets.get(id)?.object.matrixWorld.elements;
    if (!b) { mismatches.push({ asset_id: id, reason: 'missing' }); continue; }
    const delta = Math.max(...a.map((v, i) => Math.abs(v - b[i]))); maxDelta = Math.max(maxDelta, delta);
    if (delta > TOL.worldMatrix) mismatches.push({ asset_id: id, maximumElementError: delta });
  }
  return { pass: mismatches.length === 0, compared: old.assets.size, maximumElementError: maxDelta, mismatches: mismatches.slice(0, 20) };
}
function uvSchema(...models) { return [...new Set(models.flatMap(m => m.json.meshes.flatMap(me => me.primitives.flatMap(p => Object.keys(p.attributes).filter(a => /^TEXCOORD_\d+$/.test(a))))))].sort(); }
function triangles(model, uvNames, materialIds) {
  let count = 0;
  model.json.nodes.forEach((node, i) => {
    if (node.mesh === undefined || !model.active.has(model.objects[i])) return;
    for (const p of model.json.meshes[node.mesh].primitives) {
      assert.ok(p.mode === undefined || p.mode === 4, 'triangle primitive');
      const n = p.indices === undefined ? model.json.accessors[p.attributes.POSITION].count : model.json.accessors[p.indices].count;
      assert.equal(n % 3, 0, 'whole triangles'); count += n / 3;
    }
  });
  const width = 6 + 2 * uvNames.length, stride = width * 3;
  const values = new Float64Array(count * stride), materials = new Uint32Array(count), masks = new Uint32Array(count), origins = [];
  const pos = new THREE.Vector3(), norm = new THREE.Vector3(), normalMatrix = new THREE.Matrix3(); let tri = 0;
  const bbox = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  model.json.nodes.forEach((node, nodeIndex) => {
    const object = model.objects[nodeIndex]; if (node.mesh === undefined || !model.active.has(object)) return;
    assert.ok(node.skin === undefined, 'static room node is not skinned');
    assert.ok(Math.abs(object.matrixWorld.determinant()) > 1e-12, 'invertible final mesh transform');
    normalMatrix.getNormalMatrix(object.matrixWorld);
    for (const p of model.json.meshes[node.mesh].primitives) {
      assert.ok(!p.targets?.length, 'no morph geometry in reference conservation check');
      const position = model.access(p.attributes.POSITION), normal = p.attributes.NORMAL === undefined ? null : model.access(p.attributes.NORMAL);
      const uvs = uvNames.map(name => p.attributes[name] === undefined ? null : model.access(p.attributes[name]));
      const index = p.indices === undefined ? null : model.access(p.indices), length = index?.length ?? position.length / 3;
      const key = materialKey(model.json, p.material); if (!materialIds.has(key)) materialIds.set(key, materialIds.size);
      const material = materialIds.get(key), mask = (normal ? 1 : 0) | uvs.reduce((n, a, i) => n | (a ? 1 << (i + 1) : 0), 0);
      origins.push({ start: tri, triangles: length / 3, node: node.name || nodeIndex, material: model.json.materials?.[p.material]?.name || '(default)' });
      for (let start = 0; start < length; start += 3, tri++) {
        materials[tri] = material; masks[tri] = mask;
        for (let corner = 0; corner < 3; corner++) {
          const vi = index ? index[start + corner] : start + corner;
          assert.ok(Number.isInteger(vi) && vi >= 0 && vi * 3 + 2 < position.length, 'valid vertex index');
          pos.fromArray(position, vi * 3).applyMatrix4(object.matrixWorld);
          [pos.x, pos.y, pos.z].forEach((v, k) => { bbox.min[k] = Math.min(bbox.min[k], v); bbox.max[k] = Math.max(bbox.max[k], v); });
          norm.set(0, 0, 0); if (normal) norm.fromArray(normal, vi * 3).applyMatrix3(normalMatrix).normalize();
          const offset = tri * stride + corner * width;
          values.set([pos.x, pos.y, pos.z, norm.x, norm.y, norm.z], offset);
          uvs.forEach((uv, k) => { if (uv) values.set([uv[vi * 2], uv[vi * 2 + 1]], offset + 6 + k * 2); });
        }
      }
    }
  });
  finite(values, 'world triangle data'); return { count, width, stride, values, materials, masks, origins, bbox };
}
function compareTriangles(reference, target, maxExamples = 12, diagnosticIgnoreNormals = false) {
  const { width, stride } = reference; assert.equal(target.stride, stride, 'common corner schema');
  const cell = TOL.positionMetres * 4, buckets = new Map(), consumed = new Uint8Array(reference.count);
  function xyz(t, i) { const o = i * stride, a = t.values; return [0, 1, 2].map(k => Math.floor((a[o + k] + a[o + width + k] + a[o + 2 * width + k]) / (3 * cell))); }
  const key = (t, i, p) => `${t.materials[i]}/${t.masks[i]}/${p[0]},${p[1]},${p[2]}`;
  for (let i = 0; i < reference.count; i++) { const k = key(reference, i, xyz(reference, i)), bucket = buckets.get(k); if (bucket) bucket.push(i); else buckets.set(k, [i]); }
  let matched = 0, unmatched = 0; const examples = [], unmatchedByNode = new Map(); let maxPosition = 0, maxUV = 0, maxNormal = 0, worstNormalMatch = null;
  function fits(i, j) {
    for (let rotation = 0; rotation < 3; rotation++) {
      let okay = true, dp = 0, du = 0, dn = 0;
      for (let c = 0; c < 3 && okay; c++) {
        const a = i * stride + c * width, b = j * stride + ((c + rotation) % 3) * width;
        for (let k = 0; k < width; k++) {
          const d = Math.abs(reference.values[a + k] - target.values[b + k]);
          const tol = k < 3 ? TOL.positionMetres : k < 6 ? (diagnosticIgnoreNormals ? Infinity : TOL.normalizedNormal) : TOL.uv;
          if (d > tol) { okay = false; break; }
          if (k < 3) dp = Math.max(dp, d); else if (k < 6) dn = Math.max(dn, d); else du = Math.max(du, d);
        }
      }
      if (okay) {
        maxPosition = Math.max(maxPosition, dp); maxUV = Math.max(maxUV, du);
        if (dn > maxNormal) { maxNormal = dn; worstNormalMatch = { referenceNode: reference.origins.findLast(o => o.start <= i)?.node, targetNode: target.origins.findLast(o => o.start <= j)?.node, referenceTriangle: i, targetTriangle: j, maximumComponentError: dn, referenceCornerNormals: [0, 1, 2].map(c => Array.from(reference.values.subarray(i * stride + c * width + 3, i * stride + c * width + 6))), targetCorrespondingCornerNormals: [0, 1, 2].map(c => Array.from(target.values.subarray(j * stride + ((c + rotation) % 3) * width + 3, j * stride + ((c + rotation) % 3) * width + 6))) }; }
        return true; }
    }
    return false;
  }
  for (let j = 0; j < target.count; j++) {
    const centre = xyz(target, j); let found = false;
    const search = p => {
      const entries = buckets.get(key(target, j, p)); if (!entries) return false;
      for (const i of entries) if (!consumed[i] && fits(i, j)) { consumed[i] = 1; return true; }
      return false;
    };
    found = search(centre);
    for (let x = -1; x <= 1 && !found; x++) for (let y = -1; y <= 1 && !found; y++) for (let z = -1; z <= 1 && !found; z++) {
      if (x || y || z) found = search([centre[0] + x, centre[1] + y, centre[2] + z]);
    }
    if (found) matched++;
    else { unmatched++; const node = target.origins.findLast(o => o.start <= j)?.node; unmatchedByNode.set(node, (unmatchedByNode.get(node) || 0) + 1); if (examples.length < maxExamples) examples.push({ triangle: j, node, firstCorner: Array.from(target.values.subarray(j * stride, j * stride + 3)), reason: 'No same-material same-UV same-normal triangle with matching cyclic winding within tolerance' }); }
  }
  const missing = reference.count - matched;
  return { pass: missing === 0 && unmatched === 0 && reference.count === target.count, referenceBoundingBox: reference.bbox, targetBoundingBox: target.bbox, referenceTriangles: reference.count, targetTriangles: target.count, matchedTriangles: matched, missingReferenceTriangles: missing, unmatchedTargetTriangles: unmatched, maximumPositionErrorMetres: maxPosition, maximumUVError: maxUV, maximumNormalizedNormalError: maxNormal, worstNormalMatch, unmatchedByNode: Object.fromEntries([...unmatchedByNode].sort((a, b) => b[1] - a[1])), mismatchExamples: examples };
}
function assertPass(result, label) { assert.ok(result.pass, `${label}: ${result.unmatchedTargetTriangles !== undefined ? `${result.unmatchedTargetTriangles} unmatched target triangles, ${result.missingReferenceTriangles} missing reference triangles` : `${result.mismatches?.length || 0} mismatched asset matrices`}`); }

function selfTest() {
  const raw = loadGLB(OLD), old = modelFrom(raw), changed = structuredClone(raw.json);
  const ni = changed.nodes.findIndex(n => n.mesh !== undefined && changed.meshes[n.mesh].primitives.length === 1);
  assert.ok(ni >= 0); const node = changed.nodes[ni], primitive = changed.meshes[node.mesh].primitives[0];
  assert.ok(primitive.indices !== undefined, 'self-test selected indexed mesh');
  const originalAccessor = changed.accessors[primitive.indices], part = Math.floor(originalAccessor.count / 6) * 3;
  const bytesPerIndex = COMPONENT[originalAccessor.componentType][1];
  const a = changed.accessors.length; changed.accessors.push({ ...originalAccessor, count: part });
  const b = changed.accessors.length; changed.accessors.push({ ...originalAccessor, count: originalAccessor.count - part, byteOffset: (originalAccessor.byteOffset || 0) + part * bytesPerIndex });
  for (const id of [a, b]) { delete changed.accessors[id].min; delete changed.accessors[id].max; }
  const childIds = [];
  for (const id of [a, b]) {
    const mesh = changed.meshes.length; changed.meshes.push({ name: `test_split_${id}`, primitives: [{ ...primitive, indices: id }] });
    childIds.push(changed.nodes.length); changed.nodes.push({ name: `test_split_${id}`, mesh });
  }
  delete node.mesh; node.children = [...(node.children || []), ...childIds];
  // A nonidentity carrier with compensated local matrix exercises legitimate
  // reparenting, not merely an identity Empty or a copy of the old owner map.
  const local = old.objects[ni].matrix.clone(), carrierMatrix = new THREE.Matrix4().makeTranslation(.25, -.10, .40);
  node.matrix = carrierMatrix.clone().invert().multiply(local).toArray(); delete node.translation; delete node.rotation; delete node.scale;
  const carrier = changed.nodes.length;
  changed.nodes.forEach(n => { if (n.children) n.children = n.children.map(id => id === ni ? carrier : id); });
  changed.scenes.forEach(s => { s.nodes = s.nodes.map(id => id === ni ? carrier : id); });
  changed.nodes.push({ name: 'self_test_carrier', translation: [.25, -.10, .40], children: [ni], extras: { asset_id: 'fold.self_test' } });
  const next = modelFrom(raw, changed); validateAssets(old, next); assertPass(compareAssetMatrices(old, next), 'split/reparent asset matrices');
  const uv = uvSchema(old, next), mats = new Map(), refs = triangles(old, uv, mats), copy = triangles(next, uv, mats);
  assertPass(compareTriangles(refs, copy), 'V15 full-scene split/reparent triangle conservation');
  const size = Math.min(64, refs.count), fixture = { ...refs, count: size, values: refs.values.slice(0, size * refs.stride), materials: refs.materials.slice(0, size), masks: refs.masks.slice(0, size) };
  const tests = ['full V15 split + nonidentity reparent preserves world geometry and 95 roots'];
  for (const kind of ['position', 'uv', 'normal', 'winding', 'material', 'deleted_triangle']) {
    const broken = { ...fixture, values: fixture.values.slice(), materials: fixture.materials.slice(), masks: fixture.masks.slice() };
    if (kind === 'position') broken.values[0] += .003;
    if (kind === 'uv') broken.values[6] += .03;
    if (kind === 'normal') broken.values[3] += .1;
    if (kind === 'material') broken.materials[0] = 0xffffffff;
    if (kind === 'winding') for (let k = 0; k < refs.width; k++) [broken.values[refs.width + k], broken.values[refs.width * 2 + k]] = [broken.values[refs.width * 2 + k], broken.values[refs.width + k]];
    if (kind === 'deleted_triangle') broken.count--;
    assert.equal(compareTriangles(fixture, broken).pass, false, `reject ${kind}`); tests.push(`rejects ${kind}`);
  }
  // Endpoint evaluation handles actual rotations and valid cubic glTF channels.
  const cubic = { kind: 'translation', interpolation: 'CUBICSPLINE', width: 3, times: [0, 1], values: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3, 4, 0, 0, 0] };
  assert.deepEqual(Array.from(sample(cubic, 1)), [2, 3, 4]); tests.push('glTF cubic final-frame evaluation');
  return { status: 'self-test-pass', tests, actualNewModelVerified: false, referenceTriangles: refs.count, preservedAssets: 95, tolerances: TOL };
}
function main() {
  if (process.argv.includes('--self-test')) { console.log(JSON.stringify(selfTest(), null, 2)); return; }
  if (!fs.existsSync(NEW)) {
    const pending = { status: 'awaiting-export', actualNewModelVerified: false, expectedFile: path.relative(ROOT, NEW), referenceFile: path.relative(ROOT, OLD), tolerances: TOL };
    console.log(JSON.stringify(pending, null, 2)); process.exitCode = 2; return;
  }
  const report = { checkedAt: new Date().toISOString(), status: 'fail', usageStatus: 'experimental/non-active', scope: 'Entire active GLB scene, including orbital_dock and warm_gallery; no owner-based triangle attribution', tolerances: TOL, texturePixelIntegrity: 'Checked separately by scripts/compress-room-unfold.py; this comparator verifies material semantic assignment and texture slot/UV-transform semantics, not image bytes.' };
  try {
    const oldRaw = loadGLB(OLD), newRaw = loadGLB(NEW), old = modelFrom(oldRaw), next = modelFrom(newRaw);
    report.files = { reference: { path: path.relative(ROOT, OLD), sha256: sha(oldRaw.bytes), bytes: oldRaw.bytes.length }, unfolded: { path: path.relative(ROOT, NEW), sha256: sha(newRaw.bytes), bytes: newRaw.bytes.length } };
    report.assets = validateAssets(old, next);
    const clip = channels(next); report.animation = { name: clip.name, durationSeconds: clip.duration, channels: clip.channels.length, finiteLegalSamplers: true };
    const uv = uvSchema(old, next), materials = new Map(); report.comparedUVSets = uv;
    const reference = triangles(old, uv, materials);
    report.restAssetWorldMatrices = compareAssetMatrices(old, next);
    report.restGeometry = compareTriangles(reference, triangles(next, uv, materials));
    // Exercise real channel evaluation and hierarchy propagation, then retain
    // the fully unfolded final pose rather than inspecting metadata alone.
    seek(next, clip, 0); seek(next, clip, clip.duration / 2); seek(next, clip, clip.duration);
    report.finalAssetWorldMatrices = compareAssetMatrices(old, next);
    const finalTriangles = triangles(next, uv, materials);
    report.finalGeometry = compareTriangles(reference, finalTriangles);
    if (!report.finalGeometry.pass) report.normalIsolationDiagnostic = { informationalOnly: true, doesNotOverrideStrictResult: true, note: 'Normal-error examples use one valid position/UV/material/cyclic-winding pairing; coincident faces can have multiple such pairings. The strict normal-aware mismatch count remains the acceptance result.', ...compareTriangles(reference, finalTriangles, 12, true) };
    report.materialComparison = { stableNameAndEffectivePBRAndTextureSlotSemantics: true, ignoredInertFields: 'KHR_materials_unlit metallicFactor/roughnessFactor only (glTF unlit ignores both). Non-unlit values, alpha, UV transform and slot semantics remain strict.' };
    assertPass(report.restAssetWorldMatrices, 'rest root world matrices');
    assertPass(report.restGeometry, 'rest geometry');
    assertPass(report.finalAssetWorldMatrices, 'RoomUnfold final root world matrices');
    assertPass(report.finalGeometry, 'RoomUnfold final geometry');
    report.status = 'pass'; report.actualNewModelVerified = true;
  } catch (error) { report.error = error.message; report.actualNewModelVerified = false; process.exitCode = 1; }
  if (process.argv.includes('--draft')) { report.exportState = 'draft'; report.status = report.status === 'pass' ? 'draft-pass' : 'draft-fail'; }
  else { fs.mkdirSync(path.dirname(OUTPUT), { recursive: true }); fs.writeFileSync(OUTPUT, JSON.stringify(report, null, 2) + '\n'); }
  console.log(JSON.stringify(report, null, 2));
}
main();
