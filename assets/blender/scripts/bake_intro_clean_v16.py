"""Run the established clean intro receiver bakes with V16 material shaders.

Only intro-clean-v16 outputs are written. V1 lights/receiver isolation and all
geometry/UVs are preserved; each actual GPU job takes the shared queue lock.
"""
import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from photoreal_materials_v16 import PREP,gpu_job,write,sha
from bake_geometry_fingerprint import fingerprints

def locked_bake(*args,**kwargs):
    with gpu_job('room-v16-clean-intro-bake'):return bpy.ops.object.bake(*args,**kwargs)

def locked_render(*args,**kwargs):
    with gpu_job('room-v16-clean-intro-preview'):return bpy.ops.render.render(*args,**kwargs)

def main():
    assert bpy.app.background
    checks=[]
    for name in ('bake_intro_clean_v1.py','bake_intro_clean_atlas1_v1.py'):
        bpy.ops.wm.open_mainfile(filepath=str(PREP));scene=bpy.data.scenes['WEB_DUAL_V8'];before=fingerprints(scene,include_shading=True)
        path=ROOT/'assets/blender/scripts'/name;code=path.read_text()
        code=code.replace("SOURCE=ROOT/'assets/blender/orbital-dual-bake-v15.blend'","SOURCE=ROOT/'assets/blender/orbital-dual-bake-v16.blend'")
        code=code.replace('intro-clean-v1','intro-clean-v16').replace('INTRO_CLEAN_V1','INTRO_CLEAN_V16')
        # The original append-only atlas-1 job expected an already compressed
        # v1 release. V16 runs both bake groups before compression, so preserve
        # the freshly written receiver PNGs without requiring future KTX files.
        if name=='bake_intro_clean_atlas1_v1.py':
            previous="protected += [OUT/'day-0.png', OUT/'day-0.ktx2', OUT/'day-8.png', OUT/'day-8.ktx2']"
            assert code.count(previous)==1
            code=code.replace(previous,"protected += [OUT/'day-0.png', OUT/'day-8.png']")
        code=code.replace('scene.cycles.samples=48','scene.cycles.samples=96').replace("'samples':48","'samples':96").replace("'version':1","'version':16")
        code=code.replace('Original Principled PBR and original microtextures from prepared V15 .blend','V16 Principled PBR and verified scans/procedural microtextures with fixed world triplanar mapping')
        code=code.replace('before={rel(p):sha(p) for p in protected}',"protected+=sorted(p for p in (ROOT/'public/textures/intro-clean-v1').iterdir() if p.is_file())\nbefore={rel(p):sha(p) for p in protected}")
        code=code.replace('bpy.ops.object.bake(', 'locked_bake(').replace('bpy.ops.render.render(', 'locked_render(')
        scope={'__name__':'v16_clean_receivers','__file__':str(Path(__file__).resolve()),'locked_bake':locked_bake,'locked_render':locked_render}
        exec(compile(code,str(path),'exec'),scope)
        after=fingerprints(scene,include_shading=True);assert before==after
        checks.append({'inheritedAuthoringScript':str(path.relative_to(ROOT)),'inheritedScriptSha256':sha(path),'geometryUvsNormalsUnchanged':True,'fingerprints':after})
    write(ROOT/'public/textures/intro-clean-v16/validation.json',{'complete':True,'source':str(PREP.relative_to(ROOT)),'sourceSha256':sha(PREP),'samples':96,'slots':[0,1,8],'oldIntroV1Untouched':True,'receiverPipelineAndLightingUnchanged':True,'geometryUvChecks':checks})
    print('ROOM_V16_CLEAN_INTRO_COMPLETE',flush=True)

if __name__=='__main__':main()
