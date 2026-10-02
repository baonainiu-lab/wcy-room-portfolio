import gsap from 'gsap';

// Two actual Cycles lighting bakes share geometry and UVs. SRGBColorSpace maps
// are decoded by the GPU exactly as Three's stock map_fragment expects; mixing
// therefore takes place in linear space before Three's output conversion.
export async function createDualLighting({ THREE, renderer, objects, reducedMotion = false, onProgress = () => {}, profile = null }) {
  const revision = profile?.revision ?? 14;
  const blend = profile?.dayMixUniform ?? { value: 0 };
  const rgbm = profile?.encoding === 'rgbm';
  const logrgb = profile?.encoding === 'logrgb';
  const encoded = rgbm || logrgb;
  const rgbmRange = rgbm ? profile.rgbmRange : 0;
  if (rgbm && rgbmRange !== 32) throw new Error('Physical lighting requires RGBM range 32.');
  if (logrgb && (profile.radianceRange !== 32 || profile.logGain !== 256)) throw new Error('Physical lighting requires LogRGB range 32 and gain 256.');
  const isEncodedSlot = slot => encoded && typeof slot === 'number';
  // Some emitter atlases exceed the compact radiance range. Offline encoding
  // normalizes those maps; this multiplier reconstructs their actual light
  // energy before mixing endpoints, independently of any artistic grading.
  const nightRadianceScale = profile?.nightRadianceScale ?? {};
  for (const scale of Object.values(nightRadianceScale)) {
    if (!logrgb || !Number.isFinite(scale) || scale <= 0) throw new Error('Night radiance normalization requires LogRGB and positive finite scales.');
  }
  // These two atlases contain exterior geometry only (verified in preparation).
  // Grade their night endpoint separately so distant windows cannot overpower
  // the room. Day textures and all interior practical lights stay unchanged.
  const exteriorNightExposure = profile?.exteriorNightExposure ?? (encoded ? {} : { 5: 0.28, 6: 0.12 });
  // Room-only low-light grading retains the authored Cycles light pools and
  // bright fixtures. Exterior atlases and the window panorama keep their night
  // endpoint so improving small-prop legibility does not turn the sky to day.
  const interiorNightReadability = Math.min(1, Math.max(0, profile?.interiorNightReadability ?? 0));
  const bindings = [];
  const materials = new Set();
  objects.forEach((object) => object.traverse((node) => {
    if (node.isMesh) [].concat(node.material).forEach((material) => materials.add(material));
  }));
  const materialSlots = new Map();
  for (const material of materials) {
    const atlas = material.name.match(profile?.materialPattern ?? /^WEB8_LIGHTMAP_(\d+)(?:[._].*)?$/);
    const slot = atlas ? Number(atlas[1]) : /^WEB8_WINDOW_CITY(?:[._].*)?$/.test(material.name) ? 'window' : null;
    if (slot === null) continue;
    if (!material.isMeshBasicMaterial || !material.map) {
      throw new Error(`Lighting V8 requires an unlit, mapped material: ${material.name}`);
    }
    materialSlots.set(material, slot);
  }
  const presentSlots = new Set(materialSlots.values());
  const missingSlots = (profile?.slots ?? [...Array.from({ length: 8 }, (_, i) => i), 'window']).filter((slot) => !presentSlots.has(slot));
  if (missingSlots.length) throw new Error(`Lighting V8 materials missing: ${missingSlots.map((index) => index === 'window' ? 'WEB8_WINDOW_CITY' : `WEB8_LIGHTMAP_${index}`).join(', ')}`);
  // Dedicated precision atlases may be appended without sharing the window's
  // slot or changing the original eight lightmaps.
  const slots = [...presentSlots].sort((a, b) => a === 'window' ? 1 : b === 'window' ? -1 : a - b);

  const loader = profile?.loader ?? new THREE.TextureLoader();
  const anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
  let completed = 0;
  const results = await Promise.allSettled(slots.map(async (slot) => {
    const path = profile ? `${profile.directory}/day-${slot}.${profile.extension ?? "png"}` : slot === 'window' ? `/textures/lighting-v${revision}/window-day.png` : `/textures/lighting-v${revision}/day-${slot}.png`;
    const texture = await loader.loadAsync(path);
    texture.name = slot === 'window' ? 'WEB8_WINDOW_CITY_DAY' : `WEB8_LIGHTMAP_DAY_${slot}`;
    texture.flipY = false;
    texture.colorSpace = isEncodedSlot(slot) ? THREE.NoColorSpace : THREE.SRGBColorSpace;
    texture.anisotropy = anisotropy;
    texture.generateMipmaps = !texture.isCompressedTexture;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.needsUpdate = true;
    onProgress(++completed, slots.length);
    return texture;
  }));
  const failed = results.find((result) => result.status === 'rejected');
  if (failed) {
    results.forEach((result) => { if (result.status === 'fulfilled') result.value.dispose(); });
    throw new Error(`Day lighting textures could not load: ${failed.reason?.message || failed.reason}`);
  }
  const dayMaps = new Map(results.map((result, index) => [slots[index], result.value]));

  const sampleStatement = 'vec4 sampledDiffuseColor = texture2D( map, vMapUv );';
  const stockMapFragment = THREE.ShaderChunk.map_fragment;
  if (!stockMapFragment.includes(sampleStatement)) {
    dayMaps.forEach((texture) => texture.dispose());
    throw new Error('The Three.js map shader changed; the dual-lighting sampler needs review.');
  }
  const dualMapFragment = stockMapFragment.replace(sampleStatement, `
    vec4 sampledDiffuseColor;
    if (uLightingMix <= 0.0) {
      sampledDiffuseColor = atelierReadableNight(atelierDecodeBaked(texture2D(map, vMapUv)));
    } else if (uLightingMix >= 1.0) {
      sampledDiffuseColor = atelierDecodeBaked(texture2D(uDayMap, vMapUv));
    } else {
      vec4 nightColor = atelierReadableNight(atelierDecodeBaked(texture2D(map, vMapUv)));
      sampledDiffuseColor = mix(nightColor, atelierDecodeBaked(texture2D(uDayMap, vMapUv)), uLightingMix);
    }
  `);

  function restoreBindings() {
    for (const binding of bindings) {
      const { material, previousCompile, previousCacheKey, compile, key, nightMap, previousNightColorSpace } = binding;
      binding.active = false;
      if (material.onBeforeCompile === compile) material.onBeforeCompile = previousCompile;
      if (material.customProgramCacheKey === key) material.customProgramCacheKey = previousCacheKey;
      nightMap.colorSpace = previousNightColorSpace; nightMap.needsUpdate = true;
      material.needsUpdate = true;
    }
  }

  // Upload both endpoints before the entry animation. Day switching then only
  // changes one shared float, rather than triggering image decode or uploads.
  const nightMaps = new Set();
  try {
  dayMaps.forEach((texture) => renderer.initTexture(texture));
  for (const [material, slot] of materialSlots) {
    const nightMap = material.map;
    nightMap.anisotropy = anisotropy;
    const previousNightColorSpace = nightMap.colorSpace;
    nightMaps.add(nightMap);
    const previousCompile = material.onBeforeCompile;
    const previousCacheKey = material.customProgramCacheKey;
    const baseCacheKey = previousCacheKey.call(material);
    const binding = { material, previousCompile, previousCacheKey, nightMap, previousNightColorSpace, active: true };
    nightMap.colorSpace = isEncodedSlot(slot) ? THREE.NoColorSpace : THREE.SRGBColorSpace;
    nightMap.needsUpdate = true;
    const compile = (shader, currentRenderer) => {
      previousCompile.call(material, shader, currentRenderer);
      if (!binding.active) return;
      if (!shader.fragmentShader.includes('#include <map_fragment>')) {
        throw new Error(`Cannot patch the dual-lighting map shader for ${material.name}`);
      }
      shader.uniforms.uDayMap = { value: dayMaps.get(slot) };
      shader.uniforms.uBakedRGBMRange = { value: isEncodedSlot(slot) ? rgbmRange : 0 };
      shader.uniforms.uBakedLogGain = { value: logrgb && isEncodedSlot(slot) ? profile.logGain : 0 };
      shader.uniforms.uLightingMix = blend;
      shader.uniforms.uNightExposure = { value: (exteriorNightExposure[slot] ?? 1) * (nightRadianceScale[slot] ?? 1) };
      shader.uniforms.uNightReadability = { value: slot !== 'window' && !(slot in exteriorNightExposure) ? interiorNightReadability : 0 };
      const nightFunction = `
        vec4 atelierDecodeBaked(vec4 color) {
          if (uBakedLogGain > 0.0) return vec4((exp2(color.rgb * log2(8193.0)) - 1.0) / uBakedLogGain, 1.0);
          if (uBakedRGBMRange > 0.0) return vec4(color.rgb * color.a * uBakedRGBMRange, 1.0);
          return color;
        }
        vec4 atelierReadableNight(vec4 color) {
          color.rgb *= uNightExposure;
          // A shared scalar preserves the baked hue and actual light pools.
          // Unlike a constant RGB lift, zero remains zero and black materials
          // cannot acquire a uniform self-lit amber film. The peak-channel
          // shoulder also protects saturated warm emitters, not only whites.
          float peak = max(color.r, max(color.g, color.b));
          float shoulder = 1.0 - clamp(peak / 0.45, 0.0, 1.0);
          color.rgb *= 1.0 + uNightReadability * 2.4 * shoulder * shoulder;
          return color;
        }
      `;
      shader.fragmentShader = `uniform sampler2D uDayMap;\nuniform float uBakedRGBMRange;\nuniform float uBakedLogGain;\nuniform float uLightingMix;\nuniform float uNightExposure;\nuniform float uNightReadability;\n${shader.fragmentShader}`
        .replace('void main() {', `${nightFunction}\nvoid main() {`)
        .replace('#include <map_fragment>', dualMapFragment);
    };
    const key = () => `${baseCacheKey}|dual-lighting-v${revision}-precision-4-${isEncodedSlot(slot) ? profile.encoding : 'srgb'}`;
    Object.assign(binding, { compile, key });
    material.onBeforeCompile = compile; material.customProgramCacheKey = key;
    material.needsUpdate = true;
    bindings.push(binding);
  }
  nightMaps.forEach((texture) => renderer.initTexture(texture));
  } catch (error) {
    restoreBindings(); dayMaps.forEach(texture => texture.dispose()); throw error;
  }

  let disposed = false, clockDriven = false;
  return {
    setDayMix(value) {
      if (disposed || !Number.isFinite(value)) return;
      if (!clockDriven) { gsap.killTweensOf(blend); clockDriven = true; }
      blend.value = Math.min(1, Math.max(0, value));
    },
    setTheme(isDay, duration = 1.5) {
      if (disposed) return;
      clockDriven = false;
      const endpoint = isDay ? 1 : 0;
      gsap.killTweensOf(blend);
      gsap.to(blend, {
        value: endpoint,
        duration: reducedMotion ? 0.01 : duration,
        ease: 'power2.inOut',
        overwrite: true,
        onComplete: () => { blend.value = endpoint; },
      });
    },
    getState() {
      return { revision, ready: !disposed, dayMix: blend.value, dayTextureCount: dayMaps.size, materialCount: bindings.length, exteriorNightExposure, interiorNightReadability, encoding: encoded ? profile.encoding : 'srgb', rgbmRange, ...(logrgb ? { radianceRange: 32, logGain: 256, nightRadianceScale } : {}) };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      gsap.killTweensOf(blend);
      restoreBindings();
      dayMaps.forEach((texture) => texture.dispose());
    },
  };
}
