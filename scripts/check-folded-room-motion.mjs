import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createFoldedRoomMotion } from '../src/folded-room-motion.js';

// Bounded CPU tests only: synthetic two-carrier rig, persistent meshes and props.
// Actual Blender RoomUnfold GLB and browser continuity are separate checks.
const checks = [];
function check(name, run) {
  try { checks.push({ check: name, status: 'passed', ...run() }); }
  catch (error) { checks.push({ check: name, status: 'failed', error: error.stack }); }
}
function capture(root) {
  root.updateWorldMatrix(true, true); const poses = new Map();
  root.traverse(node => poses.set(node, { position: node.position.toArray(), quaternion: node.quaternion.toArray(),
    scale: node.scale.toArray(), rotation: node.rotation.toArray(), world: node.matrixWorld.toArray(),
    parent: node.parent, children: [...node.children], geometry: node.geometry, material: node.material, visible: node.visible }));
  return poses;
}
function close(actual, expected, label, tolerance = 1e-12) {
  actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) <= tolerance,
    `${label}[${index}]: ${value} != ${expected[index]}`));
}
function verify(root, poses) {
  root.updateWorldMatrix(true, true);
  for (const [node, pose] of poses) {
    close(node.position.toArray(), pose.position, `${node.name} position`);
    close(node.quaternion.toArray(), pose.quaternion, `${node.name} quaternion`);
    close(node.scale.toArray(), pose.scale, `${node.name} scale`);
    close(node.rotation.toArray().slice(0, 3), pose.rotation.slice(0, 3), `${node.name} Euler`);
    assert.equal(node.rotation.order, pose.rotation[3]);
    close(node.matrixWorld.toArray(), pose.world, `${node.name} world matrix`, 1e-10);
    assert.equal(node.parent, pose.parent); assert.deepEqual(node.children, pose.children);
    assert.equal(node.geometry, pose.geometry); assert.equal(node.material, pose.material); assert.equal(node.visible, pose.visible);
  }
}
function fixture() {
  const scene = new THREE.Scene(), room = new THREE.Group(); room.name = 'final-room'; scene.add(room);
  room.position.set(3, .2, -2); room.rotation.set(.12, -.2, .03); room.scale.set(1.2, .9, 1.1);
  const back = new THREE.Group(); back.name = 'fold.back_wall'; back.position.set(0, 1, -2); room.add(back);
  // Match GLTFLoader's real name sanitization and original-name metadata.
  const left = new THREE.Group(); left.name = THREE.PropertyBinding.sanitizeNodeName('fold.left_wall');
  left.userData.name = 'fold.left_wall'; left.position.set(-2, .1, .3); back.add(left);
  left.quaternion.fromArray([0, 0.5372995734214783, 0, 0.843391478061676]);
  left.scale.set(1.1, .9, 1.2);
  const wallMesh = new THREE.Mesh(new THREE.BoxGeometry(2, 3, .2), new THREE.MeshBasicMaterial());
  wallMesh.name = 'persistent-wall'; back.add(wallMesh);
  const prop = new THREE.Group(); prop.name = 'cup-root'; prop.userData.asset_id = 'thermal_cup';
  prop.position.set(.3, .5, .2); prop.rotation.set(.2, -.15, .4); prop.scale.set(.8, 1.2, .95); left.add(prop);
  const propMesh = new THREE.Mesh(new THREE.BoxGeometry(.2, .4, .2), wallMesh.material); propMesh.name = 'persistent-cup'; prop.add(propMesh);
  const clips = [new THREE.AnimationClip('RoomUnfold', 2, [
    new THREE.VectorKeyframeTrack(`${back.name}.position`, [0, 2], [0, -.3, 0, ...back.position.toArray()]),
    new THREE.QuaternionKeyframeTrack(`${left.name}.quaternion`, [0, 2], [0, 0, 0, 1, ...left.quaternion.toArray()]),
    new THREE.VectorKeyframeTrack(`${left.name}.scale`, [0, 2], [.2, .35, .3, ...left.scale.toArray()]),
  ])];
  return { scene, room, back, left, prop, wallMesh, propMesh, clips };
}
function create(f, clips = f.clips) { return createFoldedRoomMotion({ THREE, room: f.room, clips }); }
function checkRejected(f, clips, pattern) {
  const poses = capture(f.scene); assert.throws(() => create(f, clips), pattern); verify(f.scene, poses);
}
check('constructor validates and captures final pose without changing or hiding the persistent room', () => {
  const f = fixture(), poses = capture(f.scene), motion = create(f);
  verify(f.scene, poses);
  assert.deepEqual(motion.getState(), { revision: 1, clipName: 'RoomUnfold', clipDuration: 2,
    animatedNodes: ['fold.back_wall', 'fold.left_wall'], animatedNodeCount: 2, trackCount: 3, progress: 1, phase: 'prepared' });
  motion.dispose(); verify(f.scene, poses);
});
check('absolute sampling handles repeated resize seeks and reverse inspection without accumulating time', () => {
  const f = fixture(), final = capture(f.scene), motion = create(f), seen = new Map();
  for (const progress of [0, .2, .5, 1, .5, .5, 0, .2, 1]) {
    assert.equal(motion.setProgress(progress), true);
    const pose = [...f.back.matrixWorld.toArray(), ...f.left.matrixWorld.toArray()];
    if (seen.has(progress)) close(pose, seen.get(progress), `repeat seek ${progress}`, 1e-12);
    else seen.set(progress, pose);
    close(f.back.position.toArray(), [0, -.3 + 1.3 * progress, -2 * progress], `actual position at ${progress}`, 3e-8);
    close(f.room.position.toArray(), final.get(f.room).position, 'layout remains caller-owned');
    close(f.prop.position.toArray(), final.get(f.prop).position, 'prop local motion remains caller-owned');
    assert.equal(f.room.visible, true);
  }
  assert.notDeepEqual(seen.get(0), seen.get(1), 'actual architecture moved');
  motion.restore(); verify(f.scene, final); motion.dispose();
});
check('props follow the carrier world transform without any local transform or hierarchy changes', () => {
  const f = fixture(), original = capture(f.scene), motion = create(f);
  motion.setProgress(.4);
  close(f.prop.position.toArray(), original.get(f.prop).position, 'prop local position');
  close(f.prop.quaternion.toArray(), original.get(f.prop).quaternion, 'prop local quaternion');
  close(f.prop.scale.toArray(), original.get(f.prop).scale, 'prop local scale');
  assert.notDeepEqual(f.prop.matrixWorld.toArray(), original.get(f.prop).world);
  const expectedWorld = f.left.matrixWorld.clone().multiply(f.prop.matrix);
  close(f.prop.matrixWorld.toArray(), expectedWorld.toArray(), 'prop follows parent exactly');
  motion.restore(); verify(f.scene, original); motion.dispose();
});
check('mid-unfold restore is exact, releases mixer ownership and supports a fresh seek', () => {
  const f = fixture(), original = capture(f.scene), motion = create(f);
  motion.setProgress(.37); motion.restore(); motion.restore(); verify(f.scene, original);
  assert.equal(motion.getState().phase, 'restored');
  motion.setProgress(.7); motion.restore(); verify(f.scene, original);
  // This final quaternion came directly from float32 data, not an Euler round trip.
  assert.deepEqual(f.left.quaternion.toArray(), original.get(f.left).quaternion);
  motion.dispose();
});
check('dispose restores once, is terminal and never disposes persistent geometry or material', () => {
  const f = fixture(), original = capture(f.scene), motion = create(f); let disposed = 0;
  f.wallMesh.geometry.addEventListener('dispose', () => disposed++);
  f.propMesh.geometry.addEventListener('dispose', () => disposed++);
  f.wallMesh.material.addEventListener('dispose', () => disposed++);
  motion.setProgress(.6); motion.dispose(); verify(f.scene, original);
  f.back.position.x = 4; motion.dispose(); assert.equal(f.back.position.x, 4, 'repeat dispose does not clobber later state');
  assert.equal(motion.setProgress(.2), false); assert.equal(f.back.position.x, 4);
  assert.equal(disposed, 0); assert.equal(motion.getState().phase, 'disposed');
});
check('progress clamps finite boundaries and rejects NaN without disturbing the current sample', () => {
  const f = fixture(), motion = create(f);
  motion.setProgress(-2); assert.equal(motion.getState().progress, 0);
  motion.setProgress(2); assert.equal(motion.getState().progress, 1);
  const sampled = capture(f.scene); assert.throws(() => motion.setProgress(NaN), /progress must be finite/); verify(f.scene, sampled);
  motion.dispose();
});
check('missing, duplicate and empty clips fail before mutation', () => {
  const f = fixture();
  checkRejected(f, [], /exactly one/); checkRejected(f, [f.clips[0], f.clips[0]], /exactly one/);
  checkRejected(f, [new THREE.AnimationClip('RoomUnfold', 2, [])], /architectural tracks/);
});
check('room root, props, render meshes and non-TRS channels cannot enter the architecture clip', () => {
  const f = fixture();
  const clip = track => [new THREE.AnimationClip('RoomUnfold', 2, [track])];
  checkRejected(f, clip(new THREE.VectorKeyframeTrack(`${f.room.name}.position`, [0, 2], [0, 0, 0, ...f.room.position.toArray()])), /never the room root/);
  checkRejected(f, clip(new THREE.VectorKeyframeTrack(`${f.prop.name}.position`, [0, 2], [0, 0, 0, ...f.prop.position.toArray()])), /never a prop/);
  f.wallMesh.name = 'fold.render_mesh';
  checkRejected(f, clip(new THREE.VectorKeyframeTrack(`${f.wallMesh.name}.scale`, [0, 2], [0, 0, 0, 1, 1, 1])), /never a prop or render mesh/);
  checkRejected(f, clip(new THREE.NumberKeyframeTrack(`${f.back.name}.visible`, [0, 2], [0, 1])), /full position/);
  checkRejected(f, clip(new THREE.NumberKeyframeTrack(`${f.back.name}.position[x]`, [0, 2], [0, 0])), /full position/);
});
check('a fold-named carrier hidden inside a prop cannot bypass the ownership guard', () => {
  const f = fixture(), nested = new THREE.Group(); nested.name = 'fold.invalid_prop_child'; f.prop.add(nested);
  checkRejected(f, [new THREE.AnimationClip('RoomUnfold', 2, [new THREE.VectorKeyframeTrack(`${nested.name}.scale`, [0, 2], [.1, .1, .1, 1, 1, 1])])], /inside an interactive prop/);
});
check('competing channels, nonfinite data and a mismatched final pose fail before mutation', () => {
  const f = fixture();
  checkRejected(f, [new THREE.AnimationClip('RoomUnfold', 2, [f.clips[0].tracks[0], f.clips[0].tracks[0].clone()])], /duplicate tracks/);
  checkRejected(f, [new THREE.AnimationClip('RoomUnfold', 2, [new THREE.VectorKeyframeTrack(`${f.back.name}.position`, [0, 2], [NaN, 0, 0, ...f.back.position.toArray()])])], /nonfinite/);
  checkRejected(f, [new THREE.AnimationClip('RoomUnfold', 2, [new THREE.VectorKeyframeTrack(`${f.back.name}.position`, [0, 2], [0, 0, 0, 10, 10, 10])])], /loaded final room pose/);
});
const report = { ok: checks.every(c => c.status === 'passed'), scope: 'Synthetic two-carrier Three.js rig only; no actual Blender clip, textures, renderer or browser verification.',
  passed: checks.filter(c => c.status === 'passed').length, total: checks.length, checks };
console.log(JSON.stringify(report, null, 2)); process.exitCode = report.ok ? 0 : 1;
