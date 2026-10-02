import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import gsap from 'gsap';
import { createHomepageRoom } from '../src/homepage-room.js';

// Real Three model graphs and mathematics; only DOM/WebGL delivery is faked.
// No image decode is needed to verify resource sharing and silhouette fitting.
const results = [];
const close = (a, b, message, epsilon = 1e-9) => assert.ok(Math.abs(a - b) <= epsilon, `${message}: ${a} versus ${b}`);
const pose = node => [...node.position.toArray(), ...node.quaternion.toArray(), ...node.scale.toArray()];
function fixture() {
  const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
  const modelPath = main.match(/loader\.loadAsync\('([^']+\.glb)'/)?.[1];
  assert.ok(modelPath);
  const glb = readFileSync(new URL(`../public${modelPath}`, import.meta.url));
  const end = 20 + glb.readUInt32LE(12), spec = JSON.parse(glb.subarray(20, end)), binary = glb.subarray(end + 8);
  const types = { 5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
  function read(index) {
    const a = spec.accessors[index], v = spec.bufferViews[a.bufferView], Type = types[a.componentType];
    assert.ok(Type && !a.sparse && !v.byteStride);
    const width = a.type === 'VEC3' ? 3 : 1;
    return new THREE.BufferAttribute(new Type(binary.buffer, binary.byteOffset + (v.byteOffset || 0) + (a.byteOffset || 0), a.count * width), width);
  }
  const materials = spec.materials.map(data => new THREE.MeshBasicMaterial({ name: data.name, map: new THREE.Texture() }));
  const nodes = spec.nodes.map(data => {
    const node = new THREE.Group(); node.name = data.name || ''; node.userData = { ...data.extras };
    if (data.matrix) { node.matrix.fromArray(data.matrix); node.matrix.decompose(node.position, node.quaternion, node.scale); }
    else {
      if (data.translation) node.position.fromArray(data.translation);
      if (data.rotation) node.quaternion.fromArray(data.rotation);
      if (data.scale) node.scale.fromArray(data.scale);
    }
    if (data.mesh !== undefined) for (const primitive of spec.meshes[data.mesh].primitives) {
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', read(primitive.attributes.POSITION));
      if (primitive.indices !== undefined) geometry.setIndex(read(primitive.indices));
      node.add(new THREE.Mesh(geometry, materials[primitive.material]));
    }
    return node;
  });
  spec.nodes.forEach((data, index) => data.children?.forEach(child => nodes[index].add(nodes[child])));
  const room = new THREE.Group(), scene = new THREE.Scene(); scene.add(room);
  spec.scenes[spec.scene || 0].nodes.forEach(index => room.add(nodes[index]));
  for (const node of nodes) if (['environment.orbital_dock', 'environment.warm_gallery'].includes(node.userData.asset_id)) node.removeFromParent();
  scene.updateMatrixWorld(true);
  return { room, scene, modelPath };
}
class FakeNode {
  constructor(document) { this.ownerDocument = document; this.children = []; this.parentNode = null; this.listeners = new Map(); this.attributes = new Map(); this.classes = new Set(); this.captured = new Set(); this.rect = { width: 720, height: 500 }; this.rectReads = 0; this.style = {};
    this.classList = { add: (...names) => names.forEach(name => this.classes.add(name)), remove: (...names) => names.forEach(name => this.classes.delete(name)), contains: name => this.classes.has(name) };
  }
  get nextSibling() { return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] || null; }
  appendChild(node) { node.parentNode?.removeChild(node); this.children.push(node); node.parentNode = this; }
  removeChild(node) { this.children.splice(this.children.indexOf(node), 1); node.parentNode = null; }
  insertBefore(node, next) { node.parentNode?.removeChild(node); this.children.splice(this.children.indexOf(next), 0, node); node.parentNode = this; }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  removeEventListener(name, callback) { if (this.listeners.get(name) === callback) this.listeners.delete(name); }
  dispatch(name, event) { this.listeners.get(name)?.({ pointerId: 1, pointerType: 'mouse', button: 0, isPrimary: true, cancelable: true, preventDefault() {}, ...event }); }
  setPointerCapture(id) { this.captured.add(id); }
  hasPointerCapture(id) { return this.captured.has(id); }
  releasePointerCapture(id) { this.captured.delete(id); }
  getBoundingClientRect() { this.rectReads++; return this.rect; }
}
function environment() {
  const windowListeners = new Map(), observers = [];
  const view = { innerWidth: 1280, innerHeight: 800, devicePixelRatio: 2,
    addEventListener: (name, callback) => windowListeners.set(name, callback),
    removeEventListener: (name, callback) => { if (windowListeners.get(name) === callback) windowListeners.delete(name); },
    ResizeObserver: class { constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } },
  };
  const document = { hidden: false, defaultView: view };
  const parent = new FakeNode(document), element = new FakeNode(document), canvas = new FakeNode(document), sibling = new FakeNode(document);
  parent.appendChild(canvas); parent.appendChild(sibling); canvas.style.width = '1280px'; canvas.style.height = '800px';
  const renderer = { size: new THREE.Vector2(1280, 800), pixelRatio: 2, color: new THREE.Color('#3a5367'), alpha: 1, autoClear: false, scissorTest: true, scissor: new THREE.Vector4(1, 2, 3, 4), viewport: new THREE.Vector4(0, 0, 1280, 800),
    getSize(out) { return out.copy(this.size); }, getPixelRatio() { return this.pixelRatio; },
    getClearColor(out) { return out.copy(this.color); }, getClearAlpha() { return this.alpha; },
    getScissor(out) { return out.copy(this.scissor); }, getScissorTest() { return this.scissorTest; },
    setPixelRatio(value) { this.pixelRatio = value; }, setSize(x, y, updateStyle = true) { this.size.set(x, y); if (updateStyle) { canvas.style.width = `${x}px`; canvas.style.height = `${y}px`; } },
    setViewport(x, y, z, w) { this.viewport.set(x, y, z, w); },
    setScissor(value) { this.scissor.copy(value); }, setScissorTest(value) { this.scissorTest = value; },
    setClearColor(value, alpha) { this.color.set(value); this.alpha = alpha; },
    async compileAsync() {}, render(scene, camera) { scene.updateMatrixWorld(true); camera.updateMatrixWorld(true); this.scene = scene; this.camera = camera; },
  };
  return { renderer, element, canvas, parent, sibling, document, view, windowListeners, observers };
}
const model = fixture();
const originalNodes = []; model.room.traverse(node => originalNodes.push(node));
const originalPoses = new Map(originalNodes.map(node => [node, pose(node)]));
let disposed = 0;
model.room.traverse(node => { if (!node.isMesh) return; for (const resource of [node.geometry, node.material, node.material.map]) resource.addEventListener('dispose', () => disposed++); });
const options = env => ({ THREE, room: model.room, ...env });
const frames = (controller, count) => { for (let index = 0; index < count; index++) controller.update(1 / 120); };

const env = environment(), controller = await createHomepageRoom(options(env));
const rotor = env.renderer.scene.children[0], clone = rotor.children[0], cloneNodes = [];
clone.traverse(node => cloneNodes.push(node));
assert.equal(cloneNodes.length, originalNodes.length);
for (let i = 0; i < cloneNodes.length; i++) {
  assert.notEqual(cloneNodes[i], originalNodes[i]);
  if (!originalNodes[i].isMesh) continue;
  assert.equal(cloneNodes[i].geometry, originalNodes[i].geometry);
  assert.equal(cloneNodes[i].material, originalNodes[i].material);
  assert.equal(cloneNodes[i].material.map, originalNodes[i].material.map);
}
assert.equal(controller.getState().componentCount, 93);
assert.equal(controller.getState().motion.assetIds.length, 12);
assert.equal(env.canvas.parentNode, env.element);
assert.ok(env.element.classList.contains('is-live'));
assert.equal(env.renderer.alpha, 0);
results.push({ check: 'Actual V14 clone: 93 independent IDs, 12 mechanisms, shared geometry/material/texture references', status: 'passed' });

let minYaw = Infinity, maxYaw = -Infinity;
const cloneBefore = new Map(cloneNodes.map(node => [node, pose(node)])), moved = new Set();
for (let index = 0; index < 32 * 120; index++) {
  controller.update(1 / 120);
  const yaw = controller.getState().yawDegrees; minYaw = Math.min(minYaw, yaw); maxYaw = Math.max(maxYaw, yaw);
  for (const node of cloneNodes) if (pose(node).some((value, i) => Math.abs(value - cloneBefore.get(node)[i]) > 1e-7)) moved.add(node.userData.asset_id);
}
assert.ok(maxYaw > 17.8 && minYaw < -17.8 && maxYaw <= 18 && minYaw >= -18);
for (const id of controller.getState().motion.assetIds) assert.ok(moved.has(id), `${id} animates`);
for (const node of originalNodes) assert.deepEqual(pose(node), originalPoses.get(node), `${node.name} original remains untouched`);
assert.equal(env.element.rectReads, 1, 'no layout reads during frame updates');
results.push({ check: 'Automatic ±18° yaw and 12 moving parts never alter main room transforms; no frame-loop layout reads', status: 'passed', minYaw, maxYaw });

env.element.dispatch('pointerdown', { clientX: 100, clientY: 100 });
env.element.dispatch('pointermove', { clientX: 102, clientY: 125 });
assert.equal(controller.getState().dragging, false, 'vertical pan is released');
assert.equal(env.element.captured.size, 0);
env.element.dispatch('pointerdown', { clientX: 100, clientY: 100 });
env.element.dispatch('pointermove', { clientX: 10000, clientY: 102 });
frames(controller, 180);
assert.ok(controller.getState().dragging);
close(controller.getState().yawDegrees, 35, 'bounded manual yaw', 1e-6);
env.element.dispatch('pointerup', { clientX: 10000, clientY: 102 });
frames(controller, 12 * 120);
assert.ok(Math.abs(controller.getState().yawDegrees) < 18.1, 'manual release eases back to automatic sweep');
results.push({ check: 'Horizontal drag clamps to 35°, vertical touch intent releases capture, automatic motion resumes', status: 'passed' });

let maxNdc = 0;
const point = new THREE.Vector3();
for (const size of [[720, 500], [300, 370], [1200, 280]]) {
  env.element.rect = { width: size[0], height: size[1] }; env.observers[0].callback();
  for (let degrees = -35; degrees <= 35; degrees += 5) {
    rotor.rotation.y = degrees * Math.PI / 180; controller.render();
    clone.traverse(node => {
      if (!node.isMesh) return;
      const positions = node.geometry.attributes.position;
      for (let index = 0; index < positions.count; index++) {
        point.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld).project(env.renderer.camera);
        maxNdc = Math.max(maxNdc, Math.abs(point.x), Math.abs(point.y));
        assert.ok(Math.abs(point.x) < 1 && Math.abs(point.y) < 1 && point.z >= -1 && point.z <= 1, `silhouette outside viewport at ${degrees}° ${size}`);
      }
    });
  }
}
results.push({ check: 'Every model vertex remains inside desktop, tall mobile and wide-short orthographic frames across all drag angles', status: 'passed', maxNdc });

const beforeHidden = controller.getState(); env.document.hidden = true;
frames(controller, 120); controller.render();
assert.equal(controller.getState().yawDegrees, beforeHidden.yawDegrees);
assert.equal(controller.getState().frameCount, beforeHidden.frameCount);
env.document.hidden = false;
env.view.innerWidth = 1600; env.view.innerHeight = 900;
controller.release(); controller.release(); controller.update(1); controller.render();
assert.equal(env.canvas.parentNode, env.parent); assert.equal(env.canvas.nextSibling, env.sibling);
assert.deepEqual(env.renderer.size.toArray(), [1600, 900]);
assert.equal(env.canvas.style.width, '1600px', 'returned canvas CSS width follows current viewport');
assert.equal(env.canvas.style.height, '900px', 'returned canvas CSS height follows current viewport');
const releasedReads = env.element.rectReads;
const releasedSize = env.renderer.size.toArray();
for (const observer of env.observers) observer.callback();
assert.equal(env.element.rectReads, releasedReads, 'queued observer callback does not read layout after release');
assert.deepEqual(env.renderer.size.toArray(), releasedSize, 'queued observer callback cannot retake renderer after release');
assert.deepEqual(env.renderer.viewport.toArray(), [0, 0, 1600, 900]);
assert.equal(env.renderer.color.getHexString(), '3a5367'); assert.equal(env.renderer.alpha, 1);
assert.equal(env.renderer.autoClear, false); assert.equal(env.renderer.scissorTest, true);
assert.deepEqual(env.renderer.scissor.toArray(), [1, 2, 3, 4]);
assert.equal(env.element.listeners.size, 0); assert.equal(env.windowListeners.size, 0);
assert.ok(env.observers.every(observer => observer.disconnected)); assert.equal(disposed, 0);
assert.equal(controller.getState().active, false);
results.push({ check: 'Hidden documents pause; release restores current CSS and drawing sizes; queued observers cannot retake renderer; shared resources stay alive', status: 'passed' });

const reducedEnv = environment(), reduced = await createHomepageRoom({ ...options(reducedEnv), reducedMotion: true });
const reducedNodes = []; reducedEnv.renderer.scene.traverse(node => reducedNodes.push(node));
const reducedBefore = new Map(reducedNodes.map(node => [node, pose(node)]));
frames(reduced, 30 * 120);
for (const node of reducedNodes) assert.deepEqual(pose(node), reducedBefore.get(node));
reducedEnv.element.dispatch('pointerdown', { clientX: 100, clientY: 100 });
reducedEnv.element.dispatch('pointermove', { clientX: 230, clientY: 100 });
frames(reduced, 240); reducedEnv.element.dispatch('pointerup', { clientX: 230, clientY: 100 }); frames(reduced, 30 * 120);
assert.ok(reduced.getState().yawDegrees > 18 && reduced.getState().yawDegrees < 19);
assert.equal(reduced.getState().motion.activeCount, 0); reduced.release();
results.push({ check: 'Reduced motion has no automatic rotation/bobbing/mechanisms, while deliberate manual rotation remains available', status: 'passed' });

const failureEnv = environment(); failureEnv.renderer.compileAsync = async () => { throw new Error('Expected compile failure'); };
await assert.rejects(createHomepageRoom(options(failureEnv)), /Expected compile failure/);
assert.equal(failureEnv.canvas.parentNode, failureEnv.parent);
assert.equal(failureEnv.canvas.nextSibling, failureEnv.sibling);
assert.equal(failureEnv.element.listeners.size, 0); assert.equal(failureEnv.windowListeners.size, 0);
assert.equal(failureEnv.renderer.alpha, 1); assert.equal(disposed, 0);
assert.ok(!failureEnv.element.classList.contains('is-live'));
results.push({ check: 'Compile failure restores the static fallback and main renderer ownership', status: 'passed' });
gsap.ticker.sleep();
console.log(JSON.stringify({ model: model.modelPath, results, passed: results.length }, null, 2));
