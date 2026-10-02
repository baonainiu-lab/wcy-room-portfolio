import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
import * as THREE from 'three';
import gsap from 'gsap';
import { parseModelForCPU } from './lib/intro-controller-fixture.mjs';
import { createResidentTerminal } from '../src/resident-terminal.js';
import { createRoomEntryAttachments } from '../src/room-entry-attachments.js';
import { configureAboutBookEntry } from '../src/about-book-entry.js';
const main = readFileSync(new URL('../src/main.js',import.meta.url),'utf8');
const metadata = vm.runInNewContext(`(${main.match(/const assetMeta = (\{[\s\S]*?\n\});/)[1]})`);
const ids = scene => { const all=[];scene.traverse(node=> { if(node.userData.asset_id)all.push(node.userData.asset_id); });return all.sort(); };
class PMREMGenerator {
  fromScene() { return { texture:new THREE.Texture(), dispose() {} }; }
  dispose() {}
}
const revisions=[];
for(const revision of [15,16]) {
  const gltf = await parseModelForCPU(`public/models/orbital-atelier-v${revision}.glb`);
  const compressed=readFileSync(new URL(`../public/models/orbital-atelier-v${revision}-compressed.glb`,import.meta.url));
  const compressedJson=JSON.parse(compressed.subarray(20,20+compressed.readUInt32LE(12)));
  const compressedIds=compressedJson.nodes.map(node=>node.extras?.asset_id).filter(Boolean).sort();
  const room=gltf.scene, sourceIds=ids(room), exteriorIds=['environment.orbital_dock','environment.warm_gallery'];
  assert.deepEqual(sourceIds,compressedIds,'compressed and raw IDs identical');
  const detached=[];room.traverse(node=> {if(exteriorIds.includes(node.userData.asset_id)) detached.push(node);});
  detached.forEach(node=>node.removeFromParent());
  const attachment=createRoomEntryAttachments({THREE,room}); configureAboutBookEntry({THREE,room});
  const before=ids(room), welcomeGltf=await parseModelForCPU('public/models/welcome-terminal-v2.glb');
  const terminal=createResidentTerminal({THREE:{...THREE,PMREMGenerator},renderer:{},room,welcomeGltf}); terminal.attachHome();
  const active=ids(room), roots=active.filter(id=>metadata[id]);
  assert.equal(sourceIds.length,95);assert.equal(active.length,92);assert.equal(roots.length,37);
  assert.equal(new Set(active).size,active.length,'unique selectable IDs');
  assert.deepEqual(before.filter(id=>!active.includes(id)),['drawing_stylus','terminal_panel_L','terminal_panel_R','terminal_tilt']);
  assert.deepEqual(active.filter(id=>!before.includes(id)),['terminal_dial','terminal_lid','terminal_rail']);
  revisions.push({revision,sourceIds,activeComponentIds:active,rootIds:roots,detachedExteriorIds:exteriorIds,
    replacedTerminalIds:before.filter(id=>!active.includes(id)),replacementTerminalIds:active.filter(id=>!before.includes(id))});
  terminal.dispose();attachment.dispose();
}
assert.deepEqual(revisions[0].sourceIds,revisions[1].sourceIds);
assert.deepEqual(revisions[0].activeComponentIds,revisions[1].activeComponentIds);
assert.deepEqual(revisions[0].rootIds,revisions[1].rootIds);
gsap.ticker.sleep();
const report={complete:true,scope:'Actual V15/V16 GLTF hierarchy with current runtime attachment, book and resident V2 terminal setup; textures/PMREM mocked, no GPU rendering',
  counts:{exportedIds:95,detachedExteriorIds:2,terminalIdsReplaced:4,terminalIdsAdded:3,activeInteractiveComponents:92,logicalRoots:37},
  noComponentRegression:true,comparisons:revisions};
writeFileSync(new URL('../docs/validation/room-v16-interaction-classification.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({complete:report.complete,counts:report.counts,noComponentRegression:report.noComponentRegression},null,2));
