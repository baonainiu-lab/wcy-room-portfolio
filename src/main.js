import gsap from 'gsap';
import * as THREE from 'three';
import { OrbitControls } from './utils/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { createExteriorAtmosphere } from './exterior-atmosphere.js';
import { createDualLighting } from './dual-lighting.js';
import { createIntroLighting } from './intro-lighting.js';
import { createPhysicalSurface } from './physical-surface.js';
import { resolveMaterialRelease } from './material-release.js';
import { createTerminalToneMapping } from './terminal-tone.js';
import { createStartupReadiness, warmSceneForStartup, waitForStartupGpu } from './startup-readiness.js';
import { createSceneCallout } from './scene-callout.js';
import { createResumeEntryLabels } from './resume-entry-labels.js';
import { createRoomEntry } from './room-entry.js';
import { createRoomEntryAttachments } from './room-entry-attachments.js';
import { createSceneMotion } from './scene-motion.js';
import { createTrackedHitboxes } from './tracked-hitboxes.js';
import { createSceneClock } from './scene-clock.js';
import { createSceneTimeTheme } from './scene-time-theme.js';
import { createCubeIntro } from './cube-intro.js';
import './minimal-scene-ui.scss';
import { createResidentTerminal } from './resident-terminal.js';
import { createWorksGallery } from './works-gallery.js';
import { createAboutAtelier } from './about-atelier.js';
import { configureAboutBookEntry } from './about-book-entry.js';
import { createGalleryNavigation } from './gallery-navigation.js';
import { createWorkDetail } from './work-detail.js';
import { createExhibitDetail } from './exhibit-detail.js';
import { getGalleryExhibit, galleryFocusId } from './gallery-catalog.js';
import { createResumeBook } from './resume-book.js';
import { inspectionPose, projectObjectRect, RESUME_BOOK_ID } from './scene-inspection.js';
import { createGalleryTransition } from './gallery-transition.js';
import './gallery-transition.scss';
import { createLiveRoomSurfaces } from './live-room-surfaces.js';
import { createRoomHoverClearance, isMountedRoomPart } from './room-hover-clearance.js';
import { createRoomCameraGuard } from './room-camera-guard.js';
import warmGalleryManifest from '../assets/blender/warm-gallery-v7-manifest.json';
import './scene-time-theme.scss';

// The template's custom OrbitControls, raycast interaction, GSAP reveal and modal
// transitions are rebound to the Blender asset IDs. No upstream personal media is used.
const assetMeta = {
  'architecture.platform': ['微缩房间', '悬浮平台、金属边框与分层地面，共同构成这间创作舱。', 'about'],
  main_display: ['创作主屏', '轮播 Blender 制作的雕塑与长廊场景画面。点击进入作品长廊，个人项目资料待补充。', 'work'],
  compute_core: ['透明计算核心', '烟灰玻璃、金属骨架与橙色环形核心。', 'work'],
  'furniture.desk': ['悬臂工作台', '沿墙展开的金属工作台，承载屏幕与桌面小物。', 'work'],
  'furniture.work_chair': ['雕塑工作椅', '白色外壳与深灰软垫组成的悬浮座椅。', 'about'],
  'furniture.lounge': ['弧形休闲椅', '一处橙色的停顿，留给阅读与片刻休息。', 'about'],
  'furniture.coffee_table': ['烟色玻璃茶几', '透明桌面、雕塑底座和随手放下的笔记。', 'work'],
  'furniture.rug': ['环形嵌线地毯', '以同心圆细节划出房间的休息区域。', 'about'],
  robot_companion: ['三足机器人', '陶瓷外壳、橙色感应灯与三条独立机械腿。', 'about'],
  folding_drawing_terminal: ['折叠创作终端', '开场的创作终端停靠在这里，保留可独立选择的翻盖、橙色旋钮与侧边滑轨。', 'work'],
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
  v8_desk_glow_lamp: ['桌边暖光灯', '原创微型桌灯，以低亮度暖光照亮工作台一角，保留夜间的局部层次。', 'about'],
  v8_window_light_bar: ['窗下洗墙灯', '原创细长灯条，沿窗下边缘投下克制的暖色光带。', 'about'],
  v8_reading_puck: ['阅读微光灯', '原创小型阅读灯，为休闲区补上一点温暖的近处光线。', 'about'],
  'lighting.ceiling_warm': ['暖光顶灯', '嵌在顶部横梁内侧的暖色灯具，入夜后向上照亮木墙、向下照亮工作台与地板。', 'about'],
};
const previewQA = import.meta.env.DEV && new URLSearchParams(location.search).has('qa');
if (previewQA) performance.setResourceTimingBufferSize(1200);
const materialRelease = resolveMaterialRelease(location.search);
const roomAtlasSlots = Array.from({ length: materialRelease.roomAtlasCount ?? 12 }, (_, index) => index);
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
  (previewQA && new URLSearchParams(location.search).get('motion') === 'reduce');
const time = (duration) => reducedMotion ? 0.01 : duration;
const $ = (query) => document.querySelector(query);
const canvas = $('#experience-canvas');
const loadingScreen = $('#intro-screen');
loadingScreen.dataset.motion = reducedMotion ? 'reduce' : 'full';
const syncLoadingMotionVisibility = () => { loadingScreen.dataset.pageHidden = String(document.hidden); };
syncLoadingMotionVisibility();
document.addEventListener('visibilitychange', syncLoadingMotionVisibility);
const enterButton = $('.intro-enter');
const retryButton = $('.intro-retry');
const skipButton = $('.intro-skip');
const loadingStatus = $('#loading-status');
const meter = $('.loading-meter');
const startupReadiness = createStartupReadiness({ onUpdate: progress => {
  meter.setAttribute('aria-valuenow', progress.percent);
  meter.setAttribute('aria-valuetext', `${progress.percent}% · ${progress.message}`);
  $('.loading-meter span').style.width = `${progress.percent}%`;
  $('#loading-percent').textContent = `${progress.percent}%`;
  // Codrops PathLoader's normalized dash mapping, driven only by real readiness.
  // SVG pathLength=100 makes every authored contour share the actual percentage.
  loadingScreen.style.setProperty('--startup-progress', String(progress.percent / 100));
  for (const path of loadingScreen.querySelectorAll('[data-loading-trace]')) {
    path.style.strokeDashoffset = String(100 - progress.percent);
  }
  loadingStatus.textContent = progress.message;
  for (const stage of progress.stages) {
    const node = document.querySelector(`[data-startup-stage="${stage.id}"]`);
    if (node) node.dataset.state = stage.state;
  }
} });
const modal = $('.modal');
const overlay = $('.overlay');
const state = { loaded: false, entered: false, failed: false, isDay: false, isMuted: true, modal: null, errors: [], activeAsset: null, activeSection: 'work', currentScene: 'room', transitioning: false, galleryLoading: false, galleryRequested: false, aboutLoading: false, aboutRequested: false, introComplete: false, baked: false, lastInteraction: null };
const sceneTimeTheme = createSceneTimeTheme({ body: document.body, themeMeta: document.querySelector('meta[name="theme-color"]') });
const roots = new Map();
const components = new Map();
const snapshots = new WeakMap();
const pickMeshes = [];
const roomRuntimeMaps = new Set();
const hitboxes = [];
const hitboxToObject = new Map();
const trackedHitboxes = createTrackedHitboxes();
const portals = new Map();
let sceneClock;
let roomEntry, roomEntryAttachments, cubeIntro, terminalDock, sceneMotion, liveRoomSurfaces, hoverClearance, roomCameraGuard;
let worksGallery, galleryPromise, galleryNavigation, galleryTransition, savedRoomPose, cameraTimeline;
let galleryRequestId = 0, aboutRequestId = 0;
let aboutAtelier, aboutPromise, aboutTransition, activeSceneTransition, nextSceneAfterReturn = null;
let requestedSceneTitle = '日光长廊';
const satellite = (kind = state.currentScene) => kind === 'about' ? aboutAtelier : kind === 'gallery' ? worksGallery : null;
const hoverMaterial = new THREE.MeshBasicMaterial({ visible: false });
const frameDurations = new Float32Array(240);
let frameDurationIndex = 0, frameDurationCount = 0, previousFrameTime = 0;
let pendingPointer = null, cameraResetting = false;
let inspection = null;
let ambientGain, ambientSources = [], ambientRestoreTimer;
const portalSpecs = [
  { kind: 'work', title: '作品', subtitle: '项目资料', anchor: 'main_display' },
  { kind: 'about', title: '关于我', subtitle: '档案工坊', anchor: 'notebook' },
  { kind: 'contact', title: '联系', subtitle: '联系方式', anchor: 'portable_fold_communicator' },
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
let groundContactShadow;
let exterior, exteriorModel, lighting, introLighting, roomPhysicalSurface, terminalTone, sceneCallout, resumeEntryLabels;
let disposeLoadedRoom = () => {}, disposeOrphanWelcome = () => {};
const calloutTargets = new WeakMap();
let defaultCalloutTarget;
let pointerDown = null;
let dragging = false;
let multiTouch = false;
const activePointers = new Set();
const workDetail = createWorkDetail({
  reducedMotion,
  onClose: closeInspection,
  onPlaybackChange: playing => {
    clearTimeout(ambientRestoreTimer);
    if (ambientGain && audioContext) ambientGain.gain.setTargetAtTime(playing || !canPlaySceneAudio() ? 0 : .009, audioContext.currentTime, .15);
  },
});
const resumeBook = createResumeBook({ reducedMotion, onClose: closeInspection });
const exhibitDetail = createExhibitDetail({ reducedMotion, onClose: closeInspection,
  onPlaybackChange: playing => {
    clearTimeout(ambientRestoreTimer);
    if (ambientGain && audioContext) ambientGain.gain.setTargetAtTime(playing || !canPlaySceneAudio() ? 0 : .009, audioContext.currentTime, .15);
  },
});

function releaseInspection() {
  inspection = null; state.modal = null; state.activeAsset = null;
  applySceneLimits();
  controls.maxDistance = Math.max(controls.maxDistance, camera.position.distanceTo(controls.target) * 1.05);
  setTravelBusy(false);
  $('#experience').inert = false;
  if ($('.gallery-nav')) $('.gallery-nav').inert = false;
  updateNavigation();
  if (ambientGain && audioContext) ambientGain.gain.setTargetAtTime(canPlaySceneAudio() ? .009 : 0, audioContext.currentTime, .15);
  const focusTarget = lastFocused instanceof HTMLElement && lastFocused.isConnected && !lastFocused.closest('[hidden], [inert]') && !lastFocused.matches(':disabled') && lastFocused.getClientRects().length ? lastFocused : canvas;
  focusTarget.focus({ preventScroll: true });
}

function closeInspection() {
  if (!inspection || inspection.phase === 'returning') return;
  cameraTimeline?.kill(); cameraTimeline = null;
  inspection.phase = 'returning';
  const saved = inspection.saved;
  const startPosition = camera.position.clone(), startTarget = controls.target.clone(), progress = { value: 0 };
  let aspect, destination;
  const resolve = () => {
    if (aspect !== camera.aspect) {
      aspect = camera.aspect;
      destination = Math.abs(aspect - saved.aspect) > .05 ? satellite().pose(aspect, camera.fov) : saved;
    }
    return destination;
  };
  cameraTimeline = gsap.timeline({ onComplete: () => {
    const pose = resolve();
    cameraTimeline = null; camera.position.copy(pose.position); controls.target.copy(pose.target);
    releaseInspection();
  } }).to(progress, { value: 1, duration: time(.6), ease: 'power2.inOut', onUpdate: () => {
    const pose = resolve();
    camera.position.lerpVectors(startPosition, pose.position, progress.value);
    controls.target.lerpVectors(startTarget, pose.target, progress.value);
  } }, 0);
}

function openInspection(kind, node, exhibit = null) {
  if (!node || inspection || state.modal || state.transitioning || cameraResetting || !state.introComplete) return;
  clearHover();
  lastFocused = document.activeElement;
  inspection = { kind, node, exhibitIndex: exhibit?.index ?? null, phase: 'approaching', origin: null,
    saved: { position: camera.position.clone(), target: controls.target.clone(), aspect: camera.aspect } };
  state.modal = kind; state.activeAsset = node.userData.asset_id;
  state.activeSection = kind === 'resume' ? 'about' : 'work';
  setTravelBusy(true);
  $('#experience').inert = true;
  if ($('.gallery-nav')) $('.gallery-nav').inert = true;
  if (ambientGain && audioContext) ambientGain.gain.setTargetAtTime(0, audioContext.currentTime, .15);
  updateNavigation();
  const pose = inspectionPose(camera, node, kind);
  cameraTimeline = gsap.timeline({ onComplete: () => {
    cameraTimeline = null;
    if (!inspection || inspection.phase !== 'approaching') return;
    camera.position.copy(pose.position); controls.target.copy(pose.target);
    camera.lookAt(pose.target); camera.updateMatrixWorld(true);
    inspection.origin = projectObjectRect(node, camera, canvas.getBoundingClientRect());
    inspection.phase = 'presenting';
    (kind === 'resume' ? resumeBook : exhibit && exhibit.index > 1 ? exhibitDetail : workDetail).open({ origin: inspection.origin, exhibit });
  } }).to(camera.position, { x: pose.position.x, y: pose.position.y, z: pose.position.z, duration: time(.72), ease: 'power2.inOut' }, 0)
    .to(controls.target, { x: pose.target.x, y: pose.target.y, z: pose.target.z, duration: time(.72), ease: 'power2.inOut' }, 0);
}

function setProgress(percent, text) {
  startupReadiness.update('room', percent / 100, text);
}

function failure(error) {
  const message = error instanceof Error ? error.message : String(error);
  state.failed = true;
  resumeEntryLabels?.dispose(); resumeEntryLabels = null;
  state.loaded = false;
  if (room) room.visible = false;
  if (exteriorModel) exteriorModel.visible = false;
  if (controls) controls.enabled = false;
  sceneClock?.dispose();
  state.errors.push(message);
  const stageName = { room: '房间资源', gallery: '作品长廊', about: '关于我场景', warmup: '画面准备' }[startupReadiness.getState().current];
  startupReadiness.fail(`${stageName}未能加载完成，请重试。`);
  galleryTransition?.dispose(); aboutTransition?.dispose();
  worksGallery?.dispose(); aboutAtelier?.dispose();
  cubeIntro?.dispose();
  introLighting?.dispose();
  liveRoomSurfaces?.dispose();
  lighting?.dispose();
  roomPhysicalSurface?.dispose();
  exterior?.dispose();
  terminalTone?.dispose();
  terminalDock?.dispose();
  disposeOrphanWelcome();
  disposeLoadedRoom();
  if (room) room.visible = false;
  if (exteriorModel) exteriorModel.visible = false;
  loadingScreen.hidden = false; loadingScreen.inert = false; loadingScreen.dataset.phase = 'error';
  document.body.classList.add('intro-active'); document.body.classList.remove('intro-playing');
  retryButton.hidden = false; retryButton.disabled = false;
  enterButton.disabled = skipButton.disabled = true;
  console.error('Room preview:', error);
}

// Capture a loaded asset before resident replacement or shader decorators borrow
// its resources. The resident owns its own terminal; these are only source GLB resources.
function assetResourceDisposer(model) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  model.traverse(node => {
    if (!node.isMesh) return;
    geometries.add(node.geometry);
    for (const material of [].concat(node.material)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  let disposed = false;
  return () => {
    if (disposed) return; disposed = true;
    geometries.forEach(value => value.dispose()); materials.forEach(value => value.dispose()); textures.forEach(value => value.dispose());
  };
}
// Loading, terminal welcome and unfolding are silent even if a previous scene
// audio preference is restored. Only entered, ready scenes may create audio.
function canPlaySceneAudio() {
  return state.loaded && state.introComplete && !state.failed && !state.isMuted && !state.modal;
}
function sound(frequency = 480) {
  if (!canPlaySceneAudio()) return;
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
  if (ambientGain || !canPlaySceneAudio()) return;
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
  if (!canPlaySceneAudio()) return;
  startAmbient();
  if (!audioContext) return;
  const now = audioContext.currentTime;
  if (ambientGain) ambientGain.gain.setTargetAtTime(0.0001, now, 0.1);
  clearTimeout(ambientRestoreTimer);
  ambientRestoreTimer = setTimeout(() => {
    if (ambientGain && canPlaySceneAudio()) ambientGain.gain.setTargetAtTime(0.009, audioContext.currentTime, 0.2);
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
  if (ambientGain) ambientGain.gain.setTargetAtTime(canPlaySceneAudio() ? .009 : 0, audioContext.currentTime, .12);
}

function setupScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#10171c');
  scene.fog = new THREE.Fog('#10171c', 40, 85);
  camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, 0.1, 500);
  camera.position.set(11, 10.4, 18);
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
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
    cubeIntro?.dispose();
    galleryRequestId++; state.galleryRequested = false;
    galleryTransition?.cancel(); aboutTransition?.cancel();
    aboutRequestId++; state.aboutRequested = false;
    cameraTimeline?.kill();
    state.transitioning = false;
    roomEntry?.restore();
    state.introComplete = false;
    controls.enabled = false;
    if (ambientGain && audioContext) ambientGain.gain.setTargetAtTime(0, audioContext.currentTime, .15);
    document.querySelectorAll('.preview-ui').forEach((element) => { element.inert = true; });
    loadingScreen.hidden = false;
    loadingScreen.inert = false;
    failure(new Error('图形上下文中断，需要重新载入。'));
  });
}

// Fit to the visible room, retaining the reference camera direction on desktop
// and increasing distance on narrow screens rather than cropping the architecture.
function fitCamera(animate = false) {
  if (state.currentScene === 'about') { fitAbout(animate); return; }
  if (state.currentScene === 'gallery') { fitGallery(animate); return; }
  if (!bounds || !camera) return;
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize();
  const up = new THREE.Vector3().crossVectors(direction, right).normalize();
  const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const horizontalFill = innerWidth < 600 ? 0.84 : 0.82;
  const verticalFill = innerWidth < 600 ? 0.76 : 0.74;
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
  cameraTimeline?.kill(); cameraTimeline = null;
  gsap.killTweensOf([camera.position, controls.target]);
  controls.enableDamping = false;
  controls.update();
  if (animate) {
    clearHover();
    cameraResetting = true;
    controls.enabled = false;
    const timeline = cameraTimeline = gsap.timeline({ onComplete: () => {
      cameraTimeline = null;
      camera.position.copy(homePosition);
      controls.target.copy(homeTarget);
      controls.update();
      controls.enableDamping = true;
      cameraResetting = false;
      roomCameraGuard?.reset();
      controls.enabled = state.introComplete && !state.modal;
    } });
    timeline.to(camera.position, { x: homePosition.x, y: homePosition.y, z: homePosition.z, duration: time(1.1), ease: 'power3.inOut' }, 0)
      .to(controls.target, { x: homeTarget.x, y: homeTarget.y, z: homeTarget.z, duration: time(1.1), ease: 'power3.inOut' }, 0);
  } else {
    camera.position.copy(homePosition);
    controls.target.copy(homeTarget);
    controls.update();
    controls.enableDamping = true;
    cameraResetting = false;
    roomCameraGuard?.reset();
    controls.enabled = state.introComplete && !state.modal && !state.transitioning;
  }
}

async function loadRoom() {
  const attempt = ++loadAttempt;
  state.failed = false;
  enterButton.disabled = true;
  skipButton.disabled = true; retryButton.hidden = true; loadingScreen.dataset.phase = 'loading';
  setProgress(0, '正在载入房间模型…');
  const interfaceReady = Promise.all([
    resumeBook.ready,
    document.fonts.load('700 18px "Atelier Forge Display"', '创作空间作品关于联系'),
    // Hidden work-detail screenshots load when the article is opened. Waiting
    // on decode() for a lazy image here would deadlock the startup curtain.
    ...[...document.images].filter(image => image.loading !== 'lazy').map(image => image.decode()),
  ]).then(() => document.fonts.ready);
  // Attach a handler now; the awaited result below still propagates a failure.
  interfaceReady.catch(() => {});
  const roomTextureLoader = new KTX2Loader().setTranscoderPath('/basis/').setWorkerLimit(2).detectSupport(renderer);
  let roomDecoderDisposed = false;
  const releaseRoomDecoder = () => {
    if (roomDecoderDisposed) return;
    roomDecoderDisposed = true;
    if (roomTextureLoader.transcoderPending) roomTextureLoader.dispose();
  };
  const loader = new GLTFLoader().setKTX2Loader(roomTextureLoader);
  try {
    if (previewQA && new URLSearchParams(location.search).has('failRoom')) throw new Error('Local QA: simulated model-load failure');
    const gltf = await loader.loadAsync(materialRelease.roomModel, (event) => {
      if (!event.lengthComputable) return;
      const percent = event.loaded / event.total;
      setProgress(percent * 76, '正在载入房间模型…');
    });
    if (attempt !== loadAttempt) { assetResourceDisposer(gltf.scene)(); return; }
    room = gltf.scene;
    disposeLoadedRoom = assetResourceDisposer(room);
    if (materialRelease.physical) room.visible = false;
    room.name = 'OrbitalAtelier';
    // The V8 file shares atlas materials across room and exterior, but camera
    // framing and interactive IDs must remain scoped to the original room.
    exteriorModel = new THREE.Group();
    exteriorModel.name = 'OrbitalDockExterior';
    if (materialRelease.physical) exteriorModel.visible = false;
    const exteriorIds = new Set(['environment.orbital_dock', 'environment.warm_gallery']);
    const exteriorNodes = [];
    room.traverse((node) => { if (exteriorIds.has(node.userData.asset_id)) exteriorNodes.push(node); });
    if (exteriorNodes.length !== 2) throw new Error('The V8 model is missing its two exterior asset groups.');
    room.updateMatrixWorld(true);
    for (const node of exteriorNodes) exteriorModel.attach(node);
    // Rebind the Blender-authored device hardware before interaction bounds,
    // baked-lighting materials and animation capture their final hierarchy.
    roomEntryAttachments = createRoomEntryAttachments({ THREE, room });
    configureAboutBookEntry({ THREE, room });
    const welcomeResults = await Promise.allSettled([
      new GLTFLoader().setKTX2Loader(roomTextureLoader).loadAsync(materialRelease.terminalModel),
      // Welcome uses authored light in the existing WebGL background pass.
      Promise.resolve(null),
    ]);
    const welcomeFailure = welcomeResults.find(result => result.status === 'rejected');
    if (welcomeFailure) {
      if (welcomeResults[0].status === 'fulfilled') assetResourceDisposer(welcomeResults[0].value.scene)();
      if (welcomeResults[1].status === 'fulfilled') welcomeResults[1].value?.dispose();
      throw welcomeFailure.reason;
    }
    const welcomeGltf = welcomeResults[0].value, welcomeBackdrop = welcomeResults[1].value;
    const disposeWelcomeModel = assetResourceDisposer(welcomeGltf.scene);
    let welcomeOwnedByResident = false, backdropOwnedByIntro = false;
    disposeOrphanWelcome = () => {
      if (!welcomeOwnedByResident) disposeWelcomeModel();
      if (!backdropOwnedByIntro) { welcomeBackdrop?.dispose(); backdropOwnedByIntro = true; }
    };
    if (materialRelease.physical) terminalTone = createTerminalToneMapping({ THREE, model: welcomeGltf.scene });
    terminalDock = createResidentTerminal({ THREE, renderer, room, welcomeGltf, reducedMotion });
    welcomeOwnedByResident = true;
    // Register interaction bounds and snapshots from the actual final object,
    // before the intro borrows that same object for its welcome choreography.
    terminalDock.attachHome();
    terminalDock.setTheme(state.isDay, 0);
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
        if (material.transparent) {
          material.depthWrite = false;
          material.side = THREE.FrontSide;
          material.forceSinglePass = true;
        }
        for (const property of ['map', 'emissiveMap', 'normalMap', 'roughnessMap', 'metalnessMap']) {
          if (material[property]) { material[property].anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16); roomRuntimeMaps.add(material[property]); }
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
    const requiredRootIds = Object.keys(assetMeta).filter(id => id !== 'lighting.ceiling_warm' || materialRelease.roomRevision >= 19);
    if (requiredRootIds.some(id => !roots.has(id))) console.warn(`Expected ${requiredRootIds.length} logical roots; received ${roots.size}`);
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
    exteriorModel.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = node.receiveShadow = false;
      node.raycast = () => {};
      for (const material of [].concat(node.material)) {
        if (material.map) { material.map.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16); roomRuntimeMaps.add(material.map); }
      }
    });
    scene.add(exteriorModel);
    ground.position.y = new THREE.Box3().setFromObject(exteriorModel).min.y - 0.025;
    configureBakedScene();
    if (materialRelease.physical) {
      setProgress(76, '正在准备真实表面材质与反射…');
      roomPhysicalSurface = await createPhysicalSurface({ THREE, renderer, objects: [room, exteriorModel], loader: roomTextureLoader,
        profile: { family: 'room', directory: materialRelease.roomDirectory, ...materialRelease.radiance,
          slots: roomAtlasSlots, glass: { enabled: true } },
      });
    }
    setProgress(76, '正在载入日间灯光贴图…');
    lighting = await createDualLighting({
      THREE, renderer, objects: [room, exteriorModel], reducedMotion,
      profile: { revision: materialRelease.roomRevision, slots: [...roomAtlasSlots, 'window'],
        directory: materialRelease.roomDirectory, extension: 'ktx2', loader: roomTextureLoader,
        interiorNightReadability: materialRelease.physical ? 0 : 1,
        ...(materialRelease.physical ? { ...materialRelease.radiance, nightRadianceScale: materialRelease.roomNightRadianceScale, exteriorNightExposure: {}, dayMixUniform: roomPhysicalSurface.getDayMixUniform() } : {}) },
      onProgress: (completed, total) => setProgress(76 + completed / total * 18, `正在准备日夜灯光 · ${completed}/${total}`),
    });
    if (attempt !== loadAttempt) { lighting.dispose(); roomPhysicalSurface?.dispose(); terminalTone?.dispose(); disposeOrphanWelcome(); terminalDock?.dispose(); disposeLoadedRoom(); return; }
    // Live displays and the satellite factories each own a short-lived decoder.
    // Release this pool before they begin; intro gets its own pool afterwards.
    releaseRoomDecoder();
    liveRoomSurfaces = await createLiveRoomSurfaces({ THREE, renderer, room, reducedMotion });
    hoverClearance = createRoomHoverClearance({ THREE, room, components });
    exterior = createExteriorAtmosphere({ THREE, scene, ground, roomBounds: bounds, reducedMotion });
    const backdropReady = await exterior.loadBackdrop({
      dayUrl: '/media/scene-backdrops-v1/room-day.png',
      nightUrl: '/media/scene-backdrops-v1/room-night.png',
      latitudeOffsetDegrees: 12, groundFadeNear: 18, groundFadeFar: 40,
    });
    if (!backdropReady) throw new Error('Room background did not finish loading.');
    exterior.setWarmLights(warmGalleryManifest.warm_light_sources.map((lamp) => ({
      position: [lamp.position[0], lamp.position[2], -lamp.position[1]],
      color: lamp.color,
      scale: lamp.scale,
    })));
    // Match the approved daylight homepage before uncovering the live room.
    setTheme(true, 0, false);
    // Every opening starts in daylight, including previously shared QA links.
    // Only a completed entrance releases the automatic clock below.
    sceneClock = createSceneClock({ reducedMotion, startHour: 10,
      element: $('.scene-clock'), onDayMix: applySceneDayMix });
    createPortalButtons();
    resumeEntryLabels?.dispose();
    resumeEntryLabels = createResumeEntryLabels({ THREE, camera, onActivate: (kind, node) => {
      if (kind === 'about') enterAbout();
      else openInspection('resume', node);
    } });
    resumeEntryLabels.setTargets({ room: portals.get('about') });
    sceneCallout = createSceneCallout({ THREE, camera, onActivate: (kind) => {
      if (kind === 'return-room') returnToRoom();
      else if (kind?.startsWith('about:')) showModal(kind.slice(6));
      else if (kind?.startsWith('gallery:')) focusGalleryItem(Number(kind.split(':')[1]));
      else showModal(kind);
    } });
    defaultCalloutTarget = { object: portals.get('work'), label: '作品', action: '', kind: 'work', interactive: true };
    createStaticHitboxes();
    fitCamera();
    roomCameraGuard = createRoomCameraGuard({ THREE, room, camera, controls });
    renderer.shadowMap.needsUpdate = true;
    setProgress(96, '正在准备材质与灯光…');
    const compileRoomVisible = room.visible, compileExteriorVisible = exteriorModel.visible;
    room.visible = exteriorModel.visible = true;
    try {
      await warmSceneForStartup({ THREE, renderer, scene, camera, setDayMix: applySceneDayMix });
      startupReadiness.update('room', 1, '房间与终端资源已就绪');
      startupReadiness.update('gallery', 0, '正在载入作品长廊…');
      if (previewQA && new URLSearchParams(location.search).get('failStartup') === 'gallery') throw new Error('Local QA: simulated gallery preload failure');
      await ensureGallery(false, galleryRequestId, { onProgress: value => startupReadiness.update('gallery', value * .96, '正在准备长廊模型与昼夜材质…') });
      startupReadiness.update('gallery', 1, '作品长廊已就绪');
      startupReadiness.update('about', 0, '正在载入关于我场景…');
      if (previewQA && new URLSearchParams(location.search).get('failStartup') === 'about') throw new Error('Local QA: simulated About preload failure');
      await ensureAbout(aboutRequestId, { foreground: false, onProgress: value => startupReadiness.update('about', value * .96, '正在准备关于我的模型与昼夜材质…') });
      startupReadiness.update('about', 1, '关于我场景已就绪');
    }
    finally { room.visible = compileRoomVisible; exteriorModel.visible = compileExteriorVisible; }
    startupReadiness.update('warmup', .1, '正在准备字体与界面…');
    await interfaceReady;
    fitCamera();
    // Warm the normal day/night program above before installing the temporary
    // clean architectural bakes. Returning to it then uses the cached program.
    startupReadiness.update('warmup', .3, '正在准备房间展开动画…');
    const introTextureLoader = new KTX2Loader().setTranscoderPath('/basis/').setWorkerLimit(2).detectSupport(renderer);
    let cleanOpening;
    try {
      cleanOpening = await createIntroLighting({ THREE, renderer, room, loader: introTextureLoader,
        profile: { revision: materialRelease.roomRevision, directory: materialRelease.introDirectory,
          ...(materialRelease.physical ? materialRelease.radiance : {}) } });
    } finally { if (introTextureLoader.transcoderPending) introTextureLoader.dispose(); }
    if (attempt !== loadAttempt) { cleanOpening.dispose(); return; }
    introLighting = cleanOpening;
    releaseRoomDecoder();
    startupReadiness.update('warmup', .65, '正在预热终端展示画面…');
    sceneMotion = createSceneMotion({ components, snapshots, reducedMotion });
    roomEntry = createRoomEntry({ room, roots, snapshots, bounds, externalIds: ['folding_drawing_terminal'] });
    if (attempt !== loadAttempt) return;
    // The controller snapshots the intended final visibility before hiding the
    // model for welcome. It must not inherit the temporary RGBM loading guard.
    room.visible = exteriorModel.visible = true;
    cubeIntro = createCubeIntro({ scene, renderer, terminalDock, welcomeModel: welcomeGltf.scene, welcomeClips: welcomeGltf.animations, welcomeBackdrop, room, roomEntry, introLighting, exteriorModel, atmosphere: exterior, ground, contactShadow: groundContactShadow, camera, controls, bounds,
      element: loadingScreen, getEndPose: () => ({ position: homePosition, target: homeTarget }), reducedMotion,
      onStart: () => { state.entered = true; controls.enabled = false; setMuted(true); },
      onComplete: () => {
        gsap.to('.preview-ui', { opacity: 1, duration: reducedMotion ? .01 : .3, ease: 'power2.out' });
        completeRoomEntry();
      },
    });
    backdropOwnedByIntro = true;
    const roomWasVisible = room.visible, exteriorWasVisible = exteriorModel.visible;
    room.visible = exteriorModel.visible = true;
    try { await renderer.compileAsync(scene, camera); }
    finally { room.visible = roomWasVisible; exteriorModel.visible = exteriorWasVisible; }
    renderer.render(scene, camera);
    startupReadiness.update('warmup', .9, '正在完成画面准备…');
    await waitForStartupGpu(renderer);
    startupReadiness.update('warmup', 1, '全部场景已就绪');
    startupReadiness.finish();
    await new Promise(resolve => gsap.delayedCall(reducedMotion ? .01 : .42, resolve));
    state.loaded = true;
    cubeIntro.ready();
    if (import.meta.env.DEV && previewQA) {
      const inspectionParams = new URLSearchParams(location.search);
      if (inspectionParams.has('introAt')) cubeIntro.inspectAt(Number(inspectionParams.get('introAt')));
    }
  } catch (error) { failure(error); }
  finally { releaseRoomDecoder(); }
}

function completeRoomEntry() {
  introLighting?.dispose();
  roomCameraGuard?.reset();
  state.introComplete = true;
  controls.enabled = true;
  document.querySelectorAll('.preview-ui').forEach((element) => { element.inert = false; });
  renderer.shadowMap.needsUpdate = !state.baked;
  canvas.tabIndex = 0;
  canvas.focus({ preventScroll: true });
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
  // Navigation is bound to the actual room objects. The concept's single
  // projected callout replaces the three freestanding rectangular plaques.
  for (const spec of portalSpecs) {
    const anchor = components.get(spec.anchor);
    if (!anchor) continue;
    anchor.userData.portal = spec.kind;
    portals.set(spec.kind, anchor);
  }
}
function calloutFor(node) {
  if (satellite()) return satellite().callout(node);
  if (!node) return defaultCalloutTarget;
  if (calloutTargets.has(node)) return calloutTargets.get(node);
  let meta;
  for (let current = node; current && current !== room; current = current.parent) {
    if (assetMeta[current.userData.asset_id]) { meta = assetMeta[current.userData.asset_id]; break; }
  }
  const portal = portalSpecs.find((spec) => spec.kind === node.userData.portal);
  const target = { object: node, label: portal?.title || meta?.[0] || '房间物件',
    action: portal ? '点击物件查看' : '点击物件互动', kind: portal?.kind, interactive: false };
  calloutTargets.set(node, target);
  return target;
}
function updateNavigation() {
  document.querySelectorAll('.scene-accessibility [data-modal]').forEach((button) => {
    const active = button.dataset.modal === state.activeSection;
    button.dataset.active = String(active);
    if (active) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
    button.setAttribute('aria-expanded', String(button.dataset.modal === state.modal));
  });
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
    trackedHitboxes.bind(hitbox, target);
  }
}

function componentFor(node) {
  for (let current = node; current && current !== room; current = current.parent) {
    if (current.userData.asset_id) return current;
  }
  return null;
}
function pick(clientX, clientY) {
  if (!room || !state.introComplete || state.modal || cameraResetting || state.transitioning) return null;
  if (satellite()) return satellite().pick(clientX, clientY, camera, canvas.getBoundingClientRect());
  const rect = canvas.getBoundingClientRect();
  pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  trackedHitboxes.update();
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
  return Math.min(preferredHoverScaleFor(node), sceneMotion?.getHoverScaleLimit?.(node) ?? Infinity);
}
function preferredHoverScaleFor(node) {
  if (node.userData.asset_id === 'lighting.ceiling_warm') return 1.04;
  if (node.userData.asset_id?.startsWith('gallery.')) return 1.2;
  if (isMountedRoomPart(node)) return 1.12;
  // Keep the wall-mounted display still; smaller navigation props retain a
  // modest physical response while their individual parts stay interactive.
  if (node.userData.portal === 'work') return 1;
  if (node.userData.portal === 'about') return 1.08;
  if (node.userData.portal === 'contact') return 1.15;
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
  if (id === 'v8_desk_glow_lamp' || id === 'v8_reading_puck') return 1.5;
  if (id === 'v8_window_light_bar') return 1.2;
  if (id === 'robot_companion') return 1.3;
  return 1.8;
}
function animateHover(node, active) {
  if (state.currentScene === 'about') { aboutAtelier?.hover(node, active); return; }
  if (node.userData.asset_id?.startsWith('gallery.')) { worksGallery?.hover(node, active); return; }
  const snapshot = snapshots.get(node);
  if (!snapshot || !canHover(node)) return;
  const original = sceneMotion?.getInteractionPose(node, snapshot, active) ?? snapshot;
  gsap.killTweensOf(node.scale);
  gsap.killTweensOf(node.position);
  const factor = active ? hoverScaleFor(node) : 1;
  const pose = hoverClearance?.position(node, original, factor) ?? original.position;
  // Match translation/scale curves; elastic overshoot would sink the underside
  // through the desk or shelf even when the final enlarged pose was safe.
  const transition = { duration: time(active ? .5 : .3), ease: 'power3.out' };
  gsap.to(node.scale, { x: original.scale.x * factor, y: original.scale.y * factor, z: original.scale.z * factor, ...transition });
  gsap.to(node.position, { x: pose.x, y: pose.y, z: pose.z, ...transition });
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
  state.lastInteraction = { id, action: node.userData.portal === 'work' ? 'enter-gallery' : node.userData.portal === 'about' ? 'enter-about' : node.userData.portal ? 'open-panel' : 'animate', time: performance.now() };
  if (satellite()) {
    const result = satellite().activate(node); sound(540);
    if (result.returnToRoom) {
      state.lastInteraction.action = 'return-room';
      returnToRoom();
    } else if (result.station) focusGalleryItem(result.station);
    else if (result.panel) showModal(result.panel);
    return;
  }
  if (node.userData.portal) { showModal(node.userData.portal); return; }
  const original = snapshots.get(node);
  if (!original) return;
  sceneMotion?.hold(node);
  // The original piano press is rebound to the split keyboard and its controls.
  if (id === 'kinetic_three_petal_flower' || id.startsWith('flower_petal_')) {
    sceneMotion?.hold(roots.get('kinetic_three_petal_flower'), 1.8);
    const sequence = gsap.timeline();
    for (let index = 0; index < 3; index++) {
      const petal = components.get(`flower_petal_${index}`);
      const pose = petal && snapshots.get(petal);
      if (!pose) continue;
      gsap.killTweensOf(petal.rotation);
      sequence.to(petal.rotation, { z: pose.rotation.z + Math.PI / 9, duration: time(.5), ease: 'power2.out' }, time(index * .065))
        .to(petal.rotation, { z: pose.rotation.z, duration: time(.6), ease: 'power2.inOut' }, time(.75 + index * .065));
    }
    sound(620);
  } else if (id === 'ceramic_ring_speaker' || id === 'speaker_gimbal') {
    const gimbal = components.get('speaker_gimbal');
    const pose = gimbal && snapshots.get(gimbal);
    if (!pose) return;
    gsap.killTweensOf(gimbal.rotation);
    gsap.timeline().to(gimbal.rotation, { z: pose.rotation.z + .24, duration: time(.32), ease: 'power2.out' })
      .to(gimbal.rotation, { z: pose.rotation.z - .1, duration: time(.4), ease: 'sine.inOut' })
      .to(gimbal.rotation, { z: pose.rotation.z, duration: time(.5), ease: 'power2.out' });
    sound(330);
  } else if (id.startsWith('v5_') && node.userData.interaction === 'lift') {
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
  work: ['项目资料', '作品', '<p>项目名称、图像与过程说明待补充。</p>' + placeholderRows(['作品名称与封面', '项目简介与个人职责', '过程、成果与项目链接'])],
  about: ['个人资料', '关于我', '<p>个人介绍待补充。</p>' + placeholderRows(['姓名与头像', '简介与专业方向', '经历与技能'])],
  profile: ['档案工坊', '关于我', '<p>个人介绍待补充。</p>' + placeholderRows(['姓名与头像', '简介与专业方向', '个人经历'])],
  awards: ['奖项档案', '奖项与荣誉', '<p>玻璃罩内为场景占位雕塑，真实奖项资料待补充。</p>' + placeholderRows(['奖项名称', '获奖时间与颁发机构', '作品与获奖证明'])],
  skills: ['创作工具', '技能与方法', '<p>具体技能及项目经验待补充。</p>' + placeholderRows(['专业方向', '软件与工具', '技能说明与项目证据'])],
  contact: ['联系方式', '联系', '<p>邮箱与社交主页待补充。</p>' + placeholderRows(['电子邮箱', '社交主页', '其他联系方式'])],
};
function showModal(kind, workIndex = null) {
  if (!state.introComplete || state.transitioning || cameraResetting) return;
  if (kind === 'work' && workIndex === null) { enterGallery(); return; }
  if (kind === 'about') { enterAbout(); return; }
  if (kind === 'resume') { openInspection('resume', aboutAtelier?.components.get(RESUME_BOOK_ID)); return; }
  if (kind === 'work' && getGalleryExhibit(workIndex)) {
    openInspection('work', worksGallery?.components.get(galleryFocusId(workIndex)), getGalleryExhibit(workIndex));
    return;
  }
  aboutRequestId++; state.aboutRequested = false;
  galleryRequestId++;
  state.galleryRequested = false;
  galleryNavigation?.setState({ loading: false, error: null });
  clearHover();
  sound();
  if (!state.modal) lastFocused = document.activeElement;
  state.modal = kind;
  state.activeSection = state.currentScene === 'about' ? 'about' : kind;
  updateNavigation();
  state.activeAsset = `navigation.${kind}`;
  controls.enabled = false;
  $('.scene-accessibility').inert = true;
  $('.scene-controls').inert = true;
  $('#experience').inert = true;
  if ($('.gallery-nav')) $('.gallery-nav').inert = true;
  const [category, title, body] = workIndex === null ? content[kind] || content.about : [`日光长廊 · 展位 ${String(workIndex).padStart(2, '0')}`, `作品 ${String(workIndex).padStart(2, '0')}`, '<p>此处展品为场景占位，真实作品资料待补充。</p>' + placeholderRows(['作品名称与封面', '项目简介与个人职责', '过程、成果与项目链接'])];
  $('#modal-category').textContent = category;
  $('#modal-title').textContent = title;
  $('#modal-content').innerHTML = body;
  modal.dataset.kind = kind;
  modal.hidden = false;
  overlay.hidden = false;
  $('.modal-close-hint-desktop').innerHTML = `<kbd>Esc</kbd> 返回${state.currentScene === 'about' ? '工坊' : state.currentScene === 'gallery' ? '长廊' : '房间'}`;
  $('.modal-wrapper').scrollTop = 0;
  gsap.killTweensOf([modal, overlay]);
  gsap.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: time(0.5) });
  gsap.fromTo(modal, { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, duration: time(0.5), ease: 'back.out(2)', onComplete: () => $('.modal-exit-button').focus({ preventScroll: true }) });
}
function hideModal() {
  if (workDetail.isOpen()) { workDetail.close(); return; }
  if (exhibitDetail.isOpen()) { exhibitDetail.close(); return; }
  if (resumeBook.isOpen()) { resumeBook.close(); return; }
  if (inspection) { closeInspection(); return; }
  if (!state.modal) return;
  sound(380);
  gsap.killTweensOf([modal, overlay]);
  gsap.to(overlay, { opacity: 0, duration: time(0.5) });
  gsap.to(modal, { opacity: 0, scale: 0, duration: time(0.5), ease: 'back.in(2)', onComplete: () => {
    state.modal = null;
    updateNavigation();
    state.activeAsset = null;
    modal.hidden = true;
    overlay.hidden = true;
    controls.enabled = true;
    $('.scene-accessibility').inert = false;
    $('.scene-controls').inert = false;
    $('#experience').inert = false;
    if ($('.gallery-nav')) $('.gallery-nav').inert = false;
    const canRestoreFocus = lastFocused instanceof HTMLElement
      && lastFocused.isConnected
      && !lastFocused.matches(':disabled, [aria-disabled="true"]')
      && !lastFocused.closest('[hidden], [inert]')
      && lastFocused.getClientRects().length > 0
      && getComputedStyle(lastFocused).visibility === 'visible';
    const focusTarget = canRestoreFocus
      ? lastFocused
      : canvas;
    focusTarget?.focus({ preventScroll: true });
  } });
}
function setTheme(isDay, duration = time(1.5), playSound = true) {
  if (state.isDay === isDay) return;
  state.isDay = isDay;
  document.body.classList.toggle('day-theme', state.isDay);
  document.body.classList.toggle('night-theme', !state.isDay);
  document.querySelector('meta[name="theme-color"]').content = state.isDay ? '#e3e8e5' : '#10171c';
  const transition = { duration, ease: 'power2.inOut', overwrite: true };
  exterior?.setTheme(state.isDay, duration);
  lighting?.setTheme(state.isDay, duration);
  liveRoomSurfaces?.setTheme(state.isDay, duration);
  terminalDock?.setTheme(state.isDay, duration);
  worksGallery?.setTheme(state.isDay, duration);
  aboutAtelier?.setTheme(state.isDay, duration);
  if (state.baked) {
    if (groundContactShadow) gsap.to(groundContactShadow.material, { opacity: state.isDay ? 0.55 : 1, ...transition });
  } else {
    gsap.to(scene, { environmentIntensity: state.isDay ? 0.95 : 0.68, ...transition });
    gsap.to(keyLight, { intensity: state.isDay ? 2.8 : 1.65, ...transition });
    gsap.to(ambient, { intensity: state.isDay ? 0.8 : 0.3, ...transition });
    warmLights.forEach((light) => gsap.to(light, { intensity: state.isDay ? 2.5 : 3.6, ...transition }));
  }
  if (playSound) sound(720);
}

// Scene-time samples write to existing shader uniforms; there is no per-frame
// GSAP allocation, texture upload, shader recompilation, or additional light.
function applySceneDayMix(value) {
  const mix = THREE.MathUtils.clamp(value, 0, 1);
  state.isDay = mix >= .5; // Internal snapshot only; no visible threshold switch.
  sceneTimeTheme.apply(mix);
  exterior?.setDayMix(mix);
  lighting?.setDayMix(mix);
  liveRoomSurfaces?.setDayMix(mix);
  terminalDock?.setDayMix(mix);
  worksGallery?.setDayMix(mix);
  aboutAtelier?.setDayMix(mix);
  if (state.baked) {
    if (groundContactShadow) groundContactShadow.material.opacity = THREE.MathUtils.lerp(1, .55, mix);
  } else {
    scene.environmentIntensity = THREE.MathUtils.lerp(.68, .95, mix);
    keyLight.intensity = THREE.MathUtils.lerp(1.65, 2.8, mix);
    ambient.intensity = THREE.MathUtils.lerp(.3, .8, mix);
    warmLights.forEach(light => { light.intensity = THREE.MathUtils.lerp(3.6, 2.5, mix); });
  }
}

function setupGalleryNavigation() {
  galleryNavigation = createGalleryNavigation({ onBack: () => returnToRoom(), onRetry: () => requestedSceneTitle === '档案工坊' ? enterAbout() : enterGallery(), onSelect: focusGalleryItem });
  galleryTransition = createGalleryTransition({ renderer, camera, controls, reducedMotion });
  aboutTransition = createGalleryTransition({ renderer, camera, controls, reducedMotion });
  activeSceneTransition = galleryTransition;
  const about = $('.scene-accessibility [data-modal="about"]');
  about.removeAttribute('aria-haspopup');
  about.setAttribute('aria-label', '关于我，进入档案工坊');
  const work = $('.scene-accessibility [data-modal="work"]');
  work.removeAttribute('aria-haspopup');
  work.setAttribute('aria-label', '我的作品，进入日光长廊');
}

async function ensureGallery(foreground = true, requestId = galleryRequestId, { onProgress = () => {} } = {}) {
  if (foreground) galleryNavigation.setState({ loading: true, error: null, progress: worksGallery ? 1 : null, sceneTitle: '日光长廊' });
  if (worksGallery) {
    if (foreground) galleryNavigation.setState({ loading: false });
    return worksGallery;
  }
  if (!galleryPromise) {
    state.galleryLoading = true;
    galleryPromise = (async () => {
      const gallery = await createWorksGallery({ renderer, isDay: state.isDay, reducedMotion, materialRelease,
        backdrop: { dayUrl: '/media/scene-backdrops-v1/gallery-day.png',
          nightUrl: '/media/scene-backdrops-v1/gallery-night.png',
          yawDegrees: 31.4, forwardDetailFactor: 4, latitudeDetailFactor: 1.7,
          latitudeOffsetDegrees: 8, groundFadeNear: 18, groundFadeFar: 36 },
        onProgress: (progress) => { onProgress(progress); if (state.galleryRequested) galleryNavigation.setState({ loading: true, progress }); },
      });
      try {
        const previewCamera = camera.clone();
        const pose = gallery.pose(camera.aspect, camera.fov);
        previewCamera.position.copy(pose.position); previewCamera.lookAt(pose.target);
        if (!gallery.getState().environment.backdrop.loaded) throw new Error('Gallery background did not finish loading.');
        await warmSceneForStartup({ THREE, renderer, scene: gallery.scene, camera: previewCamera, setDayMix: gallery.setDayMix });
        gallery.setDayMix(sceneClock?.dayMix ?? (state.isDay ? 1 : 0));
        await galleryTransition.prepare({ sourceScene: scene, destinationScene: gallery.scene, destinationModel: gallery.model, destinationEnvironment: gallery.environment, destination: pose });
        worksGallery = gallery;
        return gallery;
      } catch (error) { gallery.dispose(); throw error; }
    })().finally(() => { state.galleryLoading = false; galleryPromise = null; });
  }
  try {
    const gallery = await galleryPromise;
    if (foreground && requestId === galleryRequestId && state.galleryRequested) galleryNavigation.setState({ loading: false, progress: 1 });
    return gallery;
  } catch (error) {
    if (foreground && requestId === galleryRequestId && state.galleryRequested) {
      galleryNavigation.setState({ loading: false, error: '长廊载入失败，房间仍可继续浏览。', busy: false });
      state.errors.push(`Gallery load: ${error.message}`);
    }
    throw error;
  }
}

async function ensureAbout(requestId = aboutRequestId, { foreground = true, onProgress = () => {} } = {}) {
  if (foreground) galleryNavigation.setState({ loading: true, error: null, progress: aboutAtelier ? 1 : null, sceneTitle: '档案工坊' });
  if (!aboutAtelier && !aboutPromise) {
    state.aboutLoading = true;
    aboutPromise = (async () => {
      const atelier = await createAboutAtelier({ renderer, reducedMotion, nightLighting: true,
        onProgress: progress => { onProgress(progress); if (state.aboutRequested) galleryNavigation.setState({ loading: true, progress }); },
      });
      try {
        const pose = atelier.pose(camera.aspect, camera.fov), previewCamera = camera.clone();
        previewCamera.position.copy(pose.position); previewCamera.lookAt(pose.target);
        if (!atelier.getState().lighting.night.ready) throw new Error('About night lighting did not finish loading.');
        atelier.setDayMix(sceneClock?.dayMix ?? (state.isDay ? 1 : 0));
        await warmSceneForStartup({ THREE, renderer, scene: atelier.scene, camera: previewCamera, setDayMix: atelier.setDayMix });
        await aboutTransition.prepare({ sourceScene: scene, destinationScene: atelier.scene,
          destinationModel: atelier.model, destinationEnvironment: atelier.environment, destination: pose,
          offset: new THREE.Vector3(-34, ground.position.y - atelier.floorY, 1.5) });
        aboutAtelier = atelier;
        resumeEntryLabels?.setTargets({ about: atelier.components.get(RESUME_BOOK_ID) });
        return atelier;
      } catch (error) { atelier.dispose(); throw error; }
    })().finally(() => { state.aboutLoading = false; aboutPromise = null; });
  }
  try {
    const atelier = aboutAtelier ?? await aboutPromise;
    if (foreground && requestId === aboutRequestId && state.aboutRequested) galleryNavigation.setState({ loading: false, progress: 1 });
    return atelier;
  } catch (error) {
    if (foreground && requestId === aboutRequestId && state.aboutRequested) {
      galleryNavigation.setState({ loading: false, error: '档案工坊载入失败，可重试或继续浏览房间。', busy: false });
      state.errors.push(`Atelier load: ${error.message}`);
    }
    throw error;
  }
}

function applySceneLimits() {
  const gallery = state.currentScene === 'gallery', about = state.currentScene === 'about';
  const pose = satellite()?.pose(camera.aspect, camera.fov);
  controls.enablePan = !about;
  controls.minPan.set(...(about ? [-1.8, .8, -1.3] : gallery ? [-8.3, .3, -4] : [-3, -1, -4]));
  controls.maxPan.set(...(about ? [1.8, 3.2, 1.5] : gallery ? [7.3, 5, 6] : [2, 8, 8]));
  controls.minDistance = about ? pose.minDistance : gallery ? 10 : 5;
  controls.maxDistance = pose?.maxDistance ?? savedRoomPose?.maxDistance ?? 45;
  controls.minPolarAngle = about ? .42 : gallery ? .28 : 0;
  controls.maxPolarAngle = about ? 1.42 : gallery ? 1.43 : Math.PI / 2;
  controls.minAzimuthAngle = about ? -.3 : gallery ? -.55 : 0;
  controls.maxAzimuthAngle = about ? 1.08 : gallery ? .95 : Math.PI / 2;
}

function setTravelBusy(busy) {
  cameraResetting = busy;
  controls.enabled = !busy && !state.modal && state.introComplete;
  $('.scene-accessibility').inert = busy || Boolean(state.modal);
  $('.scene-controls').inert = busy || Boolean(state.modal);
  galleryNavigation.setState({ busy });
  if (busy) {
    clearHover();
    activePointers.clear(); pointerDown = pendingPointer = null;
    dragging = multiTouch = false;
    cameraTimeline?.kill(); cameraTimeline = null;
    gsap.killTweensOf([camera.position, controls.target]);
    // Clearing damping applies its entire residual step. Restore the visible
    // pose afterwards so a click during a drag cannot jump the camera.
    const position = camera.position.clone(), target = controls.target.clone();
    controls.enableDamping = false; controls.update();
    camera.position.copy(position); controls.target.copy(target);
    camera.lookAt(target); camera.updateMatrixWorld(true);
  } else {
    controls.update(); controls.enableDamping = true;
    roomCameraGuard?.reset();
  }
}

function travelToScene(destinationScene, destination) {
  state.transitioning = true;
  setTravelBusy(true);
  const returning = destinationScene === 'room';
  const targetKind = returning ? state.currentScene : destinationScene;
  const targetScene = satellite(targetKind);
  activeSceneTransition = targetKind === 'about' ? aboutTransition : galleryTransition;
  let finalPose = destination, aspect = NaN;
  const initialAspect = destination.aspect ?? camera.aspect;
  const resolveDestination = () => {
    if (aspect !== camera.aspect) {
      aspect = camera.aspect;
      if (returning) {
        const factor = Math.max(1, initialAspect / aspect);
        finalPose = { ...destination, target: destination.target.clone(),
          position: destination.position.clone().sub(destination.target).multiplyScalar(factor).add(destination.target),
          maxDistance: Math.max(destination.maxDistance ?? 45, destination.position.distanceTo(destination.target) * factor * 1.3) };
      } else finalPose = targetScene.pose(aspect, camera.fov);
    }
    return finalPose;
  };
  activeSceneTransition.run({ destination, resolveDestination, returning,
    sourceScene: returning ? targetScene.scene : scene,
    destinationScene: returning ? scene : targetScene.scene,
    onHandoff: () => {
      state.currentScene = destinationScene;
      applySceneLimits();
      controls.maxDistance = finalPose.maxDistance ?? controls.maxDistance;
      state.activeSection = targetKind === 'about' ? 'about' : 'work'; updateNavigation();
      document.body.classList.toggle('in-works-gallery', destinationScene === 'gallery');
      document.body.classList.toggle('in-about-atelier', destinationScene === 'about');
      galleryNavigation.setState({ active: destinationScene === 'gallery', loading: false, error: null });
      $('#experience').setAttribute('aria-label', destinationScene === 'about' ? '可交互的关于我档案工坊' : destinationScene === 'gallery' ? '可交互的作品长廊' : '可交互的三维房间');
    },
    onComplete: () => {
      state.transitioning = false;
      state.galleryRequested = state.aboutRequested = false;
      setTravelBusy(false);
      canvas.focus({ preventScroll: true });
      const next = nextSceneAfterReturn; nextSceneAfterReturn = null;
      if (returning && next) { if (next === 'about') enterAbout(); else enterGallery(); }
    },
  });
}

async function enterGallery() {
  if (!state.introComplete || state.transitioning || state.modal || state.galleryRequested || cameraResetting) return;
  if (state.currentScene === 'gallery') { fitGallery(true); return; }
  if (state.currentScene === 'about') { returnToRoom('gallery'); return; }
  aboutRequestId++; state.aboutRequested = false; requestedSceneTitle = '日光长廊';
  const requestId = ++galleryRequestId;
  state.galleryRequested = true;
  sound(560);
  try {
    await ensureGallery(true, requestId);
    if (requestId !== galleryRequestId || !state.galleryRequested || state.failed || state.modal || state.transitioning) return;
    savedRoomPose = { position: camera.position.clone(), target: controls.target.clone(), maxDistance: controls.maxDistance, aspect: camera.aspect };
    travelToScene('gallery', worksGallery.pose(camera.aspect, camera.fov));
  } catch { if (requestId === galleryRequestId) state.galleryRequested = false; }
}

async function enterAbout() {
  if (!state.introComplete || state.transitioning || state.modal || state.aboutRequested || cameraResetting) return;
  if (state.currentScene === 'about') { fitAbout(true); return; }
  if (state.currentScene === 'gallery') { returnToRoom('about'); return; }
  galleryRequestId++; state.galleryRequested = false; requestedSceneTitle = '档案工坊';
  const requestId = ++aboutRequestId;
  state.aboutRequested = true;
  sound(540);
  try {
    await ensureAbout(requestId);
    if (requestId !== aboutRequestId || !state.aboutRequested || state.failed || state.modal || state.transitioning) return;
    savedRoomPose = { position: camera.position.clone(), target: controls.target.clone(), maxDistance: controls.maxDistance, aspect: camera.aspect };
    travelToScene('about', aboutAtelier.pose(camera.aspect, camera.fov));
  } catch { if (requestId === aboutRequestId) state.aboutRequested = false; }
}

function returnToRoom(next = null) {
  if (state.transitioning || state.modal || cameraResetting) return;
  galleryRequestId++; aboutRequestId++;
  state.galleryRequested = state.aboutRequested = false;
  galleryNavigation.setState({ loading: false, error: null });
  if (!satellite()) return;
  nextSceneAfterReturn = next;
  sound(380);
  travelToScene('room', savedRoomPose ?? { position: homePosition.clone(), target: homeTarget.clone() });
}

function fitAbout(animate = false) {
  if (!aboutAtelier || state.transitioning) return;
  const pose = aboutAtelier.pose(camera.aspect, camera.fov);
  controls.maxDistance = pose.maxDistance;
  controls.minDistance = pose.minDistance;
  moveGalleryCamera(pose, animate);
}

function moveGalleryCamera(pose, animate = true, onComplete = () => {}) {
  setTravelBusy(true);
  const finish = () => {
    camera.position.copy(pose.position); controls.target.copy(pose.target);
    setTravelBusy(false); onComplete();
  };
  if (!animate) { finish(); return; }
  cameraTimeline = gsap.timeline({ onComplete: () => { cameraTimeline = null; finish(); } })
    .to(camera.position, { x: pose.position.x, y: pose.position.y, z: pose.position.z, duration: time(.9), ease: 'power3.inOut' }, 0)
    .to(controls.target, { x: pose.target.x, y: pose.target.y, z: pose.target.z, duration: time(.9), ease: 'power3.inOut' }, 0);
}

function fitGallery(animate = false) {
  if (!worksGallery || state.transitioning) return;
  const pose = worksGallery.pose(camera.aspect, camera.fov);
  controls.maxDistance = pose.maxDistance;
  moveGalleryCamera(pose, animate);
}

function focusGalleryItem(index) {
  if (state.currentScene !== 'gallery' || state.transitioning || cameraResetting || state.modal || !Number.isInteger(index) || index < 1 || index > 6) return;
  galleryNavigation.setState({ selected: index });
  const exhibit = getGalleryExhibit(index);
  if (exhibit) { openInspection('work', worksGallery.components.get(galleryFocusId(index)), exhibit); return; }
  const x = [-4.8, -2.7, -.6, 1.5, 3.6, 5.7][index - 1];
  const target = new THREE.Vector3(x, 1.8, -1.6);
  const distance = Math.max(10, 4.5 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / camera.aspect);
  const offset = new THREE.Vector3(.15, .29, 1).normalize().multiplyScalar(distance);
  moveGalleryCamera({ target, position: target.clone().add(offset) }, true, () => showModal('work', index));
}

function events() {
  retryButton.addEventListener('click', () => {
    if (previewQA) { const url = new URL(location.href); url.searchParams.delete('failRoom'); url.searchParams.delete('failStartup'); history.replaceState(null, '', url); }
    location.reload();
  });
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-modal]');
    if (button) showModal(button.dataset.modal);
    if (event.target.closest('[data-action="reset"]') && !state.transitioning) { sound(); fitCamera(true); }

  });
  $('.modal-exit-button').addEventListener('click', hideModal);
  overlay.addEventListener('click', hideModal);
  updateNavigation();
  $('.mute-toggle-button').addEventListener('click', () => setMuted(!state.isMuted));
  window.addEventListener('keydown', (event) => {
    if (inspection || workDetail.isOpen() || exhibitDetail.isOpen() || resumeBook.isOpen()) {
      if (event.key === 'Escape') { event.preventDefault(); hideModal(); }
      return;
    }
    if (event.key === 'Escape') { if (state.modal) hideModal(); else if (state.currentScene !== 'room' || state.galleryRequested || state.aboutRequested) returnToRoom(); }
    if (state.modal && event.key === 'Tab') {
      const focusable = [...modal.querySelectorAll('button, a[href], [tabindex="0"]')];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  canvas.addEventListener('pointerdown', (event) => {
    if (!state.introComplete || state.transitioning || cameraResetting) return;
    activePointers.add(event.pointerId);
    multiTouch ||= activePointers.size > 1;
    pointerDown = { x: event.clientX, y: event.clientY, id: event.pointerId, button: event.button };
    dragging = false;
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!state.introComplete) return;
    if (pointerDown && (Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 6 || multiTouch)) { dragging = true; clearHover(); }
    pendingPointer = { clientX: event.clientX, clientY: event.clientY, pointerType: event.pointerType };
  });
  canvas.addEventListener('pointerup', (event) => {
    if (!state.introComplete) return;
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
  let compactViewport = innerWidth < 600;
  window.addEventListener('resize', () => {
    const previousAspect = camera.aspect;
    const nextCompactViewport = innerWidth < 600;
    const crossedCompactBoundary = nextCompactViewport !== compactViewport;
    compactViewport = nextCompactViewport;
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    galleryTransition?.resize(); aboutTransition?.resize();
    if (inspection) inspection.backgroundReady = false;
    if (cubeIntro?.active) { fitCamera(false); cubeIntro.resize(); return; }
    if (!inspection && !state.modal && !state.transitioning && (crossedCompactBoundary || Math.abs(previousAspect - camera.aspect) > 0.15 || !state.entered)) fitCamera(false);
  });
}
function render(timestamp = performance.now()) {
  frame = requestAnimationFrame(render);
  if (state.failed) return;
  // GPU uploads and offscreen preparation own the renderer until the loader
  // releases the homepage. Avoid concurrent full-scene work during startup.
  if (!state.loaded) { previousFrameTime = 0; return; }
  if (!state.introComplete || state.modal || state.transitioning || cameraResetting) resumeEntryLabels?.update({ scene: state.currentScene, visible: false });
  if (document.hidden) { sceneClock?.update(0, { enabled: false }); previousFrameTime = 0; return; }
  // The camera and scene clock are locked while reading. Retain the last GPU
  // frame so the browser compositor can spend its budget on paper deformation
  // or video instead of redrawing the same heavy 3D scene behind the dialog.
  if (inspection?.phase === 'presenting' && inspection.backgroundReady) { previousFrameTime = timestamp; return; }
  const delta = previousFrameTime ? (timestamp - previousFrameTime) / 1000 : 0;
  if (import.meta.env.DEV && previousFrameTime && (state.introComplete || cubeIntro?.active)) {
    frameDurations[frameDurationIndex] = timestamp - previousFrameTime;
    frameDurationIndex = (frameDurationIndex + 1) % frameDurations.length;
    frameDurationCount = Math.min(frameDurationCount + 1, frameDurations.length);
  }
  previousFrameTime = timestamp;
  sceneClock?.update(delta, { enabled: state.introComplete && !state.modal && !state.transitioning && !state.galleryLoading && !state.aboutLoading });
  liveRoomSurfaces?.update(delta, {
    enabled: state.currentScene === 'room' && state.introComplete && !state.modal && !state.transitioning,
    camera,
  });
  if (cubeIntro?.active) {
    cubeIntro.update(); exterior?.update(timestamp * .001, camera);
    renderer.render(scene, camera); return;
  }
  if (state.transitioning) {
    sceneCallout?.update({ visible: false });
    activeSceneTransition.render(delta, (sourceCamera, destinationCamera) => {
      const roomView = state.currentScene === 'room' ? sourceCamera : destinationCamera;
      const galleryView = state.currentScene !== 'room' ? sourceCamera : destinationCamera;
      liveRoomSurfaces?.update(delta, { enabled: true, camera: roomView });
      sceneMotion?.update(delta, { enabled: false, hovered: null, sceneHour: sceneClock?.hour ?? 10 });
      exterior?.update(timestamp * .001, roomView);
      (activeSceneTransition === aboutTransition ? aboutAtelier : worksGallery)?.update(timestamp * .001, galleryView);
    });
    if (import.meta.env.DEV) {
      const travel = activeSceneTransition.getState();
      if (!travel.active) delete canvas.dataset.travelPhase;
      else canvas.dataset.travelPhase = travel.progress < .38 ? 'departing' : travel.progress < .62 ? 'tracking' : 'arriving';
    }
    return;
  }
  if (satellite()) satellite().update(timestamp * .001, camera);
  else exterior?.update(timestamp * .001, camera);
  if (cameraResetting) camera.lookAt(controls.target); else controls.update();
  // Keep the template's drag/pan/zoom controls, but prevent low-angle panning
  // from taking the viewer below the physical exhibition floor.
  const minimumCameraY = satellite() ? satellite().floorY + .6 : ground.position.y + .25;
  if (!state.transitioning && camera.position.y < minimumCameraY) {
    const raise = minimumCameraY - camera.position.y;
    camera.position.y += raise;
    controls.target.y += raise;
    camera.lookAt(controls.target);
  }
  if (pendingPointer) { const event = pendingPointer; pendingPointer = null; updateHover(event); }
  sceneMotion?.update(delta, { enabled: state.currentScene === 'room' && state.introComplete && !state.modal && !dragging && !cameraResetting, hovered: currentHovered, sceneHour: sceneClock?.hour ?? 10 });
  roomCameraGuard?.update({ enabled: state.currentScene === 'room' && state.introComplete && !state.transitioning && !cameraResetting && !state.modal });
  if (sceneCallout) {
    sceneCallout.setTarget(resumeEntryLabels?.ownsObject(currentHovered) ? null : calloutFor(currentHovered));
    sceneCallout.update({ visible: state.introComplete && !state.modal && !dragging && !cameraResetting });
  }
  resumeEntryLabels?.update({ scene: state.currentScene, visible: state.introComplete && !state.modal && !dragging && !cameraResetting });
  renderer.render(satellite()?.scene ?? scene, camera);
  if (inspection?.phase === 'presenting') inspection.backgroundReady = true;
}
function performanceSummary() {
  const samples = Array.from(frameDurations.subarray(0, frameDurationCount)).sort((a, b) => a - b);
  if (!samples.length) return { samples: 0 };
  const p50 = samples[Math.floor(samples.length * 0.5)], p95 = samples[Math.min(samples.length - 1, Math.floor(samples.length * 0.95))];
  return { samples: samples.length, rafP50Ms: p50, rafP95Ms: p95, rafMedianFps: 1000 / p50, devicePixelRatio, renderPixelRatio: renderer.getPixelRatio() };
}

Object.defineProperty(window, '__roomPreview', { value: Object.freeze({
  getState: () => ({ resumeEntryLabel: resumeEntryLabels?.getState() ?? null, inspection: inspection ? { kind: inspection.kind, exhibitIndex: inspection.exhibitIndex, phase: inspection.phase, origin: inspection.origin, savedPosition: inspection.saved.position.toArray(), savedTarget: inspection.saved.target.toArray() } : null, workDetail: workDetail.getState?.(), exhibitDetail: exhibitDetail.getState(), resumeBook: resumeBook.getState(), startup: { ...startupReadiness.getState(), galleryPrepared: galleryTransition?.getState().prepared ?? false, aboutPrepared: aboutTransition?.getState().prepared ?? false, programs: renderer?.info.programs?.length ?? 0, assetRequests: previewQA ? performance.getEntriesByType('resource').filter(entry => /\/(models|textures|media|fonts)\//.test(entry.name)).length : null }, materialRelease: { ...materialRelease, status: state.failed ? "failed" : state.loaded ? "ready" : "loading" }, physicalSurface: roomPhysicalSurface?.getState() ?? null, terminalTone: terminalTone?.getState() ?? null, currentScene: state.currentScene, transitioning: state.transitioning, transition: activeSceneTransition?.getState() ?? null, aboutLoading: state.aboutLoading, about: aboutAtelier?.getState() ?? null, galleryLoading: state.galleryLoading, gallery: worksGallery?.getState() ?? null, loaded: state.loaded, entered: state.entered, failed: state.failed, day: state.isDay, sceneClock: sceneClock?.getState() ?? null, sceneTimeTheme: sceneTimeTheme.getState(), muted: state.isMuted, audio: { allowed: canPlaySceneAudio(), contextCreated: Boolean(audioContext), ambientSources: ambientSources.length }, modal: state.modal, activeAsset: state.activeAsset, hovered: currentHovered ? { id: currentHovered.userData.asset_id, scale: currentHovered.scale.toArray(), factor: hoverScaleFor(currentHovered) } : null, errors: [...state.errors], assetCount: roots.size, componentCount: components.size, rootIds: [...roots.keys()], componentIds: [...components.keys()], camera: camera?.position.toArray(), target: controls?.target.toArray(), drawCalls: renderer?.info.render.calls, triangles: renderer?.info.render.triangles, renderer: renderer?.getPixelRatio(), controlsEnabled: controls?.enabled, cameraLimits: { minDistance: controls?.minDistance, maxDistance: controls?.maxDistance }, introComplete: state.introComplete, baked: state.baked, roomTextures: { maps: roomRuntimeMaps.size, compressed: [...roomRuntimeMaps].filter(map => map.isCompressedTexture).length, formats: [...new Set([...roomRuntimeMaps].map(map => map.format))] }, lightingRevision: lighting?.getState().revision ?? materialRelease.roomRevision, lighting: lighting?.getState() ?? null, uiRevision: 11, homepage: { mode: `terminal-showcase-v${materialRelease.terminalRevision}`, modelUrl: materialRelease.terminalModel, characterIntegrated: false, backdrop: 'silver-current-v2' }, intro: cubeIntro?.getState() ?? null, residentTerminal: terminalDock?.getState() ?? null, motion: sceneMotion?.getState() ?? null, liveSurfaces: liveRoomSurfaces?.getState() ?? null, cameraGuard: roomCameraGuard?.getState() ?? null, entry: roomEntry?.getState() ?? null, entryAttachments: roomEntryAttachments?.getState() ?? null, activeSection: state.activeSection, callout: sceneCallout?.getState() ?? null, portalCount: portals.size, hitboxCount: hitboxes.length, lastInteraction: state.lastInteraction, performance: performanceSummary() }),
  get transitionActive() { return state.transitioning; }, get gallery() { return worksGallery; }, get about() { return aboutAtelier; }, get activeScene() { return satellite()?.scene ?? scene; }, get scene() { return scene; }, get camera() { return camera; }, get room() { return room; }, get renderer() { return renderer; }, get portals() { return new Map(portals); },
  get roots() { return new Map(roots); }, get components() { return new Map(components); },
}) });

// Opt-in local QA exposes only this preview's diagnostics through the DOM.
// It is absent from production builds and from ordinary visits.
if (import.meta.env.DEV && new URLSearchParams(location.search).has('qa')) {
  const output = document.createElement('script');
  output.type = 'application/json'; output.id = 'preview-diagnostics'; document.body.append(output);
  setInterval(() => {
    const projected = {};
    const activeNodes = satellite()?.components ?? new Map([...roots, ...[...portals.values()].map(node => [node.userData.asset_id, node])]);
    for (const [id, node] of activeNodes ?? []) {
      const center = new THREE.Box3().setFromObject(node).getCenter(new THREE.Vector3());
      center.project(camera);
      projected[id] = [Math.round((center.x + 1) * innerWidth / 2), Math.round((1 - center.y) * innerHeight / 2)];
    }
    const graphics = renderer.getContext();
    output.textContent = JSON.stringify({ ...window.__roomPreview.getState(), viewport: [innerWidth, innerHeight], projected,
      textureMemory: renderer.info.memory, compressedFormats: Array.from(graphics.getParameter(graphics.COMPRESSED_TEXTURE_FORMATS)) });
  }, 1500);
}

try { setupScene(); setupGalleryNavigation(); events(); render(); loadRoom(); }
catch (error) { failure(error); }
