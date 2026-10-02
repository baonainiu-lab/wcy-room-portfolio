// Local triangle BVHs are built once. Runtime queries inspect only nearby leaves;
// merged wall/window meshes keep their real holes and animated meshes keep their
// current transforms. No render-mesh raycast or whole-room solid AABB is used.
const EPS = 1e-9;
const SKIN = 0.0005;
const LEAF_SIZE = 20;

function buildTree(THREE, geometry) {
  const position = geometry.getAttribute('position'), index = geometry.getIndex();
  const count = Math.floor((index?.count ?? position.count) / 3);
  const vertices = new Float32Array(count * 9), bounds = new Float32Array(count * 6);
  const order = new Uint32Array(count), point = new THREE.Vector3();
  for (let triangle = 0; triangle < count; triangle++) {
    const offset = triangle * 6;
    bounds.set([Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity], offset);
    order[triangle] = triangle;
    for (let corner = 0; corner < 3; corner++) {
      const vertex = triangle * 3 + corner;
      point.fromBufferAttribute(position, index ? index.getX(vertex) : vertex);
      vertices.set(point.toArray(), triangle * 9 + corner * 3);
      for (let axis = 0; axis < 3; axis++) {
        const value = point.getComponent(axis);
        bounds[offset + axis] = Math.min(bounds[offset + axis], value);
        bounds[offset + axis + 3] = Math.max(bounds[offset + axis + 3], value);
      }
    }
  }
  function split(start, end, depth = 0) {
    const box = new THREE.Box3();
    for (let i = start; i < end; i++) {
      const offset = order[i] * 6;
      box.min.min(point.fromArray(bounds, offset)); box.max.max(point.fromArray(bounds, offset + 3));
    }
    const node = { box, start, end, left: null, right: null };
    if (end - start <= LEAF_SIZE || depth >= 28) return node;
    const size = box.getSize(point), axis = size.x >= size.y && size.x >= size.z ? 0 : size.y >= size.z ? 1 : 2;
    const midpoint = (box.min.getComponent(axis) + box.max.getComponent(axis)) * .5;
    let low = start, high = end - 1;
    while (low <= high) {
      const offset = order[low] * 6;
      if ((bounds[offset + axis] + bounds[offset + axis + 3]) * .5 < midpoint) low++;
      else { const swap = order[low]; order[low] = order[high]; order[high--] = swap; }
    }
    // A flat, tightly clustered leaf is cheaper than an unbalanced deep tree.
    if (low === start || low === end) return node;
    node.left = split(start, low, depth + 1); node.right = split(low, end, depth + 1);
    return node;
  }
  return { vertices, bounds, order, count, root: split(0, count) };
}

/**
 * Call update({ enabled }) AFTER controls.update() and floor constraints, before
 * rendering. Enable only during free room navigation; disable during homepage,
 * scene transitions, camera reset/focus animation, and gallery. Disabled updates
 * sync the previous pose without changing camera/target. reset() does the same
 * when the caller deliberately teleports. The camera and OrbitControls target
 * are in the scene's world coordinate system, as in the room's existing setup.
 *
 * A collision translates camera AND target by the minimum swept/slide correction,
 * keeping the user's viewing direction and camera-target distance unchanged.
 * If that slide would push target outside its pan bounds, stop at the swept
 * impact pose instead. This prevents target.clamp() fighting the next frame.
 * minDistance, angle limits, zoom speed, damping, and pan limits are never changed.
 */
export function createRoomCameraGuard({ THREE, room, camera, controls }) {
  if (!room || !camera?.isPerspectiveCamera || !controls?.target) throw new Error('Room camera guard requires a room, perspective camera, and OrbitControls target.');
  const colliders = [], cache = new WeakMap();
  let triangles = 0;
  room.updateWorldMatrix(true, true);
  room.traverse(mesh => {
    if (!mesh.isMesh || !mesh.geometry?.getAttribute('position')) return;
    for (let parent = mesh; parent; parent = parent.parent) {
      if (parent.userData.cameraCollision === false || ['environment.orbital_dock', 'environment.warm_gallery'].includes(parent.userData.asset_id)) return;
      if (parent === room) break;
    }
    let tree = cache.get(mesh.geometry);
    if (!tree) { tree = buildTree(THREE, mesh.geometry); cache.set(mesh.geometry, tree); }
    if (!tree.count) return;
    colliders.push({ mesh, tree, inverse: new THREE.Matrix4(), normalMatrix: new THREE.Matrix3(),
      worldBox: new THREE.Box3(), lastWorld: new THREE.Matrix4(), initialized: false, minScale: 1, visible: true });
    triangles += tree.count;
  });
  const previous = camera.position.clone(), previousTarget = controls.target.clone();
  const desired = new THREE.Vector3(), desiredTarget = new THREE.Vector3(), solved = new THREE.Vector3();
  const candidateTarget = new THREE.Vector3(), stopPosition = new THREE.Vector3(), stopTarget = new THREE.Vector3();
  const candidateOffset = new THREE.Vector3(), candidateSpherical = new THREE.Spherical();
  const remaining = new THREE.Vector3(), correction = new THREE.Vector3(), localStart = new THREE.Vector3(), localEnd = new THREE.Vector3();
  const localDelta = new THREE.Vector3(), queryBox = new THREE.Box3(), expanded = new THREE.Box3();
  const triangle = new THREE.Triangle(), closest = new THREE.Vector3(), testPoint = new THREE.Vector3();
  const contactNormal = new THREE.Vector3(), worldNormal = new THREE.Vector3(), ray = new THREE.Ray();
  const edge = new THREE.Vector3(), separation = new THREE.Vector3(), edgePoint = new THREE.Vector3();
  const normalHit = new THREE.Vector3(), overlapPush = new THREE.Vector3(), scale = new THREE.Vector3();
  const state = { revision: 1, active: false, colliderCount: colliders.length, triangleCount: triangles,
    radius: 0, corrected: false, panLimited: false, correction: [0, 0, 0], lastContact: null, triangleTests: 0, nodeTests: 0 };

  function refresh(point, radius) {
    let changedNearby = false;
    room.updateWorldMatrix(true, true);
    for (const collider of colliders) {
      const wasVisible = collider.visible;
      collider.visible = true;
      for (let node = collider.mesh; node; node = node.parent) {
        if (!node.visible || node.userData.cameraCollision === false) { collider.visible = false; break; }
        if (node === room) break;
      }
      if (collider.initialized && wasVisible === collider.visible && collider.lastWorld.equals(collider.mesh.matrixWorld)) continue;
      if (collider.initialized && expanded.copy(collider.worldBox).expandByScalar(radius).containsPoint(point)) changedNearby = true;
      collider.lastWorld.copy(collider.mesh.matrixWorld); collider.initialized = true;
      if (!collider.visible) continue;
      collider.inverse.copy(collider.mesh.matrixWorld).invert();
      collider.normalMatrix.getNormalMatrix(collider.mesh.matrixWorld);
      collider.worldBox.copy(collider.tree.root.box).applyMatrix4(collider.mesh.matrixWorld);
      scale.setFromMatrixScale(collider.mesh.matrixWorld);
      collider.minScale = Math.max(1e-6, Math.min(Math.abs(scale.x), Math.abs(scale.y), Math.abs(scale.z)));
      if (expanded.copy(collider.worldBox).expandByScalar(radius).containsPoint(point)) changedNearby = true;
    }
    return changedNearby;
  }
  function readTriangle(tree, id) {
    const offset = id * 9;
    triangle.a.fromArray(tree.vertices, offset); triangle.b.fromArray(tree.vertices, offset + 3); triangle.c.fromArray(tree.vertices, offset + 6);
  }
  function distanceAt(t) {
    testPoint.copy(localStart).addScaledVector(localDelta, t);
    triangle.closestPointToPoint(testPoint, closest);
    return testPoint.distanceToSquared(closest);
  }
  // Exact closest distance between a finite movement segment and a triangle.
  // A face intersection or an endpoint/edge pair realizes the minimum.
  function closestTime() {
    const length = localDelta.length();
    if (length < EPS) return 0;
    ray.origin.copy(localStart); ray.direction.copy(localDelta).multiplyScalar(1 / length);
    if (ray.intersectTriangle(triangle.a, triangle.b, triangle.c, false, testPoint)) {
      const distance = testPoint.distanceTo(localStart);
      if (distance <= length) return distance / length;
    }
    let time = 0, best = distanceAt(0);
    const atEnd = distanceAt(1);
    if (atEnd < best) { best = atEnd; time = 1; }
    const a = localDelta.lengthSq();
    const corners = [triangle.a, triangle.b, triangle.c];
    for (let i = 0; i < 3; i++) {
      const origin = corners[i]; edge.subVectors(corners[(i + 1) % 3], origin);
      separation.subVectors(localStart, origin);
      const e = edge.lengthSq(), b = localDelta.dot(edge), c = localDelta.dot(separation), f = edge.dot(separation);
      let s = 0, t = 0;
      if (e <= EPS) s = THREE.MathUtils.clamp(-c / a, 0, 1);
      else {
        const denominator = a * e - b * b;
        if (denominator > EPS) s = THREE.MathUtils.clamp((b * f - c * e) / denominator, 0, 1);
        t = (b * s + f) / e;
        if (t < 0) { t = 0; s = THREE.MathUtils.clamp(-c / a, 0, 1); }
        else if (t > 1) { t = 1; s = THREE.MathUtils.clamp((b - c) / a, 0, 1); }
      }
      testPoint.copy(localStart).addScaledVector(localDelta, s); edgePoint.copy(origin).addScaledVector(edge, t);
      const distance = testPoint.distanceToSquared(edgePoint);
      if (distance < best) { best = distance; time = s; }
    }
    return time;
  }
  function visit(tree, node, callback) {
    state.nodeTests++;
    if (!node.box.intersectsBox(queryBox)) return;
    if (node.left) { visit(tree, node.left, callback); visit(tree, node.right, callback); return; }
    for (let i = node.start; i < node.end; i++) {
      const id = tree.order[i], offset = id * 6;
      expanded.min.fromArray(tree.bounds, offset); expanded.max.fromArray(tree.bounds, offset + 3);
      if (!expanded.intersectsBox(queryBox)) continue;
      readTriangle(tree, id); state.triangleTests++; callback();
    }
  }
  function prepare(collider, from, to, radius) {
    localStart.copy(from).applyMatrix4(collider.inverse); localEnd.copy(to).applyMatrix4(collider.inverse);
    localDelta.subVectors(localEnd, localStart);
    const localRadius = radius / collider.minScale;
    queryBox.setFromPoints([localStart, localEnd]).expandByScalar(localRadius);
    return localRadius;
  }
  function broad(collider, from, to, radius) {
    if (!collider.visible) return false;
    expanded.copy(collider.worldBox).expandByScalar(radius);
    if (expanded.containsPoint(from) || expanded.containsPoint(to)) return true;
    ray.origin.copy(from); ray.direction.subVectors(to, from);
    const length = ray.direction.length();
    if (length < EPS) return false;
    ray.direction.multiplyScalar(1 / length);
    const hit = ray.intersectBox(expanded, testPoint);
    return hit !== null && from.distanceToSquared(hit) <= length * length;
  }
  function sweep(from, to, radius) {
    let first = 1, contact = null;
    for (const collider of colliders) {
      if (!broad(collider, from, to, radius)) continue;
      const localRadius = prepare(collider, from, to, radius), radiusSq = localRadius * localRadius;
      visit(collider.tree, collider.tree.root, () => {
        const time = closestTime();
        if (distanceAt(time) > radiusSq) return;
        let low = 0, high = time;
        if (distanceAt(0) > radiusSq) {
          for (let step = 0; step < 18; step++) {
            const middle = (low + high) * .5;
            if (distanceAt(middle) <= radiusSq) high = middle; else low = middle;
          }
        } else high = 0;
        if (high > first) return;
        distanceAt(high);
        contactNormal.subVectors(testPoint, closest);
        if (contactNormal.lengthSq() < EPS) {
          triangle.getNormal(contactNormal);
          if (contactNormal.dot(localDelta) > 0) contactNormal.negate();
        } else contactNormal.normalize();
        // Resting contact must allow movement away from or along the surface.
        if (contactNormal.dot(localDelta) >= -EPS) return;
        first = high; normalHit.copy(contactNormal).applyMatrix3(collider.normalMatrix).normalize();
        contact = collider.mesh.name || collider.mesh.parent?.userData.asset_id || 'room geometry';
      });
    }
    return contact ? { time: first, normal: normalHit.clone(), name: contact } : null;
  }
  function deepestOverlap(point, radius) {
    let depth = 0, name = null; overlapPush.set(0, 0, 0);
    for (const collider of colliders) {
      if (!broad(collider, point, point, radius)) continue;
      const localRadius = prepare(collider, point, point, radius);
      visit(collider.tree, collider.tree.root, () => {
        triangle.closestPointToPoint(localStart, closest);
        const distance = localStart.distanceTo(closest), worldDepth = (localRadius - distance) * collider.minScale;
        if (worldDepth <= depth + SKIN * .1) return;
        contactNormal.subVectors(localStart, closest);
        if (distance < EPS) {
          triangle.getNormal(contactNormal);
          // If a moving object lands exactly on the camera, prefer the side
          // occupied by the last free pose rather than triangle winding.
          testPoint.copy(previous).applyMatrix4(collider.inverse).sub(closest);
          if (contactNormal.dot(testPoint) < 0) contactNormal.negate();
        } else contactNormal.multiplyScalar(1 / distance);
        if (contactNormal.lengthSq() < EPS) return;
        worldNormal.copy(contactNormal).applyMatrix3(collider.normalMatrix).normalize();
        depth = worldDepth; overlapPush.copy(worldNormal).multiplyScalar(depth + SKIN);
        name = collider.mesh.name;
      });
    }
    return name;
  }
  function targetInBounds(target) {
    const min = controls.minPan, max = controls.maxPan;
    return (!min || target.x >= min.x - EPS && target.y >= min.y - EPS && target.z >= min.z - EPS) &&
      (!max || target.x <= max.x + EPS && target.y <= max.y + EPS && target.z <= max.z + EPS);
  }
  function legalPose(position, target) {
    if (!targetInBounds(target)) return false;
    candidateOffset.subVectors(position, target); candidateSpherical.setFromVector3(candidateOffset);
    return candidateSpherical.radius >= (controls.minDistance ?? 0) - EPS &&
      candidateSpherical.radius <= (controls.maxDistance ?? Infinity) + EPS &&
      candidateSpherical.phi >= (controls.minPolarAngle ?? 0) - EPS &&
      candidateSpherical.phi <= (controls.maxPolarAngle ?? Math.PI) + EPS &&
      candidateSpherical.theta >= (controls.minAzimuthAngle ?? -Infinity) - EPS &&
      candidateSpherical.theta <= (controls.maxAzimuthAngle ?? Infinity) + EPS;
  }
  function reset() {
    previous.copy(camera.position); previousTarget.copy(controls.target);
    state.active = false; state.corrected = false; state.panLimited = false; state.correction = [0, 0, 0];
  }
  function update({ enabled = true } = {}) {
    state.triangleTests = 0; state.nodeTests = 0; state.lastContact = null; state.panLimited = false;
    if (!enabled) { reset(); return false; }
    const wasActive = state.active, previousRadius = state.radius;
    state.active = true;
    const near = camera.near, halfHeight = near * Math.tan(THREE.MathUtils.degToRad(camera.fov * .5)) / camera.zoom;
    // Sphere centered on the eye encloses all four near-plane corners, even on
    // wide screens. A small margin keeps grazing surfaces off the clipping plane.
    const radius = state.radius = Math.hypot(near, halfHeight, halfHeight * camera.aspect) + .035;
    desired.copy(camera.position); desiredTarget.copy(controls.target);
    const changedNearby = refresh(desired, radius);
    // An idle view never revisits triangle leaves unless a nearby object's
    // transform/visibility or the near-plane extent changed.
    if (wasActive && desired.distanceToSquared(previous) < EPS && Math.abs(previousRadius - radius) < EPS && !changedNearby) {
      previousTarget.copy(controls.target); state.corrected = false; state.correction = [0, 0, 0]; return false;
    }
    solved.copy(previous);
    let beganOverlapping = false, hasStopPose = false;
    // Recover shallow overlap after an animated prop or viewport resize.
    for (let pass = 0; pass < 6; pass++) {
      const contact = deepestOverlap(solved, radius);
      if (!contact) break;
      solved.add(overlapPush); state.lastContact = contact; beganOverlapping = true;
    }
    remaining.subVectors(desired, solved);
    for (let pass = 0; pass < 4 && remaining.lengthSq() > EPS; pass++) {
      const destination = solved.clone().add(remaining), hit = sweep(solved, destination, radius);
      if (!hit) { solved.copy(destination); break; }
      state.lastContact = hit.name;
      const advance = Math.max(0, hit.time - SKIN / remaining.length());
      solved.addScaledVector(remaining, advance);
      if (pass === 0 && !beganOverlapping) {
        stopPosition.copy(solved); stopTarget.lerpVectors(previousTarget, desiredTarget, advance);
        hasStopPose = legalPose(stopPosition, stopTarget);
      }
      remaining.multiplyScalar(1 - advance);
      const inward = remaining.dot(hit.normal);
      if (inward < 0) remaining.addScaledVector(hit.normal, -inward);
    }
    // Near-plane growth and stationary geometry contact share the same clearance.
    for (let pass = 0; pass < 6; pass++) {
      const contact = deepestOverlap(solved, radius);
      if (!contact) break;
      solved.add(overlapPush); state.lastContact = contact;
    }
    correction.subVectors(solved, desired);
    candidateTarget.copy(desiredTarget).add(correction);
    if (!targetInBounds(candidateTarget) && !beganOverlapping) {
      // Both endpoints are legal controls poses. The first swept contact is a
      // useful place to stop a pan/dolly; if an orbit chord falls below the
      // minimum radius, retain the previous legal pose instead. Neither path
      // feeds an out-of-bounds target back into OrbitControls' next update.
      if (hasStopPose) {
        solved.copy(stopPosition); candidateTarget.copy(stopTarget);
      } else if (legalPose(previous, previousTarget)) {
        solved.copy(previous); candidateTarget.copy(previousTarget);
      }
      state.panLimited = true;
      correction.subVectors(solved, desired);
    }
    state.corrected = correction.lengthSq() > EPS;
    if (state.corrected) {
      camera.position.copy(solved); controls.target.copy(candidateTarget);
      camera.lookAt(controls.target);
    }
    previous.copy(camera.position); previousTarget.copy(controls.target); state.correction = correction.toArray();
    return state.corrected;
  }
  return { update, reset, getState: () => ({ ...state, correction: [...state.correction] }) };
}
