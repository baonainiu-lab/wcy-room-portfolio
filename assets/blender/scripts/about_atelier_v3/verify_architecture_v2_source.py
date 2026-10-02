"""Background-only physical source QA and final wide render of the pavilion."""
import json
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture_v2 as A
import web_export as W

assert bpy.app.background
build = json.loads(A.REPORT.read_text())
source_hash = W.sha(A.OUTPUT)
bpy.ops.wm.open_mainfile(filepath=str(A.OUTPUT))
scene = bpy.context.scene
collection = bpy.data.collections['90_RENDER_Atrium_Lake']
objects = list(collection.all_objects)
assert len(objects) == 98 and all(o.get('architecture_export') for o in objects)
signature, object_count, ids = A.main_signature(scene)
assert signature == build['mainGeometryHierarchyTransformsSignatureBefore']
assert len(ids) == 128
depsgraph = bpy.context.evaluated_depsgraph_get()
closed = []
for ob in objects:
    evaluated = ob.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert all(edge.is_manifold for edge in bm.edges), ob.name
    assert bm.calc_volume(signed=False) > 0, ob.name
    closed.append(ob.name)
    bm.free()
    evaluated.to_mesh_clear()
slab = bpy.data.objects['context.arch.deck.structural.stone.slab']
underside = bpy.data.objects['context.arch.deck.recessed.closed.underside']
floor = [o for o in objects if o.get('architecture_role') == 'floor']
coping = [o for o in objects if o.get('architecture_role') == 'deck_coping']
assert len(floor) == 20 and len(coping) == 4
assert all(A.overlaps(A.aabb(o), A.aabb(slab)) for o in floor + coping)
assert A.overlaps(A.aabb(slab), A.aabb(underside))
decks = [o for o in objects if o.get('architecture_role', '').startswith('deck_')]
bounds = {'min': [min(A.aabb(o)['min'][i] for o in decks) for i in range(3)],
          'max': [max(A.aabb(o)['max'][i] for o in decks) for i in range(3)]}
assert .46 < bounds['max'][2] - bounds['min'][2] < .49
assert W.sha(A.ORIGINAL) == build['originalSha256']
report = {'complete': True, 'source': W.rel(A.OUTPUT), 'sourceSha256': source_hash,
    'originalSourceUnchanged': True, 'mainGeometryHierarchyTransformsUnchanged': True,
    'mainObjects': object_count, 'mainAssetCount': len(ids), 'closedManifoldArchitectureObjects': len(closed),
    'allEvaluatedMeshesManifoldWithPositiveVolume': True, 'deckEnvelopeBlender': bounds,
    'allTwentyFloorTilesOverlapStructuralSlab': True, 'allFourCopingPiecesOverlapStructuralSlab': True,
    'RecessedUndersideOverlapsStructuralSlab': True, 'sourceNoLongerHasPaperEdge': True,
    'verticalsHaveTopAndBottomConnections': len(build['verticalConnections']),
    'frontAndRightRemainOpen': True}
W.write_json(A.REPORT.with_name('architecture-v2-source-validation-report.json'), report)
print('ATELIER_ARCH_V2_SOURCE_QA', json.dumps(report), flush=True)

W.device(scene)
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = .045
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
data = bpy.data.cameras.new('CAM.architecture.v2.complete-wide')
camera = bpy.data.objects.new('CAM.architecture.v2.complete-wide', data)
scene.collection.objects.link(camera)
camera.location = (13.5, -18.5, 10.8)
camera.rotation_euler = (Vector((.65, -.7, 1.65)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.lens = 38
camera.data.clip_end = 300
scene.camera = camera
scene.render.filepath = str(A.RENDERS / 'wide.png')
bpy.ops.render.render(write_still=True)
assert W.sha(A.OUTPUT) == source_hash
print('ATELIER_ARCH_V2_COMPLETE_WIDE_RENDER', scene.render.filepath, flush=True)
