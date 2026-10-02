import * as THREE from 'three';

// Existing interaction volumes stay outside the model tree, while following
// their authored local offset. Geometry is never rebuilt during a patrol.
export function createTrackedHitboxes() {
  const records = [];
  const inverseParent = new THREE.Matrix4();
  return {
    bind(hitbox, target) {
      target.updateWorldMatrix(true, false);
      hitbox.updateWorldMatrix(true, false);
      const local = target.matrixWorld.clone().invert().multiply(hitbox.matrixWorld);
      hitbox.matrixAutoUpdate = false;
      records.push({ hitbox, target, local });
    },
    update() {
      for (const { hitbox, target, local } of records) {
        target.updateWorldMatrix(true, false);
        hitbox.parent.updateWorldMatrix(true, false);
        inverseParent.copy(hitbox.parent.matrixWorld).invert();
        hitbox.matrix.copy(inverseParent).multiply(target.matrixWorld).multiply(local);
        hitbox.matrixWorldNeedsUpdate = true;
        hitbox.updateWorldMatrix(false, false);
      }
    },
    getState: () => ({ trackedCount: records.length }),
  };
}
