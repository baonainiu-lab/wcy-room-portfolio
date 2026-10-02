#!/usr/bin/env python3
"""Reuse the verified 12-atlas compression contract for material-only V16."""
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('room_v16_compression',ROOT/'scripts/compress-room-v15.py')
pipeline=importlib.util.module_from_spec(spec);spec.loader.exec_module(pipeline)
pipeline.TEX=ROOT/'public/textures/lighting-v16'
pipeline.MODEL=ROOT/'public/models/orbital-atelier-v16.glb'
pipeline.OUTPUT=ROOT/'public/models/orbital-atelier-v16-compressed.glb'
pipeline.REPORT=ROOT/'assets/blender/photoreal-materials-v16-compression.json'

def watch():
    """Encode only atomically recorded completed bakes while Cycles continues."""
    previous=pipeline.shared.read_json(pipeline.REPORT)
    records={f'{r["state"]}-{r["slot"]}':r for r in previous.get('textures',[])}
    started=time.monotonic()
    while time.monotonic()-started<10800:
        for state in ('day','night','static'):
            ready=['screen'] if state=='static' else ['window']
            manifest=pipeline.TEX/f'{state}-v16-manifest.json'
            if manifest.exists():
                for row in json.loads(manifest.read_text()).get('atlases',[]):
                    if pipeline.sha((ROOT/row['path']).read_bytes())==row['sha256']:ready.append(row['atlas'])
            for slot in ready:
                key=f'{state}-{slot}';old=records.get(key);record=pipeline.encode(state,slot,old)
                if record:
                    records[key]=record
                    if record!=old:pipeline.shared.atomic_json(pipeline.REPORT,{'complete':False,'textures':list(records.values())})
        export_report=ROOT/'assets/blender/dual-lighting-v16-export-report.json'
        if len(records)==27 and export_report.exists() and pipeline.MODEL.exists():
            exported=json.loads(export_report.read_text())
            if exported['sha256']==pipeline.sha(pipeline.MODEL.read_bytes()):
                sys.argv=[sys.argv[0]];pipeline.main();return
        time.sleep(3)
    raise TimeoutError('Room V16 bakes/export did not complete within three hours')

if __name__=='__main__':
    if '--watch' in sys.argv:watch()
    else:pipeline.main()
