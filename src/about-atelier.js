import * as THREE from 'three';
import gsap from 'gsap';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { createExteriorAtmosphere } from './exterior-atmosphere.js';
import { createAboutFraming } from './about-framing.js';
import { createAtelierEnvironmentFinish } from './about-atelier-environment.js';
import { configureResumeBook, RESUME_BOOK_ID } from './scene-inspection.js';

const DIRECTORY = '/textures/about-atelier-v3';
const RETURN_ID = 'atelier.return.interface';
const LIGHTMAP = /^ATELIER_LIGHTMAP_([0-3])$/;
const labels = [
  [/contact_terminal/, '联系终端'], [/archive\.award\.\d+\.glass_lid/, '奖项玻璃罩'], [/archive\.award/, '奖项陈列'],
  [/archive\.drawer|workbench\.drawer_\d|scroll_drawer/, '档案抽屉'], [/cabinet/, '胡桃木档案柜'],
  [/open_sketchbook/, '创作画册'], [/portfolio|archive_book|archive_folder|top_book/, '档案画册'],
  [/material|swatch|fabric_sample|surface_sample/, '材质样本'], [/lamp/, '工作台灯'],
  [/pegboard/, '工具挂板'], [/desk_structure/, '创作工作台'], [/headphones/, '监听耳机'],
  [/chair.caster/, '座椅脚轮'], [/chair/, '皮革工作椅'], [/plant/, '工坊绿植'],
  [/medal/, '奖章收藏'], [/screen/, '胡桃木屏风'], [/floor.art/, '原创几何装饰'],
  [/lens|geometry|polyhedron/, '造型习作'], [/pen|pencil|rule|caliper|brush|tool|gauge|magnifier/, '创作工具'],
  [/book|pad|envelope|scroll|drawing_roll/, '手稿与档案'],
];

export function aboutPanelFor(node) {
  const id = node?.userData.asset_id ?? '';
  if (id === RETURN_ID) return null;
  if (id === RESUME_BOOK_ID) return 'resume';
  if (/contact_terminal/.test(id)) return 'contact';
  if (/^archive\.(award|medal)/.test(id)) return 'awards';
  if (/^about\.workbench\.|material_sample/.test(id)) return 'skills';
  return 'profile';
}

/** The Blender day/night bakes share four UV atlases. All 128 authored roots
 * retain their local transforms, including nested tools and hover finishes. */
export async function createAboutAtelier({ renderer, reducedMotion = false, onProgress = () => {}, nightLighting = false }) {
  const scene = new THREE.Scene(); scene.name = 'AboutArchiveAtelier';
  const textureLoader = new KTX2Loader().setTranscoderPath('/basis/').setWorkerLimit(2).detectSupport(renderer);
  const imageLoader = new THREE.TextureLoader();
  const textures = new Set(), materials = new Set(), geometries = new Set(), animations = new Set();
  const components = new Map(), targets = new WeakMap(), finishes = new Map();
  const meshes = [], glassMeshes = new WeakSet();
  const dayMix = { value: 1 }, reflectiveMaterials = new Set(), lightRigs = [], shaderBindings = [];
  const nightState = { requested: Boolean(nightLighting), ready: false, error: null, mapCount: 0 };
  let requestedDayMix = 1, clockDriven = false;
  let model, architecture, atmosphere, reflection, ground, disposed = false, loaderDisposed = false, hovered = null, lastActivated = null, framing;
  let modelPath = '/models/about-atelier-v3-compressed.glb';
  const disposeLoader = () => {
    if (loaderDisposed) return;
    textureLoader.dispose(); loaderDisposed = true;
  };
  const captureMaterial = material => {
    materials.add(material);
    for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
  };
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    animations.forEach(animation => animation.kill()); animations.clear();
    gsap.killTweensOf(dayMix);
    shaderBindings.forEach(({ material, previousCompile, previousKey }) => {
      material.onBeforeCompile = previousCompile; material.customProgramCacheKey = previousKey;
    });
    shaderBindings.length = 0;
    for (const finish of finishes.values()) gsap.killTweensOf(finish);
    atmosphere?.dispose();
    reflection?.dispose(); disposeLoader();
    geometries.forEach(geometry => geometry.dispose());
    materials.forEach(material => material.dispose());
    textures.forEach(texture => texture.dispose());
    scene.clear();
  };
  const owner = node => {
    for (let current = node; current && current !== model; current = current.parent) if (current.userData.asset_id) return current;
    return null;
  };
  try {
    const loader = new GLTFLoader().setKTX2Loader(textureLoader);
    const progress = event => { if (event.lengthComputable) onProgress(event.loaded / event.total * .5); };
    let gltf;
    try { gltf = await loader.loadAsync(modelPath, progress); }
    catch { modelPath = '/models/about-atelier-v3.glb'; gltf = await loader.loadAsync(modelPath, progress); }
    model = gltf.scene; scene.add(model); model.updateMatrixWorld(true);
    model.traverse(node => {
      const id = node.userData.asset_id;
      if (id) {
        if (components.has(id)) throw new Error(`Duplicate atelier asset: ${id}`);
        components.set(id, node);
        finishes.set(node, { value: 0, materials: new Map() });
      }
      if (!node.isMesh) return;
      geometries.add(node.geometry); [].concat(node.material).forEach(captureMaterial);
    });
    if (components.size !== 128 || !components.has(RETURN_ID)) throw new Error(`Atelier requires 128 independent assets and its return interface; found ${components.size}`);
    const embeddedAtlases = new Map();
    for (const material of materials) {
      const match = material.name.match(LIGHTMAP);
      if (match && material.map) embeddedAtlases.set(Number(match[1]), material.map);
    }
    let loadedAtlases = 0;
    const atlasLoads = await Promise.allSettled([0, 1, 2, 3].map(async slot => {
      // Both exports embed their maps. Reuse them so the four 4K atlases are
      // decoded, transferred and held on the GPU only once.
      let texture = embeddedAtlases.get(slot);
      if (!texture) {
        try { texture = await textureLoader.loadAsync(`${DIRECTORY}/day-${slot}.ktx2`); }
        catch { texture = await imageLoader.loadAsync(`${DIRECTORY}/day-${slot}.png`); texture.flipY = false; }
      }
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
      texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
      textures.add(texture); onProgress(.5 + ++loadedAtlases / 4 * .26);
      return texture;
    }));
    const failedAtlas = atlasLoads.find(result => result.status === 'rejected');
    if (failedAtlas) throw failedAtlas.reason;
    const atlases = atlasLoads.map(result => result.value);
    const hdri = await new RGBELoader().loadAsync(`${DIRECTORY}/landscape/lake_pier_2k.hdr`);
    try {
      hdri.mapping = THREE.EquirectangularReflectionMapping;
      const pmrem = new THREE.PMREMGenerator(renderer);
      try { reflection = pmrem.fromEquirectangular(hdri); }
      finally { pmrem.dispose(); }
    } finally { hdri.dispose(); }
    scene.environment = reflection.texture;
    scene.environmentIntensity = .5;
    // The native Blender panorama includes close pier masts. Frame its open
    // water sector instead: at the approved camera azimuth the centre samples
    // u=.625. Keep the real lake horizon level and rotate reflections with it.
    scene.environmentRotation.set(0, THREE.MathUtils.degToRad(167.4), 0, 'YXZ');
    const shared = new Map();
    const materialFor = (original, asset) => {
      const finish = finishes.get(asset);
      const cache = finish?.materials ?? shared;
      if (cache.has(original)) return cache.get(original).material;
      const match = original.name.match(LIGHTMAP);
      let material;
      if (match) {
        material = new THREE.MeshBasicMaterial({ name: original.name, map: atlases[Number(match[1])], toneMapped: false, side: original.side });
      } else if (/^ATELIER_GLASS/.test(original.name)) {
        material = new THREE.MeshPhysicalMaterial({ name: original.name, color: '#faffff', metalness: 0,
          roughness: .055, transmission: 1, thickness: .004, ior: 1.46,
          transparent: true, opacity: 1, depthWrite: false, side: THREE.FrontSide,
          envMap: reflection.texture, envMapIntensity: .5, toneMapped: true });
        material.envMapRotation.copy(scene.environmentRotation);
      } else if (/^ATELIER_METAL_/.test(original.name)) {
        material = original.clone(); material.envMap = reflection.texture; material.envMapIntensity = .5;
        material.envMapRotation.copy(scene.environmentRotation);
        material.metalness = Math.max(original.metalness ?? 1, .55);
        material.roughness = THREE.MathUtils.clamp(original.roughness ?? .24, .18, .42);
        material.toneMapped = true;
      } else {
        throw new Error(`Unexpected atelier material: ${original.name}`);
      }
      materials.add(material);
      if (material.envMap) reflectiveMaterials.add(material);
      cache.set(original, { material, color: material.color.clone() });
      return material;
    };
    model.traverse(node => {
      if (!node.isMesh) return;
      const asset = owner(node), original = node.material;
      node.material = Array.isArray(original) ? original.map(material => materialFor(material, asset)) : materialFor(original, asset);
      node.castShadow = node.receiveShadow = false;
      if ([].concat(node.material).some(material => /^ATELIER_GLASS/.test(material.name))) glassMeshes.add(node);
      meshes.push(node);
    });
    // The source atrium surrounds the display at its authored metre scale. It
    // is deliberately outside model/components: camera fitting and all 128
    // independent interactions continue to use only the main atelier assets.
    const architecturePath = '/models/about-atelier-v3-architecture.glb';
    architecture = (await loader.loadAsync(`${architecturePath}?v=connected-pavilion-v2-deck`, event => {
      if (event.lengthComputable) onProgress(.77 + event.loaded / event.total * .12);
    })).scene;
    architecture.name = 'AtelierSourceArchitecture';
    architecture.userData.excludeFromFraming = true;
    architecture.userData.interactive = false;
    const architecturalMaterials = new Map();
    let architecturalMeshCount = 0, architecturalGlassCount = 0, architectureSource;
    const architectureSourceNodes = new Set();
    architecture.traverse(node => {
      if (node.userData.asset_id) throw new Error('Atelier architectural context must not introduce asset identities.');
      if (node.userData.architecture) architectureSource = { ...node.userData };
      if (node.userData.source_node) architectureSourceNodes.add(node.userData.source_node);
      if (node.userData.source_nodes) {
        for (const name of JSON.parse(node.userData.source_nodes)) architectureSourceNodes.add(name);
      }
      node.userData.interactive = false;
      node.userData.excludeFromFraming = true;
      if (!node.isMesh) return;
      architecturalMeshCount++;
      geometries.add(node.geometry);
      node.castShadow = node.receiveShadow = false;
      node.raycast = () => {};
      const convert = original => {
        captureMaterial(original);
        if (architecturalMaterials.has(original)) return architecturalMaterials.get(original);
        let material;
        if (original.name === 'ATELIER_ARCH_LIGHTMAP') {
          if (!original.map) throw new Error('Atelier architectural daylight atlas is missing.');
          original.map.colorSpace = THREE.SRGBColorSpace;
          original.map.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
          material = new THREE.MeshBasicMaterial({ name: original.name, map: original.map, toneMapped: false, side: original.side });
        } else if (original.name === 'ATELIER_ARCH_GLASS') {
          material = new THREE.MeshPhysicalMaterial({ name: original.name, color: '#f2fbff', metalness: 0,
            roughness: .055, transmission: 1, thickness: .014, ior: 1.46,
            transparent: true, opacity: 1, depthWrite: false, side: THREE.FrontSide,
            envMap: reflection.texture, envMapIntensity: .5, toneMapped: true });
          material.envMapRotation.copy(scene.environmentRotation);
        } else { throw new Error(`Unexpected atelier architecture material: ${original.name}`); }
        materials.add(material); if (material.envMap) reflectiveMaterials.add(material);
        architecturalMaterials.set(original, material); return material;
      };
      node.material = Array.isArray(node.material) ? node.material.map(convert) : convert(node.material);
      if ([].concat(node.material).some(material => material.name === 'ATELIER_ARCH_GLASS')) architecturalGlassCount++;
    });
    if (architecturalMeshCount !== 9 || architecturalGlassCount !== 8) {
      throw new Error(`Atelier requires its baked architecture and 8 panes; found ${architecturalMeshCount}/${architecturalGlassCount}.`);
    }
    scene.add(architecture);
    const architectureBounds = new THREE.Box3().setFromObject(architecture);
    const panorama = await imageLoader.loadAsync(`${DIRECTORY}/landscape/lake-pier-day.png`);
    panorama.colorSpace = THREE.SRGBColorSpace;
    panorama.wrapS = THREE.RepeatWrapping;
    panorama.wrapT = THREE.ClampToEdgeWrapping;
    textures.add(panorama); onProgress(.94);
    let nightAtlases = [], nightArchitecture, nightPanorama = panorama;
    if (nightLighting) {
      const loadNightMap = async path => {
        let map;
        try { map = await textureLoader.loadAsync(`${path}.ktx2`); }
        catch { map = await imageLoader.loadAsync(`${path}.png`); map.flipY = false; }
        map.colorSpace = THREE.SRGBColorSpace;
        map.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
        map.wrapS = map.wrapT = THREE.ClampToEdgeWrapping;
        return map;
      };
      // Install the complete lighting set atomically. A missing bake retains
      // the approved daylight; it never creates a fake uniformly tinted night.
      const results = await Promise.allSettled([
        ...[0, 1, 2, 3].map(slot => loadNightMap(`${DIRECTORY}/night-${slot}`)),
        loadNightMap(`${DIRECTORY}/architecture/night`),
        imageLoader.loadAsync(`${DIRECTORY}/landscape/lake-pier-night.png`),
      ]);
      const failure = results.find(result => result.status === 'rejected');
      if (failure) {
        new Set(results.filter(result => result.status === 'fulfilled').map(result => result.value)).forEach(map => map.dispose());
        nightState.error = failure.reason?.message ?? String(failure.reason);
        console.warn('About atelier night bakes are unavailable; retaining the approved daylight.', failure.reason);
      } else {
        nightAtlases = results.slice(0, 4).map(result => result.value);
        nightArchitecture = results[4].value; nightPanorama = results[5].value;
        nightPanorama.colorSpace = THREE.SRGBColorSpace;
        nightPanorama.wrapS = THREE.RepeatWrapping; nightPanorama.wrapT = THREE.ClampToEdgeWrapping;
        [...nightAtlases, nightArchitecture, nightPanorama].forEach(map => { textures.add(map); renderer.initTexture(map); });
        nightState.ready = true; nightState.mapCount = 5;
      }
    }
    if (nightState.ready) {
      for (const material of materials) {
        if (!material.isMeshBasicMaterial || !material.map) continue;
        const match = material.name.match(LIGHTMAP);
        const nightMap = match ? nightAtlases[Number(match[1])] : material.name === 'ATELIER_ARCH_LIGHTMAP' ? nightArchitecture : null;
        if (nightMap) shaderBindings.push(bindAtelierNightMap(material, nightMap, dayMix));
      }
    }
    const addDaylight = (targetScene, offset = new THREE.Vector3()) => {
      const rig = new THREE.Group(); rig.name = 'AtelierReflectiveMaterialCycle'; rig.position.copy(offset);
      const sun = new THREE.DirectionalLight('#ffdab0', 2.25);
      sun.position.set(-8, 6.1, 4.5); rig.add(sun, sun.target);
      const fill = new THREE.HemisphereLight('#e1efff', '#b2a58d', .35); rig.add(fill);
      // Match the authored Blender warm.awards and warm.desk positions. These
      // only light real-time glass/metals; opaque furniture uses its true bake.
      const awards = new THREE.PointLight('#ffc878', 0, 7, 2); awards.position.set(-1.15, 3.70, -.56);
      const desk = new THREE.PointLight('#ffd1a0', 0, 6, 2); desk.position.set(.95, 2.80, -.74);
      rig.add(awards, desk); lightRigs.push({ sun, fill, awards, desk });
      targetScene.add(rig); return rig;
    };
    addDaylight(scene);
    const bounds = new THREE.Box3().setFromObject(model), floorY = bounds.min.y - .006;
    ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial());
    geometries.add(ground.geometry); materials.add(ground.material);
    ground.rotation.x = -Math.PI / 2; ground.position.y = floorY; ground.name = 'Atelier exterior ground'; scene.add(ground);
    atmosphere = createExteriorAtmosphere({ THREE, scene, ground, roomBounds: bounds, reducedMotion });
    atmosphere.setDayMix(1);
    ground.material.uniforms.uDayFloor.value.set('#c9c2b4');
    ground.material.uniforms.uSunDirection.value.set(-8, 6.1, 4.5).normalize();
    const environmentFinish = createAtelierEnvironmentFinish({ ground, sky: atmosphere.sky, panorama, nightPanorama, dayMixUniform: dayMix, rotation: scene.environmentRotation });
    const nightSky = new THREE.Color('#728cac'), daySky = new THREE.Color('#e1efff');
    const nightGround = new THREE.Color('#241c16'), dayGround = new THREE.Color('#b2a58d');
    const syncLighting = () => {
      const value = dayMix.value;
      atmosphere.setDayMix(value);
      const reflectionStrength = THREE.MathUtils.lerp(.065, .5, value);
      scene.environmentIntensity = reflectionStrength;
      reflectiveMaterials.forEach(material => { material.envMapIntensity = reflectionStrength; });
      for (const { sun, fill, awards, desk } of lightRigs) {
        sun.intensity = 2.25 * value;
        fill.intensity = THREE.MathUtils.lerp(.045, .35, value);
        fill.color.copy(nightSky).lerp(daySky, value); fill.groundColor.copy(nightGround).lerp(dayGround, value);
        awards.intensity = 7 * (1 - value); desk.intensity = 5.5 * (1 - value);
      }
    };
    const setDayMix = value => {
      if (disposed || !Number.isFinite(value)) return;
      if (!clockDriven) { gsap.killTweensOf(dayMix); clockDriven = true; }
      requestedDayMix = THREE.MathUtils.clamp(value, 0, 1);
      dayMix.value = nightState.ready ? requestedDayMix : 1; syncLighting();
    };
    const setTheme = (isDay, duration = 1.5) => {
      if (disposed) return;
      clockDriven = false; gsap.killTweensOf(dayMix); requestedDayMix = isDay ? 1 : 0;
      const value = nightState.ready ? requestedDayMix : 1;
      if (duration <= 0 || reducedMotion) { dayMix.value = value; syncLighting(); return; }
      gsap.to(dayMix, { value, duration, ease: 'power2.inOut', overwrite: true, onUpdate: syncLighting });
    };
    syncLighting();
    // A photographic lake already contains the source atmospheric depth. An
    // additional procedural fog would wash the windows and dark joinery gray.
    scene.fog = null;
    const resumeEntry = configureResumeBook(model, components);
    framing = createAboutFraming(model);
    const applyFinish = finish => {
      for (const { material, color } of finish.materials.values()) material.color.copy(color).multiplyScalar(1 + finish.value * .12);
    };
    const hover = (node, active) => {
      if (disposed || !finishes.has(node) || node.userData.interactive === false) return;
      if (active && hovered && hovered !== node) hover(hovered, false);
      hovered = active ? node : hovered === node ? null : hovered;
      const finish = finishes.get(node);
      gsap.to(finish, { value: active ? 1 : 0, duration: reducedMotion ? 0 : .22, ease: 'power2.out', overwrite: true,
        onUpdate: () => applyFinish(finish) });
    };
    const activate = node => {
      if (disposed || !components.has(node?.userData.asset_id) || node.userData.interactive === false) return {};
      lastActivated = node.userData.asset_id;
      if (lastActivated === RETURN_ID) return { returnToRoom: true };
      const finish = finishes.get(node);
      gsap.killTweensOf(finish);
      const timeline = gsap.timeline({ onComplete: () => animations.delete(timeline) });
      animations.add(timeline);
      timeline.to(finish, { value: 1.5, duration: reducedMotion ? .01 : .14, onUpdate: () => applyFinish(finish) })
        .to(finish, { value: hovered === node ? 1 : 0, duration: reducedMotion ? .01 : .3, onUpdate: () => applyFinish(finish) });
      return { panel: aboutPanelFor(node) };
    };
    const ray = new THREE.Raycaster(), pointer = new THREE.Vector2();
    const pick = (x, y, camera, rect) => {
      if (disposed || !rect?.width || !rect?.height) return null;
      pointer.set((x - rect.left) / rect.width * 2 - 1, 1 - (y - rect.top) / rect.height * 2);
      ray.setFromCamera(pointer, camera);
      const hits = ray.intersectObjects(meshes, false);
      if (!hits.length) return null;
      let hit = hits[0];
      if (glassMeshes.has(hit.object)) {
        const award = owner(hit.object)?.userData.asset_id?.match(/^archive\.award\.\d+/)?.[0];
        const interior = hits.find(candidate => !glassMeshes.has(candidate.object) && owner(candidate.object)?.userData.asset_id?.startsWith(`${award}.`));
        if (award && interior) hit = interior;
      }
      const node = owner(hit.object);
      return node?.userData.interactive === false ? null : node;
    };
    const callout = node => {
      node ||= components.get(RETURN_ID);
      if (!components.has(node?.userData.asset_id)) return null;
      if (!targets.has(node)) {
        const id = node.userData.asset_id, returning = id === RETURN_ID;
        targets.set(node, { object: node, label: returning ? '返回房间' : id === RESUME_BOOK_ID ? '王丞业 · 个人能力档案' : labels.find(([pattern]) => pattern.test(id))?.[1] ?? '档案工坊藏品',
          action: returning ? '点击按钮返回' : id === RESUME_BOOK_ID ? '游戏策划 / 运营 · 点击翻阅' : '资料待补充 · 点击查看', kind: returning ? 'return-room' : `about:${aboutPanelFor(node)}`,
          interactive: node.userData.interactive !== false });
      }
      return targets.get(node);
    };
    const environment = {
      ...environmentFinish,
      configureTravelStage(stage, offset = new THREE.Vector3()) {
        addDaylight(stage, offset); syncLighting();
        const berth = new THREE.Group(); berth.name = 'AtelierArchitectureTravelBerth'; berth.position.copy(offset);
        const clone = architecture.clone(true);
        clone.traverse(node => { if (node.isMesh) node.raycast = () => {}; });
        berth.add(clone); stage.add(berth);
      },
      getState: () => ({ ...environmentFinish.getState(), dayMix: dayMix.value, fixedDaylight: false,
        reflection: `${DIRECTORY}/landscape/lake_pier_2k.hdr`, architecture: { modelPath: architecturePath,
          meshes: architecturalMeshCount, panes: architecturalGlassCount, independentOfFraming: true, originalScale: true,
          revision: architectureSource?.architectureRevision ?? 'Original architecture',
          source: architectureSource?.source ?? null, sourceSha256: architectureSource?.sourceSha256 ?? null,
          sourceNodeCount: architectureSourceNodes.size,
          bounds: { min: architectureBounds.min.toArray(), max: architectureBounds.max.toArray() },
          extraDecor: false, excludedFromPicking: true } }),
    };
    disposeLoader(); onProgress(1);
    return { scene, model, components, environment, pick, hover, activate, callout, pose: framing.pose, floorY,
      setTheme, setDayMix, update: timestamp => atmosphere.update(timestamp), dispose,
      getState: () => ({ ready: !disposed, revision: 4, modelPath, assetCount: components.size, interactiveCount: [...components.values()].filter(node => node.userData.interactive !== false).length,
        framing: framing.getState(), hovered: hovered?.userData.asset_id ?? null, lastActivated, fixedDaylight: false,
        lighting: { baked: true, dayMix: dayMix.value, requestedDayMix, atlasCount: atlases.length, night: { ...nightState },
          materialBindings: shaderBindings.length, reflectionIntensity: scene.environmentIntensity, practicalLights: 2,
          nightTextureFormats: [...nightAtlases, nightArchitecture].filter(Boolean).map(map => ({ format: map.format,
            compressed: Boolean(map.isCompressedTexture), width: map.image.width, height: map.image.height })) }, environment: environment.getState(),
        geometryTransforms: 'desk book enlarged in runtime; remaining authored transforms preserved',
        resumeEntry: resumeEntry ? { assetId: RESUME_BOOK_ID, ...resumeEntry.userData.resumeEntry } : null,
        textureFormats: atlases.map((map, slot) => ({ material: `ATELIER_LIGHTMAP_${slot}`, format: map.format, compressed: Boolean(map.isCompressedTexture), width: map.image.width, height: map.image.height })),
        glass: { transmission: 1, thickness: .004, ior: 1.46 }, floorY }),
    };
  } catch (error) { dispose(); throw error; }
}

/** Both maps share the original exported UVs. Keep material.color outside this
 * sampler so each asset's existing hover/activation brightness stays separate. */
export function bindAtelierNightMap(material, nightMap, dayMixUniform) {
  const sample = 'vec4 sampledDiffuseColor = texture2D( map, vMapUv );';
  if (!THREE.ShaderChunk.map_fragment.includes(sample)) throw new Error('Atelier lightmap shader needs review for this Three.js version.');
  const previousCompile = material.onBeforeCompile, previousKey = material.customProgramCacheKey;
  const baseKey = previousKey.call(material);
  material.onBeforeCompile = (shader, renderer) => {
    previousCompile.call(material, shader, renderer);
    if (!shader.fragmentShader.includes('#include <map_fragment>')) throw new Error(`Atelier cannot bind a night bake to ${material.name}.`);
    shader.uniforms.uAtelierNightMap = { value: nightMap }; shader.uniforms.uAtelierDayMix = dayMixUniform;
    shader.fragmentShader = `uniform sampler2D uAtelierNightMap;\nuniform float uAtelierDayMix;\n${shader.fragmentShader}`
      .replace('#include <map_fragment>', THREE.ShaderChunk.map_fragment.replace(sample, `
        vec4 sampledDiffuseColor;
        if (uAtelierDayMix >= 1.0) sampledDiffuseColor = texture2D(map, vMapUv);
        else if (uAtelierDayMix <= 0.0) sampledDiffuseColor = texture2D(uAtelierNightMap, vMapUv);
        else sampledDiffuseColor = mix(texture2D(uAtelierNightMap, vMapUv), texture2D(map, vMapUv), uAtelierDayMix);
      `));
  };
  material.customProgramCacheKey = () => `${baseKey}|atelier-true-night-v1`;
  material.needsUpdate = true;
  return { material, previousCompile, previousKey };
}
