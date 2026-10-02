"""Refresh only the two room-monitor gallery slides from verified V4 renders."""
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/textures/live-room'
MANIFEST = OUT / 'SOURCE.json'
RENDERS = ROOT / 'renders/works-gallery-v4/render-final.json'
ARCHIVE = ROOT / 'assets/experiments/gallery-v4/live-room-before'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = json.loads(RENDERS.read_text())
    manifest = json.loads(MANIFEST.read_text())
    selected = {}
    for state in ('day', 'night'):
        path = f'renders/works-gallery-v4/{state}.png'
        record = next(item for item in records if item['path'] == path)
        assert record['sha256'] == sha(ROOT / path)
        assert record['resolution'] == [2000, 1200] and record['samples'] >= 64
        selected[state] = record
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for path in [MANIFEST, OUT / 'gallery-day.ktx2', OUT / 'gallery-night.ktx2']:
        if not (ARCHIVE / path.name).exists():
            shutil.copy2(path, ARCHIVE / path.name)
    for state, record in selected.items():
        output = OUT / f'gallery-{state}.ktx2'
        pending = OUT / f'.gallery-{state}-v4.pending.ktx2'
        subprocess.run([str(ROOT / 'tools/ktx-software/bin/toktx'), '--encode', 'uastc',
                        '--uastc_quality', '2', '--zcmp', '9', '--genmipmap', '--threads', '2',
                        '--assign_oetf', 'srgb', str(pending), str(ROOT / record['path'])], check=True)
        subprocess.run([str(ROOT / 'tools/ktx-software/bin/ktx'), 'validate', str(pending)], check=True)
        blob = pending.read_bytes()
        assert list(struct.unpack_from('<II', blob, 20)) == [2000, 1200]
        assert struct.unpack_from('<I', blob, 40)[0] == 11
        pending.replace(output)
        slide = next(item for item in manifest['slides'] if isinstance(item, dict) and item['renderState'] == state)
        slide['previousSource'] = {'path': slide['source'], 'sha256': slide['sourceSha256']}
        slide.update(source=record['path'], sourceSha256=record['sha256'], sha256=sha(output),
                     bytes=output.stat().st_size, sourceRenderManifest=str(RENDERS.relative_to(ROOT)),
                     renderSamples=record['samples'], content='Original V4 gallery scene study with continuous frame walls and solid architectural glass. Personal work remains pending.')
    manifest['gallerySlideshowRevision'] = 4
    manifest['gallerySlideshowNotes'] = 'Only gallery slides refreshed from 2000×1200 V4 Cycles renders. Original sculpture slide, room model and room window city remain unchanged.'
    pending = MANIFEST.with_suffix('.json.pending')
    pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    pending.replace(MANIFEST)
    print(json.dumps({'complete': True, 'revision': 4, 'slides': 2}))


if __name__ == '__main__':
    main()
