"""Warm interior derivative of reviewed V17; invoke only through file MCP.

The user requested warm timber floors and wall faces, not recoloured exterior
platforms or props. Spatial shader masks retain all geometry/material indices.
About's verified CC0 walnut images are read-only sources, never rewritten.
"""
import json, math
from pathlib import Path
import bpy
import photoreal_materials_v18 as p
from photoreal_materials_v16 import geometry_signature
from bake_geometry_fingerprint import fingerprints

PREVIOUS={'orbital-dual-bake-v17.blend':'ec777d4d2beaa6655b3d3899f8a0317f54931f2230cebd78e2ebec560f34341c',
          'orbital-atelier-v17.blend':'699739ce0a8f6ef8759d1bfc7ddadb742fe53c9a9e7bd9c07bd48f0e2d51e794'}

def mathn(t,op,a,b=0):return p.math_node(t,op,a,b,'Warm '+op)
def mix(t,a,b,f,name):
    n=p.node(t,'ShaderNodeMixRGB',name);n.blend_type='MIX'
    for i,x in enumerate((f,a,b)):
        if isinstance(x,(tuple,list)):n.inputs[i].default_value=x
        elif isinstance(x,(int,float)):
            n.inputs[i].default_value=x if i==0 else (x,x,x,1)
        else:t.links.new(x,n.inputs[i])
    return n.outputs[0]

def box(t,axes,lo,hi):
    v=1
    for i,a in enumerate('XYZ'):
        v=mathn(t,'MULTIPLY',v,mathn(t,'GREATER_THAN',axes.outputs[a],lo[i]-.001))
        v=mathn(t,'MULTIPLY',v,mathn(t,'LESS_THAN',axes.outputs[a],hi[i]+.001))
    return v

def wood(t,geo,floor=False,cap=False):
    pos=geo.outputs['Position'];normal=geo.outputs['Normal']
    # Explicit image V grain: along world X on horizontal floor, Z on walls.
    if floor or cap:
        def rotate(v,left=False):
            sep=p.node(t,'ShaderNodeSeparateXYZ','Timber grain world axes');t.links.new(v,sep.inputs[0])
            join=p.node(t,'ShaderNodeCombineXYZ','Timber grain V along beam')
            for a,b in zip(('X','Z','Y') if left else ('Y','Z','X'),'XYZ'):t.links.new(sep.outputs[a],join.inputs[b])
            return join.outputs[0]
        if cap:
            coords=p.node(t,'ShaderNodeSeparateXYZ','Left return beam direction');t.links.new(pos,coords.inputs[0])
            left=mathn(t,'LESS_THAN',coords.outputs['X'],-4.74)
            pos=mix(t,rotate(pos),rotate(pos,True),left,'Continuous cap grain orientation')
            normal=mix(t,rotate(normal),rotate(normal,True),left,'Continuous cap projection normals')
        else:pos=rotate(pos);normal=rotate(normal)
    files=p.scan_files('walnut_veneer')
    col=p.triplanar(t,files['color'],pos,normal,1.65,True)
    gamma=p.node(t,'ShaderNodeGamma','About raw walnut gamma');gamma.inputs[1].default_value=1.14;t.links.new(col,gamma.inputs[0])
    dye=p.node(t,'ShaderNodeMixRGB','Warm transparent wood oil');dye.blend_type='MULTIPLY';dye.inputs[0].default_value=1
    t.links.new(gamma.outputs[0],dye.inputs[1]);dye.inputs[2].default_value=(.18,.12,.075,1) if floor else (.23,.16,.10,1)
    col=dye.outputs[0]
    rough=p.triplanar(t,files['roughness'],pos,normal,1.65)
    height=p.triplanar(t,files['height'],pos,normal,1.65)
    rough=p.remap(t,rough,.48,.64,'Smoked raw walnut matte roughness')
    if floor:
        coords=p.node(t,'ShaderNodeSeparateXYZ','Floor plank metres');t.links.new(geo.outputs['Position'],coords.inputs[0])
        across=mathn(t,'DIVIDE',coords.outputs['Y'],.23)
        row=mathn(t,'FLOOR',across)
        u=mathn(t,'FRACT',mathn(t,'ADD',mathn(t,'DIVIDE',coords.outputs['X'],2.1),mathn(t,'MULTIPLY',row,.37)))
        v=mathn(t,'FRACT',across)
        seam=mathn(t,'MAXIMUM',mathn(t,'LESS_THAN',u,.0017),mathn(t,'LESS_THAN',v,.010))
        seam_col=p.node(t,'ShaderNodeMixRGB','Timber-relative dark joint');seam_col.blend_type='MULTIPLY';seam_col.inputs[0].default_value=1
        t.links.new(col,seam_col.inputs[1]);seam_col.inputs[2].default_value=(.72,.72,.72,1)
        col=mix(t,col,seam_col.outputs[0],seam,'Restrained narrow plank joints')
        height=mathn(t,'SUBTRACT',height,mathn(t,'MULTIPLY',seam,.3))
    bump=p.node(t,'ShaderNodeBump','Walnut pores in metres');bump.inputs['Distance'].default_value=.0004;bump.inputs['Strength'].default_value=.35;t.links.new(height,bump.inputs['Height'])
    return col,rough,bump.outputs['Normal']

def replace_inputs(mat,mode):
    t=mat.node_tree;bs=p.principled(mat);assert bs
    geo=p.node(t,'ShaderNodeNewGeometry','Warm stable world coordinates')
    axes=p.node(t,'ShaderNodeSeparateXYZ','Warm position');t.links.new(geo.outputs['Position'],axes.inputs[0])
    norm=p.node(t,'ShaderNodeSeparateXYZ','Warm normal');t.links.new(geo.outputs['True Normal'],norm.inputs[0])
    stone_noise=p.noise(t,geo.outputs['Position'],.035,'Fine limestone mottling')
    stone=p.tint(t,(.49,.425,.335,1),stone_noise,.96,1.04,'Warm beige limestone')
    if mode=='floor':
        mask=1;col,rough,normal=wood(t,geo,True);metal=0;coat=.01
    elif mode=='wall':
        back=box(t,axes,(-4.961,3.309,.179),(4.961,3.741,5.131))
        left=box(t,axes,(-5.311,-2.451,.179),(-4.929,3.741,4.597))
        mask=mathn(t,'MAXIMUM',back,left)
        inward=mathn(t,'MAXIMUM',mathn(t,'MULTIPLY',back,mathn(t,'LESS_THAN',norm.outputs['Y'],-.3)),mathn(t,'MULTIPLY',left,mathn(t,'GREATER_THAN',norm.outputs['X'],.3)))
        wc,wr,wn=wood(t,geo)
        edge=p.node(t,'ShaderNodeMixRGB','Warm solid timber wall thickness');edge.blend_type='MULTIPLY';edge.inputs[0].default_value=1;t.links.new(wc,edge.inputs[1]);edge.inputs[2].default_value=(1,1,1,1)
        col=mix(t,edge.outputs[0],wc,inward,'Warm wall face and matching thickness')
        rough=mix(t,.61,wr,inward,'Wall edge finish');normal=mix(t,geo.outputs['Normal'],wn,inward,'Wall normal blend');metal=0;coat=.01
        # Original six-millimetre graphite grid tubes stay geometrically intact.
        # Give only that narrow floor elevation the same warm timber finish,
        # instead of layering black square tile joints over the new plank grain.
        seam=box(t,axes,(-4.555,-3.125,.181),(4.555,3.005,.190))
        fc,fr,fn=wood(t,geo,True)
        col=mix(t,col,fc,seam,'Warm existing floor construction joint')
        rough=mix(t,rough,fr,seam,'Construction joint roughness')
        normal=mix(t,normal,fn,seam,'Construction joint normal')
        mask=mathn(t,'MAXIMUM',mask,seam)
    else:
        back=box(t,axes,(-4.908,3.118,4.465),(4.913,3.782,5.215))
        left=box(t,axes,(-5.352,-2.465,3.748),(-4.758,3.780,4.716))
        mask=mathn(t,'MAXIMUM',back,left);col,rough,normal=wood(t,geo,cap=True);metal=0;coat=.01
    for name,value in [('Base Color',col),('Roughness',rough),('Normal',normal),('Metallic',metal),('Coat Weight',coat)]:
        inp=bs.inputs[name]
        old=inp.links[0].from_socket if inp.is_linked else tuple(inp.default_value) if name in ('Base Color','Normal') else inp.default_value
        if name=='Normal' and not inp.is_linked:old=geo.outputs['Normal']
        for link in list(inp.links):t.links.remove(link)
        if mode=='floor':
            if isinstance(value,(int,float)):inp.default_value=value
            else:t.links.new(value,inp)
        else:t.links.new(mix(t,old,value,mask,'Warm masked '+name),inp)
    mat['material_revision']=18;mat['v18_warm_role']=mode
    return {'name':mat.name,'mode':mode,'physicalWoodFootprintM':1.65 if mode!='cap' else None,'geometryDisplacement':False,'mapping':'world-space; texture V follows floor X / wall Z; original BakeUV untouched'}

def derive_current():
    assert bpy.app.background
    old=Path(bpy.data.filepath);assert old.name in PREVIOUS and p.sha(old)==PREVIOUS[old.name]
    new=old.with_name(old.name.replace('-v17.blend','-v18.blend'));assert not new.exists()
    before=geometry_signature();web=bpy.data.scenes.get('WEB_DUAL_V8');uv=fingerprints(web,True) if web else None
    records=[]
    for name,mat in sorted(p.relevant_materials().items()):
        c=p.canonical(name);mode=None
        if c=='MAT_Titanium_Floor':mode='floor'
        elif c=='MAT_Graphite_Enamel' and (not web or name.startswith('WEB8_BAKE_A0_')):mode='wall'
        elif c=='MAT_Satin_Titanium' and (not web or name.startswith(('WEB8_BAKE_A0_','WEB8_BAKE_A8_'))):mode='cap'
        if mode:records.append(replace_inputs(mat,mode))
    assert geometry_signature()==before and (not web or fingerprints(web,True)==uv)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new),compress=True)
    assert p.sha(old)==PREVIOUS[old.name]
    result={'complete':True,'invocation':'Blender MCP file-targeted isolated process','source':str(old.relative_to(p.ROOT)),'sourceSha256':p.sha(old),'derivative':str(new.relative_to(p.ROOT)),'sha256':p.sha(new),'geometryBefore':before,'geometryAfter':geometry_signature(),'bakeUvsNormalsUnchanged':True,'materials':records,'scanSources':p.verify_scans(),'revision':18,'reason':'User colour revision 5b requests substantially darker smoked raw walnut on floor/walls/top trim; actual scan colour is darkened selectively, with original lighting and all exterior/props unchanged.', 'colourReviewRevision':'5b','colourApproval':'awaiting explicit user confirmation; bulk paused','affectedSurfaceSlots':[0,8],'rebakeLightSlots':list(range(12)),'runtimeExported':False}
    p.write(p.ROOT/'assets/blender'/('photoreal-materials-v18-'+('prepared' if web else 'source')+'.json'),result)
    return result

def quick_review(filename='warm-review-day.png',state='day'):
    p.assert_prepared();scene=p.configure_current(state)
    scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.03
    scene.render.resolution_x=1100;scene.render.resolution_y=825;scene.render.resolution_percentage=100
    out=p.REVIEW/filename;out.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(out)
    with p.gpu_job('room-v18-warm-review'):bpy.ops.render.render(write_still=True)
    result={'path':str(out.relative_to(p.ROOT)),'sha256':p.sha(out),'sourceSha256':p.sha(bpy.data.filepath),'samples':24,'dimensions':[1100,825]}
    p.write(out.with_suffix('.json'),result);return result

def unchanged_surface_proof():
    """Read-only node and geometry fingerprints for safe V17 data-map reuse."""
    import hashlib
    assert bpy.app.background
    from pbr_bake_channels import mesh_signature
    scene=bpy.data.scenes['WEB_DUAL_V8'];rows=[]
    def value(v):
        if isinstance(v,(str,bool,int,float)) or v is None:return v
        try:return [float(x) for x in v]
        except:return str(v)
    for slot in range(12):
        if slot in (0,8):continue
        meshes=p.atlas_meshes(scene,slot);mats=sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name)
        graphs=[]
        for m in mats:
            nodes=[]
            for n in sorted(m.node_tree.nodes,key=lambda n:n.name):
                attrs={k:value(getattr(n,k)) for k in ('operation','blend_type','projection','extension','interpolation','clamp','use_clamp','vector_type','convert_from','convert_to','noise_dimensions','normalize') if hasattr(n,k)}
                img=getattr(n,'image',None)
                if img:
                    attrs['image']={'name':img.name,'path':bpy.path.abspath(img.filepath),'colorSpace':img.colorspace_settings.name}
                nodes.append({'name':n.name,'type':n.bl_idname,'inputs':[(s.identifier,value(s.default_value)) for s in n.inputs if hasattr(s,'default_value')],'attrs':attrs})
            links=sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in m.node_tree.links)
            graphs.append({'name':m.name,'nodes':nodes,'links':links})
        digest=hashlib.sha256(json.dumps(graphs,sort_keys=True).encode()).hexdigest()
        rows.append({'slot':slot,'shaderGraphsSha256':digest,'materials':[m.name for m in mats],'geometryUvNormalsSignature':mesh_signature(meshes)})
    result={'source':bpy.data.filepath,'sourceSha256':p.sha(bpy.data.filepath),'surfaces':rows,'method':'Full node types/properties/input values/links, image names/paths/color spaces plus mesh positions/UVs/normals/world transforms; no lighting dependency for F0/roughness/tangent normal.'}
    version='v18' if '-v18.blend' in bpy.data.filepath else 'v17'
    p.write(p.ROOT/'assets/blender'/f'room-{version}-surface-reuse-proof.json',result)
    return {'path':f'assets/blender/room-{version}-surface-reuse-proof.json','sourceSha256':result['sourceSha256'],'slots':[r['slot'] for r in rows]}
