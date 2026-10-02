"""Reallocate actual small-prop UV area; preserve V14 geometry and identities."""
import bpy, json, math, sys, time, hashlib, array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'assets/blender/scripts'))
from refine_edge_atlas_v14 import metrics
from bake_geometry_fingerprint import fingerprints

SOURCE = ROOT/'assets/blender/orbital-dual-bake-v14.blend'
OUTPUT = ROOT/'assets/blender/orbital-dual-bake-v15.blend'
REPORT = ROOT/'assets/blender/texture-precision-v15-prepare.json'
DESK = {'headphones_on_stand','headphone_cup_0','headphone_cup_1',
        'ceramic_ring_speaker','speaker_gimbal','keyboard_half_0','keyboard_half_1',
        'keyboard_dial','desktop_creative_controller','compact_camera','camera_focus_lens',
        'thermal_cup','drawing_stylus','coffee_table_pen','coffee_table_dial'}
SHELLS = {'main_display','compute_core','robot_companion','robot_service_hatch',
          'robot_leg_00','robot_leg_01','robot_leg_02'}

def geometry(scene):
    result = {}
    for o in scene.objects:
        if not o.get('web_export'): continue
        d=hashlib.sha256()
        d.update(json.dumps([list(r) for r in o.matrix_world]).encode())
        if o.type=='MESH':
            for attr, length, key, typ in [('vertices',len(o.data.vertices)*3,'co','f'),('loops',len(o.data.loops),'vertex_index','i')]:
                a=array.array(typ,[0])*length;getattr(o.data,attr).foreach_get(key,a);d.update(a.tobytes())
            a=array.array('f',[0])*(len(o.data.corner_normals)*3);o.data.corner_normals.foreach_get('vector',a);d.update(a.tobytes())
        result[o.name]={'geometry':d.hexdigest(),'id':o.get('asset_id'),'owner':o.get('owner_asset_id'),'parent':o.parent.name if o.parent else None}
    return result

def run():
    started=time.time();bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=scene;scene.view_layers[0].update()
    original_geo=geometry(scene);original_uv=fingerprints(scene,include_shading=True)
    selected=[o for o in scene.objects if o.type=='MESH' and o.get('web_export') and o.get('bake_atlas')==2]
    before={o.name:metrics(o,range(len(o.data.polygons)),4096) for o in selected}
    cache={}
    for atlas in (9,10):
        image=bpy.data.images.new(f'WEB8_ATLAS_{atlas}',width=4096,height=4096,alpha=False,float_buffer=True)
        image.colorspace_settings.name='Linear Rec.709'
    for o in selected:
        owner=o['owner_asset_id'];atlas=9 if owner in DESK else 2 if owner in SHELLS else 10
        o['bake_atlas']=o['geometry_atlas']=atlas;o['precision_revision']=15
        for i,mat in enumerate(list(o.data.materials)):
            key=(mat.name,atlas)
            if key not in cache:
                cp=mat.copy();cp.name=f'WEB15_BAKE_A{atlas}_'+mat.name;cp['bake_atlas']=atlas
                cp.node_tree.nodes['WEB8_BAKE_TARGET'].image=bpy.data.images[f'WEB8_ATLAS_{atlas}'];cache[key]=cp
            o.data.materials[i]=cache[key]
    atlases=[]
    for atlas in (2,9,10):
        members=[o for o in selected if o['bake_atlas']==atlas]
        bpy.ops.object.select_all(action='DESELECT')
        for o in members:
            o.hide_set(False);o.select_set(True);o.data.uv_layers.active=o.data.uv_layers['BakeUV'];o.data.uv_layers.active.active_render=True
        bpy.context.view_layer.objects.active=members[0]
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(75),island_margin=.0001,area_weight=0,correct_aspect=True,scale_to_bounds=True)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True,rotate_method='ANY',scale=True,merge_overlap=False,
                               margin_method='FRACTION',margin=8/4096,shape_method='CONCAVE',pin=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in members:
            assert all(math.isfinite(c) and -.0001<=c<=1.0001 for x in o.data.uv_layers['BakeUV'].data for c in x.uv),o.name
        rows=[]
        for o in members:
            after=metrics(o,range(len(o.data.polygons)),4096);old=before[o.name]
            rows.append({'object':o.name,'owner':o['owner_asset_id'],'before':old,'after':after,
                         'linearTexelGain':after['texelsPerMeter']/old['texelsPerMeter']})
        atlases.append({'atlas':atlas,'size':4096,'objects':rows,'uvOccupancy':sum(x['after']['uvArea'] for x in rows)})
    assert geometry(scene)==original_geo,'Only UVs/material assignments may change'
    after_uv=fingerprints(scene,include_shading=True)
    retained_before={k:v for k,v in original_uv.items() if v['atlas']!=2}
    assert retained_before=={k:v for k,v in after_uv.items() if v['atlas'] not in (2,9,10)}
    report={'revision':15,'input':str(SOURCE.relative_to(ROOT)),'prepared':str(OUTPUT.relative_to(ROOT)),
            'repackedAtlases':[2,9,10],'rebakedAtlases':[2,3,4,9,10],'retainedAtlases':[0,1,5,6,7,8],
            'atlasSizes':[4096]*6+[3072,2048,3072,4096,4096],
            'geometryAndHierarchyUnchanged':True,'retainedUVAndShadingUnchanged':True,
            'assetIds':[o['asset_id'] for o in scene.objects if o.get('web_export') and o.get('asset_id')],
            'preservedImageObjects':[o.name for o in scene.objects if o.get('web_export') and o.get('web_kind')=='image'],
            'atlases':atlases,'seconds':time.time()-started,'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    scene['precision_revision']=15;scene['texture_precision_v15']=json.dumps(report)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='atlases'},indent=2))
    for a in atlases: print('ATLAS',a['atlas'],'UV occupancy',a['uvOccupancy'],'texel gains',min(o['linearTexelGain'] for o in a['objects']),max(o['linearTexelGain'] for o in a['objects']))

if __name__=='__main__':run()
