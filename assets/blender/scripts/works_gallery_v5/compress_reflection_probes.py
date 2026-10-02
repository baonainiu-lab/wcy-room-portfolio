"""CPU-only UASTC/Zstd reflection compression with source hashes and KTX validation."""
import argparse
import hashlib
import json
import math
import struct
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'public/textures/works-gallery-v5'
MANIFEST = OUT / 'reflection-SOURCE.json'
TOKTX = ROOT / 'tools/ktx-software/bin/toktx'
KTX = ROOT / 'tools/ktx-software/bin/ktx'
SIZE = [2048, 1024]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    pending.replace(path)


def info(blob):
    assert len(blob) >= 80 and blob[:12] == b'\xabKTX 20\xbb\r\n\x1a\n'
    vk, _, width, height, depth, layers, faces, levels, scheme = struct.unpack_from('<9I', blob, 12)
    assert [width, height] == SIZE and vk == 0 and depth == 0 and layers == 0 and faces == 1
    assert scheme == 2 and levels == int(math.log2(max(SIZE))) + 1
    total = 0
    for level in range(levels):
        offset, count, raw = struct.unpack_from('<QQQ', blob, 80 + 24 * level)
        assert offset + count <= len(blob)
        expected = max(1, math.ceil(max(1, width >> level) / 4)) * max(1, math.ceil(max(1, height >> level) / 4)) * 16
        assert raw == expected
        total += raw
    start, size = struct.unpack_from('<II', blob, 56)
    assert start + size <= len(blob)
    assert b'KTXorientation\x00rd' in blob[start:start + size]
    return {'resolution': SIZE, 'mip_levels': levels, 'orientation': 'rd',
            'uastc_mip_bytes': total, 'validated': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    assert args.threads > 0 and TOKTX.is_file() and KTX.is_file()
    manifest = json.loads(MANIFEST.read_text())
    assert manifest['complete'] and {r['state'] for r in manifest['renders']} == {'day', 'night'}
    for path, expected in manifest['input_sha256'].items():
        assert sha(ROOT / path) == expected, 'Capture input is stale: ' + path
    previous = {r['state']: r for r in manifest.get('compressed_textures', [])}
    records = []
    for record in sorted(manifest['renders'], key=lambda r: r['state']):
        state = record['state']
        source = ROOT / record['path']
        assert sha(source) == record['sha256']
        png = source.read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n' and list(struct.unpack_from('>II', png, 16)) == SIZE
        output = OUT / f'reflection-{state}.ktx2'
        pending = OUT / f'.reflection-{state}.pending.ktx2'
        old = previous.get(state, {})
        started = time.monotonic()
        reuse = old.get('source_png_sha256') == record['sha256'] and output.is_file() and old.get('sha256') == sha(output)
        if not reuse:
            subprocess.run([str(TOKTX), '--encode', 'uastc', '--uastc_quality', '2', '--zcmp', '9',
                            '--genmipmap', '--threads', str(args.threads), '--assign_oetf', 'srgb',
                            str(pending), str(source)], check=True)
            subprocess.run([str(KTX), 'validate', str(pending)], check=True)
            details = info(pending.read_bytes())
            assert sha(source) == record['sha256'], 'PNG changed during encoding'
            pending.replace(output)
        else:
            subprocess.run([str(KTX), 'validate', str(output)], check=True)
            details = info(output.read_bytes())
        result = {'state': state, 'path': output.relative_to(ROOT).as_posix(), 'sha256': sha(output),
                  'bytes': output.stat().st_size, 'source_png_sha256': record['sha256'],
                  'encoding': 'UASTC quality2 + Zstd9, sRGB', 'seconds': round(time.monotonic() - started, 3),
                  'reused': reuse, **details}
        records.append(result)
        print(json.dumps(result), flush=True)
    for path, expected in manifest['input_sha256'].items():
        assert sha(ROOT / path) == expected
    manifest['compressed_textures'] = records
    manifest['compression_complete'] = True
    manifest['source_inputs_unchanged'] = True
    atomic_json(MANIFEST, manifest)
    print(json.dumps({'complete': True, 'files': len(records), 'gpu_used': False}), flush=True)


if __name__ == '__main__':
    main()
