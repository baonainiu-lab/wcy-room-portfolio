"""Persist the native V15 image renders in both editable and web-prepared sources.

Only image datablock references change. Geometry, UVs, pivots and identifiers are
verified before/after; bake-time source hashes remain in their own manifests.
"""
import bpy, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from prepare_texture_precision_v15 import geometry
from bake_geometry_fingerprint import fingerprints
OUT=ROOT/'public/textures/lighting-v15'
REPORT=ROOT/'assets/blender/precision-images-v15-bind-report.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    if REPORT.exists():
        existing=json.loads(REPORT.read_text())
        if existing.get('complete') and all(sha(ROOT/r['source'])==r['sha256AfterImageBinding'] for r in existing['sources']) and all(sha(ROOT/r['path'])==r['sha256'] for r in existing['images'].values()):
            print(json.dumps(existing,indent=2));return existing
    window=json.loads((OUT/'window-v15-manifest.json').read_text())
    screen=json.loads((OUT/'screen-v15-manifest.json').read_text())
    assert window['complete'] and screen['complete']
    image_paths={'day':OUT/'window-day.png','night':OUT/'window-night.png','screen':OUT/'screen-art-render.png'}
    rendered_windows={r['state']:r for r in window['renders']}
    for state in ('day','night'):
        assert sha(image_paths[state])==rendered_windows[state]['sha256']
    assert sha(image_paths['screen'])==screen['sha256']
    records=[]
    for filename in ('orbital-atelier-v15.blend','orbital-dual-bake-v15.blend'):
        source=ROOT/'assets/blender'/filename
        before_hash=sha(source)
        bpy.ops.wm.open_mainfile(filepath=str(source))
        prepared='dual-bake' in filename
        scene=bpy.data.scenes['WEB_DUAL_V8'] if prepared else bpy.context.scene
        before_geometry=geometry(scene) if prepared else None
        before_uv=fingerprints(scene,include_shading=True) if prepared else None
        replacements={};changes=[]
        for mat in bpy.data.materials:
            if not mat.node_tree:continue
            for node in mat.node_tree.nodes:
                if node.type!='TEX_IMAGE' or not node.image:continue
                old=node.image
                marker=(old.name+' '+old.filepath).lower()
                if 'screen-art-render' in marker:key='screen'
                elif 'window-city' in marker or 'window-day' in marker or 'window-night' in marker:
                    key='night' if 'night' in marker else 'day'
                else:continue
                if key not in replacements:
                    image=bpy.data.images.load(str(image_paths[key]),check_existing=False)
                    image.name='screen-art-render-v15.png' if key=='screen' else 'window-city-v15-'+key
                    image.colorspace_settings.name='sRGB'
                    image.pack()
                    replacements[key]=image
                node.image=replacements[key]
                changes.append({'material':mat.name,'node':node.name,'previousImage':old.name,'image':node.image.name,'path':str(image_paths[key].relative_to(ROOT))})
        assert {'screen','day'}.issubset(replacements),list(replacements)
        if prepared:
            assert geometry(scene)==before_geometry
            assert fingerprints(scene,include_shading=True)==before_uv
        bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=True)
        records.append({'source':str(source.relative_to(ROOT)),'sha256BeforeImageBinding':before_hash,
                        'sha256AfterImageBinding':sha(source),'changes':changes,
                        'geometryAndUVUnchanged':True if prepared else 'No geometry operations performed'})
    report={'revision':15,'complete':True,'sources':records,'images':{k:{'path':str(v.relative_to(ROOT)),'sha256':sha(v)} for k,v in image_paths.items()},
            'windowRenderManifest':'public/textures/lighting-v15/window-v15-manifest.json',
            'screenRenderManifest':'public/textures/lighting-v15/screen-v15-manifest.json'}
    REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':run()
