import gsap from 'gsap';
import * as THREE from 'three';
import { OrbitControls } from './utils/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { createExteriorAtmosphere } from './exterior-atmosphere.js';
import warmGalleryManifest from '../assets/blender/warm-gallery-v7-manifest.json';

// The template's custom OrbitControls, raycast interaction, GSAP reveal and modal
// transitions are rebound to the Blender asset IDs. No upstream personal media is used.
const assetMeta = {
  'architecture.platform': ['微缩房间', '悬浮平台、金属边框与分层地面，共同构成这间创作舱。', 'about'],
  main_display: ['创作主屏', '主屏上的橙蓝雕塑画面由 Blender 制作。这里将作为作品展示入口。', 'work'],
  compute_core: ['透明计算核心', '烟灰玻璃、金属骨架与橙色环形核心。', 'work'],
  'furniture.desk': ['悬臂工作台', '沿墙展开的金属工作台，承载屏幕与桌面小物。', 'work'],
  'furniture.work_chair': ['雕塑工作椅', '白色外壳与深灰软垫组成的悬浮座椅。', 'about'],
  'furniture.lounge': ['弧形休闲椅', '一处橙色的停顿，留给阅读与片刻休息。', 'about'],
  'furniture.coffee_table': ['烟色玻璃茶几', '透明桌面、雕塑底座和随手放下的笔记。', 'work'],
  'furniture.rug': ['环形嵌线地毯', '以同心圆细节划出房间的休息区域。', 'about'],
  robot_companion: ['三足机器人', '陶瓷外壳、橙色感应灯与三条独立机械腿。', 'about'],
  folding_drawing_terminal: ['折叠创作终端', '双屏、转轴与手写笔组成的小型创作设备。', 'work'],
  c_archive_dock: ['C 形归档底座', '三个独立卡匣收纳在弧形金属底座中。', 'work'],
  kinetic_three_petal_flower: ['三瓣机械花', '可以独立选择的花瓣，围绕金属轴心展开。', 'work'],
  headphones_on_stand: ['悬架耳机', '耳机与金属支架，保留独立耳罩结构。', 'about'],
  ceramic_ring_speaker: ['环形陶瓷音箱', '小巧的陶瓷环形音箱与悬挂轴。', 'about'],
  split_keyboard: ['分体键盘', '左右独立的键盘与旋钮，沿工作台排列。', 'work'],
  compact_camera: ['便携相机', '金属机身、橙色细节与独立镜头。', 'work'],
  thermal_cup: ['保温杯', '深色杯身与一圈暖色灯光。', 'about'],
  table_notebook_group: ['桌面手记', '笔记本、作品夹、笔与小旋钮构成的桌面组合。', 'work'],
  glass_bonsai_terrarium: ['玻璃微景观', '玻璃罩内的微型植物与卵石。', 'about'],
  trailing_wall_plant: ['垂坠植物', '从陈列柜顶部垂下的绿色枝叶。', 'about'],
  studio_reference_books: ['参考书与书挡', '窗下新增的三本书与钛色书挡，每本均可独立选择。', 'work'],
  geometric_specimen_cloche: ['几何标本罩', '烟色玻璃中的三叶几何雕塑。', 'work'],
  portable_fold_communicator: ['折叠通讯器', '窗下的双屏通讯器，保留独立屏幕转轴。', 'contact'],
  ceramic_mobius_study: ['莫比乌斯陶瓷', '白色连续曲面，与深色陈列台形成对比。', 'work'],
  glass_cutting_planter: ['玻璃水培盆', '透明容器与几片独立的新叶。', 'about'],
  black_ceramic_floor_planter: ['黑陶落地盆栽', '细长的黑陶花器，为房间角落补上绿色。', 'about'],
  v5_orbital_clock: ['轨道时钟', '钛色刻度、冰蓝轨道与独立指针，嵌入左侧墙面。', 'about'],
  v5_portable_projector: ['便携投影仪', '陶瓷机身、散热格栅与可转动的镜头。', 'work'],
  v5_magnetic_pen_dock: ['磁吸创作笔座', '三支金属笔停靠在橙色磁吸底座上。', 'work'],
  v5_modular_equipment_cases: ['模块器材箱', '双层器材箱填充窗下空间，上层可独立抬起。', 'work'],
  v5_geometric_floor_lamp: ['薄环落地灯', '暖色薄环灯头与双轨金属灯杆，呼应房间的弧线。', 'about'],
  v5_energy_capsule_rack: ['能量胶囊架', '三支陶瓷胶囊与冷暖状态灯组成的陈列小物。', 'work'],
  v5_mechanical_data_panel: ['机械数据面板', '墙面上的抽象信号刻度与旋钮。', 'work'],
  v5_scout_drone_display: ['微型探测艇', '悬置在窗台底座上的原创双翼探测艇。', 'about'],
};
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const time = (duration) => reducedMotion ? 0.01 : duration;
const $ = (query) => document.querySelector(query);
const canvas = $('#experience-canvas');
const loadingScreen = $('.loading-screen');
const enterButton = $('.loading-screen-button');
const soundEnterButton = $('.no-sound-button');
const loadingStatus = $('#loading-status');
const meter = $('.loading-meter');
const modal = $('.modal');
const overlay = $('.overlay');
const state = { loaded: false, entered: false, failed: false, isDay: false, isMuted: true, modal: null, errors: [], activeAsset: null, introComplete: false, baked: false, lastInteraction: null };
const roots = new Map();
const components = new Map();
const snapshots = new WeakMap();
const pickMeshes = [];
const hitboxes = [];
const hitboxToObject = new Map();
const portals = new Map();
const introTargets = [];
const hoverMaterial = new THREE.MeshBasicMaterial({ visible: false });
const frameDurations = new Float32Array(240);
let frameDurationIndex = 0, frameDurationCount = 0, previousFrameTime = 0;
let pendingPointer = null, cameraResetting = false;
let ambientGain, ambientSources = [], ambientRestoreTimer;
const portalSpecs = [
  { kind: 'work', title: '作品', subtitle: 'MY WORK', anchor: 'main_display' },
  { kind: 'about', title: '关于', subtitle: 'ABOUT ME', anchor: 'robot_companion' },
  { kind: 'contact', title: '联系', subtitle: 'CONTACT', anchor: 'portable_fold_communicator' },
];
let scene, camera, renderer, controls, room, keyLight, fillLight, ambient, ground, environment;
let currentHovered = null;
let lastFocused = null;
let audioContext;
let frame = 0;
let loadAttempt = 0;
let bounds;
const framingPoints = [];
const direction = new THREE.Vector3(11, 8.37, 18.4).normalize();
const referenceTarget = new THREE.Vector3(0, 2.03, -0.4);
const homeTarget = referenceTarget.clone();
const homePosition = new THREE.Vector3();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const warmLights = [];
const bakedMaterials = new Set();
let groundContactShadow;
let exterior, exteriorModel;
let pointerDown = null;
let dragging = false;
let multiTouch = false;
const activePointers = new Set();

function setProgress(percent, text) {
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  meter.setAttribute('aria-valuenow', value);
  $('.loading-meter span').style.width = `${value}%`;
  loadingStatus.textContent = text;
}
function failure(error) {
  const message = error instanceof Error ? error.message : String(error);
  state.failed = true;
  state.errors.push(message);
  loadingStatus.textContent = '房间载入失败，请重试。';
  enterButton.textContent = '重新载入 ↗';
  enterButton.disabled = false;
  soundEnterButton.hidden = true;
  console.error('Room preview:', error);
}
function sound(frequency = 480) {
  if (state.isMuted) return;
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    if (audioContext.state === 'suspended') audioContext.resume();
    const start = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(frequency, start);
    oscillator.frequency.exponentialRampToValueAtTime(frequency * 0.65, start + 0.1);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.025, start + 0.006);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.14);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(start);
    oscillator.stop(start + 0.15);
  } catch { /* Sound is optional; browsing remains available without it. */ }
}
function startAmbient() {
  if (ambientGain || state.isMuted) return;
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    ambientGain = audioContext.createGain();
    ambientGain.gain.value = 0.009;
    ambientGain.connect(audioContext.destination);
    [130.8128, 164.8138, 195.9977].forEach((frequency) => {
      const oscillator = audioContext.createOscillator();
      oscillator.frequency.value = frequency;
      oscillator.type = 'sine';
      oscillator.connect(ambientGain); oscillator.start(); ambientSources.push(oscillator);
    });
  } catch { /* Optional generated ambience does not block entry. */ }
}
function playNote(frequency) {
  if (state.isMuted) return;
  startAmbient();
  if (!audioContext) return;
  const now = audioContext.currentTime;
  if (ambientGain) ambientGain.gain.setTargetAtTime(0.0001, now, 0.1);
  clearTimeout(ambientRestoreTimer);
  ambientRestoreTimer = setTimeout(() => {
    if (ambientGain && !state.isMuted) ambientGain.gain.setTargetAtTime(0.009, audioContext.currentTime, 0.2);
  }, 2000);
  const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
  oscillator.type = 'triangle'; oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0, now); gain.gain.linearRampToValueAtTime(0.055, now + 0.008); gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.1);
  oscillator.connect(gain).connect(audioContext.destination); oscillator.start(now); oscillator.stop(now + 1.15);
}
function setMuted(muted) {
  state.isMuted = muted;
  document.body.classList.toggle('sound-enabled', !muted);
  $('.mute-toggle-button').setAttribute('aria-label', muted ? '开启交互声音' : '关闭交互声音');
  $('.mute-toggle-button').setAttribute('aria-pressed', String(!muted));
  if (!muted) { sound(620); startAmbient(); }
  if (ambientGain) ambientGain.gain.setTargetAtTime(muted ? 0 : 0.009, audioContext.currentTime, 0.12);
}

function setupScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#10171c');
  scene.fog = new THREE.Fog('#10171c', 40, 85);
  camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, 0.1, 500);
  camera.position.set(11, 10.4, 18);
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;
  renderer.shadowMap.autoUpdate = false;

  controls = new OrbitControls(camera, canvas);
  controls.target.copy(homeTarget);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 5;
  controls.maxDistance = 45;
  controls.minPolarAngle = 0;
  controls.maxPolarAngle = Math.PI / 2;
  controls.minAzimuthAngle = 0;
  controls.maxAzimuthAngle = Math.PI / 2;
  controls.panSpeed = 0.6;
  controls.zoomSpeed = 0.8;
  controls.enabled = false;
  controls.update();

  const pmrem = new THREE.PMREMGenerator(renderer);
  const studio = new RoomEnvironment();
  environment = pmrem.fromScene(studio, 0.025);
  scene.environment = environment.texture;
  scene.environmentIntensity = 0.68;
  studio.dispose();
  pmrem.dispose();

  ambient = new THREE.HemisphereLight('#d3e4ef', '#273745', 0.3);
  scene.add(ambient);
  keyLight = new THREE.DirectionalLight('#e9f1ff', 1.65);
  keyLight.position.set(-2.5, 14, 4);
  keyLight.target.position.set(0, 0, 0);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  Object.assign(keyLight.shadow.camera, { near: 0.1, far: 28, left: -9, right: 9, top: 9, bottom: -9 });
  keyLight.shadow.camera.updateProjectionMatrix();
  keyLight.shadow.normalBias = 0.025;
  keyLight.shadow.bias = -0.0001;
  keyLight.shadow.radius = 5;
  keyLight.shadow.blurSamples = 12;
  scene.add(keyLight, keyLight.target);
  fillLight = new THREE.DirectionalLight('#8eb8d7', 0.7);
  fillLight.position.set(5, 5, -2);
  scene.add(fillLight);

  RectAreaLightUniformsLib.init();
  for (const y of [1.33, 2.57, 3.86]) {
    const light = new THREE.RectAreaLight('#ffdfb2', 3.6, 1.2, 0.26);
    light.position.set(4, y, -2.5);
    light.lookAt(4, y - 0.6, -2.05);
    scene.add(light);
    warmLights.push(light);
  }
  const screenGlow = new THREE.RectAreaLight('#b9dcf0', 1.2, 3.6, 1.6);
  screenGlow.position.set(-3.2, 2.9, -0.3);
  screenGlow.lookAt(0, 2, 0);
  scene.add(screenGlow);

  ground = new THREE.Mesh(new THREE.PlaneGeometry(150, 150), new THREE.MeshStandardMaterial({ color: '#0d1820', roughness: 0.94, metalness: 0.04 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.3;
  ground.receiveShadow = true;
  scene.add(ground);
  canvas.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    state.errors.push('WebGL context lost');
    loadingScreen.hidden = false;
    gsap.set(loadingScreen, { clearProps: 'all' });
    failure(new Error('图形上下文中断，需要重新载入。'));
  });
}

// Fit to the visible room, retaining the reference camera direction on desktop
// and increasing distance on narrow screens rather than cropping the architecture.
function fitCamera(animate = false) {
  if (!bounds || !camera) return;
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize();
  const up = new THREE.Vector3().crossVectors(direction, right).normalize();
  const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const horizontalFill = 0.9;
  const verticalFill = innerWidth < 700 ? 0.82 : 0.88;
  const fitPoint = new THREE.Vector3();
  homeTarget.copy(referenceTarget);
  const fittedDistance = () => {
    let value = 0;
    for (const point of framingPoints) {
      const p = fitPoint.copy(point).sub(homeTarget);
      const requirement = Math.max(Math.abs(p.dot(right)) / (tan * camera.aspect * horizontalFill), Math.abs(p.dot(up)) / (tan * verticalFill));
      value = Math.max(value, requirement + p.dot(direction));
    }
    return value;
  };
  let distance = fittedDistance();
  // Perspective makes the foreground floor larger than the upper wall. Center
  // the actual projected silhouette, then refit, without changing view direction.
  for (let iteration = 0; iteration < 5; iteration++) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const point of framingPoints) {
      const p = fitPoint.copy(point).sub(homeTarget);
      const depth = distance - p.dot(direction);
      const x = p.dot(right) / (depth * tan * camera.aspect);
      const y = p.dot(up) / (depth * tan);
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    homeTarget.addScaledVector(right, (minX + maxX) * 0.5 * distance * tan * camera.aspect);
    homeTarget.addScaledVector(up, (minY + maxY) * 0.5 * distance * tan);
    distance = fittedDistance();
  }
  homePosition.copy(direction).multiplyScalar(distance).add(homeTarget);
  controls.maxDistance = Math.max(45, distance * 1.6);
  // Flush the template control's residual damping before a deterministic reset.
  gsap.killTweensOf([camera.position, controls.target]);
  controls.enableDamping = false;
  controls.update();
  if (animate) {
    clearHover();
    cameraResetting = true;
    controls.enabled = false;
    const timeline = gsap.timeline({ onComplete: () => {
      camera.position.copy(homePosition);
      controls.target.copy(homeTarget);
      controls.update();
      controls.enableDamping = true;
      cameraResetting = false;
      controls.enabled = state.introComplete && !state.modal;
    } });
    timeline.to(camera.position, { x: homePosition.x, y: homePosition.y, z: homePosition.z, duration: time(1.1), ease: 'power3.inOut' }, 0)
      .to(controls.target, { x: homeTarget.x, y: homeTarget.y, z: homeTarget.z, duration: time(1.1), ease: 'power3.inOut' }, 0);
  } else {
    camera.position.copy(homePosition);
    controls.target.copy(homeTarget);
    controls.update();
    controls.enableDamping = true;
  }
}

async function loadRoom() {
  const attempt = ++loadAttempt;
  state.failed = false;
  enterButton.disabled = true;
  enterButton.textContent = '正在载入房间';
  setProgress(0, '正在载入房间模型…');
  const loader = new GLTFLoader();
  try {
    const progress = [0, 0, 0, 0];
    const trackLoading = (index) => (event) => {
      if (!event.lengthComputable) return;
      progress[index] = event.loaded / event.total;
      const value = (progress[0] * 0.66 + progress[1] * 0.14 + progress[2] * 0.12 + progress[3] * 0.08) * 92;
      setProgress(value, `正在载入房间与小物 · ${Math.round(value)}%`);
    };
    const [gltf, additions, dock, gallery] = await Promise.all([
      loader.loadAsync('/models/orbital-atelier-v4.glb', trackLoading(0)),
      loader.loadAsync('/models/orbital-enrichment-v5.glb', trackLoading(1)),
      loader.loadAsync('/models/orbital-exterior-v6.glb', trackLoading(2)),
      loader.loadAsync('/models/orbital-warm-gallery-v7.glb', trackLoading(3)),
    ]);
    if (attempt !== loadAttempt) return;
    room = gltf.scene;
    room.name = 'OrbitalAtelier';
    additions.scene.name = 'StudioAdditionsV5';
    room.add(additions.scene);
    room.traverse((node) => {
      const id = node.userData.asset_id;
      if (id) {
        components.set(id, node);
        if (assetMeta[id]) roots.set(id, node);
        snapshots.set(node, { position: node.position.clone(), rotation: node.rotation.clone(), scale: node.scale.clone() });
      }
      if (!node.isMesh) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      const glass = materials.some((material) => material.transmission > 0.01 || material.transparent);
      node.castShadow = !glass;
      node.receiveShadow = true;
      for (const material of materials) {
        for (const property of ['map', 'emissiveMap', 'normalMap', 'roughnessMap', 'metalnessMap']) {
          if (material[property]) material[property].anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
        }
        if (material.name.includes('Vermilion_Woven')) {
          material.sheen = 0.16;
          material.sheenRoughness = 0.8;
        }
        if (material.transmission > 0) {
          // Thin transparent preview shells keep their interior models visible.
          // This also avoids an extra full-scene transmission pass on mobile.
          material.transmission = 0;
          material.transparent = true;
          material.opacity = material.name === 'WEB_MAT_Smoke_Glass' ? 0.4 : 0.16;
          material.depthWrite = false;
          material.side = THREE.FrontSide;
          material.envMapIntensity = 0.65;
          material.needsUpdate = true;
        }
      }
      pickMeshes.push(node);
    });
    if (roots.size !== Object.keys(assetMeta).length) console.warn(`Expected ${Object.keys(assetMeta).length} logical roots; received ${roots.size}`);
    scene.add(room);
    room.updateMatrixWorld(true);
    bounds = new THREE.Box3().setFromObject(room);
    // Use surface samples instead of empty AABB corners for a closer room view.
    for (const mesh of pickMeshes) {
      const positions = mesh.geometry.attributes.position;
      if (!positions) continue;
      const stride = Math.max(1, Math.floor(positions.count / 6000));
      for (let index = 0; index < positions.count; index += stride) {
        framingPoints.push(new THREE.Vector3().fromBufferAttribute(positions, index).applyMatrix4(mesh.matrixWorld));
      }
    }
    exteriorModel = new THREE.Group();
    exteriorModel.add(dock.scene, gallery.scene);
    exteriorModel.name = 'OrbitalDockExterior';
    exteriorModel.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = node.receiveShadow = false;
      node.raycast = () => {};
      for (const material of [].concat(node.material)) {
        if (material.map) material.map.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
        bakedMaterials.add(material);
        material.userData.previewBaseColor = material.color.clone();
      }
    });
    scene.add(exteriorModel);
    ground.position.y = new THREE.Box3().setFromObject(exteriorModel).min.y - 0.025;
    configureBakedScene();
    exterior = createExteriorAtmosphere({ THREE, scene, ground, roomBounds: bounds, reducedMotion });
    exterior.setWarmLights(warmGalleryManifest.warm_light_sources.map((lamp) => ({
      position: [lamp.position[0], lamp.position[2], -lamp.position[1]],
      color: lamp.color,
      scale: lamp.scale,
    })));
    createPortalButtons();
    createStaticHitboxes();
    fitCamera();
    renderer.shadowMap.needsUpdate = true;
    setProgress(96, '正在准备材质与灯光…');
    await renderer.compileAsync(scene, camera);
    renderer.render(scene, camera);
    state.loaded = true;
    setProgress(100, '房间已就绪');
    enterButton.innerHTML = '进入房间 <span>↗</span>';
    enterButton.disabled = false;
    soundEnterButton.hidden = false;
    prepareIntro();
  } catch (error) { failure(error); }
}

function prepareIntro() {
  for (const [id, node] of roots) {
    if (id.startsWith('architecture.') || id === 'furniture.desk' || id === 'furniture.rug' || id === 'main_display' || id === 'trailing_wall_plant') continue;
    introTargets.push(node);
  }
  introTargets.push(...portals.values());
  for (const node of introTargets) node.scale.setScalar(0);
}
function playIntroAnimation() {
  const timeline = gsap.timeline({
    defaults: { duration: time(0.8), ease: 'back.out(1.8)' },
    onComplete: () => {
      state.introComplete = true;
      controls.enabled = true;
      document.querySelectorAll('.preview-ui').forEach((element) => { element.inert = false; });
      renderer.shadowMap.needsUpdate = !state.baked;
      canvas.tabIndex = 0;
      canvas.focus({ preventScroll: true });
    },
  });
  timeline.timeScale(0.8);
  introTargets.forEach((node, index) => {
    const scale = snapshots.get(node).scale;
    timeline.to(node.scale, { x: scale.x, y: scale.y, z: scale.z }, time((index % 6) * 0.2 + Math.floor(index / 6) * 0.07));
  });
  timeline.to('.preview-ui', { opacity: 1, duration: time(0.5) }, time(0.4));
}
function playReveal(withSound = true) {
  if (!state.loaded || state.entered) return;
  state.entered = true;
  setMuted(!withSound);
  enterButton.disabled = true;
  soundEnterButton.hidden = true;
  gsap.timeline()
    .to(loadingScreen, { scale: 0.5, duration: time(1.2), delay: time(0.25), ease: 'back.in(1.8)' })
    .to(loadingScreen, {
      y: '200vh', transform: 'perspective(1000px) rotateX(45deg) rotateY(-35deg)',
      duration: time(1.2), ease: 'back.in(1.8)',
      onComplete: () => { loadingScreen.hidden = true; playIntroAnimation(); },
    }, `-=${time(0.1)}`);
}

function configureBakedScene() {
  let basic = 0, lit = 0;
  room.traverse((node) => {
    if (node.isMesh) for (const material of [].concat(node.material)) material.isMeshBasicMaterial ? basic++ : lit++;
  });
  state.baked = !!room.userData.web_baked || basic > lit;
  if (!state.baked) return;
  renderer.shadowMap.enabled = false;
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.toneMappingExposure = 1;
  scene.environment = null;
  environment?.dispose();
  environment = null;
  scene.traverse((node) => { if (node.isLight) node.visible = false; });
  room.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = false;
    node.receiveShadow = false;
    for (const material of [].concat(node.material)) {
      bakedMaterials.add(material);
      material.userData.previewBaseColor = material.color.clone();
    }
  });
  ground.material.dispose();
  ground.material = new THREE.MeshBasicMaterial({ color: '#101b23' });
  ground.receiveShadow = false;
  // A lightweight original contact shadow avoids a full-screen PBR ground pass.
  const shadowCanvas = document.createElement('canvas');
  shadowCanvas.width = shadowCanvas.height = 512;
  const context = shadowCanvas.getContext('2d');
  context.filter = 'blur(19px)';
  context.fillStyle = 'rgba(0,0,0,0.72)';
  context.beginPath(); context.roundRect(47, 85, 418, 342, 50); context.fill();
  const shadowTexture = new THREE.CanvasTexture(shadowCanvas);
  groundContactShadow = new THREE.Mesh(new THREE.PlaneGeometry(23, 21), new THREE.MeshBasicMaterial({ map: shadowTexture, transparent: true, depthWrite: false, toneMapped: false }));
  groundContactShadow.rotation.x = -Math.PI / 2;
  groundContactShadow.position.set(0.12, ground.position.y + 0.004, 0.06);
  scene.add(groundContactShadow);
}
function createPortalButtons() {
  for (const spec of portalSpecs) {
    const anchor = roots.get(spec.anchor);
    if (!anchor) continue;
    const anchorBounds = new THREE.Box3().setFromObject(anchor);
    const center = anchorBounds.getCenter(new THREE.Vector3());
    const sign = new THREE.Group();
    sign.name = `${spec.kind === 'work' ? 'My_Work' : spec.kind === 'about' ? 'About' : 'Contact'}_Button_Hover_Pointer`;
    sign.userData.portal = spec.kind;
    sign.userData.asset_id = `navigation.${spec.kind}`;
    sign.position.set(center.x, anchorBounds.max.y + 0.26, center.z + 0.11);
    sign.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction);
    const textureCanvas = document.createElement('canvas');
    textureCanvas.width = 640; textureCanvas.height = 240;
    const context = textureCanvas.getContext('2d');
    context.fillStyle = '#15242d'; context.fillRect(0, 0, 640, 240);
    context.strokeStyle = '#ed8149'; context.lineWidth = 6; context.strokeRect(5, 5, 630, 230);
    context.fillStyle = '#eef3f3'; context.font = '500 76px "PingFang SC", sans-serif';
    context.textAlign = 'center'; context.fillText(spec.title, 320, 113);
    context.fillStyle = '#aabfc9'; context.font = '28px sans-serif'; context.fillText(spec.subtitle, 320, 178);
    const texture = new THREE.CanvasTexture(textureCanvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(16, renderer.capabilities.getMaxAnisotropy());
    const width = spec.kind === 'work' ? 1.12 : 0.96;
    const plate = new THREE.Mesh(new THREE.BoxGeometry(width, width * 0.375, 0.045), new THREE.MeshBasicMaterial({ color: '#3c5564' }));
    const face = new THREE.Mesh(new THREE.PlaneGeometry(width * 0.985, width * 0.375 * 0.985), new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }));
    face.position.z = 0.036;
    sign.add(plate, face);
    room.add(sign);
    snapshots.set(sign, { position: sign.position.clone(), rotation: sign.rotation.clone(), scale: sign.scale.clone() });
    portals.set(spec.kind, sign);
  }
  room.updateMatrixWorld(true);
}
function canHover(node) {
  if (node.userData.portal) return true;
  const id = node.userData.asset_id;
  return id && !id.startsWith('architecture.') && !id.startsWith('furniture.') && !['main_display', 'compute_core', 'trailing_wall_plant'].includes(id);
}
function createStaticHitboxes() {
  const boxes = new Map();
  for (const mesh of pickMeshes) {
    const target = componentFor(mesh);
    if (!target || !canHover(target)) continue;
    if (!boxes.has(target)) boxes.set(target, new THREE.Box3());
    boxes.get(target).union(new THREE.Box3().setFromObject(mesh));
  }
  for (const sign of portals.values()) boxes.set(sign, new THREE.Box3().setFromObject(sign));
  for (const [target, box] of boxes) {
    const size = box.getSize(new THREE.Vector3()).multiply(new THREE.Vector3(1.04, 1.12, 1.04));
    size.max(new THREE.Vector3(0.06, 0.06, 0.06));
    const hitbox = new THREE.Mesh(new THREE.BoxGeometry(size.x, size.y, size.z), hoverMaterial);
    hitbox.name = `${target.name}_StaticHitbox`;
    hitbox.position.copy(box.getCenter(new THREE.Vector3()));
    scene.add(hitbox);
    hitboxes.push(hitbox);
    hitboxToObject.set(hitbox, target);
  }
}

function componentFor(node) {
  for (let current = node; current && current !== room; current = current.parent) {
    if (current.userData.asset_id) return current;
  }
  return null;
}
function pick(clientX, clientY) {
  if (!room || !state.introComplete || state.modal || cameraResetting) return null;
  const rect = canvas.getBoundingClientRect();
  pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(hitboxes, false);
  if (!hits.length) return null;
  let selected = hitboxToObject.get(hits[0].object);
  // A parent's broad static box can cover the empty space around its smaller
  // components (a lens or archive cartridge). Prefer an intersected descendant
  // within that same asset so each component remains independently reachable.
  for (let index = 1; index < hits.length; index++) {
    const candidate = hitboxToObject.get(hits[index].object);
    for (let parent = candidate.parent; parent; parent = parent.parent) {
      if (parent === selected) { selected = candidate; break; }
    }
  }
  return selected;
}
function hoverScaleFor(node) {
  // Keep the navigation signs at the template's original size and tilt.
  if (node.userData.portal) return 1.4;
  // Blender asset roots can tune their own response; a component inherits its
  // asset's setting unless it supplies a more specific hover_scale override.
  for (let current = node; current && current !== room; current = current.parent) {
    const configured = current.userData.hover_scale;
    if (typeof configured === 'number' && Number.isFinite(configured)) {
      return THREE.MathUtils.clamp(configured, 1.05, 2.2);
    }
  }
  const id = node.userData.asset_id || '';
  if (id.startsWith('furniture.') || id === 'black_ceramic_floor_planter') return 1.16;
  if (id === 'v5_geometric_floor_lamp') return 1.16;
  if (id === 'v5_modular_equipment_cases') return 1.28;
  if (id === 'robot_companion') return 1.3;
  return 1.8;
}
function animateHover(node, active) {
  const original = snapshots.get(node);
  if (!original || !canHover(node)) return;
  gsap.killTweensOf(node.scale);
  if (node.userData.portal) gsap.killTweensOf(node.rotation);
  if (node.userData.asset_id === 'thermal_cup') gsap.killTweensOf(node.position);
  const id = node.userData.asset_id;
  const factor = active ? hoverScaleFor(node) : 1;
  gsap.to(node.scale, { x: original.scale.x * factor, y: original.scale.y * factor, z: original.scale.z * factor, duration: time(active ? 0.5 : 0.3), ease: 'back.out(2)' });
  if (node.userData.portal) {
    const direction = node.userData.portal === 'about' ? -1 : 1;
    gsap.to(node.rotation, { x: original.rotation.x + (active ? direction * Math.PI / 10 : 0), duration: time(active ? 0.5 : 0.3), ease: 'back.out(2)' });
  }
  if (id === 'thermal_cup') gsap.to(node.position, { y: original.position.y + (active ? 0.2 : 0), duration: time(active ? 0.5 : 0.3), ease: 'back.out(2)' });
}
function clearHover() {
  if (currentHovered) animateHover(currentHovered, false);
  currentHovered = null;
  pendingPointer = null;
  canvas.style.cursor = dragging ? 'grabbing' : 'grab';
}
function updateHover(event) {
  if (event.pointerType === 'touch' || dragging || state.modal || !controls?.enabled) return;
  const hovered = pick(event.clientX, event.clientY);
  if (hovered !== currentHovered) {
    if (currentHovered) animateHover(currentHovered, false);
    currentHovered = hovered;
    if (hovered) animateHover(hovered, true);
  }
  canvas.style.cursor = hovered ? 'pointer' : 'grab';
}
function respondToObject(node, event) {
  const id = node.userData.asset_id;
  state.lastInteraction = { id, action: node.userData.portal ? 'open-panel' : 'animate', time: performance.now() };
  if (node.userData.portal) { showModal(node.userData.portal); return; }
  const original = snapshots.get(node);
  if (!original) return;
  // The original piano press is rebound to the split keyboard and its controls.
  if (id.startsWith('v5_') && node.userData.interaction === 'lift') {
    const worldUp = new THREE.Vector3(0, 0.14, 0);
    const parentRotation = node.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
    worldUp.applyQuaternion(parentRotation);
    gsap.killTweensOf(node.position);
    gsap.timeline().to(node.position, { x: original.position.x + worldUp.x, y: original.position.y + worldUp.y, z: original.position.z + worldUp.z, duration: time(0.4), ease: 'back.out(2)' })
      .to(node.position, { x: original.position.x, y: original.position.y, z: original.position.z, duration: time(0.35), ease: 'power2.out' });
    sound(440);
  } else if (id.startsWith('v5_') && ['rotate', 'tilt'].includes(node.userData.interaction)) {
    const axis = id === 'v5_floor_lamp_head' ? 'x'
      : ['v5_clock_dial', 'v5_projector_lens', 'v5_data_panel_selector'].includes(id) ? 'z'
      : node.userData.interaction === 'tilt' ? 'z' : 'y';
    gsap.killTweensOf(node.rotation);
    gsap.timeline().to(node.rotation, { [axis]: original.rotation[axis] + Math.PI / 5, duration: time(0.45), ease: 'back.out(2)' })
      .to(node.rotation, { [axis]: original.rotation[axis], duration: time(0.35), ease: 'power2.out' });
    sound(560);
  } else if (/keyboard|creative_controller/.test(id)) {
    const semitone = { keyboard_half_0: 0, keyboard_half_1: 7, keyboard_dial: 4, desktop_creative_controller: 9, split_keyboard: 12 }[id] ?? 0;
    gsap.killTweensOf(node.rotation);
    playNote(261.6256 * Math.pow(2, semitone / 12));
    gsap.timeline().to(node.rotation, { x: original.rotation.x + Math.PI / 42, duration: time(0.4), ease: 'back.out(2)' })
      .to(node.rotation, { x: original.rotation.x, duration: time(0.25), ease: 'back.out(2)' });
  } else if (/archive_cartridge/.test(id)) {
    gsap.killTweensOf(node.position);
    gsap.timeline().to(node.position, { z: original.position.z + 0.18, duration: time(0.4), ease: 'back.out(2)' })
      .to(node.position, { z: original.position.z, duration: time(0.35), ease: 'back.out(2)' });
    sound(390);
  } else if (/panel|petal|lens|dial|mobius|specimen/.test(id)) {
    gsap.killTweensOf(node.rotation);
    gsap.timeline().to(node.rotation, { y: original.rotation.y + Math.PI / 10, duration: time(0.4), ease: 'back.out(2)' })
      .to(node.rotation, { y: original.rotation.y, duration: time(0.35), ease: 'back.out(2)' });
    sound(520);
  } else {
    animateHover(node, true);
    gsap.delayedCall(time(0.55), () => { if (currentHovered !== node || event.pointerType === 'touch') animateHover(node, false); });
  }
}

const placeholderRows = (names) => `<div class="placeholder-grid">${names.map((name) => `<div class="placeholder-row"><span>${name}</span><span>待补充</span></div>`).join('')}</div>`;
const content = {
  work: ['SELECTED WORK / 01', '作品', '<p>这里将放入我的项目、过程与成果。作品资料尚未提供，先为每个故事留出位置。</p>' + placeholderRows(['作品名称与封面', '项目简介与个人职责', '过程、成果与项目链接'])],
  about: ['ABOUT / 02', '关于我', '<p>欢迎来到这间可以探索的房间。我的个人介绍会在资料补齐后放在这里。</p>' + placeholderRows(['姓名与头像', '简介与专业方向', '经历与技能'])],
  contact: ['GET IN TOUCH / 03', '联系', '<p>联系方式尚未提供。邮箱与社交主页确认后，会在这里开放。</p>' + placeholderRows(['电子邮箱', '社交主页', '其他联系方式'])],
};
function showModal(kind) {
  if (!state.introComplete) return;
  clearHover();
  sound();
  if (!state.modal) lastFocused = document.activeElement;
  state.modal = kind;
  state.activeAsset = `navigation.${kind}`;
  controls.enabled = false;
  $('.scene-accessibility').inert = true;
  $('.scene-controls').inert = true;
  $('#experience').inert = true;
  const [category, title, body] = content[kind] || content.about;
  $('#modal-category').textContent = category;
  $('#modal-title').textContent = title;
  $('#modal-content').innerHTML = body;
  modal.dataset.kind = kind;
  modal.hidden = false;
  overlay.hidden = false;
  modal.scrollTop = 0;
  gsap.killTweensOf([modal, overlay]);
  gsap.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: time(0.5) });
  gsap.fromTo(modal, { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, duration: time(0.5), ease: 'back.out(2)', onComplete: () => $('.modal-exit-button').focus({ preventScroll: true }) });
}
function hideModal() {
  if (!state.modal) return;
  sound(380);
  gsap.killTweensOf([modal, overlay]);
  gsap.to(overlay, { opacity: 0, duration: time(0.5) });
  gsap.to(modal, { opacity: 0, scale: 0, duration: time(0.5), ease: 'back.in(2)', onComplete: () => {
    state.modal = null;
    state.activeAsset = null;
    modal.hidden = true;
    overlay.hidden = true;
    controls.enabled = true;
    $('.scene-accessibility').inert = false;
    $('.scene-controls').inert = false;
    $('#experience').inert = false;
    lastFocused?.focus({ preventScroll: true });
  } });
}
function toggleTheme() {
  state.isDay = !state.isDay;
  document.body.classList.toggle('day-theme', state.isDay);
  document.body.classList.toggle('night-theme', !state.isDay);
  $('.theme-toggle-button').setAttribute('aria-label', state.isDay ? '切换为夜间灯光' : '切换为日间灯光');
  $('.theme-toggle-button').setAttribute('aria-pressed', String(state.isDay));
  const transition = { duration: time(1.5), ease: 'power2.inOut', overwrite: true };
  exterior?.setTheme(state.isDay, time(1.5));
  if (state.baked) {
    for (const material of bakedMaterials) {
      const original = material.userData.previewBaseColor;
      gsap.to(material.color, {
        r: original.r * (state.isDay ? 1.08 : 1),
        g: original.g * (state.isDay ? 1.045 : 1),
        b: original.b * (state.isDay ? 0.99 : 1),
        ...transition,
      });
    }
    if (groundContactShadow) gsap.to(groundContactShadow.material, { opacity: state.isDay ? 0.55 : 1, ...transition });
  } else {
    gsap.to(scene, { environmentIntensity: state.isDay ? 0.95 : 0.68, ...transition });
    gsap.to(keyLight, { intensity: state.isDay ? 2.8 : 1.65, ...transition });
    gsap.to(ambient, { intensity: state.isDay ? 0.8 : 0.3, ...transition });
    warmLights.forEach((light) => gsap.to(light, { intensity: state.isDay ? 2.5 : 3.6, ...transition }));
  }
  sound(720);
}

function events() {
  enterButton.addEventListener('click', () => state.failed ? location.reload() : playReveal(true));
  soundEnterButton.addEventListener('click', () => playReveal(false));
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-modal]');
    if (button) showModal(button.dataset.modal);
    if (event.target.closest('[data-action="reset"]')) { sound(); fitCamera(true); }
  });
  $('.modal-exit-button').addEventListener('click', hideModal);
  overlay.addEventListener('click', hideModal);
  $('.theme-toggle-button').addEventListener('click', toggleTheme);
  $('.mute-toggle-button').addEventListener('click', () => setMuted(!state.isMuted));
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideModal();
    if (state.modal && event.key === 'Tab') {
      const focusable = [...modal.querySelectorAll('button, a[href], [tabindex="0"]')];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  canvas.addEventListener('pointerdown', (event) => {
    activePointers.add(event.pointerId);
    multiTouch ||= activePointers.size > 1;
    pointerDown = { x: event.clientX, y: event.clientY, id: event.pointerId, button: event.button };
    dragging = false;
  });
  canvas.addEventListener('pointermove', (event) => {
    if (pointerDown && (Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 6 || multiTouch)) { dragging = true; clearHover(); }
    pendingPointer = { clientX: event.clientX, clientY: event.clientY, pointerType: event.pointerType };
  });
  canvas.addEventListener('pointerup', (event) => {
    const clicked = pointerDown && !dragging && !multiTouch && pointerDown.button === 0 && event.pointerId === pointerDown.id;
    activePointers.delete(event.pointerId);
    pointerDown = null;
    dragging = false;
    if (!activePointers.size) multiTouch = false;
    if (clicked) {
      const selected = pick(event.clientX, event.clientY);
      if (selected) respondToObject(selected, event);
    }
  });
  const cancelPointer = (event) => {
    activePointers.delete(event.pointerId);
    pointerDown = null;
    dragging = false;
    if (!activePointers.size) multiTouch = false;
    clearHover();
  };
  canvas.addEventListener('pointercancel', cancelPointer);
  canvas.addEventListener('pointerleave', clearHover);
  canvas.addEventListener('wheel', clearHover, { passive: true });
  window.addEventListener('resize', () => {
    const previousAspect = camera.aspect;
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    if (Math.abs(previousAspect - camera.aspect) > 0.15 || !state.entered) fitCamera(false);
  });
}
function render(timestamp = performance.now()) {
  frame = requestAnimationFrame(render);
  if (document.hidden) { previousFrameTime = 0; return; }
  if (import.meta.env.DEV && previousFrameTime && state.introComplete) {
    frameDurations[frameDurationIndex] = timestamp - previousFrameTime;
    frameDurationIndex = (frameDurationIndex + 1) % frameDurations.length;
    frameDurationCount = Math.min(frameDurationCount + 1, frameDurations.length);
  }
  previousFrameTime = timestamp;
  exterior?.update(timestamp * 0.001, camera);
  if (cameraResetting) camera.lookAt(controls.target); else controls.update();
  // Keep the template's drag/pan/zoom controls, but prevent low-angle panning
  // from taking the viewer below the physical exhibition floor.
  if (exterior && camera.position.y < ground.position.y + 0.25) {
    const raise = ground.position.y + 0.25 - camera.position.y;
    camera.position.y += raise;
    controls.target.y += raise;
    camera.lookAt(controls.target);
  }
  if (pendingPointer) { const event = pendingPointer; pendingPointer = null; updateHover(event); }
  if (state.introComplete && !reducedMotion && !state.modal) {
    const seconds = timestamp * 0.001;
    const chair = roots.get('furniture.work_chair');
    if (chair && currentHovered !== chair) {
      const base = snapshots.get(chair);
      chair.rotation.y = base.rotation.y + Math.PI / 8 * Math.sin(seconds * 0.5) * (1 - Math.abs(Math.sin(seconds * 0.5)) * 0.3);
    }
  }
  renderer.render(scene, camera);
}
function performanceSummary() {
  const samples = Array.from(frameDurations.subarray(0, frameDurationCount)).sort((a, b) => a - b);
  if (!samples.length) return { samples: 0 };
  const p50 = samples[Math.floor(samples.length * 0.5)], p95 = samples[Math.min(samples.length - 1, Math.floor(samples.length * 0.95))];
  return { samples: samples.length, rafP50Ms: p50, rafP95Ms: p95, rafMedianFps: 1000 / p50, devicePixelRatio, renderPixelRatio: renderer.getPixelRatio() };
}

Object.defineProperty(window, '__roomPreview', { value: Object.freeze({
  getState: () => ({ loaded: state.loaded, entered: state.entered, failed: state.failed, day: state.isDay, muted: state.isMuted, modal: state.modal, activeAsset: state.activeAsset, hovered: currentHovered ? { id: currentHovered.userData.asset_id, scale: currentHovered.scale.toArray(), factor: hoverScaleFor(currentHovered) } : null, errors: [...state.errors], assetCount: roots.size, componentCount: components.size, rootIds: [...roots.keys()], componentIds: [...components.keys()], camera: camera?.position.toArray(), target: controls?.target.toArray(), drawCalls: renderer?.info.render.calls, triangles: renderer?.info.render.triangles, renderer: renderer?.getPixelRatio(), controlsEnabled: controls?.enabled, introComplete: state.introComplete, baked: state.baked, portalCount: portals.size, hitboxCount: hitboxes.length, lastInteraction: state.lastInteraction, performance: performanceSummary() }),
  get scene() { return scene; }, get camera() { return camera; }, get room() { return room; }, get renderer() { return renderer; }, get portals() { return new Map(portals); },
  get roots() { return new Map(roots); }, get components() { return new Map(components); },
}) });

try { setupScene(); events(); render(); loadRoom(); }
catch (error) { failure(error); enterButton.addEventListener('click', () => location.reload()); }
