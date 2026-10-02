// Reposition the existing Blender objects before the entrance and hover systems
// capture their rest poses. No geometry or UVs are rebuilt here.
export function configureAboutBookEntry({ THREE, room }) {
  if (room.userData.aboutBookEntry) return room.userData.aboutBookEntry;
  const components = new Map();
  room.traverse(node => { if (node.userData.asset_id) components.set(node.userData.asset_id, node); });
  const book = components.get('notebook'), folio = components.get('creative_folio');
  const pen = components.get('coffee_table_pen'), dial = components.get('coffee_table_dial');
  const table = components.get('furniture.coffee_table');
  if (![book, folio, pen, dial, table].every(Boolean)) throw new Error('The sofa-side book assembly is missing.');
  room.updateMatrixWorld(true);
  const tabletop = new THREE.Box3().setFromObject(table, true).max.y;
  const place = (node, x, z, bottom) => {
    room.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(node, true);
    const center = bounds.getCenter(new THREE.Vector3());
    const pivot = node.getWorldPosition(new THREE.Vector3());
    pivot.add(new THREE.Vector3(x - center.x, bottom - bounds.min.y, z - center.z));
    node.position.copy(node.parent.worldToLocal(pivot));
    room.updateMatrixWorld(true);
  };
  book.scale.multiply(new THREE.Vector3(1.4, 1.2, 1.4));
  folio.scale.multiply(new THREE.Vector3(1.34, 1.12, 1.34));
  place(folio, -.21, 1.205, tabletop + .001);
  place(book, -.21, 1.205, new THREE.Box3().setFromObject(folio, true).max.y + .001);
  // Leave a clear gap around the larger cover while keeping every existing
  // loose object supported by the original rounded glass tabletop.
  pen.rotation.y = 0;
  place(pen, -.37, .71, tabletop + .001);
  place(dial, .50, 1.43, tabletop + .001);
  return room.userData.aboutBookEntry = {
    assetId: 'notebook', scaleFactor: [1.4, 1.2, 1.4], tabletop,
    direction: 'left', independentAssetsPreserved: true,
  };
}
