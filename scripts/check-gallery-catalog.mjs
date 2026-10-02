import assert from 'node:assert/strict';
import { readFileSync, existsSync, statSync, writeFileSync } from 'node:fs';
import * as THREE from 'three';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { inspectionPose, projectObjectRect } from '../src/scene-inspection.js';
import { createGalleryFraming } from '../src/gallery-framing.js';
const entries = ['23','45'].flatMap(part => JSON.parse(readFileSync(`src/content/gallery-exhibits-${part}.json`, 'utf8')));
assert.deepEqual(entries.map(e=>e.index), [2,3,4,5]);
assert.deepEqual(entries.map(e=>e.items.length), [1,3,1,6]);
const paths = new Set();
for(const entry of entries) {
 assert.ok(entry.title && entry.cover && entry.description);
 const ids=new Set(); paths.add(entry.cover);
 for(const item of entry.items){
  assert.ok(item.id && item.title && item.description && item.image); assert.ok(!ids.has(item.id)); ids.add(item.id);
  paths.add(item.image); if(item.video) paths.add(item.video);
  for(const picture of item.gallery || []) {assert.ok(picture.alt);paths.add(picture.src);}
 }
}
for(const file of paths) {assert.ok(file.startsWith('/media/works/')); assert.ok(existsSync(`public${file}`),file);assert.ok(statSync(`public${file}`).size>0);}
const gallery=readRoomGeometry('/models/works-gallery-v6-compressed.glb'), framing=createGalleryFraming(gallery.room), results=[];
for(const entry of entries){
 const number=String(entry.index).padStart(2,'0'),framed=entry.index===3;
 const node=gallery.components.get(`gallery.work.${number}${framed?'.art':''}`), boards=[];
 node.traverse(mesh=>{if(mesh.isMesh&&(framed||mesh.name.replaceAll('.','').includes(`gallerywork${number}__baked`)))boards.push(mesh);});
 assert.equal(boards.length,1,`single retained printable board ${number}`);
 const surface=new THREE.Mesh(boards[0].geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));surface.updateMatrixWorld();
 const center=new THREE.Vector3(framed?0:[-4.8,-2.7,-.6,1.5,3.6][entry.index-1],framed?0:1.88,1);
 const hit=new THREE.Raycaster(center,new THREE.Vector3(0,0,-1)).intersectObject(surface)[0];
 assert.ok(hit && hit.point.z >= (framed?.093:-2.34),`printed surface visible within shader depth ${number}`);
 for(const [w,h] of [[1280,720],[390,844]]){
  const camera=new THREE.PerspectiveCamera(35,w/h,.1,500),home=framing.pose(w/h,35);camera.position.copy(home.position);camera.lookAt(home.target);
  const pose=inspectionPose(camera,node,'work');camera.position.copy(pose.position);camera.lookAt(pose.target);camera.updateMatrixWorld(true);
  const rect=projectObjectRect(node,camera,{left:0,top:0,width:w,height:h});assert.ok(rect.width>0&&rect.height>0&&rect.x>=0&&rect.y>=0&&rect.x+rect.width<=w&&rect.y+rect.height<=h);
  results.push({index:entry.index,viewport:[w,h],origin:rect});
 }
}
writeFileSync('docs/validation/gallery-catalog.json',JSON.stringify({passed:true,exhibits:entries.map(e=>({index:e.index,title:e.title,items:e.items.map(i=>i.title)})),mediaFiles:paths.size,assetIds:gallery.components.size,cameraChecks:results},null,2));
console.log(`PASS: four exhibits / eleven projects; ${paths.size} media paths; retained printable surfaces and desktop/mobile camera bounds.`);
