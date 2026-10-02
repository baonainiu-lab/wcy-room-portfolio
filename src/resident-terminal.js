import gsap from 'gsap';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// One Blender-authored object serves both the welcome and the finished desk.
// This module owns its GPU resources; the intro controller only borrows it.
export function createResidentTerminal({ THREE, renderer, room, welcomeGltf, reducedMotion = false }) {
  let root;
  room.traverse(node => { if (node.userData.asset_id === 'folding_drawing_terminal') root = node; });
  if (!root) throw new Error('The room is missing its folding creative terminal');
  const model = welcomeGltf.scene, clips = welcomeGltf.animations;
  const opening = clips.filter(clip => clip.name === 'TerminalUnfold');
  if (opening.length !== 1) throw new Error('Resident terminal requires the Blender TerminalUnfold clip');
  room.updateWorldMatrix(true, true);
  const oldBox = new THREE.Box3().setFromObject(root, true);
  const oldSize = oldBox.getSize(new THREE.Vector3());
  const oldChildren = [...root.children], originalResidentTag = root.userData.resident_terminal;
  const meshes = [], geometries = new Set(), materials = new Set(), textures = new Set();
  let oldMeshCount = 0, oldTriangles = 0;
  root.traverse(node => {
    if (node.isMesh) { oldMeshCount++; oldTriangles += (node.geometry.index?.count ?? node.geometry.attributes.position.count) / 3; }
  });
  const authoredNodes = new Map();
  model.traverse(node => {
    authoredNodes.set(node.userData.name ?? node.name, node);
    node.userData.owner_asset_id = 'folding_drawing_terminal';
    if (!node.isMesh) return;
    meshes.push(node); geometries.add(node.geometry);
    node.castShadow = node.receiveShadow = false;
    for (const material of [].concat(node.material)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  for (const [name, id] of [['seed.lid', 'terminal_lid'], ['seed.dial', 'terminal_dial'], ['seed.rail', 'terminal_rail']]) {
    const node = authoredNodes.get(name);
    if (!node) throw new Error(`Resident terminal is missing ${name}`);
    node.userData.asset_id = id;
    node.userData.hover_scale = 1.08;
  }
  // Release the temporary action immediately after sampling. Keeping a second
  // mixer bound would make its cached original pose fight the intro's mixer.
  const sample = time => {
    const mixer = new THREE.AnimationMixer(model), action = mixer.clipAction(opening[0]);
    action.setLoop(THREE.LoopOnce, 1); action.clampWhenFinished = true; action.play(); action.paused = true;
    action.time = time; mixer.update(0);
    const pose = new Map(); model.traverse(node => pose.set(node, {
      position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone(),
    }));
    mixer.stopAllAction(); mixer.uncacheRoot(model);
    for (const [node, transform] of pose) {
      node.position.copy(transform.position); node.quaternion.copy(transform.quaternion); node.scale.copy(transform.scale);
    }
    model.updateWorldMatrix(true, true);
  };
  sample(opening[0].duration);
  const modelBox = new THREE.Box3().setFromObject(model, true);
  const modelFloor = modelBox.getCenter(new THREE.Vector3()); modelFloor.y = modelBox.min.y;
  const carrier = new THREE.Group(); carrier.name = 'Resident creative terminal carrier';
  const normalization = new THREE.Group(); normalization.name = 'Terminal authored origin normalization';
  normalization.position.copy(modelFloor).negate(); normalization.add(model); carrier.add(normalization);
  oldChildren.forEach(node => root.remove(node)); root.add(carrier);
  root.userData.resident_terminal = true;
  root.updateWorldMatrix(true, true);
  const candidateBox = new THREE.Box3().setFromObject(carrier, true);
  const candidateSize = candidateBox.getSize(new THREE.Vector3());
  const fit = Math.min(...['x', 'y', 'z'].map(axis => oldSize[axis] / candidateSize[axis])) * .97;
  if (!(fit > 0 && Number.isFinite(fit))) throw new Error('Resident terminal has invalid fit bounds');
  carrier.scale.setScalar(fit); root.updateWorldMatrix(true, true);
  candidateBox.setFromObject(carrier, true);
  const desired = oldBox.getCenter(new THREE.Vector3()); desired.y = oldBox.min.y;
  const current = candidateBox.getCenter(new THREE.Vector3()); current.y = candidateBox.min.y;
  const worldOrigin = carrier.getWorldPosition(new THREE.Vector3());
  carrier.position.copy(root.worldToLocal(worldOrigin.add(desired).sub(current)));
  root.updateWorldMatrix(true, true);
  // The old export's terminal bottom sits slightly inside the actual desk.
  // Recover the supporting triangle surface at this footprint instead of
  // inheriting that error or using the desk's higher, unrelated outer rim.
  let desk;
  room.traverse(node => { if (node.userData.asset_id === 'furniture.desk') desk = node; });
  if (!desk) throw new Error('Resident terminal requires its desk support');
  const deskBox = new THREE.Box3().setFromObject(desk, true);
  candidateBox.setFromObject(carrier, true);
  const raycaster = new THREE.Raycaster(), down = new THREE.Vector3(0, -1, 0);
  const normal = new THREE.Vector3(), normalMatrix = new THREE.Matrix3();
  const surfaceSamples = [];
  for (const fx of [0, .5, 1]) for (const fz of [0, .5, 1]) {
    const x = THREE.MathUtils.lerp(candidateBox.min.x, candidateBox.max.x, fx);
    const z = THREE.MathUtils.lerp(candidateBox.min.z, candidateBox.max.z, fz);
    raycaster.set(new THREE.Vector3(x, deskBox.max.y + .05, z), down);
    raycaster.far = deskBox.max.y - deskBox.min.y + .1;
    const hit = raycaster.intersectObject(desk, true).find(intersection => {
      normalMatrix.getNormalMatrix(intersection.object.matrixWorld);
      return intersection.face && normal.copy(intersection.face.normal).applyNormalMatrix(normalMatrix).y > .5;
    });
    if (hit) surfaceSamples.push({ x, z, y: hit.point.y });
  }
  if (!surfaceSamples.length) throw new Error('Resident terminal footprint has no measured desk surface');
  const supportSurface = Math.max(...surfaceSamples.map(point => point.y)), supportClearance = .003;
  const supportLift = Math.max(0, supportSurface + supportClearance - candidateBox.min.y);
  if (supportLift > 0) {
    const correctedWorldOrigin = carrier.getWorldPosition(new THREE.Vector3()); correctedWorldOrigin.y += supportLift;
    carrier.position.copy(root.worldToLocal(correctedWorldOrigin)); root.updateWorldMatrix(true, true);
  }
  const home = { position: carrier.position.clone(), quaternion: carrier.quaternion.clone(), scale: carrier.scale.clone() };
  const worldHome = { position: new THREE.Vector3(), quaternion: new THREE.Quaternion(), scale: new THREE.Vector3() };
  carrier.matrixWorld.decompose(worldHome.position, worldHome.quaternion, worldHome.scale);
  const finalBox = new THREE.Box3().setFromObject(carrier, true);

  const probeScene = new RoomEnvironment(), generator = new THREE.PMREMGenerator(renderer);
  let reflection;
  try { reflection = generator.fromScene(probeScene, .04); }
  finally { probeScene.dispose(); generator.dispose(); }
  const fill = new THREE.HemisphereLight('#fffaed', '#6e818e', 0);
  const sun = new THREE.DirectionalLight('#fff1d9', 0);
  const sunTarget = new THREE.Object3D(); sun.position.set(-6, 14, 10); sun.target = sunTarget;
  fill.name = 'Terminal welcome fill'; sun.name = 'Terminal welcome key';
  fill.castShadow = sun.castShadow = false;
  carrier.add(fill, sun, sunTarget);
  const emissive = new Map();
  materials.forEach(material => {
    emissive.set(material, material.emissiveIntensity);
    material.envMap = reflection.texture; material.needsUpdate = true;
  });
  let disposed = false, introLight = 0, isDay = true, dayMix = 1, clockDriven = false;
  const appearance = { environment: 1.1, screen: .84 };
  function applyLight() {
    const progress = THREE.MathUtils.clamp(introLight, 0, 1);
    fill.intensity = 2.1 * progress; sun.intensity = 3.1 * progress;
    // Keep zero-intensity lights registered at the final endpoint so the
    // shader does not need a different light-count program at touchdown.
    fill.visible = sun.visible = true;
    for (const material of materials) {
      material.envMapIntensity = THREE.MathUtils.lerp(appearance.environment, .9, progress);
      material.emissiveIntensity = emissive.get(material) * THREE.MathUtils.lerp(appearance.screen, 1, progress);
    }
  }
  sample(0); applyLight();
  return {
    model, clips, carrier, root,
    attachHome() {
      if (disposed) return;
      root.add(carrier); carrier.position.copy(home.position); carrier.quaternion.copy(home.quaternion); carrier.scale.copy(home.scale);
      sample(opening[0].duration); carrier.visible = true; carrier.updateWorldMatrix(true, true);
      introLight = 0; applyLight();
    },
    detachForIntro(scene) {
      if (disposed) return;
      carrier.updateWorldMatrix(true, true); scene.attach(carrier);
      return carrier;
    },
    getHomeWorldPose: () => worldHome,
    setDayMix(value) {
      if (disposed || !Number.isFinite(value)) return;
      if (!clockDriven) { gsap.killTweensOf(appearance); clockDriven = true; }
      dayMix = THREE.MathUtils.clamp(value, 0, 1); isDay = dayMix >= .5;
      appearance.environment = THREE.MathUtils.lerp(.3, 1.1, dayMix);
      appearance.screen = THREE.MathUtils.lerp(.47, .84, dayMix);
      applyLight();
    },
    setTheme(day, duration = 1.5) {
      if (disposed) return;
      clockDriven = false; dayMix = day ? 1 : 0;
      isDay = !!day; gsap.killTweensOf(appearance);
      const destination = { environment: isDay ? 1.1 : .3, screen: isDay ? .84 : .47 };
      if (reducedMotion || duration <= 0) { Object.assign(appearance, destination); applyLight(); }
      else gsap.to(appearance, { ...destination, duration, ease: 'power2.inOut', onUpdate: applyLight });
    },
    setIntroLight(progress) {
      if (disposed || !Number.isFinite(progress)) return;
      introLight = THREE.MathUtils.clamp(progress, 0, 1); applyLight();
    },
    getState: () => ({ revision: 1, assetId: 'folding_drawing_terminal', resident: true, disposed,
      attachedHome: carrier.parent === root, introLight, day: isDay, dayMix,
      homePosition: worldHome.position.toArray(), homeScale: worldHome.scale.toArray(),
      finalBounds: { min: finalBox.min.toArray(), max: finalBox.max.toArray() },
      originalBounds: { min: oldBox.min.toArray(), max: oldBox.max.toArray() },
      support: { assetId: 'furniture.desk', surfaceHeight: supportSurface, clearance: supportClearance, lift: supportLift, samples: surfaceSamples },
      meshCount: meshes.length, oldMeshCount, drawCallDelta: meshes.length - oldMeshCount,
      triangles: meshes.reduce((count, mesh) => count + (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3, 0), oldTriangles,
      parts: ['terminal_lid', 'terminal_dial', 'terminal_rail'],
      environmentIntensity: appearance.environment, screenIntensity: appearance.screen,
    }),
    dispose() {
      if (disposed) return;
      disposed = true; gsap.killTweensOf(appearance); carrier.removeFromParent();
      oldChildren.forEach(node => root.add(node));
      if (originalResidentTag === undefined) delete root.userData.resident_terminal;
      else root.userData.resident_terminal = originalResidentTag;
      // The retained original room children share their atlases with many
      // other objects. Only the separately loaded welcome GLB is ours.
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
      textures.forEach(texture => texture.dispose()); reflection.dispose();
    },
  };
}
