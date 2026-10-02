import * as THREE from 'three';
import { ROOM_ENTRY_PROFILES } from './room-entry-profiles.js';
export { ROOM_ENTRY_PROFILES } from './room-entry-profiles.js';

const HIDDEN_SCALE = 0.00001;
const GROUP_STARTS = [1.3, 1.6, 2.0, 2.1, 2.65];
const smooth = t => t * t * t * (t * (t * 6 - 15) + 10);

export const ROOM_ENTRY_GROUPS = [
  ['wall', ['c_archive_dock', 'kinetic_three_petal_flower', 'glass_bonsai_terrarium', 'trailing_wall_plant', 'v5_orbital_clock', 'v5_mechanical_data_panel', 'v8_window_light_bar']],
  ['furniture', ['furniture.desk', 'furniture.lounge', 'furniture.coffee_table', 'furniture.rug', 'black_ceramic_floor_planter', 'v5_geometric_floor_lamp']],
  ['desktop', ['thermal_cup', 'table_notebook_group', 'studio_reference_books', 'geometric_specimen_cloche', 'ceramic_mobius_study', 'glass_cutting_planter', 'v5_magnetic_pen_dock', 'v5_energy_capsule_rack', 'v8_reading_puck']],
  ['equipment', ['main_display', 'compute_core', 'robot_companion', 'folding_drawing_terminal', 'headphones_on_stand', 'ceramic_ring_speaker', 'split_keyboard', 'compact_camera', 'portable_fold_communicator', 'v5_portable_projector', 'v5_modular_equipment_cases', 'v5_scout_drone_display', 'v8_desk_glow_lamp']],
  ['chair', ['furniture.work_chair']],
];

// Gesture, offset inside its group, pace adjustment, and small finishing turn.
// Larger bounds independently lengthen the duration; these authored offsets
// keep unlike objects from looking like one repeated scale animation.
export const ROOM_ENTRY_MOTIONS = {
  c_archive_dock: ['slide-left', .04, .04, -.08],
  kinetic_three_petal_flower: ['bloom', .21, .1, .9],
  glass_bonsai_terrarium: ['drift', .32, .04, .28],
  trailing_wall_plant: ['unfurl', .12, .14, -.05],
  v5_orbital_clock: ['turn', 0, -.04, -.6],
  v5_mechanical_data_panel: ['panel', .15, -.03, .07],
  v8_window_light_bar: ['spread', .28, .01, 0],
  'lighting.ceiling_warm': ['spread', .36, .04, 0],
  'furniture.desk': ['spread', 0, .18, 0],
  'furniture.lounge': ['settle', .15, .15, -.13],
  'furniture.coffee_table': ['rise', .31, .08, .1],
  'furniture.rug': ['spread', .05, .16, 0],
  black_ceramic_floor_planter: ['rise', .24, .04, -.08],
  v5_geometric_floor_lamp: ['unfurl', .38, .12, .1],
  thermal_cup: ['hop', .09, -.04, .42],
  table_notebook_group: ['panel', .02, -.01, -.12],
  studio_reference_books: ['dock', .17, .02, .38],
  geometric_specimen_cloche: ['drift', .27, .06, -.32],
  ceramic_mobius_study: ['spin', .36, .08, Math.PI * 1.15],
  glass_cutting_planter: ['bloom', .22, .02, -.55],
  v5_magnetic_pen_dock: ['spring', .13, .02, .13],
  v5_energy_capsule_rack: ['dock', .32, .01, -.28],
  v8_reading_puck: ['spin', .43, -.02, -Math.PI * .8],
  main_display: ['panel', .01, .16, -.16],
  compute_core: ['rise', .16, .14, .15],
  robot_companion: ['hop', .38, .02, -.52],
  folding_drawing_terminal: ['flip', .12, .02, -.68],
  headphones_on_stand: ['spring', .28, .04, -.12],
  ceramic_ring_speaker: ['spin', .22, .01, Math.PI * .9],
  split_keyboard: ['spread', .06, -.04, 0],
  compact_camera: ['flip', .34, -.02, -.45],
  portable_fold_communicator: ['flip', .43, .02, .75],
  v5_portable_projector: ['dock', .25, -.01, -.32],
  v5_modular_equipment_cases: ['rise', .07, .12, .07],
  v5_scout_drone_display: ['drift', .47, .08, -.55],
  v8_desk_glow_lamp: ['spring', .4, .02, .11],
  'furniture.work_chair': ['chair', .08, .2, -Math.PI * .9],
};

const MOTION_LABELS = {
  spin: '旋转落位', hop: '轻跳落位', drift: '弧线缓降', flip: '翻起归位',
  dock: '侧滑归位', spring: '弹性舒展', bloom: '旋开生长',
  'slide-left': '左侧滑入', 'slide-right': '右侧滑入', settle: '轻缓落位',
  unfurl: '纵向展开', turn: '转动展开', panel: '面板展开', spread: '横向铺开',
  rise: '向上展开', chair: '转椅落位',
};
const MOTION_MIN_DURATION = { spin: 1.08, hop: .84, drift: 1.05, flip: .95, dock: .86, spring: .98, bloom: .95 };
const ramp = (value, start, end) => smooth(THREE.MathUtils.clamp((value - start) / (end - start), 0, 1));

// Animate the existing Blender roots inside their final spatial envelopes.
// Architecture belongs to the controller; each prop keeps its own exact TRS.
export function createRoomEntry({ room, roots, snapshots, bounds, externalIds = [] }) {
  const external = new Set(externalIds);
  room.updateWorldMatrix(true, true);
  const makeBinding = (node, id) => {
    const snapshot = snapshots.get(node) ?? node;
    const inverseParent = node.parent.matrixWorld.clone().invert();
    const box = new THREE.Box3(), vertex = new THREE.Vector3(), matrix = new THREE.Matrix4();
    node.traverse(mesh => {
      if (!mesh.isMesh) return;
      matrix.multiplyMatrices(inverseParent, mesh.matrixWorld);
      const positions = mesh.geometry.attributes.position;
      for (let i = 0; i < positions.count; i++) box.expandByPoint(vertex.fromBufferAttribute(positions, i).applyMatrix4(matrix));
    });
    const pivot = box.getCenter(new THREE.Vector3()); pivot.y = box.min.y;
    const size = box.getSize(new THREE.Vector3());
    const originalMatrix = node.matrix.clone(), inverseOriginal = originalMatrix.clone().invert();
    const corners = [];
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
      corners.push(new THREE.Vector3(x, y, z).applyMatrix4(inverseOriginal));
    }
    const profile = ROOM_ENTRY_MOTIONS[id] ?? ['body', 0, 0, 0];
    const choreography = ROOM_ENTRY_PROFILES[id];
    if (!choreography) throw new Error(`Room entry has no authored motion for ${id}`);
    const rotationAxis = new THREE.Vector3(...choreography.rotationAxis).normalize();
    const accentAxis = new THREE.Vector3(...choreography.accent.slice(0, 3));
    const accentAngle = accentAxis.length(); accentAxis.normalize();
    const duration = Math.max(MOTION_MIN_DURATION[profile[0]] ?? 0,
      THREE.MathUtils.clamp(.52 + Math.sqrt(size.length() / bounds.getSize(new THREE.Vector3()).length()) * .8 + profile[2] * .6, .5, 1.25));
    return { node, id, pivot, pivotLocal: pivot.clone().applyMatrix4(inverseOriginal), corners, box, factor: 0, turn: 0, size, profile, choreography, rotationAxis, accentAxis, accentAngle, duration,
      position: snapshot.position.clone(), rotation: snapshot.rotation.clone(),
      quaternion: node.quaternion.clone(), scale: snapshot.scale.clone(), at: 0 };
  };
  // V19's separate Blender fixture joins the wall sequence only when present;
  // old complete releases still require their original 36 independently bound props.
  const configuredGroups = ROOM_ENTRY_GROUPS.map(([name, ids]) => [name,
    name === 'wall' && roots.has('lighting.ceiling_warm') ? [...ids, 'lighting.ceiling_warm'] : ids]);
  const groups = configuredGroups.map(([name, ids]) => ({ name, items: ids.map(id => {
    const node = roots.get(id);
    if (!node) throw new Error(`Room entry is missing ${id}`);
    return makeBinding(node, id);
  }) }));
  const items = groups.flatMap(group => group.items), byId = new Map(items.map(item => [item.id, item]));
  // Surface-mounted props wait for the supporting furniture. Shelves belong
  // to the room shell and need no second local carrier or duplicate animation.
  const supports = new Map();
  for (const item of items) {
    if (item.id.startsWith('furniture.')) continue;
    for (const supportId of ['furniture.desk', 'furniture.coffee_table']) {
      const support = byId.get(supportId), center = item.box.getCenter(new THREE.Vector3());
      if (Math.abs(item.box.min.y - support.box.max.y) < .065 && center.x >= support.box.min.x && center.x <= support.box.max.x && center.z >= support.box.min.z && center.z <= support.box.max.z) {
        supports.set(item.id, supportId); break;
      }
    }
  }
  const turn = new THREE.Quaternion(), axisScale = new THREE.Vector3(), delta = new THREE.Vector3();
  const transform = new THREE.Matrix4(), trialBox = new THREE.Box3(), trialSize = new THREE.Vector3(), zero = new THREE.Vector3();
  let phase = 'prepared';
  function pose(binding) {
    const { node, pivot, pivotLocal } = binding;
    // Include the current rotation in pivot compensation (also for baked
    // vertices whose original root is far away from the visible object).
    transform.compose(zero, node.quaternion, node.scale);
    node.position.copy(pivot).sub(delta.copy(pivotLocal).applyMatrix4(transform));
    node.updateMatrix();
    trialBox.makeEmpty();
    for (const corner of binding.corners) trialBox.expandByPoint(delta.copy(corner).applyMatrix4(node.matrix));
  }
  function apply(binding) {
    const { node, factor, box, position, scale, quaternion, profile, size, choreography, rotationAxis, accentAxis, accentAngle } = binding;
    const f = THREE.MathUtils.clamp(factor, 0, 1), kind = profile[0];
    if (f >= 1) {
      node.position.copy(position); node.quaternion.copy(quaternion); node.scale.copy(scale); return;
    }
    const { grow, rotationWindow, rebound, accent, path } = choreography;
    axisScale.set(Math.pow(f, grow[0]), Math.pow(f, grow[1]), Math.pow(f, grow[2]));
    if (kind === 'hop') axisScale.y *= 1 - Math.sin(Math.PI * ramp(f, .45, .98)) ** 2 * .09;
    // This late, bounded compression gives each prop a soft elastic afterbeat
    // without overshooting a neighbouring surface like back.out scale would.
    axisScale.multiplyScalar(1 - rebound[0] * Math.sin(Math.PI * ramp(f, rebound[1], rebound[2])) ** 2);
    axisScale.multiplyScalar(1 - HIDDEN_SCALE).addScalar(HIDDEN_SCALE);
    node.scale.copy(scale).multiply(axisScale);
    node.quaternion.copy(quaternion);
    const rotationProgress = ramp(f, rotationWindow[0], rotationWindow[1]);
    let angle = profile[3] * (1 - rotationProgress);
    if (kind === 'hop') angle = profile[3] * Math.sin(Math.PI * rotationProgress) * (1 - f);
    if (kind === 'spring') angle = profile[3] * Math.sin(Math.PI * rotationProgress * 2) * (1 - f);
    if (angle) node.quaternion.premultiply(turn.setFromAxisAngle(rotationAxis, angle));
    const accentProgress = ramp(f, accent[3], accent[4]);
    // A separately timed pitch/roll/yaw gives e.g. the camera a lens raise,
    // the scout a wing levelling finish and the lamp an actual nod.
    const secondary = accentAngle * Math.sin(Math.PI * accentProgress);
    if (secondary) node.quaternion.premultiply(turn.setFromAxisAngle(accentAxis, secondary));
    pose(binding);
    trialBox.getSize(trialSize);
    const fit = Math.min(1, size.x / Math.max(trialSize.x, 1e-10), size.y / Math.max(trialSize.y, 1e-10), size.z / Math.max(trialSize.z, 1e-10));
    if (fit < 1) { node.scale.multiplyScalar(fit); pose(binding); trialBox.getSize(trialSize); }
    // Keep the full conservative vertex envelope inside the original footprint
    // and above its support. The old negative rise offset pierced the floor.
    const freeY = Math.max(0, size.y - trialSize.y);
    let lift = kind === 'settle' ? Math.min(freeY, Math.min(size.y * .15, .15) * (1 - f)) : 0;
    let shift = kind.startsWith('slide-') ? (kind === 'slide-left' ? -1 : 1) * Math.min(size.x * .09, .1) * (1 - f) : 0;
    let depth = 0;
    if (kind === 'hop') lift = Math.min(freeY, size.y * .55, .26) * Math.sin(Math.PI * ramp(f, .02, .92)) ** 2;
    if (kind === 'drift') {
      lift = Math.min(freeY, size.y * .5, .28) * (1 - ramp(f, .16, .94));
      shift = Math.sin(Math.PI * f) * size.x * .2 * (1 - f);
      depth = Math.sin(Math.PI * f * 2) * size.z * .1 * (1 - f);
    }
    if (kind === 'dock') {
      shift = Math.sign(profile[3]) * Math.min(size.x * .46, .35) * (1 - ramp(f, .08, .94));
      depth = Math.sin(Math.PI * f) * size.z * .08 * (1 - f);
    }
    const pathProgress = 1 - ramp(f, rotationWindow[0], Math.max(rotationWindow[1], .9));
    shift += size.x * path[0] * pathProgress;
    depth += size.z * path[2] * pathProgress;
    lift = Math.min(freeY, Math.max(0, lift + size.y * path[1] * pathProgress));
    const dx = THREE.MathUtils.clamp(shift, box.min.x - trialBox.min.x, box.max.x - trialBox.max.x);
    const dz = THREE.MathUtils.clamp(depth, box.min.z - trialBox.min.z, box.max.z - trialBox.max.z);
    node.position.x += dx; node.position.z += dz;
    node.position.y += box.min.y - trialBox.min.y + lift;
  }
  for (const id of external) if (!byId.has(id)) throw new Error(`Cannot externally control missing room prop ${id}`);
  items.forEach(item => { if (!external.has(item.id)) item.node.scale.copy(item.scale).multiplyScalar(HIDDEN_SCALE); }); room.updateMatrixWorld(true);
  function update() {
    if (phase === 'complete' || phase === 'prepared') return;
    items.forEach(item => { if (!external.has(item.id)) apply(item); }); room.updateMatrixWorld(true);
  }
  function restore() {
    for (const item of items) {
      item.node.position.copy(item.position); item.node.rotation.copy(item.rotation); item.node.scale.copy(item.scale);
      item.node.quaternion.copy(item.quaternion); item.factor = 1; item.turn = 0;
    }
    room.updateMatrixWorld(true); phase = 'complete';
  }
  return {
    appendTo(timeline, start = .9) {
      timeline.call(() => { phase = 'growing'; }, [], start);
      groups.forEach((group, groupIndex) => group.items.forEach(item => { item.at = start + GROUP_STARTS[groupIndex] + item.profile[1]; }));
      for (const [id, supportId] of supports) {
        const item = byId.get(id), support = byId.get(supportId);
        item.at = Math.max(item.at, support.at + support.duration + .025 + item.profile[1] * .85);
      }
      let end = start;
      for (const item of items) {
        if (external.has(item.id)) continue;
        timeline.to(item, { factor: 1, duration: item.duration, ease: smooth }, item.at);
        end = Math.max(end, item.at + item.duration);
      }
      return end;
    },
    update, restore,
    setExternalControl(id, enabled = true) {
      const item = byId.get(id);
      if (!item) throw new Error(`Cannot externally control missing room prop ${id}`);
      if (phase !== 'prepared') throw new Error('External room entry control must be assigned before playback');
      if (enabled) {
        external.add(id);
        item.node.position.copy(item.position); item.node.quaternion.copy(item.quaternion); item.node.scale.copy(item.scale);
      } else {
        external.delete(id); item.node.scale.copy(item.scale).multiplyScalar(HIDDEN_SCALE);
      }
      room.updateMatrixWorld(true);
    },
    setExternalProgress(id, value) {
      const item = byId.get(id);
      if (!item || !external.has(id)) throw new Error(`Room prop ${id} is not externally controlled`);
      if (!Number.isFinite(value)) throw new Error(`Room prop ${id} needs finite external progress`);
      item.factor = THREE.MathUtils.clamp(value, 0, 1);
    },
    getState: () => ({ revision: 7, phase, frameScale: 1, propCount: items.length,
      groups: groups.map(group => ({ name: group.name, count: group.items.length, revealed: group.items.filter(item => item.factor >= .999).length })),
      assets: items.map(item => ({ id: item.id, gesture: item.profile[0], motionLabel: MOTION_LABELS[item.profile[0]], motionName: item.choreography.name, motionProfile: item.choreography, externalControlled: external.has(item.id), duration: item.duration, delay: item.profile[1], start: item.at, factor: item.factor, support: supports.get(item.id) ?? null })) }),
  };
}
