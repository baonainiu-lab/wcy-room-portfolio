/* Choreography adapted from Andrew Woan's firstIntro / secondIntro (MIT, 2023).
 * Source and full license: public/licenses/abigail-bloom/. The persistent room,
 * Blender fold clip, transforms, styling and input binding are project-specific. */
import * as THREE from 'three';
import gsap from 'gsap';
import { bindIntroInput } from './intro-input.js';
import { createFoldedRoomMotion } from './folded-room-motion.js';

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

// Historical export name retained for the existing UI/input integration. There
// is no separate welcome model: these are the final room's original meshes.
export function createCubeIntro({ scene, room, clips, roomEntry, exteriorModel, atmosphere, ground, contactShadow, camera, controls,
  element, getEndPose, reducedMotion = false, onStart, onComplete }) {
  const fold = createFoldedRoomMotion({ THREE, room, clips, clipName: 'RoomUnfold' });
  for (const mesh of [ground, atmosphere.sky]) {
    if (!mesh.material.fragmentShader.includes('#include <colorspace_fragment>')) throw new Error('Intro requires the existing atmosphere color output');
  }
  const rootPose = { position: room.position.clone(), rotation: room.rotation.clone(), quaternion: room.quaternion.clone(), scale: room.scale.clone() };
  const doc = element.ownerDocument, view = doc.defaultView;
  const enterButton = element.querySelector('.intro-enter'), skipButton = element.querySelector('.intro-skip');
  const welcome = element.querySelector('.intro-welcome'), identity = element.querySelector('.intro-identity');
  const welcomeLetters = splitText(element.querySelector('[data-intro-welcome]'));
  const identityLetters = [element.querySelector('[data-intro-name]'), element.querySelector('[data-intro-role]')].flatMap(splitText);
  const paper = new THREE.Color('#f3eee4');
  const originalBackground = scene.background;
  const shadowOpacity = contactShadow?.material.opacity;
  if (contactShadow) contactShadow.material.opacity = 0;
  const environmentMix = { value: 0 }, roomFinish = { value: 0 }, shaderBindings = [], surfaceBindings = [];
  const surfaces = new Set();
  room.traverse(node => { if (node.isMesh) [].concat(node.material).forEach(material => { if (material.isMeshBasicMaterial && material.map) surfaces.add(material); }); });
  // Lift baked furniture contact marks while their owners are still folded or
  // growing, then return the unchanged original bake as the room is assembled.
  for (const material of surfaces) {
    const previousCompile = material.onBeforeCompile, previousCacheKey = material.customProgramCacheKey;
    const key = previousCacheKey.call(material);
    surfaceBindings.push({ material, previousCompile, previousCacheKey });
    material.onBeforeCompile = function(shader, renderer) {
      previousCompile.call(this, shader, renderer);
      shader.uniforms.uIntroRoomFinish = roomFinish;
      shader.fragmentShader = 'uniform float uIntroRoomFinish;\n' + shader.fragmentShader.replace('#include <color_fragment>',
        '#include <color_fragment>\ndiffuseColor.rgb = mix(max(diffuseColor.rgb, vec3(0.08, 0.11, 0.13)), diffuseColor.rgb, uIntroRoomFinish);');
    };
    material.customProgramCacheKey = () => `${key}|room-fold-intro-surface-1`; material.needsUpdate = true;
  }
  for (const mesh of [ground, atmosphere.sky]) {
    const material = mesh.material;
    shaderBindings.push({ material, fragmentShader: material.fragmentShader });
    material.uniforms.uIntroEnvironment = environmentMix;
    material.uniforms.uIntroPaper = { value: paper };
    material.fragmentShader = 'uniform float uIntroEnvironment; uniform vec3 uIntroPaper;\n' + material.fragmentShader.replace(
      '#include <colorspace_fragment>', 'gl_FragColor.rgb = mix(uIntroPaper, gl_FragColor.rgb, uIntroEnvironment);\n#include <colorspace_fragment>');
    material.needsUpdate = true;
  }
  const hiddenAtmosphere = atmosphere.group.children.filter(node => node !== atmosphere.sky).map(node => ({ node, visible: node.visible }));
  hiddenAtmosphere.forEach(({ node }) => { node.visible = false; });
  const exteriorPose = { position: exteriorModel.position.clone(), scale: exteriorModel.scale.clone(), visible: exteriorModel.visible };
  exteriorModel.visible = false;
  scene.background = paper;

  // Main has already built final-pose bounds, collision guards and all prop
  // snapshots. Only now sample Blender's collapsed architecture. This box and
  // anchor are measured once; resize never re-measures a moving room.
  fold.setProgress(0);
  const foldedBox = new THREE.Box3().setFromObject(room);
  const foldedSize = foldedBox.getSize(new THREE.Vector3());
  const foldedSpan = Math.max(foldedSize.x, foldedSize.y, foldedSize.z);
  if (!(foldedSpan > 0 && Number.isFinite(foldedSpan))) throw new Error('Folded room has no finite geometry bounds');
  const finalAnchor = foldedBox.getCenter(new THREE.Vector3());
  const localAnchor = room.worldToLocal(finalAnchor.clone());
  const foldedCorners = [];
  for (const x of [foldedBox.min.x, foldedBox.max.x]) for (const y of [foldedBox.min.y, foldedBox.max.y]) for (const z of [foldedBox.min.z, foldedBox.max.z]) {
    foldedCorners.push(room.worldToLocal(new THREE.Vector3(x, y, z)).sub(localAnchor));
  }
  const motion = { appear: .00001, shift: 0, travel: 0, fold: 0, exterior: .00001 };
  const startPosition = new THREE.Vector3(), endPosition = new THREE.Vector3(), startTarget = new THREE.Vector3(), endTarget = new THREE.Vector3();
  const right = new THREE.Vector3(), up = new THREE.Vector3(), forward = new THREE.Vector3(), point = new THREE.Vector3(), anchorOffset = new THREE.Vector3();
  const corner = new THREE.Vector3(), layoutRotation = new THREE.Quaternion(), turn = new THREE.Quaternion(), axis = new THREE.Vector3(0, 1, 0);
  const parentInverse = new THREE.Matrix4();
  let phase = 'prepared', firstTimeline, secondTimeline, cleanupInput = () => {}, startCount = 0, completeCount = 0, inputSource = null;
  let distance, tangent, compact, layoutScale = .00001, sampledFold = 0;
  const previousOverflow = doc.body.style.overflow;
  doc.body.style.overflow = 'hidden'; doc.body.classList.add('intro-active'); controls.enabled = false;
  gsap.set([welcome, identity, enterButton], { autoAlpha: 0 });
  gsap.set([...welcomeLetters, ...identityLetters], { yPercent: 115 });

  function resize() {
    const pose = getEndPose(); endPosition.copy(pose.position); endTarget.copy(pose.target);
    distance = endPosition.distanceTo(endTarget); tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    compact = view.innerWidth <= 700;
    forward.copy(endTarget).sub(endPosition).normalize(); right.crossVectors(forward, camera.up).normalize(); up.crossVectors(right, forward).normalize();
    startTarget.copy(endTarget); startPosition.copy(endTarget).addScaledVector(forward, -distance * .87).addScaledVector(up, distance * .035);
    update();
  }
  function update() {
    if (phase === 'complete' || phase === 'disposed') return;
    const travel = motion.travel;
    const moment = phase === 'playing' ? (motion.fold < .01 ? 'model' : motion.fold < .999 ? 'unfold' : 'assets') : phase;
    if (element.dataset.moment !== moment) element.dataset.moment = moment;
    camera.position.lerpVectors(startPosition, endPosition, travel);
    controls.target.lerpVectors(startTarget, endTarget, travel); camera.lookAt(controls.target); camera.updateMatrixWorld(true);
    forward.copy(controls.target).sub(camera.position).normalize(); right.crossVectors(forward, camera.up).normalize(); up.crossVectors(right, forward).normalize();
    const depth = camera.position.distanceTo(controls.target) * .8, verticalSpan = 2 * depth * tangent;
    const x = compact ? 0 : -.40 * motion.shift, y = compact ? .34 * motion.shift : .03;
    point.copy(camera.position).addScaledVector(forward, depth)
      .addScaledVector(right, x * verticalSpan * camera.aspect / 2).addScaledVector(up, y * verticalSpan / 2)
      .lerp(finalAnchor, travel);
    layoutRotation.copy(rootPose.quaternion).premultiply(turn.setFromAxisAngle(axis, .16 * (1 - travel)));
    // Uniform global scale preserves every prop's proportions and its Blender
    // hinge relationship. A vertical cap also keeps the welcome clear on phones.
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const localCorner of foldedCorners) {
      corner.copy(localCorner).multiply(rootPose.scale).applyQuaternion(layoutRotation);
      if (room.parent) corner.transformDirection(room.parent.matrixWorld).multiplyScalar(localCorner.clone().multiply(rootPose.scale).length());
      const cx = corner.dot(right), cy = corner.dot(up);
      minX = Math.min(minX, cx); maxX = Math.max(maxX, cx); minY = Math.min(minY, cy); maxY = Math.max(maxY, cy);
    }
    const initialScale = Math.min(verticalSpan * camera.aspect * (compact ? .60 : .26) / Math.max(.00001, maxX - minX),
      verticalSpan * (compact ? .30 : .46) / Math.max(.00001, maxY - minY));
    layoutScale = THREE.MathUtils.lerp(initialScale, 1, travel) * Math.max(.00001, motion.appear);
    room.scale.copy(rootPose.scale).multiplyScalar(layoutScale);
    room.quaternion.copy(layoutRotation);
    if (room.parent) { room.parent.updateWorldMatrix(true, false); parentInverse.copy(room.parent.matrixWorld).invert(); point.applyMatrix4(parentInverse); }
    anchorOffset.copy(localAnchor).multiply(room.scale).applyQuaternion(room.quaternion);
    room.position.copy(point).sub(anchorOffset);
    if (motion.fold !== sampledFold) { fold.setProgress(motion.fold); sampledFold = motion.fold; }
    roomEntry.update();
    room.updateWorldMatrix(true, true);
    if (motion.exterior > .001) exteriorModel.visible = exteriorPose.visible;
    exteriorModel.scale.copy(exteriorPose.scale).multiplyScalar(motion.exterior);
    exteriorModel.position.copy(exteriorPose.position);
    if (contactShadow) contactShadow.material.opacity = shadowOpacity * environmentMix.value;
  }
  function restoreScene() {
    fold.restore(); roomEntry.restore();
    room.position.copy(rootPose.position); room.rotation.copy(rootPose.rotation); room.quaternion.copy(rootPose.quaternion); room.scale.copy(rootPose.scale);
    room.updateWorldMatrix(true, true);
    exteriorModel.position.copy(exteriorPose.position); exteriorModel.scale.copy(exteriorPose.scale); exteriorModel.visible = exteriorPose.visible;
    environmentMix.value = 1; hiddenAtmosphere.forEach(({ node, visible }) => { node.visible = visible; });
    roomFinish.value = 1; scene.background = originalBackground;
    if (contactShadow) contactShadow.material.opacity = shadowOpacity;
    camera.position.copy(endPosition); controls.target.copy(endTarget); camera.lookAt(endTarget); camera.updateMatrixWorld(true);
  }
  function finish() {
    if (phase === 'complete' || phase === 'disposed') return;
    firstTimeline?.kill(); secondTimeline?.kill(); cleanupInput();
    restoreScene(); phase = 'complete'; completeCount++;
    element.dataset.phase = 'complete'; element.hidden = true; element.inert = true;
    doc.body.classList.remove('intro-active', 'intro-playing'); doc.body.style.overflow = previousOverflow;
    enterButton.removeEventListener('click', clickEnter); skipButton.removeEventListener('click', skip);
    media?.removeEventListener('change', preferenceChange);
    onComplete?.();
  }
  function enter(source = 'click') {
    if (phase !== 'welcome') return false;
    phase = 'playing'; inputSource = source; startCount++;
    firstTimeline?.kill(); element.dataset.phase = 'playing'; doc.body.classList.add('intro-playing');
    enterButton.disabled = true; onStart?.();
    if (reducedMotion) { finish(); return true; }
    secondTimeline = gsap.timeline({ onComplete: finish });
    secondTimeline.to(welcomeLetters, { yPercent: 120, duration: .25, stagger: { amount: .10 }, ease: 'power2.in' }, 0)
      .to(enterButton, { autoAlpha: 0, duration: .22 }, 0)
      .to(welcome, { autoAlpha: 0, duration: .15 }, .25)
      .to(motion, { appear: 1, shift: 1, duration: .25, ease: 'power1.out' }, 0)
      .to(motion, { travel: 1, duration: 2.1, ease: smooth }, 0)
      .to(motion, { fold: 1, duration: 3, ease: 'none' }, .35);
    const roomEnd = roomEntry.appendTo(secondTimeline, .35);
    secondTimeline.set(identity, { autoAlpha: 1 }, 2.2)
      .to(identityLetters, { yPercent: 0, duration: .55, stagger: .045, ease: 'back.out(1.35)' }, 2.2)
      .to(environmentMix, { value: 1, duration: 1.7, ease: smooth }, 1.8)
      .to(roomFinish, { value: 1, duration: 1.3, ease: smooth }, 2.2)
      .to(motion, { exterior: 1, duration: 1.7, ease: smooth }, 1.8)
      .to(identity, { autoAlpha: 0, y: -8, duration: .4 }, roomEnd + .1)
      .to(element.querySelector('.intro-brand'), { autoAlpha: 0, duration: .3 }, roomEnd + .1);
    return true;
  }
  function clickEnter() { enter('click'); }
  function skip() {
    if (phase === 'prepared' || phase === 'disposed' || phase === 'complete') return;
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
      phase = 'welcome'; element.dataset.phase = 'welcome'; enterButton.disabled = skipButton.disabled = false;
      enterButton.addEventListener('click', clickEnter); skipButton.addEventListener('click', skip);
      cleanupInput = bindIntroInput({ view, element, canEnter: () => phase === 'welcome', onEnter: enter, onSkip: skip });
      firstTimeline = gsap.timeline();
      firstTimeline.to(element.querySelector('.intro-loader'), { autoAlpha: 0, duration: reducedMotion ? .01 : .2 }, 0)
        .to(motion, { appear: 1, duration: reducedMotion ? .01 : .7, ease: 'back.out(1.35)' }, 0)
        .to(motion, { shift: 1, duration: reducedMotion ? .01 : .65, ease: smooth }, reducedMotion ? 0 : .5)
        .set(welcome, { autoAlpha: 1 }, reducedMotion ? 0 : .85)
        .to(welcomeLetters, { yPercent: 0, duration: reducedMotion ? .01 : .55, stagger: reducedMotion ? 0 : .035, ease: 'back.out(1.5)' }, reducedMotion ? 0 : .85)
        .to(enterButton, { autoAlpha: 1, duration: reducedMotion ? .01 : .35 }, reducedMotion ? 0 : 1.75);
    },
    update, resize, skip,
    dispose() {
      if (phase === 'disposed') return;
      firstTimeline?.kill(); secondTimeline?.kill(); cleanupInput(); restoreScene(); fold.dispose();
      enterButton.removeEventListener('click', clickEnter); skipButton.removeEventListener('click', skip);
      media?.removeEventListener('change', preferenceChange);
      shaderBindings.forEach(({ material, fragmentShader }) => {
        material.fragmentShader = fragmentShader; delete material.uniforms.uIntroEnvironment; delete material.uniforms.uIntroPaper; material.needsUpdate = true;
      });
      surfaceBindings.forEach(({ material, previousCompile, previousCacheKey }) => {
        material.onBeforeCompile = previousCompile; material.customProgramCacheKey = previousCacheKey; material.needsUpdate = true;
      });
      doc.body.style.overflow = previousOverflow; phase = 'disposed';
    },
    getState: () => ({ revision: 3, model: 'room-unfold-v1', phase, startCount, completeCount, inputSource, reducedMotion,
      progress: secondTimeline?.progress() ?? (phase === 'complete' ? 1 : 0), modelVisible: room.visible,
      layoutScale, foldedSpan, fold: fold.getState(), viewport: [view.innerWidth, view.innerHeight], assembly: roomEntry.getState() }),
  };
}
