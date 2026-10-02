/** Sample Blender's architectural fold on the persistent room itself.
 * The loaded/default TRS is the final room. This module owns only fold.*
 * carrier transforms; layout, props, textures and geometry remain caller-owned.
 */
export function createFoldedRoomMotion({ THREE, room, clips, clipName = 'RoomUnfold' }) {
  if (!THREE?.AnimationMixer || !room?.isObject3D) throw new Error('Folded room requires Three.js and a persistent room root.');
  const matches = (clips ?? []).filter(clip => clip.name === clipName);
  if (matches.length !== 1) throw new Error(`Folded room requires exactly one ${clipName} clip; received ${matches.length}.`);
  const clip = matches[0];
  if (!(Number.isFinite(clip.duration) && clip.duration > 0) || !clip.tracks?.length) {
    throw new Error(`${clipName} must have a positive duration and architectural tracks.`);
  }
  const records = new Map(), properties = new Map();
  const widths = { position: 3, quaternion: 4, scale: 3 };
  const authoredName = node => node.userData?.name ?? node.name;
  const fail = (track, reason) => { throw new Error(`${clipName}: ${track.name}: ${reason}`); };
  const epsilon = 2e-5; // Float32 glTF animation and transform storage.

  // Validate every binding before activating a mixer or changing any node.
  for (const track of clip.tracks) {
    let path;
    try { path = THREE.PropertyBinding.parseTrackName(track.name); }
    catch { fail(track, 'unparseable track path'); }
    if (!Object.hasOwn(widths, path.propertyName) || path.objectName !== undefined
      || path.objectIndex !== undefined || path.propertyIndex !== undefined) {
      fail(track, 'only full position, quaternion and scale tracks are allowed');
    }
    const node = THREE.PropertyBinding.findNode(room, path.nodeName);
    if (!node || node === room) fail(track, 'target must be an internal architecture carrier, never the room root');
    if (node.isMesh || node.isBone || node.userData?.asset_id || !/^fold\.[^\s]+$/.test(authoredName(node) ?? '')) {
      fail(track, 'target must be an untagged fold.* architecture carrier, never a prop or render mesh');
    }
    let ancestor = node.parent;
    for (; ancestor && ancestor !== room; ancestor = ancestor.parent) {
      if (ancestor.userData?.asset_id && !ancestor.userData.asset_id.startsWith('architecture.')) {
        fail(track, 'a carrier cannot animate from inside an interactive prop');
      }
    }
    if (ancestor !== room) fail(track, 'target is outside the room hierarchy');
    if (!node.matrixAutoUpdate) fail(track, 'carrier matrixAutoUpdate must be enabled for TRS animation');
    const used = properties.get(node) ?? new Set();
    if (used.has(path.propertyName)) fail(track, 'duplicate tracks would compete for the same transform');
    used.add(path.propertyName); properties.set(node, used);
    if (!track.times?.length || !track.values?.length) fail(track, 'empty animation data');
    for (let index = 0; index < track.times.length; index++) {
      const time = track.times[index];
      if (!Number.isFinite(time) || time < 0 || time > clip.duration + epsilon
        || (index > 0 && time <= track.times[index - 1])) fail(track, 'keyframe times must be finite, ordered and inside the clip');
    }
    if (!Array.from(track.values).every(Number.isFinite)) fail(track, 'nonfinite animation values');
    const value = track.createInterpolant().evaluate(clip.duration);
    const expected = node[path.propertyName].toArray();
    if (value.length !== widths[path.propertyName]) fail(track, 'track sample width does not match its transform');
    const near = sign => expected.every((number, index) => Number.isFinite(number)
      && Math.abs(value[index] * sign - number) <= epsilon * Math.max(1, Math.abs(number)));
    if (!near(1) && !(path.propertyName === 'quaternion' && near(-1))) {
      fail(track, 'last keyframe must match the loaded final room pose');
    }
    if (!records.has(node)) records.set(node, { name: authoredName(node), position: node.position.clone(),
      rotation: node.rotation.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone() });
  }

  let mixer = null, action = null, progress = 1, phase = 'prepared';
  function bind() {
    if (mixer) return;
    mixer = new THREE.AnimationMixer(room);
    action = mixer.clipAction(clip);
    action.setLoop(THREE.LoopOnce, 1); action.clampWhenFinished = true;
    action.play(); action.paused = true;
  }
  function releaseBindings() {
    if (!mixer) return;
    mixer.stopAllAction(); mixer.uncacheRoot(room);
    mixer = action = null;
  }
  function restore() {
    if (phase === 'disposed') return;
    // Deactivation restores PropertyMixer's saved state. Do that first, then
    // write the exact GLB TRS so Euler round trips cannot change quaternions.
    releaseBindings();
    for (const [node, original] of records) {
      node.position.copy(original.position); node.rotation.copy(original.rotation);
      node.quaternion.copy(original.quaternion); node.scale.copy(original.scale);
    }
    room.updateWorldMatrix(true, true); progress = 1; phase = 'restored';
  }
  return {
    setProgress(value) {
      if (phase === 'disposed') return false;
      if (!Number.isFinite(value)) throw new Error(`${clipName}: progress must be finite.`);
      bind(); progress = Math.max(0, Math.min(1, value));
      // Mixer.setTime resets action.time; paused actions must instead be
      // sampled directly and evaluated with a zero delta. Resizes can re-seek
      // any progress without accumulating time or replaying completion events.
      action.time = progress * clip.duration; mixer.update(0);
      room.updateWorldMatrix(true, true); phase = 'sampling';
      return true;
    },
    restore,
    dispose() {
      if (phase === 'disposed') return;
      restore(); phase = 'disposed';
    },
    getState: () => ({ revision: 1, clipName, clipDuration: clip.duration,
      animatedNodes: [...records.values()].map(record => record.name), animatedNodeCount: records.size,
      trackCount: clip.tracks.length, progress, phase }),
  };
}
