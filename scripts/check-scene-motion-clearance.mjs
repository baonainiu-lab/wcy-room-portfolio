import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import gsap from 'gsap';
import { createSceneMotion } from '../src/scene-motion.js';
import { actualFixture, verticesIn } from './lib/scene-motion-geometry.mjs';
import { build, intersections } from './lib/triangle-clearance.mjs';

const root = new URL('../', import.meta.url);
const hash = p => createHash('sha256').update(readFileSync(new URL(p, root))).digest('hex');
const meshes = n => { const a = []; n.traverse(c => { if (c.isMesh) a.push(c); }); return a; };
const results = [];
function check(label, run) { results.push({ check: label, status: 'passed', ...(run() || {}) }); }
try {
  check('Actual full-room patrol clears all room surfaces and independently phased chair; tripod feet retain floor or rug support', () => {
    const f = actualFixture(), m = createSceneMotion(f), robot = f.components.get('robot_companion'), chair = f.components.get('furniture.work_chair');
    const route = m.getState().robot.route;
    assert.equal(route.scope, 'connected-room-floor');
    assert.ok(route.durationSeconds > 0 && route.departureSeconds > 0, 'measured route exposes its complete clock');
    const belongs = (node, id) => { for (let p = node; p; p = p.parent) if (p.userData.asset_id === id) return true; return false; };
    const all = meshes(f.room), robotMeshes = meshes(robot), chairMeshes = meshes(chair);
    const excluded = ['robot_companion', 'furniture.work_chair', 'architecture.platform', 'furniture.rug', 'environment.orbital_dock', 'environment.warm_gallery'];
    const obstacles = all.filter(n => !excluded.some(id => belongs(n, id))).map(build);
    const chairTargets = chairMeshes.map(build), chairOriginal = f.snapshots.get(chair);
    const floor = all.filter(n => belongs(n, 'architecture.platform') || belongs(n, 'furniture.rug'));
    const rugTargets = floor.filter(n => belongs(n, 'furniture.rug')).map(build);
    const feet = [0, 1, 2].map(i => { const n = f.components.get(`robot_leg_0${i}`); return { n, vertices: verticesIn(n, n) }; });
    const floorRay = new THREE.Raycaster(), down = new THREE.Vector3(0, -1, 0), up = new THREE.Vector3(0, 1, 0);
    let minFloorGap = Infinity, maxSupportGap = 0, minPlatformEdge = Infinity, robotTravel = 0, sampledPoses = 0, chairPhasePoses = 0;
    const robotOrigin = robot.position.clone(), samples = [], visitedBounds = new THREE.Box3();
    const platformBounds = new THREE.Box3().setFromPoints(verticesIn(f.components.get('architecture.platform'), f.room));
    const chairBaseQ = new THREE.Quaternion().setFromEuler(chairOriginal.rotation);
    const duration = route.departureSeconds + 2 * route.durationSeconds + 1;
    for (let frame = 0; frame <= Math.ceil(duration * 120); frame++) {
      m.update(1 / 120);
      if (frame % 12) continue;
      f.scene.updateMatrixWorld(true); sampledPoses++;
      visitedBounds.expandByPoint(robot.position);
      for (const t of [...obstacles, ...rugTargets]) t.inverse.copy(t.mesh.matrixWorld).invert();
      for (const [sources, targets, name] of [[robotMeshes, [...obstacles, ...rugTargets], 'robot'], [chairMeshes, obstacles.filter(t => !t.mesh.parent.name.includes('room_static')), 'chair']]) {
        for (const source of sources) for (const target of targets) {
          const hits = intersections(source, target, 1);
          assert.equal(hits.length, 0, `${name} surface collision at ${frame / 120}s, robot ${robot.position.toArray()} vs ${target.mesh.parent.name}: ${JSON.stringify(hits[0])}`);
        }
      }
      // Hover can pause chair and robot independently; check the entire chair
      // phase range at each actual robot pose, not only correlated clocks.
      const currentChairQ = chair.quaternion.clone();
      for (let degree = 0; degree < 360; degree += 15) {
        chair.quaternion.setFromAxisAngle(up, degree * Math.PI / 180).multiply(chairBaseQ);
        chair.updateWorldMatrix(true, true); chairPhasePoses++;
        for (const t of chairTargets) t.inverse.copy(t.mesh.matrixWorld).invert();
        for (const source of robotMeshes) for (const target of chairTargets) {
          const hits = intersections(source, target, 1);
          assert.equal(hits.length, 0, `robot intersects independently phased chair at ${frame / 120}s, chair ${degree}deg: ${JSON.stringify(hits[0])}`);
        }
      }
      chair.quaternion.copy(currentChairQ); chair.updateWorldMatrix(true, true);
      let supportGap = Infinity;
      for (const foot of feet) {
        let lowest = null;
        for (const v of foot.vertices) {
          const world = v.clone().applyMatrix4(foot.n.matrixWorld);
          if (!lowest || world.y < lowest.y) lowest = world;
          minPlatformEdge = Math.min(minPlatformEdge, world.x - platformBounds.min.x, platformBounds.max.x - world.x, world.z - platformBounds.min.z, platformBounds.max.z - world.z);
        }
        floorRay.set(new THREE.Vector3(lowest.x, 1.5, lowest.z), down);
        const hits = floorRay.intersectObjects(floor, false).filter(h => h.point.y < .3 && h.point.y > .1);
        assert.ok(hits.length, `foot ${foot.n.userData.asset_id} has actual platform or rug below at ${frame / 120}s`);
        const gap = lowest.y - hits[0].point.y;
        minFloorGap = Math.min(minFloorGap, gap); supportGap = Math.min(supportGap, gap);
        assert.ok(gap >= -.001, `foot does not penetrate floor/rug at ${frame / 120}s: ${gap}`);
      }
      maxSupportGap = Math.max(maxSupportGap, supportGap);
      // The authored sole clearance plus one real rug step and compact stance
      // reserve may be visible during an anticipated step, but remains < 7cm.
      assert.ok(supportGap < .07, `support remains within one rug step plus authored/compact clearance: ${supportGap}`);
      robotTravel = Math.max(robotTravel, robot.position.distanceTo(robotOrigin));
      if (frame % 600 === 0) samples.push({ time: frame / 120, robot: robot.position.toArray() });
      if (process.env.MOTION_AUDIT_PROGRESS && frame % 1200 === 0) console.error(`geometry ${frame / 120}s / ${duration.toFixed(1)}s`);
    }
    assert.ok(minPlatformEdge > 0, 'all sampled foot vertices remain inside platform bounds');
    assert.ok(visitedBounds.max.x > 4 && visitedBounds.min.x < -3 && visitedBounds.min.z < -1.4 && visitedBounds.max.z > 2.9, 'actual motion reaches front, right and rear connected room floor');
    return { sampledPoses, sampleIntervalSeconds: .1, durationSeconds: duration, fullPatrolCycles: 2, route, obstacleMeshes: obstacles.length, chairIndependentPhaseSamples: chairPhasePoses, chairPhaseStepDegrees: 15, minimumFootFloorGapMetres: minFloorGap, maximumLowestSupportGapMetres: maxSupportGap, minimumPlatformBoundingEdgeMarginMetres: minPlatformEdge, maximumRobotTravelMetres: robotTravel, visitedBoundsMin: visitedBounds.min.toArray(), visitedBoundsMax: visitedBounds.max.toArray(), samples,
      limitation: 'Normal authored scales only: enlarged hover states are not audited; compact passages disable robot hover growth in production. Every moving source triangle edge is tested against actual room surfaces and rug at 0.1s samples over departure + two full patrols; independent chair angles sampled every15deg. Floor rays use each lowest foot vertex. This is sampled surface intersection testing, not a continuous collision proof, containment proof or IK foot planting. Existing chair-to-platform baked contact is unchanged.' };
  });

  check('Real GSAP ancestor transforms freeze the entire robot assembly; hover resumes its local clock without teleporting', () => {
    const f = actualFixture(), m = createSceneMotion(f), robot = f.components.get('robot_companion');
    const parts = ['robot_companion', 'robot_leg_00', 'robot_leg_01', 'robot_leg_02'].map(id => f.components.get(id));
    const pose = n => [...n.position.toArray(), ...n.quaternion.toArray()];
    for (let i = 0; i < 8 * 120; i++) m.update(1 / 120);
    const held = parts.map(pose), beforeClock = m.getState().loops.find(x => x.id === 'robot_companion').time;
    for (let i = 0; i < 6 * 120; i++) m.update(1 / 120, { hovered: parts[1] });
    parts.forEach((n, i) => assert.deepEqual(pose(n), held[i], 'hovering one leg freezes whole robot'));
    assert.equal(m.getState().loops.find(x => x.id === 'robot_companion').time, beforeClock);
    const previousPosition = robot.position.clone(), previousQ = robot.quaternion.clone();
    m.update(1 / 120);
    assert.ok(robot.position.distanceTo(previousPosition) < .01, 'hover release has no position jump');
    assert.ok(robot.quaternion.angleTo(previousQ) < .1, 'hover release has no rotation jump');
    const tween = gsap.to(robot.position, { x: robot.position.x + .1, duration: 3, ease: 'none' });
    gsap.ticker.sleep(); tween.totalTime(.5, false); assert.ok(gsap.isTweening(robot.position));
    const tweenPose = parts.map(pose), tweenClock = m.getState().loops.find(x => x.id === 'robot_companion').time;
    for (let i = 0; i < 6 * 120; i++) m.update(1 / 120);
    parts.forEach((n, i) => assert.deepEqual(pose(n), tweenPose[i], 'ancestor tween owns robot and leg transforms'));
    assert.equal(m.getState().loops.find(x => x.id === 'robot_companion').time, tweenClock);
    tween.kill(); m.update(1 / 120);
    assert.ok(m.getState().loops.find(x => x.id === 'robot_companion').time > tweenClock);
    const interactionPose = m.getInteractionPose(robot, f.snapshots.get(robot));
    assert.deepEqual(interactionPose.position.toArray(), robot.position.toArray(), 'interaction anchors current moving position');
    return { hoveredLegFreezesWholeRobot: true, ancestorTweenFreezesWholeRobot: true, interactionUsesCurrentPose: true };
  });

  check('One hour of active playback has bounded normalized poses, preserves independent IDs and creates no meshes or geometry', () => {
    const f = actualFixture(), m = createSceneMotion(f), originalMeshes = meshes(f.room);
    const geometry = originalMeshes.map(n => n.geometry);
    const moving = m.getState().assetIds.map(id => f.components.get(id));
    const original = new Map(moving.map(n => [n, { position: n.position.clone(), scale: n.scale.clone(), parent: n.parent }]));
    const platform = new THREE.Box3().setFromPoints(verticesIn(f.components.get('architecture.platform'), f.room));
    let maxTravel = 0, maxQuaternionError = 0;
    for (let frame = 0; frame < 3600 * 20; frame++) {
      m.update(.05); if (frame % 20) continue;
      for (const n of moving) {
        assert.ok([...n.position.toArray(), ...n.quaternion.toArray()].every(Number.isFinite));
        const delta = n.position.distanceTo(original.get(n).position);
        maxTravel = Math.max(maxTravel, delta);
        if (n.userData.asset_id === 'robot_companion') assert.ok(n.position.x > platform.min.x && n.position.x < platform.max.x && n.position.z > platform.min.z && n.position.z < platform.max.z, 'patrol root stays within real platform bounds');
        else assert.ok(delta < .08, 'other mechanisms retain their authored pivot or small calibrated displacement');
        maxQuaternionError = Math.max(maxQuaternionError, Math.abs(n.quaternion.length() - 1));
        assert.deepEqual(n.scale.toArray(), original.get(n).scale.toArray()); assert.equal(n.parent, original.get(n).parent);
        assert.equal(f.components.get(n.userData.asset_id), n);
      }
    }
    assert.ok(maxQuaternionError < 1e-6, 'no accumulated quaternion drift');
    assert.deepEqual(meshes(f.room), originalMeshes); originalMeshes.forEach((n, i) => assert.equal(n.geometry, geometry[i]));
    return { activeSeconds: 3600, maximumLocalTravelMetres: maxTravel, maximumQuaternionLengthError: maxQuaternionError, addedMeshes: 0, changedGeometries: 0 };
  });
  const modelPath = actualFixture().modelPath;
  const paths = ['src/scene-motion.js', 'src/robot-patrol.js', 'scripts/lib/scene-motion-geometry.mjs', 'scripts/lib/triangle-clearance.mjs', 'scripts/check-scene-motion-clearance.mjs', `public${modelPath}`];
  const report = { ok: true, revision: createSceneMotion(actualFixture()).getState().revision, generatedAt: new Date().toISOString(), scope: 'Actual active GLB surface and floor samples plus deterministic production motion; no rendered-image or FPS claim', hashes: Object.fromEntries(paths.map(p => [p, hash(p)])), results };
  if (process.argv.includes('--write-report')) writeFileSync(new URL(`docs/validation/scene-motion-clearance-v${report.revision}.json`, root), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} finally { gsap.globalTimeline.clear(); gsap.ticker.sleep(); }
