import * as THREE from 'three';

const vertexShader = `
  #include <common>
  attribute vec3 glassProbePosition;
  varying vec3 vGlassWorldPosition;
  varying vec3 vGlassNormal;
  varying vec3 vGlassProbePosition;
  void main() {
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    vGlassWorldPosition = worldPosition.xyz;
    vGlassNormal = inverseTransformDirection(normalMatrix * normal, viewMatrix);
    vGlassProbePosition = glassProbePosition;
    gl_Position = projectionMatrix * viewMatrix * worldPosition;
  }
`;

const fragmentShader = `
  uniform sampler2D uReflectionDay;
  uniform sampler2D uReflectionNight;
  uniform float uTheme;
  uniform vec3 uProbePosition;
  uniform vec3 uProbeMin;
  uniform vec3 uProbeMax;
  uniform vec3 uGlassTint;
  uniform float uTintAlpha;
  varying vec3 vGlassWorldPosition;
  varying vec3 vGlassNormal;
  varying vec3 vGlassProbePosition;

  vec3 reflectionDirection(vec3 ray) {
    // Project the ray onto the gallery's local probe volume. Positions were
    // stored in native gallery metres; the travel stage's translation must
    // not make the reflected architecture slide across the glass.
    vec3 p = vGlassProbePosition;
    if (any(lessThan(p, uProbeMin)) || any(greaterThan(p, uProbeMax))) return ray;
    vec3 safeRay = mix(vec3(-1.0), vec3(1.0), step(vec3(0.0), ray)) * max(abs(ray), vec3(0.00001));
    vec3 distances = max((uProbeMin - p) / safeRay, (uProbeMax - p) / safeRay);
    // A parallel axis is unconstrained, including when p lies on that face.
    distances = mix(vec3(1.0e20), distances, step(vec3(0.00001), abs(ray)));
    float distanceToBox = min(min(distances.x, distances.y), distances.z);
    return normalize(p + ray * distanceToBox - uProbePosition);
  }
  void main() {
    vec3 viewDirection = normalize(cameraPosition - vGlassWorldPosition);
    vec3 normal = normalize(vGlassNormal);
    vec3 ray = reflectionDirection(reflect(-viewDirection, normal));
    // Calibrated against the Blender panorama; KTX2 is top-down, flipY=false.
    vec2 uv = vec2(atan(ray.x, -ray.z) / 6.28318530718 + 0.5,
                   acos(clamp(ray.y, -1.0, 1.0)) / 3.14159265359);
    vec3 reflected = mix(texture2D(uReflectionNight, uv, 1.0).rgb,
                         texture2D(uReflectionDay, uv, 1.0).rgb, uTheme);
    float incidence = clamp(abs(dot(viewDirection, normal)), 0.0, 1.0);
    float fresnel = 0.04 + 0.96 * pow(1.0 - incidence, 5.0);
    // Both air/glass interfaces contribute. This remains transparent head-on
    // and reflects more at grazing angles without a second render pass.
    fresnel = 1.0 - (1.0 - fresnel) * (1.0 - fresnel);
    float tint = uTintAlpha * (1.0 - fresnel);
    float alpha = fresnel + tint;
    vec3 color = (reflected * fresnel + uGlassTint * mix(0.045, 1.0, uTheme) * tint) / max(alpha, 0.0001);
    gl_FragColor = vec4(color, alpha);
    #include <colorspace_fragment>
  }
`;

/** Static local reflection captures, with live view-angle and day/night blend.
 * No transmission render target or additional scene pass. Geometry and this
 * material are shared by native gallery and travel-stage clones.
 */
export async function createGalleryGlass({ model, loader, renderer, themeUniform,
  directory = '/textures/works-gallery-v4',
  probePosition = [.12, 2.7, -3.36], probeMin = [-11, -.88, -5.4], probeMax = [11, 5.6, 6.5],
}) {
  if (!themeUniform || typeof themeUniform.value !== 'number') throw new Error('Gallery glass requires the live theme uniform');
  const meshes = [];
  model.traverse(node => {
    if (node.isMesh && [].concat(node.material).some(material => material.name === 'GALLERY_ARCH_GLASS')) meshes.push(node);
  });
  if (!meshes.length) throw new Error('Gallery model is missing architectural glass');
  const results = await Promise.allSettled(['day', 'night'].map(theme => loader.loadAsync(`${directory}/reflection-${theme}.ktx2`)));
  const failure = results.find(result => result.status === 'rejected');
  if (failure) {
    results.forEach(result => { if (result.status === 'fulfilled') result.value.dispose(); });
    throw failure.reason;
  }
  const textures = results.map(result => result.value);
  let material;
  const replacements = [], boundGeometries = new Set(), ownedGeometries = new Set();
  try {
    for (const texture of textures) {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.wrapS = THREE.RepeatWrapping;
      texture.wrapT = THREE.ClampToEdgeWrapping;
      texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 4);
    }
    material = new THREE.ShaderMaterial({
      name: 'GALLERY_ARCH_GLASS · local reflections', vertexShader, fragmentShader,
      uniforms: {
        uReflectionDay: { value: textures[0] }, uReflectionNight: { value: textures[1] },
        uTheme: themeUniform,
        uProbePosition: { value: new THREE.Vector3(...probePosition) },
        uProbeMin: { value: new THREE.Vector3(...probeMin) }, uProbeMax: { value: new THREE.Vector3(...probeMax) },
        uGlassTint: { value: new THREE.Color('#9cbdc2') }, uTintAlpha: { value: .085 },
      },
      transparent: true, depthWrite: false, depthTest: true, side: THREE.FrontSide,
      toneMapped: false, forceSinglePass: true,
    });
    model.updateWorldMatrix(true, true);
    const vertex = new THREE.Vector3();
    for (const mesh of meshes) {
      const originalGeometry = mesh.geometry;
      // A GLTF can instance one geometry at several native transforms. Give
      // each binding its own probe coordinates; travel clones still share it.
      const geometry = boundGeometries.has(originalGeometry) ? originalGeometry.clone() : originalGeometry;
      boundGeometries.add(originalGeometry);
      if (geometry !== originalGeometry) ownedGeometries.add(geometry);
      const original = mesh.material;
      replacements.push({ mesh, original, originalGeometry });
      mesh.geometry = geometry;
      if (!geometry.attributes.normal) geometry.computeVertexNormals();
      const positions = geometry.attributes.position;
      const probePositions = new Float32Array(positions.count * 3);
      for (let index = 0; index < positions.count; index++) {
        vertex.fromBufferAttribute(positions, index).applyMatrix4(mesh.matrixWorld).toArray(probePositions, index * 3);
      }
      geometry.setAttribute('glassProbePosition', new THREE.BufferAttribute(probePositions, 3));
      mesh.material = Array.isArray(original) ? original.map(item => item.name === 'GALLERY_ARCH_GLASS' ? material : item) : material;
    }
  } catch (error) {
    for (const { mesh, original, originalGeometry } of replacements) {
      mesh.material = original; mesh.geometry = originalGeometry;
    }
    ownedGeometries.forEach(geometry => geometry.dispose());
    material?.dispose(); textures.forEach(texture => texture.dispose());
    throw error;
  }
  const replacedMaterials = new Set(replacements.flatMap(({ original }) => [].concat(original)).filter(item => item.name === 'GALLERY_ARCH_GLASS'));
  let disposed = false;
  return {
    material, replacedMaterials,
    getState: () => ({ revision: 1, meshes: meshes.length, reflection: 'local Blender day/night captures with box projection',
      additionalScenePasses: 0, probePosition, probeMin, probeMax, textureFormats: textures.map(texture => texture.format) }),
    dispose() {
      if (disposed) return;
      disposed = true;
      // The gallery's material set owns the shader; this helper owns only the
      // reflection images. Stage clones borrow both and never dispose them.
      textures.forEach(texture => texture.dispose());
      ownedGeometries.forEach(geometry => geometry.dispose());
    },
  };
}
