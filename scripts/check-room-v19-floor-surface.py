#!/usr/bin/env python3
"""CPU pixel evidence for the Room19 floor, independent of unfinished lighting.

Use bundled Python (NumPy/Pillow). Reads only existing GLB, PNG and provenance
files; writes one numeric report. It neither reads GPU pixels nor opens Blender.
Selection uses geometry alone, never image brightness or expected material values.
"""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'assets/blender/room-v19-floor-surface-validation.json'
SEED = 19
DRAW_COUNT = 40000
UV_MARGIN_TEXELS = 2.0
QUANTIZATION_TOLERANCE = .5 / 255 + 1e-6
spec = importlib.util.spec_from_file_location('room19_cpu_gate', ROOT / 'scripts/verify-room-v19.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
require, sha, read = gate.require, gate.sha, gate.read


def transforms(doc):
    """Resolve glTF TRS/column-major matrices to world coordinates (Y up)."""
    parents = {child: index for index, node in enumerate(doc['nodes']) for child in node.get('children', [])}
    cache = {}

    def world(index):
        if index in cache:
            return cache[index]
        node = doc['nodes'][index]
        if 'matrix' in node:
            local = np.asarray(node['matrix'], dtype=np.float64).reshape(4, 4).T
        else:
            x, y, z, w = node.get('rotation', [0, 0, 0, 1])
            rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                                 [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                                 [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
            local = np.eye(4)
            local[:3, :3] = rotation @ np.diag(node.get('scale', [1, 1, 1]))
            local[:3, 3] = node.get('translation', [0, 0, 0])
        cache[index] = world(parents[index]) @ local if index in parents else local
        return cache[index]

    return [world(i) for i in range(len(doc['nodes']))]


def validate_inputs():
    prepared = read('assets/blender/photoreal-materials-v19-prepared.json')
    baseline = read('assets/blender/photoreal-materials-v18-prepared.json')
    require(prepared['complete'] and prepared['sha256'] == gate.PREPARED_SHA and
            baseline['sha256'] == prepared['sourceSha256'], 'Wrong prepared source lineage.')
    gate.checked_file(prepared['derivative'], gate.PREPARED_SHA)
    gate.checked_file(baseline['derivative'], baseline['sha256'])
    require(prepared['changedExistingExportObjects'] == [gate.FLOOR] and
            prepared['allOtherExistingExportGeometryUnchanged'], 'Unexpected V19 geometry edits.')
    filename = ROOT / 'public/models/orbital-atelier-v18.glb'
    export = read('assets/blender/dual-lighting-v18-export-report.json')
    gate.checked_file(filename, export['sha256'])
    require(export['preparedSha256'] == baseline['sha256'], 'V18 GLB does not bind the baseline prepared source.')
    return prepared, baseline, filename


def image_inputs(slot, prepared, baseline):
    arrays, evidence = {}, []
    for version, source in (('v18', baseline), ('v19', prepared)):
        manifest_path = ROOT / f'public/textures/lighting-{version}/surface-{slot}-manifest.json'
        manifest = read(manifest_path)
        require(manifest['complete'] and manifest['sourceSha256'] == source['sha256'] and
                manifest['geometryUvNormalsUnchanged'] and manifest['decodedNormalsRenormalizedBeforeQuantization'],
                f'Surface {version}-{slot} is incomplete or bound to a different source.')
        if version == 'v19':
            require(not manifest.get('inheritedFrom'), 'The refined floor surface must be a fresh V19 bake.')
        for kind in ('normal', 'specular'):
            record = manifest[kind]
            filename = gate.checked_file(record['path'], record['sha256'])
            require(filename.resolve() == (ROOT / f'public/textures/lighting-{version}/{kind}-{slot}.png').resolve(),
                    'Surface manifest points outside the intended revision output.')
            with Image.open(filename) as image:
                require(image.mode == 'RGBA' and list(image.size) == record['dimensions'], 'Unexpected surface image format.')
                arrays[version, kind] = np.asarray(image, dtype=np.uint8).copy()
            require(record['encoding'] == 'RGBA8 linear numeric data' and
                    record['valuesOutsideRangeBeyondFloatToleranceFraction'] == 0, 'Not linear numeric surface data.')
            evidence.append(dict(version=version, kind=kind, path=str(filename.relative_to(ROOT)), sha256=record['sha256'],
                                 dimensions=record['dimensions'], manifest=str(manifest_path.relative_to(ROOT)),
                                 manifestSha256=sha(manifest_path), preparedSha256=source['sha256']))
    require(len({array.shape for array in arrays.values()}) == 1, 'Before/after surface image dimensions differ.')
    return arrays, evidence


def percentile(values):
    return dict(zip(('p1', 'p5', 'p50', 'p95', 'p99'), np.percentile(values, [1, 5, 50, 95, 99], axis=0).tolist()))


def sample_triangles(corners, uv_corners, areas, usable, size, rng):
    chosen = rng.choice(np.flatnonzero(usable), DRAW_COUNT, p=areas[usable] / areas[usable].sum())
    root = np.sqrt(rng.random(DRAW_COUNT))
    split = rng.random(DRAW_COUNT)
    barycentric = np.stack((1-root, root*(1-split), root*split), axis=1)
    world = np.sum(corners[chosen] * barycentric[:, :, None], axis=1)
    uv = np.sum(uv_corners[chosen] * barycentric[:, :, None], axis=1)
    inside = (np.abs(world[:, 0]) < 4.6) & (np.abs(world[:, 2]) < 3.1)
    # Geometry-based margins prevent atlas dilation/neighbor pixels from becoming
    # part of the measurement. No pixels are excluded for F0/roughness values.
    texel_triangles = uv_corners[chosen] * np.asarray(size)
    texel_points = uv * np.asarray(size)
    distances = []
    for corner in range(3):
        start = texel_triangles[:, corner]
        edge = texel_triangles[:, (corner+1) % 3] - start
        delta = texel_points - start
        distances.append(np.abs(edge[:, 0]*delta[:, 1] - edge[:, 1]*delta[:, 0]) /
                         np.maximum(np.linalg.norm(edge, axis=1), 1e-12))
    margin = np.min(distances, axis=0) > UV_MARGIN_TEXELS
    valid_uv = np.all((uv >= 0) & (uv < 1), axis=1)
    require(valid_uv[inside].all(), 'Interior floor uses UVs outside the atlas.')
    selected = inside & margin & valid_uv
    require(int(selected.sum()) >= 10000, 'Insufficient interior UV samples.')
    return uv[selected], dict(draws=DRAW_COUNT, interiorSamples=int(inside.sum()),
                             samples=int(selected.sum()), rejectedUvEdgeSamples=int((inside & ~margin).sum()),
                             uvEdgeMarginTexels=UV_MARGIN_TEXELS,
                             sampledTriangleIndices=np.unique(chosen[selected]).tolist())


def statistics(pixels):
    specular = pixels['specular'].astype(np.float64) / 255
    normal = pixels['normal'].astype(np.float64) / 255
    decoded = normal[:, :3] * 2 - 1
    length = np.linalg.norm(decoded, axis=1)
    unit = decoded / np.maximum(length[:, None], 1e-12)
    tilt = np.degrees(np.arccos(np.clip(unit[:, 2], -1, 1)))
    require(np.all(pixels['normal'][:, 3] == 255) and np.all((length > .99) & (length < 1.01)),
            'Normal pixels are not valid quantized unit tangent normals.')
    return dict(medianF0=np.median(specular[:, :3], axis=0).tolist(), f0Percentiles=percentile(specular[:, :3]),
                medianRoughness=float(np.median(specular[:, 3])), roughnessPercentiles=percentile(specular[:, 3]),
                roughnessMinMax=[float(specular[:, 3].min()), float(specular[:, 3].max())],
                zeroF0SampleFraction=float(np.mean(np.all(specular[:, :3] == 0, axis=1))),
                decodedNormalLengthPercentiles=percentile(length), tangentNormalTiltDegrees=percentile(tilt))


def measure():
    prepared, baseline, geometry_path = validate_inputs()
    doc, binary = gate.read_glb(geometry_path)
    matrices = transforms(doc)
    rng = np.random.default_rng(SEED)
    rows, exclusions, failures = [], [], []
    for node_index, node in enumerate(doc['nodes']):
        extra = node.get('extras', {})
        if extra.get('owner_asset_id') != 'architecture.platform' or extra.get('web_kind') != 'baked':
            continue
        name, slot = node['name'], extra['bake_atlas']
        require(prepared['existingGeometryBefore'][name] == prepared['existingGeometryAfter'][name],
                f'Platform geometry, UVs, normals or ownership changed: {name}')
        matrix = matrices[node_index]
        for primitive in gate.primitives(doc, name):
            position = gate.accessor(doc, binary, primitive['attributes']['POSITION']).astype(np.float64)
            normal = gate.accessor(doc, binary, primitive['attributes']['NORMAL']).astype(np.float64)
            uv = gate.accessor(doc, binary, primitive['attributes']['TEXCOORD_0']).astype(np.float64)
            indices = gate.accessor(doc, binary, primitive['indices']).reshape(-1, 3)
            position = position @ matrix[:3, :3].T + matrix[:3, 3]
            normal = normal @ np.linalg.inv(matrix[:3, :3])
            normal /= np.linalg.norm(normal, axis=1)[:, None]
            corners = position[indices]
            face_cross = np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0])
            doubled_areas = np.linalg.norm(face_cross, axis=1)
            areas = doubled_areas / 2
            horizontal = np.abs(face_cross[:, 1]) / np.maximum(doubled_areas, 1e-12) > .99
            upward = np.all(normal[indices][:, :, 1] > .99, axis=1)
            top = np.all((corners[:, :, 1] > .175) & (corners[:, :, 1] < .185), axis=1)
            usable = upward & horizontal & top & (areas > 1e-6)
            if not usable.any():
                exclusions.append(dict(node=name, slot=slot, reason='No upward horizontal triangles on the floor top plane.'))
                continue
            uv_corners = uv[indices]
            uv_a = uv_corners[:, 1] - uv_corners[:, 0]
            uv_b = uv_corners[:, 2] - uv_corners[:, 0]
            require(np.all(np.abs(uv_a[usable, 0]*uv_b[usable, 1]-uv_a[usable, 1]*uv_b[usable, 0]) > 1e-12),
                    'A candidate floor triangle has degenerate UVs.')
            arrays, evidence = image_inputs(slot, prepared, baseline)
            shape = arrays['v19', 'specular'].shape
            points, sampling = sample_triangles(corners, uv_corners, areas, usable, (shape[1], shape[0]), rng)
            x = (points[:, 0] * shape[1]).astype(np.int64)
            y = (points[:, 1] * shape[0]).astype(np.int64)
            pixels = {version: {kind: arrays[version, kind][y, x] for kind in ('specular', 'normal')}
                      for version in ('v18', 'v19')}
            states = {version: statistics(value) for version, value in pixels.items()}
            before = pixels['v18']['specular'].astype(np.float64) / 255
            after = pixels['v19']['specular'].astype(np.float64) / 255
            recipe = next(row for row in prepared['floorMaterials'] if row['name'].startswith(f'WEB8_BAKE_A{slot}_'))
            expected_f0 = recipe['expectedDielectricF0']
            expected_roughness = recipe['roughness']
            matches_f0 = np.all(np.abs(after[:, :3] - expected_f0) <= QUANTIZATION_TOLERANCE, axis=1)
            roughness_valid = (after[:, 3] >= expected_roughness[0]-QUANTIZATION_TOLERANCE) & (after[:, 3] <= expected_roughness[1]+QUANTIZATION_TOLERANCE)
            f0_lower = np.all(after[:, :3] < before[:, :3], axis=1)
            roughness_higher = after[:, 3] > before[:, 3]
            ratio = np.median(after[:, :3], axis=0) / np.median(before[:, :3], axis=0)
            roughness_gain = float(np.median(after[:, 3] - before[:, 3]))
            checks = dict(f0MatchesExpectedWithinHalfByte=bool(np.mean(matches_f0) >= .99),
                          roughnessWithinAuthoredRange=bool(np.mean(roughness_valid) >= .99),
                          f0LowerOnAtLeast99PercentOfSamples=bool(np.mean(f0_lower) >= .99),
                          medianF0AtMost60PercentOfV18=bool(np.all(ratio <= .60)),
                          roughnessHigherOnAtLeast95PercentOfSamples=bool(np.mean(roughness_higher) >= .95),
                          medianPairedRoughnessGainAtLeastPoint10=roughness_gain >= .10,
                          noBlankSurfaceTexels=states['v18']['zeroF0SampleFraction'] == states['v19']['zeroF0SampleFraction'] == 0,
                          baselineF0MatchesPoint04=bool(np.mean(np.all(np.abs(before[:, :3] - .04) <= QUANTIZATION_TOLERANCE, axis=1)) >= .99))
            failures += [f'{name}: {key}' for key, passed in checks.items() if not passed]
            rows.append(dict(node=name, slot=slot, candidateTopTriangleCount=int(usable.sum()), candidateTopTriangleAreaM2=float(areas[usable].sum()),
                             sampling={**sampling, 'uniqueTexels':int(len(np.unique(np.stack((x, y), axis=1), axis=0)))}, states=states,
                             expectedF0=expected_f0, expectedQuantizedF0=round(expected_f0*255)/255,
                             expectedRoughnessRange=expected_roughness, quantizationTolerance=QUANTIZATION_TOLERANCE,
                             fractionMatchingExpectedF0=float(np.mean(matches_f0)), fractionWithinRoughnessRange=float(np.mean(roughness_valid)),
                             fractionWithLowerF0=float(np.mean(f0_lower)), medianF0RatioV19ToV18=ratio.tolist(),
                             fractionWithHigherRoughness=float(np.mean(roughness_higher)), medianPairedRoughnessGain=roughness_gain,
                             normalPixelChangedFraction=float(np.mean(np.any(pixels['v19']['normal'][:, :3] != pixels['v18']['normal'][:, :3], axis=1))),
                             normalComponentAbsoluteChangeMean=float(np.mean(np.abs(pixels['v19']['normal'][:, :3].astype(float)-pixels['v18']['normal'][:, :3].astype(float)))/255),
                             checks=checks, sourceFiles=evidence))
    require(rows and sum(row['sampling']['samples'] for row in rows) >= 10000, 'No usable floor pixel footprint.')
    validate_inputs()  # Reject a concurrent source rewrite after the measurement.
    for row in rows:
        for record in row['sourceFiles']:
            gate.checked_file(record['path'], record['sha256'])
            gate.checked_file(record['manifest'], record['manifestSha256'])
    return dict(complete=not failures, status='floor_surface_pixels_passed' if not failures else 'floor_surface_pixels_failed',
                preparedSha256=prepared['sha256'], baselinePreparedSha256=baseline['sha256'],
                verifier='scripts/check-room-v19-floor-surface.py', verifierSha256=sha(Path(__file__)),
                geometrySource=str(geometry_path.relative_to(ROOT)), geometrySha256=sha(geometry_path),
                platformGeometryProof='Current pinned-source preparation records exactly equal before/after geometry/UV/normal/ownership signatures.',
                sourcePreparationManifest='assets/blender/photoreal-materials-v19-prepared.json',
                sourcePreparationManifestSha256=sha(ROOT/'assets/blender/photoreal-materials-v19-prepared.json'),
                selection='architecture.platform owner only; world-space upward normals and horizontal triangles; all corners at Y 0.175..0.185m; samples inside X +/-4.6m and Z +/-3.1m.',
                sampling='Seeded uniform barycentric draws, triangle probability proportional to world-space area; identical UV sample positions for both revisions; 2-texel UV triangle-edge exclusion.',
                imageCoordinates='glTF UV0 already includes the export V flip; PNG top-down sampling y=floor(UV.y*height), matching flipY=false.',
                selectionIndependentOfPixelValues=True, seed=SEED, rows=rows, excludedPlatformParts=exclusions, failedChecks=failures,
                dayNightBakeAssetsRequired=False, lightingPixelsSampled=False, gpuPixelsRead=False, aboutAssetsModified=False, aboutBaselineRehashed=False,
                provenance='Read-only CPU inspection of MCP-produced source-bound PNG bakes and unchanged exported platform geometry; only this report is written.',
                limitations='Verifies uncompressed linear source-bake material pixels. It does not establish final KTX/GPU decoding, visible daylight whitening, wall-wash appearance, or browser visual approval.')


if __name__ == '__main__':
    try:
        result = measure()
    except (ValueError, AssertionError, KeyError, OSError, IndexError) as error:
        result = dict(complete=False, status='floor_surface_pixels_failed', preparedSha256=gate.PREPARED_SHA,
                      errorType=type(error).__name__, error=str(error), dayNightBakeAssetsRequired=False, lightingPixelsSampled=False, gpuPixelsRead=False,
                      aboutAssetsModified=False)
    gate.worker.write(REPORT, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result['complete'] else 1)
