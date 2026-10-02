import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

// Opt-in only: the approved About atelier deliberately retains its own finish.
const FAMILIES = { room: /^WEB8_LIGHTMAP_(\d+)(?:[._].*)?$/, gallery: /^GALLERY_LIGHTMAP_(\d+)(?:[._].*)?$/ };
const GLASS_FAMILIES = { room: /^(?:WEB8_CLEAR_)?WEB8_GLASS_/, gallery: /^GALLERY_(?:ARCH_GLASS|CLEAR)(?:[._].*)?$/ };
const installed = new WeakSet();

function shaderLibrary(THREE, probe) {
  const image = probe.image, maxMip = Math.log2(image.height) - 2;
  if (!Number.isInteger(maxMip) || maxMip < 4) throw new Error('Physical surface requires a valid Three.js CubeUV PMREM.');
  // Use the installed Three version's PMREM lookup and AgX, with private names
  // so a previous compile hook can safely own another environment/tone mapper.
  let cube = THREE.ShaderChunk.cube_uv_reflection_fragment
    .replace('#ifdef ENVMAP_TYPE_CUBE_UV', '').replace(/#endif\s*$/, '');
  for (const name of ['getFace', 'getUV', 'bilinearCubeUV', 'roughnessToMip', 'textureCubeUV']) cube = cube.replace(new RegExp(`\\b${name}\\b`, 'g'), `surface_${name}`);
  cube = cube.replace(/\bcubeUV_/g, 'surface_cubeUV_').replace(/\bCUBEUV_/g, 'SURFACE_CUBEUV_');
  const toneSource = THREE.ShaderChunk.tonemapping_pars_fragment;
  const begin = toneSource.indexOf('const mat3 LINEAR_REC2020_TO_LINEAR_SRGB');
  const end = toneSource.indexOf('vec3 NeutralToneMapping');
  if (begin < 0 || end < begin) throw new Error('Three.js AgX shader changed; review the physical surface tone mapper.');
  const tone = toneSource.slice(begin, end)
    .replace(/\btoneMappingExposure\b/g, 'uSurfaceExposure')
    .replace(/\bAgXToneMapping\b/g, 'surfaceAgX')
    .replace(/\bagxDefaultContrastApprox\b/g, 'surfaceAgXContrast')
    .replace(/\bLINEAR_REC2020_TO_LINEAR_SRGB\b/g, 'SURFACE_REC2020_TO_SRGB')
    .replace(/\bLINEAR_SRGB_TO_LINEAR_REC2020\b/g, 'SURFACE_SRGB_TO_REC2020');
  return `
#define SURFACE_CUBEUV_TEXEL_WIDTH ${1 / (3 * Math.max(2 ** maxMip, 7 * 16))}
#define SURFACE_CUBEUV_TEXEL_HEIGHT ${1 / image.height}
#define SURFACE_CUBEUV_MAX_MIP ${maxMip.toFixed(1)}
uniform sampler2D uSurfaceSpecular;
uniform sampler2D uSurfaceNormal;
uniform sampler2D uSurfaceReflectionDay;
uniform sampler2D uSurfaceReflectionNight;
uniform float uSurfaceDayMix;
uniform float uSurfaceExposure;
uniform float uSurfaceReflectionStrength;
uniform mat3 uSurfaceReflectionRotation;
varying vec3 vSurfaceNormal;
varying vec3 vSurfaceViewPosition;
${cube}
${tone}
vec3 surfaceNormal(vec2 uv) {
  vec3 n = normalize(vSurfaceNormal);
  n *= gl_FrontFacing ? 1.0 : -1.0;
  vec3 q0 = dFdx(-vSurfaceViewPosition), q1 = dFdy(-vSurfaceViewPosition);
  vec2 st0 = dFdx(uv), st1 = dFdy(uv);
  vec3 q1p = cross(q1, n), q0p = cross(n, q0);
  vec3 t = q1p * st0.x + q0p * st1.x, b = q1p * st0.y + q0p * st1.y;
  float det = max(dot(t, t), dot(b, b));
  // A hidden zero-area island has no usable UV tangent; retain its mesh normal.
  if (det < 1e-30) return n;
  float scale = inversesqrt(det);
  vec3 mapN = texture2D(uSurfaceNormal, uv).rgb * 2.0 - 1.0;
  return normalize(mat3(t * scale, b * scale, n) * mapN);
}
vec3 surfaceSpecular(vec2 uv) {
  vec4 surface = texture2D(uSurfaceSpecular, uv);
  vec3 f0 = clamp(surface.rgb, 0.0, 1.0);
  vec3 n = surfaceNormal(uv), v = normalize(vSurfaceViewPosition);
  // Normal derivatives suppress subpixel normal sparkle at grazing angles.
  vec3 dn = max(abs(dFdx(n)), abs(dFdy(n)));
  float roughness = clamp(surface.a + max(max(dn.x, dn.y), dn.z), .0525, 1.0);
  float nv = clamp(dot(n, v), 0.0, 1.0);
  vec4 r = roughness * vec4(-1.0, -.0275, -.572, .022) + vec4(1.0, .0425, 1.04, -.04);
  float a004 = min(r.x * r.x, exp2(-9.28 * nv)) * r.x + r.y;
  vec2 fab = vec2(-1.04, 1.04) * a004 + r.zw;
  vec3 brdf = max(f0 * fab.x + fab.y, 0.0);
  vec3 ray = normalize(mix(reflect(-v, n), n, roughness * roughness));
  ray = uSurfaceReflectionRotation * inverseTransformDirection(ray, viewMatrix);
  vec3 radiance;
  if (uSurfaceDayMix <= 0.0) radiance = surface_textureCubeUV(uSurfaceReflectionNight, ray, roughness).rgb;
  else if (uSurfaceDayMix >= 1.0) radiance = surface_textureCubeUV(uSurfaceReflectionDay, ray, roughness).rgb;
  else radiance = mix(surface_textureCubeUV(uSurfaceReflectionNight, ray, roughness).rgb,
                     surface_textureCubeUV(uSurfaceReflectionDay, ray, roughness).rgb, uSurfaceDayMix);
  return radiance * brdf * uSurfaceReflectionStrength;
}
`;
}

function makeThinGlass({ THREE, original, library, uniforms, profile, probeHeight }) {
  const material = new THREE.MeshBasicMaterial({ name: original.name, color: original.color ?? 0xffffff,
    transparent: true, opacity: 1, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
  material.forceSinglePass = true;
  material.userData = { ...original.userData, physicalThinGlass: true };
  // This is a thin dielectric approximation: environment reflections with
  // Fresnel coverage, ordinary alpha transmission, no refraction render target.
  const smoke = /smoke/i.test(original.name);
  const roughness = original.isMeshStandardMaterial ? original.roughness : (smoke ? .14 : .085);
  const absorption = profile.absorption ?? (smoke ? .085 : .028);
  const glassUniforms = { ...uniforms,
    uSurfaceGlassRoughness: { value: THREE.MathUtils.clamp(roughness, .055, .35) },
    uSurfaceGlassAbsorption: { value: THREE.MathUtils.clamp(absorption, 0, .3) },
    uSurfaceGlassF0: { value: .04 },
  };
  material.onBeforeCompile = shader => {
    if (!shader.vertexShader.includes('#include <project_vertex>') || !shader.fragmentShader.includes('#include <opaque_fragment>')) throw new Error('Thin glass shader anchors changed.');
    shader.vertexShader = `varying vec3 vSurfaceNormal;\nvarying vec3 vSurfaceViewPosition;\n${shader.vertexShader}`
      .replace('#include <project_vertex>', '#include <project_vertex>\nvSurfaceNormal = normalMatrix * normal;\nvSurfaceViewPosition = -mvPosition.xyz;');
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>\n${library}
uniform float uSurfaceGlassRoughness;
uniform float uSurfaceGlassAbsorption;
uniform float uSurfaceGlassF0;`)
      .replace('#include <opaque_fragment>', `
vec3 glassN = normalize(vSurfaceNormal) * (gl_FrontFacing ? 1.0 : -1.0);
vec3 glassV = normalize(vSurfaceViewPosition);
float glassNV = clamp(abs(dot(glassN, glassV)), 0.0, 1.0);
float glassF = uSurfaceGlassF0 + (1.0 - uSurfaceGlassF0) * pow(1.0 - glassNV, 5.0);
float glassAlpha = glassF + (1.0 - glassF) * uSurfaceGlassAbsorption;
vec3 glassRay = uSurfaceReflectionRotation * inverseTransformDirection(reflect(-glassV, glassN), viewMatrix);
vec3 glassRadiance;
if (uSurfaceDayMix <= 0.0) glassRadiance = surface_textureCubeUV(uSurfaceReflectionNight, glassRay, uSurfaceGlassRoughness).rgb;
else if (uSurfaceDayMix >= 1.0) glassRadiance = surface_textureCubeUV(uSurfaceReflectionDay, glassRay, uSurfaceGlassRoughness).rgb;
else glassRadiance = mix(surface_textureCubeUV(uSurfaceReflectionNight, glassRay, uSurfaceGlassRoughness).rgb,
                        surface_textureCubeUV(uSurfaceReflectionDay, glassRay, uSurfaceGlassRoughness).rgb, uSurfaceDayMix);
// Divide by coverage so ordinary alpha blending applies Fresnel exactly once.
outgoingLight = surfaceAgX(max((glassRadiance * glassF * uSurfaceReflectionStrength
  + diffuse * uSurfaceGlassAbsorption * (1.0 - glassF) * .16) / max(glassAlpha, .001), vec3(0.0)));
diffuseColor.a = glassAlpha;
#include <opaque_fragment>`);
    Object.assign(shader.uniforms, glassUniforms);
  };
  material.customProgramCacheKey = () => `physical-thin-glass-v1-${probeHeight}`;
  return material;
}

/** Linear diffuse+emission RGBM bakes + view-dependent GGX IBL, one draw pass.
 * Install BEFORE dual lighting, and install clean-intro lighting LAST.
 * Data maps: specular RGB=linear F0, A=perceptual roughness; normal RGB=GL TBN.
 * Day/night HDRs are prefiltered once. About materials can never match this API.
 */
export async function createPhysicalSurface({ THREE, renderer, objects, loader, profile, hdrLoader = new RGBELoader(), pmremFactory = () => new THREE.PMREMGenerator(renderer) }) {
  const pattern = FAMILIES[profile?.family];
  const validEncoding = profile?.encoding === 'rgbm' && profile.rgbmRange === 32
    || profile?.encoding === 'logrgb' && profile.radianceRange === 32 && profile.logGain === 256;
  if (!pattern || !profile.directory || !validEncoding) {
    throw new Error('Physical surface requires room/gallery family and a supported linear-radiance profile.');
  }
  if (!loader?.loadAsync) throw new Error('Physical surface requires the existing KTX2 loader.');
  const materials = new Map(), glassSources = new Set(), glassNodes = [];
  for (const object of objects) object.traverse(node => {
    if (!node.isMesh) return;
    if (profile.glass?.enabled === true && [].concat(node.material).some(material => GLASS_FAMILIES[profile.family].test(material.name))) {
      if (!node.geometry.attributes.normal) throw new Error(`Thin glass requires original mesh normals: ${node.name}`);
      glassNodes.push({ node, original: node.material });
      for (const material of [].concat(node.material)) if (GLASS_FAMILIES[profile.family].test(material.name)) {
        if (installed.has(material)) throw new Error(`Physical glass already installed: ${material.name}`);
        glassSources.add(material);
      }
    }
    for (const material of [].concat(node.material)) {
      const match = material.name.match(pattern); if (!match) continue;
      if (installed.has(material)) throw new Error(`Physical surface already installed: ${material.name}`);
      if (!material.isMeshBasicMaterial || !material.map || !node.geometry.attributes.normal || !node.geometry.attributes.uv) {
        throw new Error(`Physical surface needs mapped Basic material, UVs and normals: ${material.name}`);
      }
      materials.set(material, Number(match[1]));
    }
  });
  const slots = [...new Set(materials.values())].sort((a,b) => a-b);
  if (!slots.length || profile.slots?.some(slot => !slots.includes(slot))) throw new Error('Physical surface atlas slots are missing.');
  const data = new Map(), textures = new Set(), targets = [], bindings = [], glassMaterials = new Map(), glassBindings = [];
  const dayMix = { value: 1 };
  let disposed = false;
  function restoreBindings() {
    for (const binding of bindings) {
      binding.active = false;
      const { material, previousCompile, previousKey, compile, key, toneMapped } = binding;
      if (material.onBeforeCompile === compile) material.onBeforeCompile = previousCompile;
      if (material.customProgramCacheKey === key) material.customProgramCacheKey = previousKey;
      material.toneMapped = toneMapped; material.needsUpdate = true; installed.delete(material);
    }
  }
  function dispose() {
    if (disposed) return;
    disposed = true; restoreBindings();
    for (const { node, original, replacement } of glassBindings) if (node.material === replacement) node.material = original;
    for (const [original, replacement] of glassMaterials) { replacement.dispose(); installed.delete(original); }
    textures.forEach(texture => texture.dispose()); targets.forEach(target => target.dispose());
  }
  try {
    const loaded = await Promise.allSettled(slots.map(async slot => {
      const pair = await Promise.allSettled(['specular', 'normal'].map(async kind => {
        const texture = await loader.loadAsync(`${profile.directory}/${kind}-${slot}.ktx2`);
        textures.add(texture); texture.flipY = false; texture.colorSpace = THREE.NoColorSpace;
        texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
        texture.generateMipmaps = false; texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter; texture.needsUpdate = true;
        renderer.initTexture(texture); return texture;
      }));
      const failure = pair.find(result => result.status === 'rejected'); if (failure) throw failure.reason;
      const [specular, normal] = pair.map(result => result.value);
      if (specular.image.width !== normal.image.width || specular.image.height !== normal.image.height) throw new Error(`Physical surface data dimensions differ at atlas ${slot}.`);
      data.set(slot, { specular, normal });
    }));
    const failure = loaded.find(result => result.status === 'rejected'); if (failure) throw failure.reason;
    const hdrPaths = [profile.reflectionDay ?? 'reflection-day.hdr', profile.reflectionNight ?? 'reflection-night.hdr']
      .map(path => path.startsWith('/') ? path : `${profile.directory}/${path}`);
    const hdrs = await Promise.allSettled(hdrPaths.map(async path => {
      const texture = await hdrLoader.loadAsync(path); textures.add(texture); return texture;
    }));
    const failedHdr = hdrs.find(result => result.status === 'rejected'); if (failedHdr) throw failedHdr.reason;
    const generator = pmremFactory();
    try {
      for (const result of hdrs) {
        const texture = result.value; texture.mapping = THREE.EquirectangularReflectionMapping;
        targets.push(generator.fromEquirectangular(texture)); texture.dispose(); textures.delete(texture);
      }
    } finally { generator.dispose(); }
    const [day, night] = targets.map(target => target.texture);
    if (day.image.width !== night.image.width || day.image.height !== night.image.height) throw new Error('Physical surface reflection probes require matching PMREM dimensions.');
    const library = shaderLibrary(THREE, day);
    const rotation = new THREE.Matrix3().setFromMatrix4(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(profile.reflectionYawDegrees ?? 0)));
    const exposure = { value: profile.exposure ?? 1 }, strength = { value: profile.reflectionStrength ?? 1 };
    for (const [material, slot] of materials) {
      const previousCompile = material.onBeforeCompile, previousKey = material.customProgramCacheKey;
      const baseKey = previousKey.call(material), toneMapped = material.toneMapped;
      const binding = { material, previousCompile, previousKey, toneMapped, active: true };
      const compile = function(shader, currentRenderer) {
        previousCompile.call(this, shader, currentRenderer); if (!binding.active) return;
        if (!shader.vertexShader.includes('#include <project_vertex>') || !shader.fragmentShader.includes('#include <opaque_fragment>')) throw new Error(`Physical surface shader anchors changed: ${material.name}`);
        shader.vertexShader = `varying vec3 vSurfaceNormal;\nvarying vec3 vSurfaceViewPosition;\n${shader.vertexShader}`
          .replace('#include <project_vertex>', `#include <project_vertex>\nvSurfaceNormal = normalMatrix * normal;\nvSurfaceViewPosition = -mvPosition.xyz;`);
        // Keep map_fragment untouched for the later dual+clean-intro hooks.
        shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>\n${library}`)
          .replace('#include <opaque_fragment>', `outgoingLight = surfaceAgX(max(outgoingLight + surfaceSpecular(vMapUv), vec3(0.0)));\n#include <opaque_fragment>`);
        Object.assign(shader.uniforms, {
          uSurfaceSpecular: { value: data.get(slot).specular }, uSurfaceNormal: { value: data.get(slot).normal },
          uSurfaceReflectionDay: { value: day }, uSurfaceReflectionNight: { value: night },
          uSurfaceDayMix: dayMix, uSurfaceExposure: exposure, uSurfaceReflectionStrength: strength,
          uSurfaceReflectionRotation: { value: rotation },
        });
      };
      const key = () => `${baseKey}|physical-surface-v1-${profile.family}-${slot}-${day.image.height}`;
      Object.assign(binding, { compile, key }); bindings.push(binding);
      material.onBeforeCompile = compile; material.customProgramCacheKey = key;
      material.toneMapped = false; material.needsUpdate = true; installed.add(material);
    }
    const glassUniforms = {
      uSurfaceReflectionDay: { value: day }, uSurfaceReflectionNight: { value: night },
      uSurfaceDayMix: dayMix, uSurfaceExposure: exposure, uSurfaceReflectionStrength: strength,
      uSurfaceReflectionRotation: { value: rotation },
    };
    for (const original of glassSources) {
      const replacement = makeThinGlass({ THREE, original, library, uniforms: glassUniforms, profile: profile.glass, probeHeight: day.image.height });
      glassMaterials.set(original, replacement); installed.add(original);
    }
    for (const { node, original } of glassNodes) {
      const replacement = Array.isArray(original) ? original.map(material => glassMaterials.get(material) ?? material) : glassMaterials.get(original);
      glassBindings.push({ node, original, replacement }); node.material = replacement;
    }
    return {
      getDayMixUniform: () => dayMix,
      setDayMix(value) { if (!disposed && Number.isFinite(value)) dayMix.value = THREE.MathUtils.clamp(value, 0, 1); },
      getReplacedMaterials: () => [...glassMaterials].map(([original, material]) => ({ original, material })),
      getState: () => ({ ready: !disposed, family: profile.family, directory: profile.directory, encoding: profile.encoding,
        ...(profile.encoding === 'rgbm' ? { rgbmRange: 32 } : { radianceRange: 32, logGain: 256 }),
        materialCount: bindings.length, slots, dataTextureCount: textures.size, reflectionProbeCount: targets.length,
        glass: { enabled: profile.glass?.enabled === true, materialCount: glassMaterials.size, meshCount: glassBindings.length,
          mode: 'thin dielectric Fresnel reflection with alpha transmission; no refraction target' },
        dayMix: dayMix.value, exposure: exposure.value, additionalScenePassesPerFrame: 0, shader: 'diffuse+emission plus GGX PMREM, one AgX mapping', hdrPaths }),
      dispose,
    };
  } catch (error) {
    dispose(); throw new Error(`Physical surface ${profile.family} could not initialize; retain the previous complete asset release: ${error.message}`, { cause: error });
  }
}
