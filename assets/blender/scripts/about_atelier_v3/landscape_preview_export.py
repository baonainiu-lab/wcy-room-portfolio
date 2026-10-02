"""Bake the source HDR's display transform into an unrotated web panorama."""
import hashlib
import json
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'assets/blender/about-atelier-v3.blend'
HDR = ROOT / 'assets/textures/about-atelier-v3/landscape/lake_pier_2k.hdr'
OUT = ROOT / 'public/textures/about-atelier-v3/landscape/lake-pier-day.png'
REPORT = ROOT / 'assets/blender/about-atelier-v3-web/landscape-preview-report.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert bpy.app.background
source_hash = sha(SOURCE)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
original_exposure = scene.view_settings.exposure
scene.view_settings.exposure = -.75
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
image = bpy.data.images.load(str(HDR), check_existing=False)
OUT.parent.mkdir(parents=True, exist_ok=True)
image.save_render(str(OUT), scene=scene)
assert sha(SOURCE) == source_hash
report = {'complete': True, 'source': str(HDR.relative_to(ROOT)), 'sourceSha256': sha(HDR),
    'modelSource': str(SOURCE.relative_to(ROOT)), 'modelSourceSha256': source_hash,
    'modelSourceUnchanged': True, 'output': str(OUT.relative_to(ROOT)), 'sha256': sha(OUT),
    'bytes': OUT.stat().st_size, 'resolution': list(image.size),
    'viewTransform': scene.view_settings.view_transform, 'look': scene.view_settings.look,
    'originalSceneExposure': original_exposure, 'displayExposure': -.75,
    'gamma': scene.view_settings.gamma, 'rotation': 'None; original equirectangular panorama pixel orientation',
    'runtime': 'sRGB map under NoToneMapping; apply original scene environment rotation at runtime; source HDR remains PMREM lighting',
    'license': 'Existing CC0-1.0 Poly Haven environment; no new imagery',
    'licenseManifest': 'assets/textures/about-atelier-v3/landscape/manifest.json'}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('ATELIER_LANDSCAPE_PREVIEW_DONE', json.dumps(report))
