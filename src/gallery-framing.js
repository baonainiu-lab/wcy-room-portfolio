import * as THREE from 'three';

// Capture the authored silhouette once. An enclosing box invents empty upper
// front corners around this open corridor and pushes the camera too far away.
export function createGalleryFraming(model) {
  const direction = new THREE.Vector3(17.3, 13.6, 28.3).normalize();
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize();
  const up = new THREE.Vector3().crossVectors(direction, right).normalize();
  const point = new THREE.Vector3(), coordinates = [];
  model.updateWorldMatrix(true, true);
  model.traverse(node => {
    if (!node.isMesh || !node.visible || !node.geometry.attributes.position) return;
    for (let ancestor = node; ancestor; ancestor = ancestor.parent) {
      if (!ancestor.visible || ancestor.userData.asset_id?.startsWith('gallery.environment.')) return;
      if (ancestor === model) break;
    }
    const positions = node.geometry.attributes.position;
    for (let index = 0; index < positions.count; index++) {
      point.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld);
      coordinates.push(point.dot(right), point.dot(up), point.dot(direction));
    }
  });
  if (!coordinates.length) throw new Error('Gallery framing requires visible model vertices');
  const vertices = new Float32Array(coordinates);
  let cache = null;
  const pose = (aspect, fov = 35) => {
    if (!(aspect > 0) || !(fov > 0 && fov < 180)) throw new Error('Invalid gallery camera projection');
    if (!cache || cache.aspect !== aspect || cache.fov !== fov) {
      const target = new THREE.Vector3(-.3, 1.9, .65);
      const tan = Math.tan(THREE.MathUtils.degToRad(fov / 2));
      const horizontalFill = aspect < .8 ? .88 : .92, verticalFill = .82;
      let distance = 0, silhouette;
      const fit = () => {
        const cx = target.dot(right), cy = target.dot(up), cz = target.dot(direction);
        distance = 0;
        for (let i = 0; i < vertices.length; i += 3) {
          distance = Math.max(distance, vertices[i + 2] - cz + Math.max(
            Math.abs(vertices[i] - cx) / (tan * aspect * horizontalFill),
            Math.abs(vertices[i + 1] - cy) / (tan * verticalFill)));
        }
        silhouette = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
        for (let i = 0; i < vertices.length; i += 3) {
          const depth = distance - vertices[i + 2] + cz;
          const x = (vertices[i] - cx) / (depth * tan * aspect), y = (vertices[i + 1] - cy) / (depth * tan);
          silhouette.minX = Math.min(silhouette.minX, x); silhouette.maxX = Math.max(silhouette.maxX, x);
          silhouette.minY = Math.min(silhouette.minY, y); silhouette.maxY = Math.max(silhouette.maxY, y);
        }
      };
      // Balance the projected silhouette; then fit again to keep every authored
      // point, including the return doorway and outer glass ribs, in frame.
      for (let pass = 0; pass < 4; pass++) {
        fit();
        if (pass < 3) target.addScaledVector(right, (silhouette.minX + silhouette.maxX) * .5 * distance * tan * aspect)
          .addScaledVector(up, (silhouette.minY + silhouette.maxY) * .5 * distance * tan);
      }
      cache = { aspect, fov, target, position: target.clone().addScaledVector(direction, distance), distance,
        maxDistance: distance * 1.12, silhouette, horizontalFill, verticalFill };
    }
    return { target: cache.target.clone(), position: cache.position.clone(), maxDistance: cache.maxDistance };
  };
  return { pose, getState: () => cache ? { revision: 2, aspect: cache.aspect, distance: cache.distance,
    maxDistance: cache.maxDistance, silhouette: { ...cache.silhouette }, vertices: vertices.length / 3 } : null };
}
