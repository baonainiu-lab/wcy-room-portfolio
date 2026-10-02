#!/usr/bin/env python3
"""CPU-only consumer of source-bound, completed V20 Blender bakes.

Never opens Blender. Source changes require an explicit watcher restart; only
F0/normal slots proven equivalent may inherit pixels from V19. Lighting, intro
and probes must be newly baked against the current white-marble-wall prepared source.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / 'public/textures/lighting-v20'
INTRO = ROOT / 'public/textures/intro-clean-v20'
PREPARED = ROOT / 'assets/blender/photoreal-materials-v20-prepared.json'
REPORT = ROOT / 'assets/blender/photoreal-materials-v20-compression.json'
EXPORT = ROOT / 'assets/blender/dual-lighting-v20-export-report.json'
CODEC_REVISION = 'linear-surface-v2-logrgb256'
LIGHT_KIND = 'logrgb32-k256'
REUSED_SLOTS = set(range(13)) - {0, 8}
ATLAS_COUNT = 13
EXPECTED = ({f'{state}-{slot}' for state in ('day', 'night', 'normal', 'specular') for slot in range(ATLAS_COUNT)}
            | {f'intro-{slot}' for slot in (0, 1, 8)} | {'day-window', 'night-window', 'static-screen'})


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


linear = module('linear_surface_v20_compression', ROOT / 'scripts/compress-linear-surface.py')
legacy = module('legacy_v20_model_compression', ROOT / 'scripts/compress-room-v15.py')
legacy.MODEL = ROOT / 'public/models/orbital-atelier-v20.glb'
legacy.OUTPUT = ROOT / 'public/models/orbital-atelier-v20-compressed.glb'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def path(value):
    return ROOT / value


def read(filename):
    try:
        return json.loads(Path(filename).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write(filename, data):
    filename.parent.mkdir(parents=True, exist_ok=True)
    pending = filename.with_suffix('.json.tmp')
    pending.write_text(json.dumps(data, indent=2) + '\n')
    pending.replace(filename)


def source_bound(filename, prepared):
    record = read(filename)
    if record.get('sourceSha256') != prepared or record.get('complete') is False:
        return None
    return record


def verify_prepared(prepared):
    report = read(PREPARED)
    assert report.get('complete') and report['sha256'] == prepared, 'Prepared source changed: restart the V20 worker.'
    assert sha(path(report['derivative'])) == prepared, 'Prepared Blender bytes changed: restart the V20 worker.'
    return report


def reuse_proof(prepared):
    """Return proof only when both MCP inspections bind exact current sources."""
    old = read(ROOT / 'assets/blender/room-v19-to-v20-surface-before.json')
    new = read(ROOT / 'assets/blender/room-v20-surface-reuse-proof.json')
    if not old or not new or new.get('sourceSha256') != prepared:
        return None
    assert old['sourceSha256'] == read(PREPARED)['sourceSha256']
    assert sha(path(old['source'])) == old['sourceSha256']
    assert sha(path(new['source'])) == prepared
    before = {row['slot']: row for row in old['surfaces']}
    after = {row['slot']: row for row in new['surfaces']}
    assert set(before) == set(after) == set(range(ATLAS_COUNT))
    assert set(read(PREPARED)['unchangedSurfaceSlots']) == REUSED_SLOTS
    assert set(read(PREPARED)['affectedSurfaceSlots']) == set(range(ATLAS_COUNT)) - REUSED_SLOTS
    for slot in REUSED_SLOTS:
        assert before[slot] == after[slot], f'Unproven inherited surface slot {slot}'
    return {'sourceSha256': old['sourceSha256'], 'preparedSha256': prepared,
            'slots': sorted(REUSED_SLOTS), 'proofs': [
                {'path': str(ROOT / filename), 'sha256': sha(ROOT / filename)}
                for filename in ('assets/blender/room-v19-to-v20-surface-before.json', 'assets/blender/room-v20-surface-reuse-proof.json')]}


def light_parameters(manifest):
    """Reconstruct every documented HDR outlier before web normalization."""
    maximum = float(manifest['sourceRadianceMaximum'])
    assert math.isfinite(maximum) and maximum >= 0
    overflow = manifest.get('hdrOutliers')
    if maximum > 32 or manifest.get('valuesAboveRangeFraction', 0) > 0:
        assert overflow and overflow['count'] > 0, 'Over-range radiance has no exact float sidecar.'
        scale = 2 ** max(0, math.ceil(math.log2(maximum / 32)))
        return scale, overflow
    assert not overflow or overflow['count'] == 0, 'Unexpected HDR sidecar for an in-range map.'
    return 1, None


def cached(previous, candidate, prepared):
    if not previous or previous.get('preparedSha256') != prepared:
        return False
    for key, expected in [('sourceSha256', candidate['digest']), ('kind', candidate['kind']),
                          ('bakeManifestSha256', candidate['manifestSha256']), ('radianceScale', candidate['scale'])]:
        if previous.get(key, 1 if key == 'radianceScale' else None) != expected:
            return False
    if (previous.get('radianceOverflow') or {}).get('sha256') != (candidate['overflow'] or {}).get('sha256'):
        return False
    output = candidate['source'].with_suffix('.ktx2')
    if not output.is_file() or sha(output) != previous.get('sha256'):
        return False
    if candidate['kind'] == LIGHT_KIND:
        fallback = previous.get('encodedSource') or {}
        if previous.get('codecRevision') != CODEC_REVISION or not fallback.get('path'):
            return False
        if not path(fallback['path']).is_file() or sha(path(fallback['path'])) != fallback.get('sha256'):
            return False
    return True


def candidates(prepared, proof):
    result = []
    def add(key, state, slot, data, manifest, manifest_file, kind):
        source = path(data['path'])
        folder = INTRO if state == 'intro' else TEX
        expected = folder / (f'day-{slot}.png' if state == 'intro' else f'{state}-{slot}.png')
        assert source.resolve() == expected.resolve(), f'Not a V20 output: {source}'
        # A completed old manifest may briefly coexist with an in-progress rewrite.
        # Wait instead of consuming mixed bytes or marking an incomplete file ready.
        if not source.is_file() or sha(source) != data['sha256']:
            return
        scale, overflow = light_parameters(manifest) if kind == LIGHT_KIND else (1, None)
        assert scale == 1 or state == 'night', 'Day/intro radiance normalization needs a separate runtime contract.'
        result.append(dict(key=key, state=state, slot=slot, source=source, digest=data['sha256'],
                           kind=kind, manifest=manifest_file, manifestSha256=sha(manifest_file),
                           scale=scale, overflow=overflow))
    for slot in range(ATLAS_COUNT):
        filename = TEX / f'surface-{slot}-manifest.json'
        surface = source_bound(filename, prepared)
        if surface and surface.get('complete') and (slot not in REUSED_SLOTS or proof):
            if slot in REUSED_SLOTS:
                old = read(ROOT / f'public/textures/lighting-v19/surface-{slot}-manifest.json')
                assert old['sourceSha256'] == proof['sourceSha256']
                for kind in ('normal', 'specular'):
                    assert surface[kind]['sha256'] == old[kind]['sha256'] == sha(path(old[kind]['path']))
            for kind in ('normal', 'specular'):
                add(f'{kind}-{slot}', kind, slot, surface[kind], surface, filename, kind)
        for state in ('day', 'night'):
            filename = TEX / f'{state}-{slot}-manifest.json'
            raw = source_bound(filename, prepared)
            if raw and raw.get('encoding') == 'RGBM32' and raw.get('glossyExcluded') and raw.get('samples') == 96:
                assert not raw.get('inheritedFrom'), 'Lighting must be newly baked against V20.'
                add(f'{state}-{slot}', state, slot, raw, raw, filename, LIGHT_KIND)
    for slot in (0, 1, 8):
        filename = INTRO / f'day-{slot}-manifest.json'
        raw = source_bound(filename, prepared)
        if raw and raw.get('cleanIntro') and raw.get('receiverOnly') and raw.get('samples') == 96:
            assert not raw.get('inheritedFrom'), 'Intro lighting must be newly baked against V20.'
            add(f'intro-{slot}', 'intro', slot, raw, raw, filename, LIGHT_KIND)
    return result


def static_textures(prepared):
    for name in ('window-day.png', 'window-night.png', 'screen-art-render.png', 'day-window.ktx2', 'night-window.ktx2', 'static-screen.ktx2'):
        source, target = ROOT / 'public/textures/lighting-v16' / name, TEX / name
        if not target.exists():
            shutil.copy2(source, target)
        assert sha(source) == sha(target)
    result = {}
    for state, slot, png in [('day', 'window', 'window-day.png'), ('night', 'window', 'window-night.png'), ('static', 'screen', 'screen-art-render.png')]:
        output = TEX / f'{state}-{slot}.ktx2'
        key = f'{state}-{slot}'
        result[key] = dict(key=key, state=state, slot=slot, preparedSha256=prepared,
                           source=str(TEX / png), sourceSha256=sha(TEX / png), path=str(output),
                           sha256=sha(output), bytes=output.stat().st_size,
                           colorSpace='sRGB, byte-identical to V16', inheritedFrom='lighting-v16; unchanged display artwork')
    return result


def probe_records(prepared):
    result = []
    for state in ('day', 'night'):
        record = source_bound(TEX / f'reflection-{state}.json', prepared)
        if not record:
            return None
        assert record['encoding'] == 'scene-linear Radiance HDR'
        filename = path(record['path'])
        assert filename.resolve() == (TEX / f'reflection-{state}.hdr').resolve()
        if not filename.is_file() or sha(filename) != record['sha256']:
            return None
        result.append(record)
    for key in ('dimensions', 'cameraLocation', 'cameraEuler'):
        assert result[0][key] == result[1][key]
    return result


def inherited_encoding(candidate, proof):
    """Copy already verified KTX bytes only for byte-identical surface inputs."""
    if not proof or candidate['kind'] not in ('normal', 'specular') or candidate['slot'] not in REUSED_SLOTS:
        return None
    manifest = ROOT / 'assets/blender/photoreal-materials-v19-compression.json'
    prior = read(manifest)
    assert prior['complete'] and prior['preparedSha256'] == proof['sourceSha256']
    old = next(row for row in prior['textures'] if row['key'] == candidate['key'])
    assert old['sourceSha256'] == candidate['digest'] == sha(path(old['source']))
    assert old['codecRevision'] == CODEC_REVISION and old['kind'] == candidate['kind']
    assert old['ktxValidate'] == 'passed' and old['transferFunction'] == 'linear'
    assert sha(path(old['path'])) == old['sha256']
    target = candidate['source'].with_suffix('.ktx2')
    shutil.copy2(path(old['path']), target)
    assert sha(target) == old['sha256']
    record = json.loads(json.dumps(old))
    record.update(source=str(candidate['source']), path=str(target), seconds=0,
                  inheritedEncoding={'manifest': str(manifest), 'sha256': sha(manifest),
                                     'sourceKtx': old['path'], 'sourceKtxSha256': old['sha256'],
                                     'reason': 'Exact PNG input and matching full source surface proof; identical codec.'})
    record['encodedSource']['path'] = str(candidate['source'])
    return record


def main(watch=False):
    prepared = read(PREPARED)['sha256']
    verify_prepared(prepared)
    TEX.mkdir(parents=True, exist_ok=True)
    old = read(REPORT)
    records = {r['key']: r for r in old.get('textures', [])
               if r.get('preparedSha256') == prepared and r['key'] in EXPECTED}
    records.update(static_textures(prepared))
    # A new prepared SHA immediately invalidates the old release summary, even
    # before its first new bake becomes available. Historical copies are kept.
    if old and old.get('preparedSha256') != prepared:
        history = ROOT / 'assets/blender/v20-compression-history' / old['preparedSha256']
        history.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPORT, history / REPORT.name)
    write(REPORT, dict(complete=False, preparedSha256=prepared, textures=list(records.values())))
    started = time.monotonic()
    while True:
        verify_prepared(prepared)
        proof = reuse_proof(prepared)
        ready = candidates(prepared, proof)
        # Drop stale records even if their new bake is not ready yet.
        ready_keys = {r['key'] for r in ready} | {'day-window', 'night-window', 'static-screen'}
        records = {key: row for key, row in records.items() if key in ready_keys}
        for candidate in ready:
            key = candidate['key']
            if cached(records.get(key), candidate, prepared):
                continue
            verify_prepared(prepared)
            kw = dict(radiance_scale=candidate['scale'], radiance_overflow=candidate['overflow']) if candidate['kind'] == LIGHT_KIND else {}
            record = inherited_encoding(candidate, proof)
            if record is None:
                record = linear.compress(candidate['source'], candidate['source'].with_suffix('.ktx2'), candidate['kind'], **kw)
            assert sha(candidate['manifest']) == candidate['manifestSha256'], 'Bake manifest changed during CPU compression.'
            verify_prepared(prepared)
            record.update(key=key, state=candidate['state'], slot=candidate['slot'], preparedSha256=prepared,
                          bakeManifest=str(candidate['manifest']), bakeManifestSha256=candidate['manifestSha256'])
            records[key] = record
            write(REPORT, dict(complete=False, preparedSha256=prepared, textures=list(records.values()), surfaceReuse=proof))
            print(json.dumps(dict(key=key, bytes=record['bytes'], seconds=record['seconds'], radianceScale=candidate['scale'],
                                  completed=len(records), expected=len(EXPECTED))), flush=True)
        export = read(EXPORT)
        probes = probe_records(prepared)
        if set(records) == EXPECTED and probes and proof and export.get('complete') and export.get('preparedSha256') == prepared and legacy.MODEL.exists() and export['sha256'] == sha(legacy.MODEL):
            verify_prepared(prepared)
            scales = {str(r['slot']): r['radianceScale'] for r in records.values() if r['state'] == 'night' and r.get('radianceScale', 1) != 1}
            assert scales == export['nightRadianceScale'], 'Exported night normalization differs from actual compressed maps.'
            embedded = {}
            for key, record in records.items():
                embedded[key] = dict(record)
                if record.get('encodedSource'):
                    embedded[key].update(source=record['encodedSource']['path'], sourceSha256=record['encodedSource']['sha256'])
            model = legacy.compress_model(embedded, atlas_count=ATLAS_COUNT)
            result = dict(complete=True, preparedSha256=prepared, model=model, textures=list(records.values()),
                          runtimeTextureCount=len(EXPECTED), nightRadianceScale=scales, surfaceReuse=proof, reflectionProbes=probes,
                          codecRevision=CODEC_REVISION, encoding='LogRGB32 gain256 opaque UASTC quality2 + Zstd9, explicit full mip chain',
                          invocation='CPU Python / KTX encoding; Blender execution provenance is recorded separately in room-v20-execution-method.json',
                          mipPolicy='Linear radiance mip filtering then opaque LogRGB; normalized tangent normals; linear F0 / GGX-alpha roughness')
            write(REPORT, result)
            print(json.dumps(dict(complete=True, model=model, textures=len(records), nightRadianceScale=scales)), flush=True)
            return result
        if not watch:
            print(json.dumps(dict(complete=False, readyTextures=len(records), expected=len(EXPECTED), probesReady=bool(probes))))
            return
        if time.monotonic() - started > 14400:
            raise TimeoutError('Room V20 completion exceeded four hours.')
        # Full source/map hashes intentionally revalidate the entire release.
        # Leave the shared CPU/memory bandwidth available to ongoing MCP bakes.
        time.sleep(30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    main(args.watch)
