#!/usr/bin/env python3
"""Compress V15 Cycles bakes without touching their pixels, UVs, or source GLB."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gallery_compression', ROOT / 'scripts/compress-works-gallery.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
TEX = ROOT / 'public/textures/lighting-v15'
MODEL = ROOT / 'public/models/orbital-atelier-v15.glb'
OUTPUT = MODEL.with_name('orbital-atelier-v15-compressed.glb')
REPORT = ROOT / 'assets/blender/texture-precision-v15-compression.json'
sha, require = shared.sha, shared.require


def encode(state, slot, previous):
    source = TEX / ('screen-art-render.png' if slot == 'screen' else f'window-{state}.png' if slot == 'window' else f'{state}-{slot}.png')
    if not source.is_file():
        return None
    source_bytes = source.read_bytes()
    digest = sha(source_bytes)
    output = TEX / f'{state}-{slot}.ktx2'
    if previous and previous['sourceSha256'] == digest and output.is_file() and sha(output.read_bytes()) == previous['sha256']:
        return previous
    pending = output.with_suffix('.pending.ktx2')
    started = time.monotonic()
    subprocess.run([str(shared.TOOL), '--encode', 'uastc', '--uastc_quality', '2', '--zcmp', '9',
                    '--genmipmap', '--threads', '2', '--assign_oetf', 'srgb', str(pending), str(source)], check=True)
    subprocess.run([str(shared.VALIDATOR), 'validate', str(pending)], check=True)
    blob = pending.read_bytes()
    info = shared.ktx_info(blob)
    require(sha(source.read_bytes()) == digest, f'Source changed while encoding {source}')
    pending.replace(output)
    print(f'Encoded {state}-{slot}: {info["resolution"]}, {time.monotonic()-started:.1f}s', flush=True)
    return {'state': state, 'slot': slot, 'source': shared.rel(source), 'sourceSha256': digest,
            'path': shared.rel(output), 'sha256': sha(blob), 'bytes': len(blob), **info}


def compress_model(records, atlas_count=12):
    original_bytes = MODEL.read_bytes()
    original, chunks = shared.parse_glb(original_bytes)
    doc = copy.deepcopy(original)
    binary = next(data for kind, data in chunks if kind == shared.BIN_CHUNK)
    replacements = {}
    slots = set()
    for material in doc['materials']:
        name = material.get('name', '')
        slot = (int(name.rsplit('_', 1)[1]) if name.startswith('WEB8_LIGHTMAP_') else
                'window' if name == 'WEB8_WINDOW_CITY' else
                'screen' if name == 'WEB8_IMAGE_MAT_Rendered_3D_ScreenArtwork' else None)
        if slot is None:
            continue
        require(slot not in slots, 'Duplicate lighting material')
        slots.add(slot)
        texture = doc['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']]
        image_index = texture['source']
        image = doc['images'][image_index]
        require(image.get('mimeType') == 'image/png' and 'bufferView' in image, 'Expected embedded PNG')
        view_index = image['bufferView']
        record = records['static-screen' if slot == 'screen' else f'night-{slot}']
        require(sha(shared.view_bytes(original, binary, original['bufferViews'][view_index])) == record['sourceSha256'],
                f'GLB night image does not match bake {slot}')
        blob = (ROOT / record['path']).read_bytes()
        require(sha(blob) == record['sha256'], 'Compressed texture changed')
        replacements[view_index] = blob
        image['mimeType'] = 'image/ktx2'
        texture.pop('source')
        texture.setdefault('extensions', {})['KHR_texture_basisu'] = {'source': image_index}
    require(slots == set(range(atlas_count)) | {'window', 'screen'}, f'Expected {atlas_count} room atlases, window, and screen')
    for key in ('extensionsUsed', 'extensionsRequired'):
        doc.setdefault(key, [])
        if 'KHR_texture_basisu' not in doc[key]:
            doc[key].append('KHR_texture_basisu')
    rebuilt = bytearray()
    preserved = {}
    for index, view in enumerate(doc['bufferViews']):
        source = shared.view_bytes(original, binary, original['bufferViews'][index])
        data = replacements.get(index, source)
        rebuilt.extend(b'\0' * (-len(rebuilt) % 4))
        view['byteOffset'], view['byteLength'] = len(rebuilt), len(data)
        rebuilt.extend(data)
        if index not in replacements:
            preserved[index] = sha(source)
    doc['buffers'][0]['byteLength'] = len(rebuilt)
    output_bytes = shared.pack_glb(doc, [(kind, bytes(rebuilt) if kind == shared.BIN_CHUNK else data) for kind, data in chunks])
    verified, out_chunks = shared.parse_glb(output_bytes)
    out_binary = next(data for kind, data in out_chunks if kind == shared.BIN_CHUNK)
    for key in set(original) - {'images', 'textures', 'bufferViews', 'buffers', 'extensionsUsed', 'extensionsRequired'}:
        require(verified.get(key) == original[key], f'Non-texture data changed: {key}')
    for index, digest in preserved.items():
        require(sha(shared.view_bytes(verified, out_binary, verified['bufferViews'][index])) == digest, f'Geometry changed: {index}')
    require(sha(MODEL.read_bytes()) == sha(original_bytes), 'Source model changed')
    pending = OUTPUT.with_suffix('.pending.glb')
    pending.write_bytes(output_bytes)
    pending.replace(OUTPUT)
    return {'path': shared.rel(OUTPUT), 'bytes': len(output_bytes), 'sha256': sha(output_bytes),
            'sourceSha256': sha(original_bytes), 'sourceBytes': len(original_bytes),
            'preservedNonAtlasBufferViews': len(preserved), 'geometryAndHierarchyUnchanged': True,
            'replacedImages': len(replacements)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--textures-only', action='store_true')
    args = parser.parse_args()
    previous = shared.read_json(REPORT)
    records = {f'{r["state"]}-{r["slot"]}': r for r in previous.get('textures', [])}
    for state in ('day', 'night', 'static'):
        for slot in (['screen'] if state == 'static' else [*range(12), 'window']):
            key = f'{state}-{slot}'
            result = encode(state, slot, records.get(key))
            if result:
                records[key] = result
                shared.atomic_json(REPORT, {'complete': False, 'textures': list(records.values())})
    if args.textures_only:
        print(f'{len(records)}/27 textures encoded', flush=True)
        return
    require(len(records) == 27, 'Not all baked images are ready')
    model = compress_model(records)
    report = {'complete': True, 'encoding': 'UASTC quality 2 + Zstd 9, full mip chain',
              'model': model, 'textures': list(records.values()),
              'rgba8MipBytes': sum(r['rgba8MipBytes'] for r in records.values()),
              'astcOrBc7MipBytes': sum(r['uastcAstcBc7MipBytes'] for r in records.values())}
    shared.atomic_json(REPORT, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'textures'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
