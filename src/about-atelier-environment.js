import * as THREE from 'three';

/** Keep the source Blender lake visible, without tone-mapping the baked room a
 * second time. The panorama already uses the source AgX view and exposure. */
export function createAtelierEnvironmentFinish({ ground, sky, panorama, nightPanorama = panorama, dayMixUniform = { value: 1 }, rotation }) {
  const nativeMix = { value: 1 }, travelMix = { value: 0 };
  // Match THREE's environment/background rotation convention for an HDR that
  // passed through PMREM; both glass reflections and visible lake face alike.
  const inverseEuler = rotation.clone();
  inverseEuler.set(-rotation.x, -rotation.y, -rotation.z, rotation.order);
  const skyRotation = new THREE.Matrix3().setFromMatrix4(new THREE.Matrix4().makeRotationFromEuler(inverseEuler));
  const declarations = `
    uniform sampler2D uAtelierPanorama;
    uniform sampler2D uAtelierNightPanorama;
    uniform float uAtelierDayMix;
    uniform mat3 uAtelierPanoramaRotation;
    uniform float uAtelierEnvironmentMix;
  `;
  const sampling = `
    vec3 atmosphericColor(vec3 ray) {
      vec3 direction = normalize(uAtelierPanoramaRotation * ray);
      vec2 uv = vec2(atan(direction.z, direction.x) / 6.28318530718 + 0.5,
                     asin(clamp(direction.y, -1.0, 1.0)) / 3.14159265359 + 0.5);
      vec3 lake = mix(texture2D(uAtelierNightPanorama, uv).rgb, texture2D(uAtelierPanorama, uv).rgb, uAtelierDayMix);
      return mix(sourceAtmosphericColor(ray), lake, uAtelierEnvironmentMix);
    }
  `;
  function decorateSky(material, mix) {
    if (!material.fragmentShader.includes('vec3 atmosphericColor(vec3 ray)')) {
      throw new Error('Atelier lake requires the continuous atmosphere shader.');
    }
    material.uniforms = { ...material.uniforms,
      uAtelierPanorama: { value: panorama },
      uAtelierNightPanorama: { value: nightPanorama }, uAtelierDayMix: dayMixUniform,
      uAtelierPanoramaRotation: { value: skyRotation }, uAtelierEnvironmentMix: mix };
    material.fragmentShader = declarations + material.fragmentShader
      .replace('vec3 atmosphericColor(vec3 ray)', 'vec3 sourceAtmosphericColor(vec3 ray)')
      .replace('void main()', `${sampling}\nvoid main()`);
    material.toneMapped = false;
    material.needsUpdate = true;
    return material;
  }
  function decorateFloor(material, mix) {
    const marker = '// Blend well before';
    if (!material.fragmentShader.includes(marker)) throw new Error('Atelier ground requires the continuous floor shader.');
    // The actual floor/shadows are Blender geometry and a 4K bake. During
    // travel only, release the room's infinite floor as this shell approaches.
    material.fragmentShader = material.fragmentShader.replace(marker, `
      result = mix(result, mix(vec3(0.015, 0.021, 0.029), vec3(0.4452, 0.3663, 0.2623), uAtelierDayMix), uAtelierEnvironmentMix);
      ${marker}`);
    material.fragmentShader = material.fragmentShader.replace('gl_FragColor = vec4(result, 1.0);',
      'gl_FragColor = vec4(result, 1.0 - uAtelierEnvironmentMix);');
    material.transparent = true;
    material.depthWrite = false;
    return decorateSky(material, mix);
  }
  decorateSky(sky.material, nativeMix);
  // The source limestone is the entire native floor. An infinite opaque plane
  // below it would occlude the lake through the lower half of every window.
  ground.visible = false;
  return {
    createTravelSkyMaterial(baseMaterial) {
      const material = baseMaterial.clone();
      material.uniforms = { ...baseMaterial.uniforms };
      material.name = 'Exterior · atelier lake travel sky';
      try { return decorateSky(material, travelMix); }
      catch (error) { material.dispose(); throw error; }
    },
    createTravelFloorMaterial(baseMaterial) {
      const material = baseMaterial.clone();
      material.uniforms = { ...baseMaterial.uniforms };
      material.name = 'Exterior · atelier limestone travel floor';
      try { return decorateFloor(material, travelMix); }
      catch (error) { material.dispose(); throw error; }
    },
    updateTravelEnvironment(progress, returning) {
      const t = THREE.MathUtils.clamp((progress - .18) / .58, 0, 1);
      const blend = t * t * t * (t * (t * 6 - 15) + 10);
      travelMix.value = returning ? 1 - blend : blend;
    },
    getState: () => ({ sky: 'source Lake Pier panorama', toneMap: 'Blender AgX Medium High Contrast, source exposure .25 and world strength .5',
      panorama: '/textures/about-atelier-v3/landscape/lake-pier-day.png', nativeGround: 'authored limestone tiles only',
      nightPanorama: nightPanorama === panorama ? null : '/textures/about-atelier-v3/landscape/lake-pier-night.png',
      dayMix: dayMixUniform.value, registeredDayNight: nightPanorama !== panorama,
      environmentRotationDegrees: [rotation.x, rotation.y, rotation.z].map(THREE.MathUtils.radToDeg),
      smoothTravel: true, addedSkyDrawCalls: 0 }),
  };
}
