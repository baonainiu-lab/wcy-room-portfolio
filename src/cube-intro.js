/* Choreography adapted from Andrew Woan's firstIntro / secondIntro (MIT, 2023).
 * Source and full license: public/licenses/abigail-bloom/. The persistent room,
 * Blender terminal clip, transforms, styling and input binding are project-specific. */
import * as THREE from 'three';
import gsap from 'gsap';
import { bindIntroInput } from './intro-input.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createIntroBackdrop } from './intro-backdrop.js';

function splitText(element) {
  const existing = [...element.querySelectorAll('.intro-char')];
  if (existing.length) return existing;
  const text = element.textContent;
  element.setAttribute('aria-label', text);
  const walker = element.ownerDocument.createTreeWalker(element, 4);
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const fragment = element.ownerDocument.createDocumentFragment();
    for (const character of Array.from(node.textContent)) {
      const mask = element.ownerDocument.createElement('span'); mask.className = 'intro-char-mask'; mask.setAttribute('aria-hidden', 'true');
      const letter = element.ownerDocument.createElement('span'); letter.className = 'intro-char'; letter.textContent = character === ' ' ? '\u00a0' : character;
      mask.append(letter); fragment.append(mask);
    }
    node.replaceWith(fragment);
  }
  return [...element.querySelectorAll('.intro-char')];
}

const smooth = value => value * value * value * (value * (value * 6 - 15) + 10);
const PLAYBACK_RATE = 1.25;

// Semantic triangle ranges audited against the original Blender V15 export.
// Read the existing mesh to measure separate wall/floor members; never use the
// merged architecture AABB, whose empty room interior is not a solid obstacle.
const SHELL_PART_RANGES = {"WEB8_room_static__baked__A0":[[0,20],[20,20],[40,20],[60,20],[80,20],[100,20],[120,20],[140,20],[160,20],[180,40],[220,300],[520,300],[820,300],[1120,300],[1420,300],[1720,828],[2548,20],[2568,828],[3396,20],[3416,828],[4244,20],[4264,80],[4344,828],[5172,204],[5376,20],[5396,868],[6264,588],[6852,1512]],"WEB8_room_static__baked__A8":[[0,1040],[1040,1040],[2080,8704],[10784,2772],[13556,588],[14144,2272],[16416,2912]]};
function measureEntryShell(room) {
  room.updateWorldMatrix(true, true);
  const inverse = room.matrixWorld.clone().invert(), transform = new THREE.Matrix4(), point = new THREE.Vector3();
  const parts = [], moving = [];
  room.traverse(mesh => {
    if (!mesh.isMesh) return;
    let ranges = SHELL_PART_RANGES[mesh.name];
    if (!ranges && !['room_static', 'architecture.platform'].includes(mesh.userData.owner_asset_id)) return;
    // The audited attachment split also records V19's removed floor-grid
    // prefix. Keep each surviving wall member's original triangle boundaries.
    const removedPrefix = mesh.geometry.userData.entryRemovedTrianglePrefix ?? 0;
    if (ranges && removedPrefix) ranges = ranges.filter(([first]) => first >= removedPrefix).map(([first, count]) => [first - removedPrefix, count]);
    transform.multiplyMatrices(inverse, mesh.matrixWorld);
    const positions = mesh.geometry.attributes.position, indices = mesh.geometry.index;
    for (const [first, count] of ranges ?? [[0, (indices?.count ?? positions.count) / 3]]) {
      const box = new THREE.Box3();
      for (let corner = first * 3; corner < (first + count) * 3; corner++) box.expandByPoint(point.fromBufferAttribute(positions, indices ? indices.getX(corner) : corner).applyMatrix4(transform));
      parts.push(box);
    }
  });
  room.traverse(node => { if (/^furniture\./.test(node.userData.asset_id ?? '')) moving.push(node); });
  return { parts, moving };
}

// Historical export name retained for the existing UI/input integration.
export function createCubeIntro({ scene, renderer, welcomeModel, welcomeClips, welcomeBackdrop, terminalDock, room, roomEntry, exteriorModel, atmosphere, ground, contactShadow, introLighting, camera, controls,
  bounds, element, getEndPose, reducedMotion = false, onStart, onComplete }) {
  for (const mesh of [ground, atmosphere.sky]) {
    if (!mesh.material.fragmentShader.includes('#include <colorspace_fragment>')) throw new Error('Intro requires the existing atmosphere color output');
  }
  const clips = (welcomeClips ?? []).filter(clip => clip.name === 'TerminalUnfold');
  if (clips.length !== 1 || !(clips[0].duration > 0)) throw new Error('Welcome terminal requires one valid TerminalUnfold clip');
  const openingClip = clips[0], animated = new Map();
  for (const track of openingClip.tracks) {
    const path = THREE.PropertyBinding.parseTrackName(track.name), node = THREE.PropertyBinding.findNode(welcomeModel, path.nodeName);
    if (!node || !/^seed\./.test(node.userData.name ?? node.name) || !['position', 'quaternion', 'scale'].includes(path.propertyName)) {
      throw new Error(`TerminalUnfold has an invalid seed binding: ${track.name}`);
    }
    animated.set(node, { position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone() });
  }
  if (!animated.size) throw new Error('Welcome terminal clip has no moving parts');
  const roomPose = { position: room.position.clone(), rotation: room.rotation.clone(), quaternion: room.quaternion.clone(), scale: room.scale.clone(), visible: room.visible };
  room.updateWorldMatrix(true, true);
  const roomSize = bounds.getSize(new THREE.Vector3());
  const shell = measureEntryShell(room), clearanceBox = new THREE.Box3(), terminalBox = new THREE.Box3();
  let platformTop = bounds.min.y;
  room.traverse(node => { if (node.userData.asset_id === 'architecture.platform') platformTop = new THREE.Box3().setFromObject(node).max.y; });
  const floorAnchor = bounds.getCenter(new THREE.Vector3()); floorAnchor.y = bounds.min.y;
  const floorPivot = room.worldToLocal(floorAnchor.clone());
  const floorInParent = room.parent ? room.parent.worldToLocal(floorAnchor.clone()) : floorAnchor.clone();
  room.visible = false;
  const doc = element.ownerDocument, view = doc.defaultView;
  const enterButton = element.querySelector('.intro-enter'), skipButton = element.querySelector('.intro-skip');
  const welcome = element.querySelector('.intro-welcome'), identity = element.querySelector('.intro-identity');
  const welcomeLetters = splitText(element.querySelector('[data-intro-welcome]'));
  const welcomeDetails = [...element.querySelectorAll('[data-intro-detail]')];
  const identityLetters = [element.querySelector('[data-intro-name]'), element.querySelector('[data-intro-role]')].flatMap(splitText);
  const paper = new THREE.Color('#e4eaf0');
  const backdrop = createIntroBackdrop({ texture: welcomeBackdrop, renderer, view, paper });
  const originalBackground = scene.background;
  const shadowOpacity = contactShadow?.material.opacity;
  if (contactShadow) contactShadow.material.opacity = 0;
  const environmentMix = { value: 0 }, shadowReveal = { value: 0 }, contactReveal = { value: 0 }, shaderBindings = [];
  for (const mesh of [ground, atmosphere.sky]) {
    const material = mesh.material;
    shaderBindings.push({ material, fragmentShader: material.fragmentShader });
    material.uniforms.uIntroEnvironment = environmentMix;
    backdrop.bind(material);
    material.fragmentShader = 'uniform float uIntroEnvironment;\n' + backdrop.declarations + material.fragmentShader.replace(
      '#include <colorspace_fragment>', 'gl_FragColor.rgb = mix(introBackdropColor(), gl_FragColor.rgb, uIntroEnvironment);\n#include <colorspace_fragment>');
    material.needsUpdate = true;
  }
  const hiddenAtmosphere = atmosphere.group.children.filter(node => node !== atmosphere.sky).map(node => ({ node, visible: node.visible }));
  // The atmosphere owns its existing glow alpha; keep those objects in place
  // and reveal them continuously instead of enabling every glow at finish().
  if (atmosphere.setIntroReveal) atmosphere.setIntroReveal(0);
  else hiddenAtmosphere.forEach(({ node }) => { node.visible = false; });
  const exteriorPose = { position: exteriorModel.position.clone(), scale: exteriorModel.scale.clone(), visible: exteriorModel.visible };
  exteriorModel.visible = false;
  // Fade the exterior where it belongs. Scaling its large orbit rings toward
  // the origin used to sweep real geometry through the desk and window.
  const exteriorMaterials = new Map(), exteriorBindings = [], exteriorFade = { value: 0 };
  exteriorModel.traverse(mesh => {
    if (!mesh.isMesh) return;
    const original = mesh.material;
    const replacements = [].concat(original).map(material => {
      if (!exteriorMaterials.has(material)) {
        const copy = material.clone();
        const baseKey = material.customProgramCacheKey.call(material);
        copy.onBeforeCompile = (shader, currentRenderer) => {
          material.onBeforeCompile.call(material, shader, currentRenderer);
          shader.uniforms.uEntryExteriorReveal = exteriorFade;
          backdrop.bind(shader);
          shader.fragmentShader = 'uniform float uEntryExteriorReveal;\n' + backdrop.declarations + shader.fragmentShader.replace(
            '#include <colorspace_fragment>', 'gl_FragColor.rgb = mix(introBackdropColor(), gl_FragColor.rgb, uEntryExteriorReveal);\n#include <colorspace_fragment>');
        };
        copy.customProgramCacheKey = () => `${baseKey}|entry-exterior-reveal-v2`;
        // Keep opaque depth ordering: alpha fading merged exterior shells made
        // their rear faces look like overlapping glass during the transition.
        exteriorMaterials.set(material, copy);
      }
      return exteriorMaterials.get(material);
    });
    mesh.material = Array.isArray(original) ? replacements : replacements[0];
    exteriorBindings.push({ mesh, original });
  });
  let exteriorReleased = false;
  function restoreExteriorMaterials() {
    if (exteriorReleased) return;
    exteriorBindings.forEach(({ mesh, original }) => { mesh.material = original; });
    exteriorMaterials.forEach(material => material.dispose()); exteriorReleased = true;
  }
  scene.background = paper;

  const group = new THREE.Group(); group.name = 'Welcome creative terminal · temporary';
  const sculpture = terminalDock?.carrier ?? new THREE.Group();
  sculpture.name = 'Blender creative terminal';
  const dockHome = terminalDock?.getHomeWorldPose();
  if (terminalDock) terminalDock.detachForIntro(scene);
  group.attach(sculpture);
  welcomeModel.updateMatrixWorld(true);
  const modelBox = new THREE.Box3();
  if (terminalDock) {
    const inverse = sculpture.matrixWorld.clone().invert(), transform = new THREE.Matrix4(), vertex = new THREE.Vector3();
    welcomeModel.traverse(mesh => {
      if (!mesh.isMesh) return;
      transform.multiplyMatrices(inverse, mesh.matrixWorld);
      const positions = mesh.geometry.attributes.position;
      for (let index = 0; index < positions.count; index++) modelBox.expandByPoint(vertex.fromBufferAttribute(positions, index).applyMatrix4(transform));
    });
  } else modelBox.setFromObject(welcomeModel);
  const modelSize = modelBox.getSize(new THREE.Vector3()), modelFloor = modelBox.getCenter(new THREE.Vector3());
  modelFloor.y = modelBox.min.y;
  const modelSpan = Math.max(modelSize.x, modelSize.y, modelSize.z);
  if (!(modelSize.x > 0 && Number.isFinite(modelSpan))) throw new Error('Welcome terminal has invalid geometry bounds');
  if (!terminalDock) {
    const normalization = new THREE.Group(); normalization.scale.setScalar(1 / modelSpan);
    normalization.position.copy(modelFloor).multiplyScalar(-1 / modelSpan);
    normalization.add(welcomeModel); sculpture.add(normalization);
  }
  const mixer = new THREE.AnimationMixer(welcomeModel), openingAction = mixer.clipAction(openingClip);
  openingAction.setLoop(THREE.LoopOnce, 1); openingAction.clampWhenFinished = true; openingAction.play(); openingAction.paused = true;
  openingAction.time = 0; mixer.update(0);
  const materials = new Set(), geometries = new Set(), textures = new Set();
  let reflection;
  if (!terminalDock) {
    const probeScene = new RoomEnvironment(), probeGenerator = new THREE.PMREMGenerator(renderer);
    reflection = probeGenerator.fromScene(probeScene, .04);
    probeScene.dispose(); probeGenerator.dispose();
    welcomeModel.traverse(node => {
    if (!node.isMesh) return;
    geometries.add(node.geometry);
    for (const material of [].concat(node.material)) {
      if (materials.has(material)) continue;
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      material.envMap = reflection.texture; material.envMapIntensity = .9;
      material.needsUpdate = true;
    }
    });
    const fill = new THREE.HemisphereLight('#fffaed', '#6e818e', 2.1);
    const sun = new THREE.DirectionalLight('#fff1d9', 3.1); sun.position.set(-6, 14, 10);
    group.add(fill, sun);
  }
  scene.add(group);
  const motion = { appear: .00001, shift: 0, travel: 0, approach: 0, dock: 0, unfold: 0, handoff: 0, morph: 0, roomScale: .025, exterior: 0, showcase: 1 };
  const dockControlA = new THREE.Vector3(), dockControlB = new THREE.Vector3();
  const welcomeRotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), .2);
  const baseWelcomeRotation = welcomeRotation.clone(), idleRotation = new THREE.Quaternion(), idleEuler = new THREE.Euler();
  const pointer = new THREE.Vector2(), pointerTarget = new THREE.Vector2();
  let idleSeconds = 0, idleLastTime = null, backdropReleased = false;
  function pointShowcase(event) {
    if (phase !== 'welcome' || reducedMotion || event.pointerType === 'touch') return;
    pointerTarget.set(event.clientX / view.innerWidth * 2 - 1, 1 - event.clientY / view.innerHeight * 2);
  }
  function resetShowcasePointer() { pointerTarget.set(0, 0); }
  element.addEventListener('pointermove', pointShowcase);
  element.addEventListener('pointerleave', resetShowcasePointer);
  function releaseShowcase() {
    element.removeEventListener('pointermove', pointShowcase);
    element.removeEventListener('pointerleave', resetShowcasePointer);
    if (backdropReleased) return;
    shaderBindings.forEach(({ material, fragmentShader }) => {
      material.fragmentShader = fragmentShader; delete material.uniforms.uIntroEnvironment;
      backdrop.unbind(material); material.needsUpdate = true;
    });
    backdrop.dispose(); backdropReleased = true;
  }
  let docked = false, dockEnd = 0;
  let roomStarted = false, sampledOpening = 0;
  const startPosition = new THREE.Vector3(), endPosition = new THREE.Vector3(), startTarget = new THREE.Vector3(), endTarget = new THREE.Vector3();
  const right = new THREE.Vector3(), up = new THREE.Vector3(), forward = new THREE.Vector3(), point = new THREE.Vector3(), anchorOffset = new THREE.Vector3();
  let phase = 'prepared', firstTimeline, secondTimeline, cleanupInput = () => {}, startCount = 0, completeCount = 0, inputSource = null, released = false;
  let loadingReveal = false;
  let distance, tangent, compact;
  const previousOverflow = doc.body.style.overflow;
  doc.body.style.overflow = 'hidden'; doc.body.classList.add('intro-active'); controls.enabled = false;
  gsap.set([welcome, identity, enterButton], { autoAlpha: 0 });
  gsap.set([...welcomeLetters, ...identityLetters], { yPercent: 115 });
  gsap.set(welcomeDetails, { autoAlpha: 0, y: 12 });

  function resize() {
    backdrop.resize();
    const pose = getEndPose(); endPosition.copy(pose.position); endTarget.copy(pose.target);
    distance = endPosition.distanceTo(endTarget); tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    compact = view.innerWidth <= 700;
    forward.copy(endTarget).sub(endPosition).normalize(); right.crossVectors(forward, camera.up).normalize(); up.crossVectors(right, forward).normalize();
    startTarget.copy(endTarget); startPosition.copy(endTarget).addScaledVector(forward, -distance * .87).addScaledVector(up, distance * .035);
    // Logo travel captured the previous DOM layout. Readiness already passed
    // before loadingReveal became true, so finish that visual handoff safely
    // instead of sending the logo toward stale coordinates after a resize.
    if (loadingReveal) firstTimeline?.progress(1);
    update();
  }
  function update() {
    if (phase === 'complete' || phase === 'disposed') return;
    const now = view.performance?.now?.() ?? 0;
    const delta = idleLastTime === null ? 0 : Math.min(Math.max((now - idleLastTime) / 1000, 0), .05);
    idleLastTime = now;
    if (phase === 'welcome' && !reducedMotion) {
      idleSeconds += delta;
      pointer.lerp(pointerTarget, 1 - Math.exp(-delta * 3.5));
    }
    backdrop.update(idleSeconds, reducedMotion);
    const idleWeight = reducedMotion ? 0 : motion.showcase * smooth(motion.shift);
    idleEuler.set((Math.sin(idleSeconds * .63) * .018 + pointer.y * .022) * idleWeight,
      (Math.sin(idleSeconds * .42) * .045 + pointer.x * .055) * idleWeight,
      Math.sin(idleSeconds * .51) * .009 * idleWeight);
    idleRotation.setFromEuler(idleEuler);
    welcomeRotation.copy(baseWelcomeRotation).multiply(idleRotation);
    // A single, continuous exchange drives both silhouettes. The terminal
    // recedes as the room grows, instead of starting a separate fast shrink.
    motion.roomScale = THREE.MathUtils.lerp(.025, 1, motion.handoff);
    motion.morph = 1 - Math.pow(1 - motion.handoff, 1.55);
    const travel = motion.travel;
    const moment = phase === 'playing' ? (motion.unfold < .01 ? 'model' : motion.morph < .01 ? 'unfold' : motion.morph < .999 ? 'emerging' : 'assets') : phase;
    if (element.dataset.moment !== moment) element.dataset.moment = moment;
    camera.position.lerpVectors(startPosition, endPosition, travel);
    controls.target.lerpVectors(startTarget, endTarget, travel); camera.lookAt(controls.target); camera.updateMatrixWorld(true);
    // Keep the welcome anchor independent from the moving camera. A moving
    // interpolation origin used to make the terminal accelerate twice.
    const anchorCamera = terminalDock ? startPosition : camera.position;
    const anchorTarget = terminalDock ? startTarget : controls.target;
    forward.copy(anchorTarget).sub(anchorCamera).normalize(); right.crossVectors(forward, camera.up).normalize(); up.crossVectors(right, forward).normalize();
    const depth = anchorCamera.distanceTo(anchorTarget) * .8;
    const verticalSpan = 2 * depth * tangent;
    const x = compact ? 0 : -.27 * motion.shift, y = compact ? (view.innerHeight <= 650 ? .46 : .34) * motion.shift : .22;
    point.copy(anchorCamera).addScaledVector(forward, depth)
      .addScaledVector(right, x * verticalSpan * camera.aspect / 2).addScaledVector(up, y * verticalSpan / 2);
    const welcomeWidth = Math.min(verticalSpan * camera.aspect * (compact ? .75 : .45), verticalSpan * (compact ? .66 : 1.22), verticalSpan * .62 * modelSize.x / Math.max(modelSize.y, .001));
    const initialSize = welcomeWidth * (terminalDock ? 1 : modelSpan) / modelSize.x;
    point.addScaledVector(up, -modelSize.y / (terminalDock ? 1 : modelSpan) * initialSize * .38);
    point.addScaledVector(up, Math.sin(idleSeconds * .85) * verticalSpan * .006 * idleWeight);
    if (terminalDock && !docked) {
      const t = motion.dock, inverse = 1 - t;
      // A real arrival: one solid object follows a continuous arc and settles
      // onto its measured desk position. It never shrinks to zero or swaps.
      dockControlA.lerpVectors(point, dockHome.position, .32);
      dockControlA.y = Math.max(point.y, dockHome.position.y) + roomSize.y * .18;
      dockControlB.copy(dockHome.position); dockControlB.y += roomSize.y * .46;
      sculpture.position.copy(point).multiplyScalar(inverse ** 3)
        .addScaledVector(dockControlA, 3 * inverse * inverse * t)
        .addScaledVector(dockControlB, 3 * inverse * t * t)
        .addScaledVector(dockHome.position, t ** 3);
      const ratio = Math.exp(Math.log(Math.max(initialSize / dockHome.scale.x, .001)) * (1 - t));
      sculpture.scale.copy(dockHome.scale).multiplyScalar(ratio * motion.appear);
      sculpture.quaternion.slerpQuaternions(welcomeRotation, dockHome.quaternion, t);
      sculpture.visible = true;
      terminalDock.setIntroLight(1 - smooth(THREE.MathUtils.clamp((t - .28) / .68, 0, 1)));
      roomEntry.setExternalProgress('folding_drawing_terminal', t);
    } else if (!terminalDock) {
    sculpture.position.lerpVectors(point, floorAnchor, motion.approach);
    // All three axes share one scale. The terminal grows toward the room's
    // footprint without stretching its bevels, dial or colored screen artwork.
    const finalSize = roomSize.x * .40 * modelSpan / modelSize.x;
    const terminalScale = THREE.MathUtils.lerp(initialSize, finalSize, motion.approach) * Math.max(.00001, motion.appear);
    // Retract solid geometry into its floor pivot; never overlap a large
    // translucent screen with the emerging room or alter its PBR colors.
    sculpture.scale.setScalar(terminalScale * Math.max(.00001, 1 - motion.morph));
    sculpture.rotation.set(0, .2 * (1 - motion.approach), 0);
    sculpture.visible = motion.morph < .999;
    }
    // Absolute paused-action sampling preserves the authored hinge and sliding
    // rail. Repeated update/resize calls never accumulate clip time or drift.
    if (!docked && sampledOpening !== motion.unfold) {
      openingAction.time = motion.unfold * openingClip.duration; mixer.update(0); sampledOpening = motion.unfold;
    }
    room.visible = roomStarted && roomPose.visible;
    room.scale.copy(roomPose.scale).multiplyScalar(motion.roomScale);
    room.quaternion.copy(roomPose.quaternion);
    anchorOffset.copy(floorPivot).multiply(room.scale).applyQuaternion(room.quaternion);
    room.position.copy(floorInParent).sub(anchorOffset);
    exteriorModel.visible = motion.exterior > .001 && exteriorPose.visible;
    exteriorModel.scale.copy(exteriorPose.scale);
    exteriorModel.position.copy(exteriorPose.position);
    exteriorFade.value = motion.exterior;
    atmosphere.setIntroReveal?.(motion.exterior);
    introLighting?.setProgress(shadowReveal.value);
    if (contactShadow) contactShadow.material.opacity = shadowOpacity * contactReveal.value;
    roomEntry.update(); room.updateWorldMatrix(true, true);
    if (!terminalDock && phase === 'playing' && sculpture.visible && roomStarted) {
      sculpture.updateWorldMatrix(true, true); terminalBox.setFromObject(sculpture);
      const floorHeight = floorAnchor.y + (platformTop - floorAnchor.y) * motion.roomScale;
      let clearance = floorHeight;
      const margin = roomSize.x * .065 * motion.roomScale;
      const inspect = box => {
        const dx = Math.max(box.min.x - terminalBox.max.x, terminalBox.min.x - box.max.x, 0);
        const dz = Math.max(box.min.z - terminalBox.max.z, terminalBox.min.z - box.max.z, 0);
        const gap = Math.hypot(dx, dz);
        const weight = smooth(THREE.MathUtils.clamp(1 - gap / Math.max(margin, .001), 0, 1));
        clearance = Math.max(clearance, floorHeight + Math.max(0, box.max.y - floorHeight) * weight);
      };
      shell.parts.forEach(box => inspect(clearanceBox.copy(box).applyMatrix4(room.matrixWorld)));
      shell.moving.forEach(node => inspect(clearanceBox.setFromObject(node)));
      const difference = clearance + .025 - terminalBox.min.y;
      // Smooth positive lift retains clearance while joining the original
      // approach without snapping; it drops toward the floor as the terminal
      // footprint fits through the open center of the growing room.
      sculpture.position.y += .5 * (difference + Math.sqrt(difference * difference + .0004));
      sculpture.updateMatrixWorld(true);
    }
    if (terminalDock && !docked && motion.dock >= 1) dockTerminal();
  }
  function dockTerminal() {
    if (!terminalDock || docked) return;
    // Stopping a mixer restores its cached pose, so detach it before writing
    // the precise authored open pose into the permanent room hierarchy.
    mixer.stopAllAction(); mixer.uncacheRoot(welcomeModel);
    terminalDock.attachHome(); roomEntry.setExternalProgress('folding_drawing_terminal', 1); docked = true;
  }
  function restoreScene() {
    roomEntry.restore(); shadowReveal.value = contactReveal.value = 1; introLighting?.restore();
    room.position.copy(roomPose.position); room.rotation.copy(roomPose.rotation); room.quaternion.copy(roomPose.quaternion); room.scale.copy(roomPose.scale); room.visible = roomPose.visible;
    room.updateWorldMatrix(true, true);
    dockTerminal();
    exteriorModel.position.copy(exteriorPose.position); exteriorModel.scale.copy(exteriorPose.scale); exteriorModel.visible = exteriorPose.visible;
    restoreExteriorMaterials();
    environmentMix.value = 1; hiddenAtmosphere.forEach(({ node, visible }) => { node.visible = visible; });
    atmosphere.setIntroReveal?.(1);
    scene.background = originalBackground;
    if (contactShadow) contactShadow.material.opacity = shadowOpacity;
    camera.position.copy(endPosition); controls.target.copy(endTarget); camera.lookAt(endTarget); camera.updateMatrixWorld(true);
  }
  function releaseCube() {
    if (released) return;
    released = true; scene.remove(group);
    if (terminalDock) return;
    mixer.stopAllAction(); mixer.uncacheRoot(welcomeModel);
    for (const [node, original] of animated) { node.position.copy(original.position); node.quaternion.copy(original.quaternion); node.scale.copy(original.scale); }
    geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose()); textures.forEach(texture => texture.dispose()); reflection.dispose();
  }
  function finish() {
    if (phase === 'complete' || phase === 'disposed') return;
    firstTimeline?.kill(); secondTimeline?.kill(); cleanupInput();
    restoreScene(); releaseCube(); releaseShowcase(); phase = 'complete'; completeCount++;
    element.dataset.phase = 'complete'; element.hidden = true; element.inert = true;
    doc.body.classList.remove('intro-active', 'intro-playing'); doc.body.style.overflow = previousOverflow;
    enterButton.removeEventListener('click', clickEnter); skipButton.removeEventListener('click', skip);
    media?.removeEventListener('change', preferenceChange);
    onComplete?.();
  }
  function enter(source = 'click') {
    if (phase !== 'welcome') return false;
    if (loadingReveal) return false;
    phase = 'playing'; inputSource = source; startCount++;
    firstTimeline?.kill(); element.dataset.phase = 'playing'; doc.body.classList.add('intro-playing');
    enterButton.disabled = true; onStart?.();
    if (reducedMotion) { finish(); return true; }
    secondTimeline = gsap.timeline({ onComplete: finish }).timeScale(PLAYBACK_RATE);
    secondTimeline.to(welcomeLetters, { yPercent: 120, duration: .25, stagger: { amount: .10 }, ease: 'power2.in' }, 0)
      .to(welcomeDetails, { autoAlpha: 0, y: 8, duration: .2, ease: 'power2.in' }, 0)
      .to(enterButton, { autoAlpha: 0, duration: .22 }, 0)
      .to(welcome, { autoAlpha: 0, duration: .15 }, .25)
      .to(motion, { appear: 1, shift: 1, duration: .25, ease: 'power1.out' }, 0)
      .to(motion, { showcase: 0, duration: .8, ease: smooth }, 0)
      .to(backdrop.reveal, { value: 0, duration: 1.6, ease: smooth }, .35)
      .to(motion, { travel: 1, duration: 2.85, ease: smooth }, .08)
      .to(motion, { approach: 1, duration: 1.72, ease: smooth }, .08)
      .to(motion, { unfold: 1, duration: 1.85, ease: smooth }, .25)
      .call(() => { roomStarted = true; }, [], 1.12)
      .to(motion, { handoff: 1, duration: 1.80, ease: smooth }, 1.12);
    let roomEnd = roomEntry.appendTo(secondTimeline, .45);
    if (terminalDock) {
      const desk = roomEntry.getState().assets.find(asset => asset.id === 'furniture.desk');
      dockEnd = Math.max(3.75, desk.start + desk.duration + .65);
      secondTimeline.to(motion, { dock: 1, duration: dockEnd - .08, ease: smooth }, .08);
      roomEnd = Math.max(roomEnd, dockEnd);
    }
    secondTimeline.set(identity, { autoAlpha: 1 }, 2.15)
      .to(identityLetters, { yPercent: 0, duration: .55, stagger: .045, ease: 'back.out(1.35)' }, 2.15)
      .to(environmentMix, { value: 1, duration: 2.35, ease: smooth }, 1.6)
      .to(motion, { exterior: 1, duration: 2.2, ease: smooth }, 1.9)
      // The completed outer plinth can receive its broad grounding shadow
      // while small props are still unfolding. Their baked cast shadows wait
      // until every caster has settled, then develop gently in linear light.
      .to(contactReveal, { value: 1, duration: 1.5, ease: smooth }, 2.9)
      .to(shadowReveal, { value: 1, duration: .95, ease: smooth }, roomEnd + .02)
      .to(identity, { autoAlpha: 0, y: -8, duration: .4 }, roomEnd + .1)
      .to(element.querySelector('.intro-brand'), { autoAlpha: 0, duration: .3 }, roomEnd + .1);
    return true;
  }
  function clickEnter() { enter('click'); }
  function skip() {
    if (phase === 'prepared' || phase === 'disposed' || phase === 'complete') return;
    if (loadingReveal) return;
    if (phase === 'welcome') { phase = 'playing'; inputSource = 'skip'; startCount++; onStart?.(); }
    finish();
  }
  const media = view.matchMedia?.('(prefers-reduced-motion: reduce)');
  function preferenceChange(event) {
    if (!event.matches) return;
    reducedMotion = true;
    if (phase === 'playing') finish();
    else if (phase === 'welcome') { firstTimeline?.progress(1); update(); }
  }
  media?.addEventListener('change', preferenceChange);
  resize();
  return {
    get active() { return phase !== 'complete' && phase !== 'disposed'; },
    ready() {
      if (phase !== 'prepared') return;
      // Asset preparation may outlive a system-preference change that happened
      // before this controller subscribed. Preserve any explicit reduced flag.
      reducedMotion ||= Boolean(media?.matches);
      element.dataset.motion = reducedMotion ? 'reduce' : 'full';
      // The real all-assets + GPU fence gate is owned by main. This visual
      // sequence is never a timer for readiness or an additional progress source.
      phase = 'welcome'; element.dataset.phase = 'welcome';
      loadingReveal = true; element.dataset.loadingReveal = 'playing';
      enterButton.disabled = skipButton.disabled = true;
      enterButton.addEventListener('click', clickEnter); skipButton.addEventListener('click', skip);
      cleanupInput = bindIntroInput({ view, element, canEnter: () => phase === 'welcome' && !loadingReveal, onEnter: enter, onSkip: skip });
      const loader = element.querySelector('.intro-loader'), mark = element.querySelector('.startup-mark');
      const brand = element.querySelector('.intro-brand');
      const completeLoadingReveal = () => {
        if (phase !== 'welcome') return;
        loadingReveal = false; element.dataset.loadingReveal = 'complete';
        enterButton.disabled = skipButton.disabled = false;
      };
      firstTimeline = gsap.timeline({ onComplete: completeLoadingReveal }).timeScale(PLAYBACK_RATE);
      if (reducedMotion) {
        firstTimeline.to(loader, { autoAlpha: 0, duration: .16 }, 0)
          .set(motion, { appear: 1, shift: 1 }, 0)
          .set(welcome, { autoAlpha: 1 }, 0)
          .set(welcomeLetters, { yPercent: 0 }, 0)
          .set(welcomeDetails, { autoAlpha: 1, y: 0 }, 0)
          .set(enterButton, { autoAlpha: 1 }, .16);
        return;
      }
      // C: PathLoader / effect1.css, Copyright 2014 Codrops (MIT core).
      // Logo lift + loaded-header rise are adapted from pinned upstream files;
      // full notices: public/loader-review-v1/source/{ATTRIBUTION.md,licenses/}.
      const start = mark.getBoundingClientRect?.() ?? { left: 0, top: 0, width: 176, height: 176 };
      const target = element.querySelector('.intro-brand img').getBoundingClientRect?.() ?? { left: 0, top: 0, width: 52, height: 52 };
      gsap.set(brand, { autoAlpha: 0 });
      firstTimeline.to(element.querySelector('.intro-loading-panel'), { autoAlpha: 0, y: -18, duration: .3, ease: 'power2.in' }, 0)
        .to(mark, { x: target.left + target.width / 2 - start.left - start.width / 2,
          y: target.top + target.height / 2 - start.top - start.height / 2,
          scale: target.width / Math.max(start.width, 1), duration: 1.1, ease: 'power3.inOut' }, .1)
        .to(element.querySelector('.startup-mark-halo'), { autoAlpha: 0, duration: .4 }, .1)
        .to(element.querySelector('.startup-mark-sheen'), { autoAlpha: 0, duration: .25 }, .1)
        .to(element.querySelector('.startup-mark-trace'), { autoAlpha: 0, duration: .4 }, .4)
        .to(element.querySelector('.startup-curtain'), { yPercent: -100, duration: 1.18, ease: 'power3.inOut' }, .2)
        .set(brand, { autoAlpha: 1 }, 1.21)
        .set(mark, { autoAlpha: 0 }, 1.21)
        .set(loader, { autoAlpha: 0 }, 1.4)
        .to(motion, { appear: 1, duration: .7, ease: 'back.out(1.35)' }, .5)
        .to(motion, { shift: 1, duration: .65, ease: smooth }, .85)
        .set(welcome, { autoAlpha: 1 }, 1.25)
        .to(welcomeLetters, { yPercent: 0, duration: .55, stagger: .035, ease: 'back.out(1.5)' }, 1.25)
        .to(welcomeDetails, { autoAlpha: 1, y: 0, duration: .5, stagger: .07, ease: 'power3.out' }, 1.4)
        .to(enterButton, { autoAlpha: 1, duration: .35 }, 2.05);
    },
    update, resize, skip,
    // Called only by main's DEV + qa + introAt gate. One fresh welcome per
    // inspection avoids rewinding one-shot visibility/entry events in the UI.
    inspectAt(seconds) {
      if (phase !== 'welcome' || !Number.isFinite(seconds) || seconds < 0) return false;
      firstTimeline?.progress(1); update(); enter('qa');
      if (!secondTimeline || phase !== 'playing') return false;
      secondTimeline.pause(); secondTimeline.time(Math.min(seconds, secondTimeline.duration()), false); update();
      element.dataset.inspectAt = String(secondTimeline.time());
      return true;
    },
    dispose() {
      if (phase === 'disposed') return;
      firstTimeline?.kill(); secondTimeline?.kill(); cleanupInput(); restoreScene(); releaseCube(); releaseShowcase();
      loadingReveal = false; element.dataset.loadingReveal = 'cancelled';
      enterButton.removeEventListener('click', clickEnter); skipButton.removeEventListener('click', skip);
      media?.removeEventListener('change', preferenceChange);
      doc.body.style.overflow = previousOverflow; phase = 'disposed';
    },
    getState: () => ({ revision: 11, model: 'welcome-terminal-v2', phase, startCount, completeCount, inputSource, reducedMotion, loadingReveal,
      showcase: { background: 'silver-current-v2', backgroundReveal: backdrop.reveal.value, idle: !reducedMotion && phase === 'welcome', idleSeconds, pointer: pointer.toArray(), weight: motion.showcase, released: backdropReleased },
      elapsedTime: secondTimeline?.time() ?? 0, paused: secondTimeline?.paused() ?? false,
      playbackRate: PLAYBACK_RATE, playbackDuration: secondTimeline ? secondTimeline.duration() / PLAYBACK_RATE : 0,
      progress: secondTimeline?.progress() ?? (phase === 'complete' ? 1 : 0), modelVisible: terminalDock ? sculpture.visible : !released && sculpture.visible,
      docking: terminalDock ? { progress: motion.dock, end: dockEnd, attached: docked, permanent: true, position: sculpture.getWorldPosition(new THREE.Vector3()).toArray(), scale: sculpture.getWorldScale(new THREE.Vector3()).toArray() } : null,
      handoff: motion.handoff, environmentReveal: environmentMix.value, exteriorReveal: motion.exterior,
      exteriorMaterialsRestored: exteriorReleased, shadowReveal: shadowReveal.value, contactReveal: contactReveal.value,
      atmosphere: atmosphere.getState?.(), cleanLighting: introLighting?.getState(),
      roomVisible: room.visible, roomScale: phase === 'complete' ? 1 : motion.roomScale,
      opening: { clip: openingClip.name, duration: openingClip.duration, progress: motion.unfold, animatedNodes: animated.size },
      viewport: [view.innerWidth, view.innerHeight], assembly: roomEntry.getState() }),
  };
}
