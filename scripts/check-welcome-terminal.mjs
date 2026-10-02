import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const file = path => new URL(`../${path}`, import.meta.url), sha = bytes => createHash('sha256').update(bytes).digest('hex');
const modelPath = 'public/models/welcome-terminal-v1.glb', blendPath = 'assets/blender/welcome-terminal-v1.blend';
const artworkPath = 'public/textures/lighting-v15/screen-art-render.png', authorPath = 'assets/blender/build-welcome-terminal-v1.py';
const bytes = readFileSync(file(modelPath)), blendBytes = readFileSync(file(blendPath));
const jsonEnd = 20 + bytes.readUInt32LE(12), data = JSON.parse(bytes.subarray(20, jsonEnd)), binary = bytes.subarray(jsonEnd + 8);
const modelSha = sha(bytes), blendSha = sha(blendBytes), expectedRoots = ['seed.base', 'seed.lid', 'seed.dial', 'seed.rail'];
const results = [], details = {};
const close = (a, b, epsilon = 2e-6) => assert.ok(Math.abs(a - b) <= epsilon, `${a} differs from ${b}`);
const nameOf = node => node.userData.name ?? node.name;
const boxJSON = box => ({ min: box.min.toArray(), max: box.max.toArray(), size: box.getSize(new THREE.Vector3()).toArray() });
const boxOf = object => { object.updateWorldMatrix(true, true); return new THREE.Box3().setFromObject(object, true); };
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.stack }); }
}

// Keep the original nodes, geometry, accessors and animations for GLTFLoader.
// The material references are removed only in this in-memory CPU fixture so
// loading an embedded image cannot start browser, canvas or GPU operations.
const cpuJSON = structuredClone(data);
cpuJSON.meshes.forEach(mesh => mesh.primitives.forEach(primitive => delete primitive.material));
const encoded = Buffer.from(JSON.stringify(cpuJSON)), padding = Buffer.alloc((-encoded.length >>> 0) % 4, 0x20);
const header = Buffer.alloc(20), binHeader = Buffer.alloc(8);
header.writeUInt32LE(0x46546c67); header.writeUInt32LE(2, 4); header.writeUInt32LE(28 + encoded.length + padding.length + binary.length, 8);
header.writeUInt32LE(encoded.length + padding.length, 12); header.writeUInt32LE(0x4e4f534a, 16);
binHeader.writeUInt32LE(binary.length); binHeader.writeUInt32LE(0x004e4942, 4);
const cpuBytes = Buffer.concat([header, encoded, padding, binHeader, binary]);
const gltf = await new GLTFLoader().parseAsync(cpuBytes.buffer.slice(cpuBytes.byteOffset, cpuBytes.byteOffset + cpuBytes.byteLength), '');
const model = gltf.scene, meshes = [], nodes = new Map();
model.traverse(node => { nodes.set(nameOf(node), node); if (node.isMesh) meshes.push(node); });
model.updateMatrixWorld(true);
const original = new Map(); model.traverse(node => original.set(node, { position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone(), matrix: node.matrixWorld.clone() }));

await check('self-contained GLB exports eighteen mesh nodes and four independent seed roots', () => {
  assert.equal(bytes.readUInt32LE(0), 0x46546c67); assert.equal(bytes.readUInt32LE(4), 2); assert.equal(bytes.readUInt32LE(8), bytes.length);
  assert.equal(data.meshes.length, 18); assert.equal(meshes.length, 18); assert.equal(data.nodes.filter(node => node.mesh !== undefined).length, 18);
  assert.deepEqual(data.scenes[data.scene ?? 0].nodes.map(index => data.nodes[index].name).sort(), [...expectedRoots].sort());
  assert.deepEqual(model.children.map(nameOf).sort(), [...expectedRoots].sort());
  assert.equal(data.buffers.length, 1); assert.equal(data.buffers[0].uri, undefined);
  assert.equal(data.images.length, 1); assert.equal(data.images[0].uri, undefined);
  assert.equal((data.cameras ?? []).length, 0); assert.equal(data.extensions?.KHR_lights_punctual, undefined);
  assert.ok(bytes.length < 8 * 1024 * 1024, 'welcome GLB remains within an eight MiB audit ceiling');
  const roots = expectedRoots.map(name => {
    const root = nodes.get(name); assert.ok(root && !root.isMesh); assert.equal(root.parent, model);
    return { name, loaderName: root.name, position: root.position.toArray(), quaternion: root.quaternion.toArray(), scale: root.scale.toArray(), destination: root.userData.intro_destination, meshCount: root.children.filter(node => node.isMesh).length };
  });
  details.roots = roots;
  return { bytes: bytes.length, meshes: meshes.length, roots };
});
await check('all positions and unit normals are finite, with no collapsed or collinear triangle', () => {
  let triangles = 0, minimumArea = Infinity, minimumNormal = Infinity, maximumNormal = 0, microscopicTriangles = 0;
  const records = meshes.map(mesh => {
    const position = mesh.geometry.attributes.position, normal = mesh.geometry.attributes.normal, indices = mesh.geometry.index;
    assert.ok(position && normal && indices); assert.equal(position.count, normal.count); assert.equal(indices.count % 3, 0);
    let areaMin = Infinity, qualityMin = Infinity, tiny = 0;
    for (let i = 0; i < position.count; i++) {
      const p = new THREE.Vector3().fromBufferAttribute(position, i), n = new THREE.Vector3().fromBufferAttribute(normal, i);
      assert.ok([...p.toArray(), ...n.toArray()].every(Number.isFinite)); close(n.length(), 1, 2e-5);
      minimumNormal = Math.min(minimumNormal, n.length()); maximumNormal = Math.max(maximumNormal, n.length());
    }
    for (let i = 0; i < indices.count; i += 3) {
      const ids = [0, 1, 2].map(j => indices.getX(i + j)); ids.forEach(id => assert.ok(Number.isInteger(id) && id >= 0 && id < position.count));
      const [a, b, c] = ids.map(id => new THREE.Vector3().fromBufferAttribute(position, id));
      const ab = b.clone().sub(a), ac = c.clone().sub(a), bc = c.clone().sub(b);
      const area = ab.clone().cross(ac).length() * .5;
      const maximumEdgeSquared = Math.max(ab.lengthSq(), ac.lengthSq(), bc.lengthSq());
      // Scale-relative quality rejects true near-collinearity; absolute area
      // alone would misclassify the tiny but valid indicator-bevel corners.
      const quality = 2 * area / maximumEdgeSquared;
      assert.ok(area > 0 && Number.isFinite(area) && quality > 1e-8, `${nameOf(mesh)}: degenerate triangle ${i / 3}`);
      areaMin = Math.min(areaMin, area); qualityMin = Math.min(qualityMin, quality); if (area < 1e-12) tiny++;
    }
    triangles += indices.count / 3; minimumArea = Math.min(minimumArea, areaMin); microscopicTriangles += tiny;
    return { name: nameOf(mesh), vertices: position.count, triangles: indices.count / 3, minimumArea: areaMin, minimumRelativeArea: qualityMin, microscopicTrianglesBelow1eMinus12: tiny };
  });
  details.triangles = triangles;
  details.geometry = { triangles, minimumArea, normalLengthRange: [minimumNormal, maximumNormal], degenerateTriangles: 0, microscopicTriangles, records };
  return details.geometry;
});
await check('UV coordinates are finite and the actual screen plane covers the bitmap without collapsed UV triangles', () => {
  for (const mesh of meshes) {
    const uv = mesh.geometry.attributes.uv; assert.ok(uv); assert.equal(uv.count, mesh.geometry.attributes.position.count);
    for (const value of uv.array) assert.ok(Number.isFinite(value) && value >= -1e-6 && value <= 1 + 1e-6, `${nameOf(mesh)} UV range`);
  }
  const screen = nodes.get('terminal.lid.artwork'), uv = screen.geometry.attributes.uv, position = screen.geometry.attributes.position;
  assert.equal(position.count, 4); assert.equal(screen.geometry.index.count, 6);
  const corners = Array.from({ length: 4 }, (_, i) => [uv.getX(i), uv.getY(i)]);
  assert.deepEqual(corners.map(p => p.join(',')).sort(), ['0,0', '0,1', '1,0', '1,1']);
  const idx = screen.geometry.index; let coveredUVArea = 0;
  for (let i = 0; i < idx.count; i += 3) {
    const [a, b, c] = [0, 1, 2].map(j => corners[idx.getX(i + j)]);
    const area = Math.abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * .5;
    assert.ok(area > 0); coveredUVArea += area;
  }
  close(coveredUVArea, 1);
  return { uvSets: ['TEXCOORD_0'], screenCorners: corners, coveredUVArea };
});
await check('five distinct PBR colors include blue, vermilion and warm accents, plus a separate emissive screen bitmap', () => {
  assert.equal(data.materials.length, 6);
  const screen = data.materials.find(material => material.name === 'TERMINAL_OriginalScreenArtwork');
  assert.ok(screen?.emissiveTexture); assert.ok(screen.emissiveFactor.every(value => value > 0));
  const solids = data.materials.filter(material => material !== screen); assert.equal(solids.length, 5);
  const palette = solids.map(material => {
    const p = material.pbrMetallicRoughness, rgb = p.baseColorFactor.slice(0, 3);
    assert.ok(rgb.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
    assert.ok(p.roughnessFactor > 0 && p.roughnessFactor <= 1); assert.ok(p.metallicFactor >= 0 && p.metallicFactor <= 1);
    assert.equal(p.baseColorFactor[3], 1); assert.ok(!p.baseColorTexture);
    return { name: material.name, linearRGB: rgb, srgbHex: `#${new THREE.Color().setRGB(...rgb).getHexString()}`, metallic: p.metallicFactor, roughness: p.roughnessFactor };
  });
  assert.equal(new Set(palette.map(item => item.srgbHex)).size, 5);
  assert.ok(palette.some(item => item.linearRGB[2] > item.linearRGB[0] * 3), 'blue enamel is actually blue');
  assert.ok(palette.some(item => item.linearRGB[0] > item.linearRGB[2] * 6), 'warm accent is not grey');
  details.palette = palette;
  return { palette, screenMaterial: screen.name, emissiveFactor: screen.emissiveFactor };
});
await check('embedded screen PNG is byte-identical to the existing original artwork source', () => {
  const image = data.images[0], view = data.bufferViews[image.bufferView];
  assert.equal(image.mimeType, 'image/png'); assert.equal(image.name, 'screen-art-render');
  const imageBytes = binary.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength);
  assert.deepEqual([...imageBytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  const source = readFileSync(file(artworkPath)); assert.equal(sha(imageBytes), sha(source));
  const material = data.materials.find(item => item.name === 'TERMINAL_OriginalScreenArtwork');
  const tex = data.textures[material.emissiveTexture.index]; assert.equal(tex.source, 0);
  const screenNode = data.nodes.find(node => node.name === 'terminal.lid.artwork');
  assert.equal(data.materials[data.meshes[screenNode.mesh].primitives[0].material], material);
  details.texture = { source: artworkPath, embeddedImageIndex: 0, embeddedBufferView: image.bufferView, dimensions: [imageBytes.readUInt32BE(16), imageBytes.readUInt32BE(20)], bytes: imageBytes.length, sha256: sha(imageBytes), sourceSha256: sha(source), byteIdentical: true, pixelsIdentical: true };
  return details.texture;
});
await check('TerminalUnfold has the expected root rotation and lid translation tracks with finite ordered samples', () => {
  const clips = gltf.animations.filter(clip => clip.name === 'TerminalUnfold'); assert.equal(clips.length, 1);
  const clip = clips[0]; assert.equal(clip.tracks.length, 4);
  assert.ok(clip.duration > 1 && clip.duration < 3);
  const tracks = clip.tracks.map(track => {
    const binding = THREE.PropertyBinding.parseTrackName(track.name), node = THREE.PropertyBinding.findNode(model, binding.nodeName);
    assert.ok(node && expectedRoots.includes(nameOf(node))); assert.ok(['quaternion', 'position'].includes(binding.propertyName));
    assert.ok([...track.times, ...track.values].every(Number.isFinite));
    for (let i = 1; i < track.times.length; i++) assert.ok(track.times[i] > track.times[i - 1]);
    const width = binding.propertyName === 'quaternion' ? 4 : 3;
    assert.equal(track.values.length, track.times.length * width);
    if (width === 4) for (let i = 0; i < track.values.length; i += 4) close(Math.hypot(...track.values.slice(i, i + 4)), 1, 2e-5);
    return { root: nameOf(node), property: binding.propertyName, loaderTrack: track.name, keys: track.times.length, firstTime: track.times[0], lastTime: track.times.at(-1), first: [...track.values.slice(0, width)], last: [...track.values.slice(-width)] };
  });
  assert.deepEqual(tracks.map(track => `${track.root}/${track.property}`).sort(), ['seed.dial/quaternion', 'seed.lid/position', 'seed.lid/quaternion', 'seed.rail/quaternion']);
  details.animation = { name: clip.name, duration: clip.duration, tracks };
  return details.animation;
});
await check('real AnimationMixer first sample matches the default pose; opening and reverse seeks stay finite and restore exactly', () => {
  const clip = gltf.animations.find(item => item.name === 'TerminalUnfold'); assert.ok(clip);
  const mixer = new THREE.AnimationMixer(model), action = mixer.clipAction(clip);
  action.setLoop(THREE.LoopOnce, 1); action.clampWhenFinished = true; action.play(); action.paused = true;
  const maxMatrixError = () => { let error = 0; model.traverse(node => node.matrixWorld.elements.forEach((value, i) => { error = Math.max(error, Math.abs(value - original.get(node).matrix.elements[i])); })); return error; };
  const sample = time => { action.time = time; mixer.update(0); model.updateMatrixWorld(true); return boxOf(model); };
  sample(0); const initialMatrixError = maxMatrixError(); assert.ok(initialMatrixError < 2e-6, 'clip first pose differs from loaded default');
  const sampledBounds = [0, .25, .5, .75, 1, .4].map(progress => {
    const box = sample(progress * clip.duration), size = box.getSize(new THREE.Vector3());
    assert.ok([...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite));
    assert.ok(Math.max(...size.toArray()) < 5 && Math.min(...size.toArray()) > .05);
    for (const name of expectedRoots) close(nodes.get(name).scale.distanceTo(original.get(nodes.get(name)).scale), 0);
    return { progress, ...boxJSON(box) };
  });
  sample(0); close(maxMatrixError(), initialMatrixError);
  mixer.stopAllAction(); mixer.uncacheRoot(model); model.updateMatrixWorld(true);
  const restorationError = maxMatrixError(); assert.ok(restorationError < 1e-10);
  details.animationSampling = { initialMatrixError, restorationError, sampledBounds };
  return details.animationSampling;
});
await check('default and unfolded dimensions are practical and the exported file stayed unchanged throughout this audit', () => {
  const box = boxOf(model), size = box.getSize(new THREE.Vector3());
  assert.ok(size.x > 2 && size.x < 4 && size.y > .2 && size.y < 2 && size.z > 1 && size.z < 3);
  assert.equal(sha(readFileSync(file(modelPath))), modelSha); assert.equal(sha(readFileSync(file(blendPath))), blendSha);
  details.bounds = boxJSON(box);
  return { defaultBounds: details.bounds, sourceGlbUnchanged: true, sourceBlendUnchanged: true };
});

const report = { revision: 1, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Actual GLB/BIN attributes and material/image JSON; actual GLTFLoader and AnimationMixer for hierarchy and sampled pose. Only primitive material references are removed in memory for that CPU loader fixture, avoiding image or GPU initialization. Original material/bitmap bindings are verified separately from untouched bytes. No browser or visual-quality claim.',
  model: { path: modelPath, bytes: bytes.length, sha256: modelSha }, sourceBlend: { path: blendPath, bytes: blendBytes.length, sha256: blendSha },
  checks: results.length, passed: results.filter(result => result.status === 'passed').length, failed: results.filter(result => result.status === 'failed').length, results,
  limitations: ['Geometry checks do not verify browser shading, camera framing or visual appeal.', 'Very small nonzero indicator bevel triangles are reported separately; degeneracy uses scale-relative collinearity, not an arbitrary world-area threshold.'] };
const source = { asset: 'welcome-terminal-v1', checkedAt: report.checkedAt, type: 'Independent Blender-authored portable creative terminal',
  description: data.scenes[0].extras?.design_note,
  source_blend: blendPath, authoring_record: authorPath, runtime_glb: modelPath,
  provenance: { geometry: 'Authored in a dedicated WELCOME_TERMINAL_V1 Blender scene; editable base, lid, dial and rail carriers.',
    materials: 'Five original constant-factor PBR colors plus the project’s existing rendered screen artwork.',
    reused_bitmap: artworkPath, third_party_models_added: false, third_party_textures_added: false },
  coordinate_system: 'glTF/Three +Y up, metres; Blender source +Z up. Raw glTF node names with dots are preserved by GLTFLoader in userData.name.',
  roots: details.roots, mesh_count: meshes.length, material_count: data.materials.length, triangles: details.triangles,
  palette: details.palette, embedded_texture: details.texture, default_world_bounds: details.bounds,
  animation: details.animation, animation_initial_matrix_error: details.animationSampling?.initialMatrixError,
  file_bytes: { blend: blendBytes.length, glb: bytes.length }, sha256: { blend: blendSha, glb: modelSha, authoring_record: sha(readFileSync(file(authorPath))) },
  validation: { report: 'docs/validation/welcome-terminal-v1.json', checks: report.checks, passed: report.passed, failed: report.failed, passed_all: report.failed === 0, browser_visual_review: 'separate' } };
if (!process.argv.includes('--draft')) {
  writeFileSync(file('docs/validation/welcome-terminal-v1.json'), JSON.stringify(report, null, 2) + '\n');
  writeFileSync(file('public/models/welcome-terminal-v1.source.json'), JSON.stringify(source, null, 2) + '\n');
}
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, model: report.model, triangles: details.triangles, animation: details.animation, failures: results.filter(item => item.status === 'failed'), wroteReports: !process.argv.includes('--draft') }, null, 2));
if (report.failed) process.exitCode = 1;
