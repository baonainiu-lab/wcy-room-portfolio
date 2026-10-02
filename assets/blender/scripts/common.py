"""Shared materials for the V2 Orbital Atelier. Created through Blender MCP."""
import bpy, math, os
import numpy as np
from mathutils import Vector
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
M={}

def make_image(name,arr,path,noncolor=True):
    h,w=arr.shape[:2]
    rgba=np.ones((h,w,4),dtype=np.float32)
    if arr.ndim==2: rgba[:,:,:3]=arr[:,:,None]
    else: rgba[:,:,:3]=arr[:,:,:3]
    im=bpy.data.images.new(name,width=w,height=h,alpha=True,float_buffer=False)
    if noncolor: im.colorspace_settings.name='Non-Color'
    im.pixels.foreach_set(rgba.ravel()); im.filepath_raw=str(path);im.file_format='PNG';im.save();im.pack()
    return im

def material(name,color,metal=0,rough=.4,texture=None,bump=.04,emission=None,transmission=0):
    m=bpy.data.materials.new('MAT_'+name);m.use_nodes=True
    n=m.node_tree.nodes;p=n.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    if transmission: p.inputs['Transmission Weight'].default_value=transmission;p.inputs['IOR'].default_value=1.46
    if emission: p.inputs['Emission Color'].default_value=(*emission[0],1);p.inputs['Emission Strength'].default_value=emission[1]
    if texture:
        tc=n.new('ShaderNodeTexCoord');tex=n.new('ShaderNodeTexImage');tex.image=texture;tex.extension='REPEAT'
        mapping=n.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs[3].default_value=3
        m.node_tree.links.new(tc.outputs['UV'],mapping.inputs[0]);m.node_tree.links.new(mapping.outputs[0],tex.inputs['Vector'])
        ramp=n.new('ShaderNodeMapRange');ramp.inputs['From Min'].default_value=0;ramp.inputs['From Max'].default_value=1
        ramp.inputs['To Min'].default_value=max(.02,rough-.08);ramp.inputs['To Max'].default_value=min(1,rough+.08)
        m.node_tree.links.new(tex.outputs['Color'],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs[0],p.inputs['Roughness'])
        bn=n.new('ShaderNodeBump');bn.inputs['Strength'].default_value=bump;bn.inputs['Distance'].default_value=.025
        m.node_tree.links.new(tex.outputs['Color'],bn.inputs['Height']);m.node_tree.links.new(bn.outputs[0],p.inputs['Normal'])
    return m

def init_materials():
    out=ROOT/'assets/textures';out.mkdir(exist_ok=True,parents=True)
    rng=np.random.default_rng(28);h=w=512;y,x=np.mgrid[0:h,0:w]
    brush=np.clip(.5+.13*np.sin(y*2.7)+rng.normal(0,.035,(h,w)),0,1)
    weave=np.clip(.5+.16*np.sin(x*math.pi/2)*np.cos(y*math.pi/2)+rng.normal(0,.05,(h,w)),0,1)
    grain=np.clip(.5+rng.normal(0,.14,(h,w)),0,1)
    images={k:make_image(k,a,out/(k+'.png')) for k,a in [('titanium_brush',brush),('fabric_weave',weave),('micro_grain',grain)]}
    M.update({
      'titanium':material('Satin_Titanium',(.42,.47,.53),.92,.24,images['titanium_brush'],.1),
      'graphite':material('Graphite_Enamel',(.023,.033,.048),.55,.28,images['micro_grain'],.04),
      'ceramic':material('Ivory_Ceramic',(.68,.73,.74),.12,.2,images['micro_grain'],.025),
      'black':material('Optical_Black',(.006,.009,.015),.4,.18),
      'glass':material('Smoke_Glass',(.11,.17,.21),.2,.12,transmission=.7),
      'orange_fabric':material('Vermilion_Woven',(.55,.085,.022),0,.66,images['fabric_weave'],.21),
      'charcoal_fabric':material('Charcoal_Woven',(.018,.025,.033),0,.78,images['fabric_weave'],.24),
      'rug':material('Graphite_Rug',(.025,.038,.05),0,.92,images['fabric_weave'],.3),
      'floor':material('Titanium_Floor',(.16,.19,.225),.66,.39,images['micro_grain'],.055),
      'cool_light':material('Optical_White',(.55,.85,1),.15,.23,emission=((.50,.8,1),4)),
      'warm_light':material('Warm_White',(.95,.7,.39),0,.3,emission=((1,.77,.46),3)),
      'amber_light':material('Amber_Status',(.95,.23,.015),.2,.2,emission=((1,.26,.02),3.8)),
      'green':material('Botanical_Leaf',(.045,.12,.018),0,.46),
      'soil':material('Soil',(.022,.016,.012),0,.92,images['micro_grain'],.3),
    })
    return M

def collection(name):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c

def group(name,location=(0,0,0),coll=None):
    o=bpy.data.objects.new(name,None);(coll or bpy.context.scene.collection).objects.link(o);o.location=location;o['asset_id']=name;return o

def material_assign(obj,mat):
    if mat:obj.data.materials.append(mat)
    return obj

def smooth(obj):
    if obj.type=='MESH':
        for p in obj.data.polygons:p.use_smooth=True
    return obj

def parent_keep(obj,parent):
    bpy.context.view_layer.update()
    mx=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=mx;return obj

def bevel(obj,width=.05,segments=3):
    mod=obj.modifiers.new('Precision edge radii','BEVEL');mod.width=width;mod.segments=segments
    return obj

def mesh_object(name,verts,faces,mat=None,coll=None):
    me=bpy.data.meshes.new(name+'_mesh');me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);(coll or bpy.context.scene.collection).objects.link(o);material_assign(o,mat)
    # Box projection UV supplied as durable fallback for procedural construction.
    uv=me.uv_layers.new(name='UVMap')
    if verts:
        lo=np.min(np.array(verts),axis=0);hi=np.max(np.array(verts),axis=0);span=np.maximum(hi-lo,.0001)
        for face in me.polygons:
            axes=sorted(range(3),key=lambda k:abs(face.normal[k]))[:2]
            for li in face.loop_indices:
                v=me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv=((v[axes[0]]-lo[axes[0]])/span[axes[0]],(v[axes[1]]-lo[axes[1]])/span[axes[1]])
    return o

def box(name,loc,dims,mat,coll=None,radius=.04):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if coll:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
    material_assign(o,mat)
    if radius:bevel(o,radius,4)
    return o

def uv_sphere(name,loc,scale,mat,coll=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=loc);o=bpy.context.object;o.name=name;o.scale=scale
    if coll:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
    material_assign(o,mat);smooth(o);return o

def cylinder(name,loc,radius,depth,mat,coll=None,rotation=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=depth,location=loc);o=bpy.context.object;o.name=name
    if coll:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
    if rotation:o.rotation_euler=rotation
    material_assign(o,mat);bevel(o,min(.025,radius*.1,depth*.1),3);smooth(o);return o

def torus(name,loc,major,minor,mat,coll=None,rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=12,location=loc);o=bpy.context.object;o.name=name
    if coll:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
    if rotation:o.rotation_euler=rotation
    material_assign(o,mat);smooth(o);return o

def tube(name,points,radius,mat,coll=None,closed=False):
    cr=bpy.data.curves.new(name,'CURVE');cr.dimensions='3D';cr.resolution_u=16;cr.bevel_depth=radius;cr.bevel_resolution=3
    sp=cr.splines.new('POLY');sp.points.add(len(points)-1)
    for p,v in zip(sp.points,points):p.co=(*v,1)
    sp.use_cyclic_u=closed
    o=bpy.data.objects.new(name,cr);(coll or bpy.context.scene.collection).objects.link(o);material_assign(o,mat);return o
