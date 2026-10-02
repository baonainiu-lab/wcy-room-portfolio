#!/usr/bin/env python3
"""CPU release gate: source provenance, inherited data proof, radiance and GLB."""
import importlib.util
from collections import Counter
import json
import math
import numpy as np
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

worker = module('room_v18_compression_check', ROOT / 'scripts/compress-room-v18.py')
geometry = module('room_v18_geometry_check', ROOT / 'scripts/verify-room-v16.py')
sha = worker.sha

def read(path):
    return json.loads((ROOT / path).read_text())

def verify():
    prepared = read('assets/blender/photoreal-materials-v18-prepared.json')
    source = read('assets/blender/photoreal-materials-v18-source.json')
    for report in (prepared, source):
        assert report['complete'] and report['revision'] == 18
        assert report['geometryBefore'] == report['geometryAfter'] and report['bakeUvsNormalsUnchanged']
        assert sha(ROOT / report['source']) == report['sourceSha256']
        assert sha(ROOT / report['derivative']) == report['sha256']
        assert report['affectedSurfaceSlots'] == [0, 8]
    current_sha = prepared['sha256']
    predecessor = read('assets/blender/photoreal-materials-v17-prepared.json')
    assert predecessor['sha256'] == prepared['sourceSha256']
    previous_materials = {m['name']: m for m in predecessor['materials']}
    assert len(previous_materials) == 117 and sum(predecessor['coverage'].values()) == 117
    replacements = {m['name']: m for m in prepared['materials']}
    assert set(replacements) <= previous_materials.keys()
    final_roles = Counter('warm_wood_' + replacements[name]['mode'] if name in replacements else material['role']
                          for name, material in previous_materials.items())
    assert sum(final_roles.values()) == 117
    material_coverage = dict(baselineRevision=17, baselineCount=len(previous_materials),
                            baselineRoleCounts=predecessor['coverage'], warmReplacements=prepared['materials'],
                            unchangedMaterialNames=sorted(previous_materials.keys() - replacements.keys()),
                            finalMaterialCount=len(previous_materials), finalRoleCounts=dict(final_roles))
    approved = read('docs/validation/about-approved-material-baseline.json')
    for filename, digest in approved['files'].items():
        assert sha(ROOT / filename) == digest, 'Approved About asset changed: ' + filename
    reuse = worker.reuse_proof(current_sha)
    assert reuse and reuse['slots'] == sorted(worker.REUSED_SLOTS)
    inheritance = read('assets/blender/room-v18-surface-inheritance.json')
    assert inheritance['complete'] and inheritance['sourceSha256'] == current_sha
    assert inheritance['oldSourceSha256'] == prepared['sourceSha256']
    assert inheritance['inheritedSlots'] == sorted(worker.REUSED_SLOTS) and inheritance['rebakedSurfaceSlots'] == [0, 8]
    for record in inheritance['records']:
        assert sha(ROOT / record['manifest']) == record['manifestSha256']
    compression = read('assets/blender/photoreal-materials-v18-compression.json')
    assert compression['complete'] and compression['preparedSha256'] == current_sha
    assert compression['codecRevision'] == worker.CODEC_REVISION and compression['surfaceReuse'] == reuse
    records = {r['key']: r for r in compression['textures']}
    assert len(compression['textures']) == 54 and set(records) == worker.EXPECTED
    candidates = worker.candidates(current_sha, reuse)
    assert len(candidates) == 51
    for candidate in candidates:
        assert worker.cached(records[candidate['key']], candidate, current_sha), candidate['key']
    for row in records.values():
        assert row['preparedSha256'] == current_sha
        assert sha(ROOT / row['source']) == row['sourceSha256'] and sha(ROOT / row['path']) == row['sha256']
        assert (ROOT / row['path']).stat().st_size == row['bytes']
        if row['key'] in ('day-window', 'night-window', 'static-screen'):
            for field in ('path', 'source'):
                filename = Path(row[field]).name
                assert sha(ROOT / row[field]) == sha(ROOT / 'public/textures/lighting-v16' / filename)
            continue
        assert row['transferFunction'] == 'linear' and row['targetType'] == 'RGBA' and not row['premultipliedAlpha']
        assert row['mipLevels'] == int(math.floor(math.log2(max(row['dimensions'])))) + 1
        if row['state'] in ('day', 'night', 'intro'):
            assert row['kind'] == worker.LIGHT_KIND and row['sourceEncoding'] == 'RGBM32'
            assert row['encodedSource']['encoding'] == 'LogRGB32 k256 alpha1'
            with Image.open(ROOT / row['encodedSource']['path']) as image:
                assert image.mode == 'RGBA' and image.getextrema()[3] == (255, 255)
                assert list(image.size) == row['dimensions']
    light_manifests, recovered = [], []
    for state in ('day', 'night'):
        for slot in range(12):
            raw = read(f'public/textures/lighting-v18/{state}-{slot}-manifest.json')
            encoded = records[f'{state}-{slot}']
            assert raw['sourceSha256'] == current_sha and raw['samples'] == 96
            assert raw['encoding'] == 'RGBM32' and raw['glossyExcluded'] and raw['geometryUvNormalsUnchanged']
            assert not raw.get('inheritedFrom')
            scale, overflow = worker.light_parameters(raw)
            assert encoded['radianceScale'] == scale
            if overflow:
                assert state == 'night'
                # Shared codec validates bottom-up source-index mapping, exact
                # float restoration and recorded NPZ/source-manifest hashes.
                restored, actual_scale, detail = worker.linear.restored_radiance(
                    np.asarray(Image.open(ROOT / raw['path']), dtype=np.uint8),
                    ROOT / raw['path'], scale, overflow)
                assert actual_scale == scale
                assert detail['count'] == overflow['count']
                assert detail['sha256'] == overflow['sha256']
                assert detail['restoredMaximum'] == raw['sourceRadianceMaximum']
                assert encoded['radianceOverflow'] == detail
                assert encoded['sourceSceneRadiancePeak'] == float(restored.max())
                recovered.append(dict(slot=slot, scale=scale, peak=raw['sourceRadianceMaximum'], channels=overflow['count'], sidecarSha256=overflow['sha256']))
                del restored
            else:
                assert scale == 1
            light_manifests.append(raw)
    for slot in range(12):
        manifest = read(f'public/textures/lighting-v18/surface-{slot}-manifest.json')
        assert manifest['complete'] and manifest['sourceSha256'] == current_sha
        assert manifest['geometryUvNormalsUnchanged'] and manifest['decodedNormalsRenormalizedBeforeQuantization']
        for kind in ('normal', 'specular'):
            assert manifest[kind]['valuesOutsideRangeBeyondFloatToleranceFraction'] == 0
        if slot in (0, 8):
            assert not manifest.get('inheritedFrom'), 'Warm material surface data must be newly baked.'
    for slot in (0, 1, 8):
        manifest = read(f'public/textures/intro-clean-v18/day-{slot}-manifest.json')
        assert manifest['sourceSha256'] == current_sha and manifest['samples'] == 96
        assert manifest['cleanIntro'] and manifest['receiverOnly'] and manifest['glossyExcluded']
        assert manifest['geometryUvNormalsUnchanged'] and not manifest.get('inheritedFrom')
        assert worker.light_parameters(manifest) == (1, None)
    probes = worker.probe_records(current_sha)
    assert probes and probes == compression['reflectionProbes']
    model = compression['model']
    raw_path = ROOT / 'public/models/orbital-atelier-v18.glb'
    assert sha(raw_path) == model['sourceSha256'] and sha(ROOT / model['path']) == model['sha256']
    baseline, baseline_bin = geometry.read(ROOT / 'public/models/orbital-atelier-v16.glb')
    raw, raw_bin = geometry.read(raw_path)
    packed, packed_bin = geometry.read(ROOT / model['path'])
    assert geometry.geometry(baseline, baseline_bin) == geometry.geometry(raw, raw_bin) == geometry.geometry(packed, packed_bin)
    assert geometry.hierarchy(baseline) == geometry.hierarchy(raw) == geometry.hierarchy(packed)
    export = read('assets/blender/dual-lighting-v18-export-report.json')
    assert export['complete'] and export['preparedSha256'] == current_sha and export['sha256'] == model['sourceSha256']
    baseline_export = read('assets/blender/dual-lighting-v16-export-report.json')
    assert sorted(export['componentIds']) == sorted(baseline_export['componentIds'])
    scales = {str(r['slot']): r['radianceScale'] for r in records.values() if r['state'] == 'night' and r.get('radianceScale', 1) != 1}
    assert scales == compression['nightRadianceScale'] == export['nightRadianceScale']
    for material in raw['materials']:
        if material['name'].startswith('WEB8_LIGHTMAP_'):
            slot = material['name'].rsplit('_', 1)[1]
            extras = material['extras']
            assert extras['diffuseEncoding'] == 'LogRGB32 gain256' and extras['nightRadianceScale'] == scales.get(slot, 1)
            assert not extras['glossyBaked']
    legacy_records = 0
    for version in ('v16', 'v17'):
        old = read(f'assets/blender/photoreal-materials-{version}-compression.json')
        if old.get('model'):
            assert sha(ROOT / old['model']['path']) == old['model']['sha256']
            assert sha(ROOT / f'public/models/orbital-atelier-{version}.glb') == old['model']['sourceSha256']
        for row in old['textures']:
            assert sha(ROOT / row['source']) == row['sourceSha256'] and sha(ROOT / row['path']) == row['sha256']
            legacy_records += 1
    result = dict(complete=True, preparedSha256=current_sha, model=model,
                  sourceGeometryUvsNormalsUnchanged=True, geometryBuffersExactlyMatchV16=True,
                  idsHierarchyTransformsUnchanged=True, legacySourcesModelsTexturesUnchanged=True,
                  legacyTextureRecordsChecked=legacy_records, surfaceReuse=reuse,
                  surfaceInheritanceProofSha256=sha(ROOT/'assets/blender/room-v18-surface-inheritance.json'),
                  all54TextureHashesVerified=True, all27LightMapsFreshSourceBound=True,
                  allRecordedNightHdrOutliersRecovered=True, recoveredNightHighlights=recovered,
                  nightRadianceScale=scales, webLogRgb32Gain256=True, webLightAlphaConstantOne=True,
                  linearMipsAndDataAlphaVerified=True, probeOrientationMatches=True,
                  mainAtlasPairs=12, surfaceAtlasPairs=12, introAtlases=3,
                  triangles=export['triangles'], nodes=len(raw['nodes']), materials=len(raw['materials']),
                  assetIds=len(export['componentIds']), warmSourceMaterials=prepared['materials'], sourceMaterialCoverage=material_coverage,
                  approvedAboutFilesUnchanged=len(approved['files']),
                  lightingBakeSeconds=round(sum(r['seconds'] for r in light_manifests), 2),
                  glass=export['glass'], browserVerified=False,
                  provenance='Source changes, actual bakes and raw export through Blender MCP; compression and this verification CPU-only.')
    worker.write(ROOT / 'assets/blender/photoreal-materials-v18-validation.json', result)
    return result

if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
