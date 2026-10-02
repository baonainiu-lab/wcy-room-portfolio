import * as THREE from 'three';

export const smoothTravel = value => {
  const t = Math.max(0, Math.min(1, value));
  return t * t * t * (t * (t * 6 - 15) + 10);
};
const phase = (p, a, b) => smoothTravel((p - a) / (b - a));

/** Bounded orbit curves, with zero velocity/acceleration at the visible ends. */
export function sampleTravelPose({ source, destination, progress, returning = false, reducedMotion = false,
  sourceCamera, sourceTarget, destinationCamera, destinationTarget }) {
  const p = Math.max(0, Math.min(1, progress)), sign = returning ? -1 : 1;
  const depart = reducedMotion ? 0 : smoothTravel(p);
  const arrive = reducedMotion ? 1 : phase(p, .04, 1);
  sourceTarget.copy(source.target);
  destinationTarget.copy(destination.target);
  const from = new THREE.Spherical().setFromVector3(source.position.clone().sub(source.target));
  const sourceFreedom = THREE.MathUtils.clamp((from.radius - 7) / 8, 0, 1);
  from.theta += sign * .075 * depart * sourceFreedom; from.phi -= .025 * depart * sourceFreedom;
  from.radius *= 1 - .065 * depart * sourceFreedom;
  sourceCamera.position.copy(sourceTarget).add(new THREE.Vector3().setFromSpherical(from));
  const to = new THREE.Spherical().setFromVector3(destination.position.clone().sub(destination.target));
  const destinationFreedom = THREE.MathUtils.clamp((to.radius - 7) / 8, 0, 1);
  to.theta -= sign * .105 * (1 - arrive) * destinationFreedom; to.phi += .018 * (1 - arrive) * destinationFreedom;
  to.radius *= 1 + .10 * (1 - arrive) * destinationFreedom;
  destinationCamera.position.copy(destinationTarget).add(new THREE.Vector3().setFromSpherical(to));
  if (p === 0 || reducedMotion) sourceCamera.position.copy(source.position);
  if (p === 1 || reducedMotion) destinationCamera.position.copy(destination.position);
  sourceCamera.lookAt(sourceTarget); destinationCamera.lookAt(destinationTarget);
  sourceCamera.updateProjectionMatrix(); destinationCamera.updateProjectionMatrix();
  sourceCamera.updateMatrixWorld(true); destinationCamera.updateMatrixWorld(true);
}

export function travelAperture(progress, anchor, cssSize, reducedMotion = false) {
  const p = Math.max(0, Math.min(1, progress));
  const expansion = phase(p, .035, .92);
  const center = anchor.center.clone().lerp(new THREE.Vector2(.5, .5), phase(p, .02, .8));
  const halfSize = anchor.halfSize.clone().lerp(new THREE.Vector2(.61, .61), expansion);
  const radius = Math.min(cssSize.x, cssSize.y) * (.014 + .032 * Math.sin(Math.PI * expansion));
  return { center, halfSize, radius, reveal: reducedMotion ? smoothTravel(p) : phase(p, 0, .16) };
}
