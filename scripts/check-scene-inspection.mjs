import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import * as THREE from 'three';
import { readRoomGeometry } from './lib/read-room-geometry.mjs';
import { configureResumeBook, RESUME_BOOK_ID, inspectionPose, projectObjectRect } from '../src/scene-inspection.js';
import { createAboutFraming } from '../src/about-framing.js';
import { createGalleryFraming } from '../src/gallery-framing.js';
const about = readRoomGeometry('/models/about-atelier-v3-compressed.glb');
const ids = [...about.components.keys()];
const book = about.components.get(RESUME_BOOK_ID), originalY = new THREE.Box3().setFromObject(book,true).min.y;
configureResumeBook(about.room, about.components);
const position = book.position.clone(), scale = book.scale.clone();
configureResumeBook(about.room, about.components);
assert.equal(position.distanceTo(book.position),0); assert.equal(scale.distanceTo(book.scale),0);
assert.deepEqual([...about.components.keys()], ids);
const bookBounds = new THREE.Box3().setFromObject(book,true);
assert.ok(Math.abs(bookBounds.min.y-originalY)<1e-6);
for(const [id,node] of about.components) if(id!==RESUME_BOOK_ID&&id.startsWith('about.workbench.')) assert.ok(!bookBounds.intersectsBox(new THREE.Box3().setFromObject(node,true)),`expanded book overlaps ${id}`);
const gallery=readRoomGeometry('/models/works-gallery-v6-compressed.glb');
const results=[];
for(const [kind,scene,node,frame] of [['resume',about,book,createAboutFraming(about.room)],['work',gallery,gallery.components.get('gallery.work.01.art'),createGalleryFraming(gallery.room)]]) {
 for(const [w,h] of [[1280,720],[1920,1080],[390,844],[844,390]]) {
  const camera=new THREE.PerspectiveCamera(35,w/h,.1,500),home=frame.pose(w/h,35);
  camera.position.copy(home.position); camera.lookAt(home.target); camera.updateMatrixWorld(true);
  const pose=inspectionPose(camera,node,kind),sourceDistance=camera.position.distanceTo(pose.target);
  assert.ok(pose.position.distanceTo(pose.target)<=sourceDistance+1e-6,'camera must move forward');
  camera.position.copy(pose.position);camera.lookAt(pose.target);camera.updateMatrixWorld(true);
  const rect=projectObjectRect(node,camera,{left:0,top:0,width:w,height:h});
  assert.ok(Object.values(rect).every(Number.isFinite));assert.ok(rect.width>0&&rect.height>0);
  assert.ok(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=w&&rect.y+rect.height<=h,'projected origin within viewport');
  results.push({kind,viewport:[w,h],distance:pose.position.distanceTo(pose.target),origin:rect});
 }
}
writeFileSync('docs/validation/scene-inspection-geometry.json',JSON.stringify({passed:true,assetCount:ids.length,book:book.userData.resumeEntry,results},null,2));
console.log('PASS: book support and desk clearances; stable IDs; idempotence; forward camera poses and projected origins at 4 viewports per scene.');
