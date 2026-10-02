import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { bindIntroInput } from '../src/intro-input.js';

const file = name => new URL(`../${name}`, import.meta.url);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const modelPath = 'public/models/welcome-orbit-v1.glb';
const bytes = readFileSync(file(modelPath)), modelSha = hash(bytes);
const data = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString());
const introSource = readFileSync(file('src/cube-intro.js'), 'utf8');
const mainSource = readFileSync(file('src/main.js'), 'utf8');
const provenance = JSON.parse(readFileSync(file('public/models/welcome-orbit-v1.source.json')));
const names = ['welcome_base', 'welcome_ring_left', 'welcome_ring_right', 'welcome_core'];
const parse = async () => (await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')).scene;
const model = await parse(), meshes = [];
model.traverse(node => { if (node.isMesh) meshes.push(node); });
const boxJSON = box => ({ min: box.min.toArray(), max: box.max.toArray() });
const bounds = object => { object.updateWorldMatrix(true, true); return new THREE.Box3().setFromObject(object, true); };
const close = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
const results = [];
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.stack }); }
}

await check('small self-contained GLB needs no textures, external requests or decoder extensions', () => {
  assert.equal(bytes.readUInt32LE(0), 0x46546c67); assert.equal(bytes.readUInt32LE(4), 2);
  assert.equal(bytes.readUInt32LE(8), bytes.length); assert.ok(bytes.length < 1024 * 1024);
  assert.equal(data.buffers.length, 1); assert.equal(data.buffers[0].uri, undefined);
  assert.equal((data.images ?? []).length, 0); assert.equal((data.textures ?? []).length, 0);
  assert.equal((data.extensionsRequired ?? []).length, 0);
  const triangles = meshes.reduce((sum, mesh) => sum + (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3, 0);
  assert.ok(triangles > 0 && triangles < 10000);
  return { bytes: bytes.length, triangles, externalDependencies: 0 };
});
await check('real GLTFLoader produces four independently addressable sibling meshes and one primitive each', () => {
  assert.deepEqual(meshes.map(mesh => mesh.name).sort(), [...names].sort());
  assert.equal(data.meshes.length, 4);
  const records = names.map(name => {
    const node = model.getObjectByName(name); assert.ok(node.isMesh);
    assert.equal(node.parent, model); assert.equal(node.children.length, 0);
    assert.equal(node.userData.asset_id, name);
    const specification = data.nodes.find(item => item.name === name);
    assert.equal(data.meshes[specification.mesh].primitives.length, 1);
    return { name, vertices: node.geometry.attributes.position.count, triangles: node.geometry.index.count / 3 };
  });
  assert.equal(new Set(meshes.map(mesh => mesh.geometry)).size, 4);
  return { logicalParts: 4, renderableMeshes: meshes.length, records };
});
await check('finite Y-up bounds, original shared ring pivot and left/right sides agree with production motion axes', () => {
  const box = bounds(model), size = box.getSize(new THREE.Vector3());
  for (const value of [...box.min.toArray(), ...box.max.toArray()]) assert.ok(Number.isFinite(value) && Math.abs(value) < 2);
  assert.ok(size.x > 1 && size.y > 1 && size.z > .1 && Math.max(...size.toArray()) < 2);
  const parts = names.map(name => {
    const node = model.getObjectByName(name);
    close(node.quaternion.angleTo(new THREE.Quaternion()), 0); assert.deepEqual(node.scale.toArray(), [1, 1, 1]);
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(node.getWorldQuaternion(new THREE.Quaternion()));
    close(up.distanceTo(new THREE.Vector3(0, 1, 0)), 0);
    return { name, position: node.position.toArray(), quaternion: node.quaternion.toArray(), bounds: boxJSON(bounds(node)), localYInModel: up.toArray() };
  });
  const left = model.getObjectByName(names[1]), right = model.getObjectByName(names[2]);
  close(left.position.distanceTo(right.position), 0); close(left.position.y, .3);
  assert.ok(bounds(left).max.x < 0); assert.ok(bounds(right).min.x > 0);
  close(bounds(left).getSize(new THREE.Vector3()).z, .07);
  close(bounds(right).getSize(new THREE.Vector3()).z, .07);
  return { bounds: boxJSON(box), parts, ringPlane: 'XY', openingAxis: '+Y, vertical in the glTF model' };
});
await check('actual exported normals are unit, finite and aligned with nondegenerate triangle winding', () => {
  const records = meshes.map(mesh => {
    const position = mesh.geometry.attributes.position, normal = mesh.geometry.attributes.normal, indices = mesh.geometry.index;
    assert.equal(normal.count, position.count); assert.equal(indices.count % 3, 0);
    let minimumNormalLength = Infinity, maximumNormalLength = 0, minimumArea = Infinity, minimumFaceNormalDot = 1;
    for (let i = 0; i < position.count; i++) {
      const vertex = new THREE.Vector3().fromBufferAttribute(position, i), n = new THREE.Vector3().fromBufferAttribute(normal, i);
      assert.ok([...vertex.toArray(), ...n.toArray()].every(Number.isFinite)); close(n.length(), 1, 2e-5);
      minimumNormalLength = Math.min(minimumNormalLength, n.length()); maximumNormalLength = Math.max(maximumNormalLength, n.length());
    }
    for (let i = 0; i < indices.count; i += 3) {
      const ids = [0, 1, 2].map(j => indices.getX(i + j));
      ids.forEach(index => assert.ok(Number.isInteger(index) && index >= 0 && index < position.count));
      const [a, b, c] = ids.map(index => new THREE.Vector3().fromBufferAttribute(position, index));
      const face = b.sub(a).cross(c.sub(a)), area = face.length() * .5;
      assert.ok(area > 1e-10, `${mesh.name}: degenerate triangle ${i / 3}`);
      minimumArea = Math.min(minimumArea, area);
      const smoothNormal = ids.reduce((sum, index) => sum.add(new THREE.Vector3().fromBufferAttribute(normal, index)), new THREE.Vector3()).normalize();
      const dot = face.normalize().dot(smoothNormal); assert.ok(dot > .9, `${mesh.name}: face/vertex normal mismatch ${dot}`);
      minimumFaceNormalDot = Math.min(minimumFaceNormalDot, dot);
    }
    return { name: mesh.name, minimumNormalLength, maximumNormalLength, minimumArea, minimumFaceNormalDot, degenerates: 0 };
  });
  return { records };
});
await check('constant PBR materials and copper vertex colors survive real loading without texture or transmission dependencies', () => {
  const materials = [...new Set(meshes.map(mesh => mesh.material))]; assert.equal(materials.length, 3);
  for (const material of materials) {
    assert.ok(material.isMeshStandardMaterial); assert.equal(material.opacity, 1); assert.equal(material.transparent, false);
    assert.ok(material.roughness > 0 && material.roughness <= 1); assert.ok(material.metalness >= 0 && material.metalness <= 1);
    for (const [key, value] of Object.entries(material)) assert.ok(!value?.isTexture, `${material.name}: unexpected texture ${key}`);
    assert.ok(!material.transmission);
  }
  for (const name of names.slice(1, 3)) {
    const mesh = model.getObjectByName(name), colors = mesh.geometry.attributes.color;
    assert.ok(mesh.material.vertexColors && colors); assert.equal(colors.count, mesh.geometry.attributes.position.count);
    const distinct = new Set();
    for (let i = 0; i < colors.count; i++) {
      const values = [colors.getX(i), colors.getY(i), colors.getZ(i)];
      assert.ok(values.every(value => Number.isFinite(value) && value >= 0 && value <= 1)); distinct.add(values.join(','));
    }
    assert.ok(distinct.size >= 2, `${name}: copper endcap has no distinct vertex color`);
  }
  return { materials: materials.map(material => ({ name: material.name, metalness: material.metalness, roughness: material.roughness, vertexColors: material.vertexColors })) };
});
await check('authored source evidence matches the actual GLB and Blender file', () => {
  assert.equal(provenance.sha256.glb, modelSha);
  assert.equal(provenance.sha256.blend, hash(readFileSync(file(provenance.source_blend))));
  assert.equal(provenance.file_bytes.glb, bytes.length);
  const box = bounds(model);
  ['min', 'max'].forEach(key => box[key].toArray().forEach((value, index) => close(value, provenance.gltf_world_bbox[key][index])));
  return { sourceBlend: provenance.source_blend, sourceSha256: provenance.sha256.blend, provenance: 'Original procedural geometry and constant-factor PBR; no third-party assets declared.' };
});

// Execute the production controller with real Three objects and the actual GLB.
// Only DOM, timeline scheduling and the GPU-only PMREM operation are substituted.
function fixture(welcomeModel) {
  const timelines = [], reflection = { texture: new THREE.Texture(), disposals: 0, dispose() { this.disposals++; } };
  const gpu = { probeGeneration: 0, probeDisposals: 0, environmentDisposals: 0 };
  class Environment extends THREE.Scene { dispose() { gpu.environmentDisposals++; } }
  class Generator {
    fromScene() { gpu.probeGeneration++; return reflection; }
    dispose() { gpu.probeDisposals++; }
  }
  const fakeGsap = { set() {}, timeline() {
    const timeline = { steps: [], to(target, vars) { this.steps.push({ target, vars }); return this; }, set() { return this; }, call() { return this; }, kill() {}, progress() { return 0; } };
    timelines.push(timeline); return timeline;
  } };
  const classes = new Set(), media = new EventTarget(), view = new EventTarget();
  Object.assign(view, { innerWidth: 1440, innerHeight: 900, matchMedia: () => media });
  const doc = { defaultView: view, body: { style: { overflow: 'auto' }, classList: { add: (...values) => values.forEach(v => classes.add(v)), remove: (...values) => values.forEach(v => classes.delete(v)) } }, createTreeWalker: () => ({ nextNode: () => false }) };
  const elements = new Map(), element = new EventTarget();
  const child = () => Object.assign(new EventTarget(), { ownerDocument: doc, textContent: '', setAttribute() {}, querySelectorAll: () => [], disabled: false });
  Object.assign(element, { ownerDocument: doc, dataset: {}, querySelector: selector => { if (!elements.has(selector)) elements.set(selector, child()); return elements.get(selector); } });
  const createIntro = vm.runInNewContext(introSource.replace(/^import .*;\n/gm, '').replace('export function createCubeIntro', 'function createCubeIntro') + '\ncreateCubeIntro;', {
    THREE: { ...THREE, PMREMGenerator: Generator }, gsap: fakeGsap, RoomEnvironment: Environment, bindIntroInput,
  });
  const scene = new THREE.Scene(), room = new THREE.Group(), exteriorModel = new THREE.Group(), atmosphereGroup = new THREE.Group();
  const shader = () => new THREE.ShaderMaterial({ uniforms: {}, fragmentShader: '#include <colorspace_fragment>' });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), shader()), sky = new THREE.Mesh(new THREE.SphereGeometry(3), shader());
  atmosphereGroup.add(sky, new THREE.Group()); scene.add(room, exteriorModel, ground, atmosphereGroup);
  const camera = new THREE.PerspectiveCamera(35, 1.6, .1, 1000), controls = { target: new THREE.Vector3(), enabled: true };
  const endPose = { position: new THREE.Vector3(12, 10, 16), target: new THREE.Vector3(0, 2, 0) };
  const roomEntry = { updates: 0, restores: 0, update() { this.updates++; }, restore() { this.restores++; }, appendTo: () => 5, getState: () => ({}) };
  const counts = { start: 0, complete: 0 }, disposals = new Map(), owned = new Set();
  welcomeModel.traverse(node => { if (node.isMesh) { owned.add(node.geometry); owned.add(node.material); } });
  owned.forEach(resource => { disposals.set(resource, 0); resource.addEventListener('dispose', () => disposals.set(resource, disposals.get(resource) + 1)); });
  const intro = createIntro({ scene, renderer: {}, welcomeModel, room, roomEntry, exteriorModel, atmosphere: { group: atmosphereGroup, sky }, ground, camera, controls,
    bounds: new THREE.Box3(new THREE.Vector3(-5, 0, -4), new THREE.Vector3(5, 5, 4)), element, getEndPose: () => endPose,
    onStart: () => { counts.start++; }, onComplete: () => { counts.complete++; controls.enabled = true; } });
  intro.ready(); element.querySelector('.intro-enter').dispatchEvent(new Event('click'));
  const motion = timelines.flatMap(timeline => timeline.steps).find(step => 'appear' in step.target && 'unfold' in step.target)?.target;
  assert.ok(motion, 'production timeline exposes the actual animated motion object');
  return { intro, motion, view, model: welcomeModel, scene, camera, controls, endPose, roomEntry, counts, disposals, reflection, gpu, element, doc };
}
await check('production controller opens the actual independent rings around Y without drift and lowers its core correctly', async () => {
  const actual = await parse(), nativeSize = bounds(actual).getSize(new THREE.Vector3());
  const originals = new Map(names.map(name => { const node = actual.getObjectByName(name); return [name, { position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone() }]; }));
  const f = fixture(actual), samples = [];
  try {
    for (const opening of [0, .25, .5, .75, 1, .5]) {
      Object.assign(f.motion, { appear: 1, shift: 1, travel: .5, unfold: opening, morph: opening * .8 }); f.intro.update(); actual.updateWorldMatrix(true, true);
      for (const [name, sign] of [['welcome_ring_left', -1], ['welcome_ring_right', 1]]) {
        const node = actual.getObjectByName(name), original = originals.get(name);
        close(node.position.x - original.position.x, sign * nativeSize.x * .19 * opening);
        close(node.position.y, original.position.y); close(node.position.z, original.position.z);
        const expected = original.quaternion.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), sign * opening * .65));
        close(node.quaternion.angleTo(expected), 0); close(node.scale.distanceTo(original.scale), 0);
      }
      const core = actual.getObjectByName('welcome_core'), original = originals.get('welcome_core');
      close(core.position.y, original.position.y - nativeSize.y * .26 * opening);
      close(core.scale.x, original.scale.x * Math.max(.00001, 1 - opening));
      const box = bounds(actual); assert.ok([...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite));
      samples.push({ opening, leftPosition: actual.getObjectByName('welcome_ring_left').position.toArray(), coreY: core.position.y });
    }
    const base = actual.getObjectByName('welcome_base'); close(base.position.distanceTo(originals.get('welcome_base').position), 0);
    return { samples, ringTurnAtFullOpeningRadians: [-.65, .65], axis: 'local +Y = glTF up; ring plane is XY', productionControllerExecuted: true };
  } finally { f.intro.skip(); f.intro.dispose(); }
});
await check('production resize and skip restore exact native camera and release welcome resources only once', async () => {
  const f = fixture(await parse());
  Object.assign(f.motion, { appear: 1, travel: .55, unfold: .4, morph: .25 }); f.intro.update();
  f.view.innerWidth = 390; f.view.innerHeight = 844; f.camera.aspect = 390 / 844; f.intro.resize();
  assert.ok(f.camera.position.toArray().every(Number.isFinite));
  f.intro.skip(); f.intro.skip(); f.intro.update(); f.intro.dispose(); f.intro.dispose();
  assert.equal(f.counts.start, 1); assert.equal(f.counts.complete, 1);
  close(f.camera.position.distanceTo(f.endPose.position), 0); close(f.controls.target.distanceTo(f.endPose.target), 0);
  assert.equal(f.controls.enabled, true); assert.equal(f.doc.body.style.overflow, 'auto');
  assert.equal(f.scene.getObjectByName('Welcome orbital sculpture · temporary'), undefined);
  assert.equal(f.reflection.disposals, 1); assert.deepEqual([...f.disposals.values()], [...f.disposals.values()].map(() => 1));
  assert.deepEqual(f.gpu, { probeGeneration: 1, probeDisposals: 1, environmentDisposals: 1 });
  return { startCount: f.counts.start, completeCount: f.counts.complete, disposedGeometriesAndMaterials: f.disposals.size, resourceDisposals: [...f.disposals.values()], reflectionTargetDisposals: f.reflection.disposals };
});
await check('main loads the checked GLB before the controller and prewarms its materials before ready', () => {
  const load = mainSource.indexOf("new GLTFLoader().loadAsync('/models/welcome-orbit-v1.glb')"), create = mainSource.indexOf('cubeIntro = createCubeIntro('), ready = mainSource.indexOf('cubeIntro.ready()');
  assert.ok(load >= 0 && create > load && ready > create);
  assert.match(mainSource.slice(create, ready), /renderer, welcomeModel: welcomeGltf\.scene/);
  assert.match(mainSource.slice(create, ready), /await renderer\.compileAsync\(scene, camera\)/);
  assert.match(mainSource.slice(create, ready), /renderer\.render\(scene, camera\)/);
  assert.equal(hash(readFileSync(file(modelPath))), modelSha, 'model did not change during validation');
  return { url: '/models/welcome-orbit-v1.glb', modelSha256: modelSha, inspection: 'Main loading order and wiring; shader compilation itself is not run by this CPU test.' };
});

const report = {
  revision: 1, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Actual GLB loaded by real GLTFLoader; vertex/index/normal/material and authored-pivot checks. Production intro controller runs in a VM with real Three transforms and real input binding; DOM, timeline scheduling and GPU PMREM are controlled substitutes. No browser, GPU, rendered appearance or performance claim.',
  model: { path: modelPath, sha256: modelSha, bytes: bytes.length },
  sourceSha256: Object.fromEntries(['src/cube-intro.js', 'src/main.js', 'src/room-entry.js', 'src/intro-input.js', modelPath, 'assets/blender/welcome-orbit-v1.blend'].map(path => [path, hash(readFileSync(file(path)))])),
  checks: results.length, passed: results.filter(item => item.status === 'passed').length, failed: results.filter(item => item.status === 'failed').length, results,
};
if (process.argv.includes('--write-report')) writeFileSync(file('docs/validation/welcome-orbit-v1.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, model: report.model, failures: results.filter(item => item.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
