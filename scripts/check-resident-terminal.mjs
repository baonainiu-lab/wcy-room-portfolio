import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { createResidentTerminal } from '../src/resident-terminal.js';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';

const checks = [];
const close = (a, b, tolerance = 1e-6) => assert.ok(Math.abs(a - b) <= tolerance, `${a} != ${b}`);
const equalMatrix = (a, b) => a.elements.forEach((value, index) => close(value, b.elements[index]));
const pose = node => ({ position: node.position.toArray(), quaternion: node.quaternion.toArray(), scale: node.scale.toArray() });
const roomGltf = await parseModelForCPU('public/models/orbital-atelier-v16.glb');
const welcomeGltf = await parseModelForCPU('public/models/welcome-terminal-v1.glb');
const room = roomGltf.scene, scene = new THREE.Scene(); scene.add(room);
let root; room.traverse(node => { if (node.userData.asset_id === 'folding_drawing_terminal') root = node; });
const originalRoot = pose(root), children = [...root.children];
const oldResources = new Map(), newResources = new Map();
for (const [model, resources] of [[room, oldResources], [welcomeGltf.scene, newResources]]) model.traverse(node => {
  if (!node.isMesh) return;
  for (const resource of [node.geometry, ...[].concat(node.material), ...[].concat(node.material).flatMap(material => Object.values(material).filter(value => value?.isTexture))]) {
    if (resources.has(resource)) continue;
    resources.set(resource, 0); resource.addEventListener('dispose', () => resources.set(resource, resources.get(resource) + 1));
  }
});
let reflectionDisposals = 0;
class Generator {
  fromScene() { return { texture: new THREE.Texture(), dispose() { reflectionDisposals++; } }; }
  dispose() {}
}
const binding = createResidentTerminal({ THREE: { ...THREE, PMREMGenerator: Generator }, renderer: {}, room, welcomeGltf });
async function check(name, run) {
  try { checks.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { checks.push({ check: name, status: 'failed', error: error.stack }); }
}
await check('the actual fully opened terminal fits within the original asset envelope without changing its root', () => {
  binding.attachHome();
  const state = binding.getState(), box = new THREE.Box3().setFromObject(binding.carrier, true);
  for (const [index, axis] of ['x', 'y', 'z'].entries()) {
    assert.ok(box.min[axis] >= state.originalBounds.min[index] - 1e-6);
    assert.ok(box.max[axis] <= state.originalBounds.max[index] + 1e-6);
  }
  let desk; room.traverse(node => { if (node.userData.asset_id === 'furniture.desk') desk = node; });
  const deskBox = new THREE.Box3().setFromObject(desk, true), raycaster = new THREE.Raycaster();
  const normal = new THREE.Vector3(), normalMatrix = new THREE.Matrix3(), surfaceHeights = [];
  // A denser independent grid checks the supporting triangles between the
  // production module's corner/edge/center samples, including rounded edges.
  for (let ix = 0; ix <= 6; ix++) for (let iz = 0; iz <= 6; iz++) {
    raycaster.set(new THREE.Vector3(THREE.MathUtils.lerp(box.min.x, box.max.x, ix / 6), deskBox.max.y + .1,
      THREE.MathUtils.lerp(box.min.z, box.max.z, iz / 6)), new THREE.Vector3(0, -1, 0));
    for (const hit of raycaster.intersectObject(desk, true)) {
      normalMatrix.getNormalMatrix(hit.object.matrixWorld);
      if (hit.face && normal.copy(hit.face.normal).applyNormalMatrix(normalMatrix).y > .5) { surfaceHeights.push(hit.point.y); break; }
    }
  }
  assert.ok(surfaceHeights.length > 20, 'many actual desk triangles support the terminal');
  const measuredSurface = Math.max(...surfaceHeights);
  assert.ok(box.min.y >= measuredSurface + .00299, 'underside clears the actual desk, including samples between placement probes');
  close(box.min.y, measuredSurface + .003, 2e-6);
  assert.deepEqual(pose(root), originalRoot);
  close(binding.carrier.scale.x, binding.carrier.scale.y); close(binding.carrier.scale.x, binding.carrier.scale.z);
  return { finalBounds: state.finalBounds, originalBounds: state.originalBounds, support: state.support,
    independentlyMeasuredSupport: { validSamples: surfaceHeights.length, surfaceHeight: measuredSurface, actualClearance: box.min.y - measuredSurface },
    meshes: state.meshCount, triangleDelta: state.triangles - state.oldTriangles, drawCallDelta: state.drawCallDelta };
});
await check('all native parts remain independently selectable and the original Blender animation still resolves', () => {
  const parts = [], nodes = new Map();
  binding.model.traverse(node => { nodes.set(node.name, node); if (node.userData.asset_id) parts.push(node.userData.asset_id); });
  assert.deepEqual(parts.sort(), ['terminal_dial', 'terminal_lid', 'terminal_rail']);
  for (const track of binding.clips[0].tracks) {
    const target = THREE.PropertyBinding.parseTrackName(track.name).nodeName;
    assert.ok(nodes.has(target), `native track still resolves: ${target}`);
  }
  assert.equal(root.userData.asset_id, 'folding_drawing_terminal');
  assert.ok(children.every(child => !root.children.includes(child)));
  return { parts, tracks: binding.clips[0].tracks.map(track => track.name) };
});
await check('detachment preserves the exact world pose and landing restores final native geometry even after room animation', () => {
  binding.carrier.updateWorldMatrix(true, true);
  const world = binding.carrier.matrixWorld.clone(), finalLocal = pose(binding.carrier);
  const home = binding.getHomeWorldPose(), cached = new THREE.Matrix4().compose(home.position, home.quaternion, home.scale);
  equalMatrix(world, cached);
  binding.detachForIntro(scene); binding.carrier.updateWorldMatrix(true, true); equalMatrix(binding.carrier.matrixWorld, world);
  room.scale.setScalar(.1); room.position.set(2, -1, 5); room.updateWorldMatrix(true, true);
  equalMatrix(new THREE.Matrix4().compose(home.position, home.quaternion, home.scale), cached);
  room.scale.setScalar(1); room.position.set(0, 0, 0);
  const lid = binding.model.getObjectByName('seedlid'), finalQuaternion = lid.quaternion.clone();
  lid.quaternion.identity(); binding.carrier.position.set(4, 8, 2); binding.carrier.scale.setScalar(5);
  binding.attachHome(); binding.carrier.updateWorldMatrix(true, true);
  assert.equal(binding.carrier.parent, root); assert.deepEqual(pose(binding.carrier), finalLocal);
  close(lid.quaternion.angleTo(finalQuaternion), 0); equalMatrix(binding.carrier.matrixWorld, world);
  assert.ok([...newResources.values()].every(count => count === 0), 'landing retains every GPU resource');
  assert.equal(reflectionDisposals, 0);
});
await check('welcome lighting fades to retained PBR reflections and room day/night values instead of black', () => {
  binding.setTheme(true, 0); binding.setIntroLight(1);
  const material = binding.model.getObjectByName('terminalbasenavy').material, env = material.envMap;
  assert.ok(env?.isTexture); close(material.envMapIntensity, .9);
  binding.setIntroLight(.001); const nearLanding = material.envMapIntensity;
  binding.setIntroLight(0); close(material.envMapIntensity, 1.1); assert.ok(Math.abs(material.envMapIntensity - nearLanding) < .001);
  binding.setTheme(false, 0); close(material.envMapIntensity, .3); assert.equal(material.envMap, env);
  const lights = []; binding.carrier.traverse(node => { if (node.isLight) lights.push(node); });
  assert.equal(lights.length, 2); assert.ok(lights.every(light => light.intensity === 0 && !light.castShadow));
  assert.equal(binding.carrier.parent, root, 'lights inherit room visibility after landing');
});
await check('disposal restores original children once and never disposes the shared room atlases', () => {
  binding.dispose(); binding.dispose();
  assert.deepEqual(root.children, children); assert.deepEqual(pose(root), originalRoot);
  assert.ok([...oldResources.values()].every(count => count === 0));
  assert.ok([...newResources.values()].every(count => count === 1)); assert.equal(reflectionDisposals, 1);
});
const source = path => readFileSync(new URL(`../${path}`, import.meta.url));
const paths = ['src/resident-terminal.js', 'src/main.js'];
const report = { checkedAt: new Date().toISOString(), checks, passed: checks.filter(check => check.status === 'passed').length,
  failed: checks.filter(check => check.status === 'failed').length,
  scope: 'Actual GLTFLoader vertices, native clip and transforms. Image decoding and GPU PMREM generation are substituted; no rendered brightness or FPS claim.',
  sourceSha256: Object.fromEntries(paths.map(path => [path, createHash('sha256').update(source(path)).digest('hex')])) };
if (process.argv.includes('--write-report')) writeFileSync(new URL('../docs/validation/resident-terminal-v1.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2)); if (report.failed) process.exitCode = 1;
