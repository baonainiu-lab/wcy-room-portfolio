#!/usr/bin/env python3
"""Strict CPU-only Room19 asset gate; no Blender, baking, or compression.

Run with bundled Python (NumPy/Pillow):
  python scripts/verify-room-v19.py
  python scripts/verify-room-v19.py --geometry-review

Exit 0 means the complete CPU release gate passed; 2 means assets are pending
or the explicitly requested geometry-only diagnostic is not a release gate;
1 means verification failed. Browser appearance is always a separate review.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BLENDER = ROOT / 'assets/blender'
REPORT = BLENDER / 'photoreal-materials-v19-validation.json'
PREPARED_SHA = '45e258c586f5bc46203ca1d3ff6be14cfde72fcc28a40ec919040fcee9a9cd64'
EDITABLE_SHA = '175deff40751433f8e39783cc67b8fc437dd067a69ac9652df7d213f3ba8832f'
FLOOR = 'WEB8_room_static__baked__A0'
LAMP_ROOT = 'WEB19_CEILING_WARM_Root'
LAMP_MESH = 'WEB19_lighting.ceiling_warm__baked__A12'
REUSED = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11]
FRESH = [0, 8, 12]
LIGHT_SIZES = [4096] * 6 + [3072, 2048, 3072, 4096, 4096, 3072, 1024]
DATA_SIZES = [2048, 2048, 2048, 2048, 2048, 1024, 1024, 2048, 2048, 2048, 2048, 2048, 1024]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


worker = module('room_v19_compression_contract', 'scripts/compress-room-v19.py')
shared = worker.legacy.shared
sha = worker.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(filename):
    return json.loads((ROOT / filename).read_text())


def checked_file(filename, digest):
    target = ROOT / filename
    require(target.is_file(), f'Missing file: {filename}')
    require('room-v19-review-history' not in target.parts, f'Rejected historical V19 artifact: {filename}')
    require(sha(target) == digest, f'SHA256 mismatch: {filename}')
    return target


def source_contract():
    prepared = read('assets/blender/photoreal-materials-v19-prepared.json')
    source = read('assets/blender/photoreal-materials-v19-source.json')
    for report, expected in ((prepared, PREPARED_SHA), (source, EDITABLE_SHA)):
        require(report['complete'] is True and report['revision'] == 19 and report['reviewRevision'] == 2,
                'Expected the current complete V19 review2 source preparation.')
        require(report['sha256'] == expected, 'Prepared/editable SHA differs from the reviewed V19 contract.')
        checked_file(report['source'], report['sourceSha256'])
        checked_file(report['derivative'], expected)
        require(report['atlasCount'] == 13 and report['affectedSurfaceSlots'] == FRESH and
                report['unchangedSurfaceSlots'] == REUSED and report['rebakeDayNightSlots'] == list(range(13)) and
                report['introSlots'] == [0, 1, 8], 'Incorrect V19 atlas coverage.')
        require(report['legacyV18Preserved'] and report['aboutAssetsUnchanged'], 'Source preservation claim missing.')
        for recipe in report['recipeFiles']:
            checked_file(recipe['path'], recipe['sha256'])
        require(len(report['removedSourceCurves']) == 27 and len(set(report['removedSourceCurves'])) == 27,
                'Expected nine deleted floor curves in each of three source scenes.')
        for floor in report['floorMaterials']:
            require(floor['coatWeight'] == 0 and floor['geometryDisplacement'] is False and
                    floor['roughness'] == [.64, .82] and floor['expectedDielectricF0'] < .02,
                    'Refined low-gloss timber source recipe changed.')
        for lamp in report['lamps']:
            require(lamp['assetId'] == 'lighting.ceiling_warm' and lamp['colorTemperatureK'] == 3000 and
                    lamp['dayWatts'] == 0 and set(lamp['nightWatts']) == {'down', 'rearUpperWall', 'leftWall'} and
                    all(value > 0 for value in lamp['nightWatts'].values()), 'Warm fixture source recipe changed.')
    previous = read('assets/blender/photoreal-materials-v18-prepared.json')
    require(previous['sha256'] == prepared['sourceSha256'], 'V18 prepared lineage mismatch.')
    previous_editable = read('assets/blender/photoreal-materials-v18-source.json')
    require(previous_editable['sha256'] == source['sourceSha256'], 'V18 editable lineage mismatch.')
    require(prepared['changedExistingExportObjects'] == [FLOOR] and
            prepared['allOtherExistingExportGeometryUnchanged'] is True, 'Unexpected source geometry edits.')
    require(prepared['expectedExportTriangles'] == 418383 and len(prepared['lamps']) == 1 and
            prepared['lamps'][0]['root'] == LAMP_ROOT and prepared['lamps'][0]['parts'] == [LAMP_MESH] and
            prepared['lamps'][0]['atlas'] == 12, 'Current independent fixture/export geometry contract changed.')
    before, after = prepared['existingGeometryBefore'], prepared['existingGeometryAfter']
    require(set(after) - set(before) == {LAMP_ROOT, LAMP_MESH} and set(before) <= set(after),
            'Source objects changed outside floor removal and independent fixture.')
    for name, old in before.items():
        expected = dict(old)
        if name == FLOOR:
            require(old['geometry'] != after[name]['geometry'], 'Floor geometry was not changed.')
            expected['geometry'] = after[name]['geometry']
        require(expected == after[name], f'Source geometry/ID/ownership/parent changed: {name}')
    removed = prepared['removedFloorGrid']
    require(len(removed) == 1 and removed[0]['object'] == FLOOR, 'Unexpected floor removal object.')
    removal = removed[0]
    require((removal['removedComponents'], removal['removedPolygons'], removal['removedTriangles']) == (9, 90, 180)
            and removal['remainingUvsExactlyPreserved'] and removal['remainingCornerNormalMaxError'] == 0,
            'Floor removal source evidence differs from the accepted nine strips.')
    index_map = read(prepared['floorRemovalIndexMap'])
    require(index_map['sourceSha256'] == prepared['sourceSha256'] and index_map['mesh'] == FLOOR and
            index_map['originalPolygonIndices'] == list(range(90)) and
            index_map['originalLoopTriangleIndices'] == list(range(180)) and
            index_map['originalMeshTriangles'] == 23712 and index_map['remainingUvsExactlyPreserved'] and
            index_map['remainingOriginalCornerNormalsMaxError'] == 0, 'Floor deletion index map mismatch.')
    approved = read('docs/validation/about-approved-material-baseline.json')
    require(len(approved['files']) == 38, 'Expected the approved 38-file About baseline.')
    for filename, digest in approved['files'].items():
        checked_file(filename, digest)
    return prepared, source, approved


def read_glb(filename):
    doc, chunks = shared.parse_glb((ROOT / filename).read_bytes())
    return doc, next(data for kind, data in chunks if kind == shared.BIN_CHUNK)


def accessor(doc, binary, number):
    a = doc['accessors'][number]
    require('sparse' not in a and not a.get('normalized'), 'Unexpected sparse/normalized geometry accessor.')
    view = doc['bufferViews'][a['bufferView']]
    require(view.get('buffer', 0) == 0, 'Unexpected external geometry buffer.')
    dtype = np.dtype({5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[a['componentType']])
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    stride = view.get('byteStride', width * dtype.itemsize)
    local = a.get('byteOffset', 0)
    end = local + max(0, a['count'] - 1) * stride + width * dtype.itemsize
    require(stride >= width * dtype.itemsize and end <= view['byteLength'], 'Accessor exceeds its buffer view.')
    start = view.get('byteOffset', 0) + local
    require(start + end - local <= len(binary), 'Accessor exceeds GLB binary chunk.')
    result = np.ndarray((a['count'], width), dtype=dtype, buffer=binary,
                        offset=start, strides=(stride, dtype.itemsize)).copy()
    require(np.isfinite(result).all(), 'Non-finite mesh data.')
    return result


def array_fingerprint(value):
    # Numeric canonicalization avoids index component width and -0/+0 artifacts.
    numeric = value.astype('<f8' if value.dtype.kind == 'f' else '<i8')
    numeric[numeric == 0] = 0
    return dict(shape=list(value.shape), sha256=hashlib.sha256(numeric.tobytes()).hexdigest())


def nodes(doc):
    result = {node['name']: node for node in doc['nodes']}
    require(len(result) == len(doc['nodes']), 'Duplicate or missing node names.')
    return result


def hierarchy(doc):
    parents = {}
    for node in doc['nodes']:
        for child in node.get('children', []):
            require(child not in parents, 'Node has more than one parent.')
            parents[child] = node['name']
    return {node['name']: dict(parent=parents.get(index), hasMesh='mesh' in node,
                             children=sorted(doc['nodes'][child]['name'] for child in node.get('children', [])),
                             **{key: node[key] for key in ('translation', 'rotation', 'scale', 'matrix', 'extras') if key in node})
            for index, node in enumerate(doc['nodes'])}


def primitives(doc, name):
    node = nodes(doc)[name]
    return doc['meshes'][node['mesh']]['primitives'] if 'mesh' in node else []


def geometry_fingerprint(doc, binary, name):
    return [dict(mode=primitive.get('mode', 4), indices=array_fingerprint(accessor(doc, binary, primitive['indices'])),
                 attributes={key: array_fingerprint(accessor(doc, binary, value))
                             for key, value in sorted(primitive['attributes'].items())})
            for primitive in primitives(doc, name)]


def floor_change(before, before_bin, after, after_bin):
    old_primitives, new_primitives = primitives(before, FLOOR), primitives(after, FLOOR)
    require(len(old_primitives) == len(new_primitives) == 1, 'Floor must remain a single primitive.')
    old, new = old_primitives[0], new_primitives[0]
    require(old.get('mode', 4) == new.get('mode', 4) == 4, 'Expected indexed triangles.')
    require(set(old['attributes']) == set(new['attributes']) == {'POSITION', 'NORMAL', 'TEXCOORD_0'},
            'Floor position, normal or BakeUV attributes changed.')
    oi = accessor(before, before_bin, old['indices']).ravel()
    ni = accessor(after, after_bin, new['indices']).ravel()
    require((len(oi) // 3, len(ni) // 3) == (23712, 23532), 'Floor triangle count differs from removing 180 triangles.')
    details = {}
    for key in sorted(old['attributes']):
        oa = accessor(before, before_bin, old['attributes'][key])
        na = accessor(after, after_bin, new['attributes'][key])
        require((len(oa), len(na)) == (21635, 21373), f'Unexpected {key} vertex count after floor strip removal.')
        require(int(oi.max()) < len(oa) and int(ni.max()) < len(na), 'Floor index outside vertex buffer.')
        expected, actual = oa[oi[180 * 3:]], na[ni]
        require(np.array_equal(expected, actual), f'Retained floor indexed-corner {key} differs from V18 after triangle 180.')
        details[key] = dict(retainedCorners=array_fingerprint(actual), exportedVertices=array_fingerprint(na), maxError=0)
    return dict(node=FLOOR, oldVertices=21635, newVertices=21373, oldTriangles=23712, newTriangles=23532,
                removedTriangles=180, removedComponents=9, deletedOldTriangleRange=[0, 179],
                indexedCornersExactlyPreserved=True, attributes=details, indices=array_fingerprint(ni),
                fingerprintEncoding='Float attributes as little-endian float64, indices as int64, signed zero canonicalized.')


def geometry_audit(filename, prepared, final=True):
    baseline_path = ROOT / 'public/models/orbital-atelier-v18.glb'
    baseline_export = read('assets/blender/dual-lighting-v18-export-report.json')
    checked_file(baseline_path, baseline_export['sha256'])
    before, bb = read_glb(baseline_path)
    after, ab = read_glb(filename)
    old_nodes, new_nodes = nodes(before), nodes(after)
    require(set(new_nodes) - set(old_nodes) == {LAMP_ROOT, LAMP_MESH} and set(old_nodes) <= set(new_nodes),
            'Export changed nodes outside the independent warm fixture.')
    old_h, new_h = hierarchy(before), hierarchy(after)
    unchanged = []
    for name in old_nodes:
        require(old_h[name] == new_h[name], f'Existing hierarchy, ID, transform or ownership changed: {name}')
        if name != FLOOR:
            require(geometry_fingerprint(before, bb, name) == geometry_fingerprint(after, ab, name),
                    f'Unexpected existing mesh/UV/normal/index change: {name}')
            if 'mesh' in old_nodes[name]:
                unchanged.append(name)
    floor = floor_change(before, bb, after, ab)
    ids = [node.get('extras', {}).get('asset_id') for node in after['nodes'] if node.get('extras', {}).get('asset_id')]
    require(len(ids) == len(set(ids)) == 96 and sorted(ids) == sorted(baseline_export['componentIds'] + ['lighting.ceiling_warm']),
            'The original 95 asset IDs plus exactly one warm fixture are required.')
    require(new_h[LAMP_ROOT]['parent'] is None and new_h[LAMP_ROOT]['children'] == [LAMP_MESH] and
            new_h[LAMP_MESH]['parent'] == LAMP_ROOT and
            new_nodes[LAMP_MESH]['extras']['owner_asset_id'] == 'lighting.ceiling_warm' and
            new_nodes[LAMP_MESH]['extras']['bake_atlas'] == 12, 'Ceiling fixture is not an independent owned asset.')
    triangles = sum(len(accessor(after, ab, p['indices'])) // 3 for mesh in after['meshes'] for p in mesh['primitives'])
    if final:
        require(triangles == prepared['expectedExportTriangles'], 'Final triangle count differs from current prepared source.')
        require(all(m.get('name') != 'GEOMETRY_REVIEW_ONLY' for m in after['materials']), 'Gray review GLB is not publishable.')
        scene = after['scenes'][after.get('scene', 0)].get('extras', {})
        require(scene.get('source_revision') == scene.get('lighting_revision') == 19, 'Missing V19 runtime scene provenance.')
    return dict(complete=final, geometryDiagnosticComplete=True, preparedSha256=PREPARED_SHA,
                currentRuntimeVerified=final, baseline=str(baseline_path.relative_to(ROOT)), baselineSha256=sha(baseline_path),
                path=str((ROOT / filename).relative_to(ROOT)), sha256=sha(ROOT / filename), floor=floor,
                oldNodeCount=len(old_nodes), newNodeCount=len(new_nodes), preservedAssetIds=95, addedAssetIds=['lighting.ceiling_warm'],
                unchangedExistingMeshCount=len(unchanged), unchangedExistingMeshNodes=unchanged,
                oldNodeHierarchyIdsOwnershipTransformsExactlyPreserved=True, addedNodes=[LAMP_ROOT, LAMP_MESH],
                triangles=triangles, expectedCurrentTriangles=prepared['expectedExportTriangles'],
                nodeIdentityPolicy='Compare by stable node name, allowing Blender mesh datablock suffixes such as .001.')


def pending_inputs():
    requirements = [
        ('assets/blender/room-v19-surface-reuse-proof.json', 'sourceSha256', False),
        ('assets/blender/room-v19-surface-inheritance.json', 'sourceSha256', True),
        ('assets/blender/photoreal-materials-v19-compression.json', 'preparedSha256', True),
        ('assets/blender/dual-lighting-v19-export-report.json', 'preparedSha256', True),
    ]
    requirements += [(f'public/textures/lighting-v19/{state}-{slot}-manifest.json', 'sourceSha256', False)
                     for state in ('day', 'night', 'surface') for slot in range(13)]
    requirements += [(f'public/textures/intro-clean-v19/day-{slot}-manifest.json', 'sourceSha256', False) for slot in (0, 1, 8)]
    requirements += [(f'public/textures/lighting-v19/reflection-{state}.json', 'sourceSha256', False) for state in ('day', 'night')]
    pending = []
    for filename, binding, complete in requirements:
        if not (ROOT / filename).is_file():
            pending.append(dict(path=filename, reason='missing'))
            continue
        record = read(filename)
        if record.get(binding) != PREPARED_SHA:
            pending.append(dict(path=filename, reason='stale_source', recordedSha256=record.get(binding)))
        elif record.get('complete') is False or (complete and record.get('complete') is not True):
            pending.append(dict(path=filename, reason='incomplete'))
    for filename in ('public/models/orbital-atelier-v19.glb', 'public/models/orbital-atelier-v19-compressed.glb'):
        if not (ROOT / filename).is_file():
            pending.append(dict(path=filename, reason='missing'))
    return pending


def surface_contract(prepared):
    reuse = worker.reuse_proof(PREPARED_SHA)
    require(reuse and reuse['slots'] == REUSED, 'No exact current source-bound surface reuse proof.')
    proof = read('assets/blender/room-v19-surface-reuse-proof.json')
    proof_rows = {row['slot']: row for row in proof['surfaces']}
    require(len(proof_rows) == len(proof['surfaces']) == 10, 'Duplicate or missing surface proof slots.')
    for row in proof_rows.values():
        require(len(row['shaderGraphsSha256']) == len(row['geometryUvNormalsSignature']) == 64 and row['materials'],
                'Surface inheritance requires shader graph and geometry/UV/normal/world-transform signatures.')
    inherited = read('assets/blender/room-v19-surface-inheritance.json')
    require(inherited['complete'] and inherited['sourceSha256'] == PREPARED_SHA and
            inherited['oldSourceSha256'] == prepared['sourceSha256'] and
            inherited['inheritedSlots'] == REUSED and inherited['rebakedSurfaceSlots'] == FRESH,
            'Wrong surface inheritance source or coverage.')
    rows = {row['slot']: row for row in inherited['records']}
    require(set(rows) == set(REUSED) and len(inherited['records']) == 10, 'Incomplete inheritance records.')
    for slot in range(13):
        filename = f'public/textures/lighting-v19/surface-{slot}-manifest.json'
        manifest = read(filename)
        require(manifest['complete'] and manifest['sourceSha256'] == PREPARED_SHA and manifest['slot'] == slot and
                manifest['dataSize'] == DATA_SIZES[slot] and manifest['geometryUvNormalsUnchanged'] and
                manifest['decodedNormalsRenormalizedBeforeQuantization'], f'Invalid surface manifest {slot}.')
        if slot in FRESH:
            require(not manifest.get('inheritedFrom'), f'Surface {slot} must be freshly baked.')
        else:
            row = rows[slot]
            require(row['proof'] == proof_rows[slot] and (ROOT / row['manifest']).resolve() == (ROOT / filename).resolve(),
                    f'Inheritance proof/manifest mismatch for slot {slot}.')
            checked_file(row['manifest'], row['manifestSha256'])
            provenance = manifest['inheritedFrom']
            checked_file(provenance['manifest'], provenance['manifestSha256'])
            checked_file(provenance['equivalenceProof'], provenance['equivalenceProofSha256'])
            checked_file(provenance['sourceProof'], provenance['sourceProofSha256'])
            require(provenance['sourceSha256'] == prepared['sourceSha256'], 'Wrong inherited source SHA.')
            old = read(provenance['manifest'])
            for kind in ('normal', 'specular'):
                require(manifest[kind]['sha256'] == old[kind]['sha256'] == row['maps'][kind]['sha256'],
                        f'Inherited {kind} pixels changed in slot {slot}.')
        for kind in ('normal', 'specular'):
            data = manifest[kind]
            checked_file(data['path'], data['sha256'])
            require(data['dimensions'] == [DATA_SIZES[slot]] * 2 and
                    data['valuesOutsideRangeBeyondFloatToleranceFraction'] == 0, f'Invalid {kind} data: slot {slot}.')
    return reuse


def texture_contract(compression, reuse):
    require(compression['complete'] and compression['preparedSha256'] == PREPARED_SHA and
            compression['codecRevision'] == worker.CODEC_REVISION and compression['surfaceReuse'] == reuse,
            'Compression is not complete for the exact current source and reuse proof.')
    records = {row['key']: row for row in compression['textures']}
    require(len(compression['textures']) == len(records) == 58 and set(records) == worker.EXPECTED and
            compression['runtimeTextureCount'] == 58, 'Expected exactly 58 KTX2 textures.')
    candidates = worker.candidates(PREPARED_SHA, reuse)
    require(len(candidates) == 55 and len({row['key'] for row in candidates}) == 55, 'Expected 55 source-bound generated textures.')
    for candidate in candidates:
        require(worker.cached(records[candidate['key']], candidate, PREPARED_SHA), f'Outdated compression: {candidate["key"]}')
    for row in records.values():
        require(row['preparedSha256'] == PREPARED_SHA, f'Stale texture record: {row["key"]}')
        source = checked_file(row['source'], row['sourceSha256'])
        output = checked_file(row['path'], row['sha256'])
        require(output.stat().st_size == row['bytes'], f'Wrong KTX size: {row["key"]}')
        blob = output.read_bytes()
        metadata = shared.ktx_info(blob)
        subprocess.run([str(worker.linear.VALIDATOR), 'validate', str(output)], check=True, capture_output=True, text=True)
        if row['key'] in ('day-window', 'night-window', 'static-screen'):
            for target in (source, output):
                require(sha(target) == sha(ROOT / 'public/textures/lighting-v16' / target.name), 'Static display artwork changed.')
            continue
        require(metadata['resolution'] == row['dimensions'] and metadata['mipLevels'] == row['mipLevels'] and
                row['transferFunction'] == 'linear' and row['targetType'] == 'RGBA' and row['premultipliedAlpha'] is False,
                f'Invalid linear/full-mip contract: {row["key"]}')
        dfd_offset, dfd_length = struct.unpack_from('<II', blob, 48)
        require(dfd_length >= 24 and dfd_offset + dfd_length <= len(blob), 'Invalid KTX data format descriptor.')
        require(blob[dfd_offset + 14] == 1 and blob[dfd_offset + 15] & 1 == 0,
                f'Actual KTX DFD is nonlinear or premultiplied: {row["key"]}')
        levels = row['mipStatistics']
        # Surface level 0 is the unchanged, hash-checked PNG; only generated
        # levels have filtering statistics. Radiance is re-encoded at level 0
        # and therefore also has a level-0 quantization statistic.
        first_generated_level = 0 if row['kind'] == worker.LIGHT_KIND else 1
        if first_generated_level == 1:
            require(row['kind'] in ('normal', 'specular') and
                    row['encodedSource']['sha256'] == row['sourceSha256'],
                    f'Surface base mip must be the unchanged source: {row["key"]}')
            with Image.open(source) as image:
                require(list(image.size) == row['dimensions'], f'Surface base mip dimensions: {row["key"]}')
        require(row['mipLevels'] == max(row['dimensions']).bit_length() and
                [m['level'] for m in levels] == list(range(first_generated_level, row['mipLevels'])) and
                all(m['dimensions'] == [max(1, value >> m['level']) for value in row['dimensions']] for m in levels),
                f'Incomplete linear mip evidence: {row["key"]}')
        if row['state'] in ('day', 'night', 'intro'):
            require(row['kind'] == worker.LIGHT_KIND and row['sourceEncoding'] == 'RGBM32' and
                    row['encodedSource']['encoding'] == 'LogRGB32 k256 alpha1', 'Wrong runtime radiance codec.')
            encoded = checked_file(row['encodedSource']['path'], row['encodedSource']['sha256'])
            with Image.open(encoded) as image:
                require(image.mode == 'RGBA' and list(image.size) == row['dimensions'] and image.getextrema()[3] == (255, 255),
                        'LogRGB runtime alpha must be identically one.')
    return records


def light_contract(records):
    recovered, manifests = [], []
    for state, slots, folder in [('day', range(13), 'lighting-v19'), ('night', range(13), 'lighting-v19'),
                                 ('intro', (0, 1, 8), 'intro-clean-v19')]:
        for slot in slots:
            prefix = 'day' if state == 'intro' else state
            raw = read(f'public/textures/{folder}/{prefix}-{slot}-manifest.json')
            require(raw['sourceSha256'] == PREPARED_SHA and raw['samples'] == 96 and raw['slot'] == slot and
                    raw['state'] == prefix and raw['dimensions'] == [LIGHT_SIZES[slot]] * 2 and
                    raw['encoding'] == 'RGBM32' and raw['glossyExcluded'] and raw['geometryUvNormalsUnchanged'] and
                    not raw.get('inheritedFrom'), f'Light map is not a fresh current-source 96-sample bake: {state}-{slot}')
            if state == 'intro':
                require(raw['cleanIntro'] and raw['receiverOnly'], 'Intro map is not clean receiver-only.')
            checked_file(raw['path'], raw['sha256'])
            scale, overflow = worker.light_parameters(raw)
            encoded = records[f'{state}-{slot}']
            require(encoded['radianceScale'] == scale, 'Radiance normalization scale mismatch.')
            if overflow:
                require(state == 'night', 'Only the night endpoint supports normalized HDR outliers.')
                with Image.open(ROOT / raw['path']) as image:
                    restored, actual_scale, detail = worker.linear.restored_radiance(
                        np.asarray(image, dtype=np.uint8), ROOT / raw['path'], scale, overflow)
                require(actual_scale == scale and detail['count'] == overflow['count'] and detail['sha256'] == overflow['sha256'] and
                        detail['restoredMaximum'] == raw['sourceRadianceMaximum'] and encoded['radianceOverflow'] == detail and
                        encoded['sourceSceneRadiancePeak'] == float(restored.max()), 'HDR sidecar restoration mismatch.')
                recovered.append(dict(slot=slot, scale=scale, peak=raw['sourceRadianceMaximum'], channels=overflow['count'],
                                      sidecarSha256=overflow['sha256']))
                del restored
            else:
                require(scale == 1, 'Unexpected radiance scale without outliers.')
            manifests.append(raw)
    probes = worker.probe_records(PREPARED_SHA)
    require(probes and {p['state'] for p in probes} == {'day', 'night'}, 'Missing fresh reflection probes.')
    for probe in probes:
        require(probe['samples'] == 64 and probe['dimensions'] == [2048, 1024] and not probe.get('inheritedFrom'),
                'Reflection probe must be fresh 2048x1024, 64 samples.')
    return manifests, recovered, probes


def model_contract(compression, records, prepared):
    model = compression['model']
    raw_path = ROOT / 'public/models/orbital-atelier-v19.glb'
    checked_file(raw_path, model['sourceSha256'])
    packed_path = checked_file(model['path'], model['sha256'])
    require(packed_path.resolve() == (ROOT / 'public/models/orbital-atelier-v19-compressed.glb').resolve() and
            packed_path.stat().st_size == model['bytes'] and raw_path.stat().st_size == model['sourceBytes'], 'Wrong V19 model path/size.')
    export = read('assets/blender/dual-lighting-v19-export-report.json')
    require(export['complete'] and export['preparedSha256'] == PREPARED_SHA and export['sha256'] == sha(raw_path) and
            export['atlasSizes'] == LIGHT_SIZES and export['surfaceSizes'] == DATA_SIZES, 'Export provenance or atlas sizing mismatch.')
    require((ROOT / export['model']).resolve() == raw_path.resolve() and export['bytes'] == raw_path.stat().st_size and
            export['source'] == 'assets/blender/orbital-atelier-v19.blend', 'Wrong raw export source/path/size.')
    audit = geometry_audit(raw_path, prepared)
    raw, rb = read_glb(raw_path)
    packed, pb = read_glb(packed_path)
    require(hierarchy(raw) == hierarchy(packed), 'Compressed hierarchy/extras/transforms changed.')
    for name in nodes(raw):
        require(geometry_fingerprint(raw, rb, name) == geometry_fingerprint(packed, pb, name), f'Compressed geometry changed: {name}')
    for key in set(raw) - {'images', 'textures', 'bufferViews', 'buffers', 'extensionsUsed', 'extensionsRequired'}:
        require(raw[key] == packed.get(key), f'Compression modified non-texture GLB data: {key}')
    require(export['triangles'] == audit['triangles'] and export['nodes'] == len(raw['nodes']) and
            sorted(export['componentIds']) == sorted(n['extras']['asset_id'] for n in raw['nodes'] if n.get('extras', {}).get('asset_id')),
            'Export counts or component IDs disagree with GLB contents.')
    scales = {str(row['slot']): row['radianceScale'] for row in records.values()
              if row['state'] == 'night' and row.get('radianceScale', 1) != 1}
    require(scales == compression['nightRadianceScale'] == export['nightRadianceScale'], 'Night endpoint normalization mismatch.')
    bound_images = []
    for index, material in enumerate(raw['materials']):
        name = material.get('name', '')
        if name.startswith('WEB8_LIGHTMAP_'):
            slot = name.rsplit('_', 1)[1]
            extras = material['extras']
            require(extras['diffuseEncoding'] == 'LogRGB32 gain256' and extras['nightRadianceScale'] == scales.get(slot, 1) and
                    extras['glossyBaked'] is False, 'GLB material runtime codec mismatch.')
            key = f'night-{slot}'
        elif name == 'WEB8_WINDOW_CITY':
            key = 'night-window'
        elif name == 'WEB8_IMAGE_MAT_Rendered_3D_ScreenArtwork':
            key = 'static-screen'
        else:
            continue
        record = records[key]
        for doc, binary, expected, packed_image in ((raw, rb, record.get('encodedSource', {}).get('sha256', record['sourceSha256']), False),
                                                   (packed, pb, record['sha256'], True)):
            texture = doc['textures'][doc['materials'][index]['pbrMetallicRoughness']['baseColorTexture']['index']]
            image_index = texture['extensions']['KHR_texture_basisu']['source'] if packed_image else texture['source']
            image = doc['images'][image_index]
            require(image['mimeType'] == ('image/ktx2' if packed_image else 'image/png'), 'Unexpected embedded image type.')
            data = shared.view_bytes(doc, binary, doc['bufferViews'][image['bufferView']])
            require(hashlib.sha256(data).hexdigest() == expected, f'Embedded GLB image differs from current texture: {key}')
        bound_images.append(key)
    require(set(bound_images) == {f'night-{i}' for i in range(13)} | {'night-window', 'static-screen'}, 'GLB image binding coverage mismatch.')
    audit.update(compressedPath=str(packed_path.relative_to(ROOT)), compressedSha256=sha(packed_path),
                 compressedGeometryHierarchyExactlyPreserved=True, boundEmbeddedImages=bound_images)
    worker.write(BLENDER / 'room-v19-geometry-audit.json', audit)
    return export, audit, scales


def legacy_contract():
    count = 0
    for version in ('v16', 'v17', 'v18'):
        previous = read(f'assets/blender/photoreal-materials-{version}-compression.json')
        if version in ('v16', 'v18'):
            require(previous['complete'] is True, f'Previously released {version} must remain complete.')
            checked_file(previous['model']['path'], previous['model']['sha256'])
            checked_file(f'public/models/orbital-atelier-{version}.glb', previous['model']['sourceSha256'])
        else:
            # V17 is an unfinished historical bake, not a published model
            # release. Its existing texture bytes still must remain unchanged.
            require(previous['complete'] is False and 'model' not in previous,
                    'Unexpected change to the historical incomplete V17 manifest.')
        for row in previous['textures']:
            checked_file(row['source'], row['sourceSha256'])
            checked_file(row['path'], row['sha256'])
            count += 1
    return count


def verify(prepared, approved):
    reuse = surface_contract(prepared)
    compression = read('assets/blender/photoreal-materials-v19-compression.json')
    records = texture_contract(compression, reuse)
    manifests, recovered, probes = light_contract(records)
    require(probes == compression['reflectionProbes'], 'Compression probe records differ from current source-bound probes.')
    export, audit, scales = model_contract(compression, records, prepared)
    legacy_count = legacy_contract()
    # Recheck source bytes after reading all outputs to reject a mixed concurrent run.
    source_contract()
    return dict(complete=True, status='cpu_release_passed', revision=19, preparedSha256=PREPARED_SHA, editableSha256=EDITABLE_SHA,
                model=compression['model'], surfaceReuse=reuse, freshSurfaceSlots=FRESH,
                surfaceInheritanceProofSha256=sha(BLENDER / 'room-v19-surface-inheritance.json'),
                geometryAudit='assets/blender/room-v19-geometry-audit.json',
                geometryAuditSha256=sha(BLENDER / 'room-v19-geometry-audit.json'),
                floorGridStripsRemoved=9, retainedFloorIndexedCornersExactlyPreserved=True,
                otherExistingGeometryUvsNormalsUnchanged=True, preservedAssetIds=95, addedAssetIds=['lighting.ceiling_warm'],
                independentCeilingFixture=True, all58TextureHashesVerified=True, all29LightMapsFreshSourceBound=True,
                allRecordedNightHdrOutliersRecovered=True, recoveredNightHighlights=recovered, nightRadianceScale=scales,
                webLogRgb32Gain256=True, webLightAlphaConstantOne=True, actualKtxLinearTransferAndFullMipChainsVerified=True,
                ktxValidationCount=58, linearMipGenerationEvidenceVerified=True, probeOrientationMatches=True,
                reflectionProbeSamples=64, reflectionProbeDimensions=[2048, 1024],
                mainAtlasPairs=13, surfaceAtlasPairs=13, introAtlases=3, lightingSamples=96,
                triangles=export['triangles'], nodes=export['nodes'], materials=len(export['materials']), assetIds=96,
                v18SourceFilesUnchanged=True, legacyModelsTexturesUnchanged=True, legacyTextureRecordsChecked=legacy_count,
                legacyModelVersionsVerified=['v16', 'v18'], legacyIncompleteBakeTextureVersionsVerified=['v17'],
                approvedAboutFilesUnchanged=len(approved['files']), lightingBakeSeconds=round(sum(m['seconds'] for m in manifests), 2),
                glass=export['glass'], browserVerified=False, visualApproval=False,
                limitations=['CPU asset integrity does not establish browser rendering quality, wall-wash appearance, or subjective timber whiteness.'],
                provenance='Room19 scene/model/material preparation, surface bakes, HDR reflection captures and raw GLB export through Blender MCP; remaining full-atlas lighting and intro bakes use the documented offline Blender CLI fallback after repeated MCP 120-second timeouts. GPU OIDN changes only the denoising backend, with quality/input settings retained. Export hashes bind the resulting assets to the same prepared source. Compression and this gate are CPU-only.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry-review', action='store_true', help='Audit historical gray GLB geometry only; always non-release exit 2.')
    args = parser.parse_args()
    destination = BLENDER / 'room-v19-geometry-review-audit.json' if args.geometry_review else REPORT
    try:
        require(__debug__, 'Do not run this release gate with python -O; shared validators use assertions.')
        prepared, _, approved = source_contract()
        if args.geometry_review:
            review = read('assets/blender/room-v19-geometry-review.json')
            checked_file(review['path'], review['sha256'])
            require(review['geometryReviewOnly'] and review['notForRuntime'], 'Expected an explicitly labeled gray review GLB.')
            result = geometry_audit(review['path'], prepared, final=False)
            result.update(status='geometry_diagnostic_only', reviewPreparedSha256=review['preparedSha256'],
                          reviewMatchesCurrentSource=review['preparedSha256'] == PREPARED_SHA,
                          limitation='Only V18 retained-node and floor-removal geometry is established. This older gray fixture is not the current runtime export.')
            code = 2
        else:
            pending = pending_inputs()
            if pending:
                result = dict(complete=False, status='pending', preparedSha256=PREPARED_SHA, editableSha256=EDITABLE_SHA,
                              sourcePreparationVerified=True, approvedAboutFilesUnchanged=len(approved['files']),
                              missingOrStaleInputs=pending, browserVerified=False,
                              message='No release success is recorded until every current-source output passes. Review-history outputs are excluded.')
                code = 2
            else:
                result, code = verify(prepared, approved), 0
    except (AssertionError, ValueError, KeyError, OSError, subprocess.CalledProcessError, IndexError) as error:
        result = dict(complete=False, status='failed', preparedSha256=PREPARED_SHA, errorType=type(error).__name__,
                      error=str(error), browserVerified=False)
        code = 1
    worker.write(destination, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
