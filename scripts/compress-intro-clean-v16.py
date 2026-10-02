#!/usr/bin/env python3
"""Encode only the three V16 clean intro maps using the existing KTX contract."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v16_intro_compression',ROOT/'scripts/compress-intro-clean-v1.py')
pipeline=importlib.util.module_from_spec(spec);spec.loader.exec_module(pipeline)
pipeline.OUT=ROOT/'public/textures/intro-clean-v16';pipeline.REPORT=pipeline.OUT/'compression.json'

def validate_sources():
    prepared=ROOT/'assets/blender/orbital-dual-bake-v16.blend'
    digest=hashlib.sha256(prepared.read_bytes()).hexdigest()
    validation=json.loads((pipeline.OUT/'validation.json').read_text())
    assert validation['complete'] and validation['sourceSha256']==digest
    assert validation['samples']==96 and validation['slots']==[0,1,8]
    assert validation['oldIntroV1Untouched'] and validation['receiverPipelineAndLightingUnchanged']
    for name,slots in [('SOURCE.json',{0,8}),('atlas-1-SOURCE.json',{1})]:
        record=json.loads((pipeline.OUT/name).read_text())
        assert record['complete'] and record['sourceBlend']==str(prepared.relative_to(ROOT))
        assert record['sourceBlendSha256']==digest and record['bake']['samples']==96
        assert record['geometryUVUnchanged'] and record['protectedFilesUnchanged']
        assert {row['atlas'] for row in record['atlases']}==slots
        assert len(record['atlases'])==len(slots)
        for row in record['atlases']:
            assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    return digest

if __name__=='__main__':
    prepared_sha=validate_sources()
    pipeline.main()
    report=json.loads(pipeline.REPORT.read_text())
    assert validate_sources()==prepared_sha
    report['authoringScript']='scripts/compress-intro-clean-v16.py'
    report['inheritedEncoderScript']='scripts/compress-intro-clean-v1.py'
    report['preparedSha256']=prepared_sha
    pipeline.shared.atomic_json(pipeline.REPORT,report)
