import * as THREE from 'three';
const vec=(attr,index)=>new THREE.Vector3().fromBufferAttribute(attr,index);
export function build(mesh){
 const p=mesh.geometry.attributes.position,ix=mesh.geometry.index,n=(ix?.count??p.count)/3;
 const triangles=Array.from({length:n},(_,id)=>{const v=[0,1,2].map(k=>vec(p,ix?ix.getX(id*3+k):id*3+k));return {id,v,box:new THREE.Box3().setFromPoints(v),center:v[0].clone().add(v[1]).add(v[2]).multiplyScalar(1/3)};});
 function tree(ids){const box=new THREE.Box3();ids.forEach(i=>box.union(triangles[i].box));if(ids.length<=12)return {box,ids};const d=box.getSize(new THREE.Vector3()),axis=d.x>d.y&&d.x>d.z?'x':d.y>d.z?'y':'z';ids.sort((a,b)=>triangles[a].center[axis]-triangles[b].center[axis]);const mid=ids.length>>1;return {box,left:tree(ids.slice(0,mid)),right:tree(ids.slice(mid))};}
 return {mesh,triangles,tree:tree(triangles.map((_,i)=>i)),inverse:new THREE.Matrix4()};
}
const ray=new THREE.Ray(),point=new THREE.Vector3();
function query(node,tree,box,limit){if(!node.box.intersectsBox(box))return null;if(node.ids){for(const id of node.ids){const tri=tree.triangles[id];if(!tri.box.intersectsBox(box))continue;if(ray.intersectTriangle(...tri.v,false,point)){const d=point.distanceTo(ray.origin);if(d>1e-7&&d<limit-1e-7)return {id,point:point.clone()};}}return null}return query(node.left,tree,box,limit)||query(node.right,tree,box,limit)}
const conversion=new THREE.Matrix4();
// The baked wall mesh spans most of the room. Its root AABB overlaps every
// moving prop even in empty interior space; descend its BVH once before the
// expensive source-edge pass. This only rejects boxes with no target triangle
// AABB overlap, so it cannot discard a possible surface intersection.
function triangleBoxOverlap(node,tree,box){
 if(!node.box.intersectsBox(box))return false;
 if(node.ids)return node.ids.some(id=>tree.triangles[id].box.intersectsBox(box));
 return triangleBoxOverlap(node.left,tree,box)||triangleBoxOverlap(node.right,tree,box);
}
export function intersections(source,tree,stride=3){
 const p=source.geometry.attributes.position,ix=source.geometry.index,n=(ix?.count??p.count)/3,hits=[];
 conversion.copy(tree.inverse).multiply(source.matrixWorld);
 const sourcebox=new THREE.Box3().setFromBufferAttribute(p).applyMatrix4(conversion);
 if(!triangleBoxOverlap(tree.tree,tree,sourcebox))return hits;
 for(let id=0;id<n;id+=stride){const v=[0,1,2].map(k=>vec(p,ix?ix.getX(id*3+k):id*3+k).applyMatrix4(conversion));for(let k=0;k<3;k++){
  const a=v[k],b=v[(k+1)%3],len=a.distanceTo(b);if(len<1e-8)continue;
  ray.origin.copy(a);ray.direction.copy(b).sub(a).multiplyScalar(1/len);
  const box=new THREE.Box3().setFromPoints([a,b]).expandByScalar(1e-8),hit=query(tree.tree,tree,box,len);
  if(hit){hits.push({sourceTriangle:id,sourceEdge:k,targetTriangle:hit.id,point:hit.point.applyMatrix4(tree.mesh.matrixWorld).toArray(),edge:[a.clone().applyMatrix4(tree.mesh.matrixWorld).toArray(),b.clone().applyMatrix4(tree.mesh.matrixWorld).toArray()]});if(hits.length>=2)return hits;}
 }}return hits;
}
