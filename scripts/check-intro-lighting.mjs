import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { createIntroLighting } from '../src/intro-lighting.js';

function fixture(failingSlot = null) {
  const room = new THREE.Group(), originals = [], maps = [], cleanMaps = [], requestedPaths = [];
  for (const slot of [0, 1, 8]) {
    const map = new THREE.Texture(); maps.push(map);
    const material = new THREE.MeshBasicMaterial({ map, color: '#31576b' });
    material.name = `WEB8_LIGHTMAP_${slot}`;
    const previousCompile = shader => {
      shader.uniforms.uDayMap = { value: map };
      shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', THREE.ShaderChunk.map_fragment);
    };
    const previousCacheKey = () => `real-day-night-${slot}`;
    material.onBeforeCompile = previousCompile; material.customProgramCacheKey = previousCacheKey;
    originals.push({ material, previousCompile, previousCacheKey, map, color: material.color.clone() });
    room.add(new THREE.Mesh(new THREE.PlaneGeometry(), material));
  }
  const loader = { async loadAsync(path) {
    requestedPaths.push(path);
    if (path.endsWith(`day-${failingSlot}.ktx2`)) throw new Error('missing clean atlas');
    const texture = new THREE.Texture(); texture.disposeCount = 0;
    texture.addEventListener('dispose', () => texture.disposeCount++);
    cleanMaps.push(texture); return texture;
  } };
  const renderer = { capabilities: { getMaxAnisotropy: () => 16 }, initTexture() {} };
  return { room, originals, maps, cleanMaps, requestedPaths, loader, renderer };
}
const checks = [];
async function check(name, fn) { await fn(); checks.push({ name, passed: true }); }
await check('runtime requests the three released V16 receiver maps from the same prepared source', async () => {
  const f = fixture(), intro = await createIntroLighting({ THREE, ...f });
  try {
    assert.deepEqual([...f.requestedPaths].sort(), [0, 1, 8].map(slot => `/textures/intro-clean-v16/day-${slot}.ktx2`));
    const release = JSON.parse(fs.readFileSync(new URL('../assets/blender/photoreal-materials-v16-release.json', import.meta.url)));
    const validation = JSON.parse(fs.readFileSync(new URL('../public/textures/intro-clean-v16/validation.json', import.meta.url)));
    const compressed = JSON.parse(fs.readFileSync(new URL('../public/textures/intro-clean-v16/compression.json', import.meta.url)));
    assert.equal(release.complete, true); assert.equal(validation.complete, true); assert.equal(compressed.complete, true);
    assert.equal(validation.sourceSha256, release.preparedSha256);
    assert.deepEqual(compressed.textures.map(record => record.atlas).sort((a,b) => a-b), [0,1,8]);
    for (const record of compressed.textures) {
      const bytes = fs.readFileSync(new URL(`../${record.path}`, import.meta.url));
      assert.equal(createHash('sha256').update(bytes).digest('hex'), record.sha256);
    }
  } finally { intro.dispose(); }
});
await check('UV-based clean color composes after the existing dual-lighting hook', async () => {
  const f = fixture(), intro = await createIntroLighting({ THREE, ...f });
  for (const original of f.originals) {
    const shader = { uniforms: {}, fragmentShader: '#include <map_fragment>' };
    original.material.onBeforeCompile(shader, f.renderer);
    assert.equal(shader.uniforms.uDayMap.value, original.map);
    assert(f.cleanMaps.includes(shader.uniforms.uIntroCleanMap.value));
    assert(shader.fragmentShader.includes('texture2D(uIntroCleanMap, vMapUv)'));
    assert(!shader.fragmentShader.includes('max(diffuseColor'));
    intro.setProgress(.3); assert.equal(shader.uniforms.uIntroShadowMix.value, .3);
    assert.equal(original.material.map, original.map);
    assert(original.material.color.equals(original.color));
  }
  intro.dispose();
});
await check('skip restores exact day/night hooks without disposing persistent maps', async () => {
  const f = fixture(); let disposed = 0;
  f.maps.forEach(map => map.addEventListener('dispose', () => disposed++));
  const intro = await createIntroLighting({ THREE, ...f });
  intro.setProgress(.4); intro.restore(); intro.restore(); intro.setProgress(0);
  for (const o of f.originals) {
    assert.equal(o.material.onBeforeCompile, o.previousCompile);
    assert.equal(o.material.customProgramCacheKey, o.previousCacheKey);
    assert.equal(o.material.map, o.map);
  }
  assert.equal(intro.getState().progress, 1);
  intro.dispose(); intro.dispose();
  assert.equal(disposed, 0); assert(f.cleanMaps.every(map => map.disposeCount === 1));
});
await check('partial loading failure disposes clean maps and leaves all materials unchanged', async () => {
  const f = fixture(8);
  await assert.rejects(createIntroLighting({ THREE, ...f }), /Clean opening textures/);
  assert(f.cleanMaps.every(map => map.disposeCount === 1));
  for (const o of f.originals) assert.equal(o.material.onBeforeCompile, o.previousCompile);
});
await check('partial shader installation failure rolls back earlier hooks and textures', async () => {
  const f = fixture();
  f.originals[1].material.customProgramCacheKey = () => { throw new Error('broken inherited hook'); };
  await assert.rejects(createIntroLighting({ THREE, ...f }), /broken inherited hook/);
  assert.equal(f.originals[0].material.onBeforeCompile, f.originals[0].previousCompile);
  assert.equal(f.originals[0].material.customProgramCacheKey, f.originals[0].previousCacheKey);
  assert(f.cleanMaps.every(map => map.disposeCount === 1));
});
const report = { ok: true, passed: checks.length, total: checks.length, checks,
  limitations: 'Lifecycle and shader-composition checks; actual baked pixels and GPU render are checked separately.' };
fs.writeFileSync(new URL('../docs/validation/intro-clean-lighting.json', import.meta.url), JSON.stringify(report, null, 2)+'\n');
console.log(`${checks.length}/${checks.length} clean-intro lighting checks passed`);
