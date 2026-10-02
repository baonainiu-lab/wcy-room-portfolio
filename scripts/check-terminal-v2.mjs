import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createResidentTerminal } from '../src/resident-terminal.js';

// Usage: node scripts/check-terminal-v2.mjs [model.glb] [--report path.json] [--max-mib 8]
// Mesh/material counts are observations, not compatibility requirements.
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2), reportFlag = args.indexOf('--report');
const modelArg = args[0] && !args[0].startsWith('--') ? args[0] : 'public/models/welcome-terminal-v2.glb';
const modelPath = resolve(project, modelArg), bytes = readFileSync(modelPath);
const budgetFlag = args.indexOf('--max-mib'), budgetMiB = budgetFlag < 0 ? 8 : Number(args[budgetFlag + 1]);
assert.ok(Number.isFinite(budgetMiB) && budgetMiB > 0, '--max-mib requires a positive budget');
const sha = value => createHash('sha256').update(value).digest('hex');
const initialSha = sha(bytes), expectedRoots = ['seed.base', 'seed.lid', 'seed.dial', 'seed.rail'];
const checks = [], metrics = {};
const close = (a, b, epsilon = 2e-6) => assert.ok(Math.abs(a - b) <= epsilon, `${a} differs from ${b}`);
const nameOf = node => node.userData.name ?? node.name;
const pose = node => ({ position: node.position.toArray(), quaternion: node.quaternion.toArray(), scale: node.scale.toArray() });
const boxOf = node => { node.updateWorldMatrix(true, true); return new THREE.Box3().setFromObject(node, true); };
const boxJSON = box => ({ min: box.min.toArray(), max: box.max.toArray(), size: box.getSize(new THREE.Vector3()).toArray() });
async function check(name, run) {
  try { checks.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { checks.push({ check: name, status: 'failed', error: error.stack }); }
}
function parseContainer(input) {
  assert.equal(input.readUInt32LE(0), 0x46546c67, 'GLB magic');
  assert.equal(input.readUInt32LE(4), 2, 'glTF version');
  assert.equal(input.readUInt32LE(8), input.length, 'declared file length');
  const chunks = [];
  for (let offset = 12; offset < input.length;) {
    assert.ok(offset + 8 <= input.length, 'complete chunk header');
    const length = input.readUInt32LE(offset), type = input.readUInt32LE(offset + 4);
    assert.equal(length % 4, 0, 'aligned GLB chunk');
    assert.ok(offset + 8 + length <= input.length, 'complete GLB chunk');
    chunks.push({ type, bytes: input.subarray(offset + 8, offset + 8 + length) });
    offset += length + 8;
  }
  assert.equal(chunks[0]?.type, 0x4e4f534a, 'JSON must be first');
  const binary = chunks.filter(chunk => chunk.type === 0x004e4942);
  assert.equal(binary.length, 1, 'one embedded binary buffer');
  return { data: JSON.parse(chunks[0].bytes.toString()), binary: binary[0].bytes };
}
async function cpuLoad(input) {
  const { data } = parseContainer(input), loader = new GLTFLoader();
  // Preserve real PBR materials and bindings. Only browser image decode is
  // replaced; embedded image bytes and signatures are audited separately.
  loader.register(() => ({ name: data.extensionsUsed?.includes('KHR_texture_basisu') ? 'KHR_texture_basisu' : 'CPU_TERMINAL_IMAGE_DECODE', loadTexture(index) {
    const texture = new THREE.Texture(); texture.name = data.textures?.[index]?.name ?? `cpu-image-${index}`;
    texture.userData.cpuImageDecodeOmitted = true; return Promise.resolve(texture);
  } }));
  return loader.parseAsync(input.buffer.slice(input.byteOffset, input.byteOffset + input.byteLength), '');
}
const { data, binary } = parseContainer(bytes), gltf = await cpuLoad(bytes), model = gltf.scene;
const nodes = new Map(), meshes = [];
model.traverse(node => { assert.ok(!nodes.has(nameOf(node)), `duplicate node name ${nameOf(node)}`); nodes.set(nameOf(node), node); if (node.isMesh) meshes.push(node); });
const original = new Map();
model.updateMatrixWorld(true);
model.traverse(node => original.set(node, { ...pose(node), matrix: node.matrixWorld.clone() }));
const matrixError = () => {
  let error = 0;
  model.traverse(node => node.matrixWorld.elements.forEach((value, index) => { error = Math.max(error, Math.abs(value - original.get(node).matrix.elements[index])); }));
  return error;
};

await check('self-contained asset retains four independently animated carriers and complete child ownership', () => {
  assert.deepEqual(model.children.map(nameOf).sort(), [...expectedRoots].sort());
  assert.ok(meshes.length > 0);
  for (const seed of expectedRoots) {
    const root = nodes.get(seed); assert.ok(root && !root.isMesh && root.parent === model, `${seed} must remain a scene-root carrier`);
    let descendants = 0; root.traverse(node => { if (node.isMesh) descendants++; });
    assert.ok(descendants > 0, `${seed} cannot be empty`);
  }
  for (const mesh of meshes) {
    let carrier = mesh;
    while (carrier.parent && carrier.parent !== model) carrier = carrier.parent;
    assert.ok(expectedRoots.includes(nameOf(carrier)), `${nameOf(mesh)} has no seed owner`);
  }
  assert.equal(data.buffers?.length, 1); assert.equal(data.buffers[0].uri, undefined);
  assert.ok(data.buffers[0].byteLength <= binary.length);
  assert.equal((data.cameras ?? []).length, 0); assert.equal(data.extensions?.KHR_lights_punctual, undefined);
  assert.ok(bytes.length < budgetMiB * 1024 * 1024, `retain explicit ${budgetMiB} MiB welcome-asset budget`);
  metrics.counts = { meshNodes: meshes.length, meshDefinitions: data.meshes.length, materials: data.materials?.length ?? 0, images: data.images?.length ?? 0 };
  return { bytes: bytes.length, ...metrics.counts, roots: expectedRoots };
});

await check('geometry has finite positions, unit normals and nondegenerate triangles', () => {
  let triangles = 0, minimumRelativeArea = Infinity;
  for (const mesh of meshes) {
    const positions = mesh.geometry.attributes.position, normals = mesh.geometry.attributes.normal, indices = mesh.geometry.index;
    assert.ok(positions && normals); assert.equal(positions.count, normals.count);
    for (let i = 0; i < positions.count; i++) {
      const point = new THREE.Vector3().fromBufferAttribute(positions, i), normal = new THREE.Vector3().fromBufferAttribute(normals, i);
      assert.ok([...point.toArray(), ...normal.toArray()].every(Number.isFinite), `${nameOf(mesh)} finite vertices/normals`);
      close(normal.length(), 1, 2e-5);
    }
    const count = indices?.count ?? positions.count; assert.equal(count % 3, 0);
    for (let i = 0; i < count; i += 3) {
      const ids = [0, 1, 2].map(delta => indices ? indices.getX(i + delta) : i + delta);
      ids.forEach(id => assert.ok(Number.isInteger(id) && id >= 0 && id < positions.count));
      const [a, b, c] = ids.map(id => new THREE.Vector3().fromBufferAttribute(positions, id));
      const ab = b.clone().sub(a), ac = c.clone().sub(a), bc = c.clone().sub(b);
      const twiceArea = ab.clone().cross(ac).length(), longestEdgeSquared = Math.max(ab.lengthSq(), ac.lengthSq(), bc.lengthSq());
      const quality = twiceArea / longestEdgeSquared;
      assert.ok(Number.isFinite(quality) && quality > 1e-8, `${nameOf(mesh)} triangle ${i / 3} degenerates`);
      minimumRelativeArea = Math.min(minimumRelativeArea, quality);
    }
    triangles += count / 3;
    for (const material of [].concat(mesh.material)) {
      if (!['map', 'emissiveMap', 'normalMap', 'roughnessMap', 'metalnessMap'].some(key => material[key])) continue;
      const uv = mesh.geometry.attributes.uv;
      assert.ok(uv && uv.count === positions.count, `${nameOf(mesh)} textured mesh requires valid UVs`);
      assert.ok([...uv.array].every(Number.isFinite));
    }
  }
  metrics.triangles = triangles;
  return { triangles, minimumRelativeArea };
});

await check('PBR palette and embedded image bindings remain valid without fixed material counts', () => {
  const images = (data.images ?? []).map((image, index) => {
    assert.equal(image.uri, undefined, `image ${index} must be embedded`);
    const view = data.bufferViews?.[image.bufferView]; assert.ok(view && (view.buffer ?? 0) === 0);
    assert.ok((view.byteOffset ?? 0) >= 0 && view.byteLength > 0 && (view.byteOffset ?? 0) + view.byteLength <= binary.length);
    const content = binary.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength);
    let dimensions = null;
    if (image.mimeType === 'image/png') {
      assert.deepEqual([...content.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
      dimensions = [content.readUInt32BE(16), content.readUInt32BE(20)]; assert.ok(dimensions.every(value => value > 0));
    } else if (image.mimeType === 'image/jpeg') assert.equal(content.readUInt16BE(0), 0xffd8);
    else assert.ok(['image/webp', 'image/ktx2'].includes(image.mimeType), `unknown image type ${image.mimeType}`);
    return { index, name: image.name, type: image.mimeType, bytes: content.length, dimensions, sha256: sha(content) };
  });
  const validTexture = info => {
    if (!info) return;
    const texture = data.textures?.[info.index]; assert.ok(texture, 'material texture reference resolves');
    const source = texture.source ?? texture.extensions?.KHR_texture_basisu?.source ?? texture.extensions?.EXT_texture_webp?.source;
    assert.ok(Number.isInteger(source) && images[source], 'texture image reference resolves');
  };
  const palette = (data.materials ?? []).map(material => {
    const pbr = material.pbrMetallicRoughness ?? {}, color = pbr.baseColorFactor ?? [1, 1, 1, 1];
    assert.equal(color.length, 4); assert.ok(color.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
    for (const value of [pbr.roughnessFactor ?? 1, pbr.metallicFactor ?? 1]) assert.ok(Number.isFinite(value) && value >= 0 && value <= 1);
    for (const info of [pbr.baseColorTexture, pbr.metallicRoughnessTexture, material.emissiveTexture, material.normalTexture, material.occlusionTexture]) validTexture(info);
    if (material.emissiveFactor) assert.ok(material.emissiveFactor.every(value => Number.isFinite(value) && value >= 0));
    return { name: material.name, color, metallic: pbr.metallicFactor ?? 1, roughness: pbr.roughnessFactor ?? 1 };
  });
  const mappedPalette = data.materials.filter(material => material.extras?.v3_finish);
  if (mappedPalette.length) {
    // V3 stores the original palette in a real color atlas, so neutral factors
    // are expected. Pixel colors and V2 triangle correspondence have their own
    // verify-terminal-v3.py audit; this check verifies real UV1 shader bindings.
    assert.equal(mappedPalette.length, 6);
    for (const material of mappedPalette) for (const info of [material.pbrMetallicRoughness.baseColorTexture,
      material.pbrMetallicRoughness.metallicRoughnessTexture, material.normalTexture]) {
      assert.ok(info); assert.equal(info.texCoord, 1); validTexture(info);
    }
  } else {
    assert.ok(palette.some(item => item.color[2] > item.color[0] * 3), 'existing blue enamel family remains blue');
    assert.ok(palette.some(item => item.color[0] > item.color[2] * 6), 'existing orange accent family remains warm');
  }
  const screen = data.materials.find(material => material.emissiveTexture && material.emissiveFactor?.some(value => value > 0));
  assert.ok(screen, 'terminal screen keeps actual emissive artwork');
  return { palette, images, emissiveScreen: screen.name };
});

await check('native unfold clip only targets supported seed transforms and deterministic seeks restore the original pose', () => {
  const clips = gltf.animations.filter(clip => clip.name === 'TerminalUnfold'); assert.equal(clips.length, 1);
  const clip = clips[0]; assert.ok(clip.duration > 0 && Number.isFinite(clip.duration)); assert.ok(clip.tracks.length > 0);
  const tracks = clip.tracks.map(track => {
    const binding = THREE.PropertyBinding.parseTrackName(track.name), node = THREE.PropertyBinding.findNode(model, binding.nodeName);
    assert.ok(node && expectedRoots.includes(nameOf(node)), `${track.name} violates intro seed binding`);
    assert.ok(['position', 'quaternion', 'scale'].includes(binding.propertyName));
    assert.ok([...track.times, ...track.values].every(Number.isFinite));
    for (let i = 1; i < track.times.length; i++) assert.ok(track.times[i] > track.times[i - 1]);
    const width = binding.propertyName === 'quaternion' ? 4 : 3;
    assert.equal(track.getValueSize(), width);
    if (width === 4) for (let i = 0; i < track.values.length; i += 4) close(Math.hypot(...track.values.slice(i, i + 4)), 1, 2e-5);
    return { root: nameOf(node), property: binding.propertyName, keys: track.times.length };
  });
  const mixer = new THREE.AnimationMixer(model), action = mixer.clipAction(clip);
  action.setLoop(THREE.LoopOnce, 1); action.clampWhenFinished = true; action.play(); action.paused = true;
  const sample = fraction => { action.time = clip.duration * fraction; mixer.update(0); return boxOf(model); };
  sample(0); assert.ok(matrixError() < 2e-6, 'default authored pose must match first animation frame');
  const initial = boxOf(model), span = initial.getSize(new THREE.Vector3()).length(), samples = [];
  for (let i = 0; i <= 60; i++) {
    const box = sample(i / 60), size = box.getSize(new THREE.Vector3());
    assert.ok([...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite));
    assert.ok(size.toArray().every(value => value > 0)); assert.ok(size.length() < span * 3, 'opening envelope does not explode');
    model.traverse(node => assert.ok(node.scale.toArray().every(value => value > 0 && Number.isFinite(value)), 'no inverted/zero scale during opening'));
    if (i % 15 === 0) samples.push({ fraction: i / 60, ...boxJSON(box) });
  }
  const firstMiddle = boxJSON(sample(.43)); sample(.91); assert.deepEqual(boxJSON(sample(.43)), firstMiddle, 'absolute seeks are deterministic');
  sample(0); assert.ok(matrixError() < 2e-6);
  mixer.stopAllAction(); mixer.uncacheRoot(model); model.updateMatrixWorld(true); assert.ok(matrixError() < 1e-10, 'animation releases exact original pose');
  metrics.animation = { duration: clip.duration, tracks, sampledBounds: samples };
  return metrics.animation;
});

await check('actual resident placement fits the desk, retains independent controls and releases only owned resources', async () => {
  const room = (await cpuLoad(readFileSync(resolve(project, 'public/models/orbital-atelier-v16.glb')))).scene;
  const scene = new THREE.Scene(); scene.add(room);
  let asset; room.traverse(node => { if (node.userData.asset_id === 'folding_drawing_terminal') asset = node; });
  assert.ok(asset); const oldChildren = [...asset.children], oldPose = pose(asset), resources = new Map(), roomResources = new Map();
  const track = (root, registry) => root.traverse(node => {
    if (!node.isMesh) return;
    for (const resource of [node.geometry, ...[].concat(node.material), ...[].concat(node.material).flatMap(material => Object.values(material).filter(value => value?.isTexture))]) {
      if (registry.has(resource)) continue; registry.set(resource, 0); resource.addEventListener('dispose', () => registry.set(resource, registry.get(resource) + 1));
    }
  });
  track(model, resources); track(room, roomResources);
  let reflectionDisposals = 0;
  class Generator { fromScene() { return { texture: new THREE.Texture(), dispose() { reflectionDisposals++; } }; } dispose() {} }
  const resident = createResidentTerminal({ THREE: { ...THREE, PMREMGenerator: Generator }, renderer: {}, room, welcomeGltf: gltf });
  try {
    resident.attachHome(); const state = resident.getState(), box = boxOf(resident.carrier);
    for (const [index, axis] of ['x', 'y', 'z'].entries()) {
      assert.ok(box.min[axis] >= state.originalBounds.min[index] - 1e-6, `${axis} minimum exceeds resident envelope`);
      assert.ok(box.max[axis] <= state.originalBounds.max[index] + 1e-6, `${axis} maximum exceeds resident envelope`);
    }
    // Independently measure a denser grid than the production placement's
    // nine probes, so new feet/rims cannot silently inherit a false clearance.
    let desk; room.traverse(node => { if (node.userData.asset_id === 'furniture.desk') desk = node; });
    assert.ok(desk); const deskBox = boxOf(desk), ray = new THREE.Raycaster();
    const normal = new THREE.Vector3(), normalMatrix = new THREE.Matrix3(), supportHeights = [];
    for (let ix = 0; ix <= 6; ix++) for (let iz = 0; iz <= 6; iz++) {
      ray.set(new THREE.Vector3(THREE.MathUtils.lerp(box.min.x, box.max.x, ix / 6), deskBox.max.y + .1,
        THREE.MathUtils.lerp(box.min.z, box.max.z, iz / 6)), new THREE.Vector3(0, -1, 0));
      const hit = ray.intersectObject(desk, true).find(item => {
        normalMatrix.getNormalMatrix(item.object.matrixWorld);
        return item.face && normal.copy(item.face.normal).applyNormalMatrix(normalMatrix).y > .5;
      });
      if (hit) supportHeights.push(hit.point.y);
    }
    assert.ok(supportHeights.length > 20, 'most of terminal footprint has real desk support');
    const independentlyMeasuredSurface = Math.max(...supportHeights);
    close(box.min.y, independentlyMeasuredSurface + .003, 2e-6);
    assert.ok(state.support.samples.length > 0); assert.deepEqual(pose(asset), oldPose);
    const interactionParts = []; model.traverse(node => { if (node.userData.asset_id) interactionParts.push(node.userData.asset_id); });
    assert.deepEqual(interactionParts.sort(), ['terminal_dial', 'terminal_lid', 'terminal_rail']);
    const world = resident.carrier.matrixWorld.clone(), homePose = pose(resident.carrier);
    resident.detachForIntro(scene); resident.carrier.updateWorldMatrix(true, true);
    world.elements.forEach((value, index) => close(value, resident.carrier.matrixWorld.elements[index]));
    resident.carrier.position.set(2, 8, 5); resident.carrier.scale.setScalar(3); resident.attachHome();
    assert.deepEqual(pose(resident.carrier), homePose); assert.equal(resident.carrier.parent, asset);
    for (const dayMix of [0, .25, .5, .75, 1]) for (const introLight of [0, .5, 1]) {
      resident.setDayMix(dayMix); resident.setIntroLight(introLight);
      model.traverse(node => { if (node.isMesh) for (const material of [].concat(node.material)) {
        assert.ok(material.envMap?.isTexture); assert.ok(Number.isFinite(material.envMapIntensity) && material.envMapIntensity > 0);
        assert.ok(Number.isFinite(material.emissiveIntensity) && material.emissiveIntensity >= 0);
      } });
    }
    assert.ok([...resources.values()].every(count => count === 0), 'landing never disposes resident GLB resources');
    metrics.resident = { bounds: state.finalBounds, originalBounds: state.originalBounds, support: state.support,
      independentSupport: { samples: supportHeights.length, surfaceHeight: independentlyMeasuredSurface, clearance: box.min.y - independentlyMeasuredSurface },
      drawCallDelta: state.drawCallDelta, triangles: state.triangles };
  } finally { resident.dispose(); resident.dispose(); }
  assert.deepEqual(asset.children, oldChildren); assert.deepEqual(pose(asset), oldPose);
  assert.ok([...roomResources.values()].every(count => count === 0), 'shared room resources remain intact');
  assert.ok([...resources.values()].every(count => count === 1), 'owned GLB resources dispose exactly once');
  assert.equal(reflectionDisposals, 1);
  return metrics.resident;
});

assert.equal(sha(readFileSync(modelPath)), initialSha, 'validation must not modify the asset');
gsap.ticker.sleep();
const report = {
  checkedAt: new Date().toISOString(), model: relative(project, modelPath), bytes: bytes.length, sha256: initialSha,
  runtime: process.version, threeRevision: THREE.REVISION, checks, metrics,
  passed: checks.filter(item => item.status === 'passed').length, failed: checks.filter(item => item.status === 'failed').length,
  methodology: 'Actual GLTFLoader geometry, hierarchy, PBR JSON and AnimationMixer; production resident-terminal placement/disposal. Browser image decode and PMREM GPU rendering are substituted. No visual-quality, collision-free-surface or FPS claim.',
};
if (reportFlag >= 0) {
  assert.ok(args[reportFlag + 1], '--report requires an output filename');
  const reportPath = resolve(project, args[reportFlag + 1]); mkdirSync(dirname(reportPath), { recursive: true });
  writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({ model: report.model, passed: report.passed, failed: report.failed, metrics: { ...metrics.counts, triangles: metrics.triangles, animationSeconds: metrics.animation?.duration, drawCallDelta: metrics.resident?.drawCallDelta }, failures: checks.filter(item => item.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
