"""Run through Blender MCP on orbital-atelier-v5.blend. Bake the physical dock."""
from pathlib import Path
BAKE_SPEC = {
    'revision':6, 'script':'exterior_dock_v6.py', 'collection':'EXTERIOR_DOCK_V6',
    'source':'orbital-atelier-v6.blend', 'scene':'WEB_EXTERIOR_V6',
    'model':'orbital-exterior-v6.glb', 'texture':'room-exterior-v6.png',
    'record':'exterior-v6',
}
exec(compile((Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio/assets/blender/scripts/bake_enrichment_v5.py')).read_text(), 'bake_enrichment_v5.py', 'exec'))
