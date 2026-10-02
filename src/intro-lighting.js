// Blender-baked architecture, desktop and rug maps without absent props.
// This only crossfades real UV-matched textures; it never lifts/clamps RGB.
export async function createIntroLighting({ THREE, renderer, room, loader, profile = null }) {
  const revision = profile?.revision ?? 16;
  const directory = profile?.directory ?? '/textures/intro-clean-v16';
  const rgbm = profile?.encoding === 'rgbm';
  const logrgb = profile?.encoding === 'logrgb';
  const encoded = rgbm || logrgb;
  if (rgbm && profile.rgbmRange !== 32) throw new Error('Clean intro requires RGBM range 32.');
  if (logrgb && (profile.radianceRange !== 32 || profile.logGain !== 256)) throw new Error('Clean intro requires LogRGB range 32 and gain 256.');
  const shadowMix = { value: 0 }, bindings = [], textures = new Map();
  const materials = new Map();
  room.traverse(node => {
    if (!node.isMesh) return;
    for (const material of [].concat(node.material)) {
      const match = material.name.match(/^WEB8_LIGHTMAP_(0|1|8)(?:[._].*)?$/);
      if (match) materials.set(material, Number(match[1]));
    }
  });
  if (new Set(materials.values()).size !== 3) throw new Error('Clean intro lighting requires receiver atlases 0, 1 and 8.');
  const results = await Promise.allSettled([0, 1, 8].map(async slot => {
    const texture = await loader.loadAsync(`${directory}/day-${slot}.ktx2`);
    texture.name = `INTRO_CLEAN_DAY_${slot}`;
    texture.colorSpace = encoded ? THREE.NoColorSpace : THREE.SRGBColorSpace;
    texture.flipY = false;
    texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
    texture.generateMipmaps = false;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.needsUpdate = true;
    textures.set(slot, texture);
    renderer.initTexture(texture);
  }));
  const failed = results.find(result => result.status === 'rejected');
  if (failed) {
    textures.forEach(texture => texture.dispose());
    throw new Error(`Clean opening textures could not load: ${failed.reason?.message || failed.reason}`);
  }
  const sample = 'diffuseColor *= sampledDiffuseColor;';
  try { for (const [material, slot] of materials) {
    const previousCompile = material.onBeforeCompile;
    const previousCacheKey = material.customProgramCacheKey;
    const cacheKey = previousCacheKey.call(material);
    const binding = { material, previousCompile, previousCacheKey, active: true };
    const compile = function(shader, currentRenderer) {
      previousCompile.call(this, shader, currentRenderer);
      if (!binding.active) return;
      // The existing day/night hook has already expanded map_fragment here.
      if (!shader.fragmentShader.includes(sample)) throw new Error(`Missing dual-lighting sample for ${material.name}`);
      shader.uniforms.uIntroCleanMap = { value: textures.get(slot) };
      shader.uniforms.uIntroShadowMix = shadowMix;
      if (encoded && !shader.fragmentShader.includes('vec4 atelierDecodeBaked(')) throw new Error('Encoded clean intro requires the matching dual-lighting decoder.');
      shader.fragmentShader = `uniform sampler2D uIntroCleanMap;\nuniform float uIntroShadowMix;\n${shader.fragmentShader}`
        .replace(sample, `sampledDiffuseColor = mix(${encoded ? 'atelierDecodeBaked(texture2D(uIntroCleanMap, vMapUv))' : 'texture2D(uIntroCleanMap, vMapUv)'}, sampledDiffuseColor, uIntroShadowMix);\n${sample}`);
    };
    const key = () => `${cacheKey}|intro-clean-bake-${revision}-${slot}-${encoded ? profile.encoding : 'srgb'}`;
    Object.assign(binding, { compile, key });
    material.onBeforeCompile = compile; material.customProgramCacheKey = key;
    material.needsUpdate = true;
    bindings.push(binding);
  } } catch (error) {
    for (const binding of bindings) {
      const { material, previousCompile, previousCacheKey, compile, key } = binding;
      binding.active = false;
      if (material.onBeforeCompile === compile) material.onBeforeCompile = previousCompile;
      if (material.customProgramCacheKey === key) material.customProgramCacheKey = previousCacheKey;
      material.needsUpdate = true;
    }
    textures.forEach(texture => texture.dispose());
    throw error;
  }
  let restored = false, disposed = false;
  function restore() {
    if (restored) return;
    shadowMix.value = 1;
    for (const binding of bindings) {
      const { material, previousCompile, previousCacheKey, compile, key } = binding;
      binding.active = false;
      if (material.onBeforeCompile === compile) material.onBeforeCompile = previousCompile;
      if (material.customProgramCacheKey === key) material.customProgramCacheKey = previousCacheKey;
      material.needsUpdate = true;
    }
    restored = true;
  }
  return {
    setProgress(value) {
      if (!restored && Number.isFinite(value)) shadowMix.value = Math.max(0, Math.min(1, value));
    },
    restore,
    dispose() {
      if (disposed) return;
      restore(); textures.forEach(texture => texture.dispose()); textures.clear(); disposed = true;
    },
    getState: () => ({ revision, encoding: encoded ? profile.encoding : 'srgb', slots: [0, 1, 8], progress: shadowMix.value, restored, disposed,
      method: 'Blender receiver-only color bakes; no RGB grading', maps: textures.size }),
  };
}
