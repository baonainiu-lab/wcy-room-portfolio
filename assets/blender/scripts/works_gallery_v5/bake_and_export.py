"""V5 64-sample day/night rebake using unchanged V4 geometry/UV pipeline."""
import fcntl, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bake=module('gallery_v4_bake',ROOT/'assets/blender/scripts/works_gallery_v4/bake_gallery.py')
bake.PREPARED=ROOT/'assets/blender/works-gallery-bake-v5.blend'
bake.OUT=ROOT/'public/textures/works-gallery-v5';bake.REPORTS=ROOT/'assets/blender/works-gallery-v5'
for state in ('day','night'):
    for atlas in range(4):
        print('V5_BAKE_START',state,atlas,flush=True)
        with open('/tmp/room-portfolio-blender-gpu.lock','a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            bake.bake_state(state,[atlas],prepared_path=bake.PREPARED,output_directory=bake.OUT)
        print('V5_BAKE_COMPLETE',state,atlas,flush=True)
exporter=module('gallery_v4_export',ROOT/'assets/blender/scripts/works_gallery_v4/export_gallery.py')
report=exporter.export(prepared_path=bake.PREPARED,output_path=ROOT/'public/models/works-gallery-v5.glb',textures_directory=bake.OUT,report_path=bake.REPORTS/'export-report.json')
print('V5_EXPORT_COMPLETE',json.dumps({k:report[k] for k in ('model','bytes','sha256','triangles','materials')}),flush=True)
