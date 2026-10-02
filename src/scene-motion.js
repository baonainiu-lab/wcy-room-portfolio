import * as THREE from 'three';
import gsap from 'gsap';
import { createRobotPatrol } from './robot-patrol.js';

const TURN = Math.PI * 2;
const EPSILON = 1e-7;
const UP = new THREE.Vector3(0, 1, 0);
const smooth = value => { const t = Math.max(0, Math.min(1, value)); return t * t * t * (t * (t * 6 - 15) + 10); };
const phaseAt = (time, period) => ((time % period) + period) % period;
const related = (a, b) => {
  if (!a || !b) return false;
  for (let parent = a; parent; parent = parent.parent) if (parent === b) return true;
  for (let parent = b; parent; parent = parent.parent) if (parent === a) return true;
  return false;
};

// Runtime animation of existing Blender pivots only. Every mechanism owns its
// clock, so hovering/clicking it freezes its current place in the choreography.
// No mesh, material, light, hierarchy or scale is created/changed here.
export function createSceneMotion({ components, snapshots, reducedMotion = false }) {
  let elapsed = 0, activeCount = 0, lastHovered = null, enabledLastFrame = false, sceneHour = null;
  const records = [];
  const hoverAnchors = new WeakMap();
  const bind = id => {
    const node = components.get(id), original = node && snapshots.get(node);
    if (!original) return null;
    const baseQuaternion = new THREE.Quaternion().setFromEuler(original.rotation);
    return { id, node, original, baseQuaternion, targetQuaternion: baseQuaternion.clone(),
      offsetQuaternion: new THREE.Quaternion(), targetPosition: original.position.clone(),
      positionOwned: false, rotationOwned: true };
  };
  const add = (id, label, period, sample, ids = [id], phase = 0) => {
    const parts = ids.map(bind).filter(Boolean);
    if (!parts.length || parts[0].id !== id) return null;
    const watch = new Set();
    for (const part of parts) for (let node = part.node; node; node = node.parent) watch.add(node);
    const record = { id, label, period, sample, parts, watch: [...watch], phase,
      time: 0, heldUntil: 0, hovered: false, activity: 'resting', blocked: false,
      values: Object.create(null) };
    records.push(record); return record;
  };
  const localRotation = (part, axis, angle) => {
    part.offsetQuaternion.setFromAxisAngle(axis, angle);
    part.targetQuaternion.copy(part.baseQuaternion).multiply(part.offsetQuaternion);
  };
  const parentRotation = (part, axis, angle) => {
    part.offsetQuaternion.setFromAxisAngle(axis, angle);
    part.targetQuaternion.copy(part.offsetQuaternion).multiply(part.baseQuaternion);
  };
  const axisX = new THREE.Vector3(1, 0, 0), axisZ = new THREE.Vector3(0, 0, 1);
  const pulse = (time, period, attack, hold, release) => {
    const t = phaseAt(time, period);
    if (t < attack) return smooth(t / attack);
    if (t < attack + hold) return 1;
    if (t < attack + hold + release) return 1 - smooth((t - attack - hold) / release);
    return 0;
  };

  add('furniture.work_chair', '工作椅 · 连续慢转', 18, record => {
    const angle = record.time / record.period * TURN;
    parentRotation(record.parts[0], UP, angle);
    record.activity = 'swivelling'; record.values.turns = record.time / record.period;
  });

  // The measured route follows the front aisle, folds the real hip pivots to
  // side-step the lounge edge, then reaches the window/work area via the right
  // wall. It never crosses the obstructed low desk supports or teleports.
  const robotIds = ['robot_companion', 'robot_leg_00', 'robot_leg_01', 'robot_leg_02'];
  const robot = add('robot_companion', '三足机器人 · 巡游、停步观察', 1, record => {
    const body = record.parts[0], t = record.time, departure = 2.5;
    let x, z, height, heading, compact, speed;
    if (t < departure) {
      const progress = smooth(t / departure), pose = record.patrol.sample(0);
      x = record.origin.x + (pose.x - record.origin.x) * progress;
      z = record.origin.z + (pose.z - record.origin.z) * progress;
      compact = pose.compact * progress; height = pose.height * progress;
      // Clear the original desk-side footprint before turning its full tripod.
      heading = pose.heading * smooth((progress - .91) / .09);
      // A short, low-amplitude departure gait clears the nearby desk before
      // the wider normal stride begins; the robot never slides with dead legs.
      speed = .3 * Math.sin(Math.PI * t / departure);
      record.activity = 'leaving-dock';
    } else {
      const pose = record.patrol.sample(t - departure);
      x = pose.x; z = pose.z; height = pose.height; heading = pose.heading; compact = pose.compact;
      speed = Math.min(1, pose.speed / .35);
      record.activity = pose.observing ? 'looking-around' : compact > .5 ? 'side-stepping' : 'patrolling';
      record.values.distance = pose.distance;
    }
    const stride = t * TURN;
    const bob = .004 * speed * Math.pow(Math.sin(stride * 1.5), 2);
    body.targetPosition.copy(body.original.position)
      .addScaledVector(record.worldX, x - record.origin.x).addScaledVector(record.worldZ, z - record.origin.z)
      .addScaledVector(record.worldUp, height + .055 * compact + bob);
    parentRotation(body, record.parentUp, heading);
    for (let index = 1; index < record.parts.length; index++) {
      const leg = record.parts[index], stepPhase = phaseAt(t + (index - 1) / 3, 1);
      const lift = stepPhase < 1 / 3 ? Math.pow(Math.sin(stepPhase * 3 * Math.PI), 2) * (.07 - .035 * compact) * speed : 0;
      parentRotation(leg, leg.hipAxis, -.16 * compact + lift);
    }
    record.values.pathOffsetX = x - record.origin.x; record.values.pathOffsetZ = z - record.origin.z;
    record.values.heading = heading; record.values.gait = speed; record.values.compact = compact;
    record.values.floorLift = height;
  }, robotIds);
  if (robot) {
    const body = robot.parts[0]; body.positionOwned = true;
    body.node.parent.updateWorldMatrix(true, false);
    const inverse = body.node.parent.matrixWorld.clone().invert();
    const origin = new THREE.Vector3().setFromMatrixPosition(body.node.parent.matrixWorld).applyMatrix4(inverse);
    const parentWorldOrigin = new THREE.Vector3().setFromMatrixPosition(body.node.parent.matrixWorld);
    const inParent = vector => vector.add(parentWorldOrigin).applyMatrix4(inverse).sub(origin);
    robot.worldX = inParent(new THREE.Vector3(1, 0, 0)); robot.worldZ = inParent(new THREE.Vector3(0, 0, 1));
    robot.worldUp = inParent(new THREE.Vector3(0, 1, 0)); robot.parentUp = robot.worldUp.clone().normalize();
    robot.origin = body.node.getWorldPosition(new THREE.Vector3());
    for (let index = 1; index < robot.parts.length; index++) {
      const leg = robot.parts[index], p = leg.original.position;
      leg.hipAxis = new THREE.Vector3(-p.z, 0, p.x).normalize();
    }
    const outward = [
      [-3.23, 2.84], [-.4, 2.99], [2, 2.99], [3.4, 2.99], [4, 2.99],
      [4.5, 2.75], [4.5, 1.5], [4.5, .18], [3.18, .18], [2.67, .19],
      [1.83, .19], [1.47, -.05], [1.35, -.41], [.39, -.53], [.15, -.77],
      [.03, -1.61], [-.8, -1.65], [-1.8, -1.65], [-3.3, -1.5],
    ];
    const waypoints = [...outward, ...outward.slice(1, -1).reverse()];
    const profile = (x, z, tangent) => {
      const compact = z > 2 ? smooth((x + 2) / 1.4) : x < -1.9 ? 1 - smooth((-x - 1.9) / 1.4) : 1;
      const turn = Math.atan2(Math.sin(Math.PI - tangent), Math.cos(Math.PI - tangent));
      return { compact, heading: tangent + turn * compact, fixedHeading: compact > .999,
        maximumSpeed: .42 - compact * .07 };
    };
    const rug = components.get('furniture.rug'), platform = components.get('architecture.platform');
    const rugBounds = rug ? new THREE.Box3().setFromObject(rug) : null;
    const floorY = platform ? new THREE.Box3().setFromObject(platform).max.y : robot.origin.y;
    const rugLift = rugBounds ? Math.max(0, rugBounds.max.y - floorY) : 0;
    const rootScale = body.node.getWorldScale(new THREE.Vector3());
    const rootRotation = body.node.getWorldQuaternion(new THREE.Quaternion());
    const rootInverse = body.node.matrixWorld.clone().invert(), point = new THREE.Vector3();
    const feet = [];
    for (const leg of robot.parts.slice(1)) {
      let minY = Infinity; const points = [];
      leg.node.updateWorldMatrix(true, true);
      leg.node.traverse(node => {
        const positions = node.geometry?.getAttribute('position'); if (!positions) return;
        for (let index = 0; index < positions.count; index++) {
          const p = new THREE.Vector3().fromBufferAttribute(positions, index).applyMatrix4(node.matrixWorld);
          minY = Math.min(minY, p.y); points.push(p);
        }
      });
      feet.push({ leg, points: points.filter(p => p.y < minY + .014).map(p => p.applyMatrix4(rootInverse).sub(leg.original.position)) });
    }
    const hip = new THREE.Quaternion(), yaw = new THREE.Quaternion();
    const sampleHeight = (x, z, heading) => {
      if (!rugBounds) return 0;
      const compact = profile(x, z, heading).compact; yaw.setFromAxisAngle(UP, heading);
      for (const foot of feet) {
        hip.setFromAxisAngle(foot.leg.hipAxis, -.16 * compact);
        for (const p of foot.points) {
          point.copy(p).applyQuaternion(hip).add(foot.leg.original.position).multiply(rootScale)
            .applyQuaternion(rootRotation).applyQuaternion(yaw);
          const px = x + point.x, pz = z + point.z;
          if (px >= rugBounds.min.x && px <= rugBounds.max.x && pz >= rugBounds.min.z && pz <= rugBounds.max.z) return rugLift;
        }
      }
      return 0;
    };
    robot.patrol = createRobotPatrol({ waypoints, sampleHeight, samplePose: profile,
      cornerRadius: (x, z) => profile(x, z, 0).compact > .5 ? .065 : .18,
      cruiseSpeed: .42, turnSpeed: .16, observationIndices: [6, 15, 18, 21, 30], observationSeconds: 1 });
    robot.period = robot.patrol.duration;
  }

  for (let index = 0; index < 3; index++) {
    add(`flower_petal_${index}`, `机械花瓣 ${index + 1} · 依次开合`, 10.8, record => {
      const open = pulse(record.time + record.phase, record.period, 2.1, 1.25, 2.8);
      localRotation(record.parts[0], axisZ, .29 * open);
      record.activity = open > .005 ? 'blooming' : 'resting';
    }, undefined, -index * .45);
  }
  add('speaker_gimbal', '环形音箱 · 摆环回响', 8.4, record => {
    const t = phaseAt(record.time, record.period);
    const amount = t < 5.6 ? Math.sin(t / 5.6 * TURN) * Math.pow(Math.sin(t / 5.6 * Math.PI), 2) : 0;
    localRotation(record.parts[0], axisZ, amount * .21);
    record.activity = Math.abs(amount) > .01 ? 'ringing' : 'resting';
  });
  const scout = add('v5_scout_drone', '侦察飞行器 · 悬停与侧倾', 6.4, record => {
    const phase = record.time / record.period * TURN;
    const lift = .052 * (.5 - .5 * Math.cos(phase));
    const part = record.parts[0]; part.targetPosition.copy(part.original.position).addScaledVector(record.worldUp, lift);
    // A small bank is applied around the actual parent-space fore/aft axis.
    localRotation(part, axisZ, .055 * Math.sin(phase));
    record.activity = 'hovering'; record.values.lift = lift;
  });
  if (scout) {
    const part = scout.parts[0]; part.positionOwned = true;
    part.node.parent.updateWorldMatrix(true, false);
    const origin = part.node.getWorldPosition(new THREE.Vector3());
    scout.worldUp = part.node.parent.worldToLocal(origin.clone().add(UP)).sub(part.node.parent.worldToLocal(origin));
  }
  add('v5_clock_dial', '轨道时钟 · 间歇分度', 7.5, record => {
    if (sceneHour !== null) {
      // Keep the authored dial pose at the scene clock's initial 10:00. Its
      // spindle then completes one revolution per twelve simulated hours.
      localRotation(record.parts[0], axisZ, (sceneHour - 10) / 12 * TURN);
      record.activity = 'tracking-daylight'; record.values.sceneHour = sceneHour;
      return;
    }
    const t = record.time + 1.7;
    const step = Math.floor(t / record.period) + smooth(Math.min(phaseAt(t, record.period) / .7, 1));
    localRotation(record.parts[0], axisZ, step * Math.PI / 6);
    record.activity = phaseAt(t, record.period) < .7 ? 'indexing' : 'resting';
  });
  const lens = add('v5_projector_lens', '投影镜头 · 伸缩对焦', 9.2, record => {
    const amount = pulse(record.time + 2, record.period, 1.15, 1.2, 1.6);
    const part = record.parts[0]; localRotation(part, axisZ, .31 * amount);
    part.targetPosition.copy(part.original.position); part.targetPosition.z += .01 * amount;
    record.activity = amount > .01 ? 'focusing' : 'resting';
  });
  if (lens) lens.parts[0].positionOwned = true;
  add('v5_data_panel_selector', '数据控制盘 · 双段切换', 8.8, record => {
    const t = phaseAt(record.time + 1.2, record.period);
    const amount = t < 2 ? smooth(t / 2) : t < 3.5 ? 1 : t < 5.8 ? 1 - 1.55 * smooth((t - 3.5) / 2.3) : -.55 + .55 * smooth((t - 5.8) / 3);
    localRotation(record.parts[0], axisZ, .52 * amount); record.activity = 'selecting';
  });
  add('original_trefoil_geometry', '玻璃雕塑 · 轴心自转', 24, record => {
    // The glass is revolved about its parent Y; this preserves radial clearance.
    parentRotation(record.parts[0], UP, record.time / record.period * TURN); record.activity = 'orbiting';
  });
  add('v5_floor_lamp_head', '落地灯 · 缓慢巡光', 12.5, record => {
    const amount = pulse(record.time + 3.6, record.period, 2.2, 1.5, 3.2);
    localRotation(record.parts[0], axisX, -.13 * amount); record.activity = amount > .01 ? 'looking-down' : 'resting';
  });
  add('communicator_panel_1', '通讯屏 · 轻启回落', 11.4, record => {
    const amount = pulse(record.time + 5.1, record.period, 1.6, 1.5, 2.5);
    localRotation(record.parts[0], axisX, -.19 * amount); record.activity = amount > .01 ? 'opening' : 'resting';
  });

  const applyPart = (part, follow) => {
    let changed = false;
    if (part.positionOwned && part.node.position.distanceToSquared(part.targetPosition) > EPSILON * EPSILON) {
      part.node.position.lerp(part.targetPosition, follow); changed = true;
    }
    if (part.rotationOwned && part.node.quaternion.angleTo(part.targetQuaternion) > EPSILON) {
      part.node.quaternion.slerp(part.targetQuaternion, follow); changed = true;
    }
    return changed;
  };
  return {
    update(delta, { enabled = true, hovered = null, sceneHour: nextSceneHour = null } = {}) {
      activeCount = 0; enabledLastFrame = enabled && !reducedMotion;
      if (!enabledLastFrame) return;
      const step = Number.isFinite(delta) ? Math.max(0, Math.min(delta, .05)) : 0;
      if (!step) return;
      elapsed += step;
      sceneHour = Number.isFinite(nextSceneHour) ? phaseAt(nextSceneHour, 24) : null;
      // Exponential following also absorbs external click tweens: no snapping
      // back to a cached pose when the click's transform ownership is released.
      const follow = 1 - Math.exp(-step * 8);
      if (hovered !== lastHovered) {
        for (const record of records) record.hovered = !!hovered && record.parts.some(part => related(part.node, hovered));
        lastHovered = hovered;
      }
      for (const record of records) {
        record.blocked = record.hovered || elapsed < record.heldUntil;
        if (!record.blocked) for (const node of record.watch) {
          if (gsap.isTweening(node.position) || gsap.isTweening(node.rotation) || gsap.isTweening(node.quaternion) || gsap.isTweening(node.scale)) { record.blocked = true; break; }
        }
        if (record.blocked) continue;
        record.time += step; record.sample(record);
        for (const part of record.parts) if (applyPart(part, follow)) activeCount++;
      }
    },
    hold(node, seconds = 1.6) {
      if (!node) return;
      for (const record of records) if (record.parts.some(part => related(part.node, node))) record.heldUntil = elapsed + Math.max(0, seconds);
    },
    getInteractionPose(node, original, active = true) {
      if (!original || reducedMotion || !records.some(record => record.parts.some(part => related(part.node, node)))) return original;
      let anchor = hoverAnchors.get(node);
      if (active && !anchor?.active) {
        anchor = { position: node.position.clone(), rotation: node.rotation.clone(), scale: original.scale.clone(), active: true };
        hoverAnchors.set(node, anchor);
      }
      if (anchor && !active) anchor.active = false;
      return anchor || original;
    },
    getHoverScaleLimit(node) {
      // The authored tripod keeps its normal inspection response in open
      // space, but cannot grow into the measured narrow-passage clearance.
      return robot && related(robot.parts[0].node, node) && (robot.values.compact || 0) > .02 ? 1 : Infinity;
    },
    getState() {
      return { revision: 9, enabled: !reducedMotion, running: enabledLastFrame, elapsed, activeCount,
        assetIds: records.flatMap(record => record.parts.map(part => part.id)),
        movingPartCount: records.reduce((count, record) => count + record.parts.length, 0),
        loops: records.map(record => ({ id: record.id, label: record.label, period: record.period, time: record.time,
          phase: phaseAt(record.time, record.period) / record.period, activity: record.activity,
          paused: record.blocked, movingParts: record.parts.map(part => part.id), ...record.values })),
        robot: robot ? { position: robot.parts[0].node.position.toArray(), originalPosition: robot.parts[0].original.position.toArray(),
          route: { ...robot.patrol.getState(), departureSeconds: 2.5, period: robot.patrol.duration, gaitPeriodSeconds: 1, scope: 'connected-room-floor' },
          compact: robot.values.compact || 0, floorLift: robot.values.floorLift || 0,
          activity: robot.activity, gait: robot.values.gait || 0, legIds: robot.parts.slice(1).map(part => part.id) } : null,
      };
    },
  };
}
