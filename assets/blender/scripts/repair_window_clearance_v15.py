"""Remove the actual window/display-tower overlap in new V15 sources only."""
import bpy, json, sys, hashlib, shutil
from pathlib import Path
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from refine_edge_atlas_v14 import components, bounds
PREP=ROOT/'assets/blender/orbital-dual-bake-v15.blend'
REPORT=ROOT/'assets/blender/window-clearance-v15-repair.json'
DELTA=.25

def shrink_vertices(o,faces):
    lo,hi=bounds(o,faces);scale=(hi.x-lo.x-DELTA)/(hi.x-lo.x);inv=o.matrix_world.inverted()
    for vi in {v for f in faces for v in o.data.polygons[f].vertices}:
        p=o.matrix_world@o.data.vertices[vi].co;p.x=lo.x+(p.x-lo.x)*scale;o.data.vertices[vi].co=inv@p
    o.data.update();newlo,newhi=bounds(o,faces)
    return {'object':o.name,'beforeMin':list(lo),'beforeMax':list(hi),'afterMin':list(newlo),'afterMax':list(newhi),'xScale':scale}

def bvh(o,fs):
    ids=sorted({v for f in fs for v in o.data.polygons[f].vertices});remap={v:i for i,v in enumerate(ids)}
    return BVHTree.FromPolygons([o.matrix_world@o.data.vertices[v].co for v in ids],
        [tuple(remap[v] for v in o.data.polygons[f].vertices) for f in fs],epsilon=.00001)

def repair_source():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-atelier-v14.blend'))
    source_edits=[]
    for o in bpy.data.objects:
        if not any(n in o.name for n in ('A_PanoramaTitaniumBezel','A_WindowRecessLight','A_Window_CityPanel')):continue
        bpy.context.window.scene=o.users_scene[0];bpy.context.view_layer.update()
        evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        corners=[evaluated.matrix_world@v.co for v in mesh.vertices];evaluated.to_mesh_clear()
        left=min(p.x for p in corners);right=max(p.x for p in corners)
        assert right-left>5.5,(o.name,left,right)
        scale=(right-left-DELTA)/(right-left)
        o.matrix_world=Matrix.Translation((left,0,0))@Matrix.Diagonal((scale,1,1,1))@Matrix.Translation((-left,0,0))@o.matrix_world
        source_edits.append({'name':o.name,'leftPreserved':left,'rightBefore':right,'rightAfter':right-DELTA})
    assert len(source_edits)>=3,len(source_edits)
    patched=0
    for m in bpy.data.materials:
        if not m.get('day_sun_v9_aperture') or not m.node_tree:continue
        for node in m.node_tree.nodes:
            if node.type!='SEPXYZ' or not node.outputs['X'].links:continue
            center=node.outputs['X'].links[0].to_node
            if center.type!='MATH' or center.operation!='SUBTRACT':continue
            if abs(center.inputs[1].default_value-.25)>.001:continue
            center.inputs[1].default_value=.125
            absolute=center.outputs[0].links[0].to_node
            for link in absolute.outputs[0].links:
                extent=link.to_node
                if extent.type=='MATH' and extent.operation=='SUBTRACT':extent.inputs[1].default_value=(5.82-DELTA)/2-.29;patched+=1
    for scene in bpy.data.scenes:
        scene['web_precision_revision']=15;scene['web_precision_source']='assets/blender/orbital-dual-bake-v15.blend';scene['window_clearance_revision']=15
        if scene.get('day_sunlight_v9_report'):
            r=json.loads(scene['day_sunlight_v9_report']);r['aperture'].update(center_x=.125,width=5.57);scene['day_sunlight_v9_report']=json.dumps(r)
    bpy.context.window.scene=bpy.data.scenes['ORIGINAL_DAY_V13']
    source=ROOT/'assets/blender/orbital-atelier-v15.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=True)
    return source_edits,patched,source

def run():
    before_hash=hashlib.sha256(PREP.read_bytes()).hexdigest()
    snapshot=ROOT/'assets/blender/orbital-dual-bake-v15-props-snapshot.blend'
    if not snapshot.exists():shutil.copy2(PREP,snapshot)
    bpy.ops.wm.open_mainfile(filepath=str(PREP));s=bpy.data.scenes['WEB_DUAL_V8'];bpy.context.window.scene=s;s.view_layers[0].update()
    jobs=[];tower=[];edits=[]
    for o in s.objects:
        if o.type!='MESH' or o.get('owner_asset_id')!='room_static':continue
        for fs in components(o):
            lo,hi=bounds(o,fs);d=hi-lo
            if o.get('web_kind')=='image' or (o.get('bake_atlas')==8 and lo.x< -2.7 and 5.9<d.x<6.4 and 2.4<d.z<2.9):jobs.append((o,fs))
            elif lo.x>3.15 and 1.5<d.x<1.7 and d.z>4:tower.append((o,fs))
    assert len(jobs)==3 and len(tower)>=2,(len(jobs),len(tower))
    for o,fs in jobs:edits.append(shrink_vertices(o,fs))
    s.view_layers[0].update();checks=[]
    for o,fs in jobs:
        for t,tf in tower:
            hits=bvh(o,fs).overlap(bvh(t,tf));checks.append({'window':o.name,'tower':t.name,'triangleIntersections':len(hits)});assert not hits,checks[-1]
    s['window_clearance_revision']=15;s['window_clearance_delta_x']=DELTA
    bpy.ops.wm.save_as_mainfile(filepath=str(PREP),compress=True)
    prepared_hash=hashlib.sha256(PREP.read_bytes()).hexdigest()
    source_edits,patched,source=repair_source()
    report={'revision':15,'windowWidthReduction':DELTA,'reason':'Actual window/display tower geometry intersections confirmed by world-space BVH.','preparedEdits':edits,'bvhChecks':checks,
            'allWindowTowerIntersectionsRemoved':True,'editableSourceEdits':source_edits,'dayApertureMaterialsUpdated':patched,
            'preparedBeforeWindowRepairSha256':before_hash,'preparedAfterWindowRepairSha256':prepared_hash,
            'smallPropBakeSnapshot':str(snapshot.relative_to(ROOT)),'editableSource':str(source.relative_to(ROOT)),
            'geometryChangedAtlases':[8],'independentWindowImageChanged':True,'requiredSupplementalBakes':[0,8],
            'lightingNote':'Sun/world/practical lamp powers unchanged. Aperture right boundary narrowed with the real bezel. In-flight small-prop maps retain prior aperture irradiance; architecture atlases 0/8 are rebaked against repaired geometry.'}
    REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    if '--source-only' in sys.argv:
        edits,patched,source=repair_source();report=json.loads(REPORT.read_text())
        report['editableSourceEdits']=edits;report['dayApertureMaterialsUpdated']=patched
        report['editableSourceSha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(edits,indent=2))
    else:run()
