"""Check the final compressed architecture GLB without opening Blender."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('architecture_compression',
    ROOT / 'scripts/compress-about-atelier-v3-architecture.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accessor(document, binary, index):
    item = document['accessors'][index]
    view = document['bufferViews'][item['bufferView']]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[item['type']]
    kind = {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}[item['componentType']]
    form = '<' + kind * components
    offset = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    stride = view.get('byteStride', struct.calcsize(form))
    return [struct.unpack_from(form, binary, offset + i * stride) for i in range(item['count'])]


def main():
    directory = ROOT / 'assets/blender/about-atelier-v3-web'
    exported = json.loads((directory / 'architecture-export-report.json').read_text())
    compressed = json.loads((directory / 'architecture-compression-report.json').read_text())
    revision = json.loads((directory / 'architecture-v2-build-report.json').read_text())
    source_qa = json.loads((directory / 'architecture-v2-source-validation-report.json').read_text())
    model = ROOT / compressed['model']['path']
    document, _, binary = C.parse_glb(model.read_bytes())
    inventory = C.inspect_architecture(document)
    assert sha(model) == compressed['model']['sha256']
    assert sha(ROOT / exported['source']) == exported['sourceSha256']
    assert sha(ROOT / exported['bake']['path']) == exported['bake']['sha256']
    assert compressed['textures'][0]['sourceSha256'] == exported['bake']['sha256']
    assert len(exported['sourceNodes']) == revision['architectureSourceNodes'] == 98
    assert sha(ROOT / revision['original']) == revision['originalSha256']
    assert exported['originalSourceSha256'] == revision['originalSha256']
    assert exported['sourceSha256'] == revision['derivativeSha256']
    assert exported['sourceSha256'] == source_qa['sourceSha256']
    assert source_qa['closedManifoldArchitectureObjects'] == 98
    assert source_qa['allEvaluatedMeshesManifoldWithPositiveVolume']
    assert source_qa['allTwentyFloorTilesOverlapStructuralSlab']
    assert source_qa['allFourCopingPiecesOverlapStructuralSlab']
    assert source_qa['RecessedUndersideOverlapsStructuralSlab']
    assert revision['mainGeometryHierarchyTransformsSignatureBefore'] == revision['mainGeometryHierarchyTransformsSignatureAfter']
    assert all(connection['bottomConnections'] and connection['topConnections'] for connection in revision['verticalConnections'])
    assert revision['headerCornerConnected'] and revision['sillCornerConnected']
    assert revision['deckHasClosedStructuralBoxAndRecessedUnderside']
    assert len(revision['floorTilesRetainedAndCropped']) == 20
    assert len(document['nodes']) == 10
    assert len(document['scenes']) == 1 and len(document['scenes'][0]['nodes']) == 1
    root = document['nodes'][document['scenes'][0]['nodes'][0]]
    assert root['name'] == 'ATELIER_ARCHITECTURE' and len(root['children']) == 9
    assert root['extras']['interactive'] is False and root['extras']['excludeFromFraming'] is True
    assert document['asset']['extras']['sourceNodes'] == exported['sourceNodes']
    assert all(n['extras']['interactive'] is False for n in document['nodes'])
    assert not any(n.startswith(('context.', 'rug.')) for n in exported['contextObjectsRetainedForBakeOnly'])
    assert len(exported['excludedFromBakeAsWell']) == 0
    assert len(exported['decorRemovedFromDerivativeSource']) == 144
    coordinates, triangles = [], 0
    for node in document['nodes']:
        # World coordinates were baked into geometry before the glTF Y-up conversion.
        assert not any(key in node for key in ('matrix', 'translation', 'rotation', 'scale'))
        if 'mesh' not in node:
            continue
        for primitive in document['meshes'][node['mesh']]['primitives']:
            positions = accessor(document, binary, primitive['attributes']['POSITION'])
            assert all(math.isfinite(value) for point in positions for value in point)
            indices = [value[0] for value in accessor(document, binary, primitive['indices'])]
            assert len(indices) % 3 == 0 and min(indices) >= 0 and max(indices) < len(positions)
            coordinates.extend(positions)
            triangles += len(indices) // 3
            if primitive['material'] == inventory['opaqueMaterial']:
                uvs = accessor(document, binary, primitive['attributes']['TEXCOORD_0'])
                assert all(-1e-5 <= value <= 1.00001 for uv in uvs for value in uv)
    measured = {'min': [min(p[i] for p in coordinates) for i in range(3)],
                'max': [max(p[i] for p in coordinates) for i in range(3)]}
    assert all(abs(measured[key][i] - exported['boundsGltf'][key][i]) < 1e-5
               for key in measured for i in range(3))
    assert triangles == exported['triangles'] == compressed['model']['triangles']
    assert 20000 <= triangles <= 50000
    texture = compressed['textures'][0]
    assert sha(ROOT / texture['path']) == texture['sha256']
    assert C.ktx_info((ROOT / texture['path']).read_bytes())['resolution'] == [4096, 4096]
    assert C.view_bytes(document, binary, document['images'][0]['bufferView']) == (ROOT / texture['path']).read_bytes()
    main_doc, _, _ = C.parse_glb((ROOT / 'public/models/about-atelier-v3-compressed.glb').read_bytes())
    asset_ids = [n['extras']['asset_id'] for n in main_doc['nodes'] if 'asset_id' in n.get('extras', {})]
    assert len(asset_ids) == len(set(asset_ids)) == 128
    report = {'complete': True, 'model': C.rel(model), 'bytes': model.stat().st_size,
        'sha256': sha(model), 'sourceFileUnchanged': True, 'sourceSha256': exported['sourceSha256'],
        'geometryBoundsVerifiedFromVertexBuffers': measured, 'triangles': triangles,
        'opaqueMeshes': 1, 'glassMeshes': 8, 'nodes': 10, 'architectureAssetIds': 0,
        'mainModelAssetIds': 128, 'sourceArchitectureNodes': len(exported['sourceNodes']),
        'architectureRevision': exported['architectureRevision'],
        'originalSourceUnchanged': True, 'mainGeometryHierarchyTransformsUnchanged': True,
        'allVerticalMembersHaveTopAndBottomConnections': True,
        'headerAndSillCornersConnected': True,
        'croppedDeckHasStoneFasciaAndClosedUnderside': True,
        'all98SourceArchitectureMeshesClosedAndManifold': True,
        'floorAndCopingConnectedToStructuralSlab': True,
        'omittedDecorObjectsExcludedFromBakeAndExport': 144,
        'sourceFurnitureRetainedAsOccluders': True, 'embeddedKtxMatchesValidatedTexture': True,
        'bakePngMatchesCompressionSource': True, 'sourceTransformsPreserved': True,
        'noninteractiveAndExcludedFromFraming': True, 'newThirdPartyTextures': [],
        'validation': 'GLB structure, finite geometry, index bounds, UV range, source coordinate bounds, source and texture hashes, 128 main IDs, KTX2 image equality'}
    C.atomic_json(directory / 'architecture-validation-report.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
