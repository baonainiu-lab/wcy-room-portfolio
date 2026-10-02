import * as THREE from 'three';

// Blender's approved (8, -12.3, 5.2) → (0, .2, 1.95) camera,
// converted from Z-up to glTF Y-up. Fit the silhouette, not empty box corners.
export function createAboutFraming(model) {
  const direction = new THREE.Vector3(8, 3.25, 12.5).normalize();
  const right = new THREE.Vector3().crossVectors(THREE.Object3D.DEFAULT_UP, direction).normalize();
  const up = new THREE.Vector3().crossVectors(direction, right).normalize();
  const vertex = new THREE.Vector3(), coordinates = [], bounds = new THREE.Box3();
  model.updateWorldMatrix(true, true);
  model.traverse(node => {
    if (!node.isMesh || !node.geometry.attributes.position) return;
    for (let ancestor = node; ancestor; ancestor = ancestor.parent) {
      if (!ancestor.visible || ancestor.userData.excludeFromAboutFraming) return;
      if (ancestor === model) break;
    }
    const positions = node.geometry.attributes.position;
    for (let index = 0; index < positions.count; index++) {
      vertex.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld);
      if (![vertex.x, vertex.y, vertex.z].every(Number.isFinite)) throw new Error('Atelier contains non-finite geometry');
      coordinates.push(vertex.dot(right), vertex.dot(up), vertex.dot(direction));
      bounds.expandByPoint(vertex);
    }
  });
  if (!coordinates.length) throw new Error('Atelier framing requires visible model vertices');
  const vertices = new Float32Array(coordinates);
  let cache = null;
  const pose = (aspect, fov = 35) => {
    if (!Number.isFinite(aspect) || !(aspect > 0) || !Number.isFinite(fov) || !(fov > 0 && fov < 180)) {
      throw new Error('Invalid atelier camera projection');
    }
    if (!cache || cache.aspect !== aspect || cache.fov !== fov) {
      const target = new THREE.Vector3(0, 1.95, -.2);
      const tan = Math.tan(THREE.MathUtils.degToRad(fov / 2));
      const horizontalFill = .88, verticalFill = .89;
      let distance, minDistance, silhouette;
      const fit = () => {
        const cx = target.dot(right), cy = target.dot(up), cz = target.dot(direction);
        distance = 0;
        let radiusSquared = 0;
        for (let index = 0; index < vertices.length; index += 3) {
          radiusSquared = Math.max(radiusSquared, (vertices[index] - cx) ** 2 + (vertices[index + 1] - cy) ** 2 + (vertices[index + 2] - cz) ** 2);
          distance = Math.max(distance, vertices[index + 2] - cz + Math.max(
            Math.abs(vertices[index] - cx) / (tan * aspect * horizontalFill),
            Math.abs(vertices[index + 1] - cy) / (tan * verticalFill)));
        }
        // This sphere encloses the complete assembly from every orbit angle.
        minDistance = Math.sqrt(radiusSquared) + .7;
        distance = Math.max(distance, minDistance);
        silhouette = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
        for (let index = 0; index < vertices.length; index += 3) {
          const depth = distance - vertices[index + 2] + cz;
          const x = (vertices[index] - cx) / (depth * tan * aspect), y = (vertices[index + 1] - cy) / (depth * tan);
          silhouette.minX = Math.min(silhouette.minX, x); silhouette.maxX = Math.max(silhouette.maxX, x);
          silhouette.minY = Math.min(silhouette.minY, y); silhouette.maxY = Math.max(silhouette.maxY, y);
        }
      };
      for (let pass = 0; pass < 12; pass++) {
        fit();
        if (pass < 11) target.addScaledVector(right, (silhouette.minX + silhouette.maxX) * .5 * distance * tan * aspect)
          .addScaledVector(up, (silhouette.minY + silhouette.maxY) * .5 * distance * tan);
      }
      // A sphere enclosing all model vertices also encloses every permitted
      // orbit direction. Keep the near plane and a small inspection margin
      // outside it; zooming never enters the desk, cabinet or glass cloches.
      cache = { aspect, fov, target, position: target.clone().addScaledVector(direction, distance), distance,
        minDistance, maxDistance: distance * 1.12, silhouette, horizontalFill, verticalFill };
    }
    return { target: cache.target.clone(), position: cache.position.clone(), minDistance: cache.minDistance, maxDistance: cache.maxDistance };
  };
  return { pose, getState: () => cache ? { revision: 1, aspect: cache.aspect, fov: cache.fov,
    distance: cache.distance, minDistance: cache.minDistance, maxDistance: cache.maxDistance,
    horizontalFill: cache.horizontalFill, verticalFill: cache.verticalFill, silhouette: { ...cache.silhouette },
    vertices: vertices.length / 3, bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() } } : null };
}
