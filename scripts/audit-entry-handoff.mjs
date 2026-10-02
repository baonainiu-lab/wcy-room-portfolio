import * as THREE from 'three';
import {parseModelForCPU,introFixture} from './lib/intro-controller-fixture.mjs';
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const root=new URL('../', import.meta.url);
const hash=p=>createHash('sha256').update(readFileSync(new URL(p, root))).digest('hex');
const paths=['src/cube-intro.js','src/room-entry.js','public/models/welcome-terminal-v1.glb','public/models/orbital-atelier-v16.glb'];
const hashes=Object.fromEntries(paths.map(p=>[p,hash(p)]));
const f=introFixture({welcomeGltf:await parseModelForCPU(paths[2]),roomGltf:await parseModelForCPU(paths[3])});
const meshList=(root,fn=()=>true)=>{const list=[];root.traverse(n=>{if(n.isMesh&&fn(n))list.push(n)});return list};
const targets=meshList(f.room,n=>['room_static','architecture.platform'].includes(n.userData.owner_asset_id));
const other=meshList(f.room,n=>['furniture.desk','main_display','compute_core'].includes(n.userData.owner_asset_id));
const vec=(attr,index)=>new THREE.Vector3().fromBufferAttribute(attr,index);
function build(mesh){
 const p=mesh.geometry.attributes.position,ix=mesh.geometry.index,n=(ix?.count??p.count)/3;
 const triangles=Array.from({length:n},(_,id)=>{const v=[0,1,2].map(k=>vec(p,ix?ix.getX(id*3+k):id*3+k));return {id,v,box:new THREE.Box3().setFromPoints(v),center:v[0].clone().add(v[1]).add(v[2]).multiplyScalar(1/3)};});
 function tree(ids){const box=new THREE.Box3();ids.forEach(i=>box.union(triangles[i].box));if(ids.length<=12)return {box,ids};const d=box.getSize(new THREE.Vector3()),axis=d.x>d.y&&d.x>d.z?'x':d.y>d.z?'y':'z';ids.sort((a,b)=>triangles[a].center[axis]-triangles[b].center[axis]);const mid=ids.length>>1;return {box,left:tree(ids.slice(0,mid)),right:tree(ids.slice(mid))};}
 return {mesh,triangles,tree:tree(triangles.map((_,i)=>i)),inverse:new THREE.Matrix4()};
}
const bvh=[...targets,...other].map(build), ray=new THREE.Ray(),point=new THREE.Vector3();
function query(node,tree,box,limit){if(!node.box.intersectsBox(box))return null;if(node.ids){for(const id of node.ids){const tri=tree.triangles[id];if(!tri.box.intersectsBox(box))continue;if(ray.intersectTriangle(...tri.v,false,point)){const d=point.distanceTo(ray.origin);if(d>1e-7&&d<limit-1e-7)return {id,point:point.clone()};}}return null}return query(node.left,tree,box,limit)||query(node.right,tree,box,limit)}
const conversion=new THREE.Matrix4();
function intersections(source,tree,stride=3){
 const p=source.geometry.attributes.position,ix=source.geometry.index,n=(ix?.count??p.count)/3,hits=[];
 conversion.copy(tree.inverse).multiply(source.matrixWorld);
 const sourcebox=new THREE.Box3().setFromBufferAttribute(p).applyMatrix4(conversion);
 if(!sourcebox.intersectsBox(tree.tree.box))return hits;
 for(let id=0;id<n;id+=stride){const v=[0,1,2].map(k=>vec(p,ix?ix.getX(id*3+k):id*3+k).applyMatrix4(conversion));for(let k=0;k<3;k++){
  const a=v[k],b=v[(k+1)%3],len=a.distanceTo(b);if(len<1e-8)continue;
  ray.origin.copy(a);ray.direction.copy(b).sub(a).multiplyScalar(1/len);
  const box=new THREE.Box3().setFromPoints([a,b]).expandByScalar(1e-8),hit=query(tree.tree,tree,box,len);
  if(hit){hits.push({sourceTriangle:id,sourceEdge:k,targetTriangle:hit.id,point:hit.point.applyMatrix4(tree.mesh.matrixWorld).toArray(),edge:[a.clone().applyMatrix4(tree.mesh.matrixWorld).toArray(),b.clone().applyMatrix4(tree.mesh.matrixWorld).toArray()]});if(hits.length>=2)return hits;}
 }}return hits;
}
const exteriorMeshes=meshList(f.exteriorModel),terminalMeshes=meshList(f.welcomeModel),records=[];
f.ready().progress(1);const timeline=f.enter();
for(const time of Array.from({length:181},(_,i)=>1.10+i/60)){
 timeline.time(time);f.intro.update();f.scene.updateMatrixWorld(true);bvh.forEach(t=>t.inverse.copy(t.mesh.matrixWorld).invert());
 const record={time,roomScale:f.intro.getState().roomScale,exteriorScale:f.exteriorModel.scale.toArray(),terminal:[],exterior:[]};
 if(f.intro.getState().modelVisible&&f.room.visible)for(const source of terminalMeshes)for(const target of bvh){const hits=intersections(source,target,2);if(hits.length)record.terminal.push({source:source.name,target:target.mesh.name,hits});}
 if(f.exteriorModel.visible&&f.room.visible)for(const source of exteriorMeshes)for(const target of bvh){const hits=intersections(source,target,7);if(hits.length)record.exterior.push({source:source.name,target:target.mesh.name,hits});}
 records.push(record);console.log(JSON.stringify({time,terminal:record.terminal.map(h=>[h.source,h.target,h.hits[0].point]),exterior:record.exterior.map(h=>[h.source,h.target,h.hits[0].point])}));
}
f.intro.skip();f.scene.updateMatrixWorld(true);bvh.forEach(t=>t.inverse.copy(t.mesh.matrixWorld).invert());const final=[];for(const source of exteriorMeshes)for(const target of bvh){const hits=intersections(source,target,7);if(hits.length)final.push({source:source.name,target:target.mesh.name,hits})};
f.cleanup();const report={hashes,unchanged:paths.every(p=>hash(p)===hashes[p]),method:'Real GLTFLoader + production controller and GSAP; source triangle edge segments intersect target triangles using BVH broadphase, strict interior segment hits. Sparse source triangle sampling: terminal stride2, exterior stride7; coordinates are world units. Does not prove absence of unsampled collisions.',records,final};report.collisionFrames = records.filter(r=>r.terminal.length||r.exterior.length).length; if(report.collisionFrames || final.length) process.exitCode=1; writeFileSync(new URL('docs/validation/entry-handoff-audit.json',root),JSON.stringify(report,null,2));console.log(JSON.stringify({hashes,unchanged:report.unchanged,final}));
