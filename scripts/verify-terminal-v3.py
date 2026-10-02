#!/usr/bin/env python3
"""Compare expanded V2/V3 triangle corners and animation data despite new UV seams."""
import collections
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('glb', ROOT / 'scripts/compress-works-gallery-v5.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def load(name):
    blob = (ROOT / 'public/models' / name).read_bytes()
    doc, chunks = g.parse_glb(blob)
    return doc, next(data for kind, data in chunks if kind == g.BIN_CHUNK), blob


def accessor(doc, binary, index):
    a = doc['accessors'][index]
    assert 'sparse' not in a and not a.get('normalized')
    view = doc['bufferViews'][a['bufferView']]
    fmt, size = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2), 5121: ('B', 1)}[a['componentType']]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    offset, stride = view.get('byteOffset', 0) + a.get('byteOffset', 0), view.get('byteStride', size * width)
    result = [struct.unpack_from('<' + fmt * width, binary, offset + row * stride) for row in range(a['count'])]
    assert all(math.isfinite(n) for row in result for n in row)
    return result


def mesh_corners(doc, binary, mesh):
    # Canonicalize cyclic starting corners and triangle order, but preserve winding.
    triangles = []
    for primitive in mesh['primitives']:
        assert primitive.get('mode', 4) == 4
        attrs = [accessor(doc, binary, primitive['attributes'][semantic]) for semantic in ['POSITION', 'NORMAL', 'TEXCOORD_0']]
        indices = [row[0] for row in accessor(doc, binary, primitive['indices'])]
        material = doc['materials'][primitive['material']]['name']
        for at in range(0, len(indices), 3):
            corners = tuple(tuple(value for attr in attrs for value in attr[i]) for i in indices[at:at + 3])
            triangles.append((material, min(corners, corners[1:] + corners[:1], corners[2:] + corners[:2])))
    return collections.Counter(triangles)


def animation(doc, binary):
    records = []
    for clip in doc['animations']:
        for channel in clip['channels']:
            sampler = clip['samplers'][channel['sampler']]
            records.append((clip['name'], doc['nodes'][channel['target']['node']]['name'], channel['target']['path'],
                            sampler.get('interpolation', 'LINEAR'), accessor(doc, binary, sampler['input']), accessor(doc, binary, sampler['output'])))
    return sorted(records)


def main():
    from PIL import Image
    a, ab, old = load('welcome-terminal-v2.glb')
    b, bb, new = load('welcome-terminal-v3.glb')
    c, cb, compressed = load('welcome-terminal-v3-compressed.glb')
    assert a['nodes'] == b['nodes'] == c['nodes'], 'Names, hierarchy, TRS or component IDs changed'
    am, bm = {m['name']: m for m in a['meshes']}, {m['name']: m for m in b['meshes']}
    assert set(am) == set(bm) and len(bm) == 27
    total = 0
    for name in am:
        ac, bc = mesh_corners(a, ab, am[name]), mesh_corners(b, bb, bm[name])
        assert ac == bc, f'Expanded positions/normals/UV0/winding/material assignment differs: {name}'
        total += sum(ac.values())
    assert animation(a, ab) == animation(b, bb) == animation(c, cb), 'Native unfold clip changed'
    mapped = []
    for material in b['materials']:
        if material['name'] == 'TERMINAL_OriginalScreenArtwork': continue
        pbr = material['pbrMetallicRoughness']
        for info in [pbr['baseColorTexture'], pbr['metallicRoughnessTexture'], material['normalTexture']]:
            assert info['texCoord'] == 1
        mapped.append(material['name'])
    assert len(mapped) == 6
    pixels = Image.open(ROOT / 'public/textures/welcome-terminal-v3/basecolor.png').convert('RGB')
    width, height = pixels.size
    assert (width, height) == (2048, 2048)
    coverage, palette = {}, collections.defaultdict(list)
    for mesh in b['meshes']:
        for p in mesh['primitives']:
            if b['materials'][p['material']]['name'] in mapped:
                uv = accessor(b, bb, p['attributes']['TEXCOORD_1'])
                assert len(uv) == b['accessors'][p['attributes']['POSITION']]['count']
                assert all(-1e-6 <= x <= 1.000001 for row in uv for x in row)
                indices = [row[0] for row in accessor(b, bb, p['indices'])]
                samples = []
                for at in range(0, len(indices), 3):
                    va, vb, vc = [uv[i] for i in indices[at:at + 3]]
                    area = abs((vb[0]-va[0])*(vc[1]-va[1])-(vc[0]-va[0])*(vb[1]-va[1])) / 2
                    u, v = [(va[axis]+vb[axis]+vc[axis])/3 for axis in range(2)]
                    color = pixels.getpixel((min(width-1, max(0, int(u*width))), min(height-1, max(0, int(v*height)))))
                    samples.append((area, color))
                name = b['materials'][p['material']]['name']
                palette[name].extend(samples)
                node_name = next(n['name'] for n in b['nodes'] if n.get('mesh') == b['meshes'].index(mesh))
                coverage[node_name] = sum(area for area, color in samples if sum(color) > 5) / sum(area for area, _ in samples)
    assert coverage['terminal.v2.dial.ivoryceramic'] > .99, 'Dial ceramic engravings fall outside baked texels'
    palette_samples = {}
    for name, samples in palette.items():
        average = [sum(area*color[ch] for area, color in samples)/sum(area for area, _ in samples) for ch in range(3)]
        old_color = next(m for m in a['materials'] if m['name'] == name)['pbrMetallicRoughness']['baseColorFactor']
        reference = [(x*12.92 if x <= .0031308 else 1.055*x**(1/2.4)-.055)*255 for x in old_color[:3]]
        assert max(abs(x-y) for x, y in zip(average, reference)) < 9, f'Baked palette changed: {name}'
        palette_samples[name] = {'uvAreaWeightedBakedSRGB8': average, 'originalSRGB8': reference}
    old_screen = a['materials'][next(i for i, m in enumerate(a['materials']) if m['name'] == 'TERMINAL_OriginalScreenArtwork')]
    new_screen = b['materials'][next(i for i, m in enumerate(b['materials']) if m['name'] == 'TERMINAL_OriginalScreenArtwork')]
    def screen_bytes(doc, binary, material):
        image = doc['images'][doc['textures'][material['emissiveTexture']['index']]['source']]
        return g.view_bytes(doc, binary, doc['bufferViews'][image['bufferView']])
    assert screen_bytes(a, ab, old_screen) == screen_bytes(b, bb, new_screen)
    source = ROOT / 'assets/blender/welcome-terminal-v2.blend'
    assert g.sha(source.read_bytes()) == '0461e14ab58d2fb6d11cd31f068fb6f51d4b2e2e07b3c931580c275ebc0eaa53'
    compression = json.loads((ROOT / 'assets/blender/welcome-terminal-v3-compression.json').read_text())
    assert compression['complete'] and compression['sourceSha256'] == g.sha(new) and compression['sha256'] == g.sha(compressed)
    report = {'complete': True, 'meshCount': len(bm), 'triangles': total, 'nodes': len(b['nodes']),
              'exactExpandedPositionsNormalsUV0WindingMaterialAssignments': True,
              'exactHierarchyTransformsAndComponentIDs': True, 'exactNativeAnimationSamples': True,
              'addedSurfaceUVForPBR': True, 'bodyMaterialsWithThreeUV1Maps': mapped,
              'actualPNGPaletteSamples': palette_samples, 'dialCeramicUVAreaCoverage': coverage['terminal.v2.dial.ivoryceramic'],
              'screenArtworkByteIdentical': True, 'v2SourceBlendUnchanged': True,
              'raw': {'path': 'public/models/welcome-terminal-v3.glb', 'sha256': g.sha(new), 'bytes': len(new)},
              'runtime': {'path': 'public/models/welcome-terminal-v3-compressed.glb', 'sha256': g.sha(compressed), 'bytes': len(compressed)},
              'scope': 'CPU data audit; real Blender bakes executed through file-targeted MCP. Website GPU appearance requires browser validation.'}
    g.atomic_json(ROOT / 'docs/validation/terminal-v3-material-data.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__': main()
