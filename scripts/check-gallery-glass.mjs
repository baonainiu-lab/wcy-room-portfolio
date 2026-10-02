import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { WebGLRenderList } from '../node_modules/three/src/renderers/webgl/WebGLRenderLists.js';
import { createGalleryGlass } from '../src/gallery-glass.js';
import { GALLERY_OFFSET } from '../src/gallery-transition-path.js';

const results = [];
const close = (a, b, label, epsilon = 3e-6) => {
  const left = a.toArray ? a.toArray() : a, right = b.toArray ? b.toArray() : b;
  assert.equal(left.length, right.length, label);
  left.forEach((value, index) => assert.ok(Math.abs(value - right[index]) <= epsilon, `${label}[${index}]: ${value} != ${right[index]}`));
};
async function check(name, run) {
  try { results.push({ check: name, status: 'passed', ...await run() }); }
  catch (error) { results.push({ check: name, status: 'failed', error: error.message, stack: error.stack }); }
}
function fixture({ sharedGeometry = false } = {}) {
  const scene = new THREE.Scene(), model = new THREE.Group(), parent = new THREE.Group();
  scene.add(parent); parent.add(model);
  parent.position.set(1.2, .4, -1.7); parent.rotation.set(.1, -.23, .07); parent.scale.set(1.2, .8, 1.1);
  model.position.set(.7, .2, -.3); model.rotation.y = .14;
  const glass = new THREE.MeshBasicMaterial({ name: 'GALLERY_ARCH_GLASS', transparent: true, opacity: .1 });
  const ordinary = new THREE.MeshBasicMaterial({ name: 'GALLERY_CLEAR', transparent: true, opacity: .1 });
  const opaque = new THREE.MeshBasicMaterial({ name: 'GALLERY_LIGHTMAP_0' });
  const geometry = new THREE.BoxGeometry(2, 3, .06); geometry.deleteAttribute('normal');
  const first = new THREE.Mesh(geometry, glass); first.position.set(-2, 1.5, -.8); first.rotation.y = .24;
  const branch = new THREE.Group(); branch.position.set(2.4, .1, .8); branch.rotation.z = -.1; model.add(first, branch);
  const second = new THREE.Mesh(sharedGeometry ? geometry : geometry.clone(), [opaque, glass]);
  second.position.set(.5, 2.2, -.4); second.rotation.y = -.21; branch.add(second);
  const untouched = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), ordinary); model.add(untouched);
  const themeUniform = { value: .25 }, textures = [new THREE.Texture(), new THREE.Texture()], textureDisposals = [0, 0];
  textures.forEach((texture, index) => texture.addEventListener('dispose', () => textureDisposals[index]++));
  const requested = [], rendererAccess = [];
  const renderer = new Proxy({ capabilities: { getMaxAnisotropy() { rendererAccess.push('capabilities.getMaxAnisotropy'); return 16; } } }, {
    get(target, key) { assert.ok(key in target, `glass must not call renderer.${String(key)}`); return target[key]; },
  });
  const loader = { async loadAsync(url) { requested.push(url); return textures[url.includes('reflection-day') ? 0 : 1]; } };
  const create = extras => createGalleryGlass({ model, loader, renderer, themeUniform, ...extras });
  return { scene, parent, model, branch, first, second, untouched, glass, ordinary, opaque,
    themeUniform, textures, textureDisposals, requested, rendererAccess, renderer, loader, create };
}
function localToNative(mesh) {
  const chain = []; for (let node = mesh; node; node = node.parent) chain.unshift(node);
  const matrix = new THREE.Matrix4();
  for (const node of chain) matrix.multiply(new THREE.Matrix4().compose(node.position, node.quaternion, node.scale));
  return matrix;
}
function verifyProbePositions(mesh) {
  const expectedMatrix = localToNative(mesh), local = mesh.geometry.attributes.position, probe = mesh.geometry.attributes.glassProbePosition;
  assert.ok(probe); assert.equal(probe.itemSize, 3); assert.equal(probe.count, local.count);
  for (let i = 0; i < local.count; i++) {
    close(new THREE.Vector3().fromBufferAttribute(probe, i), new THREE.Vector3().fromBufferAttribute(local, i).applyMatrix4(expectedMatrix), 'native probe coordinate');
  }
}

await check('parent transforms, missing normals and multi-material selection bind correct native coordinates', async () => {
  const f = fixture(), normalBefore = f.first.geometry.getAttribute('normal'); assert.equal(normalBefore, undefined);
  const helper = await f.create(); verifyProbePositions(f.first); verifyProbePositions(f.second);
  assert.equal(f.first.material, helper.material); assert.equal(f.second.material[1], helper.material);
  assert.equal(f.second.material[0], f.opaque); assert.equal(f.untouched.material, f.ordinary);
  assert.equal(f.untouched.geometry.getAttribute('glassProbePosition'), undefined);
  assert.deepEqual([...helper.replacedMaterials], [f.glass]);
  for (const mesh of [f.first, f.second]) {
    const normals = mesh.geometry.getAttribute('normal'); assert.ok(normals);
    for (let i = 0; i < normals.count; i++) close([new THREE.Vector3().fromBufferAttribute(normals, i).length()], [1], 'computed normal length');
  }
  assert.equal(helper.getState().meshes, 2); helper.dispose(); helper.material.dispose();
  return { architecturalMeshes: 2, retainedOtherMaterials: 2, vertexCounts: [f.first.geometry.attributes.position.count, f.second.geometry.attributes.position.count] };
});
await check('different native meshes sharing geometry keep independent probe coordinate bindings', async () => {
  const f = fixture({ sharedGeometry: true }), originalGeometry = f.first.geometry, helper = await f.create();
  verifyProbePositions(f.first); verifyProbePositions(f.second);
  assert.notEqual(f.first.geometry.getAttribute('glassProbePosition'), f.second.geometry.getAttribute('glassProbePosition'), 'different world transforms require different probe attributes');
  assert.equal(f.first.geometry, originalGeometry); assert.notEqual(f.second.geometry, originalGeometry);
  let originalDisposals = 0, cloneDisposals = 0;
  originalGeometry.addEventListener('dispose', () => originalDisposals++); f.second.geometry.addEventListener('dispose', () => cloneDisposals++);
  const clone = f.model.clone(true); assert.ok(clone.children[1].children[0].geometry === f.second.geometry, 'stage borrows the independent native binding');
  helper.dispose(); helper.dispose(); helper.material.dispose();
  assert.equal(originalDisposals, 0); assert.equal(cloneDisposals, 1);
  return { originalGeometryDisposals: originalDisposals, helperOwnedCloneDisposals: cloneDisposals };
});
await check('stage clones borrow resources and translation preserves native probe attributes and reflection directions', async () => {
  const f = fixture(), helper = await f.create(); f.scene.updateMatrixWorld(true);
  const before = f.first.geometry.attributes.glassProbePosition.array.slice();
  const stage = f.scene.clone(true); stage.position.add(GALLERY_OFFSET); stage.updateMatrixWorld(true);
  const clone = stage.children[0].children[0].children.find(node => node.isMesh && node.material === helper.material);
  assert.ok(clone); assert.equal(clone.geometry, f.first.geometry); assert.equal(clone.material, helper.material);
  assert.equal(clone.geometry.attributes.glassProbePosition, f.first.geometry.attributes.glassProbePosition);
  const vertex = new THREE.Vector3().fromBufferAttribute(f.first.geometry.attributes.position, 0);
  const nativePoint = vertex.clone().applyMatrix4(f.first.matrixWorld), stagePoint = vertex.clone().applyMatrix4(clone.matrixWorld);
  close(stagePoint, nativePoint.clone().add(GALLERY_OFFSET), 'stage model translates physically');
  const nativeCamera = new THREE.Vector3(12, 10, 20), stageCamera = nativeCamera.clone().add(GALLERY_OFFSET);
  close(stageCamera.sub(stagePoint).normalize(), nativeCamera.sub(nativePoint).normalize(), 'translated view direction is invariant');
  assert.deepEqual(f.first.geometry.attributes.glassProbePosition.array, before);
  helper.dispose(); helper.material.dispose(); return { sharedGeometry: true, sharedMaterial: true, stageOffset: GALLERY_OFFSET.toArray() };
});
await check('live theme and reflection textures remain shared; the helper owns images and the gallery owns materials', async () => {
  const f = fixture(), helper = await f.create(); let shaderDisposals = 0, originalDisposals = 0, geometryDisposals = 0;
  helper.material.addEventListener('dispose', () => shaderDisposals++); f.glass.addEventListener('dispose', () => originalDisposals++);
  f.first.geometry.addEventListener('dispose', () => geometryDisposals++);
  assert.equal(helper.material.uniforms.uTheme, f.themeUniform);
  assert.equal(helper.material.uniforms.uReflectionDay.value, f.textures[0]); assert.equal(helper.material.uniforms.uReflectionNight.value, f.textures[1]);
  for (const value of [0, .5, 1]) { f.themeUniform.value = value; assert.equal(f.first.clone().material.uniforms.uTheme.value, value); }
  for (const texture of f.textures) {
    assert.equal(texture.colorSpace, THREE.SRGBColorSpace); assert.equal(texture.wrapS, THREE.RepeatWrapping);
    assert.equal(texture.wrapT, THREE.ClampToEdgeWrapping); assert.equal(texture.anisotropy, 4);
  }
  helper.dispose(); helper.dispose();
  assert.deepEqual(f.textureDisposals, [1, 1]); assert.equal(shaderDisposals, 0); assert.equal(originalDisposals, 0); assert.equal(geometryDisposals, 0);
  helper.material.dispose(); assert.equal(shaderDisposals, 1); helper.replacedMaterials.forEach(material => material.dispose()); assert.equal(originalDisposals, 1);
  return { helperTextureDisposals: f.textureDisposals, ownerShaderDisposals: shaderDisposals, ownerReplacedMaterialDisposals: originalDisposals, helperGeometryDisposals: geometryDisposals };
});
await check('either reflection loading failure releases every successful image without replacing materials', async () => {
  const cases = [];
  for (const failing of ['day', 'night']) {
    const f = fixture();
    const loader = { async loadAsync(url) { if (url.includes(`reflection-${failing}.`)) throw new Error(`injected ${failing} load failure`); return f.loader.loadAsync(url); } };
    await assert.rejects(f.create({ loader }), new RegExp(`injected ${failing}`));
    assert.deepEqual(f.textureDisposals, failing === 'day' ? [0, 1] : [1, 0]);
    assert.equal(f.first.material, f.glass); assert.equal(f.second.material[1], f.glass);
    assert.equal(f.first.geometry.attributes.glassProbePosition, undefined); cases.push({ failing, disposals: f.textureDisposals });
  }
  return { cases };
});
await check('setup failure restores assigned materials and releases images; invalid inputs never start loading', async () => {
  const f = fixture({ sharedGeometry: true }), originalGeometry = f.first.geometry;
  const invalid = new THREE.Mesh(new THREE.BufferGeometry(), f.glass); f.model.add(invalid);
  let clonedDisposals = 0, shaderDisposals = 0, originalDisposals = 0;
  const originalClone = originalGeometry.clone;
  originalGeometry.clone = function () { const clone = originalClone.call(this); clone.addEventListener('dispose', () => clonedDisposals++); return clone; };
  originalGeometry.addEventListener('dispose', () => originalDisposals++);
  let boundMaterial = f.first.material;
  Object.defineProperty(f.first, 'material', { get: () => boundMaterial, set(value) {
    boundMaterial = value; if (value.isShaderMaterial) value.addEventListener('dispose', () => shaderDisposals++);
  } });
  await assert.rejects(f.create()); assert.equal(f.first.material, f.glass); assert.equal(f.second.material[1], f.glass);
  assert.equal(f.first.geometry, originalGeometry); assert.equal(f.second.geometry, originalGeometry);
  assert.equal(clonedDisposals, 1); assert.equal(shaderDisposals, 1); assert.equal(originalDisposals, 0);
  assert.deepEqual(f.textureDisposals, [1, 1]);
  const badTheme = fixture(); await assert.rejects(badTheme.create({ themeUniform: null }), /live theme uniform/); assert.equal(badTheme.requested.length, 0);
  const absent = fixture(); absent.first.material = absent.opaque; absent.second.material = absent.opaque;
  await assert.rejects(absent.create(), /missing architectural glass/); assert.equal(absent.requested.length, 0);
  return { failedOwnedCloneDisposals: clonedDisposals, failedShaderDisposals: shaderDisposals, originalGeometryDisposals: originalDisposals };
});
await check('normal transform remains perpendicular under rotated and nonuniform parent transforms', async () => {
  const f = fixture(), helper = await f.create();
  const camera = new THREE.PerspectiveCamera(35, 1.6, .1, 500); camera.position.set(12, 10, 20); camera.lookAt(0, 2, 0); camera.updateMatrixWorld(true);
  const mesh = f.first, view = camera.matrixWorldInverse, modelView = new THREE.Matrix4().multiplyMatrices(view, mesh.matrixWorld);
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(modelView), normal = new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.normal, 0);
  const transformed = normal.applyMatrix3(normalMatrix).transformDirection(camera.matrixWorld);
  const indices = mesh.geometry.index.array, points = [0, 1, 2].map(i => new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.position, indices[i]).applyMatrix4(mesh.matrixWorld));
  const geometricNormal = points[1].clone().sub(points[0]).cross(points[2].clone().sub(points[0])).normalize();
  close(transformed, geometricNormal, 'world normal equals actual transformed surface normal');
  assert.match(helper.material.vertexShader, /inverseTransformDirection\(normalMatrix \* normal, viewMatrix\)/);
  helper.dispose(); helper.material.dispose();
});
await check('Fresnel and alpha obey analytic endpoint, monotonicity and energy-weighted blending expectations', async () => {
  const f = fixture(), helper = await f.create(), shader = helper.material.fragmentShader;
  const first = shader.match(/float fresnel = ([^;]+);/)?.[1];
  const second = shader.match(/\n\s*fresnel = ([^;]+);/)?.[1]; assert.ok(first && second);
  const evaluate = new Function('incidence', `let fresnel = ${first.replaceAll('pow(', 'Math.pow(')}; fresnel = ${second}; return fresnel;`);
  const incidenceSource = shader.match(/float incidence = ([^;]+);/)?.[1]; assert.ok(incidenceSource);
  const incidence = new Function('dotValue', 'clamp', `return ${incidenceSource.replace('abs(dot(viewDirection, normal))', 'Math.abs(dotValue)')};`);
  for (const dotValue of [-1.00000012, -1, 0, 1, 1.00000012]) {
    const value = incidence(dotValue, THREE.MathUtils.clamp);
    assert.ok(value >= 0 && value <= 1, 'roundoff cannot put the GLSL pow base outside its nonnegative domain');
    assert.ok(Number.isFinite(evaluate(value)));
  }
  const tintAlpha = helper.material.uniforms.uTintAlpha.value, atHead = evaluate(1), atSixty = evaluate(.5), atEdge = evaluate(0);
  close([atHead, atSixty, atEdge], [.0784, .1351, 1], 'two-interface Fresnel analytic cases', 1e-12);
  close([atHead + tintAlpha * (1 - atHead)], [.156736], 'head-on blended opacity', 1e-12);
  let prior = -Infinity;
  for (let i = 0; i <= 100; i++) {
    const fresnel = evaluate(1 - i / 100), tint = tintAlpha * (1 - fresnel), alpha = fresnel + tint;
    assert.ok(fresnel >= prior && alpha >= 0 && alpha <= 1); prior = fresnel;
    for (const reflected of [0, .2, 1]) {
      const tinted = .4, straightColor = (reflected * fresnel + tinted * tint) / Math.max(alpha, .0001);
      close([straightColor * alpha], [reflected * fresnel + tinted * tint], 'reflection is not attenuated twice by alpha', 1e-12);
    }
  }
  helper.dispose(); helper.material.dispose(); return { reflectanceAtNormal: atHead, reflectanceAt60Degrees: atSixty, reflectanceAtGrazing: atEdge, opacityAtNormal: .156736 };
});
await check('box projection agrees with independent ray-box intersections, including parallel rays on a box face', async () => {
  const f = fixture(), helper = await f.create(), shader = helper.material.fragmentShader;
  assert.match(shader, /distances = mix\(vec3\(1\.0e20\), distances, step\(vec3\(0\.00001\), abs\(ray\)\)\);/,
    'the actual shader excludes parallel axes rather than accepting their zero distance');
  assert.match(shader, /return normalize\(p \+ ray \* distanceToBox - uProbePosition\);/);
  const box = new THREE.Box3(helper.material.uniforms.uProbeMin.value, helper.material.uniforms.uProbeMax.value);
  const probe = helper.material.uniforms.uProbePosition.value;
  const origins = [new THREE.Vector3(0, 2, 0), new THREE.Vector3(11, 2, 0), new THREE.Vector3(-11, 2, 0),
    new THREE.Vector3(0, box.max.y, 0), new THREE.Vector3(0, box.min.y, 0), new THREE.Vector3(0, 2, box.min.z), new THREE.Vector3(0, 2, box.max.z)];
  const directions = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 1, 0),
    new THREE.Vector3(0, -1, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, -1), new THREE.Vector3(.2, .7, -.4).normalize()];
  let cases = 0, maxError = 0;
  for (const position of origins) for (const ray of directions) {
    // Evaluate the shader's scalar component equations; THREE.Ray supplies
    // the independent slab-intersection oracle for the resulting exit point.
    const distances = ['x', 'y', 'z'].map(axis => {
      const component = ray[axis]; if (Math.abs(component) < .00001) return 1e20;
      return Math.max((box.min[axis] - position[axis]) / component, (box.max[axis] - position[axis]) / component);
    });
    const projected = position.clone().addScaledVector(ray, Math.min(...distances)).sub(probe).normalize();
    // Intersect backwards from beyond the volume to select the far/exit face.
    // A ray starting exactly on a box face may otherwise return its near hit.
    const hit = new THREE.Ray(position.clone().addScaledVector(ray, 1000), ray.clone().negate()).intersectBox(box, new THREE.Vector3()); assert.ok(hit);
    const expected = hit.sub(probe).normalize();
    const error = projected.distanceTo(expected); maxError = Math.max(maxError, error);
    assert.ok(error < 1e-10, `box projected reflection should match independent geometry, got ${error}`); cases++;
  }
  helper.dispose(); helper.material.dispose(); return { rayCases: cases, maximumDirectionError: maxError, parallelBoundaryCasesIncluded: true };
});
await check('actual Three render-list classification stays transparent without transmission or renderer passes', async () => {
  const f = fixture(), helper = await f.create(), list = new WebGLRenderList(); list.init();
  list.push(f.first, f.first.geometry, helper.material, 0, 0, null); list.finish();
  assert.equal(list.transparent.length, 1); assert.equal(list.transmissive.length, 0); assert.equal(list.opaque.length, 0);
  assert.equal(helper.material.transparent, true); assert.equal(helper.material.depthWrite, false); assert.equal(helper.material.depthTest, true);
  assert.equal(helper.material.forceSinglePass, true); assert.equal(helper.material.side, THREE.FrontSide);
  assert.ok(f.rendererAccess.every(name => name === 'capabilities.getMaxAnisotropy'));
  assert.equal(helper.getState().additionalScenePasses, 0);
  assert.ok(!helper.material.uniforms.cameraPosition, 'renderer supplies the camera for native and cloned stages');
  helper.dispose(); helper.material.dispose(); return { opaqueItems: 0, transparentItems: 1, transmissiveItems: 0, rendererCalls: f.rendererAccess };
});

const file = path => new URL(`../${path}`, import.meta.url), sha = path => createHash('sha256').update(readFileSync(file(path))).digest('hex');
const report = { revision: 1, checkedAt: new Date().toISOString(), runtime: process.version, threeRevision: THREE.REVISION,
  methodology: 'Real Three.js model hierarchy, geometry, shader materials and renderer render-list classification with production gallery-glass. Texture loader and renderer capabilities are simulated; no GPU, browser, shader compilation or performance measurement. Analytic Fresnel anchors are compared with expressions extracted from the actual shader. Actual V4 GLB geometry and resource checks are recorded separately in works-gallery-v4.json.',
  sourceSha256: Object.fromEntries(['src/gallery-glass.js', 'src/gallery-floor-finish.js', 'src/gallery-transition.js', 'src/gallery-transition-path.js'].map(path => [path, sha(path)])),
  checks: results.length, passed: results.filter(item => item.status === 'passed').length, failed: results.filter(item => item.status === 'failed').length, results };
if (process.argv.includes('--write-report')) {
  mkdirSync(file('docs/validation/'), { recursive: true }); writeFileSync(file('docs/validation/gallery-glass-v1.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({ checks: report.checks, passed: report.passed, failed: report.failed, failures: results.filter(item => item.status === 'failed') }, null, 2));
if (report.failed) process.exitCode = 1;
