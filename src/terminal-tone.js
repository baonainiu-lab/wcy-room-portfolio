const installed = new WeakSet();

/** Preserve the native glTF BRDF/lights, then display its linear output with AgX.
 * Only the opt-in welcome terminal calls this; global renderer and About stay unchanged.
 */
export function createTerminalToneMapping({ THREE, model, exposure = 1 }) {
  if (!Number.isFinite(exposure) || exposure <= 0) throw new Error('Terminal AgX exposure must be positive.');
  const source = THREE.ShaderChunk.tonemapping_pars_fragment;
  const start = source.indexOf('const mat3 LINEAR_REC2020_TO_LINEAR_SRGB');
  const end = source.indexOf('vec3 NeutralToneMapping');
  if (start < 0 || end <= start) throw new Error('Three.js AgX source changed; terminal tone mapping requires review.');
  const library = source.slice(start, end)
    .replace(/\btoneMappingExposure\b/g, 'uTerminalExposure')
    .replace(/\bAgXToneMapping\b/g, 'terminalAgX')
    .replace(/\bagxDefaultContrastApprox\b/g, 'terminalAgXContrast')
    .replace(/\bLINEAR_REC2020_TO_LINEAR_SRGB\b/g, 'TERMINAL_REC2020_TO_SRGB')
    .replace(/\bLINEAR_SRGB_TO_LINEAR_REC2020\b/g, 'TERMINAL_SRGB_TO_REC2020');
  const materials = new Set(), bindings = [], uniform = { value: exposure };
  model.traverse(node => {
    if (node.isMesh) for (const material of [].concat(node.material)) {
      if (!/^TERMINAL_/.test(material.name)) continue;
      if (!material.isMeshStandardMaterial) throw new Error(`Terminal AgX requires a native PBR material: ${material.name}`);
      if (installed.has(material)) throw new Error(`Terminal AgX already installed: ${material.name}`);
      materials.add(material);
    }
  });
  if (!materials.size) throw new Error('Terminal AgX found no TERMINAL_* PBR materials.');
  let disposed = false;
  function dispose() {
    if (disposed) return; disposed = true;
    for (const binding of bindings) {
      const { material, previousCompile, previousKey, toneMapped, compile, key } = binding;
      binding.active = false;
      if (material.onBeforeCompile === compile) material.onBeforeCompile = previousCompile;
      if (material.customProgramCacheKey === key) material.customProgramCacheKey = previousKey;
      material.toneMapped = toneMapped; material.needsUpdate = true; installed.delete(material);
    }
  }
  try {
    for (const material of materials) {
      const previousCompile = material.onBeforeCompile, previousKey = material.customProgramCacheKey;
      const inheritedKey = previousKey.call(material);
      const binding = { material, previousCompile, previousKey, toneMapped: material.toneMapped, active: true };
      const compile = function(shader, renderer) {
        previousCompile.call(this, shader, renderer); if (!binding.active) return;
        if (!shader.fragmentShader.includes('#include <common>') || !shader.fragmentShader.includes('#include <tonemapping_fragment>')) throw new Error('Terminal PBR tone-mapping anchors changed.');
        shader.fragmentShader = shader.fragmentShader
          .replace('#include <common>', `#include <common>\nuniform float uTerminalExposure;\n${library}`)
          .replace('#include <tonemapping_fragment>', 'gl_FragColor.rgb = terminalAgX(max(gl_FragColor.rgb, vec3(0.0)));');
        shader.uniforms.uTerminalExposure = uniform;
      };
      const key = () => `${inheritedKey}|terminal-native-agx-v1`;
      Object.assign(binding, { compile, key }); bindings.push(binding);
      material.onBeforeCompile = compile; material.customProgramCacheKey = key;
      // The local AgX hook owns display conversion even while the welcome
      // renderer is being configured. It cannot also receive global tone mapping.
      material.toneMapped = false; material.needsUpdate = true; installed.add(material);
    }
  } catch (error) { dispose(); throw error; }
  return { dispose, getState: () => ({ ready: !disposed, materialCount: bindings.length, exposure: uniform.value,
    method: 'native PBR linear radiance, then one local AgX, then normal sRGB output',
    lightIntensitiesChanged: false, additionalPassesPerFrame: 0 }) };
}
