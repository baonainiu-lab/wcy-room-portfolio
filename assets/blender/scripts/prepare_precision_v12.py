"""Prepare the measured V12 geometry profile from a fresh V12 source blend."""
import json
import sys
from pathlib import Path

ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
sys.path.insert(0, str(ROOT/'assets/blender/scripts'))
from prepare_dual_bake_v8 import prepare

def run():
    # The experimental UV reweighting loses visible platform detail. It is
    # intentionally disabled; this revision repairs geometry and rebakes the
    # existing 4K atlas strategy without increasing texture memory or draw calls.
    return prepare(
        output_path=ROOT/'assets/blender/orbital-dual-bake-v12.blend',
        report_path=ROOT/'assets/blender/dual-bake-v12-preparation.json',
        source_label='assets/blender/orbital-atelier-v12.blend', revision=12,
        precision_budgets={'room_static':None, 'terminal_panel_L':10000,
                           'terminal_panel_R':10000, 'glass_bonsai_terrarium':18000})

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
