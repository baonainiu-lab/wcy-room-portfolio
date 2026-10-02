"""Read-only checks of the exported geometry, interactive hierarchy and maps."""
import io, json, struct, hashlib, sys
from pathlib import Path
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[3]
revision = int(sys.argv[1]) if len(sys.argv) > 1 else 8
path = ROOT/f'public/models/orbital-atelier-v{revision}.glb'
blob = path.read_bytes()
magic, version, total = struct.unpack_from('<III', blob)
assert (magic, version, total) == (0x46546C67, 2, len(blob))
size = struct.unpack_from('<I', blob, 12)[0]
doc = json.loads(blob[20:20+size])
binary = blob[28+size:]
expected = json.loads((ROOT/f'assets/blender/dual-bake-v{revision}-preparation.json').read_text())
nodes = doc['nodes']
ids = [n.get('extras',{}).get('asset_id') for n in nodes]
actual_ids = [v for v in ids if v]
assert len(actual_ids) == len(set(actual_ids))
assert sorted(actual_ids) == sorted(expected['asset_ids'])
parents = {child:index for index, node in enumerate(nodes) for child in node.get('children',[])}
roots = []
for index, asset in enumerate(ids):
    if not asset or asset.startswith('environment.'):
        continue
    parent = parents.get(index)
    while parent is not None and not ids[parent]:
        parent = parents.get(parent)
    if parent is None:
        roots.append(asset)
assert len(roots) == 37
assert sum(not asset.startswith('environment.') for asset in actual_ids) == 93
required = {f'WEB8_LIGHTMAP_{i}' for i in range(8)} | {'WEB8_WINDOW_CITY'}
assert required.issubset({m['name'] for m in doc['materials']})
assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in doc['materials'])
textures = []
for state in ('day','night'):
    for index, resolution in enumerate([4096]*6+[3072,2048]):
        texture = ROOT/f'public/textures/lighting-v{revision}/{state}-{index}.png'
        with Image.open(texture) as image:
            assert image.size == (resolution,resolution)
            stats = ImageStat.Stat(image.resize((128,128)))
            assert max(stats.stddev) > 1, f'Blank map: {texture}'
        textures.append({'path':str(texture.relative_to(ROOT)), 'bytes':texture.stat().st_size,
                         'sha256':hashlib.sha256(texture.read_bytes()).hexdigest()})
for image in doc.get('images',[]):
    assert 'bufferView' in image, 'Night images must be embedded in the model.'
    view = doc['bufferViews'][image['bufferView']]
    start = view.get('byteOffset',0)
    with Image.open(io.BytesIO(binary[start:start+view['byteLength']])) as bitmap:
        bitmap.verify()
result = {'passed':True,'modelSHA256':hashlib.sha256(blob).hexdigest(),'modelBytes':len(blob),
          'interiorRoots':len(roots),'interiorIDs':93,'exteriorIDs':2,'embeddedImages':len(doc.get('images',[])),
          'externalBakedStates':textures}
(ROOT/f'renders/asset-validation-v{revision}.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:value for key,value in result.items() if key!='externalBakedStates'},indent=2))
