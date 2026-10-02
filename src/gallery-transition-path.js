import * as THREE from 'three';

export const smoothTravel = value => {
  const t = Math.max(0, Math.min(1, value));
  return t * t * t * (t * (t * 6 - 15) + 10);
};
export const GALLERY_OFFSET = new THREE.Vector3(34, -.185, 1.5);
const zero = new THREE.Vector3();

/** Both buildings occupy one stage. Only the camera travels between them. */
export function sampleTravelPose({ source, destination, progress, returning = false, reducedMotion = false, offset = GALLERY_OFFSET,
  sourceCamera, sourceTarget, destinationCamera, destinationTarget, stageCamera }) {
  const p = Math.max(0, Math.min(1, progress)), t = smoothTravel(p);
  const fromOffset = returning ? offset : zero;
  const toOffset = returning ? zero : offset;
  if (reducedMotion) {
    sourceTarget.copy(source.target); destinationTarget.copy(destination.target);
    sourceCamera.position.copy(source.position); destinationCamera.position.copy(destination.position);
    sourceCamera.lookAt(sourceTarget); destinationCamera.lookAt(destinationTarget);
    stageCamera?.copy(sourceCamera);
  } else {
    const start = source.position.clone().add(fromOffset), end = destination.position.clone().add(toOffset);
    const target = source.target.clone().add(fromOffset).lerp(destination.target.clone().add(toOffset), t);
    const outward = source.position.clone().sub(source.target).normalize()
      .add(destination.position.clone().sub(destination.target).normalize()).normalize();
    const arc = 4 * t * (1 - t);
    const distance = Math.min(22, offset.length() * .43 / Math.max(.65, sourceCamera.aspect));
    const position = start.lerp(end, t).addScaledVector(outward, distance * arc);
    if (!returning) {
      // One continuous arrival: approach just outside the final composition,
      // then gently push forward through the last part of the same camera path.
      const approach = smoothTravel(p / .55) * (1 - smoothTravel((p - .58) / .42));
      position.addScaledVector(destination.position.clone().sub(destination.target), .10 * approach);
    }
    position.y += 2.1 * arc;
    sourceCamera.position.copy(position).sub(fromOffset); sourceTarget.copy(target).sub(fromOffset);
    destinationCamera.position.copy(position).sub(toOffset); destinationTarget.copy(target).sub(toOffset);
    if (p === 0) { sourceCamera.position.copy(source.position); sourceTarget.copy(source.target); }
    if (p === 1) { destinationCamera.position.copy(destination.position); destinationTarget.copy(destination.target); }
    sourceCamera.lookAt(sourceTarget); destinationCamera.lookAt(destinationTarget);
    if (stageCamera) { stageCamera.position.copy(position); stageCamera.lookAt(target); }
  }
  for (const view of [sourceCamera, destinationCamera, stageCamera].filter(Boolean)) {
    view.updateProjectionMatrix(); view.updateMatrixWorld(true);
  }
}
