import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';

const SCREEN_MATERIAL = /^WEB8_IMAGE_MAT_Rendered_3D_ScreenArtwork(?:[._].*)?$/;
const WINDOW_MATERIAL = /^WEB8_WINDOW_CITY(?:[._].*)?$/;
const HOLD_SECONDS = 5.8;
const FADE_SECONDS = 1.35;
const SLIDE_SECONDS = HOLD_SECONDS + FADE_SECONDS;
const SCREEN_ASPECT = 2.91 / 1.2;
const SCREEN_SAMPLE = 'vec4 sampledDiffuseColor = texture2D( map, vMapUv );';

const screenFunctions = /* glsl */`
uniform sampler2D uLiveScreenA;
uniform sampler2D uLiveScreenB;
uniform float uLiveScreenAspectA;
uniform float uLiveScreenAspectB;
uniform float uLiveScreenMix;
uniform float uLiveScreenDay;
vec4 liveScreenSample(sampler2D sourceMap, vec2 uv, float aspect) {
  vec2 fit = vec2(${SCREEN_ASPECT.toFixed(6)} / aspect, 1.0);
  if (fit.x < 1.0) fit = vec2(1.0, 1.0 / fit.x);
  vec2 sampleUv = (uv - 0.5) * fit + 0.5;
  float inside = step(0.0, sampleUv.x) * step(sampleUv.x, 1.0)
    * step(0.0, sampleUv.y) * step(sampleUv.y, 1.0);
  vec4 image = texture2D(sourceMap, clamp(sampleUv, vec2(0.0), vec2(1.0)));
  return vec4(mix(vec3(0.0025, 0.004, 0.005), image.rgb, inside), 1.0);
}
`;

const windowFunctions = /* glsl */`
uniform float uLiveWindowTime;
uniform vec2 uLiveWindowParallax;
uniform float uLiveWindowMotion;
float liveWindowHash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float liveWindowNoise(vec2 p) {
  vec2 cell = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(liveWindowHash(cell), liveWindowHash(cell + vec2(1.0, 0.0)), f.x),
    mix(liveWindowHash(cell + vec2(0.0, 1.0)), liveWindowHash(cell + vec2(1.0, 1.0)), f.x), f.y);
}
float liveWindowEdge(vec2 uv) {
  vec2 edge = smoothstep(vec2(0.0), vec2(0.075), uv)
    * (1.0 - smoothstep(vec2(0.925), vec2(1.0), uv));
  return edge.x * edge.y;
}
vec2 liveWindowCityUv(vec2 uv) {
  // Less than a few image pixels; window borders stay exactly pinned.
  float depth = mix(0.22, 1.0, smoothstep(0.45, 0.94, uv.y));
  return clamp(uv + uLiveWindowParallax * depth * liveWindowEdge(uv), vec2(0.0), vec2(1.0));
}
float liveWindowTraffic(vec2 uv, float phase, float lane, float direction) {
  float travel = fract(phase);
  float x = mix(0.035, 0.555, direction > 0.0 ? travel : 1.0 - travel);
  float y = lane - x * 0.008;
  vec2 p = uv - vec2(x, y);
  float head = exp(-dot(p / vec2(0.0032, 0.0017), p / vec2(0.0032, 0.0017)));
  float trail = exp(-abs(p.x + direction * 0.009) / 0.011)
    * exp(-pow(p.y / 0.0012, 2.0)) * (1.0 - smoothstep(0.0, 0.004, p.x * direction));
  float arrival = smoothstep(0.0, 0.06, travel) * (1.0 - smoothstep(0.94, 1.0, travel));
  return (head + trail * 0.22) * arrival;
}
vec3 liveWindowAtmosphere(vec3 color, vec2 uv, float dayMix) {
  if (uLiveWindowMotion < 0.5) return color;
  float edge = liveWindowEdge(uv);
  vec2 distant = uv + uLiveWindowParallax * 2.0;
  vec2 close = uv + uLiveWindowParallax * 5.0;
  // The original daylight render masks the sky, leaving building silhouettes intact.
  vec3 dayReference = texture2D(uDayMap, liveWindowCityUv(uv)).rgb;
  float sky = smoothstep(0.22, 0.43, dot(dayReference, vec3(0.2126, 0.7152, 0.0722)))
    * (1.0 - smoothstep(0.69, 0.79, uv.y));
  vec2 wind = vec2(uLiveWindowTime * 0.021, -uLiveWindowTime * 0.003);
  float cloud = liveWindowNoise(distant * vec2(5.0, 8.0) - wind) * 0.7
    + liveWindowNoise(distant * vec2(10.0, 17.0) - wind * 1.4) * 0.3;
  float cloudAmount = smoothstep(0.43, 0.79, cloud) * sky * edge * mix(0.15, 0.31, dayMix);
  color = mix(color, mix(vec3(0.034, 0.049, 0.078), vec3(0.76, 0.81, 0.83), dayMix), cloudAmount);
  float mist = liveWindowNoise(close * vec2(7.0, 15.0) - vec2(uLiveWindowTime * 0.04, 0.0));
  float mistAmount = smoothstep(0.76, 0.98, uv.y) * smoothstep(0.30, 0.78, mist) * edge * mix(0.12, 0.22, dayMix);
  color = mix(color, mix(vec3(0.027, 0.040, 0.069), vec3(0.66, 0.73, 0.77), dayMix), mistAmount);
  if (uv.x < 0.59 && uv.y > 0.712 && uv.y < 0.84) {
    float nearTraffic = liveWindowTraffic(uv, uLiveWindowTime * 0.047 + 0.10, 0.825, 1.0)
      + liveWindowTraffic(uv, uLiveWindowTime * 0.047 + 0.61, 0.825, 1.0);
    float farTraffic = liveWindowTraffic(uv, uLiveWindowTime * 0.033 + 0.28, 0.731, -1.0)
      + liveWindowTraffic(uv, uLiveWindowTime * 0.033 + 0.76, 0.731, -1.0);
    color += (vec3(0.84, 0.44, 0.14) * nearTraffic + vec3(0.38, 0.60, 0.85) * farTraffic)
      * edge * mix(0.72, 0.44, dayMix);
  }
  return color;
}
`;

/** Initialize after createDualLighting, preserving its compiled day/night endpoints. */
export async function createLiveRoomSurfaces({ THREE, renderer, room, reducedMotion = false }) {
  const roots = Array.isArray(room) ? room : [room];
  const screens = new Set(), windows = new Set();
  let windowMesh = null;
  roots.filter(Boolean).forEach((root) => root.traverse((node) => {
    if (!node.isMesh) return;
    for (const material of [].concat(node.material)) {
      if (SCREEN_MATERIAL.test(material.name)) screens.add(material);
      if (WINDOW_MATERIAL.test(material.name)) { windows.add(material); windowMesh ??= node; }
    }
  }));
  if (!screens.size || !windows.size) throw new Error('Live surfaces require the V14 independent screen and window materials.');
  for (const material of [...screens, ...windows]) {
    if (!material.isMeshBasicMaterial || !material.map) throw new Error(`Live surface is not mapped/unlit: ${material.name}`);
  }
  for (const material of windows) {
    if (!material.customProgramCacheKey().includes('dual-lighting')) {
      throw new Error('Create live room surfaces after createDualLighting has bound the window.');
    }
  }
  if (!THREE.ShaderChunk.map_fragment.includes(SCREEN_SAMPLE)) throw new Error('Three.js map shader changed; live screen sampler needs review.');

  const loader = new KTX2Loader().setTranscoderPath('/basis/').setWorkerLimit(1).detectSupport(renderer);
  const results = await Promise.allSettled(['day', 'night'].map((state) =>
    loader.loadAsync(`/textures/live-room/gallery-${state}.ktx2`)));
  loader.dispose();
  const failed = results.find((result) => result.status === 'rejected');
  if (failed) {
    results.forEach((result) => { if (result.status === 'fulfilled') result.value.dispose(); });
    throw new Error(`Scene-study images could not load: ${failed.reason?.message || failed.reason}`);
  }
  const ownedTextures = results.map((result) => result.value);
  ownedTextures.forEach((texture, index) => {
    texture.name = `ROOM_SCENE_STUDY_GALLERY_${index ? 'NIGHT' : 'DAY'}`;
    texture.flipY = false;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.needsUpdate = true;
    renderer.initTexture(texture);
  });
  const originalScreen = screens.values().next().value.map;
  const slides = [originalScreen, ...ownedTextures];
  const slideLabels = ['原创橙蓝雕塑场景', '日光长廊日景实模', '日光长廊夜景实模'];
  const aspectOf = (texture) => texture.image?.width && texture.image?.height ? texture.image.width / texture.image.height : 2.4;
  const uniforms = {
    uLiveScreenA: { value: slides[0] }, uLiveScreenB: { value: slides[1] },
    uLiveScreenAspectA: { value: aspectOf(slides[0]) }, uLiveScreenAspectB: { value: aspectOf(slides[1]) },
    uLiveScreenMix: { value: 0 }, uLiveScreenDay: { value: 0 },
    uLiveWindowTime: { value: 0 }, uLiveWindowParallax: { value: new THREE.Vector2() },
    uLiveWindowMotion: { value: reducedMotion ? 0 : 1 },
  };
  const bindings = [];
  const install = (material, kind) => {
    const previousCompile = material.onBeforeCompile;
    const previousCacheKey = material.customProgramCacheKey;
    const baseCacheKey = previousCacheKey.call(material);
    material.onBeforeCompile = (shader, currentRenderer) => {
      previousCompile.call(material, shader, currentRenderer);
      Object.assign(shader.uniforms, uniforms);
      if (kind === 'screen') {
        if (!shader.fragmentShader.includes('#include <map_fragment>')) throw new Error('Screen map fragment was replaced by another effect.');
        const map = THREE.ShaderChunk.map_fragment.replace(SCREEN_SAMPLE, `
          vec4 sampledDiffuseColor = mix(
            liveScreenSample(uLiveScreenA, vMapUv, uLiveScreenAspectA),
            liveScreenSample(uLiveScreenB, vMapUv, uLiveScreenAspectB), uLiveScreenMix);
          sampledDiffuseColor.rgb *= mix(0.76, 1.0, uLiveScreenDay);
        `);
        shader.fragmentShader = screenFunctions + shader.fragmentShader.replace('#include <map_fragment>', map);
      } else {
        if (!shader.uniforms.uDayMap || !shader.uniforms.uLightingMix) throw new Error('Window lost its dual-lighting uniforms.');
        // Patch only sampler coordinates and the final map color, after dual lighting.
        // Keep its original uDayMap, uLightingMix, exposure and texture ownership.
        shader.fragmentShader = shader.fragmentShader
          .replaceAll('texture2D(map, vMapUv)', 'texture2D(map, liveWindowCityUv(vMapUv))')
          .replaceAll('texture2D(uDayMap, vMapUv)', 'texture2D(uDayMap, liveWindowCityUv(vMapUv))')
          .replace('diffuseColor *= sampledDiffuseColor;', `
            sampledDiffuseColor.rgb = liveWindowAtmosphere(sampledDiffuseColor.rgb, vMapUv, uLightingMix);
            diffuseColor *= sampledDiffuseColor;
          `);
        // uDayMap is declared by the earlier lighting patch, before these helpers use it.
        shader.fragmentShader = shader.fragmentShader.replace('void main() {', windowFunctions + '\nvoid main() {');
      }
    };
    material.customProgramCacheKey = () => `${baseCacheKey}|live-room-${kind}-v1`;
    material.needsUpdate = true;
    bindings.push({ material, previousCompile, previousCacheKey });
  };
  screens.forEach((material) => install(material, 'screen'));
  windows.forEach((material) => install(material, 'window'));

  windowMesh.geometry.computeBoundingBox();
  const center = windowMesh.geometry.boundingBox.getCenter(new THREE.Vector3());
  const localCamera = new THREE.Vector3();
  const baseline = new THREE.Vector2();
  const targetParallax = new THREE.Vector2();
  let baselineReady = false, disposed = false, enabled = false, elapsed = 0, slideIndex = 0;
  let dayTarget = 0, dayDuration = 1.2, themeInitialized = false;

  const setDayMix = (value) => {
    if (disposed || !Number.isFinite(value)) return;
    dayTarget = uniforms.uLiveScreenDay.value = Math.min(1, Math.max(0, value));
    dayDuration = 0; themeInitialized = true;
  };

  const setTheme = (isDay, duration = 1.2) => {
    if (disposed) return;
    dayTarget = isDay ? 1 : 0;
    dayDuration = Math.max(0, Number(duration) || 0);
    if (!themeInitialized || reducedMotion || !enabled || dayDuration === 0) uniforms.uLiveScreenDay.value = dayTarget;
    themeInitialized = true;
  };

  const update = (delta, options = {}) => {
    if (disposed) return;
    enabled = options.enabled !== false;
    if (!enabled || document.hidden) return;
    const dt = Math.min(Math.max(Number(delta) || 0, 0), 0.1);
    if (Math.abs(dayTarget - uniforms.uLiveScreenDay.value) > 0.0001) {
      uniforms.uLiveScreenDay.value += (dayTarget - uniforms.uLiveScreenDay.value) * (1 - Math.exp(-dt * 5 / Math.max(dayDuration, 0.01)));
    } else uniforms.uLiveScreenDay.value = dayTarget;
    if (reducedMotion) return;
    elapsed += dt;
    uniforms.uLiveWindowTime.value = elapsed;
    const nextIndex = Math.floor(elapsed / SLIDE_SECONDS) % slides.length;
    if (nextIndex !== slideIndex) {
      slideIndex = nextIndex;
      uniforms.uLiveScreenA.value = slides[slideIndex];
      uniforms.uLiveScreenB.value = slides[(slideIndex + 1) % slides.length];
      uniforms.uLiveScreenAspectA.value = aspectOf(uniforms.uLiveScreenA.value);
      uniforms.uLiveScreenAspectB.value = aspectOf(uniforms.uLiveScreenB.value);
    }
    const transition = Math.min(1, Math.max(0, (elapsed % SLIDE_SECONDS - HOLD_SECONDS) / FADE_SECONDS));
    uniforms.uLiveScreenMix.value = transition * transition * (3 - 2 * transition);
    if (options.camera) {
      options.camera.getWorldPosition(localCamera);
      windowMesh.updateWorldMatrix(true, false);
      windowMesh.worldToLocal(localCamera).sub(center);
      const depth = Math.max(3, Math.abs(localCamera.z));
      targetParallax.set(localCamera.x / depth, localCamera.y / depth);
      if (!baselineReady) { baseline.copy(targetParallax); baselineReady = true; }
      targetParallax.sub(baseline).multiplyScalar(0.0042);
      targetParallax.x = Math.min(0.0035, Math.max(-0.0035, targetParallax.x));
      targetParallax.y = Math.min(0.0015, Math.max(-0.0015, targetParallax.y));
      uniforms.uLiveWindowParallax.value.lerp(targetParallax, 1 - Math.exp(-dt * 5));
    }
  };

  const getState = () => ({
    ready: !disposed, enabled, paused: disposed || !enabled || document.hidden || reducedMotion,
    reducedMotion, elapsed, slideIndex, nextSlideIndex: (slideIndex + 1) % slides.length,
    slideMix: uniforms.uLiveScreenMix.value, slideLabels,
    contentRole: 'original-project-scene-studies-not-personal-portfolio-content',
    screenDayMix: uniforms.uLiveScreenDay.value,
    parallax: uniforms.uLiveWindowParallax.value.toArray(),
    screenMaterialCount: screens.size, windowMaterialCount: windows.size,
    extraTextureCount: ownedTextures.length, compressedTextures: ownedTextures.filter((texture) => texture.isCompressedTexture).length,
    addedDrawCalls: 0,
  });

  const dispose = () => {
    if (disposed) return;
    disposed = true;
    bindings.forEach(({ material, previousCompile, previousCacheKey }) => {
      material.onBeforeCompile = previousCompile;
      material.customProgramCacheKey = previousCacheKey;
      material.needsUpdate = true;
    });
    ownedTextures.forEach((texture) => texture.dispose());
  };
  return { setTheme, setDayMix, update, getState, dispose };
}
