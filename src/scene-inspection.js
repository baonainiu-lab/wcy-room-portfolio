import * as THREE from 'three';

export const RESUME_BOOK_ID = 'about.workbench.open_sketchbook';

/** Reuse the authored mesh/UVs. Keep its footprint centred and underside on the desk. */
export function configureResumeBook(model, components) {
  const node = components.get(RESUME_BOOK_ID);
  if (!node || node.userData.resumeEntry) return node;
  model.updateMatrixWorld(true);
  const before = new THREE.Box3().setFromObject(node, true);
  const center = before.getCenter(new THREE.Vector3());
  node.scale.multiply(new THREE.Vector3(1.42, 1.12, 1.42));
  model.updateMatrixWorld(true);
  const after = new THREE.Box3().setFromObject(node, true);
  const nextCenter = after.getCenter(new THREE.Vector3());
  const position = node.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(
    center.x - nextCenter.x, before.min.y - after.min.y, center.z - nextCenter.z));
  node.position.copy(node.parent.worldToLocal(position));
  node.userData.resumeEntry = { scaleFactor: [1.42, 1.12, 1.42], supportY: before.min.y };
  node.userData.interaction = 'open_resume';
  node.userData.content_status = 'verified_resume';
  model.updateMatrixWorld(true);
  const bookBounds = new THREE.Box3().setFromObject(node, true);
  const moved = [];
  // Four loose desk props touched the expanded page footprint. Slide each to
  // the nearest free edge without changing its height, UVs or independent ID.
  for (const [id, axis, edge] of [
    ['desk_ring_gauge', 'x', 'min'], ['machined_lens_study', 'z', 'min'],
    ['desk_graphite_pencil', 'x', 'max'], ['desk_eraser', 'x', 'max'],
  ]) {
    const prop = components.get(`about.workbench.${id}`);
    if (!prop) continue;
    const bounds = new THREE.Box3().setFromObject(prop, true);
    if (!bounds.intersectsBox(bookBounds)) continue;
    const amount = edge === 'min' ? bookBounds.min[axis] - .045 - bounds.max[axis] : bookBounds.max[axis] + .045 - bounds.min[axis];
    const world = prop.getWorldPosition(new THREE.Vector3()); world[axis] += amount;
    prop.position.copy(prop.parent.worldToLocal(world));
    moved.push(prop.userData.asset_id);
    model.updateMatrixWorld(true);
  }
  node.userData.resumeEntry.clearanceAdjusted = moved;
  return node;
}

/** Move into the selected object while keeping its full silhouette in view. */
export function inspectionPose(camera, node, kind = 'work') {
  node.updateWorldMatrix(true, true);
  const box = new THREE.Box3().setFromObject(node, true);
  const target = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const direction = camera.position.clone().sub(target);
  const initialDistance = direction.length();
  direction.normalize();
  // The book is horizontal: stay above the desk/chair instead of diving into it.
  if (kind === 'resume') direction.y = Math.max(direction.y, .52);
  direction.normalize();
  const fitDistance = Math.max(size.y, size.x / camera.aspect) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * .65);
  // A closer reading stop, still derived from the current view and mesh bounds.
  // Leave enough height over the desk and space in front of the framed exhibit.
  const distance = Math.min(initialDistance, Math.max(initialDistance * (kind === 'resume' ? .43 : .45), fitDistance, kind === 'resume' ? 3.2 : 4.5));
  return { target, position: target.clone().addScaledVector(direction, distance) };
}

/** Screen-space source for the HTML layer, measured after camera movement. */
export function projectObjectRect(node, camera, rect) {
  node.updateWorldMatrix(true, true); camera.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(node, true);
  const xs = [], ys = [];
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
    const p = new THREE.Vector3(x, y, z).project(camera);
    if (p.z < -1 || p.z > 1) continue;
    xs.push(rect.left + (p.x + 1) * rect.width / 2);
    ys.push(rect.top + (1 - p.y) * rect.height / 2);
  }
  if (!xs.length) return { x: rect.left + rect.width * .45, y: rect.top + rect.height * .45, width: rect.width * .1, height: rect.height * .1 };
  const x = THREE.MathUtils.clamp(Math.min(...xs), rect.left + 8, rect.left + rect.width - 24);
  const y = THREE.MathUtils.clamp(Math.min(...ys), rect.top + 8, rect.top + rect.height - 24);
  return { x, y, width: Math.max(16, Math.min(rect.left + rect.width - 8, Math.max(...xs)) - x),
    height: Math.max(16, Math.min(rect.top + rect.height - 8, Math.max(...ys)) - y) };
}
