import * as THREE from 'three';

/** A registered day/night panorama pair. The image is sampled by world ray,
 * never screen UV; both endpoints always share the same yaw and horizon. */
export function createScenePanorama({ prefix, label = 'Scene backdrop', loader = new THREE.TextureLoader(), renderer } = {}) {
  if (!/^[A-Za-z][A-Za-z0-9]*$/.test(prefix)) throw new Error('Panorama shader prefix must be an identifier.');
  const keys = { day: `u${prefix}Day`, night: `u${prefix}Night`, enabled: `u${prefix}Enabled`, yaw: `u${prefix}Yaw`, latitude: `u${prefix}LatitudeOffset`, detail: `u${prefix}AngularDetail` };
  const sample = `${prefix}Sample`, fallback = `${prefix}PreviousAtmosphere`;
  const uniforms = {
    [keys.day]: { value: null }, [keys.night]: { value: null },
    [keys.enabled]: { value: 0 }, [keys.yaw]: { value: 0 }, [keys.latitude]: { value: 0 }, [keys.detail]: { value: new THREE.Vector2(1, 1) },
  };
  let disposed = false, generation = 0, maps = [], state = { status: 'idle', loaded: false, dayUrl: null, nightUrl: null, yawDegrees: 0, latitudeOffsetDegrees: 0, error: null };
  const glsl = `
    uniform sampler2D ${keys.day};
    uniform sampler2D ${keys.night};
    uniform float ${keys.enabled};
    uniform float ${keys.yaw};
    uniform float ${keys.latitude};
    uniform vec2 ${keys.detail};
    vec3 ${sample}(vec3 ray, float dayMix) {
      vec3 direction = normalize(ray);
      // u=.5 faces web -Z. Standard PNG textures flip Y on upload, so sky is
      // at v=1 and the lower hemisphere at v=0; the horizon stays at v=.5.
      float latitude = asin(clamp(direction.y, -1.0, 1.0));
      // A bounded world-elevation remap places a low architectural horizon
      // behind an elevated miniature camera. Both poles stay fixed, and the
      // same level latitude ring is retained throughout a full orbit.
      latitude += ${keys.latitude} * cos(latitude);
      latitude = atan(${keys.detail}.y * sin(latitude), cos(latitude));
      float longitude = fract(atan(direction.x, -direction.z) / 6.28318530718 + ${keys.yaw} + 0.5) - 0.5;
      // Prioritize angular detail in the forward view while retaining the
      // complete sphere. This monotonic periodic remap has no clipped sector
      // edges, including when an overhead orbit looks across every longitude.
      float halfAngle = longitude * 3.14159265359;
      float horizontalUv = fract(atan(${keys.detail}.x * sin(halfAngle), cos(halfAngle)) / 3.14159265359 + 0.5);
      vec2 uv = vec2(horizontalUv,
                     latitude / 3.14159265359 + 0.5);
      return mix(texture2D(${keys.night}, uv).rgb, texture2D(${keys.day}, uv).rgb, clamp(dayMix, 0.0, 1.0));
    }
  `;
  const inject = material => {
    if (material.uniforms[keys.enabled]) return material;
    material.uniforms = { ...material.uniforms, ...uniforms };
    material.fragmentShader = glsl + material.fragmentShader;
    material.toneMapped = false; material.needsUpdate = true;
    return material;
  };
  return {
    uniforms, keys, sample, inject,
    decorateAtmosphere(material) {
      if (material.fragmentShader.includes(`vec3 ${fallback}(`)) return material;
      if (!material.fragmentShader.includes('vec3 atmosphericColor(vec3 ray)')) throw new Error('Panorama requires a world-ray atmosphericColor shader.');
      inject(material);
      material.fragmentShader = material.fragmentShader
        .replace('vec3 atmosphericColor(vec3 ray)', `vec3 ${fallback}(vec3 ray)`)
        .replace('void main()', `
          vec3 atmosphericColor(vec3 ray) {
            if (${keys.enabled} > 0.5) return ${sample}(ray, uTheme);
            return ${fallback}(ray);
          }
          void main()`);
      material.needsUpdate = true;
      return material;
    },
    async load({ dayUrl, nightUrl, yawDegrees = 0, latitudeOffsetDegrees = 0, forwardDetailFactor = 1, latitudeDetailFactor = 1 } = {}) {
      if (disposed) return false;
      const request = ++generation;
      state = { ...state, status: 'loading', requestedDayUrl: dayUrl ?? null, requestedNightUrl: nightUrl ?? null, error: null };
      if (!dayUrl || !nightUrl || !Number.isFinite(yawDegrees) || !Number.isFinite(latitudeOffsetDegrees) || Math.abs(latitudeOffsetDegrees) > 45 || ![forwardDetailFactor, latitudeDetailFactor].every(value => Number.isFinite(value) && value >= 1 && value <= 6)) {
        state.status = 'failed'; state.error = 'A day/night pair, finite yaw, latitude offset within ±45°, and detail factors within 1–6 are required.';
        console.warn(`${label}: ${state.error}`); return false;
      }
      const results = await Promise.allSettled([dayUrl, nightUrl].map(url => loader.loadAsync(url)));
      const fulfilled = results.filter(result => result.status === 'fulfilled').map(result => result.value);
      if (disposed || request !== generation) { new Set(fulfilled).forEach(texture => texture.dispose()); return false; }
      const failure = results.find(result => result.status === 'rejected');
      if (failure) {
        new Set(fulfilled).forEach(texture => texture.dispose());
        state.status = 'failed'; state.error = failure.reason?.message ?? String(failure.reason);
        console.warn(`${label}: images unavailable; retaining the existing sky.`, failure.reason);
        return false;
      }
      const next = results.map(result => result.value);
      for (const texture of next) {
        texture.colorSpace = THREE.SRGBColorSpace; texture.flipY = true;
        texture.wrapS = THREE.RepeatWrapping; texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.anisotropy = Math.min(renderer?.capabilities?.getMaxAnisotropy?.() ?? 1, 8);
        texture.needsUpdate = true;
      }
      const previous = maps; maps = next;
      uniforms[keys.day].value = maps[0]; uniforms[keys.night].value = maps[1];
      uniforms[keys.yaw].value = yawDegrees / 360; uniforms[keys.enabled].value = 1;
      uniforms[keys.latitude].value = THREE.MathUtils.degToRad(latitudeOffsetDegrees);
      uniforms[keys.detail].value.set(forwardDetailFactor, latitudeDetailFactor);
      new Set(previous).forEach(texture => { if (!maps.includes(texture)) texture.dispose(); });
      state = { status: 'ready', loaded: true, dayUrl, nightUrl, yawDegrees, latitudeOffsetDegrees, forwardDetailFactor, latitudeDetailFactor, error: null };
      return true;
    },
    getState: () => ({ ...state, worldDirection: true, sameDayNightOrientation: true,
      projection: 'continuous forward-weighted full sphere',
      resolutions: maps.map(texture => [texture.image?.width ?? 0, texture.image?.height ?? 0]) }),
    dispose() {
      if (disposed) return;
      disposed = true; generation++;
      new Set(maps).forEach(texture => texture.dispose()); maps = [];
      uniforms[keys.day].value = uniforms[keys.night].value = null; uniforms[keys.enabled].value = 0;
      state = { ...state, status: 'disposed', loaded: false };
    },
  };
}
