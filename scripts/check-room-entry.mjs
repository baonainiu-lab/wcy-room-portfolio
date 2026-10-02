import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import * as THREE from 'three';
import gsap from 'gsap';
import { createRoomEntry, ROOM_ENTRY_GROUPS } from '../src/room-entry.js';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';

// The cube controller owns shell growth, reduced motion and final restoration.
// This test isolates the current prop controller against real V16 geometry.
const results = [];
const capture = root => {
  root.updateWorldMatrix(true, true);
  const poses = new Map();
  root.traverse(node => poses.set(node, { position: node.position.clone(), quaternion: node.quaternion.clone(),
    rotation: node.rotation.clone(), scale: node.scale.clone(), world: node.matrixWorld.clone() }));
  return poses;
};
const equal = (actual, expected, label, eps = 1e-10) => actual.forEach((v,i) => assert.ok(Math.abs(v-expected[i]) < eps, label));
const assertPose = (node, pose, label) => {
  equal(node.position.toArray(), pose.position.toArray(), `${label} position`);
  equal(node.quaternion.toArray(), pose.quaternion.toArray(), `${label} quaternion`);
  equal(node.scale.toArray(), pose.scale.toArray(), `${label} scale`);
  equal(node.matrixWorld.elements, pose.world.elements, `${label} world`);
};
for (const transformed of [false, true]) {
  const { room } = readRoomGeometry('/models/orbital-atelier-v16-compressed.glb');
  const parent = new THREE.Group(); parent.add(room);
  if (transformed) {
    parent.position.set(3,-2,1); parent.rotation.set(.12,-.3,.05); parent.scale.set(1.3,.8,1.1);
    room.position.set(.3,.2,-.5); room.rotation.y = .18; room.scale.set(1.2,.9,1.1);
  }
  parent.updateMatrixWorld(true);
  const originals = capture(parent), snapshots = new WeakMap();
  originals.forEach((pose,node) => snapshots.set(node,pose));
  const roots = new Map(); room.traverse(node => { if (node.userData.asset_id) roots.set(node.userData.asset_id,node); });
  const ids = ROOM_ENTRY_GROUPS.flatMap(([, group]) => group);
  assert.equal(ids.length,36); assert.ok(ids.every(id => roots.has(id)));
  const propNodes = new Set(ids.map(id => roots.get(id)));
  const entry = createRoomEntry({ room, roots, snapshots, bounds: new THREE.Box3().setFromObject(room,true) });
  assert.equal(entry.getState().frameScale,1);
  assert.equal(entry.getState().phase,'prepared');
  assertPose(room, originals.get(room), 'shell remains owned by cube controller');
  for (const node of propNodes) equal(node.scale.toArray(), originals.get(node).scale.clone().multiplyScalar(.00001).toArray(),'prop prepared scale');
  const timeline = gsap.timeline({ paused:true });
  const end = entry.appendTo(timeline,.42);
  for (let t=.42; t<end; t+=.17) {
    timeline.time(t,false); entry.update(); parent.updateMatrixWorld(true);
    assertPose(room, originals.get(room),'shell unchanged during prop timeline');
    room.traverse(node => {
      if (propNodes.has(node) || node===room) return;
      const old = originals.get(node);
      equal(node.position.toArray(),old.position.toArray(),'descendant local position is not double-animated');
      equal(node.quaternion.toArray(),old.quaternion.toArray(),'descendant local quaternion is not double-animated');
      equal(node.scale.toArray(),old.scale.toArray(),'descendant local scale is not double-animated');
    });
  }
  timeline.time(end,false); entry.update();
  assert.ok(entry.getState().assets.every(asset => asset.factor===1));
  entry.restore(); entry.restore(); parent.updateMatrixWorld(true);
  for (const [node,pose] of originals) assertPose(node,pose,'idempotent endpoint restoration');
  timeline.kill();
  results.push({ check: transformed ? 'nonuniform transformed parent and exact recovery' : 'V16 shell ownership, independent prop hierarchy and exact recovery', status:'passed', propCount:ids.length, duration:end-.42 });
}
{
  const { room } = readRoomGeometry('/models/orbital-atelier-v16-compressed.glb');
  const originals=capture(room), snapshots=new WeakMap(), roots=new Map();
  originals.forEach((pose,node)=> { snapshots.set(node,pose); if(node.userData.asset_id)roots.set(node.userData.asset_id,node); });
  const entry=createRoomEntry({room,roots,snapshots,bounds:new THREE.Box3().setFromObject(room,true)});
  const timeline=gsap.timeline({paused:true}); entry.appendTo(timeline,0); timeline.time(2.1,false); entry.update();
  timeline.kill(); entry.restore(); room.updateMatrixWorld(true);
  for (const [node,pose] of originals) assertPose(node,pose,'interruption recovery');
  assert.equal(entry.getState().phase,'complete');
  results.push({check:'interrupted timeline returns every node to exact authored transform',status:'passed'});
}
gsap.ticker.sleep();
const report={ok:true,model:'/models/orbital-atelier-v16-compressed.glb',scope:'CPU real geometry and GSAP; cube suite separately checks shell growth/reduced motion/skip',passed:results.length,results};
writeFileSync(new URL('../docs/validation/room-entry-v16.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
