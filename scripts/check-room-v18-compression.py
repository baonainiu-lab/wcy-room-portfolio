#!/usr/bin/env python3
"""Small CPU lifecycle checks for V18's source-bound compression queue."""
import copy
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('worker', ROOT / 'scripts/compress-room-v18.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
checks = []

def rejects(call):
    try:
        call()
    except AssertionError:
        return
    raise AssertionError('Expected rejection')

with tempfile.TemporaryDirectory(prefix='room-v18-queue-') as tmp:
    folder = Path(tmp)
    png, ktx, fallback, manifest = [folder / name for name in ('night-4.png', 'night-4.ktx2', 'night-4.logrgb.png', 'night-4-manifest.json')]
    for name in (png, ktx, fallback):
        name.write_bytes(name.name.encode())
    manifest.write_text(json.dumps({'sourceSha256': 'prepared-new', 'complete': True}))
    assert w.source_bound(manifest, 'prepared-new')
    assert w.source_bound(manifest, 'prepared-old') is None
    manifest.write_text('{')
    assert w.source_bound(manifest, 'prepared-new') is None
    manifest.write_text(json.dumps({'sourceSha256': 'prepared-new', 'complete': False}))
    assert w.source_bound(manifest, 'prepared-new') is None
    checks.append('incomplete, partially written and previous-source manifests never enter the queue')
    candidate = dict(source=png, digest=w.sha(png), kind=w.LIGHT_KIND, manifestSha256=w.sha(manifest), scale=8, overflow={'sha256':'overflow-a'})
    record = dict(preparedSha256='prepared-new', sourceSha256=w.sha(png), kind=w.LIGHT_KIND, bakeManifestSha256=w.sha(manifest),
                  radianceScale=8, radianceOverflow={'sha256':'overflow-a'}, sha256=w.sha(ktx), codecRevision=w.CODEC_REVISION,
                  encodedSource=dict(path=str(fallback), sha256=w.sha(fallback)))
    assert w.cached(record, candidate, 'prepared-new')
    for field, value in [('preparedSha256','prepared-old'), ('sourceSha256','old'), ('bakeManifestSha256','old'),
                         ('radianceScale', 2), ('radianceOverflow', {'sha256':'overflow-b'}), ('kind','rgbm32'), ('codecRevision','old')]:
        stale = copy.deepcopy(record)
        stale[field] = value
        assert not w.cached(stale, candidate, 'prepared-new'), field
    checks.append('cache binds prepared source, raw source, complete manifest, codec, normalization and exact HDR sidecar')
    fallback.write_bytes(b'corrupted fallback')
    assert not w.cached(record, candidate, 'prepared-new')
    fallback.unlink()
    assert not w.cached(record, candidate, 'prepared-new')
    checks.append('missing or changed LogRGB fallback invalidates an otherwise matching KTX cache')
    assert w.light_parameters({'sourceRadianceMaximum': 31.5, 'valuesAboveRangeFraction': 0}) == (1, None)
    overflow = {'count': 5022, 'sha256': 'actual-sidecar'}
    assert w.light_parameters({'sourceRadianceMaximum':139.899, 'valuesAboveRangeFraction':.001, 'hdrOutliers':overflow}) == (8, overflow)
    assert w.light_parameters({'sourceRadianceMaximum':32.01, 'valuesAboveRangeFraction':.00001, 'hdrOutliers':overflow}) == (2, overflow)
    rejects(lambda: w.light_parameters({'sourceRadianceMaximum': 139.899, 'valuesAboveRangeFraction': .001}))
    rejects(lambda: w.light_parameters({'sourceRadianceMaximum': float('nan')}))
    checks.append('new peak determines ceil-power-of-two scale; missing overflow and nonfinite source peaks reject')
    assert len(w.EXPECTED) == 54 and len(w.REUSED_SLOTS) == 10 and not {0,8} & w.REUSED_SLOTS
    assert {'intro-0','intro-1','intro-8','day-window','night-window','static-screen'} <= w.EXPECTED
    checks.append('exact complete-key set distinguishes all lighting, source data, intro and unmodified image slots')
    derivative = folder / 'source.blend'
    derivative.write_bytes(b'prepared new')
    w.PREPARED = folder / 'prepared.json'
    digest = w.sha(derivative)
    w.PREPARED.write_text(json.dumps({'complete':True, 'sha256':digest, 'derivative':str(derivative)}))
    w.verify_prepared(digest)
    derivative.write_bytes(b'edited during watcher')
    rejects(lambda: w.verify_prepared(digest))
    checks.append('prepared Blender bytes changing during a queue stop rather than mix material revisions')
print(json.dumps({'complete':True, 'checks':checks, 'passed':len(checks), 'GPUUsed':False}, indent=2))
