"""Verify the V13 lighting export did not alter V12 geometry, UVs or day maps."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_glb(revision):
    blob = (ROOT / f'public/models/orbital-atelier-v{revision}.glb').read_bytes()
    size = struct.unpack_from('<I', blob, 12)[0]
    return json.loads(blob[20:20 + size]), blob[28 + size:]


def accessor_hash(document, binary, index):
    accessor = document['accessors'][index]
    assert 'sparse' not in accessor
    view = document['bufferViews'][accessor['bufferView']]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
    sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    width = components[accessor['type']] * sizes[accessor['componentType']]
    stride = view.get('byteStride', width)
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    digest = hashlib.sha256()
    for item in range(accessor['count']):
        start = offset + item * stride
        digest.update(binary[start:start + width])
    return [accessor['count'], accessor['type'], accessor['componentType'], digest.hexdigest()]


def surface_signature(document, binary):
    result = {}
    for mesh in document['meshes']:
        result[mesh['name']] = [{
            'attributes': {key: accessor_hash(document, binary, index)
                           for key, index in primitive['attributes'].items()},
            'indices': accessor_hash(document, binary, primitive['indices']),
            'mode': primitive.get('mode', 4),
        } for primitive in mesh['primitives']]
    return result


def hierarchy_signature(document):
    nodes = document['nodes']
    result = {}
    for node in nodes:
        result[node['name']] = {
            'asset_id': node.get('extras', {}).get('asset_id'),
            'children': sorted(nodes[index]['name'] for index in node.get('children', [])),
            'matrix': node.get('matrix'),
            'translation': node.get('translation'),
            'rotation': node.get('rotation'),
            'scale': node.get('scale'),
        }
    return result


def run():
    previous, old_binary = load_glb(12)
    current, new_binary = load_glb(13)
    old_surfaces = surface_signature(previous, old_binary)
    new_surfaces = surface_signature(current, new_binary)
    assert old_surfaces == new_surfaces, 'A geometry, UV or vertex attribute changed'
    assert hierarchy_signature(previous) == hierarchy_signature(current), 'The object hierarchy or transform changed'
    old_maps = ROOT / 'public/textures/lighting-v12'
    new_maps = ROOT / 'public/textures/lighting-v13'
    day_hashes = {}
    for path in sorted(old_maps.glob('*day*.png')):
        original = hashlib.sha256(path.read_bytes()).hexdigest()
        assert original == hashlib.sha256((new_maps / path.name).read_bytes()).hexdigest(), path.name
        day_hashes[path.name] = original
    assert len(day_hashes) == 9
    assert (old_maps / 'window-night.png').read_bytes() == (new_maps / 'window-night.png').read_bytes()
    report = {
        'passed': True, 'previousRevision': 12, 'lightingRevision': 13,
        'geometryUvNormalsExact': True, 'hierarchyAndTransformsExact': True,
        'meshCount': len(new_surfaces), 'nodeCount': len(current['nodes']),
        'dayMapCount': len(day_hashes), 'daySHA256': day_hashes,
        'windowNightUnchanged': True,
        'scope': 'Exact decoded accessor bytes and hierarchy; 9 day PNGs and night window are byte-identical. Light quality is reviewed separately.'
    }
    destination = ROOT / 'renders/night-warm-v13-continuity-check.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'daySHA256'}, indent=2))


if __name__ == '__main__':
    run()
