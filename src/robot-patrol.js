import * as THREE from 'three';

const TAU = Math.PI * 2;
const ease = t => t * t * t * (t * (t * 6 - 15) + 10);
const wrap = (v, period) => ((v % period) + period) % period;

// Paths are measured world-space floor routes, not geometry. Rounded corners
// and a precomputed arc-length clock keep movement independent of waypoint
// density; runtime only interpolates this table and creates no scene objects.
export function createRobotPatrol({ waypoints, cornerRadius = .2, cruiseSpeed = .42,
  turnSpeed = .16, observationIndices = [], observationSeconds = 1,
  sampleHeight = () => 0, samplePose = () => null }) {
  if (waypoints.length < 3) throw new Error('Robot patrol needs a measured closed floor route');
  const points = waypoints.map(([x, z]) => new THREE.Vector2(x, z));
  const sections = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i], previous = points[wrap(i - 1, points.length)], next = points[(i + 1) % points.length];
    const incoming = p.clone().sub(previous), outgoing = next.clone().sub(p);
    const inLength = incoming.length(), outLength = outgoing.length();
    incoming.normalize(); outgoing.normalize();
    const dot = incoming.dot(outgoing);
    // A measured U-turn needs several explicit waypoints; do not improvise a
    // full circular turn inside a narrow corridor.
    const configuredRadius = typeof cornerRadius === 'function' ? cornerRadius(p.x, p.y, i) : cornerRadius;
    const radius = dot < -.95 ? 0 : Math.min(configuredRadius, inLength * .24, outLength * .24);
    sections.push({ centre: p, entry: p.clone().addScaledVector(incoming, -radius),
      exit: p.clone().addScaledVector(outgoing, radius), radius, index: i,
      reverse: dot < -.95, incomingHeading: Math.atan2(incoming.x, incoming.y),
      outgoingHeading: Math.atan2(outgoing.x, outgoing.y) });
  }
  const raw = [];
  const push = (x, z, marker = -1) => {
    if (raw.length && Math.hypot(x - raw.at(-1).x, z - raw.at(-1).z) < 1e-8) {
      if (marker >= 0) raw.at(-1).marker = marker;
      return;
    }
    raw.push({ x, z, marker });
  };
  // Keep the first measured point as the departure destination. On an
  // out-and-back branch its explicit turnaround happens at the end of the lap,
  // so the first visit can start walking forwards without a redundant spin.
  const first = sections[0];
  const seam = first.entry.clone();
  const line = (a, b) => {
    const count = Math.max(1, Math.ceil(a.distanceTo(b) / .025));
    for (let j = 1; j <= count; j++) { const t = j / count; push(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t); }
  };
  push(seam.x, seam.y); line(seam, first.entry);
  for (let i = 0; i < sections.length; i++) {
    const s = sections[i], count = Math.max(2, Math.ceil(s.radius * 2 / .018));
    for (let j = 1; j <= count; j++) {
      const t = j / count, a = (1 - t) * (1 - t), b = 2 * (1 - t) * t, c = t * t;
      push(s.entry.x * a + s.centre.x * b + s.exit.x * c,
        s.entry.y * a + s.centre.y * b + s.exit.y * c,
        j === Math.ceil(count / 2) ? s.index : -1);
    }
    line(s.exit, i + 1 < sections.length ? sections[i + 1].entry : seam);
  }
  if (first.reverse) raw[raw.length - 1].marker = 0;
  const count = raw.length, distance = new Float64Array(count), speed = new Float64Array(count);
  const height = new Float64Array(count), heading = new Float64Array(count), compact = new Float64Array(count);
  const fixedHeading = new Uint8Array(count);
  const turnAt = new Map();
  const stops = new Set(observationIndices);
  for (let i = 0; i < count; i++) {
    if (i) distance[i] = distance[i - 1] + Math.hypot(raw[i].x - raw[i - 1].x, raw[i].z - raw[i - 1].z);
    const previous = raw[i === 0 ? count - 2 : i - 1], next = raw[i === count - 1 ? 1 : i + 1];
    heading[i] = Math.atan2(next.x - previous.x, next.z - previous.z);
    const a = new THREE.Vector2(raw[i].x - previous.x, raw[i].z - previous.z);
    const b = new THREE.Vector2(next.x - raw[i].x, next.z - raw[i].z);
    const curvature = Math.acos(THREE.MathUtils.clamp(a.normalize().dot(b.normalize()), -1, 1)) /
      Math.max(.02, Math.hypot(next.x - previous.x, next.z - previous.z) / 2);
    speed[i] = Math.max(turnSpeed, Math.min(cruiseSpeed, Math.sqrt(.12 / Math.max(.01, curvature))));
    if (stops.has(raw[i].marker)) speed[i] = 0;
    const pose = samplePose(raw[i].x, raw[i].z, heading[i]);
    if (pose) { heading[i] = pose.heading ?? heading[i]; compact[i] = pose.compact ?? 0;
      fixedHeading[i] = pose.fixedHeading ? 1 : 0;
      if (Number.isFinite(pose.maximumSpeed)) speed[i] = Math.max(0, Math.min(speed[i], pose.maximumSpeed)); }
    const section = sections[raw[i].marker];
    if (section?.reverse) {
      speed[i] = 0;
      if (!pose?.fixedHeading) {
        heading[i] = section.incomingHeading;
        turnAt.set(i, { start: section.incomingHeading, end: section.outgoingHeading });
      } else stops.add(raw[i].marker);
    }
    height[i] = sampleHeight(raw[i].x, raw[i].z, heading[i]);
  }
  // Forward/backward acceleration limits make turns and observation stops slow
  // down before arrival rather than changing velocity at the corner itself.
  const acceleration = .32;
  for (let pass = 0; pass < 3; pass++) {
    for (let i = 1; i < count; i++) speed[i] = Math.min(speed[i], Math.sqrt(speed[i - 1] ** 2 + 2 * acceleration * (distance[i] - distance[i - 1])));
    for (let i = count - 2; i >= 0; i--) speed[i] = Math.min(speed[i], Math.sqrt(speed[i + 1] ** 2 + 2 * acceleration * (distance[i + 1] - distance[i])));
    speed[0] = speed[count - 1] = Math.min(speed[0], speed[count - 1]);
  }
  // Anticipate shallow rug edges with a short raised envelope: the body eases
  // upward before the leading support foot reaches the measured higher floor.
  const h = new Float64Array(height);
  for (let i = 0; i < count; i++) for (let j = 0; j < count; j++) {
    const d = Math.min(Math.abs(distance[i] - distance[j]), distance[count - 1] - Math.abs(distance[i] - distance[j]));
    if (d < .22) height[i] = Math.max(height[i], h[j] * ease(1 - d / .22));
  }
  const timeline = [];
  let duration = 0;
  for (let i = 0; i < count - 1; i++) {
    const speedSum = speed[i] + speed[i + 1];
    if (speedSum < 1e-8) throw new Error('A robot travel segment needs positive speed; use observation stops to pause');
    const seconds = 2 * (distance[i + 1] - distance[i]) / speedSum;
    timeline.push({ start: duration, end: duration + seconds, i, hold: false }); duration += seconds;
    if (turnAt.has(i + 1)) {
      timeline.push({ start: duration, end: duration + 1.7, i: i + 1, hold: true, turn: turnAt.get(i + 1) }); duration += 1.7;
    }
    if (stops.has(raw[i + 1].marker)) {
      timeline.push({ start: duration, end: duration + observationSeconds, i: i + 1, hold: true }); duration += observationSeconds;
    }
  }
  let cursor = 0;
  const state = { x: raw[0].x, z: raw[0].z, height: height[0], heading: heading[0], compact: compact[0], speed: speed[0], distance: 0, observing: false };
  return {
    duration, length: distance[count - 1], start: [raw[0].x, raw[0].z], waypoints: waypoints.map(p => [...p]),
    sample(time) {
      const t = wrap(time, duration);
      if (t < timeline[cursor].start) cursor = 0;
      while (cursor < timeline.length - 1 && t >= timeline[cursor].end) cursor++;
      const segment = timeline[cursor], i = segment.i;
      if (segment.hold) {
        state.x = raw[i].x; state.z = raw[i].z; state.height = height[i]; state.speed = 0;
        if (segment.turn) {
          const angular = Math.atan2(Math.sin(segment.turn.end - segment.turn.start), Math.cos(segment.turn.end - segment.turn.start));
          state.heading = segment.turn.start + angular * ease((t - segment.start) / (segment.end - segment.start));
        } else state.heading = (turnAt.get(i)?.end ?? heading[i]) +
          (fixedHeading[i] || compact[i] > .5 ? 0 : .08 * Math.sin((t - segment.start) / observationSeconds * TAU));
        state.compact = compact[i]; state.distance = distance[i]; state.observing = true;
      } else {
        const segmentSeconds = segment.end - segment.start, elapsedSeconds = t - segment.start;
        const elapsedFraction = elapsedSeconds / segmentSeconds;
        const travelled = speed[i] * elapsedSeconds +
          .5 * (speed[i + 1] - speed[i]) / segmentSeconds * elapsedSeconds * elapsedSeconds;
        const u = Math.min(1, travelled / Math.max(1e-8, distance[i + 1] - distance[i]));
        const startHeading = turnAt.get(i)?.end ?? heading[i];
        const angular = Math.atan2(Math.sin(heading[i + 1] - startHeading), Math.cos(heading[i + 1] - startHeading));
        state.x = raw[i].x + (raw[i + 1].x - raw[i].x) * u;
        state.z = raw[i].z + (raw[i + 1].z - raw[i].z) * u;
        state.height = height[i] + (height[i + 1] - height[i]) * u;
        state.heading = startHeading + angular * u;
        state.compact = compact[i] + (compact[i + 1] - compact[i]) * u;
        state.speed = speed[i] + (speed[i + 1] - speed[i]) * elapsedFraction;
        state.distance = distance[i] + (distance[i + 1] - distance[i]) * u; state.observing = false;
      }
      return state;
    },
    getState: () => ({ lengthMetres: distance[count - 1], durationSeconds: duration, cruiseSpeedMetresPerSecond: cruiseSpeed,
      minimumTurnSpeedMetresPerSecond: turnSpeed, observationSeconds, observations: observationIndices.length,
      samples: count, waypoints: waypoints.map(p => [...p]), start: [raw[0].x, raw[0].z] }),
  };
}
