#!/usr/bin/env python3
"""Verify the complete physical-material release before runtime activation."""
import hashlib,importlib.util,json,math,struct
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('room_geometry_check',ROOT/'scripts/verify-room-v16.py');geometry_check=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry_check)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads((ROOT/path).read_text())
def verify():
    prepared=read('assets/blender/photoreal-materials-v17-prepared.json');source=read('assets/blender/photoreal-materials-v17-source.json')
    for report in (prepared,source):
        assert report['complete'] and report['geometryBefore']==report['geometryAfter'] and report['bakeUvsNormalsUnchanged']
        assert sha(ROOT/report['source'])==report['sourceSha256'] and sha(ROOT/report['derivative'])==report['sha256']
    prepared_sha=prepared['sha256'];compression=read('assets/blender/photoreal-materials-v17-compression.json')
    assert compression['complete'] and compression['preparedSha256']==prepared_sha and len(compression['textures'])==54
    assert compression['codecRevision']=='linear-surface-v2-logrgb256'
    model=compression['model'];raw=ROOT/'public/models/orbital-atelier-v17.glb'
    assert sha(raw)==model['sourceSha256'] and sha(ROOT/model['path'])==model['sha256']
    v16,b16=geometry_check.read(ROOT/'public/models/orbital-atelier-v16.glb');v17,b17=geometry_check.read(raw);packed,bp=geometry_check.read(ROOT/model['path'])
    assert geometry_check.geometry(v16,b16)==geometry_check.geometry(v17,b17)==geometry_check.geometry(packed,bp)
    assert geometry_check.hierarchy(v16)==geometry_check.hierarchy(v17)==geometry_check.hierarchy(packed)
    for row in compression['textures']:
        assert sha(ROOT/row['source'])==row['sourceSha256'] and sha(ROOT/row['path'])==row['sha256']
        if row['state'] not in ('static',) and row['slot']!='window':
            assert row['transferFunction']=='linear' and row['targetType']=='RGBA' and not row['premultipliedAlpha']
            assert row['mipLevels']==int(math.floor(math.log2(max(row['dimensions']))))+1
            if row['state'] in ('day','night','intro'):
                assert row['kind']=='logrgb32-k256' and row['codecRevision']=='linear-surface-v2-logrgb256'
                assert row['sourceEncoding']=='RGBM32' and row['encodedSource']['encoding']=='LogRGB32 k256 alpha1'
                assert sha(row['encodedSource']['path'])==row['encodedSource']['sha256']
                with Image.open(row['encodedSource']['path']) as image:
                    assert image.mode=='RGBA' and image.getextrema()[3]==(255,255)
                    assert list(image.size)==row['dimensions']
    texture_records={r['key']:r for r in compression['textures']}
    manifests=[];highlight_audits=[]
    for state in ('day','night'):
        for slot in range(12):
            row=read(f'public/textures/lighting-v17/{state}-{slot}-manifest.json')
            assert row['sourceSha256']==prepared_sha and row['encoding']=='RGBM32' and row['glossyExcluded'] and row['samples']==96
            if row['valuesAboveRangeFraction']:
                assert state=='night','Daylight range overflow requires separate review'
                encoded=texture_records[f'night-{slot}'];overflow=row.get('hdrOutliers')
                if overflow:
                    expected_scale=2**math.ceil(math.log2(row['sourceRadianceMaximum']/32))
                    assert encoded['radianceScale']==expected_scale
                    assert encoded['radianceOverflow']['sha256']==overflow['sha256'] and sha(overflow['path'])==overflow['sha256']
                    assert sha(encoded['radianceOverflow']['sourceManifest'])==encoded['radianceOverflow']['sourceManifestSha256']
                    assert encoded['radianceOverflow']['restoredMaximum']==row['sourceRadianceMaximum']
                    assert encoded['radianceOverflow']['count']==overflow['count']
                    assert encoded['encodedSource']['radianceScale']==expected_scale
                else:raise AssertionError('Final release must preserve all over-range night radiance')
                audit=read(f'assets/blender/room-v17-highlight-audit-{slot}.json')
                assert audit['complete'] and audit['geometryUvsNormalsUnchanged']
                if not overflow:assert audit['notLargeArea']
                audit['webRadianceRecovered']=bool(overflow);audit['webRadianceScale']=encoded.get('radianceScale',1)
                assert audit['sourceSha256']==prepared_sha and audit['rawPngSha256']==row['sha256'] and audit['objectAttribution']
                if row.get('hdrOutliers'):assert sha(row['hdrOutliers']['path'])==row['hdrOutliers']['sha256']
                highlight_audits.append({k:v for k,v in audit.items() if k!='samples'})
            assert sha(row['path'])==row['sha256'];manifests.append(row)
    for slot in range(12):
        row=read(f'public/textures/lighting-v17/surface-{slot}-manifest.json')
        assert row['complete'] and row['sourceSha256']==prepared_sha and row['geometryUvNormalsUnchanged']
        assert row['decodedNormalsRenormalizedBeforeQuantization']
        for kind in ('normal','specular'):assert sha(row[kind]['path'])==row[kind]['sha256'] and row[kind]['valuesOutsideRangeBeyondFloatToleranceFraction']==0
    for slot in (0,1,8):
        row=read(f'public/textures/intro-clean-v17/day-{slot}-manifest.json')
        assert row['sourceSha256']==prepared_sha and row['encoding']=='RGBM32' and row['samples']==96 and row['cleanIntro'] and row['receiverOnly']
        assert sha(row['path'])==row['sha256'] and row['valuesAboveRangeFraction']==0
    probes=[read(f'public/textures/lighting-v17/reflection-{state}.json') for state in ('day','night')]
    for p in probes:assert p['sourceSha256']==prepared_sha and sha(ROOT/p['path'])==p['sha256'] and p['encoding']=='scene-linear Radiance HDR'
    for key in ('dimensions','cameraLocation','cameraEuler'):assert probes[0][key]==probes[1][key]
    legacy=read('assets/blender/photoreal-materials-v16-compression.json')
    assert sha(ROOT/legacy['model']['path'])==legacy['model']['sha256']
    for row in legacy['textures']:assert sha(ROOT/row['source'])==row['sourceSha256'] and sha(ROOT/row['path'])==row['sha256']
    export=read('assets/blender/dual-lighting-v17-export-report.json')
    assert export['nightRadianceScale']==compression['nightRadianceScale']
    actual_scales={str(r['slot']):r['radianceScale'] for r in compression['textures'] if r['state']=='night' and r.get('radianceScale',1)!=1}
    assert actual_scales==export['nightRadianceScale']
    for material in v17['materials']:
        if material['name'].startswith('WEB8_LIGHTMAP_'):
            slot=material['name'].rsplit('_',1)[1];extras=material['extras']
            assert extras['diffuseEncoding']=='LogRGB32 gain256' and extras['nightRadianceScale']==actual_scales.get(slot,1)
    result={'complete':True,'preparedSha256':prepared_sha,'model':model,'sourceGeometryUvsNormalsUnchanged':True,'geometryBuffersExactlyMatchV16':True,
        'idsHierarchyTransformsUnchanged':True,'legacyV16SourcesModelsTexturesUnchanged':True,'all54TextureHashesVerified':True,'linearMipsAndDataAlphaVerified':True,
        'nightRadianceScale':compression['nightRadianceScale'],'dayLinearRgbm32NoClipping':True,'nightHighlightAudits':highlight_audits,'allRecordedNightHdrOutliersRecovered':True,'webLogRgb32Gain256':True,'webLightAlphaConstantOne':True,'probeOrientationMatches':True,'mainAtlasPairs':12,'surfaceAtlasPairs':12,'introAtlases':3,'triangles':export['triangles'],
        'nodes':len(v17['nodes']),'materials':len(v17['materials']),'assetIds':len(export['componentIds']),'sourceMaterialCoverage':prepared['coverage'],
        'lightingBakeSeconds':round(sum(r['seconds'] for r in manifests),2),'glass':export['glass']}
    path=ROOT/'assets/blender/photoreal-materials-v17-validation.json';path.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(verify(),indent=2))
