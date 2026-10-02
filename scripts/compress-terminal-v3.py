#!/usr/bin/env python3
"""Compress Terminal V3 material images; never change source meshes or animations."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gallery_compression', ROOT / 'scripts/compress-works-gallery-v5.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
TEXTURES = ROOT / 'public/textures/welcome-terminal-v3'
SOURCE = ROOT / 'public/models/welcome-terminal-v3.glb'
OUTPUT = ROOT / 'public/models/welcome-terminal-v3-compressed.glb'
REPORT = ROOT / 'assets/blender/welcome-terminal-v3-compression.json'


def main():
    original_bytes = SOURCE.read_bytes()
    original, chunks = c.parse_glb(original_bytes)
    binary = next(data for kind, data in chunks if kind == c.BIN_CHUNK)
    document = copy.deepcopy(original)
    records, replacements, indices = [], {}, set()
    for channel, oetf in [('normal', 'linear'), ('basecolor', 'srgb'), ('orm', 'linear')]:
        source, output = TEXTURES / f'{channel}.png', TEXTURES / f'{channel}.ktx2'
        source_hash = c.sha(source.read_bytes())
        matches = [(i, image) for i, image in enumerate(document['images'])
                   if image['mimeType'] == 'image/png' and c.sha(c.view_bytes(original, binary, original['bufferViews'][image['bufferView']])) == source_hash]
        c.require(len(matches) == 1, f'Expected exact embedded source image: {channel}')
        started = time.monotonic()
        command = [str(c.TOOL), '--encode', 'uastc', '--uastc_quality', '3', '--uastc_rdo_l', '.5',
                   '--zcmp', '9', '--genmipmap', '--threads', '4', '--assign_oetf', oetf]
        # Standard glTF requires RGB tangent normals, not the alternate XY/AG packing.
        if channel == 'normal': command += ['--normalize', '--input_swizzle', 'rgb1']
        subprocess.run(command + [str(output), str(source)], check=True)
        subprocess.run([str(c.VALIDATOR), 'validate', str(output)], check=True)
        blob = output.read_bytes()
        info = c.ktx_info(blob)
        c.require(info['resolution'] == [2048, 2048], 'Resolution changed')
        index, image = matches[0]
        replacements[image['bufferView']] = blob
        indices.add(index)
        image['mimeType'] = 'image/ktx2'
        records.append({'channel': channel, 'source': c.rel(source), 'sourceSha256': source_hash,
                        'path': c.rel(output), 'sha256': c.sha(blob), 'bytes': len(blob), 'oetf': oetf,
                        'seconds': round(time.monotonic() - started, 2), **info})
        c.require(c.sha(source.read_bytes()) == source_hash, 'Compression modified source PNG')
        print(f'{channel}: {len(blob)} bytes', flush=True)
    for texture in document['textures']:
        if texture.get('source') in indices:
            texture.setdefault('extensions', {})['KHR_texture_basisu'] = {'source': texture.pop('source')}
    for key in ('extensionsUsed', 'extensionsRequired'):
        document.setdefault(key, [])
        if 'KHR_texture_basisu' not in document[key]: document[key].append('KHR_texture_basisu')
    rebuilt, preserved = bytearray(), {}
    for index, view in enumerate(document['bufferViews']):
        old = c.view_bytes(original, binary, original['bufferViews'][index])
        payload = replacements.get(index, old)
        rebuilt.extend(b'\0' * (-len(rebuilt) % 4))
        view['byteOffset'], view['byteLength'] = len(rebuilt), len(payload)
        rebuilt.extend(payload)
        if index not in replacements: preserved[index] = c.sha(old)
    document['buffers'][0]['byteLength'] = len(rebuilt)
    compressed = c.pack_glb(document, [(kind, bytes(rebuilt) if kind == c.BIN_CHUNK else data) for kind, data in chunks])
    check, check_chunks = c.parse_glb(compressed)
    check_bin = next(data for kind, data in check_chunks if kind == c.BIN_CHUNK)
    for key in set(original) - {'images', 'textures', 'bufferViews', 'buffers', 'extensionsUsed', 'extensionsRequired'}:
        c.require(check.get(key) == original[key], f'Unrelated JSON changed: {key}')
    for index, expected in preserved.items():
        c.require(c.sha(c.view_bytes(check, check_bin, check['bufferViews'][index])) == expected, 'Non-material buffer changed')
    c.require(c.sha(SOURCE.read_bytes()) == c.sha(original_bytes), 'Raw source GLB changed')
    OUTPUT.write_bytes(compressed)
    report = {'complete': True, 'method': 'Official KTX-Software UASTC quality 3, RDO .5, Zstd 9; source Blender bakes unmodified',
              'source': c.rel(SOURCE), 'sourceSha256': c.sha(original_bytes), 'sourceBytes': len(original_bytes),
              'output': c.rel(OUTPUT), 'sha256': c.sha(compressed), 'bytes': len(compressed),
              'textures': records, 'geometryAndAnimationUnchangedFromRawV3': True,
              'preservedNonMaterialBufferViews': len(preserved), 'preservedOriginalScreenArtwork': True}
    c.atomic_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__': main()
