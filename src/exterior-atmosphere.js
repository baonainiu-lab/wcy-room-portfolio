import gsap from 'gsap';
import { createScenePanorama } from './scene-panorama.js';

// The exterior architecture is supplied by Blender. This module only provides
// its continuous world-space light environment, plus optional instanced halos.
// Use camera.far >= 500 for the 320-unit sky and a maximum orbit distance of 60.
export function createExteriorAtmosphere({ THREE, scene, ground, roomBounds, reducedMotion = false }) {
  const SKY_RADIUS = 320;
  const group = new THREE.Group();
  group.name = 'ExteriorAtelierAtmosphere';
  group.userData.excludeFromRoomFraming = true;
  const center = roomBounds.getCenter(new THREE.Vector3());
  const prior = {
    geometry: ground.geometry,
    material: ground.material,
    receiveShadow: ground.receiveShadow,
    frustumCulled: ground.frustumCulled,
    background: scene.background,
    fog: scene.fog,
  };
  const theme = { value: 0 };
  const color = (value) => new THREE.Color(value);
  const nightFog = color('#111e32');
  const dayFog = color('#d6e8f2');
  const background = nightFog.clone();
  const fog = new THREE.Fog(nightFog, 50, 175);
  scene.background = background;
  scene.fog = fog;

  const shared = {
    uTheme: { value: 0 },
    uBreathing: { value: 1 },
    uCenter: { value: new THREE.Vector2(center.x, center.z) },
    uGroundHaze: { value: new THREE.Vector2(70, 160) },
    uNightFloor: { value: color('#0c1625') },
    uDayFloor: { value: color('#d7dcd9') },
    uNightHorizon: { value: nightFog },
    uDayHorizon: { value: dayFog },
    uNightZenith: { value: color('#070e1c') },
    uDayZenith: { value: color('#478bc4') },
    uNightLower: { value: color('#101a2b') },
    uDayLower: { value: color('#c1cdd2') },
    uCool: { value: color('#98d3e1') },
    uWarm: { value: color('#efb77d') },
    // day_sunlight_v9.py SUN_POSITION=(7,16,12) in Blender Z-up.
    uSunDirection: { value: new THREE.Vector3(7, 12, -16).normalize() },
    uWarmPools: { value: [
      new THREE.Vector4(-8, 4, 4.0, 5.8),
      new THREE.Vector4(8, 3, 4.4, 5.6),
      new THREE.Vector4(-11, -13, 6.0, 6.0),
      new THREE.Vector4(10, -15, 6.0, 5.6),
    ] },
  };
  const atmosphereDeclarations = `
    uniform float uTheme;
    uniform vec3 uNightHorizon;
    uniform vec3 uDayHorizon;
    uniform vec3 uNightZenith;
    uniform vec3 uDayZenith;
    uniform vec3 uNightLower;
    uniform vec3 uDayLower;
    uniform vec3 uCool;
    uniform vec3 uWarm;
    uniform vec3 uSunDirection;
  `;
  // A low-cost, direction-based scattering approximation. Both floor and dome
  // evaluate this with the actual world-space view ray, so they agree at every
  // angle and zoom level. There are no screen-fixed shapes, textures or trig.
  const atmosphericColor = `
    vec3 atmosphericColor(vec3 ray) {
      vec3 horizon = mix(uNightHorizon, uDayHorizon, uTheme);
      vec3 zenith = mix(uNightZenith, uDayZenith, uTheme);
      vec3 lower = mix(uNightLower, uDayLower, uTheme);
      vec3 result = mix(horizon, zenith, smoothstep(-0.025, 0.83, ray.y));
      result = mix(result, lower, smoothstep(0.0, 0.62, -ray.y));
      float coolLobe = max(dot(ray, vec3(-0.771, 0.155, -0.617)), 0.0);
      float warmLobe = max(dot(ray, vec3(0.501, 0.180, -0.847)), 0.0);
      float rearWarmLobe = max(dot(ray, vec3(-0.450, 0.180, -0.875)), 0.0);
      coolLobe *= coolLobe;
      warmLobe *= warmLobe;
      rearWarmLobe *= rearWarmLobe;
      rearWarmLobe *= rearWarmLobe;
      // At night only a trace of fixture light reaches the lower haze. Keep
      // the sky darker than the room without losing its blue silhouette.
      float lowHaze = 1.0 - smoothstep(0.16, 0.52, ray.y);
      result = mix(result, uCool, coolLobe * coolLobe * lowHaze * mix(0.012, 0.008, uTheme));
      result = mix(result, uWarm, warmLobe * warmLobe * lowHaze * mix(0.012, 0.007, uTheme));
      result = mix(result, uWarm, rearWarmLobe * rearWarmLobe * lowHaze * mix(0.009, 0.006, uTheme));

      // A restrained forward-scattering aureole and real angular-sized sun
      // align with the baked Blender sun, not with the screen or camera.
      if (uTheme > 0.0) {
        float sunAlignment = max(dot(ray, uSunDirection), 0.0);
        float aureole = sunAlignment * sunAlignment;
        aureole *= aureole;
        aureole *= aureole;
        aureole *= aureole;
        aureole *= aureole;
        result = mix(result, vec3(0.95, 0.925, 0.83), aureole * 0.13 * uTheme);
        float sunDisc = smoothstep(0.999974, 0.999989, sunAlignment);
        result = mix(result, vec3(1.0, 0.975, 0.91), sunDisc * uTheme);
      }
      return result;
    }
  `;
  const worldVertexShader = `
    varying vec3 vWorldPosition;
    void main() {
      vec4 world = modelMatrix * vec4(position, 1.0);
      vWorldPosition = world.xyz;
      gl_Position = projectionMatrix * viewMatrix * world;
    }
  `;
  const floorGeometry = new THREE.PlaneGeometry(1000, 1000);
  const floorMaterial = new THREE.ShaderMaterial({
    name: 'Exterior · continuous satin floor',
    uniforms: { ...shared },
    vertexShader: worldVertexShader,
    fragmentShader: `
      ${atmosphereDeclarations}
      uniform float uBreathing;
      uniform vec2 uCenter;
      uniform vec2 uGroundHaze;
      uniform vec3 uNightFloor;
      uniform vec3 uDayFloor;
      uniform vec4 uWarmPools[4];
      varying vec3 vWorldPosition;
      ${atmosphericColor}
      float softPool(vec2 position, vec2 source, vec2 spread) {
        vec2 delta = (position - source) / spread;
        float falloff = 1.0 / (1.0 + dot(delta, delta));
        return falloff * falloff;
      }
      void main() {
        vec2 p = vWorldPosition.xz - uCenter;
        vec3 result = mix(uNightFloor, uDayFloor, uTheme);

        // Night pools stay close to their fixtures. Preserve the existing
        // broad daylight reflections at the day endpoint of the same blend.
        float poolSpread = mix(0.48, 1.0, uTheme);
        float coolPool = softPool(p, vec2(-14.0, -3.0), vec2(7.0, 22.0) * poolSpread);
        float warmPool = 0.0;
        for (int i = 0; i < 4; i++) {
          warmPool += softPool(p, uWarmPools[i].xy, uWarmPools[i].zw * poolSpread);
        }
        result = mix(result, uCool, coolPool * mix(0.025, 0.012, uTheme));
        result = mix(result, uWarm, min(warmPool, 0.78) * mix(0.12, 0.033, uTheme) * uBreathing);
        float platformShade = softPool(p, vec2(0.0), vec2(7.5, 6.0));
        result *= 1.0 - platformShade * 0.22;

        // Blend well before both the finite floor edge (500 units away) and
        // the 500-unit far clip. The same ray color exists behind it on the dome.
        float radiusSquared = dot(p, p);
        float haze = smoothstep(uGroundHaze.x * uGroundHaze.x, uGroundHaze.y * uGroundHaze.y, radiusSquared);
        if (haze > 0.0) {
          vec3 ray = normalize(vWorldPosition - cameraPosition);
          result = mix(result, atmosphericColor(ray), haze);
        }
        gl_FragColor = vec4(result, 1.0);
        #include <colorspace_fragment>
      }
    `,
    depthTest: true,
    depthWrite: true,
    toneMapped: false,
  });
  ground.geometry = floorGeometry;
  ground.material = floorMaterial;
  ground.receiveShadow = false;
  ground.frustumCulled = false;

  const skyGeometry = new THREE.SphereGeometry(SKY_RADIUS, 40, 24);
  const skyMaterial = new THREE.ShaderMaterial({
    name: 'Exterior · enclosing atmospheric dome',
    uniforms: { ...shared },
    vertexShader: worldVertexShader,
    fragmentShader: `
      ${atmosphereDeclarations}
      varying vec3 vWorldPosition;
      ${atmosphericColor}
      void main() {
        vec3 ray = normalize(vWorldPosition - cameraPosition);
        gl_FragColor = vec4(atmosphericColor(ray), 1.0);
        #include <colorspace_fragment>
      }
    `,
    side: THREE.BackSide,
    depthTest: true,
    depthWrite: false,
    toneMapped: false,
  });
  const sky = new THREE.Mesh(skyGeometry, skyMaterial);
  sky.name = 'Enclosing three-dimensional exhibition sky';
  sky.position.set(center.x, 0, center.z);
  sky.frustumCulled = false;
  // Draw last within the opaque queue: the opaque room and floor have already
  // populated depth, so early-Z rejects hidden sky fragments. Three renders
  // transparent glass/contact shadows in a later queue, above this background.
  sky.renderOrder = 1000;
  sky.raycast = () => {};
  group.add(sky);
  scene.add(group);

  // Optional real fixture halos use a single instanced draw. Their positions
  // remain in world space while the vertex shader faces each plane to camera.
  // Opaque geometry can occlude them; they never write depth or cover the room.
  const glowCapacity = 32;
  const glowGeometry = new THREE.PlaneGeometry(1, 1);
  const glowColors = new THREE.InstancedBufferAttribute(new Float32Array(glowCapacity * 3), 3);
  glowGeometry.setAttribute('aGlowColor', glowColors);
  const introReveal = { value: 1 };
  const glowMaterial = new THREE.ShaderMaterial({
    name: 'Exterior · soft fixture halos',
    uniforms: { uTheme: shared.uTheme, uBreathing: shared.uBreathing, uIntroReveal: introReveal },
    vertexShader: `
      uniform float uTheme;
      attribute vec3 aGlowColor;
      varying vec2 vUv;
      varying vec3 vColor;
      void main() {
        vUv = uv;
        vColor = aGlowColor;
        mat4 worldTransform = modelMatrix * instanceMatrix;
        vec4 worldCenter = worldTransform * vec4(0.0, 0.0, 0.0, 1.0);
        vec4 viewCenter = viewMatrix * worldCenter;
        vec2 worldScale = vec2(length(worldTransform[0].xyz), length(worldTransform[1].xyz));
        worldScale *= mix(0.68, 1.0, uTheme);
        viewCenter.xy += position.xy * worldScale;
        gl_Position = projectionMatrix * viewCenter;
      }
    `,
    fragmentShader: `
      uniform float uTheme;
      uniform float uBreathing;
      uniform float uIntroReveal;
      varying vec2 vUv;
      varying vec3 vColor;
      void main() {
        vec2 point = vUv * 2.0 - 1.0;
        float radiusSquared = dot(point, point);
        float halo = max(1.0 - radiusSquared, 0.0);
        halo = halo * halo * halo;
        float core = halo * halo * halo;
        float opacity = (halo * 0.15 + core * 0.11) * mix(0.4, 0.055, uTheme) * uBreathing * uIntroReveal;
        gl_FragColor = vec4(vColor, opacity);
        #include <colorspace_fragment>
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: true,
    depthWrite: false,
    toneMapped: false,
  });
  const glows = new THREE.InstancedMesh(glowGeometry, glowMaterial, glowCapacity);
  glows.name = 'Warm architecture fixture halos';
  glows.count = 0;
  glows.visible = false;
  glows.frustumCulled = false;
  glows.renderOrder = -1;
  glows.raycast = () => {};
  group.add(glows);
  const glowTransform = new THREE.Object3D();
  const glowColor = new THREE.Color();
  const poolAnchors = [[-8, 4], [8, 3], [-11, -13], [10, -15]];

  const syncTheme = () => {
    shared.uTheme.value = theme.value;
    background.copy(nightFog).lerp(dayFog, theme.value);
    fog.color.copy(background);
    fog.near = THREE.MathUtils.lerp(50, 95, theme.value);
    fog.far = THREE.MathUtils.lerp(175, 245, theme.value);
  };
  syncTheme();
  let disposed = false, clockDriven = false;
  const backdrop = createScenePanorama({ prefix: 'RoomBackdrop', label: 'Room panorama' });
  return {
    group,
    sky,
    recommendedCameraFar: 500,
    async loadBackdrop({ groundFadeNear = 18, groundFadeFar = 40, ...options } = {}) {
      if (!Number.isFinite(groundFadeNear) || !Number.isFinite(groundFadeFar) || groundFadeNear < 0 || groundFadeFar <= groundFadeNear) {
        console.warn('Room panorama: invalid ground fade distances; retaining the current sky.'); return false;
      }
      const loaded = await backdrop.load(options);
      if (!loaded || disposed) return false;
      backdrop.decorateAtmosphere(skyMaterial); backdrop.decorateAtmosphere(floorMaterial);
      shared.uGroundHaze.value.set(groundFadeNear, groundFadeFar);
      return true;
    },
    update(seconds) {
      if (disposed) return;
      shared.uBreathing.value = reducedMotion ? 1 : 0.985 + 0.015 * Math.sin(seconds * 0.15);
    },
    setIntroReveal(value) {
      if (disposed || !Number.isFinite(value)) return;
      introReveal.value = THREE.MathUtils.clamp(value, 0, 1);
    },
    getState() {
      return { dayMix: theme.value, introReveal: introReveal.value, warmLightCount: glows.count, warmLightsVisible: glows.visible, disposed,
        backdrop: { ...backdrop.getState(), groundFadeMetres: shared.uGroundHaze.value.toArray() } };
    },
    setWarmLights(sources = []) {
      if (disposed) return 0;
      const valid = sources.filter((source) => Array.isArray(source?.position) && source.position.length >= 3 && source.position.slice(0, 3).every(Number.isFinite)).slice(0, glowCapacity);
      valid.forEach((source, index) => {
        const rawScale = source.scale ?? 1.4;
        const width = Number(Array.isArray(rawScale) ? rawScale[0] : rawScale);
        const height = Number(Array.isArray(rawScale) ? rawScale[1] ?? rawScale[0] : rawScale);
        glowTransform.position.fromArray(source.position);
        glowTransform.scale.set(
          THREE.MathUtils.clamp(Number.isFinite(width) ? width : 1.4, 0.1, 8),
          THREE.MathUtils.clamp(Number.isFinite(height) ? height : 1.4, 0.1, 8),
          1,
        );
        glowTransform.updateMatrix();
        glows.setMatrixAt(index, glowTransform.matrix);
        glowColor.set(source.color ?? '#ffc68d');
        glowColors.setXYZ(index, glowColor.r, glowColor.g, glowColor.b);
      });
      glows.count = valid.length;
      glows.visible = valid.length > 0;
      glows.instanceMatrix.needsUpdate = true;
      glowColors.needsUpdate = true;
      group.userData.warmLightCount = valid.length;
      // Match each light pool to its nearest actual fixture in that zone.
      // Empty manifests retain the designed four-zone illumination.
      poolAnchors.forEach(([x, z], index) => {
        let nearest = null;
        let nearestDistance = 64;
        for (const source of valid) {
          const px = source.position[0] - center.x;
          const pz = source.position[2] - center.z;
          const distance = (px - x) ** 2 + (pz - z) ** 2;
          if (distance < nearestDistance) { nearest = [px, pz]; nearestDistance = distance; }
        }
        const pool = shared.uWarmPools.value[index];
        pool.x = nearest ? nearest[0] : x;
        pool.y = nearest ? nearest[1] : z;
      });
      return valid.length;
    },
    setDayMix(value) {
      if (disposed || !Number.isFinite(value)) return;
      if (!clockDriven) { gsap.killTweensOf(theme); clockDriven = true; }
      theme.value = THREE.MathUtils.clamp(value, 0, 1); syncTheme();
    },
    setTheme(isDay, duration = 1.5) {
      if (disposed) return;
      clockDriven = false;
      gsap.killTweensOf(theme);
      gsap.to(theme, {
        value: isDay ? 1 : 0,
        duration: reducedMotion ? 0.01 : duration,
        ease: 'power2.inOut',
        onUpdate: syncTheme,
      });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      gsap.killTweensOf(theme);
      backdrop.dispose();
      scene.remove(group);
      if (ground.geometry === floorGeometry) ground.geometry = prior.geometry;
      if (ground.material === floorMaterial) ground.material = prior.material;
      ground.receiveShadow = prior.receiveShadow;
      ground.frustumCulled = prior.frustumCulled;
      if (scene.background === background) scene.background = prior.background;
      if (scene.fog === fog) scene.fog = prior.fog;
      floorMaterial.dispose();
      skyMaterial.dispose();
      floorGeometry.dispose();
      skyGeometry.dispose();
      glows.dispose();
      glowGeometry.dispose();
      glowMaterial.dispose();
    },
  };
}
