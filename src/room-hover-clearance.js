// Hinges and controls remain attached to their mechanisms. Loose props can
// expand upwards for inspection without pushing their underside into a shelf.
const mounted = /^(flower_petal_|headphone_cup_|speaker_gimbal$|keyboard_dial$|camera_focus_lens$|robot_leg_|robot_service_hatch$|terminal_|communicator_panel_|small_planter_leaf_|floor_vase_leaf_|v5_clock_dial$|v5_projector_lens$|v5_data_panel_|v5_floor_lamp_head$|v5_scout_drone$)/;

export function isMountedRoomPart(node) {
  return node.userData.asset_id === 'lighting.ceiling_warm' || mounted.test(node.userData.asset_id ?? '');
}

export function createRoomHoverClearance({ THREE, room, components }) {
  room.updateMatrixWorld(true);
  const geometry = new WeakMap();
  for (const node of components.values()) {
    const box = new THREE.Box3().setFromObject(node, true);
    if (box.isEmpty()) continue;
    const pivot = node.getWorldPosition(new THREE.Vector3());
    geometry.set(node, { bottomOffset: Math.max(0, pivot.y - box.min.y), size: box.getSize(new THREE.Vector3()) });
  }
  return {
    position(node, original, factor) {
      const result = original.position.clone();
      const measured = geometry.get(node);
      if (!measured || factor <= 1 || isMountedRoomPart(node) || (node.userData.portal && node.userData.portal !== 'about')) return result;
      const id = node.userData.asset_id ?? '';
      // Furniture and wall fixtures already use a restrained scale response.
      if (/^(architecture\.|furniture\.|v5_orbital_clock|v5_mechanical_data_panel|v8_window_light_bar)/.test(id)) return result;
      const lift = measured.bottomOffset * (factor - 1) + Math.min(.08, measured.size.y * .08);
      const forward = Math.min(.12, measured.size.z * (factor - 1) * .2);
      const worldOrigin = new THREE.Vector3().setFromMatrixPosition(node.parent.matrixWorld);
      const localOffset = node.parent.worldToLocal(worldOrigin.clone().add(new THREE.Vector3(0, lift, forward)))
        .sub(node.parent.worldToLocal(worldOrigin));
      return result.add(localOffset);
    },
  };
}
