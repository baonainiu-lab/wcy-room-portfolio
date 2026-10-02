import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const MODEL_URL = '/models/avatar/geometric-creator-v1.glb';
const PART_NAMES = ['AvatarBody', 'AvatarHead', 'AvatarArmL', 'AvatarArmR', 'AvatarTerminal', 'EyeL', 'EyeR'];

/**
 * A rigid, deterministic character: the GLB is also the design source.
 * update(delta, elapsed, { paused }) uses an internal clock so returning from a
 * hidden tab cannot skip a greeting. Pointer coordinates are normalized -1…1.
 * All scene additions, materials and textures owned here are removed by dispose.
 */
export async function createGeometricCreator({
  THREE, scene, renderer, camera, reducedMotion = false,
  onOpenPanel = () => {}, onReady = () => {},
}) {
  const gltf = await new GLTFLoader().loadAsync(MODEL_URL);
  const model = gltf.scene;
  const parts = Object.fromEntries(PART_NAMES.map((name) => [name, model.getObjectByName(name)]));
  const missing = PART_NAMES.filter((name) => !parts[name]);
  if (missing.length) {
    disposeModel(model);
    throw new Error(`GeometricCreator model is missing: ${missing.join(', ')}`);
  }

  // Placement belongs to the wrapper; animation never changes these transforms.
  const root = new THREE.Group();
  root.name = 'GeometricCreatorHost';
  root.userData.asset_id = 'avatar.creator';
  root.userData.avatarInteraction = 'about';
  root.add(model);
  scene.add(root);
  root.updateMatrixWorld(true);

  const head = parts.AvatarHead;
  const body = parts.AvatarBody;
  // The right arm holds the terminal. Only the free left arm waves.
  const wavingArm = parts.AvatarArmL;
  const headRest = head.rotation.clone();
  const armRest = wavingArm.rotation.clone();
  const bodyRestY = body.position.y;
  const eyes = [parts.EyeL, parts.EyeR].map((object) => ({ object, y: object.scale.y }));
  const materialSet = new Set();
  const geometrySet = new Set();
  let triangles = 0;
  let meshCount = 0;
  let drawCalls = 0;
  model.traverse((object) => {
    if (!object.isMesh) return;
    meshCount += 1;
    const geometry = object.geometry;
    geometrySet.add(geometry);
    triangles += (geometry.index?.count ?? geometry.attributes.position?.count ?? 0) / 3;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    drawCalls += geometry.groups.length || 1;
    for (const material of materials) {
      materialSet.add(material);
      material.toneMapped = false;
      if (material.transmission > 0) material.transmission = 0;
    }
    // The room is baked, and a live shadow map would make the whole room render
    // again on every blink. The contact shadow below stays attached to the feet.
    object.castShadow = false;
    object.receiveShadow = false;
  });

  // A baked room clears scene.environment. Bind a small neutral studio map only
  // to the character's materials rather than changing the room's appearance.
  let ownedEnvironment = null;
  let environmentTexture = scene.environment;
  if (!environmentTexture) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    const studio = new RoomEnvironment();
    ownedEnvironment = pmrem.fromScene(studio, 0.04, 0.1, 20);
    environmentTexture = ownedEnvironment.texture;
    studio.dispose();
    pmrem.dispose();
  }
  const materialDefaults = new Map();
  for (const material of materialSet) {
    materialDefaults.set(material, { emissiveIntensity: material.emissiveIntensity ?? 0 });
    if ('envMap' in material) {
      material.envMap = environmentTexture;
      material.envMapIntensity = 0.35;
    }
    material.needsUpdate = true;
  }

  const lightRig = new THREE.Group();
  lightRig.name = 'GeometricCreatorLighting';
  const sky = new THREE.HemisphereLight('#d9eaff', '#6f4c36', 0.38);
  const key = new THREE.DirectionalLight('#ffedd7', 1.0);
  key.position.set(-2.4, 4, 3.5);
  key.target.position.set(0, 1, 0);
  const rim = new THREE.DirectionalLight('#b5d9ff', 0.25);
  rim.position.set(2, 2.5, -1.5);
  rim.target.position.set(0, 1.1, 0);
  for (const light of [sky, key, rim]) {
    light.castShadow = false;
    light.userData.avatarLight = true;
  }
  lightRig.add(sky, key, key.target, rim, rim.target);
  root.add(lightRig);

  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(32, 32, 1, 32, 32, 31);
  gradient.addColorStop(0, 'rgba(8,12,15,0.38)');
  gradient.addColorStop(0.42, 'rgba(8,12,15,0.17)');
  gradient.addColorStop(1, 'rgba(8,12,15,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);
  const shadowTexture = new THREE.CanvasTexture(canvas);
  const shadowMaterial = new THREE.MeshBasicMaterial({
    map: shadowTexture, transparent: true, depthWrite: false,
    toneMapped: false, opacity: 0.85,
  });
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(1.12, 0.76), shadowMaterial);
  shadow.name = 'GeometricCreatorContactShadow';
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.set(0, 0.012, 0.02);
  shadow.raycast = () => {};
  root.add(shadow);

  // Proxies inherit each part's animated transform. Material visibility hides
  // their pixels while retaining raycasting, unlike disabling the whole object.
  const proxyMaterial = new THREE.MeshBasicMaterial({ visible: false });
  const pickTargets = [];
  const interactables = [];
  const inverse = new THREE.Matrix4();
  const relative = new THREE.Matrix4();
  const corner = new THREE.Vector3();
  const skipParts = new Set(['AvatarHead', 'AvatarArmL', 'AvatarArmR', 'AvatarTerminal']);
  const proxyForPart = (parent, action, excludeNestedParts = false) => {
    root.updateMatrixWorld(true);
    inverse.copy(parent.matrixWorld).invert();
    const box = new THREE.Box3();
    parent.traverse((object) => {
      if (!object.isMesh || !object.geometry?.attributes.position) return;
      if (excludeNestedParts) {
        for (let ancestor = object; ancestor && ancestor !== parent; ancestor = ancestor.parent) {
          if (skipParts.has(ancestor.name)) return;
        }
      }
      object.geometry.computeBoundingBox();
      const local = object.geometry.boundingBox;
      relative.multiplyMatrices(inverse, object.matrixWorld);
      for (let i = 0; i < 8; i += 1) {
        corner.set(i & 1 ? local.max.x : local.min.x, i & 2 ? local.max.y : local.min.y, i & 4 ? local.max.z : local.min.z);
        box.expandByPoint(corner.applyMatrix4(relative));
      }
    });
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    size.addScalar(action === 'work' ? 0.028 : 0.016);
    const proxy = new THREE.Mesh(new THREE.BoxGeometry(size.x, size.y, size.z), proxyMaterial);
    proxy.name = `${parent.name}Interaction`;
    proxy.position.copy(box.getCenter(new THREE.Vector3()));
    proxy.userData.avatarInteraction = action;
    proxy.userData.asset_id = action === 'work' ? 'avatar.terminal' : 'avatar.creator';
    parent.add(proxy);
    pickTargets.push(proxy);
    interactables.push({ object: proxy, action });
  };
  proxyForPart(body, 'about', true);
  proxyForPart(head, 'about');
  proxyForPart(parts.AvatarArmL, 'about', true);
  proxyForPart(parts.AvatarArmR, 'about', true);
  proxyForPart(parts.AvatarTerminal, 'work');
  // Include boots/legs when the body pivot is a separate sibling in the GLB.
  const footProxy = new THREE.Mesh(new THREE.BoxGeometry(0.51, 0.56, 0.37), proxyMaterial);
  footProxy.name = 'GeometricCreatorFeetInteraction';
  footProxy.position.set(0, 0.29, 0.025);
  footProxy.userData.avatarInteraction = 'about';
  footProxy.userData.asset_id = 'avatar.creator';
  model.add(footProxy);
  pickTargets.push(footProxy);
  interactables.push({ object: footProxy, action: 'about' });
  root.updateMatrixWorld(true);

  let disposed = false;
  let clock = 0;
  let waveStarted = -Infinity;
  let lastInteractionAt = -Infinity;
  let lastAction = null;
  let hovered = false;
  let pointerActive = false;
  let pointerX = 0;
  let pointerY = 0;
  let currentYaw = 0;
  let currentPitch = 0;
  let themeBlend = 0;
  let themeTarget = 0;
  let greetingCount = 0;
  const worldPosition = new THREE.Vector3();
  const viewDirection = new THREE.Vector3();
  const rootRotation = new THREE.Quaternion();

  const applyLighting = () => {
    sky.intensity = THREE.MathUtils.lerp(0.26, 0.43, themeBlend);
    key.intensity = THREE.MathUtils.lerp(0.85, 1.12, themeBlend);
    rim.intensity = THREE.MathUtils.lerp(0.29, 0.19, themeBlend);
    key.color.set(themeBlend > 0.5 ? '#fff3e2' : '#ffe1bf');
    for (const material of materialSet) {
      if ('envMapIntensity' in material) material.envMapIntensity = THREE.MathUtils.lerp(0.30, 0.43, themeBlend);
      const base = materialDefaults.get(material).emissiveIntensity;
      if (base > 0) material.emissiveIntensity = base * THREE.MathUtils.lerp(1.08, 0.8, themeBlend) * (hovered ? 1.12 : 1);
    }
  };

  const resolvePick = (object) => {
    if (disposed || !object) return null;
    const candidate = object.object ?? object;
    // Validate ownership before interpreting asset IDs from another room object.
    let owned = false;
    for (let ancestor = candidate; ancestor; ancestor = ancestor.parent) {
      if (ancestor === root) { owned = true; break; }
    }
    if (!owned) return null;
    for (let ancestor = candidate; ancestor && ancestor !== root; ancestor = ancestor.parent) {
      if (ancestor.userData.avatarInteraction) return ancestor.userData.avatarInteraction;
      if (ancestor === parts.AvatarTerminal || ancestor.userData.asset_id === 'avatar.terminal') return 'work';
    }
    return 'about';
  };

  const controller = {
    root,
    pickTargets,
    interactables,
    resolvePick,
    setPlacement(position, yaw = 0, scale = 1) {
      if (disposed) return;
      if (Array.isArray(position)) root.position.fromArray(position);
      else if (position) root.position.set(position.x, position.y, position.z);
      root.rotation.y = yaw;
      if (typeof scale === 'number') root.scale.setScalar(scale);
      else if (scale) root.scale.set(scale.x, scale.y, scale.z);
      root.updateMatrixWorld(true);
    },
    setPointer(ndc) {
      pointerActive = Boolean(ndc && Number.isFinite(ndc.x) && Number.isFinite(ndc.y));
      if (pointerActive) {
        pointerX = THREE.MathUtils.clamp(ndc.x, -1, 1);
        pointerY = THREE.MathUtils.clamp(ndc.y, -1, 1);
      }
    },
    setHovered(value) {
      hovered = Boolean(value);
      applyLighting();
    },
    setTheme(isDay, immediate = false) {
      themeTarget = isDay ? 1 : 0;
      if (immediate || reducedMotion) themeBlend = themeTarget;
      applyLighting();
    },
    greet() {
      if (disposed || clock - waveStarted < 1.95) return false;
      waveStarted = clock;
      greetingCount += 1;
      return true;
    },
    handlePick(target) {
      if (disposed) return false;
      const action = typeof target === 'string' ? target : resolvePick(target);
      if (action !== 'about' && action !== 'work') return false;
      // A pointer-up and its synthesized click must not open the panel twice.
      const now = performance.now();
      if (now - lastInteractionAt < 450) return false;
      lastInteractionAt = now;
      lastAction = action;
      controller.greet();
      onOpenPanel(action);
      return true;
    },
    update(delta, _elapsed, { paused = false } = {}) {
      if (disposed || paused) return;
      const dt = THREE.MathUtils.clamp(Number.isFinite(delta) ? delta : 0, 0, 0.05);
      clock += dt;
      if (Math.abs(themeBlend - themeTarget) > 0.001) {
        themeBlend = THREE.MathUtils.damp(themeBlend, themeTarget, 5, dt);
        applyLighting();
      }
      if (reducedMotion) return;

      // Turn toward the visitor, with a modest pointer offset. Deriving the
      // camera direction in root-local coordinates works after placement/yaw.
      let targetYaw = 0;
      let targetPitch = 0;
      if (pointerActive || hovered) {
        head.getWorldPosition(worldPosition);
        viewDirection.copy(camera.position).sub(worldPosition);
        root.getWorldQuaternion(rootRotation).invert();
        viewDirection.applyQuaternion(rootRotation);
        targetYaw = THREE.MathUtils.clamp(Math.atan2(viewDirection.x, viewDirection.z) + pointerX * 0.10, -0.32, 0.32);
        targetPitch = THREE.MathUtils.clamp(-pointerY * 0.08, -0.09, 0.09);
      }
      currentYaw = THREE.MathUtils.damp(currentYaw, targetYaw, 5, dt);
      currentPitch = THREE.MathUtils.damp(currentPitch, targetPitch, 5, dt);
      body.position.y = bodyRestY + Math.sin(clock * 1.75) * 0.004;

      const waveTime = clock - waveStarted;
      const waveIn = THREE.MathUtils.smoothstep(waveTime, 0, 0.35);
      const waveOut = 1 - THREE.MathUtils.smoothstep(waveTime, 1.45, 1.95);
      const waveWeight = waveTime >= 0 && waveTime <= 1.95 ? waveIn * waveOut : 0;
      wavingArm.rotation.copy(armRest);
      wavingArm.rotation.z += waveWeight * (2.03 + Math.sin(Math.max(0, waveTime - 0.3) * 13) * 0.20);
      wavingArm.rotation.x -= waveWeight * 0.16;
      head.rotation.copy(headRest);
      head.rotation.y += currentYaw;
      head.rotation.x += currentPitch + waveWeight * Math.sin(Math.max(0, waveTime) * 5.4) * 0.055;

      // A deterministic blink every 4.8 seconds; the closed scale stays nonzero.
      const blinkPhase = clock % 4.8;
      const blink = blinkPhase < 0.16 ? Math.sin(blinkPhase / 0.16 * Math.PI) : 0;
      for (const eye of eyes) eye.object.scale.y = eye.y * (1 - blink * 0.94);
      root.updateMatrixWorld(true);
    },
    getDebugState() {
      return {
        loaded: !disposed, model: MODEL_URL, reducedMotion, hovered,
        pointerActive, theme: themeTarget ? 'day' : 'night', greetingCount,
        waving: !reducedMotion && clock - waveStarted < 1.95,
        lastAction, meshCount, triangles: Math.round(triangles),
        materialCount: materialSet.size, estimatedModelDrawCalls: drawCalls,
        pickTargetCount: pickTargets.length,
        placement: root.position.toArray(), yaw: root.rotation.y, scale: root.scale.toArray(),
      };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      root.removeFromParent();
      for (const proxy of pickTargets) proxy.geometry.dispose();
      proxyMaterial.dispose();
      shadow.geometry.dispose();
      shadowMaterial.dispose();
      shadowTexture.dispose();
      for (const geometry of geometrySet) geometry.dispose();
      const textures = new Set();
      for (const material of materialSet) {
        for (const value of Object.values(material)) {
          if (value?.isTexture && value !== environmentTexture) textures.add(value);
        }
        material.dispose();
      }
      for (const texture of textures) texture.dispose();
      ownedEnvironment?.dispose();
      pickTargets.length = 0;
      interactables.length = 0;
    },
  };
  applyLighting();
  onReady(controller);
  return controller;

  function disposeModel(object) {
    const geometries = new Set();
    const materials = new Set();
    const textures = new Set();
    object.traverse((node) => {
      if (!node.isMesh) return;
      geometries.add(node.geometry);
      for (const material of [].concat(node.material)) materials.add(material);
    });
    for (const material of materials) {
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      material.dispose();
    }
    for (const geometry of geometries) geometry.dispose();
    for (const texture of textures) texture.dispose();
  }
}
