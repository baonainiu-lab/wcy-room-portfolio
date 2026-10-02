"""Read-only source, offline bake fallback for the MCP CLI's fixed 120s limit.

Authoring, source inspection, material edits and reviews were done through MCP.
This launcher is only for already-approved expensive bakes. Every job opens the
same immutable prepared file in a fresh background Blender, serially. It never
connects to or modifies the interactive Blender project.
"""
import argparse,hashlib,json,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'assets/blender/orbital-dual-bake-v19.blend'
EXPECTED='45e258c586f5bc46203ca1d3ff6be14cfde72fcc28a40ec919040fcee9a9cd64'
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'
AUDIT=ROOT/'assets/blender/room-v19-offline-bake-jobs'
SIZES=[4096]*6+[3072,2048,3072,4096,4096,3072,1024]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.pending.json');temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(path)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['day','night','intro','probes','export']);parser.add_argument('--gpu-denoise',action='store_true');args=parser.parse_args()
    assert sha(SOURCE)==EXPECTED
    if args.stage in ('day','night'):
        jobs=[(f'{args.stage}-{slot}',f"p.bake_light_current({slot},{args.stage!r},samples=96)",ROOT/f'public/textures/lighting-v19/{args.stage}-{slot}-manifest.json',slot) for slot in range(13)]
    elif args.stage=='intro':
        jobs=[(f'intro-{slot}',f"p.bake_light_current({slot},'day',intro=True,samples=96)",ROOT/f'public/textures/intro-clean-v19/day-{slot}-manifest.json',slot) for slot in (0,1,8)]
    elif args.stage=='probes':
        jobs=[(f'reflection-{state}',f'p.reflection_current({state!r},width=2048)',ROOT/f'public/textures/lighting-v19/reflection-{state}.json',None) for state in ('day','night')]
    else:jobs=[('export','p.export_current()',ROOT/'assets/blender/dual-lighting-v19-export-report.json',None)]
    AUDIT.mkdir(parents=True,exist_ok=True);progress=AUDIT/f'{args.stage}-progress.json';completed=[]
    for name,expression,manifest,slot in jobs:
        assert sha(SOURCE)==EXPECTED
        if manifest.exists() and args.stage!='export':
            row=json.loads(manifest.read_text());path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
            valid=row.get('sourceSha256')==EXPECTED and path.exists() and sha(path)==row['sha256']
            if slot is not None:valid=valid and row['samples']==96 and row['dimensions']==[SIZES[slot]]*2
            if valid:
                completed.append({'job':name,'status':'preserved_verified_existing'});write(progress,{'stage':args.stage,'status':'running','completed':completed,'sourceSha256':EXPECTED});print(f'PRESERVED {name}',flush=True);continue
            raise RuntimeError(f'Stale or incomplete manifest {manifest}; never overwrite silently')
        execution_override=(
          "denoise_execution=[]\n"
          "def enable_gpu_oidn(scene):\n"
          "    settings=scene.cycles\n"
          "    fields=('denoiser','denoising_quality','denoising_prefilter','denoising_input_passes','denoising_use_gpu')\n"
          "    before={key:getattr(settings,key) for key in fields}\n"
          "    assert before['denoiser']=='OPENIMAGEDENOISE' and before['denoising_quality']=='HIGH'\n"
          "    prefs=bpy.context.preferences.addons['cycles'].preferences\n"
          "    assert prefs.has_oidn_gpu_devices(), 'GPU OIDN not available for configured device'\n"
          "    settings.denoising_use_gpu=True\n"
          "    after={key:getattr(settings,key) for key in fields}\n"
          "    assert {k:v for k,v in before.items() if k!='denoising_use_gpu'}=={k:v for k,v in after.items() if k!='denoising_use_gpu'}\n"
          "    denoise_execution.append({'before':before,'after':after,'supported':True,'computeBackend':prefs.compute_device_type})\n"
          "    return scene\n"
          "original_configure=p.configure_current\n"
          "original_intro=p.configure_intro_current\n"
          "p.configure_current=lambda state:enable_gpu_oidn(original_configure(state))\n"
          "p.configure_intro_current=lambda slot:enable_gpu_oidn(original_intro(slot))\n"
        ) if args.gpu_denoise else "denoise_execution=[]\n"
        code=("import sys,json,hashlib\nfrom pathlib import Path\n"
          +f"sys.path.insert(0,{str(ROOT/'assets/blender/scripts')!r})\n"
          +"import bpy\nimport photoreal_materials_v19 as p\n"
          +f"assert p.sha(bpy.data.filepath)=={EXPECTED!r}\n"
          +execution_override
          +f"r={expression}\n"
          +"r['execution']={'method':'offline Blender CLI fallback','reason':'MCP file-targeted CLI hard timeout 120 seconds; same approved source and bake recipe','authoringAndReview':'Blender MCP','blenderVersion':bpy.app.version_string,'denoiseExecutionOverride':denoise_execution}\n"
          +f"p.write(Path({str(manifest)!r}),r)\n"
          +f"assert p.sha(bpy.data.filepath)=={EXPECTED!r}\n"
          +"print('ROOM_V19_JOB_COMPLETE '+json.dumps(r),flush=True)\n")
        log=AUDIT/(name+'.log');started=time.time();write(progress,{'stage':args.stage,'status':'running','job':name,'startedUnix':started,'sourceSha256':EXPECTED,'completed':completed,'log':str(log)})
        print(f'START {name}',flush=True)
        try:
            with log.open('w') as output:
                result=subprocess.run([BLENDER,'--background',str(SOURCE),'--python-exit-code','1','--python-expr',code],stdout=output,stderr=subprocess.STDOUT,timeout=1800)
            assert result.returncode==0,f'Blender exit {result.returncode}'
            assert 'ROOM_V19_JOB_COMPLETE ' in log.read_text(), 'Missing completion marker'
            row=json.loads(manifest.read_text());assert row.get('sourceSha256',row.get('preparedSha256'))==EXPECTED
            assert sha(SOURCE)==EXPECTED
            completed.append({'job':name,'status':'complete','wallSeconds':round(time.time()-started,2),'manifest':str(manifest),'manifestSha256':sha(manifest),'log':str(log)})
            write(progress,{'stage':args.stage,'status':'running','completed':completed,'sourceSha256':EXPECTED})
            print(f'COMPLETE {name} {round(time.time()-started,2)}s',flush=True)
        except Exception as error:
            write(progress,{'stage':args.stage,'status':'failed','job':name,'error':str(error),'completed':completed,'sourceSha256':EXPECTED,'log':str(log)})
            raise
    write(progress,{'stage':args.stage,'status':'complete','completed':completed,'sourceSha256':EXPECTED,'launcherSha256':sha(__file__)})
    print(f'STAGE_COMPLETE {args.stage}',flush=True)

if __name__=='__main__':main()
