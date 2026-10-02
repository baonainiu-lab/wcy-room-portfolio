#!/usr/bin/env python3
"""CPU-only V20 gate: white marble walls, frozen V19 geometry/floor/fixture.

No Blender invocation, baking, compression, runtime edits, or browser claims.
Use bundled Python with NumPy/Pillow. Exit 0 is a full CPU release pass, 2 is
pending/source diagnostic only, and 1 is a failed integrity check.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BLENDER = ROOT/'assets/blender'
REPORT = BLENDER/'photoreal-materials-v20-validation.json'
BASELINE = BLENDER/'room-v20-frozen-baseline.json'
BASELINE_SHA = 'b002c19bd783f3087355b2070bc9d0ef5d4c4243f961fa8ddb91ebd949b10069'
SUPPLEMENT = BLENDER/'room-v20-frozen-baseline-supplement.json'
SUPPLEMENT_SHA = '6ff447f8e994edbbf4582f20831e03b49d14995b250cad2afacb1a0c3bf65c91'
PREPARED_SHA = None  # Resolved from the finalized, byte-verified V20 report.
EDITABLE_SHA = None
REUSED = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]
FRESH = [0, 8]
LIGHT_SIZES = [4096]*6+[3072, 2048, 3072, 4096, 4096, 3072, 1024]
DATA_SIZES = [2048, 2048, 2048, 2048, 2048, 1024, 1024, 2048, 2048, 2048, 2048, 2048, 1024]
EXPECTED_KEYS = {f'{state}-{slot}' for state in ('day', 'night', 'normal', 'specular') for slot in range(13)} | \
                {f'intro-{slot}' for slot in (0, 1, 8)} | {'day-window', 'night-window', 'static-screen'}
MARBLE_ROOT = Path('assets/textures/room-marble-v20')
# The official, selected CC0 source archives are immutable inputs, separate
# from the still-evolving authored .blend revision and its runtime outputs.
MARBLE_PACKAGES = {
    'Marble005': dict(bytes=192443533, sha256='142239c6b7cbe338a32379b9dbfa28fd02ea1ac2bb7a40f7c6e2e651c96387b1'),
    'Marble002': dict(bytes=186677681, sha256='df234bc3163c13e83937aa71d5c6c210e19b7e79a186c04c7206ea67ade5bd4f'),
}
MARBLE_ROLES = {'wall': 'Marble005', 'cap': 'Marble002'}
MARBLE_MAPS = {'color': 'Color', 'roughness': 'Roughness', 'normal': 'NormalGL', 'height': 'Displacement'}
EDITABLE_WALL_BINDINGS = {}
for _prefix, _material_prefix in (('', ''), ('DAY_V8__', 'DAY_V8__'), ('NIGHT_V8__', 'NIGHT_V8__'), ('V10__', '')):
    for _component in ('BackWall_Graphite', 'LeftFrontRail', 'LeftTopRail', 'LeftWallInner', 'SweepingTopBand'):
        _material = 'MAT_Graphite_Enamel' if _component in ('BackWall_Graphite', 'LeftWallInner') else 'MAT_Satin_Titanium'
        _variant = 'DAY_SUN_V9_DAY_V8__' if _prefix == 'DAY_V8__' and _component in ('BackWall_Graphite', 'SweepingTopBand') else _material_prefix
        EDITABLE_WALL_BINDINGS[_prefix+'A_'+_component] = _variant+_material
worker = None


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


geometry = module('v20_immutable_v19_geometry_helpers', 'scripts/verify-room-v19.py')
shared = geometry.shared
read_glb, accessor, nodes, hierarchy, primitives = (getattr(geometry, key) for key in ('read_glb', 'accessor', 'nodes', 'hierarchy', 'primitives'))
require = geometry.require


def sha(filename):
    digest = hashlib.sha256()
    with Path(filename).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(filename):
    return json.loads((ROOT/filename).read_text())


def write(filename, value):
    pending = Path(filename).with_suffix('.json.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    pending.replace(filename)


def checked_file(filename, digest):
    target = ROOT/filename
    require(target.is_file(), f'Missing file: {filename}')
    require(not any('review-history' in part or 'compression-history' in part for part in target.parts),
            f'Historical artifact cannot establish the current release: {filename}')
    require(sha(target) == digest, f'SHA256 mismatch: {filename}')
    return target


def capture_baseline():
    """One-time snapshot before V20; never silently rebase changed assets."""
    require(not BASELINE.exists(), 'The immutable V20 frozen baseline already exists; refusing to overwrite it.')
    selected = set()
    for folder in ('public/textures/lighting-v19', 'public/textures/intro-clean-v19',
                   'public/textures/works-gallery-v5', 'public/textures/gallery-atmosphere-v2',
                   'public/textures/gallery-atmosphere-v1', 'public/media/scene-backdrops-v1',
                   'public/textures/welcome-terminal-v3', 'public/media/brand', 'public/media/terminal-showcase-v1',
                   'assets/blender/linear-intermediates/lighting-v19', 'assets/blender/linear-intermediates/intro-clean-v19'):
        target = ROOT/folder
        if target.is_dir():
            selected.update(path for path in target.rglob('*') if path.is_file() and not path.name.endswith(('.log', '.tmp')))
    for pattern in ('assets/blender/*v19*.blend', 'assets/blender/*v19*.json', 'assets/blender/scripts/*v19*.py',
                    'scripts/*v19*.py', 'public/models/*v19*.glb', 'public/models/works-gallery-v5*.glb',
                    'public/models/welcome-terminal-v3*.glb', 'src/gallery*.js', 'src/gallery*.scss',
                    'src/works-gallery.js', 'src/about*.js',
                    'assets/blender/works-gallery-v5*.blend', 'assets/blender/works-gallery-v5/*.json'):
        selected.update(ROOT.glob(pattern))
    approved = read('docs/validation/about-approved-material-baseline.json')
    for filename, digest in approved['files'].items():
        selected.add(checked_file(filename, digest))
    # The root can add other explicitly frozen display assets before capture.
    extra = BLENDER/'room-v20-additional-frozen-files.json'
    if extra.exists():
        for filename in read(extra)['files']:
            require((ROOT/filename).is_file(), f'Missing additional frozen asset: {filename}')
            selected.add(ROOT/filename)
    files = {str(path.relative_to(ROOT)): sha(path) for path in sorted(selected)}
    require('public/models/orbital-atelier-v19.glb' in files and len(approved['files']) == 38,
            'Incomplete V19/About frozen baseline.')
    result = dict(complete=True, baselineRevision=19, purpose='Frozen source/runtime/evidence files for the V20 wall-only change.',
                  files=files, approvedAboutFiles=38, fileCount=len(files),
                  extraManifestSha256=sha(extra) if extra.exists() else None)
    write(BASELINE, result)
    return result


def frozen_contract():
    checked_file(BASELINE, BASELINE_SHA)
    checked_file(SUPPLEMENT, SUPPLEMENT_SHA)
    snapshot = read(BASELINE)
    supplement = read(SUPPLEMENT)
    require(snapshot['complete'] and snapshot['baselineRevision'] == 19 and snapshot['fileCount'] == len(snapshot['files']),
            'Invalid frozen baseline snapshot.')
    require(supplement['complete'] and supplement['baselineRevision'] == 19 and
            supplement['primaryBaselineSha256'] == BASELINE_SHA and supplement['fileCount'] == len(supplement['files']) and
            not (set(snapshot['files']) & set(supplement['files'])), 'Invalid frozen baseline supplement.')
    snapshot = dict(snapshot, files={**snapshot['files'], **supplement['files']},
                    fileCount=snapshot['fileCount']+supplement['fileCount'])
    for filename, digest in snapshot['files'].items():
        checked_file(filename, digest)
    return snapshot


def marble_inputs_contract():
    """Bind the eight used maps to the selected official immutable CC0 ZIPs."""
    catalog = read(MARBLE_ROOT/'ambientcg-catalog.json')
    official = {row['assetId']: row for row in catalog['foundAssets']}
    license_copy = (ROOT/MARBLE_ROOT/'ambientcg-license.html').read_text()
    require('Creative Commons CC0 1.0 Universal License' in license_copy and
            'downloadable asset files' in license_copy and 'material preview renders' in license_copy,
            'Missing official ambientCG license evidence for source assets and previews.')
    result = {}
    for asset, fixed in MARBLE_PACKAGES.items():
        metadata_path = MARBLE_ROOT/f'{asset}-SOURCE.json'
        metadata = read(metadata_path)
        download = metadata['download']
        filename = f'{asset}_4K-PNG.zip'
        url = f'https://ambientcg.com/get?file={filename}'
        require(metadata['assetId'] == asset and metadata['url'] == f'https://ambientcg.com/a/{asset}' and
                metadata['license'] == 'CC0-1.0' and metadata['licenseUrl'] == 'https://docs.ambientcg.com/license/' and
                metadata['creationMethod'] == official[asset]['creationMethod'] == 'PBRProcedural',
                f'Incorrect official material identity, creation method or license: {asset}')
        official_downloads = official[asset]['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']
        require(download in official_downloads and download['fullDownloadPath'] == download['downloadLink'] == url and
                download['fileName'] == filename and download['attribute'] == '4K-PNG' and
                download['size'] == fixed['bytes'] and metadata['zipSha256'] == fixed['sha256'],
                f'Material archive is not the selected official 4K PNG bundle: {asset}')
        archive = checked_file(MARBLE_ROOT/filename, fixed['sha256'])
        require(archive.stat().st_size == fixed['bytes'], f'Truncated material archive: {asset}')
        rows = {Path(row['path']).name: row for row in metadata['files']}
        require(len(rows) == len(metadata['files']) == 10, f'Material package inventory changed: {asset}')
        with zipfile.ZipFile(archive) as bundle:
            require(len(bundle.infolist()) == 10 and set(bundle.namelist()) == set(rows), 'Extracted package file inventory differs.')
            for basename, row in rows.items():
                expected = MARBLE_ROOT/f'{asset}_4K-PNG'/basename
                require((ROOT/row['path']).resolve() == (ROOT/expected).resolve(), 'Source map escaped its official package directory.')
                path = checked_file(row['path'], row['sha256'])
                require(path.stat().st_size == row['bytes'] == bundle.getinfo(basename).file_size, 'Extracted material file size differs.')
                digest = hashlib.sha256()
                with bundle.open(basename) as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b''):
                        digest.update(chunk)
                require(digest.hexdigest() == row['sha256'], f'Extracted map is not byte-identical to the official package: {basename}')
        used = {}
        for kind, suffix in MARBLE_MAPS.items():
            row = rows[f'{asset}_4K-PNG_{suffix}.png']
            with Image.open(ROOT/row['path']) as image:
                require(image.format == 'PNG' and image.size == (4096, 4096), f'Actual material source is not 4K PNG: {asset}/{kind}')
            used[kind] = row
        result[asset] = dict(metadata=metadata, metadataPath=str(metadata_path), metadataSha256=sha(ROOT/metadata_path), maps=used)
    return result


def source_contract():
    global PREPARED_SHA, EDITABLE_SHA
    prepared = read('assets/blender/photoreal-materials-v20-prepared.json')
    source = read('assets/blender/photoreal-materials-v20-source.json')
    for kind, record, predecessor in (
            ('prepared', prepared, read('assets/blender/photoreal-materials-v19-prepared.json')),
            ('source', source, read('assets/blender/photoreal-materials-v19-source.json'))):
        require(record['complete'] is True and record['revision'] == 20, f'V20 {kind} preparation is incomplete.')
        require(record['sourceSha256'] == predecessor['sha256'] and record['sha256'] != predecessor['sha256'],
                f'V20 {kind} is not derived from the frozen V19 source.')
        checked_file(record['source'], predecessor['sha256'])
        checked_file(record['derivative'], record['sha256'])
        expected_name = 'orbital-dual-bake-v20.blend' if kind == 'prepared' else 'orbital-atelier-v20.blend'
        require((ROOT/record['derivative']).resolve() == (BLENDER/expected_name).resolve(), 'Wrong V20 derivative path.')
        require(record['atlasCount'] == 13 and record['affectedSurfaceSlots'] == FRESH and record['unchangedSurfaceSlots'] == REUSED and
                record['legacyV19Preserved'] and record['aboutAssetsUnchanged'] and record['galleryAssetsUnchanged'] and
                record['rebakeDayNightSlots'] == list(range(13)) and record['introSlots'] == [0, 1, 8],
                'V20 material coverage or preservation contract changed.')
        require(isinstance(record['existingGeometryBefore'], dict) and record['existingGeometryBefore'] and
                record['existingGeometryBefore'] == record['existingGeometryAfter'],
                f'Wall material refinement changed {kind} geometry, UVs, normals, IDs or ownership.')
        for recipe in record['recipeFiles']:
            checked_file(recipe['path'], recipe['sha256'])
    require(prepared['expectedExportTriangles'] == 418383, 'V20 must retain the complete V19 geometry.')
    require(PREPARED_SHA in (None, prepared['sha256']) and EDITABLE_SHA in (None, source['sha256']),
            'Source changed during the verification run.')
    PREPARED_SHA, EDITABLE_SHA = prepared['sha256'], source['sha256']
    wall_scope_contract(prepared, source)
    approved = read('docs/validation/about-approved-material-baseline.json')
    require(len(approved['files']) == 38, 'Expected the approved About 38-file baseline.')
    for filename, digest in approved['files'].items():
        checked_file(filename, digest)
    return prepared, source, approved


def reuse_contract(prepared):
    before_path = 'assets/blender/room-v19-to-v20-surface-before.json'
    after_path = 'assets/blender/room-v20-surface-reuse-proof.json'
    before, after = read(before_path), read(after_path)
    require(before['sourceSha256'] == prepared['sourceSha256'] and after['sourceSha256'] == PREPARED_SHA,
            'Surface proof sources are stale.')
    checked_file(before['source'], before['sourceSha256'])
    checked_file(after['source'], after['sourceSha256'])
    old_rows, new_rows = ({r['slot']: r for r in value['surfaces']} for value in (before, after))
    require(len(before['surfaces']) == len(after['surfaces']) == 13 and set(old_rows) == set(new_rows) == set(range(13)),
            'Both V19 and V20 inspection proofs must cover all 13 atlas slots.')
    for slot in range(13):
        old, new = old_rows[slot], new_rows[slot]
        require(len(new['shaderGraphsSha256']) == len(new['geometryUvNormalsSignature']) == 64 and new['materials'], 'Incomplete surface proof.')
        require(old['geometryUvNormalsSignature'] == new['geometryUvNormalsSignature'], f'Geometry changed in slot {slot}.')
        if slot in REUSED:
            require(old == new, f'Surface inheritance is not proven for slot {slot}.')
        else:
            require(old['shaderGraphsSha256'] != new['shaderGraphsSha256'], f'Expected wall material change missing in slot {slot}.')
    return old_rows, new_rows


def surface_contract(prepared):
    _, new_rows = reuse_contract(prepared)
    reuse = worker.reuse_proof(PREPARED_SHA)
    require(reuse and reuse['slots'] == REUSED, 'Compressor reuse contract differs from independently checked slots.')
    inherited = read('assets/blender/room-v20-surface-inheritance.json')
    require(inherited['complete'] and inherited['sourceSha256'] == PREPARED_SHA and
            inherited['oldSourceSha256'] == prepared['sourceSha256'] and inherited['inheritedSlots'] == REUSED and
            inherited['rebakedSurfaceSlots'] == FRESH, 'Wrong V20 inheritance lineage/coverage.')
    rows = {r['slot']: r for r in inherited['records']}
    require(len(inherited['records']) == len(rows) == 11 and set(rows) == set(REUSED), 'Incomplete inherited surface records.')
    for slot in range(13):
        filename = f'public/textures/lighting-v20/surface-{slot}-manifest.json'
        manifest = read(filename)
        require(manifest['complete'] and manifest['sourceSha256'] == PREPARED_SHA and manifest['slot'] == slot and
                manifest['dataSize'] == DATA_SIZES[slot] and manifest['geometryUvNormalsUnchanged'] and
                manifest['decodedNormalsRenormalizedBeforeQuantization'], f'Invalid current surface slot {slot}.')
        if slot in FRESH:
            require(not manifest.get('inheritedFrom'), f'Wall surface slot {slot} must be freshly baked.')
        else:
            row = rows[slot]
            require(row['proof'] == new_rows[slot] and (ROOT/row['manifest']).resolve() == (ROOT/filename).resolve(), 'Wrong inherited proof/manifest.')
            checked_file(row['manifest'], row['manifestSha256'])
            provenance = manifest['inheritedFrom']
            require(provenance['sourceSha256'] == prepared['sourceSha256'], 'Inherited surface source mismatch.')
            old_path = f'public/textures/lighting-v19/surface-{slot}-manifest.json'
            require((ROOT/provenance['manifest']).resolve() == (ROOT/old_path).resolve(), 'Surface must inherit from current V19.')
            checked_file(provenance['manifest'], provenance['manifestSha256'])
            for key in ('equivalenceProof', 'sourceProof'):
                checked_file(provenance[key], provenance[key+'Sha256'])
            old = read(old_path)
            for kind in ('normal', 'specular'):
                require(manifest[kind]['sha256'] == old[kind]['sha256'] == row['maps'][kind]['sha256'], 'Inherited source pixels changed.')
        for kind in ('normal', 'specular'):
            data = manifest[kind]
            checked_file(data['path'], data['sha256'])
            require(data['dimensions'] == [DATA_SIZES[slot]]*2 and data['valuesOutsideRangeBeyondFloatToleranceFraction'] == 0,
                    f'Invalid numeric surface data: {kind}-{slot}')
    return reuse


def geometry_fingerprint(doc, binary, name):
    def fingerprint(index):
        values = accessor(doc, binary, index)
        return dict(dtype=values.dtype.str, shape=list(values.shape), sha256=hashlib.sha256(values.tobytes()).hexdigest())
    return [dict(mode=p.get('mode', 4), indices=fingerprint(p['indices']),
                 attributes={k: fingerprint(v) for k, v in sorted(p['attributes'].items())}) for p in primitives(doc, name)]


def scene_binding(doc):
    return dict(defaultScene=doc.get('scene', 0), roots=[sorted(doc['nodes'][i]['name'] for i in scene.get('nodes', []))
                                                      for scene in doc['scenes']])


def draw_binding(doc, name):
    node = nodes(doc)[name]
    omitted = {'name', 'mesh', 'children', 'extras', 'translation', 'rotation', 'scale', 'matrix'}
    other_node_fields = {key: value for key, value in node.items() if key not in omitted}
    rows = []
    for primitive in primitives(doc, name):
        rows.append(dict(material=doc['materials'][primitive['material']]['name'],
                         other={key: value for key, value in primitive.items() if key not in {'attributes', 'indices', 'material', 'mode'}}))
    mesh_weights = doc['meshes'][node['mesh']].get('weights') if 'mesh' in node else None
    return dict(nodeFields=other_node_fields, primitives=rows, meshWeights=mesh_weights)


def geometry_audit(filename, prepared):
    baseline_path = ROOT/'public/models/orbital-atelier-v19.glb'
    baseline_export = read('assets/blender/dual-lighting-v19-export-report.json')
    checked_file(baseline_path, baseline_export['sha256'])
    before, bb = read_glb(baseline_path)
    after, ab = read_glb(filename)
    require(hierarchy(before) == hierarchy(after), 'V20 changed V19 node names, hierarchy, IDs, transforms or ownership.')
    require(scene_binding(before) == scene_binding(after), 'V20 changed active scene root membership or the default scene.')
    require(len(before['meshes']) == len(after['meshes']) and
            before.get('skins', []) == after.get('skins', []) and before.get('animations', []) == after.get('animations', []),
            'V20 changed mesh inventory, skinning or animation structure.')
    for name in nodes(before):
        require(geometry_fingerprint(before, bb, name) == geometry_fingerprint(after, ab, name),
                f'V20 changed exact typed geometry/UV/normal/index buffers: {name}')
        require(draw_binding(before, name) == draw_binding(after, name), f'V20 changed primitive material/atlas binding or morph/skin structure: {name}')
    triangles = sum(len(accessor(after, ab, p['indices']))//3 for mesh in after['meshes'] for p in mesh['primitives'])
    ids = [n['extras']['asset_id'] for n in after['nodes'] if n.get('extras', {}).get('asset_id')]
    require(triangles == prepared['expectedExportTriangles'] == baseline_export['triangles'] == 418383 and
            len(after['nodes']) == 199 and len(ids) == len(set(ids)) == 96 and sorted(ids) == sorted(baseline_export['componentIds']),
            'V20 must retain 199 nodes, 96 independent asset IDs and 418383 triangles.')
    scene = after['scenes'][after.get('scene', 0)].get('extras', {})
    require(scene.get('source_revision') == scene.get('lighting_revision') == 20, 'Missing V20 runtime scene provenance.')
    require(all('REVIEW_ONLY' not in m.get('name', '') for m in after['materials']), 'A review GLB is not a release asset.')
    return dict(complete=True, preparedSha256=PREPARED_SHA, baseline=str(baseline_path.relative_to(ROOT)), baselineSha256=sha(baseline_path),
                path=str((ROOT/filename).relative_to(ROOT)), sha256=sha(ROOT/filename), triangles=triangles, nodes=199, assetIds=96,
                allV19TypedGeometryBuffersExactlyPreserved=True, allV19HierarchyIdsTransformsOwnershipExactlyPreserved=True,
                allV19SceneRootsAndPrimitiveMaterialBindingsExactlyPreserved=True,
                floorGeometryExactlyPreserved=True, ceilingFixtureGeometryExactlyPreserved=True,
                nodeIdentityPolicy='Stable node names; mesh datablock names may receive Blender numeric suffixes.')

def texture_contract(compression, reuse):
    require(compression['complete'] and compression['preparedSha256'] == PREPARED_SHA and
            compression['codecRevision'] == worker.CODEC_REVISION and compression['surfaceReuse'] == reuse,
            'Compression is not complete for the exact current source and reuse proof.')
    records = {row['key']: row for row in compression['textures']}
    require(len(compression['textures']) == len(records) == 58 and set(records) == worker.EXPECTED == EXPECTED_KEYS and
            compression['runtimeTextureCount'] == 58, 'Expected exactly 58 KTX2 textures.')
    candidates = worker.candidates(PREPARED_SHA, reuse)
    require(len(candidates) == 55 and len({row['key'] for row in candidates}) == 55, 'Expected 55 source-bound generated textures.')
    for candidate in candidates:
        require(worker.cached(records[candidate['key']], candidate, PREPARED_SHA), f'Outdated compression: {candidate["key"]}')
        row = records[candidate['key']]
        require((ROOT/row['source']).resolve() == candidate['source'].resolve() and
                (ROOT/row['path']).resolve() == candidate['source'].with_suffix('.ktx2').resolve(),
                f'Current revision compression record points outside V20: {candidate["key"]}')
        expected_size = LIGHT_SIZES[candidate['slot']] if candidate['state'] in ('day', 'night', 'intro') else DATA_SIZES[candidate['slot']]
        require(row['state'] == candidate['state'] and row['slot'] == candidate['slot'] and row['dimensions'] == [expected_size]*2,
                f'Compression state/slot/resolution contract changed: {candidate["key"]}')
        with Image.open(candidate['source']) as image:
            require(image.mode == 'RGBA' and list(image.size) == [expected_size]*2, f'Actual source PNG dimensions changed: {candidate["key"]}')
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


def inherited_ktx_contract(records):
    previous = read('assets/blender/photoreal-materials-v19-compression.json')
    old = {row['key']: row for row in previous['textures']}
    for slot in REUSED:
        for kind in ('normal', 'specular'):
            key = f'{kind}-{slot}'
            require(records[key]['sha256'] == old[key]['sha256'] and
                    records[key]['sourceSha256'] == old[key]['sourceSha256'], f'Inherited data/KTX bytes changed: {key}')
            for field in ('dimensions', 'mipLevels', 'mipMethod', 'mipStatistics', 'kind', 'codecRevision', 'transferFunction', 'targetType', 'premultipliedAlpha'):
                require(records[key][field] == old[key][field], f'Inherited codec evidence changed: {key}/{field}')
            inheritance = records[key]['inheritedEncoding']
            checked_file(inheritance['manifest'], inheritance['sha256'])
            checked_file(inheritance['sourceKtx'], inheritance['sourceKtxSha256'])
            require(inheritance['sourceKtxSha256'] == old[key]['sha256'] and
                    (ROOT/inheritance['manifest']).resolve() == (BLENDER/'photoreal-materials-v19-compression.json').resolve(),
                    f'Inherited KTX provenance is not the frozen V19 release: {key}')
    return len(REUSED)*2


def light_contract(records):
    recovered, manifests = [], []
    for state, slots, folder in [('day', range(13), 'lighting-v20'), ('night', range(13), 'lighting-v20'),
                                 ('intro', (0, 1, 8), 'intro-clean-v20')]:
        for slot in slots:
            prefix = 'day' if state == 'intro' else state
            raw = read(f'public/textures/{folder}/{prefix}-{slot}-manifest.json')
            require(raw['sourceSha256'] == PREPARED_SHA and raw['samples'] == 96 and raw['slot'] == slot and
                    raw['state'] == prefix and raw['dimensions'] == [LIGHT_SIZES[slot]] * 2 and
                    raw['encoding'] == 'RGBM32' and raw['glossyExcluded'] and raw['geometryUvNormalsUnchanged'] and
                    not raw.get('inheritedFrom'), f'Light map is not a fresh current-source 96-sample bake: {state}-{slot}')
            if state == 'intro':
                require(raw['cleanIntro'] is True and raw['receiverOnly'] is True, 'Intro map is not clean receiver-only.')
            else:
                require(raw.get('cleanIntro') is False and raw.get('receiverOnly') is False,
                        f'Main scene lightmap cannot use receiver-only intro lighting: {state}-{slot}')
            require(set(raw['passFilter']) == {'DIRECT', 'INDIRECT', 'COLOR', 'DIFFUSE', 'EMIT'} and len(raw['passFilter']) == 5,
                    'Lightmap must retain diffuse direct/indirect, color and emit passes without gloss.')
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
        with (ROOT/probe['path']).open('rb') as stream:
            header = stream.read(4096)
        dimensions = re.search(rb'^-Y (\d+) \+X (\d+)\s*$', header, re.MULTILINE)
        require(b'FORMAT=32-bit_rle_rgbe' in header and dimensions is not None and
                [int(dimensions.group(2)), int(dimensions.group(1))] == [2048, 1024], 'Actual HDR header resolution/orientation differs.')
        old_probe = read(f'public/textures/lighting-v19/reflection-{probe["state"]}.json')
        require(all(probe[key] == old_probe[key] for key in ('cameraLocation', 'cameraEuler')), 'Probe camera placement changed from V19.')
    return manifests, recovered, probes


def model_contract(compression, records, prepared):
    model = compression['model']
    raw_path = ROOT / 'public/models/orbital-atelier-v20.glb'
    checked_file(raw_path, model['sourceSha256'])
    packed_path = checked_file(model['path'], model['sha256'])
    require(packed_path.resolve() == (ROOT / 'public/models/orbital-atelier-v20-compressed.glb').resolve() and
            packed_path.stat().st_size == model['bytes'] and raw_path.stat().st_size == model['sourceBytes'], 'Wrong V20 model path/size.')
    export = read('assets/blender/dual-lighting-v20-export-report.json')
    require(export['complete'] and export['preparedSha256'] == PREPARED_SHA and export['sha256'] == sha(raw_path) and
            export['atlasSizes'] == LIGHT_SIZES and export['surfaceSizes'] == DATA_SIZES, 'Export provenance or atlas sizing mismatch.')
    require((ROOT / export['model']).resolve() == raw_path.resolve() and export['bytes'] == raw_path.stat().st_size and
            export['source'] == 'assets/blender/orbital-atelier-v20.blend', 'Wrong raw export source/path/size.')
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
    worker.write(BLENDER / 'room-v20-geometry-audit.json', audit)
    return export, audit, scales


def delivery_contract(prepared, source, export, manifests, scales):
    """Check the recorded production method without claiming CPU sees MCP calls."""
    delivery_path = 'assets/blender/room-v20-bake-delivery.json'
    method_path = 'assets/blender/room-v20-execution-method.json'
    delivery, method = read(delivery_path), read(method_path)
    require(delivery['complete'] is True and method['complete'] is True and method['revision'] == 20 and
            method['reviewRevision'] == prepared['reviewRevision'], 'Incomplete/stale V20 delivery evidence.')
    for kind, record in (('prepared', prepared), ('editable', source)):
        require(delivery[kind] == dict(path=record['derivative'], sha256=record['sha256']), 'Delivery source differs from the verified source.')
    require(delivery['rawModel'] == dict(path=export['model'], sha256=export['sha256'], bytes=export['bytes']) and
            delivery['nightRadianceScale'] == scales and delivery['surfaceFreshSlots'] == FRESH and
            delivery['surfaceInheritedSlots'] == REUSED and delivery['allLightingFreshlyBaked'] is True,
            'Delivery model/radiance/surface coverage differs from the verified assets.')
    require(delivery['counts'] == dict(dayLightmaps=13, nightLightmaps=13, surfacePairs=13, freshIntroMaps=3, hdrProbes=2,
                                       independentAssetIds=96, nodes=199, triangles=418383, drawPrimitives=103),
            'Delivery counts differ from actual asset coverage.')
    expected_lists = {
        'sourceReports': {f'assets/blender/photoreal-materials-v20-{kind}.json' for kind in ('prepared', 'source')},
        'inheritanceProofs': {'assets/blender/room-v19-to-v20-surface-before.json', 'assets/blender/room-v20-surface-reuse-proof.json',
                              'assets/blender/room-v20-surface-inheritance.json'},
        'licenseSources': {str(MARBLE_ROOT/f'{asset}-SOURCE.json') for asset in MARBLE_PACKAGES} | {str(MARBLE_ROOT/'LICENSE-SOURCE.md')},
    }
    for field, expected in expected_lists.items():
        records = delivery[field]
        require(len(records) == len(expected) and {r['path'] for r in records} == expected, f'Incomplete delivery evidence: {field}')
        for record in records:
            checked_file(record['path'], record['sha256'])
    groups = {
        'dayNight': {f'public/textures/lighting-v20/{state}-{slot}-manifest.json' for state in ('day', 'night') for slot in range(13)},
        'surface': {f'public/textures/lighting-v20/surface-{slot}-manifest.json' for slot in range(13)},
        'intro': {f'public/textures/intro-clean-v20/day-{slot}-manifest.json' for slot in (0, 1, 8)},
        'hdr': {f'public/textures/lighting-v20/reflection-{state}.json' for state in ('day', 'night')},
    }
    require(set(delivery['sourceBoundManifests']) == set(groups), 'Unexpected delivery manifest groups.')
    for group, expected in groups.items():
        records = delivery['sourceBoundManifests'][group]
        require(len(records) == len(expected) and {r['path'] for r in records} == expected, f'Delivery manifest coverage differs: {group}')
        for record in records:
            checked_file(record['path'], record['sha256'])
            require(read(record['path'])['sourceSha256'] == PREPARED_SHA, 'Delivery includes a stale source-bound manifest.')
    for field, expected in (('executionMethod', method_path), ('exportReport', 'assets/blender/dual-lighting-v20-export-report.json')):
        record = delivery[field]
        require(record['path'] == expected, 'Delivery points to the wrong current evidence.')
        checked_file(record['path'], record['sha256'])
    production = method['production']
    require(method['preparedSource'] == prepared['derivative'] and method['preparedSha256'] == PREPARED_SHA and
            method['authoring']['method'] == 'File-targeted Blender MCP with Python helper scripts' and
            production['method'] == 'File-targeted Blender MCP' and production['offlineCliFallbackUsed'] is False and
            production['receiverPartitioningUsed'] is False and production['rawModelExportedThroughMcp'] is True,
            'V20 execution record must accurately distinguish its complete MCP workflow from V19 fallback work.')
    require(production['freshSurfacePasses'] == 6 and production['freshSurfaceSlots'] == FRESH and
            production['provenInheritedSurfaceSlots'] == REUSED and
            production['dayRadianceSlots'] == production['nightRadianceSlots'] == list(range(13)) and
            production['introRadianceSlots'] == [0, 1, 8] and production['reflectionStates'] == ['day', 'night'] and
            production['bakeSamples'] == 96 and production['surfaceSamples'] == 8 and production['reflectionSamples'] == 64 and
            production['atlasDimensionsPreserved'] is True and production['qualityReduced'] is False and
            production['largestRecordedSingleRadianceBakeSeconds'] == max(row['seconds'] for row in manifests),
            'Recorded production quality or coverage differs from the source-bound outputs.')
    for slot in FRESH:
        require(read(f'public/textures/lighting-v20/surface-{slot}-manifest.json')['samples'] == 8, 'Fresh surface samples differ.')
    require(method['denoising']['algorithm'] == 'OPENIMAGEDENOISE' and method['denoising']['quality'] == 'HIGH' and
            method['denoising']['recipeFiles'] == prepared['recipeFiles'], 'Denoiser recipe evidence differs from the finalized source.')
    texture = method['textureCreation']
    require(texture['provider'] == 'ambientCG' and set(texture['assets']) == set(MARBLE_PACKAGES) and
            texture['creationMethod'] == 'PBRProcedural' and texture['license'] == 'CC0-1.0' and
            texture['notDescribedAsPhotogrammetry'] is True and texture['newPackedSourceImages'] == 8 and
            texture['oldPackedImagesUnchanged'] is True, 'Material creation method/license record is inaccurate.')
    return dict(complete=True, status='delivery_provenance_consistency_passed',
                recordedMethod='File-targeted Blender MCP with Python helper scripts', offlineCliFallbackUsed=False,
                sourceBoundManifestRecords=44, deliveryPath=delivery_path, deliverySha256=sha(ROOT/delivery_path),
                executionMethodPath=method_path, executionMethodSha256=sha(ROOT/method_path),
                limitation='CPU verifies evidence consistency and source hashes; the actual MCP invocations are recorded by the producing task.')


def pending_inputs(prepared_sha=None):
    requirements = [
        ('assets/blender/photoreal-materials-v20-prepared.json', 'sha256', True),
        ('assets/blender/photoreal-materials-v20-source.json', None, True),
        ('assets/blender/room-v19-to-v20-surface-before.json', None, False),
        ('assets/blender/room-v20-surface-reuse-proof.json', 'sourceSha256', False),
        ('assets/blender/room-v20-surface-inheritance.json', 'sourceSha256', True),
        ('assets/blender/photoreal-materials-v20-compression.json', 'preparedSha256', True),
        ('assets/blender/dual-lighting-v20-export-report.json', 'preparedSha256', True),
        ('assets/blender/room-v20-bake-delivery.json', None, True),
        ('assets/blender/room-v20-execution-method.json', 'preparedSha256', True),
    ]
    requirements += [(f'public/textures/lighting-v20/{state}-{slot}-manifest.json', 'sourceSha256', state == 'surface')
                     for state in ('day', 'night', 'surface') for slot in range(13)]
    requirements += [(f'public/textures/intro-clean-v20/day-{slot}-manifest.json', 'sourceSha256', False) for slot in (0, 1, 8)]
    requirements += [(f'public/textures/lighting-v20/reflection-{state}.json', 'sourceSha256', False) for state in ('day', 'night')]
    pending = []
    for filename, binding, complete in requirements:
        if not (ROOT/filename).is_file():
            pending.append(dict(path=filename, reason='missing'))
            continue
        record = read(filename)
        if prepared_sha and binding and record.get(binding) != prepared_sha:
            pending.append(dict(path=filename, reason='stale_source', recordedSha256=record.get(binding)))
        elif record.get('complete') is False or (complete and record.get('complete') is not True):
            pending.append(dict(path=filename, reason='incomplete'))
    for filename in ('public/models/orbital-atelier-v20.glb', 'public/models/orbital-atelier-v20-compressed.glb'):
        if not (ROOT/filename).is_file():
            pending.append(dict(path=filename, reason='missing'))
    return pending


def wall_scope_contract(prepared, source):
    """Validate the MCP-authored full graph/geometry/light preservation schema."""
    external = marble_inputs_contract()
    for kind, report in (('prepared', prepared), ('source', source)):
        require(report['reviewRevision'] >= 4, 'Rejected procedural review revisions cannot establish the current marble release.')
        old_graphs, new_graphs = report['originalMaterialGraphsBefore'], report['originalMaterialGraphsAfter']
        require(old_graphs and old_graphs == new_graphs and all(len(digest) == 64 for digest in old_graphs.values()),
                f'An original V19 material graph changed in {kind}.')
        require(report['wholeFileMeshSignatureBefore'] == report['wholeFileMeshSignatureAfter'] and
                len(report['wholeFileMeshSignatureBefore']) == 64 and report['geometryUvsNormalsMaterialIndicesUnchanged'] is True,
                f'Whole-file geometry or material indices changed in {kind}.')
        require(report['authoredLightsBefore'] == report['authoredLightsAfter'] and len(report['authoredLightsBefore']) == 64,
                f'Authored light transform, energy, color, shape or size changed in {kind}.')
        predecessor = read(f'assets/blender/photoreal-materials-v19-{kind}.json')
        expected_floors = {row['name'] for row in predecessor['floorMaterials']}
        floor_proof, lamp_proof = report['protectedFloorMaterials'], report['protectedLampMaterials']
        require(expected_floors and expected_floors <= set(floor_proof['before']) and
                floor_proof['before'] == floor_proof['after'], f'Floor-specific graph proof incomplete/changed in {kind}.')
        expected_lamp = {'V19_Ceiling_Anodized_Graphite', 'V19_Ceiling_Brushed_Champagne', 'V19_Ceiling_Opal_Diffuser'}
        require(expected_lamp <= set(lamp_proof['before']) and lamp_proof['before'] == lamp_proof['after'],
                f'Fixture-specific graph proof incomplete/changed in {kind}.')
        for proof in (floor_proof, lamp_proof):
            require(all(name in old_graphs and digest == old_graphs[name] for name, digest in proof['before'].items()),
                    'Protected graph hashes do not match the full original material inventory.')
        walls = {row['name']: row for row in report['wallMaterials']}
        require(len(walls) == len(report['wallMaterials']) == (3 if kind == 'prepared' else 8) and
                set(walls) == set(report['newWallMaterialGraphs']) and all(len(value) == 64 for value in report['newWallMaterialGraphs'].values()),
                'Unexpected new wall material inventory.')
        for material in walls.values():
            role = material['role']
            require(role in MARBLE_ROLES and material['assetId'] == MARBLE_ROLES[role] and
                    material['geometryDisplacement'] is False, 'White wall/black cap material identity or geometry displacement changed.')
            asset = material['assetId']
            evidence = external[asset]
            require(material['provider'] == 'ambientCG' and material['license'] == 'CC0-1.0' and
                    material['sourceUrl'] in (f'https://ambientcg.com/a/{asset}', f'https://ambientcg.com/view?id={asset}') and
                    material['creationMethod'].startswith('PBRProcedural') and
                    material['licenseSource'] == str(MARBLE_ROOT/'LICENSE-SOURCE.md'), 'Incorrect authored material source attribution.')
            require(material['sourceMetadata'] == dict(path=evidence['metadataPath'], sha256=evidence['metadataSha256']),
                    'Authored material does not bind the current verified official package evidence.')
            require(material['textureImagesPacked'] is True and set(material['maps']) == set(MARBLE_MAPS),
                    'Every selected color/roughness/NormalGL/height map must be evidenced and packed.')
            for map_kind, data in material['maps'].items():
                original = evidence['maps'][map_kind]
                require(data['path'] == original['path'] and data['sha256'] == data['packedSha256'] == original['sha256'] and
                        data['dimensions'] == [4096, 4096] and
                        len(data['usedByTextureNodes']) == len(set(data['usedByTextureNodes'])) == 3 and
                        data['colorSpace'] == ('sRGB' if map_kind == 'color' else 'Non-Color') and data['encoding'] == '4K PNG',
                        f'Authored packed material map differs from the official input or projection/color-space contract: {asset}/{map_kind}')
            require(0 < material['physicalFootprintMetres'] < 20 and 0 < material['colorGamma'] < 2 and
                    0 < min(material['roughness']) <= max(material['roughness']) <= 1 and
                    1 < material['ior'] < 2 and 0 <= material['specularIORLevel'] <= 1 and
                    0 < material['normalMapStrength'] <= 1 and 0 < material['heightBumpDistanceMetres'] <= .001 and
                    0 < material['heightBumpStrength'] <= 1,
                    'Invalid authored surface calibration or more than a millimetre of shading relief.')
        bindings = report['wallMaterialBindings']
        require(bindings and {row['after'] for row in bindings} == set(walls), 'Missing wall material bindings.')
        before_bindings, after_bindings = report['allMaterialBindingsBefore'], report['allMaterialBindingsAfter']
        require(isinstance(before_bindings, dict) and before_bindings and set(before_bindings) == set(after_bindings),
                'Incomplete whole-file object material-slot binding proof.')
        actual_changes = set()
        for obj, old_slots in before_bindings.items():
            new_slots = after_bindings[obj]
            require(isinstance(old_slots, list) and isinstance(new_slots, list) and len(old_slots) == len(new_slots),
                    f'Material slot inventory changed: {obj}')
            for slot, (old_material, new_material) in enumerate(zip(old_slots, new_slots)):
                if old_material != new_material:
                    actual_changes.add((obj, slot, old_material, new_material))
        declared_changes = {(row['object'], row['slot'], row['before'], row['after']) for row in bindings}
        require(actual_changes == declared_changes and len(actual_changes) == len(bindings),
                'Actual whole-file material slot changes differ from the exact declared wall/cap replacements.')
        for binding in bindings:
            require(binding['before'] in old_graphs and binding['before'] not in floor_proof['before'] and
                    binding['before'] not in lamp_proof['before'] and binding['after'] == 'V20_MARBLE_'+binding['before'] and
                    binding['after'] in walls,
                    'A protected floor/fixture material was replaced by a marble clone.')
            expected_role = 'wall' if 'Graphite_Enamel' in binding['before'] else 'cap'
            require(('Graphite_Enamel' if expected_role == 'wall' else 'Satin_Titanium') in binding['before'] and
                    walls[binding['after']]['role'] == expected_role, 'White wall/black cap material assigned to the wrong legacy surface.')
        if kind == 'prepared':
            expected = {('WEB8_room_static__baked__A0', 0, 'WEB8_BAKE_A0_MAT_Satin_Titanium', 0),
                        ('WEB8_room_static__baked__A0', 1, 'WEB8_BAKE_A0_MAT_Graphite_Enamel', 0),
                        ('WEB8_room_static__baked__A8', 0, 'WEB8_BAKE_A8_MAT_Satin_Titanium', 8)}
            require(len(bindings) == 3 and {(row['object'], row['slot'], row['before'], row['atlas']) for row in bindings} == expected,
                    'Prepared wall replacement affected objects/material slots outside the accepted walls/caps.')
        else:
            expected = {(obj, 0, material, None) for obj, material in EDITABLE_WALL_BINDINGS.items()}
            require(len(bindings) == 20 and {(row['object'], row['slot'], row['before'], row['atlas']) for row in bindings} == expected,
                    'Editable material replacement changed, repeated or omitted an existing wall/cap binding.')
    return True


def verify(prepared, source, approved):
    require(worker.REUSED_SLOTS == set(REUSED) and worker.ATLAS_COUNT == 13, 'Compressor atlas contract differs from V20 audit.')
    reuse = surface_contract(prepared)
    compression = read('assets/blender/photoreal-materials-v20-compression.json')
    records = texture_contract(compression, reuse)
    inherited = inherited_ktx_contract(records)
    manifests, recovered, probes = light_contract(records)
    require(probes == compression['reflectionProbes'], 'Current source-bound probes differ from compression report.')
    export, audit, scales = model_contract(compression, records, prepared)
    delivery = delivery_contract(prepared, source, export, manifests, scales)
    snapshot = frozen_contract()
    source_contract()
    return dict(complete=True, status='cpu_release_passed', revision=20, preparedSha256=PREPARED_SHA, editableSha256=EDITABLE_SHA,
                model=compression['model'], surfaceReuse=reuse, freshSurfaceSlots=FRESH, unchangedSurfaceSlots=REUSED,
                deliveryEvidence=delivery,
                inheritedSurfaceKtxBytesExactlyPreserved=inherited, all58TextureHashesVerified=True, all29LightMapsFreshSourceBound=True,
                allRecordedNightHdrOutliersRecovered=True, recoveredNightHighlights=recovered, nightRadianceScale=scales,
                allV19GeometryUvsNormalsIndicesExactlyPreserved=True, allV19HierarchyIdsTransformsOwnershipExactlyPreserved=True,
                floorAndFixtureSourceMaterialsVerifiedUnchanged=True, assetIds=96, nodes=199, triangles=418383,
                allUnchangedObjectsRetainActualOriginalMaterialBindings=True,
                wallMaterialAsset='Marble005', capMaterialAsset='Marble002', licensedMaterialMapsVerified=8,
                officialMaterialPackagesVerified=MARBLE_PACKAGES, officialPackageExtractionExactlyVerified=True,
                newPackedMaterialImageHashesMatchOfficialInputs=True,
                geometryAudit='assets/blender/room-v20-geometry-audit.json', geometryAuditSha256=sha(BLENDER/'room-v20-geometry-audit.json'),
                frozenBaseline='assets/blender/room-v20-frozen-baseline.json', frozenBaselineSha256=sha(BASELINE),
                frozenBaselineSupplement='assets/blender/room-v20-frozen-baseline-supplement.json',
                frozenBaselineSupplementSha256=sha(SUPPLEMENT),
                frozenFilesVerified=snapshot['fileCount'], approvedAboutFilesUnchanged=len(approved['files']),
                webLogRgb32Gain256=True, webLightAlphaConstantOne=True, ktxValidationCount=58,
                actualKtxLinearTransferAndFullMipChainsVerified=True, linearMipGenerationEvidenceVerified=True,
                mainAtlasPairs=13, surfaceAtlasPairs=13, introAtlases=3, lightingSamples=96,
                reflectionProbeSamples=64, reflectionProbeDimensions=[2048, 1024], probeOrientationMatches=True,
                lightingBakeSeconds=round(sum(m['seconds'] for m in manifests), 2), glass=export['glass'],
                browserVerified=False, visualApproval=False,
                limitations=['CPU integrity establishes source binding and wall-only scope, not subjective marble veining or browser appearance.'],
                provenance='V20 source authoring, fresh surface/radiance bakes, reflection probes and raw export were recorded as file-targeted Blender MCP operations with Python helpers, without a CLI fallback. This verifier and compression are CPU-only.')


def main():
    global worker
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-baseline', action='store_true', help='Create the one-time frozen V19/Gallery/About/display-asset snapshot.')
    parser.add_argument('--source-only', action='store_true', help='Inspect current source/proof only, never record release success.')
    args = parser.parse_args()
    destination = BLENDER/'room-v20-source-diagnostic.json' if args.source_only else REPORT
    try:
        require(__debug__, 'Do not use python -O; shared compressor validators use assertions.')
        if args.capture_baseline:
            snapshot = capture_baseline()
            print(json.dumps(dict(complete=False, status='baseline_captured_not_release', fileCount=snapshot['fileCount'], path=str(BASELINE)), indent=2))
            return 2
        require(BASELINE.is_file(), 'Capture the V20 frozen baseline before accepting any new source/output.')
        source_paths = [BLENDER/f'photoreal-materials-v20-{name}.json' for name in ('prepared', 'source')]
        if not all(path.exists() and read(path).get('complete') is True for path in source_paths):
            result, code = dict(complete=False, status='pending', missingOrStaleInputs=pending_inputs(), browserVerified=False), 2
        else:
            prepared, source, approved = source_contract()
            if args.source_only:
                reuse_contract(prepared)
                result, code = dict(complete=False, status='source_diagnostic_only', sourceVerified=True, preparedSha256=PREPARED_SHA,
                                    editableSha256=EDITABLE_SHA, freshSurfaceSlots=FRESH, unchangedSurfaceSlots=REUSED,
                                    protectedMaterialsVerified=True, browserVerified=False), 2
            else:
                pending = pending_inputs(PREPARED_SHA)
                if pending:
                    result, code = dict(complete=False, status='pending', preparedSha256=PREPARED_SHA, editableSha256=EDITABLE_SHA,
                                        sourcePreparationVerified=True, missingOrStaleInputs=pending, browserVerified=False), 2
                else:
                    worker = module('room_v20_compression_contract', 'scripts/compress-room-v20.py')
                    result, code = verify(prepared, source, approved), 0
    except (ValueError, AssertionError, KeyError, OSError, IndexError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        result, code = dict(complete=False, status='failed', preparedSha256=PREPARED_SHA,
                            errorType=type(error).__name__, error=str(error), browserVerified=False), 1
    write(destination, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
