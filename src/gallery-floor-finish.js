import * as THREE from 'three';
import { createScenePanorama } from './scene-panorama.js';

// The illumination was baked against the actual gallery in Blender. Keep it in
// world metres so orbiting and the shared travel stage see the same shadows.
export async function createGalleryFloorFinish({ ground, sky, loader, renderer,
  floorDirectory = '/textures/gallery-atmosphere-v1', skyDirectory = '/textures/gallery-atmosphere-v1',
  backdrop,
}) {
  const maps = await Promise.allSettled(['day', 'night', 'day-sky', 'night-sky'].map(state =>
    loader.loadAsync(`${state.endsWith('-sky') ? skyDirectory : floorDirectory}/${state}.ktx2`)));
  const failure = maps.find(result => result.status === 'rejected');
  if (failure) {
    maps.forEach(result => { if (result.status === 'fulfilled') result.value.dispose(); });
    throw failure.reason;
  }
  const [day, night, daySky, nightSky] = maps.map(result => result.value);
  const textures = [day, night, daySky, nightSky];
  for (const texture of textures) {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
  }
  daySky.wrapS = nightSky.wrapS = THREE.RepeatWrapping;
  const nativeSkyMix = { value: 1 }, travelSkyMix = { value: 0 };
  const panorama = createScenePanorama({ prefix: 'GalleryBackdrop', label: 'Gallery panorama', renderer });
  const groundFade = new THREE.Vector2(18, 36);
  if (backdrop) {
    if (Number.isFinite(backdrop.groundFadeNear) && Number.isFinite(backdrop.groundFadeFar) && backdrop.groundFadeNear >= 0 && backdrop.groundFadeFar > backdrop.groundFadeNear) {
      groundFade.set(backdrop.groundFadeNear, backdrop.groundFadeFar);
    }
    await panorama.load(backdrop);
  }
  const skyDeclarations = `
    uniform sampler2D uGallerySkyDay;
    uniform sampler2D uGallerySkyNight;
    uniform float uGallerySkyMix;
  `;
  const skySampling = `
    vec3 atmosphericColor(vec3 ray) {
      // Blender cardinal calibration: u=.5 faces web -Z, u=.75 faces +X.
      // A physical sky texture is black below Earth. Here the distant ground
      // meets aerial haze, so sample the horizon and fade to its lower-air tint.
      vec3 skyRay = normalize(vec3(ray.x, max(ray.y, 0.018), ray.z));
      vec2 skyUv = vec2(atan(skyRay.x, -skyRay.z) / 6.28318530718 + 0.5,
                         acos(clamp(skyRay.y, -1.0, 1.0)) / 3.14159265359);
      vec3 physicalSky = mix(texture2D(uGallerySkyNight, skyUv).rgb,
                            texture2D(uGallerySkyDay, skyUv).rgb, uTheme);
      physicalSky = mix(physicalSky, mix(uNightLower, uDayLower, uTheme), smoothstep(0.0, 0.5, -ray.y));
      if (uGalleryBackdropEnabled > 0.5) physicalSky = GalleryBackdropSample(ray, uTheme);
      return mix(atelierAtmosphericColor(ray), physicalSky, uGallerySkyMix);
    }
  `;
  function decorateSky(material, skyMix) {
    if (!material.fragmentShader.includes('vec3 atmosphericColor(vec3 ray)')) throw new Error('Gallery sky requires the atmosphere shader');
    material.uniforms = { ...material.uniforms, uGallerySkyDay: { value: daySky },
      uGallerySkyNight: { value: nightSky }, uGallerySkyMix: skyMix };
    material.fragmentShader = skyDeclarations + material.fragmentShader
      .replace('vec3 atmosphericColor(vec3 ray)', 'vec3 atelierAtmosphericColor(vec3 ray)')
      .replace('void main()', `${skySampling}\nvoid main()`);
    panorama.inject(material);
    material.needsUpdate = true;
    return material;
  }

  const declarations = `
    uniform sampler2D uGalleryFloorDay;
    uniform sampler2D uGalleryFloorNight;
    uniform vec2 uGalleryFloorOrigin;
    uniform vec3 uGalleryGroundDay;
    uniform vec3 uGalleryGroundNight;
    uniform vec2 uGalleryBackdropGroundFade;
    float galleryLobe(vec2 point, vec2 center, vec2 spread) {
      vec2 q = (point - center) / spread;
      return exp(-dot(q, q));
    }
  `;
  const finish = `
    vec2 galleryPoint = vWorldPosition.xz - uGalleryFloorOrigin;
    vec3 distantStone = mix(uGalleryGroundNight, uGalleryGroundDay, uTheme);
    result = mix(result, distantStone, uGallerySkyMix);
    // KTX is top-down (rd), flipY=false: its first row is web Z=-32.
    vec2 galleryUv = galleryPoint / 64.0 + 0.5;
    float galleryWeight = 1.0 - smoothstep(23.0, 32.0, length(galleryPoint));
    if (galleryWeight > 0.0) {
      vec3 galleryColor = mix(texture2D(uGalleryFloorNight, galleryUv).rgb,
                             texture2D(uGalleryFloorDay, galleryUv).rgb, uTheme);
      // Soft satin highlights, not a mirror pass. Their footprint is anchored
      // to the same world-space light field and changes gently with incidence.
      vec3 viewRay = normalize(cameraPosition - vWorldPosition);
      float grazing = 1.0 - clamp(viewRay.y, 0.0, 1.0);
      grazing *= grazing;
      vec2 alongSun = vec2(dot(galleryPoint, vec2(0.740, -0.673)),
                           dot(galleryPoint, vec2(0.673, 0.740)));
      float daylightSheen = galleryLobe(alongSun, vec2(-1.5, 9.5), vec2(20.0, 7.0));
      float warmSheen = galleryLobe(galleryPoint, vec2(8.0, 6.0), vec2(5.0, 11.0))
                      + galleryLobe(galleryPoint, vec2(-8.0, 2.0), vec2(4.0, 8.0));
      galleryColor += vec3(0.93, 0.82, 0.65) * daylightSheen * uTheme * (0.008 + 0.020 * grazing);
      galleryColor += vec3(0.34, 0.17, 0.065) * warmSheen * (1.0 - uTheme) * (0.015 + 0.045 * grazing);
      result = mix(result, galleryColor, galleryWeight);
    }
  `;
  const marker = '// Blend well before';
  function decorate(material, origin, skyMix = nativeSkyMix) {
    if (!material.fragmentShader.includes(marker)) throw new Error('Gallery floor requires the continuous atmosphere shader');
    material.uniforms = { ...material.uniforms,
      uGalleryFloorDay: { value: day }, uGalleryFloorNight: { value: night },
      uGalleryFloorOrigin: { value: new THREE.Vector2(origin.x, origin.z) },
      uGalleryGroundDay: { value: new THREE.Vector3(...(floorDirectory.endsWith('-v2') ? [.2451356144, .2539532254, .2613208385] : [.32, .35, .37])) },
      uGalleryGroundNight: { value: new THREE.Vector3(...(floorDirectory.endsWith('-v2') ? [.0009678794, .0027816690, .0057189824] : [.004, .008, .015])) },
      uGalleryBackdropGroundFade: { value: groundFade },
    };
    material.fragmentShader = declarations + material.fragmentShader.replace(marker, `${finish}\n        ${marker}`);
    material.fragmentShader = material.fragmentShader.replace(
      'float haze = smoothstep(uGroundHaze.x * uGroundHaze.x, uGroundHaze.y * uGroundHaze.y, radiusSquared);',
      `float galleryHaze = smoothstep(625.0, 6400.0, dot(galleryPoint, galleryPoint));
       if (uGalleryBackdropEnabled > 0.5) galleryHaze = smoothstep(uGalleryBackdropGroundFade.x * uGalleryBackdropGroundFade.x,
         uGalleryBackdropGroundFade.y * uGalleryBackdropGroundFade.y, dot(galleryPoint, galleryPoint));
       float haze = mix(smoothstep(uGroundHaze.x * uGroundHaze.x, uGroundHaze.y * uGroundHaze.y, radiusSquared), galleryHaze, uGallerySkyMix);`);
    decorateSky(material, skyMix);
    material.needsUpdate = true;
    return material;
  }
  try {
    if (!sky?.material) throw new Error('Gallery environment requires its sky mesh');
    decorate(ground.material, new THREE.Vector3());
    decorateSky(sky.material, nativeSkyMix);
  }
  catch (error) { panorama.dispose(); textures.forEach(texture => texture.dispose()); throw error; }
  let disposed = false;
  return {
    // Glass must follow the exact atmosphere blend, including an interrupted
    // theme switch. The atmosphere remains the sole writer of this uniform.
    getThemeUniform: () => ground.material.uniforms.uTheme,
    createTravelFloorMaterial(baseMaterial, offset) {
      const material = baseMaterial.clone();
      // Reuse the live room's read-only theme uniforms, not stale cloned values.
      // These image resources belong to this finish, not to a travel clone.
      material.uniforms = { ...baseMaterial.uniforms };
      material.name = 'Exterior · gallery-lit travel floor';
      try { return decorate(material, offset, travelSkyMix); }
      catch (error) { material.dispose(); throw error; }
    },
    createTravelSkyMaterial(baseMaterial) {
      const material = baseMaterial.clone();
      material.uniforms = { ...baseMaterial.uniforms };
      material.name = 'Exterior · physical gallery travel sky';
      try { return decorateSky(material, travelSkyMix); }
      catch (error) { material.dispose(); throw error; }
    },
    updateTravelEnvironment(progress, returning) {
      const t = THREE.MathUtils.clamp((progress - .18) / .58, 0, 1);
      const blend = t * t * t * (t * (t * 6 - 15) + 10);
      travelSkyMix.value = returning ? 1 - blend : blend;
    },
    getState: () => ({ revision: 2, baked: true, sizeMetres: 64, resolution: 2048,
      textureFormats: textures.map(texture => texture.format), sky: 'Blender physical atmosphere, same sun as gallery bake', addedDrawCalls: 0,
      backdrop: { ...panorama.getState(), groundFadeMetres: groundFade.toArray() },
      source: `${floorDirectory}/SOURCE.json`, skySource: `${skyDirectory}/SKY_SOURCE.json` }),
    dispose() {
      if (disposed) return;
      disposed = true;
      panorama.dispose();
      textures.forEach(texture => texture.dispose());
    },
  };
}
