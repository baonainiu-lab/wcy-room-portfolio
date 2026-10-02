#!/usr/bin/env python3
"""Verify runtime texture bindings and independent assets against the actual GLB."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compression', ROOT / 'scripts/compress-works-gallery.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
report = json.loads((ROOT / 'assets/blender/texture-precision-v15-compression.json').read_text())
assert report['complete']
blob = (ROOT / report['model']['path']).read_bytes()
assert hashlib.sha256(blob).hexdigest() == report['model']['sha256']
doc, chunks = module.parse_glb(blob)
binary = next(data for kind, data in chunks if kind == module.BIN_CHUNK)
ids = [n['extras']['asset_id'] for n in doc['nodes'] if n.get('extras', {}).get('asset_id')]
assert len(ids) == len(set(ids)) == 95
triangles = sum(doc['accessors'][p['indices']]['count'] // 3 for m in doc['meshes'] for p in m['primitives'])
assert triangles == json.loads((ROOT / 'assets/blender/dual-lighting-v15-export-report.json').read_text())['triangles']
assert len(report['textures']) == 27
sizes = {}
for material in doc['materials']:
    texture_index = material.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
    if texture_index is None:
        continue
    texture = doc['textures'][texture_index]
    image = doc['images'][texture['extensions']['KHR_texture_basisu']['source']]
    assert image['mimeType'] == 'image/ktx2'
    info = module.ktx_info(module.view_bytes(doc, binary, doc['bufferViews'][image['bufferView']]))
    sizes[material['name']] = info['resolution']
assert sizes['WEB8_WINDOW_CITY'] == [3072, 1344]
assert sizes['WEB8_IMAGE_MAT_Rendered_3D_ScreenArtwork'] == [2880, 1200]
assert len(sizes) == 14
for record in report['textures']:
    data = (ROOT / record['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    assert module.ktx_info(data)['resolution'] == record['resolution']
    source = (ROOT / record['source']).read_bytes()
    assert hashlib.sha256(source).hexdigest() == record['sourceSha256']
    assert list(struct.unpack_from('>II', source, 16)) == record['resolution']
old = ROOT / 'public/models/orbital-atelier-v14.glb'
assert hashlib.sha256(old.read_bytes()).hexdigest() == 'a933ce1ba865c5ad5293e11bfac51ad082f8c1522ff828ad89d45aa17bd5e232'
old_doc, _ = module.parse_glb(old.read_bytes())
old_ids = {n['extras']['asset_id'] for n in old_doc['nodes'] if n.get('extras', {}).get('asset_id')}
assert set(ids) == old_ids
repair = json.loads((ROOT / 'assets/blender/window-clearance-v15-repair.json').read_text())
assert repair['allWindowTowerIntersectionsRemoved']
assert len(repair['bvhChecks']) == 6 and all(check['triangleIntersections'] == 0 for check in repair['bvhChecks'])
result = {'passed': True, 'model': report['model'], 'independentIds': len(ids),
          'triangles': triangles, 'mappedMaterials': sizes, 'verifiedTextures': 27,
          'previousV14Unchanged': True, 'windowRepairReport': 'assets/blender/window-clearance-v15-repair.json',
          'textureRgba8MipBytes': report['rgba8MipBytes'], 'textureAstcOrBc7MipBytes': report['astcOrBc7MipBytes']}
output = ROOT / 'docs/validation/room-v15-assets.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
