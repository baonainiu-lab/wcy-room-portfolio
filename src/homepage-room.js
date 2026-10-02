import { createSceneMotion } from './scene-motion.js';

const RAD = Math.PI / 180;
const LIMIT = 35 * RAD;
const AUTO_LIMIT = 18 * RAD;
const AUTO_PERIOD = 26;

// A second scene, not a second renderer or model download. Object transforms
// belong to the preview; all geometry, lightmaps and shader materials are shared.
export async function createHomepageRoom({ THREE, renderer, room, element, canvas, reducedMotion = false }) {
  if (!room || !element || !canvas?.parentNode) throw new Error('Homepage room requires a loaded room and a mounted canvas.');
  const document = canvas.ownerDocument;
  const view = document.defaultView;
  const original = {
    parent: canvas.parentNode, next: canvas.nextSibling,
    size: renderer.getSize(new THREE.Vector2()), pixelRatio: renderer.getPixelRatio(),
    clearColor: renderer.getClearColor(new THREE.Color()), clearAlpha: renderer.getClearAlpha(),
    autoClear: renderer.autoClear, scissorTest: renderer.getScissorTest(),
    scissor: renderer.getScissor(new THREE.Vector4()), style: canvas.getAttribute('style'),
  };
  const scene = new THREE.Scene();
  scene.name = 'HomepageRoomPreview';
  for (let parent = room.parent; parent; parent = parent.parent) {
    if (!parent.isScene) continue;
    scene.environment = parent.environment;
    scene.environmentIntensity = parent.environmentIntensity;
    scene.environmentRotation.copy(parent.environmentRotation);
    break;
  }
  room.updateWorldMatrix(true, true);
  const clone = room.clone(true);
  clone.name = 'HomepageRoomClone';
  room.matrixWorld.decompose(clone.position, clone.quaternion, clone.scale);
  const roomBounds = new THREE.Box3().setFromObject(room);
  const center = roomBounds.getCenter(new THREE.Vector3());
  center.y = roomBounds.min.y;
  clone.position.sub(center);
  const rotating = new THREE.Group();
  rotating.name = 'HomepageRoomTurntable';
  rotating.add(clone); scene.add(rotating);
  const components = new Map(), snapshots = new WeakMap();
  clone.traverse(node => {
    if (node.isMesh) { node.castShadow = false; node.receiveShadow = false; }
    if (!node.userData.asset_id) return;
    components.set(node.userData.asset_id, node);
    snapshots.set(node, { position: node.position.clone(), rotation: node.rotation.clone(), scale: node.scale.clone() });
  });
  scene.updateMatrixWorld(true);
  const motion = createSceneMotion({ components, snapshots, reducedMotion });
  const motionOptions = { enabled: true, hovered: null };
  const direction = new THREE.Vector3(11, 8.37, 18.4).normalize();
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize();
  const up = new THREE.Vector3().crossVectors(direction, right).normalize();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 200);
  const bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  const point = new THREE.Vector3();
  const cosine = Math.cos(LIMIT), sine = Math.sin(LIMIT);
  // Exact projected extrema for every vertex across the entire allowed yaw,
  // including extrema between the endpoints. This avoids clipping at drag limits.
  function extend(axis, prefix) {
    const a = axis.x * point.x + axis.z * point.z;
    const b = axis.x * point.z - axis.z * point.x;
    const c = axis.y * point.y;
    let min = Math.min(a * cosine - b * sine + c, a * cosine + b * sine + c);
    let max = Math.max(a * cosine - b * sine + c, a * cosine + b * sine + c);
    const phase = Math.atan2(b, a);
    for (let turn = -1; turn <= 1; turn++) {
      const angle = phase + turn * Math.PI;
      if (angle < -LIMIT || angle > LIMIT) continue;
      const value = a * Math.cos(angle) + b * Math.sin(angle) + c;
      min = Math.min(min, value); max = Math.max(max, value);
    }
    bounds[`min${prefix}`] = Math.min(bounds[`min${prefix}`], min);
    bounds[`max${prefix}`] = Math.max(bounds[`max${prefix}`], max);
  }
  clone.traverseVisible(node => {
    const positions = node.isMesh && node.geometry.attributes.position;
    if (!positions) return;
    for (let index = 0; index < positions.count; index++) {
      point.fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld);
      extend(right, 'X'); extend(up, 'Y');
    }
  });
  if (!Number.isFinite(bounds.minX)) throw new Error('Homepage room has no renderable geometry.');
  const target = right.clone().multiplyScalar((bounds.minX + bounds.maxX) / 2)
    .addScaledVector(up, (bounds.minY + bounds.maxY) / 2);
  const extent = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
  camera.position.copy(target).addScaledVector(direction, Math.max(30, extent * 3));
  camera.far = Math.max(100, extent * 6);
  camera.lookAt(target); camera.updateMatrixWorld(true);

  let active = true, frameCount = 0, elapsed = 0, yaw = 0, manualYaw = 0, manualWeight = 0;
  let width = 0, height = 0, pixelRatio = 0, resizeObserver;
  let pointerId = null, startX = 0, startY = 0, startYaw = 0, dragging = false;
  function resize() {
    if (!active) return;
    const rect = element.getBoundingClientRect();
    const nextWidth = Math.max(1, Math.round(rect.width));
    const nextHeight = Math.max(1, Math.round(rect.height));
    const nextRatio = Math.min(view.devicePixelRatio || 1, 2);
    if (width === nextWidth && height === nextHeight && pixelRatio === nextRatio) return;
    width = nextWidth; height = nextHeight; pixelRatio = nextRatio;
    renderer.setPixelRatio(pixelRatio); renderer.setSize(width, height, false);
    renderer.setViewport(0, 0, width, height); renderer.setScissorTest(false);
    const aspect = width / height;
    const halfHeight = Math.max((bounds.maxY - bounds.minY) / 2, (bounds.maxX - bounds.minX) / (2 * aspect)) * 1.075 + .025;
    camera.left = -halfHeight * aspect; camera.right = halfHeight * aspect;
    camera.top = halfHeight; camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
  }
  function finishPointer(event) {
    if (event && event.pointerId !== pointerId) return;
    const captured = pointerId;
    pointerId = null; dragging = false;
    element.classList.remove('is-dragging');
    if (captured !== null && element.hasPointerCapture?.(captured)) element.releasePointerCapture(captured);
  }
  function pointerDown(event) {
    if (!active || pointerId !== null || event.isPrimary === false || (event.pointerType === 'mouse' && event.button !== 0)) return;
    pointerId = event.pointerId; startX = event.clientX; startY = event.clientY; startYaw = yaw;
    element.setPointerCapture?.(pointerId);
  }
  function pointerMove(event) {
    if (event.pointerId !== pointerId) return;
    const dx = event.clientX - startX, dy = event.clientY - startY;
    if (!dragging) {
      if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 6) { finishPointer(event); return; }
      if (Math.abs(dx) < 6) return;
      dragging = true; element.classList.add('is-dragging');
    }
    if (event.cancelable) event.preventDefault();
    manualYaw = Math.max(-LIMIT, Math.min(LIMIT, startYaw + dx / Math.max(width, 1) * 1.8));
    manualWeight = 1;
  }
  const listeners = { pointerdown: pointerDown, pointermove: pointerMove, pointerup: finishPointer, pointercancel: finishPointer, lostpointercapture: finishPointer };
  function release() {
    if (!active) return;
    active = false; finishPointer();
    resizeObserver?.disconnect();
    view.removeEventListener('resize', resize);
    for (const [name, listener] of Object.entries(listeners)) element.removeEventListener(name, listener);
    element.classList.remove('is-live', 'is-dragging'); canvas.classList.remove('entry-live-canvas');
    if (original.next?.parentNode === original.parent) original.parent.insertBefore(canvas, original.next);
    else original.parent.appendChild(canvas);
    if (original.style === null) canvas.removeAttribute('style'); else canvas.setAttribute('style', original.style);
    renderer.setPixelRatio(original.pixelRatio);
    const fullWidth = view.innerWidth || original.size.x, fullHeight = view.innerHeight || original.size.y;
    renderer.setSize(fullWidth, fullHeight); renderer.setViewport(0, 0, fullWidth, fullHeight);
    renderer.setScissor(original.scissor); renderer.setScissorTest(original.scissorTest);
    renderer.setClearColor(original.clearColor, original.clearAlpha); renderer.autoClear = original.autoClear;
    // No disposal: clone and original deliberately share their GPU resources.
    scene.remove(rotating); rotating.remove(clone);
  }
  const controller = {
    update(delta) {
      if (!active || document.hidden) return;
      const step = Math.max(0, Math.min(delta, .05));
      if (!reducedMotion) elapsed += step;
      if (!dragging && !reducedMotion) manualWeight *= Math.exp(-step * .8);
      const automatic = reducedMotion ? 0 : Math.sin(elapsed * Math.PI * 2 / AUTO_PERIOD) * AUTO_LIMIT;
      const desired = reducedMotion && manualWeight ? manualYaw : automatic * (1 - manualWeight) + manualYaw * manualWeight;
      yaw += (desired - yaw) * (1 - Math.exp(-step * (dragging ? 14 : 4)));
      rotating.rotation.y = yaw;
      rotating.position.y = reducedMotion ? 0 : Math.sin(elapsed * Math.PI * 2 / 8) * .012;
      motionOptions.enabled = !dragging; motion.update(step, motionOptions);
    },
    render() {
      if (!active || document.hidden) return;
      renderer.setClearColor(0x000000, 0); renderer.autoClear = true;
      renderer.render(scene, camera); frameCount++;
      if (frameCount === 1) element.classList.add('is-live');
    },
    release,
    getState: () => ({ revision: 7, active, frameCount, yawDegrees: yaw / RAD, dragging,
      viewport: { width, height, pixelRatio }, componentCount: components.size,
      motion: motion.getState(), sharedResources: true }),
  };
  try {
    element.appendChild(canvas); canvas.classList.add('entry-live-canvas');
    for (const [name, listener] of Object.entries(listeners)) element.addEventListener(name, listener);
    resize();
    const ResizeObserver = view.ResizeObserver;
    if (ResizeObserver) { resizeObserver = new ResizeObserver(resize); resizeObserver.observe(element); }
    view.addEventListener('resize', resize, { passive: true });
    if (renderer.compileAsync) await renderer.compileAsync(scene, camera);
    controller.render();
    return controller;
  } catch (error) { release(); throw error; }
}
