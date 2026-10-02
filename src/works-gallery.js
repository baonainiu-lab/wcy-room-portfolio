import * as THREE from 'three';
import gsap from 'gsap';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createDualLighting } from './dual-lighting.js';
import { createExteriorAtmosphere } from './exterior-atmosphere.js';
import { createGalleryFloorFinish } from './gallery-floor-finish.js';
import { createGalleryGlass } from './gallery-glass.js';
import { createGalleryFraming } from './gallery-framing.js';
import { createPhysicalSurface } from './physical-surface.js';
import { resolveMaterialRelease } from './material-release.js';
import { createGalleryExhibitCover, FIRST_GALLERY_WORK } from './gallery-exhibit-cover.js';
import { getGalleryExhibit } from './gallery-catalog.js';

const stationPattern = /^gallery\.work\.(\d{2})$/;
const returnPortalId = 'gallery.architecture.portal';
const names = [
  ['gallery.album.', '陈列画册'], ['gallery.archive.drawer.', '归档抽屉'],
  ['gallery.archive.wheel.', '推车轮'], ['gallery.archive.cart', '归档推车'],
  ['gallery.sculpture.ring', '轨道摆件'], ['gallery.lamp.', '阅读灯'],
  ['gallery.library.', '书册'], ['gallery.planter.', '绿植'],
  ['gallery.lantern.', '暖光灯笼'], ['gallery.tool.', '创作工具'],
  ['gallery.cup', '陶瓷杯'], ['gallery.bench', '阅读长椅'], ['gallery.table.', '画册陈列桌'],
];

/** Independently renderable gallery; transition clones share its resources. */
export async function createWorksGallery({ renderer, isDay, reducedMotion, onProgress = () => {}, backdrop, materialRelease = resolveMaterialRelease() }) {
  // Room/terminal physical materials do not imply a different gallery finish.
  // V5 must retain its complete sRGB bake and original reflection pipeline.
  const physicalGallery = materialRelease.galleryPhysical ?? materialRelease.physical;
  const scene = new THREE.Scene();
  const textureLoader = new KTX2Loader().setTranscoderPath('/basis/').setWorkerLimit(2).detectSupport(renderer);
  let decoderReleased = false;
  const releaseDecoder = () => {
    if (decoderReleased) return;
    decoderReleased = true;
    // KTX2Loader.dispose decrements Three's global active-loader counter on
    // every call, including before init. Release only an initialized decoder,
    // once, whether loading succeeds or an early/late failure is cleaned up.
    if (textureLoader.transcoderPending) textureLoader.dispose();
  };
  let gltf;
  try { gltf = await new GLTFLoader().setKTX2Loader(textureLoader).loadAsync(materialRelease.galleryModel, (event) => {
    if (event.lengthComputable) onProgress(event.loaded / event.total * .72);
  }); } catch (error) { releaseDecoder(); throw error; }
  const model = gltf.scene;
  scene.add(model);
  const components = new Map(), poses = new WeakMap(), targets = new WeakMap();
  const picks = [], materials = new Set(), geometries = new Set(), modelTextures = new Set();
  // Capture native asset ownership before any shader replacement. All physical
  // reflection resources are separately owned by surface and disposed first.
  model.traverse(node => {
    if (!node.isMesh) return;
    geometries.add(node.geometry);
    for (const material of [].concat(node.material)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) modelTextures.add(value);
    }
  });
  let lighting, atmosphere, environment, glass, surface, floor, exhibitCover, disposed = false;
  const dispose = () => {
    if (disposed) return; disposed = true;
    lighting?.dispose(); exhibitCover?.dispose(); surface?.dispose(); glass?.dispose(); environment?.dispose(); atmosphere?.dispose(); releaseDecoder();
    floor?.geometry.dispose(); floor?.material.dispose();
    for (const node of components.values()) gsap.killTweensOf([node.position, node.scale, node.rotation]);
    geometries.forEach((geometry) => geometry.dispose());
    materials.forEach((material) => material.dispose());
    modelTextures.forEach((texture) => texture.dispose());
  };
  try {
    model.updateMatrixWorld(true);
    const pivotedAssets = [];
    model.traverse((node) => {
      if ((node.isMesh && node.userData.asset_id) || node.userData.asset_id === returnPortalId) pivotedAssets.push(node);
    });
    // Some editable leaf meshes use world-space vertices. A centered wrapper
    // also lets the complete doorway respond around its own center, without
    // separating its frame pieces or moving any of the resting geometry.
    for (const node of pivotedAssets) {
      const parent = node.parent;
      const pivot = new THREE.Group();
      pivot.name = `${node.name}_Pivot`;
      pivot.userData = { ...node.userData };
      parent.add(pivot);
      pivot.position.copy(parent.worldToLocal(new THREE.Box3().setFromObject(node).getCenter(new THREE.Vector3())));
      pivot.updateMatrixWorld(true);
      pivot.attach(node);
      delete node.userData.asset_id;
    }
    model.traverse((node) => {
      const id = node.userData.asset_id;
      if (id) {
        if (id === returnPortalId) node.userData.interactive = true;
        if (components.has(id)) throw new Error(`Duplicate gallery asset: ${id}`);
        components.set(id, node);
        poses.set(node, { position: node.position.clone(), rotation: node.rotation.clone(), scale: node.scale.clone() });
      }
      if (!node.isMesh) return;
      node.castShadow = node.receiveShadow = false;
      geometries.add(node.geometry);
      let glass = false;
      for (const material of [].concat(node.material)) {
        materials.add(material);
        if (material.map) material.map.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
        if (material.transparent || /CLEAR|ARCH_GLASS/.test(material.name)) {
          glass = true;
          material.depthWrite = false;
          material.side = THREE.FrontSide;
          material.forceSinglePass = true;
          material.toneMapped = false;
        }
      }
      if (!glass && !owner(node)?.userData.asset_id?.startsWith('gallery.environment')) picks.push(node);
    });
    if (components.size !== 77) throw new Error(`Gallery needs 77 independent IDs; found ${components.size}`);
    if (physicalGallery) surface = await createPhysicalSurface({ THREE, renderer, objects: [model], loader: textureLoader,
      profile: { family: 'gallery', directory: materialRelease.galleryDirectory, ...materialRelease.radiance,
        slots: [0, 1, 2, 3], glass: { enabled: true } },
    });
    exhibitCover = createGalleryExhibitCover({ model, renderer });
    lighting = await createDualLighting({ THREE, renderer, objects: [model], reducedMotion,
      profile: { revision: materialRelease.galleryRevision, materialPattern: /^GALLERY_LIGHTMAP_(\d+)/, slots: [0, 1, 2, 3], directory: materialRelease.galleryDirectory, loader: textureLoader, extension: 'ktx2', exteriorNightExposure: {},
        ...(physicalGallery ? { ...materialRelease.radiance, interiorNightReadability: 0, dayMixUniform: surface.getDayMixUniform() } : {}) },
      onProgress: (n, total) => onProgress(.72 + n / total * .23),
    });
    floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial());
    floor.rotation.x = -Math.PI / 2; floor.position.y = -.88; scene.add(floor);
    const bounds = new THREE.Box3(new THREE.Vector3(-9.29, -.49, -4), new THREE.Vector3(8.2, 5.42, 6.48));
    atmosphere = createExteriorAtmosphere({ THREE, scene, ground: floor, roomBounds: bounds, reducedMotion });
    environment = await createGalleryFloorFinish({ ground: floor, sky: atmosphere.sky, loader: textureLoader, renderer,
      floorDirectory: '/textures/gallery-atmosphere-v2', backdrop });
    if (!physicalGallery) {
      glass = await createGalleryGlass({ model, loader: textureLoader, renderer, themeUniform: environment.getThemeUniform(), directory: materialRelease.galleryDirectory });
      materials.add(glass.material);
    }
    const setDayMix = value => { lighting.setDayMix(value); atmosphere.setDayMix(value); };
    const setTheme = (day, duration = 1.5) => { lighting.setTheme(day, duration); atmosphere.setTheme(day, duration); };
    setTheme(isDay, 0);
    await exhibitCover.ready;
    releaseDecoder();
    onProgress(.97);
    let hovered = null;
    const ray = new THREE.Raycaster(), pointer = new THREE.Vector2();
    const temporary = new THREE.Vector3();

    function owner(node) {
      for (let current = node; current && current !== model; current = current.parent) if (current.userData.asset_id) return current;
      return null;
    }
    function station(node) {
      for (let current = node; current && current !== model; current = current.parent) {
        const match = current.userData.asset_id?.match(stationPattern);
        if (match) return Number(match[1]);
      }
      return null;
    }
    const pick = (x, y, camera, rect) => {
      pointer.set((x - rect.left) / rect.width * 2 - 1, 1 - (y - rect.top) / rect.height * 2);
      ray.setFromCamera(pointer, camera);
      const hits = ray.intersectObjects(picks, false);
      if (!hits.length) return null;
      let node = owner(hits[0].object);
      // A cabinet rail should not steal a click from its own drawer behind it.
      // Only prefer descendants within that same asset, never unrelated objects.
      for (const hit of hits.slice(1)) {
        const candidate = owner(hit.object);
        for (let parent = candidate?.parent; parent; parent = parent.parent) {
          if (parent === node) { node = candidate; break; }
        }
      }
      if (node?.userData.asset_id === returnPortalId) return node;
      return node?.userData.interactive === false || node?.userData.asset_id?.startsWith('gallery.architecture') ? null : node;
    };
    const scaleFor = (node) => {
      const id = node.userData.asset_id;
      if (id === returnPortalId) return 1.025;
      if (stationPattern.test(id) || /vitrine$|sculpture$|table|bench/.test(id)) return 1.035;
      return /label|album|tool|cup|maquette/.test(id) ? 1.2 : 1.1;
    };
    const hover = (node, active) => {
      const pose = poses.get(node); if (!pose) return;
      if (active) hovered = node; else if (hovered === node) hovered = null;
      const amount = active ? scaleFor(node) : 1;
      gsap.to(node.scale, { x: pose.scale.x * amount, y: pose.scale.y * amount, z: pose.scale.z * amount, duration: reducedMotion ? .01 : .32, ease: node.userData.asset_id === returnPortalId ? 'power2.out' : 'back.out(1.4)', overwrite: true });
    };
    const activate = (node) => {
      const id = node.userData.asset_id;
      if (id === returnPortalId) return { returnToRoom: true };
      const index = station(node);
      if (index && (getGalleryExhibit(index) || !/geometry|maquette|sculpture\.model/.test(id))) return { station: index };
      const pose = poses.get(node); if (!pose) return {};
      const duration = reducedMotion ? .01 : .5;
      if (/drawer/.test(id)) {
        // Convert web-space forward into the retained Blender parent's basis.
        temporary.set(0, 0, .27).applyQuaternion(node.parent.getWorldQuaternion(new THREE.Quaternion()).invert());
        gsap.killTweensOf(node.position);
        gsap.timeline().to(node.position, { x: pose.position.x + temporary.x, y: pose.position.y + temporary.y, z: pose.position.z + temporary.z, duration, ease: 'power2.out' })
          .to(node.position, { x: pose.position.x, y: pose.position.y, z: pose.position.z, duration, ease: 'power2.inOut' }, '+=.7');
      } else if (/album|lamp\.head|sculpture|geometry|maquette|wheel|tool/.test(id)) {
        const axis = /album|lamp\.head|wheel/.test(id) ? 'x' : 'z';
        gsap.killTweensOf(node.rotation);
        gsap.timeline().to(node.rotation, { [axis]: pose.rotation[axis] + (/album/.test(id) ? -.2 : .55), duration, ease: 'power2.out' })
          .to(node.rotation, { [axis]: pose.rotation[axis], duration, ease: 'power2.inOut' }, '+=.3');
      } else {
        const pointerWasHere = hovered === node;
        hover(node, true);
        if (!pointerWasHere) hovered = null;
        gsap.delayedCall(duration + .2, () => { if (hovered !== node) hover(node, false); });
      }
      return {};
    };
    const callout = (node) => {
      node ||= components.get(returnPortalId);
      if (targets.has(node)) return targets.get(node);
      if (node.userData.asset_id === returnPortalId) {
        const target = { object: node, label: '返回房间', action: '点击入口返回', kind: 'return-room', interactive: true };
        targets.set(node, target); return target;
      }
      const index = station(node);
      const exhibit = getGalleryExhibit(index);
      const target = { object: node, label: exhibit?.title || (index ? `作品 ${String(index).padStart(2, '0')}` : names.find(([prefix]) => node.userData.asset_id.startsWith(prefix))?.[1] || '陈列物件'),
        action: index === 1 ? `${FIRST_GALLERY_WORK.category} · 点击观看` : exhibit ? `${exhibit.items.length > 1 ? `${exhibit.items.length} 个项目 · ` : ''}点击查看` : index ? '资料待补充 · 点击查看' : '点击互动', kind: index ? `gallery:${index}` : null, interactive: Boolean(index) };
      targets.set(node, target); return target;
    };
    const framing = createGalleryFraming(model), pose = framing.pose;
    const update = (timestamp, camera) => atmosphere.update(timestamp, camera);
    return { scene, model, components, environment, setTheme, setDayMix, pick, hover, activate, callout, pose, update, dispose, floorY: -.49,
      getState: () => ({ ready: !disposed, release: materialRelease.name, modelUrl: materialRelease.galleryModel, physicalMaterials: physicalGallery,
        assetCount: components.size, framing: framing.getState(), hovered: hovered?.userData.asset_id ?? null,
        lighting: lighting.getState(), physicalSurface: surface?.getState() ?? null, environment: environment.getState(),
        firstExhibit: exhibitCover.getState(),
        glass: glass?.getState() ?? surface?.getState().glass ?? null, compressedTextures: true,
        textureFormats: [...materials].filter(m => m.map).map(m => ({ material: m.name, format: m.map.format, compressed: Boolean(m.map.isCompressedTexture), width: m.map.image.width, height: m.map.image.height })) }),
    };
  } catch (error) { dispose(); throw error; }
}
