"""V5 finish-only derivatives. Never rebuild, unwrap, move, or overwrite V4.

Geometry.Position and Geometry.Normal are world-space in Cycles. Explicit
triplanar sampling therefore remains identical when disposable bake proxies
are joined, unlike Generated coordinates or object-bound BOX projections.
"""
import bpy, hashlib, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
from prepare_gallery import _fingerprint, _hierarchy
TEX=ROOT/'assets/textures/about-atelier-v3'
OUT=ROOT/'assets/blender/works-gallery-v5'
REVISION='V5 photographed mineral aggregate and saddle leather; stable world-metre brushed finishes'
MAPS={
 'terrazzo':('Terrazzo001/Terrazzo001_2K-JPG_Color.jpg','Terrazzo001/Terrazzo001_2K-JPG_Roughness.jpg','Terrazzo001/Terrazzo001_2K-JPG_Displacement.jpg'),
 'leather':('brown_leather/brown_leather_albedo_2k.jpg','brown_leather/brown_leather_rough_2k.jpg','brown_leather/brown_leather_disp_2k.jpg')}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def relative(path): return Path(path).relative_to(ROOT).as_posix()

def geometry(scene):
    digest=hashlib.sha256()
    for o in sorted(scene.objects,key=lambda o:o.name):
        digest.update((o.name+'|'+o.type+'|'+(o.parent.name if o.parent else '')+'|'+str(o.get('asset_id',''))).encode())
        for row in o.matrix_world: digest.update(struct.pack('<4f',*row))
        if o.type=='MESH':
            for v in o.data.vertices: digest.update(struct.pack('<3f',*v.co))
            for p in o.data.polygons:
                digest.update(struct.pack('<I',len(p.vertices)))
                digest.update(struct.pack('<%dI'%len(p.vertices),*p.vertices))
                digest.update(struct.pack('<I',p.material_index))
            for uv in o.data.uv_layers:
                digest.update(uv.name.encode())
                for l in uv.data: digest.update(struct.pack('<2f',*l.uv))
        elif o.type=='CURVE':
            for spline in o.data.splines:
                for p in spline.points: digest.update(struct.pack('<4f',*p.co))
                for p in spline.bezier_points:
                    for v in (p.co,p.handle_left,p.handle_right): digest.update(struct.pack('<3f',*v))
        elif o.type=='FONT': digest.update(o.data.body.encode())
    return digest.hexdigest()

def lights(scene):
    return {o.name:{'matrix':[list(r) for r in o.matrix_world], 'type':o.data.type,'energy':o.data.energy,'color':list(o.data.color)} for o in scene.objects if o.type=='LIGHT'}

def vec(tree,operation,a,b=None):
    n=tree.nodes.new('ShaderNodeVectorMath'); n.operation=operation
    tree.links.new(a,n.inputs[0])
    if b is not None:
        if isinstance(b,(tuple,list)): n.inputs[1].default_value=b
        else: tree.links.new(b,n.inputs[1])
    return n

def triplanar(tree,repeat):
    geo=tree.nodes.new('ShaderNodeNewGeometry');geo.label='World position + normal: invariant under bake proxy joins'
    scaled=vec(tree,'MULTIPLY',geo.outputs['Position'],(repeat,)*3)
    xyz=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(scaled.outputs['Vector'],xyz.inputs[0])
    absolute=vec(tree,'ABSOLUTE',geo.outputs['Normal'])
    nxyz=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(absolute.outputs[0],nxyz.inputs[0])
    powers=[];coords=[]
    for axis,uv in zip('XYZ',[('Y','Z'),('X','Z'),('X','Y')]):
        co=tree.nodes.new('ShaderNodeCombineXYZ')
        tree.links.new(xyz.outputs[uv[0]],co.inputs['X']);tree.links.new(xyz.outputs[uv[1]],co.inputs['Y'])
        coords.append(co.outputs[0])
        power=tree.nodes.new('ShaderNodeMath');power.operation='POWER';power.inputs[1].default_value=6
        tree.links.new(nxyz.outputs[axis],power.inputs[0]);powers.append(power.outputs[0])
    xy=tree.nodes.new('ShaderNodeMath');xy.operation='ADD'
    tree.links.new(powers[0],xy.inputs[0]);tree.links.new(powers[1],xy.inputs[1])
    total=tree.nodes.new('ShaderNodeMath');total.operation='ADD'
    tree.links.new(xy.outputs[0],total.inputs[0]);tree.links.new(powers[2],total.inputs[1])
    weights=[]
    for power in powers:
        n=tree.nodes.new('ShaderNodeMath');n.operation='DIVIDE'
        tree.links.new(power,n.inputs[0]);tree.links.new(total.outputs[0],n.inputs[1]);weights.append(n.outputs[0])
    return coords,weights

def image(tree,name,coordinates,color):
    im=bpy.data.images.load(str(TEX/name),check_existing=True)
    im.colorspace_settings.name='sRGB' if color else 'Non-Color'
    if not im.packed_file: im.pack()
    im['license']='CC0-1.0';im['provenance_manifest']='assets/textures/about-atelier-v3/texture-manifest.json'
    samples=[]
    for axis,co,weight in zip('XYZ',*coordinates):
        n=tree.nodes.new('ShaderNodeTexImage');n.image=im;n.projection='FLAT';n.extension='REPEAT';n.interpolation='Linear';n.label=axis+' world plane'
        tree.links.new(co,n.inputs['Vector'])
        scale=vec(tree,'SCALE',n.outputs['Color']);tree.links.new(weight,scale.inputs['Scale']);samples.append(scale.outputs[0])
    return vec(tree,'ADD',vec(tree,'ADD',samples[0],samples[1]).outputs[0],samples[2]).outputs[0]

def roughness(tree,p,fac,lo,hi):
    n=tree.nodes.new('ShaderNodeMapRange');n.inputs['To Min'].default_value=lo;n.inputs['To Max'].default_value=hi
    tree.links.new(fac,n.inputs['Value']);tree.links.new(n.outputs[0],p.inputs['Roughness'])

def bump(tree,p,fac,distance,strength):
    n=tree.nodes.new('ShaderNodeBump');n.inputs['Distance'].default_value=distance;n.inputs['Strength'].default_value=strength
    tree.links.new(fac,n.inputs['Height']);tree.links.new(n.outputs[0],p.inputs['Normal'])

def modify(mat):
    source=mat.get('source_material',mat.name)
    kind=source.removeprefix('GALLERY_')
    if kind not in {'terrazzo','leather','silver','bronze','navy','paper'}: return None
    tree=mat.node_tree
    pold=next(n for n in tree.nodes if n.type=='BSDF_PRINCIPLED')
    base=tuple(pold.inputs['Base Color'].default_value)
    metallic=pold.inputs['Metallic'].default_value;rough=pold.inputs['Roughness'].default_value
    target=tree.nodes.get('GALLERY_BAKE_TARGET');target_image=target.image if target else None
    tree.nodes.clear()
    out=tree.nodes.new('ShaderNodeOutputMaterial');p=tree.nodes.new('ShaderNodeBsdfPrincipled')
    tree.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    p.inputs['Base Color'].default_value=base;p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=rough
    if kind in MAPS:
        repeat=2.0 if kind=='terrazzo' else 2.5
        coordinate=triplanar(tree,repeat)
        albedo=image(tree,MAPS[kind][0],coordinate,True)
        scanned_rough=image(tree,MAPS[kind][1],coordinate,False)
        height=image(tree,MAPS[kind][2],coordinate,False)
        # Warm saddlery and cool mineral finishes retain the original palette.
        tint=(1.12,1.09,1.02) if kind=='terrazzo' else (2.40,2.05,1.90)
        tinted=vec(tree,'MULTIPLY',albedo,tint)
        tree.links.new(tinted.outputs[0],p.inputs['Base Color'])
        roughness(tree,p,scanned_rough,*( (.27,.43) if kind=='terrazzo' else (.36,.55) ))
        distance=.00024 if kind=='terrazzo' else .00065
        bump(tree,p,height,distance,.22 if kind=='terrazzo' else .30)
        p.inputs['Coat Weight'].default_value=.08 if kind=='terrazzo' else .04
        p.inputs['Coat Roughness'].default_value=.3
        mat['maps']=';'.join(MAPS[kind]);mat['repeat_per_metre']=repeat
        mat['physical_bump_distance_m']=distance
    else:
        geo=tree.nodes.new('ShaderNodeNewGeometry')
        axis_scale=(4,680,680) if kind in {'silver','bronze'} else (310,310,310)
        vector=vec(tree,'MULTIPLY',geo.outputs['Position'],axis_scale)
        noise=tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1;noise.inputs['Detail'].default_value=2
        tree.links.new(vector.outputs[0],noise.inputs['Vector'])
        variation=.045 if kind in {'silver','bronze'} else .025
        roughness(tree,p,noise.outputs['Fac'],rough-variation,rough+variation)
        distance=.000025 if kind in {'silver','bronze','navy'} else .00005
        bump(tree,p,noise.outputs['Fac'],distance,.15)
        mat['physical_bump_distance_m']=distance
    if target_image:
        target=tree.nodes.new('ShaderNodeTexImage');target.name='GALLERY_BAKE_TARGET';target.image=target_image
        uv=tree.nodes.new('ShaderNodeUVMap');uv.uv_map='BakeUV';tree.links.new(uv.outputs[0],target.inputs['Vector'])
        tree.nodes.active=target;target.select=True
    mat['finish_revision']=REVISION
    mat['coordinates']='World metres: explicit triplanar with normalized world-normal weights for scans; world-position procedural finishes'
    return {'name':mat.name,'source':source,'coordinates':mat['coordinates'],'height_m':mat['physical_bump_distance_m'],'maps':list(MAPS.get(kind,()))}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    original_inputs={relative(ROOT/'assets/blender'/f):sha(ROOT/'assets/blender'/f) for f in ['works-gallery-v4.blend','works-gallery-bake-v4.blend']}
    records=[]
    revision_hash=sha(Path(__file__))
    for prepared in [False,True]:
        stem='works-gallery-bake' if prepared else 'works-gallery'
        path=ROOT/'assets/blender'/f'{stem}-v4.blend';output=ROOT/'assets/blender'/f'{stem}-v5.blend'
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene=bpy.data.scenes['WEB_WORKS_GALLERY_V4' if prepared else 'WORKS_GALLERY_V4'];bpy.context.window.scene=scene
        before=geometry(scene);hierarchy=_hierarchy(scene.objects);before_lights=lights(scene)
        assert len(hierarchy)==77
        meshes=[o for o in scene.objects if o.type=='MESH' and o.get('web_export')]
        original_fp=_fingerprint(meshes) if prepared else None
        mats={m for o in scene.objects if hasattr(o.data,'materials') for m in o.data.materials if m}
        changed=[r for m in sorted(mats,key=lambda m:m.name) if (r:=modify(m))]
        assert geometry(scene)==before and _hierarchy(scene.objects)==hierarchy and lights(scene)==before_lights
        if prepared: assert _fingerprint(meshes)==original_fp
        scene['material_revision']=REVISION
        scene['material_revision_script_sha256']=revision_hash
        scene['source_blend']=str(ROOT/'assets/blender/works-gallery-v5.blend')
        if prepared:
            oldpid=scene['preparation_id']
            pid=hashlib.sha256((oldpid+'|'+revision_hash).encode()).hexdigest()
            scene['preparation_id']=pid;scene['geometry_uv_sha256']=original_fp
            scene['web_baked']=False
            manifest=json.loads((ROOT/'assets/blender/works-gallery-v4/preparation-report.json').read_text())
            manifest.update(source='assets/blender/works-gallery-v5.blend',prepared=relative(output),preparation_id=pid,geometry_uv_sha256=original_fp,material_revision=REVISION,source_preparation_id=oldpid,geometryUVUnchanged=True)
            scene['preparation_manifest']=json.dumps(manifest,ensure_ascii=False)
            (OUT/'preparation-report.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        bpy.data.libraries.write(str(output),{scene},fake_user=True,compress=True)
        records.append({'input':relative(path),'output':relative(output),'sha256':sha(output),'scene':scene.name,'assets':77,'identityHierarchyUnchanged':True,'geometryTransformsAllUVsBefore':before,'geometryTransformsAllUVsAfter':geometry(scene),'geometryUVFingerprint':original_fp,'lightsUnchanged':True,'modifiedMaterials':changed})
    for p,s in original_inputs.items(): assert sha(ROOT/p)==s
    maps={relative(TEX/m):sha(TEX/m) for seq in MAPS.values() for m in seq}
    report={'complete':True,'revision':REVISION,'originalInputsUnchanged':original_inputs,'derivatives':records,'sourceMapsCC0':maps,'licenseManifest':'assets/textures/about-atelier-v3/texture-manifest.json','notes':['No re-unwrapping or geometry operation. All material slots preserved.','Tangent-space normal images are retained in source library; triplanar uses scanned height to avoid invalid UV-tangent normals.','World coordinates are stable across source and disposable joined bake proxies.']}
    (OUT/'material-refinement-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'complete':True,'outputs':[r['output'] for r in records],'assets':77,'geometryUnchanged':True}))

if __name__=='__main__': main()
