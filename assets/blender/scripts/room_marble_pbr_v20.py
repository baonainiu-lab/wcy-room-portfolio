"""Licensed ambientCG PBR materials, wall/cap only; no geometry displacement.

ambientCG declares these assets PBRProcedural, not photogrammetry/scans.
All images remain original licensed inputs; authored projection is in metres.
"""
from pathlib import Path
import json
import bpy
import photoreal_materials_v20 as p

TEXTURES=p.ROOT/'assets/textures/room-marble-v20'

def mix(t,a,b,f,label):
    n=p.node(t,'ShaderNodeMixRGB',label);n.blend_type='MIX'
    for i,x in enumerate((f,a,b)):
        if isinstance(x,(tuple,list)):n.inputs[i].default_value=x
        elif isinstance(x,(int,float)):n.inputs[i].default_value=x if i==0 else (x,x,x,1)
        else:t.links.new(x,n.inputs[i])
    return n.outputs[0]

def m(t,op,a,b=0):return p.math_node(t,op,a,b,'V20 stone mask '+op)

def box(t,axes,lo,hi):
    q=1
    for i,axis in enumerate('XYZ'):
        q=m(t,'MULTIPLY',q,m(t,'GREATER_THAN',axes.outputs[axis],lo[i]-.001))
        q=m(t,'MULTIPLY',q,m(t,'LESS_THAN',axes.outputs[axis],hi[i]+.001))
    return q

def vector(t,op,a,b,label):
    n=p.node(t,'ShaderNodeVectorMath',label);n.operation=op
    for i,x in enumerate((a,b)):
        if isinstance(x,(tuple,list)):n.inputs[i].default_value=x
        elif x is not None:t.links.new(x,n.inputs[i])
    return n.outputs[0]

def normal_world(t,path,position,normal,tile_m,strength=.22):
    """Triplanar tangent map perturbations reoriented onto the world normal.

    Neutral tangent normals produce exactly the original world normal, also
    on bevels. Only the perturbation is blended, not the three axis normals.
    """
    im=bpy.data.images.load(str(path),check_existing=True);im.colorspace_settings.name='Non-Color'
    coords=p.node(t,'ShaderNodeSeparateXYZ','V20 normal world metres');t.links.new(p.scale_vector(t,position,(1/tile_m,)*3,'V20 normal map footprint'),coords.inputs[0])
    components=p.node(t,'ShaderNodeSeparateXYZ','V20 normal projection signs');t.links.new(normal,components.inputs[0])
    weights=[m(t,'POWER',m(t,'ABSOLUTE',components.outputs[a]),6) for a in 'XYZ'];total=m(t,'ADD',m(t,'ADD',weights[0],weights[1]),weights[2]);parts=[]
    for i,(u,v) in enumerate((('Y','Z'),('X','Z'),('X','Y'))):
        uv=p.node(t,'ShaderNodeCombineXYZ','V20 NormalGL plane '+str(i));t.links.new(coords.outputs[u],uv.inputs['X']);t.links.new(coords.outputs[v],uv.inputs['Y'])
        image=p.node(t,'ShaderNodeTexImage','V20 real NormalGL '+str(i));image.image=im;image.extension='REPEAT';image.projection='FLAT';t.links.new(uv.outputs[0],image.inputs['Vector'])
        decoded=vector(t,'SUBTRACT',vector(t,'MULTIPLY',image.outputs['Color'],(2,2,2),'V20 normal double'),(1,1,1),'V20 signed tangent normal')
        xyz=p.node(t,'ShaderNodeSeparateXYZ','V20 tangent components');t.links.new(decoded,xyz.inputs[0])
        axial=m(t,'MULTIPLY',m(t,'SUBTRACT',xyz.outputs['Z'],1),m(t,'SIGN',components.outputs['XYZ'[i]]))
        values=(axial,xyz.outputs['X'],xyz.outputs['Y']) if i==0 else (xyz.outputs['X'],axial,xyz.outputs['Y']) if i==1 else (xyz.outputs['X'],xyz.outputs['Y'],axial)
        join=p.node(t,'ShaderNodeCombineXYZ','V20 world perturbation '+str(i))
        for socket,value in zip(join.inputs,values):t.links.new(value,socket)
        weight=m(t,'MULTIPLY',m(t,'DIVIDE',weights[i],total),strength)
        scale=p.node(t,'ShaderNodeVectorMath','V20 weighted normal deviation');scale.operation='SCALE';t.links.new(join.outputs[0],scale.inputs[0]);t.links.new(weight,scale.inputs['Scale']);parts.append(scale.outputs[0])
    delta=vector(t,'ADD',vector(t,'ADD',parts[0],parts[1],'V20 normal pair'),parts[2],'V20 normal triplanar sum')
    return vector(t,'NORMALIZE',vector(t,'ADD',normal,delta,'V20 original surface plus map deviation'),None,'V20 physical normal')

def apply_marble(mat,role):
    assert role in ('wall','cap')
    asset='Marble005' if role=='wall' else 'Marble002';tile=5.6 if role=='wall' else 5.2
    directory=TEXTURES/(asset+'_4K-PNG')
    files={key:directory/(asset+'_4K-PNG_'+suffix+'.png') for key,suffix in [('color','Color'),('roughness','Roughness'),('normal','NormalGL'),('height','Displacement')]}
    assert all(path.is_file() for path in files.values()),files
    source_metadata=TEXTURES/(asset+'-SOURCE.json');source=json.loads(source_metadata.read_text())
    assert source['assetId']==asset and source['license']=='CC0-1.0' and source['creationMethod']=='PBRProcedural'
    documented={row['path']:row['sha256'] for row in source['files']}
    for path in files.values():assert p.sha(path)==documented[str(path.relative_to(p.ROOT))]
    t=mat.node_tree;bs=p.principled(mat);geo=p.node(t,'ShaderNodeNewGeometry','V20 stable world-space stone')
    axes=p.node(t,'ShaderNodeSeparateXYZ','V20 material-only architectural mask');t.links.new(geo.outputs['Position'],axes.inputs[0])
    if role=='wall':
        mask=m(t,'MAXIMUM',box(t,axes,(-4.961,3.309,.179),(4.961,3.741,5.131)),box(t,axes,(-5.311,-2.451,.179),(-4.929,3.741,4.617)))
    else:
        mask=m(t,'MAXIMUM',box(t,axes,(-4.968,3.115,4.45),(5.012,3.792,5.23)),box(t,axes,(-5.352,-2.551,3.746),(-4.758,3.780,4.717)))
    color=p.triplanar(t,files['color'],geo.outputs['Position'],geo.outputs['Normal'],tile,True)
    gamma=p.node(t,'ShaderNodeGamma','V20 mild native mineral contrast');gamma.inputs[1].default_value=1.045 if role=='wall' else 1.035;t.links.new(color,gamma.inputs[0]);color=gamma.outputs[0]
    measured_rough=p.triplanar(t,files['roughness'],geo.outputs['Position'],geo.outputs['Normal'],tile)
    rough_range=(.22,.38) if role=='wall' else (.25,.41)
    rough=p.remap(t,measured_rough,*rough_range,'V20 calibrated satin stone finish')
    measured_normal=normal_world(t,files['normal'],geo.outputs['Position'],geo.outputs['Normal'],tile,.22)
    height=p.triplanar(t,files['height'],geo.outputs['Position'],geo.outputs['Normal'],tile)
    bump=p.node(t,'ShaderNodeBump','V20 height-map microdetail without displacement');bump.inputs['Distance'].default_value=.0001;bump.inputs['Strength'].default_value=.08;t.links.new(height,bump.inputs['Height']);t.links.new(measured_normal,bump.inputs['Normal'])
    for name,value in [('Base Color',color),('Roughness',rough),('Normal',bump.outputs['Normal']),('Metallic',0),('Coat Weight',0),('IOR',1.52),('Specular IOR Level',.5)]:
        inp=bs.inputs[name];old=inp.links[0].from_socket if inp.is_linked else tuple(inp.default_value) if name in ('Base Color','Normal') else inp.default_value
        if name=='Normal' and not inp.is_linked:old=geo.outputs['Normal']
        for link in list(inp.links):t.links.remove(link)
        t.links.new(mix(t,old,value,mask,'V20 protected-scope '+name),inp)
    mat['material_revision']=20;mat['v20_role']='ambientcg_white_marble_wall' if role=='wall' else 'ambientcg_black_marble_cap';mat['v20_material_asset']=asset
    maps={}
    for key,path in files.items():
        image=bpy.data.images.load(str(path),check_existing=True)
        if not image.packed_file:image.pack()
        import hashlib
        packed_hash=hashlib.sha256(image.packed_file.data).hexdigest();expected=documented[str(path.relative_to(p.ROOT))]
        assert packed_hash==expected,'Packed texture must retain exact licensed PNG bytes'
        nodes=sorted(n.name for n in t.nodes if n.type=='TEX_IMAGE' and n.image==image);assert nodes
        maps[key]={'path':str(path.relative_to(p.ROOT)),'sha256':expected,'packedSha256':packed_hash,'colorSpace':image.colorspace_settings.name,'dimensions':list(image.size),'usedByTextureNodes':nodes,'encoding':'4K PNG'}
    return {'name':mat.name,'role':role,'assetId':asset,'materialFamily':'white marble with native grey mineral veins' if role=='wall' else 'black marble with restrained native light veins','creationMethod':'PBRProcedural','provider':'ambientCG','sourceUrl':'https://ambientcg.com/view?id='+asset,'license':'CC0-1.0','licenseSource':'assets/textures/room-marble-v20/LICENSE-SOURCE.md','sourceMetadata':{'path':str(source_metadata.relative_to(p.ROOT)),'sha256':p.sha(source_metadata)},'textureImagesPacked':True,'physicalFootprintMetres':tile,'scaleMetadata':'Authored projection calibration; not asserted as vendor physical size','colorGamma':1.045 if role=='wall' else 1.035,'roughness':list(rough_range),'ior':1.52,'specularIORLevel':.5,'normalMapStrength':.22,'heightBumpDistanceMetres':.0001,'heightBumpStrength':.08,'geometryDisplacement':False,'mapping':'Stable world-metre triplanar with reoriented NormalGL perturbations, original geometry and BakeUV untouched','maps':maps}
