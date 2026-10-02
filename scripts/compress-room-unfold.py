#!/usr/bin/env python3
"""Reuse the 14 verified V15 KTX2 images in a Blender-exported RoomUnfold GLB.

No encoding, Blender invocation, geometry edit or source-file write occurs here.
Use the bundled Python (Pillow required). --self-test never writes a model.
"""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gallery_compression', ROOT / 'scripts/compress-works-gallery.py')
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)
sha, require = shared.sha, shared.require
MODEL = ROOT / 'public/models/room-unfold-v1.glb'
OUTPUT = ROOT / 'public/models/room-unfold-v1-compressed.glb'
REPORT = ROOT / 'docs/validation/room-unfold-compression.json'
BASELINE = ROOT / 'public/models/orbital-atelier-v15.glb'
MANIFEST = ROOT / 'assets/blender/texture-precision-v15-compression.json'
EXPECTED_SLOTS = set(range(12)) | {'window', 'screen'}


def pixel_fingerprint(blob):
    """Compare decoded samples, allowing harmless Blender PNG recompression.

    Pillow does not apply ICC/gamma transforms here. The material's sRGB color
    contract is retained, and the existing KTX2 was encoded from this baseline.
    Reject high-depth PNG instead of silently quantizing to pass the comparison.
    """
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError('Pillow is required; use the bundled dependencies/python/bin/python3') from error
    require(blob[:8] == b'\x89PNG\r\n\x1a\n' and len(blob) >= 33, 'Expected complete PNG header')
    require(blob[24] == 8 and blob[25] in (2, 6), 'Expected 8-bit RGB/RGBA PNG; refusing sample-depth conversion')
    with Image.open(io.BytesIO(blob)) as image:
        image.load()
        require(image.format == 'PNG', 'Decoded format is not PNG')
        size = list(image.size)
        with image.convert('RGBA') as rgba:
            # Dimensions are part of the hash so differently shaped images
            # cannot alias even if their raw sample sequence were identical.
            digest = shared.hashlib.sha256(struct.pack('>II', *size))
            digest.update(rgba.tobytes())
    return {'resolution': size, 'rgba8PixelSha256': digest.hexdigest()}


def material_slot(name):
    match = re.fullmatch(r'WEB8_LIGHTMAP_(\d+)(?:\.\d+)?', name)
    if match:
        return int(match.group(1))
    if re.fullmatch(r'WEB8_WINDOW_CITY(?:\.\d+)?', name):
        return 'window'
    if re.fullmatch(r'WEB8_IMAGE_MAT_Rendered_3D_ScreenArtwork(?:\.\d+)?', name):
        return 'screen'
    return None


def cached_textures():
    manifest = shared.read_json(MANIFEST)
    require(manifest.get('complete') is True, 'V15 compression manifest is incomplete')
    require(sha(BASELINE.read_bytes()) == manifest['model']['sourceSha256'], 'Protected V15 source differs from its compression manifest')
    records = {f"{record['state']}-{record['slot']}": record for record in manifest['textures']}
    result = {}
    for slot in sorted(EXPECTED_SLOTS, key=str):
        key = 'static-screen' if slot == 'screen' else f'night-{slot}'
        record = records.get(key)
        require(record is not None, f'Missing known V15 compression record: {key}')
        source_path, compressed_path = ROOT / record['source'], ROOT / record['path']
        png, ktx = source_path.read_bytes(), compressed_path.read_bytes()
        require(sha(png) == record['sourceSha256'], f'Protected PNG changed: {source_path}')
        require(sha(ktx) == record['sha256'], f'Protected KTX2 changed: {compressed_path}')
        pixels, info = pixel_fingerprint(png), shared.ktx_info(ktx)
        require(pixels['resolution'] == info['resolution'] == record['resolution'], f'Texture dimensions differ: {key}')
        result[slot] = {'record': record, 'pixels': pixels, 'ktx': ktx}
    return result


def non_image_accessor_views(document):
    references = set()
    for accessor in document.get('accessors', []):
        if 'bufferView' in accessor:
            references.add(accessor['bufferView'])
        for entry in ('indices', 'values'):
            sparse_view = accessor.get('sparse', {}).get(entry, {}).get('bufferView')
            if sparse_view is not None:
                references.add(sparse_view)
    return references


def animation_views(document):
    indices = set()
    for animation in document.get('animations', []):
        for sampler in animation.get('samplers', []):
            for key in ('input', 'output'):
                accessor = document['accessors'][sampler[key]]
                if 'bufferView' in accessor:
                    indices.add(accessor['bufferView'])
                for entry in ('indices', 'values'):
                    index = accessor.get('sparse', {}).get(entry, {}).get('bufferView')
                    if index is not None:
                        indices.add(index)
    return indices


def verify_replacement(original, original_binary, output_blob, replacements):
    output, chunks = shared.parse_glb(output_blob)
    binary = next(payload for kind, payload in chunks if kind == shared.BIN_CHUNK)
    allowed = {'images', 'textures', 'bufferViews', 'buffers', 'extensionsUsed', 'extensionsRequired'}
    require(set(output) == set(original) | {'extensionsUsed', 'extensionsRequired'}, 'Unexpected top-level keys changed')
    for key in set(original) - allowed:
        require(output[key] == original[key], f'Non-texture JSON changed: {key}')
    require(output.get('animations', []) == original.get('animations', []), 'Animation definitions changed')
    require(len(output['bufferViews']) == len(original['bufferViews']), 'bufferView count changed')
    preserved = {}
    for index, before in enumerate(original['bufferViews']):
        after = output['bufferViews'][index]
        require({k: v for k, v in before.items() if k not in {'byteOffset', 'byteLength'}} ==
                {k: v for k, v in after.items() if k not in {'byteOffset', 'byteLength'}}, f'bufferView metadata changed: {index}')
        expected = replacements.get(index, shared.view_bytes(original, original_binary, before))
        actual = shared.view_bytes(output, binary, after)
        require(actual == expected, f'Buffer payload changed unexpectedly: {index}')
        if index not in replacements:
            require(before['byteLength'] == after['byteLength'], f'Non-image byteLength changed: {index}')
            preserved[str(index)] = sha(actual)
    require({k: v for k, v in original['buffers'][0].items() if k != 'byteLength'} ==
            {k: v for k, v in output['buffers'][0].items() if k != 'byteLength'}, 'Buffer metadata changed')
    for key in ('extensionsUsed', 'extensionsRequired'):
        require(output[key] == original.get(key, []) + (['KHR_texture_basisu'] if 'KHR_texture_basisu' not in original.get(key, []) else []), f'Unexpected extension change: {key}')
    require(len(output['images']) == len(original['images']), 'Image count changed')
    for before, after in zip(original['images'], output['images']):
        require({**before, 'mimeType': 'image/ktx2'} == after, 'Image metadata changed beyond mimeType')
    require(len(output['textures']) == len(original['textures']), 'Texture count changed')
    for before, after in zip(original['textures'], output['textures']):
        expected = copy.deepcopy(before)
        image_index = expected.pop('source')
        expected.setdefault('extensions', {})['KHR_texture_basisu'] = {'source': image_index}
        require(expected == after, 'Texture binding changed beyond KHR_texture_basisu')
    return preserved


def compress(source_blob, cache, require_animation=True):
    original, chunks = shared.parse_glb(source_blob)
    require(len(original.get('buffers', [])) == 1 and 'uri' not in original['buffers'][0], 'Expected one embedded buffer')
    binary = next(payload for kind, payload in chunks if kind == shared.BIN_CHUNK)
    if require_animation:
        clips = [clip for clip in original.get('animations', []) if clip.get('name') == 'RoomUnfold']
        require(len(clips) == 1 and clips[0].get('channels'), 'Expected one nonempty RoomUnfold animation')
    require(len(original.get('images', [])) == 14, 'Expected exactly the 14 original V15 PNG images')
    document = copy.deepcopy(original)
    bindings, images = {}, {}
    for material in original.get('materials', []):
        slot = material_slot(material.get('name', ''))
        if slot is None:
            continue
        require(slot in EXPECTED_SLOTS, f'Unexpected lightmap slot {slot}')
        texture_index = material.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
        require(texture_index is not None, f'Missing texture for slot {slot}')
        texture = original['textures'][texture_index]
        require('source' in texture and 'KHR_texture_basisu' not in texture.get('extensions', {}), 'Input must be the uncompressed Blender GLB')
        image_index = texture['source']
        require(slot not in bindings or bindings[slot] == image_index, f'Slot {slot} references multiple images')
        require(image_index not in images or images[image_index] == slot, 'Different slots share an image')
        bindings[slot], images[image_index] = image_index, slot
    require(set(bindings) == EXPECTED_SLOTS, 'Expected 12 named room atlases plus window and screen')
    require(set(images) == set(range(14)), 'There are unmapped or duplicate embedded images')
    replacements, image_records = {}, []
    for index, image in enumerate(document['images']):
        require(image.get('mimeType') == 'image/png' and 'uri' not in image and 'bufferView' in image, 'Expected embedded PNG')
        view_index, slot = image['bufferView'], images[index]
        require(view_index not in replacements, 'Image bufferViews unexpectedly alias')
        require(view_index not in non_image_accessor_views(original), 'Image bufferView is also used by geometry or animation')
        embedded = shared.view_bytes(original, binary, original['bufferViews'][view_index])
        expected = cache[slot]
        actual_pixels = pixel_fingerprint(embedded)
        require(actual_pixels == expected['pixels'], f'Pixel data changed in exported image {index}, slot {slot}; refusing old KTX2 reuse')
        replacements[view_index] = expected['ktx']
        image['mimeType'] = 'image/ktx2'
        image_records.append({'slot': slot, 'imageIndex': index, 'bufferView': view_index,
                              'exportedPngSha256': sha(embedded), 'originalPngSha256': expected['record']['sourceSha256'],
                              'pngBytesIdentical': sha(embedded) == expected['record']['sourceSha256'],
                              **actual_pixels, 'ktx2Path': expected['record']['path'], 'ktx2Sha256': sha(expected['ktx'])})
    for texture in document['textures']:
        require(texture.get('source') in images, 'Unmapped texture source')
        image_index = texture.pop('source')
        texture.setdefault('extensions', {})['KHR_texture_basisu'] = {'source': image_index}
    for key in ('extensionsUsed', 'extensionsRequired'):
        document.setdefault(key, [])
        if 'KHR_texture_basisu' not in document[key]:
            document[key].append('KHR_texture_basisu')
    rebuilt = bytearray()
    for index, view in enumerate(document['bufferViews']):
        payload = replacements.get(index, shared.view_bytes(original, binary, original['bufferViews'][index]))
        rebuilt.extend(b'\0' * (-len(rebuilt) % 4))
        view['byteOffset'], view['byteLength'] = len(rebuilt), len(payload)
        rebuilt.extend(payload)
    document['buffers'][0]['byteLength'] = len(rebuilt)
    output = shared.pack_glb(document, [(kind, bytes(rebuilt) if kind == shared.BIN_CHUNK else payload) for kind, payload in chunks])
    preserved = verify_replacement(original, binary, output, replacements)
    tracks = animation_views(original)
    require(tracks.issubset(set(map(int, preserved))), 'Animation data was classified as replaceable imagery')
    report = {'sourceBytes': len(source_blob), 'sourceSha256': sha(source_blob), 'bytes': len(output), 'sha256': sha(output),
              'replacedImages': len(replacements), 'images': image_records,
              'reencodedPngSlots': [item['slot'] for item in image_records if not item['pngBytesIdentical']],
              'preservedNonImageBufferViews': len(preserved),
              'preservedBufferViewSha256': preserved, 'animationNames': [a.get('name') for a in original.get('animations', [])],
              'animationChannelCount': sum(len(a.get('channels', [])) for a in original.get('animations', [])),
              'animationBufferViews': sorted(tracks), 'animationJsonUnchanged': True, 'allNonImageBytesUnchanged': True,
              'nodesMeshesAccessorsMaterialsUnchanged': True, 'inputImagesPixelIdenticalToV15': True}
    return output, report


def self_test(cache):
    from PIL import Image
    pixels = Image.new('RGBA', (2, 2), (13, 27, 91, 255))
    a, b = io.BytesIO(), io.BytesIO()
    pixels.save(a, format='PNG', compress_level=0); pixels.save(b, format='PNG', compress_level=9)
    require(a.getvalue() != b.getvalue(), 'PNG recompression fixture did not change bytes')
    require(pixel_fingerprint(a.getvalue()) == pixel_fingerprint(b.getvalue()), 'Pixel check rejects harmless recompression')
    pixels.putpixel((1, 1), (13, 27, 92, 255)); changed = io.BytesIO(); pixels.save(changed, format='PNG')
    require(pixel_fingerprint(a.getvalue()) != pixel_fingerprint(changed.getvalue()), 'Pixel check misses one changed sample')
    baseline_blob = BASELINE.read_bytes()
    output, report = compress(baseline_blob, cache, require_animation=False)
    doc, chunks = shared.parse_glb(output)
    # Corrupt one original accessor payload in memory; verification must reject.
    original, original_chunks = shared.parse_glb(baseline_blob)
    old_binary = next(data for kind, data in original_chunks if kind == shared.BIN_CHUNK)
    replacements = {item['bufferView']: cache[item['slot']]['ktx'] for item in report['images']}
    corrupted = bytearray(next(data for kind, data in chunks if kind == shared.BIN_CHUNK))
    view_index = min(non_image_accessor_views(doc)); corrupted[doc['bufferViews'][view_index].get('byteOffset', 0)] ^= 1
    bad = shared.pack_glb(doc, [(kind, bytes(corrupted) if kind == shared.BIN_CHUNK else data) for kind, data in chunks])
    try:
        verify_replacement(original, old_binary, bad, replacements)
    except RuntimeError as error:
        require('payload changed' in str(error), str(error))
    else:
        raise RuntimeError('Binary corruption was accepted')
    doc['animations'] = [{'name': 'unexpected animation mutation'}]
    bad_json = shared.pack_glb(doc, chunks)
    try:
        verify_replacement(original, old_binary, bad_json, replacements)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('Animation JSON mutation was accepted')
    require(sha(BASELINE.read_bytes()) == sha(baseline_blob), 'Protected baseline changed during self-test')
    return {'selfTest': True, 'checks': 5, 'passed': 5, 'wroteModel': False,
            'checksCovered': ['decoded pixels tolerate lossless PNG recompression', 'one changed pixel is detected',
                              'all 14 real V15 image replacements preserve non-image bytes', 'accessor byte mutation is rejected',
                              'animation JSON mutation is rejected'],
            'realBaselineImages': report['replacedImages'], 'realBaselinePreservedBufferViews': report['preservedNonImageBufferViews']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Verify and pack in memory without writing model/report')
    parser.add_argument('--self-test', action='store_true', help='Test pixels and protected V15 replacement entirely in memory')
    args = parser.parse_args()
    if not args.self_test and not MODEL.is_file():
        print(json.dumps({'status': 'awaiting-export', 'model': shared.rel(MODEL)})); return 2
    cache = cached_textures()
    if args.self_test:
        print(json.dumps(self_test(cache), indent=2)); return 0
    source = MODEL.read_bytes()
    output, result = compress(source, cache)
    require(sha(MODEL.read_bytes()) == sha(source), 'Source GLB changed during compression')
    for item in cache.values():
        record = item['record']
        require(sha((ROOT / record['source']).read_bytes()) == record['sourceSha256'], 'Protected PNG changed during compression')
        require(sha((ROOT / record['path']).read_bytes()) == record['sha256'], 'Protected KTX2 changed during compression')
    report = {'complete': True, 'usageStatus': 'experimental/non-active',
              'method': 'Reuse existing V15 UASTC/Zstd KTX2 only after exact decoded RGBA8 pixel SHA match; no encoder is invoked.',
              'source': shared.rel(MODEL), 'output': shared.rel(OUTPUT), 'compressionManifest': shared.rel(MANIFEST),
              'sourceGlbUnchanged': True, 'protectedV15AndTexturesUnchanged': True, **result}
    if not args.dry_run:
        pending = OUTPUT.with_name(OUTPUT.name + '.tmp')
        pending.write_bytes(output)
        require(sha(MODEL.read_bytes()) == sha(source), 'Source changed before committing output')
        pending.replace(OUTPUT)
        shared.atomic_json(REPORT, report)
    print(json.dumps({key: value for key, value in report.items() if key not in {'images', 'preservedBufferViewSha256'}}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, KeyError, ValueError) as error:
        print(json.dumps({'complete': False, 'error': str(error)}), file=sys.stderr)
        sys.exit(1)
