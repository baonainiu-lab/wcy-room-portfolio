import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { bindIntroInput } from '../src/intro-input.js';
import { createRoomEntry, ROOM_ENTRY_GROUPS, ROOM_ENTRY_MOTIONS } from '../src/room-entry.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

// Actual EventTargets + actual V16 vertices, indices, pivots and hierarchy.
// No fake clock, browser, screenshot, WebGL, atlas decode or visual assertions.
const checks = [];
function check(name, callback) {
  try { checks.push({ check: name, status: 'passed', ...callback() }); }
  catch (error) { checks.push({ check: name, status: 'failed', error: error.stack }); }
}
function emit(target, type, properties = {}) {
  const event = Object.assign(new Event(type, { cancelable: true }), properties);
  target.dispatchEvent(event); return event;
}
function inputFixture(width = 1440) {
  const view = new EventTarget(), element = new EventTarget(); view.innerWidth = width;
  let allowed = true, skipped = 0; const starts = [];
  const cleanup = bindIntroInput({ view, element, canEnter: () => allowed,
    onEnter(source) { starts.push(source); allowed = false; }, onSkip() { skipped++; } });
  return { view, element, starts, cleanup, get skipped() { return skipped; } };
}
function touches(...ys) { return ys.map((clientY, identifier) => ({ clientY, identifier })); }

check('first downward wheel enters once; repeated momentum and reverse wheel stay locked', () => {
  const f = inputFixture(); let downstream = 0;
  f.view.addEventListener('wheel', () => downstream++);
  try {
    for (const deltaY of [-30, 0]) assert.equal(emit(f.view, 'wheel', { deltaY }).defaultPrevented, true);
    assert.deepEqual(f.starts, []);
    emit(f.view, 'wheel', { deltaY: 40, ctrlKey: true }); assert.deepEqual(f.starts, [], 'pinch/zoom wheel does not enter');
    for (const deltaY of [1, 10, 22, -14, 0, 300]) assert.equal(emit(f.view, 'wheel', { deltaY }).defaultPrevented, true);
    assert.deepEqual(f.starts, ['wheel']); assert.equal(downstream, 0, 'camera never receives intro wheel events');
  } finally { f.cleanup(); }
});
check('single-finger up swipe enters once; downward swipe and cancelled touches do not', () => {
  const f = inputFixture(390);
  try {
    emit(f.view, 'touchstart', { touches: touches(200) });
    emit(f.view, 'touchmove', { touches: touches(240) }); assert.deepEqual(f.starts, []);
    emit(f.view, 'touchcancel', { touches: [] });
    emit(f.view, 'touchmove', { touches: touches(140) }); assert.deepEqual(f.starts, []);
    emit(f.view, 'touchstart', { touches: touches(240) });
    assert.equal(emit(f.view, 'touchmove', { touches: touches(200) }).defaultPrevented, true);
    emit(f.view, 'touchmove', { touches: touches(160) });
    emit(f.view, 'touchend', { touches: [] });
    emit(f.view, 'touchstart', { touches: touches(240) }); emit(f.view, 'touchmove', { touches: touches(100) });
    assert.deepEqual(f.starts, ['touch']);
  } finally { f.cleanup(); }
});
check('multi-touch gestures never trigger entry, including browser touch + pointer event streams', () => {
  const f = inputFixture(390);
  try {
    emit(f.element, 'pointerdown', { pointerType: 'touch', pointerId: 1, isPrimary: true, button: 0, clientX: 80, clientY: 250 });
    emit(f.view, 'touchstart', { touches: touches(250, 270) });
    emit(f.element, 'pointermove', { pointerType: 'touch', pointerId: 1, isPrimary: true, clientX: 80, clientY: 180 });
    emit(f.view, 'touchmove', { touches: touches(180, 200) });
    emit(f.view, 'touchend', { touches: touches(180) });
    emit(f.view, 'touchmove', { touches: touches(90) });
    assert.deepEqual(f.starts, [], 'the primary pointer of a two-finger gesture must not bypass the touch guard');
    emit(f.view, 'touchend', { touches: [] }); emit(f.element, 'pointerup', { pointerId: 1 });
    emit(f.view, 'touchstart', { touches: touches(250) }); emit(f.view, 'touchmove', { touches: touches(200) });
    assert.deepEqual(f.starts, ['touch'], 'a fresh one-finger gesture still works');
  } finally { f.cleanup(); }
});
check('compact mouse/pen swipe respects vertical intent and pointer cancellation', () => {
  const f = inputFixture(390);
  try {
    emit(f.element, 'pointerdown', { pointerType: 'pen', pointerId: 7, isPrimary: true, button: 0, clientX: 80, clientY: 250 });
    emit(f.element, 'pointermove', { pointerId: 7, clientX: 230, clientY: 220 }); assert.deepEqual(f.starts, []);
    emit(f.element, 'pointercancel', { pointerId: 7 });
    emit(f.element, 'pointermove', { pointerId: 7, clientX: 80, clientY: 150 }); assert.deepEqual(f.starts, []);
    emit(f.element, 'pointerdown', { pointerType: 'pen', pointerId: 8, isPrimary: true, button: 0, clientX: 80, clientY: 250 });
    emit(f.element, 'pointermove', { pointerId: 8, clientX: 82, clientY: 200 });
    emit(f.element, 'pointermove', { pointerId: 8, clientX: 84, clientY: 120 });
    assert.deepEqual(f.starts, ['swipe']);
  } finally { f.cleanup(); }
});
check('keyboard entry is one-shot; Escape remains available during playback', () => {
  const f = inputFixture();
  try {
    for (const key of ['ArrowUp', 'PageUp', 'Home', 'End']) assert.equal(emit(f.view, 'keydown', { key }).defaultPrevented, true);
    assert.deepEqual(f.starts, []);
    emit(f.view, 'keydown', { key: 'ArrowDown' });
    for (const key of ['ArrowDown', 'PageDown', ' ']) emit(f.view, 'keydown', { key });
    assert.deepEqual(f.starts, ['keyboard']);
    assert.equal(emit(f.view, 'keydown', { key: 'Escape' }).defaultPrevented, true);
    assert.equal(f.skipped, 1);
  } finally { f.cleanup(); }
});
check('native button Space stays available; click/keyboard share a guarded controller entry', () => {
  const f = inputFixture();
  try {
    const space = new Event('keydown', { cancelable: true });
    Object.defineProperties(space, { key: { value: ' ' }, target: { value: { closest: selector => selector === 'button' ? {} : null } } });
    f.view.dispatchEvent(space); assert.equal(space.defaultPrevented, false); assert.deepEqual(f.starts, []);
    const source = readFileSync(new URL('../src/cube-intro.js', import.meta.url), 'utf8');
    const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
    assert.match(html, /<button[^>]*class="intro-enter"[^>]*type="button"/);
    assert.match(source, /function clickEnter\(\)\s*\{\s*enter\('click'\)/);
    assert.match(source, /function enter\([^)]*\)\s*\{\s*if \(phase !== 'welcome'\) return false;/);
    assert.match(source, /enterButton\.addEventListener\('click', clickEnter\)/);
    assert.match(source, /enterButton\.removeEventListener\('click', clickEnter\)/);
    return { note: 'Native-button key default and input handler executed; controller click wiring/phase gate inspected statically. Actual browser click checked separately.' };
  } finally { f.cleanup(); }
});
check('cleanup is idempotent and releases all wheel, keyboard, touch and pointer locks', () => {
  const f = inputFixture(390); f.cleanup(); f.cleanup();
  let reached = 0;
  for (const name of ['wheel', 'touchmove', 'keydown']) f.view.addEventListener(name, () => reached++);
  assert.equal(emit(f.view, 'wheel', { deltaY: 20 }).defaultPrevented, false);
  emit(f.view, 'touchstart', { touches: touches(200) });
  assert.equal(emit(f.view, 'touchmove', { touches: touches(80) }).defaultPrevented, false);
  assert.equal(emit(f.view, 'keydown', { key: 'ArrowDown' }).defaultPrevented, false);
  emit(f.view, 'keydown', { key: 'Escape' });
  emit(f.element, 'pointerdown', { pointerId: 3, button: 0, clientX: 20, clientY: 200 });
  emit(f.element, 'pointermove', { pointerId: 3, clientX: 20, clientY: 100 });
  assert.equal(reached, 4); assert.deepEqual(f.starts, []); assert.equal(f.skipped, 0);
});

function close(actual, expected, label, epsilon = 1e-11) {
  assert.equal(actual.length, expected.length, label);
  actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) <= epsilon, `${label}[${i}]: ${value} != ${expected[i]}`));
}
function capture(scene) {
  scene.updateMatrixWorld(true); const state = new Map();
  scene.traverse(node => state.set(node, { parent: node.parent, children: [...node.children],
    id: node.userData.asset_id, position: node.position.toArray(), rotation: node.rotation.toArray(),
    quaternion: node.quaternion.toArray(), scale: node.scale.toArray(), world: node.matrixWorld.toArray(), visible: node.visible }));
  return state;
}
function sameTopology(records) {
  for (const [node, old] of records) {
    assert.equal(node.parent, old.parent, `${node.name}: parent remains unchanged`);
    assert.deepEqual(node.children, old.children, `${node.name}: independent children remain unchanged`);
    assert.equal(node.userData.asset_id, old.id, `${node.name}: stable interactive ID`);
  }
}
function restored(scene, records, label) {
  scene.updateMatrixWorld(true); sameTopology(records);
  for (const [node, old] of records) {
    close(node.position.toArray(), old.position, `${label}:${node.name}:position`, 1e-12);
    close(node.quaternion.toArray(), old.quaternion, `${label}:${node.name}:quaternion`, 1e-12);
    close(node.scale.toArray(), old.scale, `${label}:${node.name}:scale`, 1e-12);
    close(node.rotation.toArray().slice(0, 3), old.rotation.slice(0, 3), `${label}:${node.name}:Euler`, 1e-12);
    assert.equal(node.rotation.order, old.rotation[3], `${label}:${node.name}:Euler order`);
    close(node.matrixWorld.toArray(), old.world, `${label}:${node.name}:world`, 1e-10);
    assert.equal(node.visible, old.visible, `${label}:${node.name}:visibility`);
  }
}
function fixture(transformed = false) {
  const actual = readRoomGeometry('/models/orbital-atelier-v16-compressed.glb');
  const scene = new THREE.Scene(), parent = new THREE.Group(); scene.add(parent); parent.add(actual.room);
  const exterior = new THREE.Group(); scene.add(exterior);
  for (const id of ['environment.orbital_dock', 'environment.warm_gallery']) exterior.add(actual.components.get(id));
  const roots = new Map(actual.room.children.filter(n => n.userData.asset_id).map(n => [n.userData.asset_id, n]));
  if (transformed) {
    parent.position.set(3, -2, 1); parent.rotation.set(.12, -.3, .05); parent.scale.set(1.3, .8, 1.1);
    actual.room.position.set(.3, .2, -.5); actual.room.rotation.set(.04, .18, -.05); actual.room.scale.set(1.2, .9, 1.1);
    roots.get('furniture.desk').scale.set(1.16, .82, 1.08);
  }
  scene.updateMatrixWorld(true);
  const snapshots = new WeakMap();
  scene.traverse(n => snapshots.set(n, { position: n.position.clone(), rotation: n.rotation.clone(), scale: n.scale.clone() }));
  return { ...actual, scene, roots, exterior, snapshots, bounds: new THREE.Box3().setFromObject(actual.room) };
}
function runAssembly({ transformed = false, interruption = false }) {
  const f = fixture(transformed), records = capture(f.scene);
  const originalComponentIds = [...f.components.keys()].sort();
  const ids = ROOM_ENTRY_GROUPS.flatMap(([, ids]) => ids);
  assert.equal(f.roots.size, 37); assert.equal(f.components.size, 95);
  assert.equal(new Set(ids).size, ids.length, 'no asset appears in two animation groups');
  assert.deepEqual([...ids, 'architecture.platform'].sort(), [...f.roots.keys()].sort(), 'every prop root has a reveal; platform belongs to the structural animation');
  const floorWorld = f.bounds.getCenter(new THREE.Vector3()); floorWorld.y = f.bounds.min.y;
  const floorLocal = f.room.worldToLocal(floorWorld.clone());
  const staticNode = f.room.children.find(n => !n.userData.asset_id && n.children.some(c => c.isMesh));
  const staticMesh = staticNode.children.find(n => n.isMesh);
  const staticPoint = new THREE.Vector3().fromBufferAttribute(staticMesh.geometry.attributes.position, 0);
  const staticOriginal = staticMesh.localToWorld(staticPoint.clone());
  const geometryDigests = new Map();
  f.scene.traverse(node => { if (node.isMesh) {
    const attribute = node.geometry.attributes.position;
    geometryDigests.set(attribute, createHash('sha256').update(new Uint8Array(attribute.array.buffer, attribute.array.byteOffset, attribute.array.byteLength)).digest('hex'));
  } });
  const entry = createRoomEntry(f); assert.equal(entry.getState().phase, 'prepared'); assert.equal(f.room.visible, true);
  assert.equal(entry.getState().revision, 7); assert.equal(entry.getState().frameScale, 1);
  const timeline = gsap.timeline({ paused: true }); const start = .5, end = entry.appendTo(timeline, start);
  let observedChairTurn = false, partiallyRevealed = false;
  try {
    const samples = interruption ? [start + .25, start + 1.35, start + 2.1] : [start + .25, start + 1.35, start + 1.8, start + 2.1, start + 2.5, start + 2.9, start + 3.25, end];
    for (const time of samples) {
      timeline.time(time, false); entry.update(); f.scene.updateMatrixWorld(true);
      const state = entry.getState(); const factor = state.frameScale;
      close(f.room.localToWorld(floorLocal.clone()).toArray(), floorWorld.toArray(), `fixed real-geometry floor anchor @${time}`, 1e-8);
      close(staticMesh.localToWorld(staticPoint.clone()).toArray(), staticOriginal.clone().sub(floorWorld).multiplyScalar(factor).add(floorWorld).toArray(), `actual wall vertex remains owned by the structural animation @${time}`, 1e-8);
      for (const node of f.components.values()) {
        if (!f.roots.has(node.userData.asset_id) && !node.userData.asset_id.startsWith('environment.')) {
          const old = records.get(node);
          close(node.position.toArray(), old.position, `${node.name}: child local position untouched`);
          close(node.quaternion.toArray(), old.quaternion, `${node.name}: child local rotation untouched`);
          close(node.scale.toArray(), old.scale, `${node.name}: child scale not animated twice`);
        }
      }
      f.exterior.traverse(node => close(node.matrixWorld.toArray(), records.get(node).world, `${node.name}: external asset is not part of room assembly`));
      assert.deepEqual([...f.components.keys()].sort(), originalComponentIds); sameTopology(records);
      const chair = f.roots.get('furniture.work_chair');
      observedChairTurn ||= chair.quaternion.toArray().some((v, i) => Math.abs(v - records.get(chair).quaternion[i]) > .02);
      partiallyRevealed ||= state.groups.some(g => g.revealed > 0 && g.revealed < g.count);
    }
    if (!interruption) {
      assert.ok(observedChairTurn, 'chair actually turns before returning');
      assert.ok(partiallyRevealed, 'independent props reveal at different times, not as a single pop');
      assert.ok(entry.getState().groups.every(g => g.revealed === g.count));
    }
  } finally { timeline.kill(); entry.restore(); }
  restored(f.scene, records, interruption ? 'interrupted' : 'complete');
  entry.restore(); entry.update(); restored(f.scene, records, 'idempotent restore + later update');
  for (const [attribute, digest] of geometryDigests) assert.equal(createHash('sha256').update(new Uint8Array(attribute.array.buffer, attribute.array.byteOffset, attribute.array.byteLength)).digest('hex'), digest, 'animation never rewrites mesh vertices');
  const geometrySummary = { modelUrl: f.modelUrl, roots: f.roots.size, independentlyIdentifiedComponents: f.components.size,
    animatedPropRoots: ids.length, frameOnlyRoots: ['architecture.platform'], groups: entry.getState().groups,
    meshes: geometryDigests.size, triangles: f.data.meshes.reduce((total, mesh) => total + mesh.primitives.reduce((sum, p) => sum + f.data.accessors[p.indices ?? p.attributes.POSITION].count / 3, 0), 0), duration: Number((end - start).toFixed(3)), transformedParent: transformed,
    interrupted: interruption, oldDeskPosition: records.get(f.roots.get('furniture.desk')).position };
  f.scene.traverse(node => { if (node.isMesh) { node.geometry.dispose(); node.material.dispose(); } });
  return geometrySummary;
}
check('actual V16 room remains visible while every prop assembles and 95 independent components restore', () => runAssembly({}));
check('nonuniform transformed parent/room/desk preserve floor anchor, nested children and final original pose', () => runAssembly({ transformed: true }));
check('mid-assembly skip recovery restores actual room and desk offset; later updates cannot re-hide it', () => runAssembly({ transformed: true, interruption: true }));

function choreographyFixture(transformed = false) {
  const f = fixture(transformed), originals = capture(f.scene), anchors = new Map();
  for (const [id, node] of f.roots) {
    const box = new THREE.Box3().setFromObject(node), world = box.getCenter(new THREE.Vector3()); world.y = box.min.y;
    anchors.set(id, { local: node.worldToLocal(world.clone()), parent: node.parent.worldToLocal(world.clone()) });
  }
  const entry = createRoomEntry(f), timeline = gsap.timeline({ paused: true }), end = entry.appendTo(timeline, .5);
  const tweens = new Map(timeline.getChildren(false, true, false).filter(tween => tween.vars.factor !== undefined)
    .map(tween => [tween.targets()[0].id, tween]));
  function sample(id, progress = .12) {
    const node = f.roots.get(id), tween = tweens.get(id), original = originals.get(node), anchor = anchors.get(id);
    assert.ok(tween, `${id}: independent size timeline exists`);
    timeline.time(tween.startTime() + tween.duration() * progress, false); entry.update(); f.scene.updateMatrixWorld(true);
    return { scaleRatios: node.scale.toArray().map((v, i) => v / original.scale[i]),
      rotated: node.quaternion.toArray().some((v, i) => Math.abs(v - original.quaternion[i]) > 1e-4),
      actualAnchor: node.localToWorld(anchor.local.clone()), expectedAnchor: node.parent.localToWorld(anchor.parent.clone()),
      parentAnchorDisplacement: node.parent.worldToLocal(node.localToWorld(anchor.local.clone())).sub(anchor.parent) };
  }
  function dispose() {
    timeline.kill(); entry.restore(); restored(f.scene, originals, 'individual-motion recovery');
    f.scene.traverse(node => { if (node.isMesh) { node.geometry.dispose(); node.material.dispose(); } });
  }
  return { ...f, entry, timeline, tweens, originals, anchors, end, sample, dispose };
}
check('all 36 prop roots have explicit individual motion, actual separate timelines and authored offsets', () => {
  const f = choreographyFixture();
  try {
    const animatedIds = [...f.roots.keys()].filter(id => id !== 'architecture.platform').sort();
    assert.deepEqual(Object.keys(ROOM_ENTRY_MOTIONS).sort(), animatedIds, 'no prop silently falls back to the generic body gesture');
    assert.deepEqual([...f.tweens.keys()].filter(id => id !== 'room').sort(), animatedIds, 'each root has its own reveal tween');
    for (const id of animatedIds) {
      const [gesture, delay, pace, tilt] = ROOM_ENTRY_MOTIONS[id];
      assert.equal(typeof gesture, 'string'); assert.ok(Number.isFinite(delay) && delay >= 0);
      assert.ok(Number.isFinite(pace) && Number.isFinite(tilt));
      assert.equal(f.tweens.get(id).targets()[0].node, f.roots.get(id));
    }
    assert.equal(f.tweens.has('room'), false, 'no tween competes with the root layout');
    const starts = new Set([...f.tweens.values()].map(t => Number(t.startTime().toFixed(5))));
    assert.ok(starts.size >= 30, 'props must not collapse into five simultaneous group pops');
    const gestures = [...new Set(f.entry.getState().assets.map(a => a.gesture))];
    assert.ok(gestures.length >= 8, 'authored motion vocabulary includes unfolding, settling, sliding and rotation');
    return { independentPropTimelines: animatedIds.length, uniqueStartTimes: starts.size, gestures };
  } finally { f.dispose(); }
});
check('large desk animates slower than the cup; rotations and suspended arrivals remain readable', () => {
  const f = choreographyFixture();
  try {
    const desk = f.tweens.get('furniture.desk'), cup = f.tweens.get('thermal_cup');
    assert.ok(desk.duration() > cup.duration() + .2, 'desk reveal needs visibly more time than a small cup');
    const expressive = ['ceramic_mobius_study', 'geometric_specimen_cloche'];
    const durations = expressive.map(id => f.tweens.get(id).duration());
    assert.ok(durations.every(duration => duration >= .9), 'spins and suspended arrivals have time to remain visible');
    return { deskSeconds: desk.duration(), cupSeconds: cup.duration(), expressiveAssets: expressive, actualDurations: durations };
  } finally { f.dispose(); }
});
check('distinct unfolding, settling, sliding and rotation trajectories survive safe spatial constraints', () => {
  const f = choreographyFixture(true);
  try {
    const desk = f.sample('furniture.desk'), rug = f.sample('furniture.rug'), keyboard = f.sample('split_keyboard');
    for (const [name, pose] of [['desk', desk], ['rug', rug], ['keyboard', keyboard]]) {
      assert.ok(Math.max(...pose.scaleRatios) - Math.min(...pose.scaleRatios) > .02, `${name}: actual anisotropic unfold`);
      assert.ok(pose.actualAnchor.toArray().every(Number.isFinite), `${name}: support-relative pivot is finite under transformed parents`);
    }
    const cup = f.sample('thermal_cup');
    close([cup.scaleRatios[0]], [cup.scaleRatios[2]], 'cup retains its round footprint');
    assert.ok(cup.scaleRatios[1] <= cup.scaleRatios[0], 'cup uses a restrained vertical landing compression');
    assert.ok(cup.parentAnchorDisplacement.length() > .01, 'cup settles from an offset rather than staying at the expansion anchor');
    const plant = f.sample('trailing_wall_plant');
    assert.ok(plant.scaleRatios[1] > plant.scaleRatios[0] + .02, 'plant unfolds vertically before spreading');
    const panel = f.sample('main_display'); assert.ok(panel.rotated, 'display visibly tilts into position');
    const turning = f.sample('ceramic_mobius_study'); assert.ok(turning.rotated, 'sculpture visibly turns');
    const sliding = f.sample('studio_reference_books');
    assert.ok(sliding.parentAnchorDisplacement.length() > .01, 'books slide from a displaced anchor');
    f.timeline.time(f.end, false); f.entry.update();
    return { comparedAssets: ['furniture.desk', 'furniture.rug', 'split_keyboard', 'thermal_cup', 'trailing_wall_plant', 'main_display', 'ceramic_mobius_study', 'studio_reference_books'],
      deskScaleRatios: desk.scaleRatios, cupScaleRatios: cup.scaleRatios, plantScaleRatios: plant.scaleRatios,
      anchorTolerance: 1e-8, finalRestoreChecked: true };
  } finally { f.dispose(); }
});

check('preparation only epsilon-hides props; root layout, architecture, positions and rotations stay intact', () => {
  const f = fixture(true), original = capture(f.scene), entry = createRoomEntry(f);
  for (const [id, node] of f.roots) {
    const before = original.get(node);
    close(node.position.toArray(), before.position, `${id}: preparation retains local position`);
    close(node.quaternion.toArray(), before.quaternion, `${id}: preparation retains local rotation`);
    close(node.scale.toArray(), before.scale.map(value => value * (id === 'architecture.platform' ? 1 : .00001)), `${id}: preparation scale`);
  }
  close(f.room.position.toArray(), original.get(f.room).position, 'preparation keeps root position');
  close(f.room.quaternion.toArray(), original.get(f.room).quaternion, 'preparation keeps root rotation');
  close(f.room.scale.toArray(), original.get(f.room).scale, 'preparation keeps root scale');
  assert.equal(f.room.visible, original.get(f.room).visible);
  entry.update(); entry.restore(); restored(f.scene, original, 'preparation recovery');
  return { architectureRemainsVisible: true, initialPropScaleMultiplier: .00001 };
});
check('fold parent and global layout remain externally owned during prop animation and restore', () => {
  const f = fixture(), carrier = new THREE.Group(); carrier.name = 'fold.left_wall'; f.room.add(carrier);
  const prop = f.roots.get('c_archive_dock'); carrier.add(prop); // Identity carrier keeps the exact original local TRS.
  f.scene.updateMatrixWorld(true);
  const original = capture(f.scene), entry = createRoomEntry(f), timeline = gsap.timeline({ paused: true });
  entry.appendTo(timeline, .5);
  f.room.position.set(2.1, .7, -1.3); f.room.rotation.set(.1, -.35, .08); f.room.scale.setScalar(.43);
  carrier.position.set(.2, .6, -.1); carrier.rotation.set(.5, -.2, .1);
  const layout = { position: f.room.position.toArray(), quaternion: f.room.quaternion.toArray(), scale: f.room.scale.toArray() };
  const fold = { position: carrier.position.toArray(), quaternion: carrier.quaternion.toArray(), scale: carrier.scale.toArray() };
  const verifyOwners = () => {
    for (const [node, pose] of [[f.room, layout], [carrier, fold]]) {
      close(node.position.toArray(), pose.position, `${node.name}: owner position`);
      close(node.quaternion.toArray(), pose.quaternion, `${node.name}: owner rotation`);
      close(node.scale.toArray(), pose.scale, `${node.name}: owner scale`);
    }
    assert.equal(f.room.visible, true); assert.equal(prop.parent, carrier);
  };
  try {
    for (const time of [1.4, 1.9, 2.2, 2.6]) {
      timeline.time(time, false); entry.update(); f.scene.updateMatrixWorld(true); verifyOwners();
      close(prop.matrixWorld.toArray(), carrier.matrixWorld.clone().multiply(prop.matrix).toArray(), 'prop travels exactly with folded support');
    }
  } finally { timeline.kill(); entry.restore(); }
  verifyOwners();
  for (const node of f.roots.values()) {
    close(node.position.toArray(), original.get(node).position, `${node.name}: final local position`);
    close(node.quaternion.toArray(), original.get(node).quaternion, `${node.name}: final local quaternion`);
    close(node.scale.toArray(), original.get(node).scale, `${node.name}: final local scale`);
  }
  return { externalOwnersPreserved: ['room layout', 'fold.left_wall'], prop: 'c_archive_dock', parentPreserved: true };
});
check('new reveal schedule overlaps groups, remains monotonic and eases in/out without scale overshoot', () => {
  const f = choreographyFixture();
  try {
    const starts = [.0 + 1.3, 1.6, 2.0, 2.1, 2.65];
    ROOM_ENTRY_GROUPS.forEach(([, ids], group) => ids.forEach(id => {
      const asset = f.entry.getState().assets.find(asset => asset.id === id);
      assert.ok(f.tweens.get(id).startTime() >= .5 + starts[group] + ROOM_ENTRY_MOTIONS[id][1] - 1e-6);
      if (asset.support) {
        const support = f.tweens.get(asset.support);
        assert.ok(f.tweens.get(id).startTime() > support.startTime() + support.duration(), `${id}: support surface settles first`);
      }
    }));
    let maximumScale = 0;
    for (const [id, tween] of f.tweens) {
      const original = f.originals.get(f.roots.get(id)), node = f.roots.get(id); let previous = [0, 0, 0];
      for (const progress of [0, .01, .05, .15, .3, .5, .7, .85, .95, .99, 1]) {
        f.timeline.time(tween.startTime() + tween.duration() * progress, false); f.entry.update();
        const ratios = node.scale.toArray().map((value, axis) => value / original.scale[axis]);
        ratios.forEach((ratio, axis) => {
          assert.ok(ratio >= previous[axis] - 1e-10 && ratio <= 1 + 1e-10, `${id}: positive monotonic scale without back overshoot`);
          maximumScale = Math.max(maximumScale, ratio);
        });
        previous = ratios;
      }
      const earlySlope = (tween.vars.ease(.001) - tween.vars.ease(0)) / .001;
      const finalSlope = (tween.vars.ease(1) - tween.vars.ease(.999)) / .001;
      assert.ok(earlySlope < .001 && finalSlope < .001, `${id}: endpoint speed is softened`);
    }
    close([Math.abs(ROOM_ENTRY_MOTIONS['furniture.work_chair'][3]) / (2 * Math.PI)], [.45], 'chair finishing turn');
    assert.ok(f.end - .5 > 3.5 && f.end - .5 < 4.8, 'prop assembly ends about four seconds after structural start');
    return { groupOffsets: starts, durationAfterStructureStart: f.end - .5, maximumScale, chairTurns: .45 };
  } finally { f.dispose(); }
});

gsap.ticker.sleep();
const report = { ok: checks.every(check => check.status === 'passed'), testedAt: new Date().toISOString(),
  scope: 'Node EventTarget gestures and actual V16 GLB positions/indices/hierarchy with GSAP. Native click wiring inspected statically. Browser rendering, resizing, touch synthesis, focus and visual quality are separate checks.',
  sourceSha256: Object.fromEntries(['src/intro-input.js', 'src/room-entry.js', 'src/cube-intro.js', 'public/models/orbital-atelier-v16-compressed.glb'].map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')])),
  passed: checks.filter(c => c.status === 'passed').length, total: checks.length, checks };
const target = new URL('../docs/validation/cube-intro.json', import.meta.url);
mkdirSync(new URL('../docs/validation/', import.meta.url), { recursive: true }); writeFileSync(target, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
process.exitCode = report.ok ? 0 : 1;
