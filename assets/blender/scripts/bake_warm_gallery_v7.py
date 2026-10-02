"""Run through Blender MCP on orbital-atelier-v6.blend."""
from pathlib import Path
BAKE_SPEC = {
    'revision':7, 'script':'warm_gallery_v7.py', 'collection':'WARM_GALLERY_V7',
    'source':'orbital-atelier-v7.blend', 'scene':'WEB_WARM_GALLERY_V7',
    'model':'orbital-warm-gallery-v7.glb', 'texture':'room-warm-gallery-v7.png',
    'record':'warm-gallery-v7', 'atlas':3072,
}
exec(compile((Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio/assets/blender/scripts/bake_enrichment_v5.py')).read_text(), 'bake_enrichment_v5.py', 'exec'))
