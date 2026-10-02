"""Original, editable Blender construction kit for the approved gallery B."""
import bpy, math
from pathlib import Path
from mathutils import Vector
M = {}
ROOT = Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')

def init_materials():
    colors = {'silver':((.52,.61,.70),.88,.26),'navy':((.024,.045,.070),.42,.32),
      'bronze':((.49,.28,.10),.8,.29),'ivory':((.74,.72,.62),.05,.43),
      'black':((.01,.017,.023),.3,.31),'glass':((.69,.84,.89),0,.085),
      'warm':((1,.65,.27),.1,.26),'leather':((.33,.095,.032),0,.43),
      'leaf':((.055,.15,.026),0,.5),'soil':((.032,.022,.012),0,.95),
      'paper':((.81,.76,.65),0,.75),'ink':((.045,.039,.032),0,.8),
      'terrazzo':((.59,.58,.52),.05,.40)}
    for key,(color,metal,rough) in colors.items():
        mat=bpy.data.materials.new('GALLERY_'+key);mat.use_nodes=True
        tree=mat.node_tree;p=tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
        if key=='glass':
            p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.45
            clear=tree.nodes.new('ShaderNodeBsdfTransparent')
            mix=tree.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.035
            tree.links.new(clear.outputs[0],mix.inputs[1]);tree.links.new(p.outputs[0],mix.inputs[2]);tree.links.new(mix.outputs[0],tree.nodes.get('Material Output').inputs['Surface'])
        elif key=='warm':
            p.inputs['Emission Color'].default_value=(1,.54,.19,1);p.inputs['Emission Strength'].default_value=2.3
        elif key in {'silver','leather','terrazzo','navy','paper'}:
            tex=tree.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value={'silver':220,'leather':140,'terrazzo':280,'navy':200,'paper':180}[key]
            tex.inputs['Detail'].default_value=2
            coords=tree.nodes.new('ShaderNodeTexCoord');tree.links.new(coords.outputs['Generated'],tex.inputs['Vector'])
            bump=tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.10 if key!='terrazzo' else .16;bump.inputs['Distance'].default_value=.006
            tree.links.new(tex.outputs['Fac'],bump.inputs['Height']);tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
            if key=='terrazzo':
                ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.27;ramp.color_ramp.elements[0].color=(.39,.38,.34,1);ramp.color_ramp.elements[1].position=.43;ramp.color_ramp.elements[1].color=(.68,.64,.55,1)
                tree.links.new(tex.outputs['Fac'],ramp.inputs[0]);tree.links.new(ramp.outputs[0],p.inputs['Base Color'])
        M[key]=mat
    return M

def attach(obj,mat,parent):
    if mat is not None:obj.data.materials.append(mat)
    if parent:
        bpy.context.view_layer.update();mx=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=mx
    return obj

def group(name,loc=(0,0,0),parent=None,atlas=2):
    obj=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(obj);obj.location=loc
    obj['asset_id']=name;obj['bake_atlas']=atlas;obj['interactive']=not name.startswith(('gallery.architecture','gallery.environment'))
    if parent:attach(obj,None,parent)
    return obj

def finish(obj,mat,parent,radius=0):
    attach(obj,mat,parent)
    if radius:
        b=obj.modifiers.new('Manufactured edge radius','BEVEL');b.width=radius;b.segments=4
        b.affect='EDGES'
        n=obj.modifiers.new('Face-weighted normals','WEIGHTED_NORMAL');n.keep_sharp=True;n.weight=50
    return obj

def box(name,loc,dims,mat,parent=None,radius=.03):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);obj=bpy.context.object;obj.name=name;obj.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(obj,mat,parent,min(radius,min(dims)*.48) if radius else 0)

def cyl(name,loc,radius,depth,mat,parent=None,rotation=None,vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc);obj=bpy.context.object;obj.name=name
    if rotation:obj.rotation_euler=rotation
    for p in obj.data.polygons:p.use_smooth=len(p.vertices)==4
    return finish(obj,mat,parent,min(.018,radius*.12,depth*.2))

def sphere(name,loc,scale,mat,parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=loc);obj=bpy.context.object;obj.name=name;obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for p in obj.data.polygons:p.use_smooth=True
    return finish(obj,mat,parent)

def torus(name,loc,major,minor,mat,parent=None,rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=10,location=loc);obj=bpy.context.object;obj.name=name
    if rotation:obj.rotation_euler=rotation
    for p in obj.data.polygons:p.use_smooth=True
    return finish(obj,mat,parent)

def tube(name,points,radius,mat,parent=None,closed=False):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=12;data.bevel_depth=radius;data.bevel_resolution=3
    spline=data.splines.new('POLY');spline.points.add(len(points)-1)
    for p,v in zip(spline.points,points):p.co=(*v,1)
    spline.use_cyclic_u=closed;obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);return attach(obj,mat,parent)

def mesh(name,verts,faces,mat,parent=None):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update();obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);return attach(obj,mat,parent)

def outline(width,height,radius,steps=14):
    r=min(radius,width/2,height/2);points=[]
    for cx,cy,start in [(width/2-r,height/2-r,0),(-width/2+r,height/2-r,90),(-width/2+r,-height/2+r,180),(width/2-r,-height/2+r,270)]:
        for i in range(steps+1):
            a=math.radians(start+i*90/steps);points.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return points

def rounded_rect(name,center,width,height,depth,radius,mat,parent=None,plane='XZ'):
    pts=outline(width,height,radius);N=len(pts);cx,cy,cz=center;verts=[]
    for d in [-depth/2,depth/2]:
        for u,v in pts:
            verts.append((cx+u,cy+d,cz+v) if plane=='XZ' else (cx+u,cy+v,cz+d))
    faces=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
    obj=mesh(name,verts,faces,mat,parent)
    # The XZ basis reverses orientation relative to XY.
    if plane=='XZ':
        for poly in obj.data.polygons:poly.flip()
    return finish(obj,None,None,min(.008,depth*.1))

def label(name,text,loc,size,mat,parent=None,rotation=(math.pi/2,0,0)):
    data=bpy.data.curves.new(name,'FONT');data.body=text;data.size=size;data.extrude=.0007;data.bevel_depth=.0004;data.align_x='LEFT'
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=rotation;return attach(obj,mat,parent)

def area(name,loc,target,power,color,size=2):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=color;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();obj['export_exclude']=True;obj['base_power']=power;return obj
