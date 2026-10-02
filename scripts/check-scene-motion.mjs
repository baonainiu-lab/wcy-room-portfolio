import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { createSceneMotion } from '../src/scene-motion.js';
import { actualFixture, verticesIn, floorHull, separatingGap } from './lib/scene-motion-geometry.mjs';

// Real Three/GSAP objects, deterministic time, no WebGL or texture decoding.
const EPS = 1e-10;
const expectedIds = [
  'furniture.work_chair', 'robot_companion', 'robot_leg_00', 'robot_leg_01', 'robot_leg_02', 'flower_petal_0', 'flower_petal_1',
  'flower_petal_2', 'speaker_gimbal', 'v5_scout_drone',
  'v5_clock_dial', 'v5_projector_lens', 'v5_data_panel_selector',
  'original_trefoil_geometry', 'v5_floor_lamp_head', 'communicator_panel_1',
];
const results = [];
const position = node => node.position.toArray();
const rotation = node => node.quaternion.toArray();
function close(actual, expected, label, epsilon = EPS) {
  assert.equal(actual.length, expected.length, label);
  actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) <= epsilon,
    `${label}[${index}]: ${value} != ${expected[index]}`));
}
function pose(node) {
  return [...position(node), ...rotation(node), ...node.scale.toArray()];
}
function unchanged(nodes, original, label) {
  for (const node of nodes) close(pose(node), original.get(node), `${label}: ${node.name}`);
}
function snapshot(nodes) {
  return new Map([...nodes].map(node => [node, pose(node)]));
}
function frames(motion, count, options = {}, delta = 1 / 120) {
  for (let index = 0; index < count; index++) motion.update(delta, options);
}
function movedDuring(motion, nodes, count, options = {}) {
  const before = snapshot(nodes), moved = new Set();
  for (let index = 0; index < count; index++) {
    motion.update(1 / 120, options);
    for (const node of nodes) if (pose(node).some((value, i) => Math.abs(value - before.get(node)[i]) > EPS)) moved.add(node);
  }
  return moved;
}
function check(label, run) {
  const detail = run() ?? {};
  results.push({ check: label, status: 'passed', ...detail });
}
function fixture() {
  const scene = new THREE.Scene();
  const room = new THREE.Group(); room.name = 'room'; scene.add(room);
  const components = new Map(); const snapshots = new WeakMap();
  function asset(id, parent = room) {
    const node = new THREE.Group(); node.name = id; node.userData.asset_id = id;
    parent.add(node); components.set(id, node); return node;
  }
  const chair = asset('furniture.work_chair'); chair.rotation.set(.1, .2, -.15);
  const chairChild = asset('chair-unanimated-child', chair);
  const robot = asset('robot_companion'); robot.position.set(-3.23,.18,2.58);
  [[.1717,.413,.1113],[-.1717,.413,.1113],[0,.413,-.185]].forEach((p,i)=>asset(`robot_leg_0${i}`,robot).position.fromArray(p));
  const flower = asset('kinetic_three_petal_flower'); flower.position.set(1, .6, -.8);
  for (let i = 0; i < 3; i++) {
    const node = asset(`flower_petal_${i}`, flower); node.rotation.set(.1, i * 2, .3);
  }
  const petalChild = asset('petal-unanimated-child', components.get('flower_petal_1'));
  const speaker = asset('ceramic_ring_speaker');
  asset('speaker_gimbal', speaker).rotation.set(-.2, .3, .15);
  const droneBase = asset('v5_scout_drone_display');
  droneBase.position.set(2.4, .9, -.3); droneBase.scale.setScalar(1.14);
  droneBase.rotation.set(Math.PI / 2, -.36, .27);
  const drone = asset('v5_scout_drone', droneBase);
  drone.position.set(.2, .4, .3); drone.scale.set(.6, .9, 1.1);
  for (const id of expectedIds.slice(10)) asset(id).position.set(.2, .3, -.4);
  components.get('original_trefoil_geometry').rotation.set(1.18, -.30, .21);
  asset('unanimated-independent-cup').position.set(-1, .7, .8);
  scene.updateMatrixWorld(true);
  scene.traverse(node => snapshots.set(node, {
    position: node.position.clone(), rotation: node.rotation.clone(), scale: node.scale.clone(),
  }));
  return { scene, room, components, snapshots, flower, chair, chairChild, petalChild, drone, droneBase, robot };
}
function worldLift(f, seconds = 18) {
  const motion = createSceneMotion(f);
  f.scene.updateMatrixWorld(true);
  const origin = f.drone.getWorldPosition(new THREE.Vector3());
  const delta = new THREE.Vector3(); let maxVertical = 0, maxHorizontal = 0;
  for (let index = 0; index < seconds * 120; index++) {
    motion.update(1 / 120);
    f.drone.getWorldPosition(delta).sub(origin);
    maxVertical = Math.max(maxVertical, Math.abs(delta.y));
    maxHorizontal = Math.max(maxHorizontal, Math.hypot(delta.x, delta.z));
  }
  assert.ok(maxVertical <= .06 + EPS, `world lift exceeds 6 cm: ${maxVertical}`);
  assert.ok(maxVertical > .04, 'world lift actually occurs');
  assert.ok(maxHorizontal < EPS, `world lift is not vertical: ${maxHorizontal}`);
  return { maxVerticalMetres: maxVertical, maxHorizontalMetres: maxHorizontal };
}

try {
  check('Sixteen independent components move over their schedules; hierarchy, other assets and all scales stay intact', () => {
    const f = fixture(); const motion = createSceneMotion(f);
    const nodes = [...f.components.values()]; const original = snapshot(nodes);
    const parents = new Map(nodes.map(node => [node, node.parent]));
    assert.deepEqual(motion.getState().assetIds, expectedIds);
    const untouched = nodes.filter(node => !expectedIds.includes(node.userData.asset_id));
    const moved = movedDuring(motion, nodes, 24 * 120);
    unchanged(untouched, original, 'unrelated asset');
    for (const node of nodes) {
      assert.equal(node.parent, parents.get(node), `${node.name} parent preserved`);
      close(node.scale.toArray(), original.get(node).slice(7), `${node.name} scale preserved`);
      assert.equal(f.components.get(node.userData.asset_id), node, `${node.name} independently addressable`);
    }
    for (const id of expectedIds) assert.ok(moved.has(f.components.get(id)), `${id} moves during its schedule`);
  });
  check('Drone remains world-vertical and within 6 cm under rotated, 1.14-scaled parent', () => worldLift(fixture()));
  check('Reduced motion performs zero transform writes', () => {
    const f = fixture(); const motion = createSceneMotion({ ...f, reducedMotion: true });
    let writes = 0;
    for (const node of f.components.values()) {
      for (const [object, keys] of [[node.position, ['x', 'y', 'z']], [node.scale, ['x', 'y', 'z']], [node.rotation, ['_x', '_y', '_z']], [node.quaternion, ['_x', '_y', '_z', '_w']]]) {
        for (const key of keys) {
          let value = object[key];
          Object.defineProperty(object, key, { configurable: true, get: () => value, set(next) { writes++; value = next; } });
        }
      }
    }
    frames(motion, 120); motion.hold(f.flower); motion.update(60, { hovered: f.drone });
    assert.equal(writes, 0); assert.equal(motion.getState().activeCount, 0);
  });
  check('Modal/drag disable pauses transforms and motion time; resume matches uninterrupted active time', () => {
    const a = fixture(), b = fixture(); const ma = createSceneMotion(a), mb = createSceneMotion(b);
    frames(ma, 90); frames(mb, 90);
    const before = snapshot(a.components.values());
    frames(ma, 100, { enabled: false }, 60);
    unchanged(a.components.values(), before, 'disabled');
    assert.equal(ma.getState().activeCount, 0);
    ma.update(1 / 120); mb.update(1 / 120);
    for (const id of expectedIds) close(pose(a.components.get(id)), pose(b.components.get(id)), `resumed ${id}`);
  });
  check('Hover ownership excludes both ancestors and descendants, while unrelated pieces keep moving', () => {
    for (const [hoverKey, blockedIds] of [
      ['robot', ['robot_companion', 'robot_leg_00', 'robot_leg_01', 'robot_leg_02']],
      ['flower', ['flower_petal_0', 'flower_petal_1', 'flower_petal_2']],
      ['petalChild', ['flower_petal_1']],
      ['chairChild', ['furniture.work_chair']],
      ['droneBase', ['v5_scout_drone']],
    ]) {
      const f = fixture(); const motion = createSceneMotion(f); const before = snapshot(f.components.values());
      const moved = movedDuring(motion, [...f.components.values()], 24 * 120, { hovered: f[hoverKey] });
      unchanged(blockedIds.map(id => f.components.get(id)), before, `hover ${hoverKey}`);
      for (const id of expectedIds.filter(id => !blockedIds.includes(id))) {
        assert.ok(moved.has(f.components.get(id)), `${hoverKey} must not block ${id}`);
      }
      const released = movedDuring(motion, blockedIds.map(id => f.components.get(id)), 24 * 120, { hovered: null });
      for (const id of blockedIds) assert.ok(released.has(f.components.get(id)), `${id} releases after hover`);
    }
  });
  check('Click hold covers the whole related assembly, survives disabled time, and resumes only after active hold time', () => {
    const f = fixture(); const motion = createSceneMotion(f);
    const petals = [0, 1, 2].map(index => f.components.get(`flower_petal_${index}`));
    const before = snapshot(petals); motion.hold(f.flower, 1.8);
    frames(motion, 120); frames(motion, 50, { enabled: false }, 60);
    frames(motion, 90); unchanged(petals, before, '1.75 seconds held');
    frames(motion, 240);
    for (const petal of petals) assert.notDeepEqual(pose(petal), before.get(petal), 'hold eventually releases');
  });
  check('Real GSAP rotation/position/quaternion tweens own their transforms even after click hold expires', () => {
    for (const [id, property, axis] of [['speaker_gimbal', 'rotation', 'z'], ['v5_scout_drone', 'position', 'y'], ['original_trefoil_geometry', 'quaternion', 'y']]) {
      const f = fixture(); const motion = createSceneMotion(f); const node = f.components.get(id);
      motion.hold(node, .1);
      const tween = gsap.to(node[property], { [axis]: node[property][axis] + .1, duration: 5, ease: 'none' });
      gsap.ticker.sleep(); tween.totalTime(.5, false);
      assert.ok(gsap.isTweening(node[property]), `real GSAP tween must be active for ${id}`);
      const value = pose(node); frames(motion, 180);
      close(pose(node), value, `${id} external tween is not overwritten`);
      tween.kill(); motion.update(1 / 120);
      assert.notDeepEqual(pose(node), value, `${id} resumes after tween is killed`);
    }
  });
  check('Long tab delta is clamped; negative delta cannot rewind the motion clock', () => {
    const a = fixture(), b = fixture(); const ma = createSceneMotion(a), mb = createSceneMotion(b);
    frames(ma, 90); frames(mb, 90); ma.update(300); mb.update(.05);
    for (const id of expectedIds) close(pose(a.components.get(id)), pose(b.components.get(id)), `tab restore ${id}`);
    ma.update(-5); mb.update(0); ma.update(1 / 120); mb.update(1 / 120);
    for (const id of expectedIds) close(pose(a.components.get(id)), pose(b.components.get(id)), `negative delta ${id}`);
  });
  check('Chair completes repeated full revolutions around a fixed parent-vertical swivel with no reverse jump', () => {
    const f = fixture(), motion = createSceneMotion(f), chair = f.chair;
    const startPosition = chair.position.toArray(), startScale = chair.scale.toArray();
    const original = chair.quaternion.clone(), relative = new THREE.Quaternion();
    let last = new THREE.Vector3(1, 0, 0), travel = 0, maxSpeed = 0;
    for (let frame = 0; frame < 45 * 120; frame++) {
      motion.update(1 / 120);
      relative.copy(chair.quaternion).multiply(original.clone().invert());
      const current = new THREE.Vector3(1, 0, 0).applyQuaternion(relative);
      const angle = Math.atan2(new THREE.Vector3().crossVectors(last, current).y, last.dot(current));
      assert.ok(angle >= -EPS, 'swivel does not reverse at a cycle boundary');
      travel += angle; maxSpeed = Math.max(maxSpeed, Math.abs(angle) * 120); last = current;
      close(chair.position.toArray(), startPosition, 'fixed swivel pivot');
      close(chair.scale.toArray(), startScale, 'fixed chair scale');
    }
    assert.ok(travel > Math.PI * 4, 'chair completes at least two full turns');
    assert.ok(maxSpeed < 1, 'slow swivel remains smooth');
    return { totalTurns: travel / (2 * Math.PI), maxRadiansPerSecond: maxSpeed };
  });
  check('Actual mechanical face normals, fixed pivots, lens travel and enclosed sculpture use the intended axes', () => {
    const f = actualFixture(), motion = createSceneMotion(f), lens = f.components.get('v5_projector_lens');
    const pivotIds = ['v5_clock_dial', 'v5_data_panel_selector', 'original_trefoil_geometry', 'v5_floor_lamp_head', 'communicator_panel_1'];
    const pivots = new Map(pivotIds.map(id => [id, position(f.components.get(id))]));
    const faceDimensions = {};
    for (const id of ['v5_clock_dial', 'v5_projector_lens', 'v5_data_panel_selector']) {
      const node = f.components.get(id), size = new THREE.Box3().setFromPoints(verticesIn(node, node)).getSize(new THREE.Vector3());
      assert.ok(size.x > size.z * 1.5 && size.y > size.z * 1.5, `${id}: glTF face is XY, spindle is Z`);
      faceDimensions[id] = size.toArray();
    }
    const lensStart = lens.position.clone(); let maxLensTravel = 0;
    for (let frame = 0; frame < 40 * 120; frame++) {
      motion.update(1 / 120);
      maxLensTravel = Math.max(maxLensTravel, lens.position.z - lensStart.z);
      assert.equal(lens.position.x, lensStart.x); assert.equal(lens.position.y, lensStart.y);
      for (const [id, original] of pivots) close(position(f.components.get(id)), original, `${id}: hinge remains fixed`);
    }
    assert.ok(maxLensTravel > .009 && maxLensTravel <= .01 + EPS, 'focus barrel extends at most one centimetre');
    const sculpture = f.components.get('original_trefoil_geometry');
    const points = verticesIn(sculpture, sculpture.parent);
    const profile = [[.05, .204], [.08, .208], [.386, .208], [.455, .196], [.511, .159], [.551, .102], [.571, .028]];
    let minimumClearance = Infinity;
    for (const point of points) {
      const section = profile.findIndex(([height]) => height >= point.y);
      assert.ok(section > 0, 'sculpture lies within the glass display height');
      const [bottom, bottomRadius] = profile[section - 1], [top, topRadius] = profile[section];
      const innerRadius = bottomRadius + (topRadius - bottomRadius) * ((point.y - bottom) / (top - bottom));
      minimumClearance = Math.min(minimumClearance, innerRadius - Math.hypot(point.x, point.z));
    }
    assert.ok(minimumClearance > .008, 'parent-vertical rotation preserves clearance to the revolved glass enclosure');
    return { faceDimensionsMetres: faceDimensions, maxLensTravelMetres: maxLensTravel, sculptureRadialClearanceMetres: minimumClearance };
  });
  check('Actual chair sweep keeps a separating floor-plane gap to the workstation across the full 360 degrees at 1-degree samples', () => {
    const f = actualFixture(), chair = f.components.get('furniture.work_chair');
    const deskHull = floorHull(verticesIn(f.components.get('furniture.desk'), f.room));
    const localVertices = verticesIn(chair, chair), initialAngle = chair.rotation.y;
    let minimumGap = Infinity;
    const sweptBounds = new THREE.Box3();
    for (let degree = 0; degree < 360; degree++) {
      chair.rotation.y = initialAngle + degree * Math.PI / 180; chair.updateWorldMatrix(true, false);
      const worldVertices = localVertices.map(point => point.clone().applyMatrix4(chair.matrixWorld));
      const chairHull = floorHull(worldVertices); minimumGap = Math.min(minimumGap, separatingGap(chairHull, deskHull));
      for (const point of worldVertices) sweptBounds.expandByPoint(point);
    }
    assert.ok(minimumGap > .01, `chair's sampled swept footprint stays outside the desk: ${minimumGap}`);
    return { sampledPoses: 360, minimumSeparatingGapMetres: minimumGap, sweptBoundsMin: sweptBounds.min.toArray(), sweptBoundsMax: sweptBounds.max.toArray(), limitation: 'Desk footprint check across the full 360 degrees at 1-degree samples; not continuous full-room collision detection' };
  });
  check('Actual active GLB keeps every asset independently addressable, with bounded drone movement', () => {
    const actual = actualFixture(); const { nodes, components, modelPath } = actual;
    const original = snapshot(nodes);
    const parents = new Map(nodes.map(node => [node, node.parent]));
    assert.ok(actual.drone, 'actual independent drone exists');
    const detail = worldLift(actual);
    for (const node of nodes) {
      assert.equal(node.parent, parents.get(node), `${node.name}: original parent`);
      close(node.scale.toArray(), original.get(node).slice(7), `${node.name}: original scale`);
      if (!expectedIds.includes(node.userData.asset_id)) close(pose(node), original.get(node), `${node.name}: not animated`);
    }
    return { modelPath, independentlyAddressableAssets: components.size, ...detail };
  });
  check('Full-room patrol uses authored scales, limits hover growth in narrow passages, and visits the connected floor while preserving local pause clocks', () => {
    const f = actualFixture(), motion = createSceneMotion(f), robot = f.components.get('robot_companion');
    const route = motion.getState().robot.route, originalScale = robot.scale.clone();
    assert.equal(route.scope, 'connected-room-floor');
    const bounds = new THREE.Box3(), activities = new Set(); let compactFrames = 0, openFrames = 0;
    const framesInRoute = Math.ceil((route.departureSeconds + route.durationSeconds) * 120);
    for (let frame = 0; frame < framesInRoute; frame++) {
      motion.update(1 / 120); const state = motion.getState().robot;
      bounds.expandByPoint(robot.position); activities.add(state.activity);
      assert.deepEqual(robot.scale.toArray(), originalScale.toArray(), 'narrow route never shrinks the model');
      if (state.compact > .02) { compactFrames++; assert.equal(motion.getHoverScaleLimit(robot), 1, 'compact passages suppress hover growth'); }
      else { openFrames++; assert.equal(motion.getHoverScaleLimit(robot), Infinity, 'open floor retains normal hover behavior'); }
    }
    assert.ok(compactFrames > 0 && openFrames > 0, 'both narrow and open configurations occur');
    assert.ok(bounds.max.x > 4 && bounds.min.x < -3 && bounds.min.z < -1.4 && bounds.max.z > 2.9, 'route reaches connected front/right/rear areas');
    assert.ok(activities.has('looking-around') && activities.has('patrolling') && activities.has('side-stepping'), 'patrol, narrow side-step and observation phases all occur');
    return { route, compactFrames, openFrames, activities: [...activities], visitedBoundsMin: bounds.min.toArray(), visitedBoundsMax: bounds.max.toArray() };
  });
  const hash = path => createHash('sha256').update(readFileSync(new URL(path, import.meta.url))).digest('hex');
  const report = { ok: true, revision: createSceneMotion(fixture()).getState().revision, generatedAt: new Date().toISOString(), scope: 'Deterministic Three.js + GSAP motion and actual GLB hierarchy; no render/FPS claim', hashes: { sceneMotion: hash('../src/scene-motion.js'), robotPatrol: hash('../src/robot-patrol.js'), fixture: hash('./lib/scene-motion-geometry.mjs'), test: hash('./check-scene-motion.mjs') }, results };
  if (process.argv.includes('--write-report')) writeFileSync(new URL(`../docs/validation/scene-motion-v${report.revision}.json`, import.meta.url), JSON.stringify(report, null, 2)+'\n');
  console.log(JSON.stringify(report, null, 2));
} finally {
  gsap.globalTimeline.clear(); gsap.ticker.sleep();
}
