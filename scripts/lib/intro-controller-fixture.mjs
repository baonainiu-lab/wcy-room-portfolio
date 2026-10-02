import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import * as THREE from 'three';
import gsap from 'gsap';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { bindIntroInput } from '../../src/intro-input.js';
import { createRoomEntry, ROOM_ENTRY_GROUPS } from '../../src/room-entry.js';
import { createRoomEntryAttachments } from '../../src/room-entry-attachments.js';
import { createIntroBackdrop } from '../../src/intro-backdrop.js';

/** Actual GLTFLoader hierarchy, vertices, materials and animation. The only
 * parser substitution is image decoding, which requires a browser. Metadata
 * and image byte checks belong to the caller; no texture appearance is claimed. */
export async function parseModelForCPU(relativePath) {
  const bytes = readFileSync(new URL(`../../${relativePath}`, import.meta.url));
  const data = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString());
  const loader = new GLTFLoader();
  // Override only image decode, including compressed assets. Actual KTX2
  // contents and formats are audited separately; no GPU transcode claim.
  loader.register(() => ({ name: data.extensionsUsed?.includes('KHR_texture_basisu') ? 'KHR_texture_basisu' : 'CPU_IMAGE_DECODE', loadTexture(index) {
    const texture = new THREE.Texture(); texture.name = data.textures?.[index]?.name ?? `cpu-texture-${index}`;
    texture.userData.cpuImageDecodeOmitted = true; return Promise.resolve(texture);
  } }));
  const gltf = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  return { ...gltf, bytes, data };
}

export function emit(target, type, properties = {}) {
  const event = Object.assign(new Event(type, { cancelable: true }), properties);
  target.dispatchEvent(event); return event;
}

/** Execute the unchanged production controller, real GSAP easing/timing, real
 * room-entry and Three.js transforms. DOM layout and PMREM GPU work are mocks.
 * Timelines are manually sought; there is no wall-clock timing assertion. */
export function introFixture({ welcomeGltf, roomGltf, width = 1440, height = 900, reducedMotion = false, introLighting, resident = false }) {
  const source = readFileSync(new URL('../../src/cube-intro.js', import.meta.url), 'utf8');
  const gpu = { generations: 0, generatorDisposals: 0, environmentDisposals: 0, reflectionDisposals: 0 };
  class Environment extends THREE.Scene { dispose() { gpu.environmentDisposals++; } }
  class Generator {
    fromScene() { gpu.generations++; return { texture: new THREE.Texture(), dispose() { gpu.reflectionDisposals++; } }; }
    dispose() { gpu.generatorDisposals++; }
  }
  const media = new EventTarget(), view = new EventTarget(), classes = new Set();
  Object.assign(view, { innerWidth: width, innerHeight: height, matchMedia: () => media });
  const doc = { defaultView: view, body: { style: { overflow: 'auto' }, classList: {
    add: (...values) => values.forEach(v => classes.add(v)), remove: (...values) => values.forEach(v => classes.delete(v)),
  } } };
  const child = () => Object.assign(new EventTarget(), { ownerDocument: doc, textContent: '', autoAlpha: 1, x: 0, y: 0, scale: 1, yPercent: 0, setAttribute() {}, querySelectorAll: () => [], disabled: false });
  const elements = new Map(), element = new EventTarget();
  const welcomeDetails = Array.from({ length: 3 }, child);
  Object.assign(element, { ownerDocument: doc, dataset: {}, querySelectorAll(selector) {
    return selector === '[data-intro-detail]' ? welcomeDetails : [];
  }, querySelector(selector) {
    if (!elements.has(selector)) {
      const node = child();
      if (selector.startsWith('[data-intro-')) {
        const letters = Array.from({ length: selector.includes('welcome') ? 11 : 6 }, child);
        node.querySelectorAll = query => query === '.intro-char' ? letters : [];
      }
      elements.set(selector, node);
    }
    return elements.get(selector);
  } });
  const createIntro = vm.runInNewContext(source.replace(/^import .*;\n/gm, '').replace('export function createCubeIntro', 'function createCubeIntro') + '\ncreateCubeIntro;', {
    THREE: { ...THREE, PMREMGenerator: Generator }, gsap, RoomEnvironment: Environment, bindIntroInput, createIntroBackdrop,
  });
  const welcomeResources = new Map();
  welcomeGltf.scene.traverse(node => {
    if (!node.isMesh) return;
    for (const resource of [node.geometry, ...[].concat(node.material), ...[].concat(node.material).flatMap(material => Object.values(material).filter(value => value?.isTexture))]) {
      if (welcomeResources.has(resource)) continue;
      welcomeResources.set(resource, 0); resource.addEventListener('dispose', () => welcomeResources.set(resource, welcomeResources.get(resource) + 1));
    }
  });
  const room = roomGltf.scene, originals = new Map(), resources = new Map(), exteriorModel = new THREE.Group();
  const snapshot = node => ({ position: node.position.clone(), quaternion: node.quaternion.clone(), rotation: node.rotation.clone(), scale: node.scale.clone(), visible: node.visible });
  const attachments = createRoomEntryAttachments({ THREE, room });
  // Capture original room ownership before resident replacement detaches old
  // terminal children. Their atlases remain shared with other room objects.
  room.traverse(node => {
    if (!node.isMesh) return;
    for (const resource of [node.geometry, ...[].concat(node.material), ...[].concat(node.material).flatMap(material => Object.values(material).filter(value => value?.isTexture))]) {
      if (resources.has(resource)) continue;
      resources.set(resource, 0); resource.addEventListener('dispose', () => resources.set(resource, resources.get(resource) + 1));
    }
  });
  let terminalDock;
  if (resident) {
    const residentSource = readFileSync(new URL('../../src/resident-terminal.js', import.meta.url), 'utf8');
    const createResident = vm.runInNewContext(residentSource.replace(/^import .*;\n/gm, '').replace('export function createResidentTerminal', 'function createResidentTerminal') + '\ncreateResidentTerminal;', {
      gsap, RoomEnvironment: Environment,
    });
    terminalDock = createResident({ THREE: { ...THREE, PMREMGenerator: Generator }, renderer: {}, room, welcomeGltf, reducedMotion });
    terminalDock.attachHome(); terminalDock.setTheme(true, 0);
  }
  room.traverse(node => originals.set(node, snapshot(node)));
  const external = [];
  room.traverse(node => { if (['environment.orbital_dock', 'environment.warm_gallery'].includes(node.userData.asset_id)) external.push(node); });
  room.updateWorldMatrix(true, true); external.forEach(node => exteriorModel.attach(node));
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#0b1d2d'); scene.add(room, exteriorModel);
  const componentIds = new Set(ROOM_ENTRY_GROUPS.flatMap(([, ids]) => ids)); componentIds.add('architecture.platform');
  componentIds.add('lighting.ceiling_warm');
  const roots = new Map(), snapshots = new WeakMap(), components = new Map();
  room.traverse(node => {
    if (node.userData.asset_id) { components.set(node.userData.asset_id, node); snapshots.set(node, snapshot(node)); }
    if (componentIds.has(node.userData.asset_id)) roots.set(node.userData.asset_id, node);
  });
  const bounds = new THREE.Box3().setFromObject(room);
  const shader = () => new THREE.ShaderMaterial({ uniforms: {}, fragmentShader: '#include <colorspace_fragment>' });
  const atmosphereGroup = new THREE.Group(), sky = new THREE.Mesh(new THREE.SphereGeometry(3), shader());
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), shader());
  atmosphereGroup.add(sky, new THREE.Group()); scene.add(ground, atmosphereGroup);
  // Controlled substitute for the existing instanced halo's shared uniform.
  // It lets controller tests verify its gradual reveal without claiming GPU output.
  let atmosphereIntroReveal = 1;
  const atmosphere = {
    group: atmosphereGroup, sky,
    setIntroReveal(value) {
      if (Number.isFinite(value)) atmosphereIntroReveal = THREE.MathUtils.clamp(value, 0, 1);
    },
    getState: () => ({ introReveal: atmosphereIntroReveal, warmLightCount: 1,
      warmLightsVisible: atmosphereGroup.children[1].visible, disposed: false }),
  };
  const contactShadow = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ transparent: true, opacity: .42 }));
  scene.add(contactShadow);
  const camera = new THREE.PerspectiveCamera(35, width / height, .01, 5000), controls = { target: new THREE.Vector3(), enabled: true };
  const endPose = { position: new THREE.Vector3(12, 10, 16), target: bounds.getCenter(new THREE.Vector3()) };
  const roomEntry = createRoomEntry({ room, roots, snapshots, bounds, externalIds: resident ? ['folding_drawing_terminal'] : [] });
  const counts = { start: 0, complete: 0 };
  const intro = createIntro({ scene, renderer: {}, welcomeModel: welcomeGltf.scene, welcomeClips: welcomeGltf.animations, terminalDock,
    room, roomEntry, exteriorModel, atmosphere, ground, contactShadow, camera, controls,
    bounds, element, reducedMotion, introLighting, getEndPose: () => endPose,
    onStart: () => { counts.start++; }, onComplete: () => { counts.complete++; controls.enabled = true; } });
  const timelines = () => gsap.globalTimeline.getChildren(false, false, true);
  function ready() {
    const before = new Set(timelines()); intro.ready();
    const timeline = timelines().find(item => !before.has(item)); timeline?.pause(); return timeline;
  }
  function enter(source = 'click') {
    const before = new Set(timelines());
    if (source === 'wheel') emit(view, 'wheel', { deltaY: 24 });
    else if (source === 'touch') { emit(view, 'touchstart', { touches: [{ clientY: 280 }] }); emit(view, 'touchmove', { touches: [{ clientY: 230 }] }); }
    else if (source === 'keyboard') emit(view, 'keydown', { key: 'ArrowDown' });
    else emit(element.querySelector('.intro-enter'), 'click');
    const timeline = timelines().find(item => !before.has(item)); timeline?.pause(); return timeline;
  }
  function assertRestored() {
    for (const [node, original] of originals) {
      // Exterior nodes were attached before the controller; their exact world
      // placement is verified independently, as attach can change local TRS.
      if (external.includes(node)) continue;
      assert.deepEqual(node.position.toArray(), original.position.toArray(), `${node.name}: position`);
      assert.deepEqual(node.quaternion.toArray(), original.quaternion.toArray(), `${node.name}: quaternion`);
      assert.deepEqual(node.scale.toArray(), original.scale.toArray(), `${node.name}: scale`);
      assert.equal(node.visible, original.visible, `${node.name}: visible`);
    }
    assert.deepEqual(camera.position.toArray(), endPose.position.toArray());
    assert.deepEqual(controls.target.toArray(), endPose.target.toArray());
    assert.equal(atmosphereIntroReveal, 1, 'existing fixture halos restore their complete alpha');
    assert.equal(atmosphereGroup.children[1].visible, true, 'fixture halo visibility returns unchanged');
    assert.equal(doc.body.style.overflow, 'auto'); assert.equal(controls.enabled, true);
    assert.ok([...resources.values()].every(count => count === 0), 'persistent room resources are never disposed');
    if (terminalDock) {
      assert.equal(terminalDock.getState().attachedHome, true);
      assert.equal(terminalDock.getState().introLight, 0);
      assert.ok([...welcomeResources.values()].every(count => count === 0), 'the intro borrows the resident GLB without releasing its resources');
      assert.equal(gpu.reflectionDisposals, 0, 'resident reflection remains alive after docking');
    }
  }
  return { intro, ready, enter, welcomeResources, introLighting, terminalDock, welcomeModel: welcomeGltf.scene, welcomeClips: welcomeGltf.animations, bounds, room, roomEntry, attachments, roots, components, resources, originals, scene, camera, controls, view, doc, element, media, counts, endPose, gpu,
    ground, sky, atmosphere, contactShadow, exteriorModel, assertRestored, cleanup() {
      intro.dispose();
      if (terminalDock) {
        assert.ok([...welcomeResources.values()].every(count => count === 0), 'controller disposal must leave the resident owner alive');
        terminalDock.dispose(); terminalDock.dispose();
        assert.ok([...welcomeResources.values()].every(count => count === 1), 'the resident owner releases only its separate GLB exactly once');
        assert.equal(gpu.reflectionDisposals, 1);
        assert.ok([...resources.values()].every(count => count === 0), 'resident disposal preserves all original shared room resources');
      }
      gsap.ticker.sleep();
    } };
}
