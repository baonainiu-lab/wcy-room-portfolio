"""About Atelier V3 geometry tools; local coordinates, Blender Z up."""
import bpy, bmesh, math
from mathutils import Vector, Matrix
from pathlib import Path
PROJECT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
M={};FONT=None

def srgb(h):
    v=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v)+(1,)

def mat(name,color,metal=0,rough=.4):
    m=bpy.data.materials.new('ATELIER_'+name);m.use_nodes=True;m.diffuse_color=srgb(color)
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=srgb(color)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    return m

def materials():
    from materials import materials as build_materials
    M.clear(); M.update(build_materials()); return M

def root(id,loc=(0,0,0)):
    o=bpy.data.objects.new(id,None);bpy.context.scene.collection.objects.link(o)
    o.location=loc;o['asset_id']=id;o['interactive']=True;o['interaction']='inspect';o['content_status']='placeholder'
    return o

def bevel(o,width=.015,segments=3):
    if not width:return o
    m=o.modifiers.new('Physical edge radius','BEVEL');m.width=width;m.segments=segments;m.harden_normals=True
    m=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');m.keep_sharp=True
    return o

def attach(o,name,loc,ma,parent):
    o.name=name
    if ma:o.data.materials.append(ma)
    o.parent=parent;o.matrix_parent_inverse=Matrix.Identity(4);o.location=loc
    return o

def box(name,loc,dims,ma,parent=None,bevel=.02):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o=bpy.context.object;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    attach(o,name,loc,ma,parent)
    return globals()['bevel'](o,min(bevel,min(dims)*.3),4)

def cylinder(name,loc,radius,depth,ma,parent=None,vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth)
    o=attach(bpy.context.object,name,loc,ma,parent)
    for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
    return bevel(o,min(.014,depth*.18,radius*.13))

def sphere(name,loc,radius,ma,parent=None,scale=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=36,ring_count=20,radius=radius)
    o=bpy.context.object
    if scale:o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for p in o.data.polygons:p.use_smooth=True
    return attach(o,name,loc,ma,parent)

def mesh(name,verts,faces,ma,parent=None):
    d=bpy.data.meshes.new(name);d.from_pydata(verts,[],faces);d.update()
    bm=bmesh.new();bm.from_mesh(d);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.dissolve_degenerate(bm,dist=1e-9,edges=list(bm.edges));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(d);bm.free()
    o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o)
    if ma:d.materials.append(ma)
    o.parent=parent;return o

def tube(name,points,radius,ma,parent=None):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.resolution_u=12;d.bevel_depth=radius;d.bevel_resolution=3
    sp=d.splines.new('POLY');sp.points.add(len(points)-1)
    for p,v in zip(sp.points,points):p.co=(*v,1)
    o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o)
    if ma:d.materials.append(ma)
    o.parent=parent;return o

def text(name,body,loc,size,ma,parent=None,rotation=(math.pi/2,0,0)):
    global FONT
    if FONT is None:FONT=bpy.data.fonts.load(str(PROJECT/'assets/font-candidates/v4/douyin-upstream/DouyinSans/DouyinSansBold.ttf'))
    d=bpy.data.curves.new(name,'FONT');d.font=FONT;d.body=body;d.size=size;d.align_x='CENTER';d.align_y='CENTER'
    d.extrude=.0006;d.bevel_depth=.0002;d.resolution_u=6;d.bevel_resolution=2
    o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o);o.parent=parent;o.location=loc;o.rotation_euler=rotation
    if ma:d.materials.append(ma)
    return o

def torus(name,loc,radius,minor,ma,parent=None,rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=96,minor_segments=12,major_radius=radius,minor_radius=minor)
    o=attach(bpy.context.object,name,loc,ma,parent)
    if rotation:o.rotation_euler=rotation
    for f in o.data.polygons:f.use_smooth=True
    return o

def arc(name,center,ri,ro,z0,z1,a0,a1,ma,parent=None,edge=.01):
    # Closed annulus has welded end topology, open sectors have solid end caps.
    closed=abs(a1-a0-360)<1e-5;n=max(12,int((a1-a0)/3))
    N=n if closed else n+1;verts=[]
    for i in range(N):
        a=math.radians(a0+(a1-a0)*i/n);c=math.cos(a);s=math.sin(a)
        verts +=[(ri*c,ri*s,z0),(ro*c,ro*s,z0),(ri*c,ri*s,z1),(ro*c,ro*s,z1)]
    faces=[]
    for i in range(n):
        a=i*4;b=((i+1)%N)*4
        faces +=[(a,b,b+2,a+2),(a+1,a+3,b+3,b+1),(a+2,b+2,b+3,a+3),(a,a+1,b+1,b)]
    if not closed:faces +=[(0,2,3,1),((N-1)*4,(N-1)*4+1,(N-1)*4+3,(N-1)*4+2)]
    o=mesh(name,verts,faces,ma,parent);o.location=center
    return bevel(o,min(edge,(ro-ri)*.12,(z1-z0)*.2))

def rod(name,p0,p1,radius,ma,parent=None):
    mid=(Vector(p0)+Vector(p1))/2;length=(Vector(p1)-Vector(p0)).length
    o=cylinder(name,mid,radius,length,ma,parent)
    o.rotation_euler=(Vector(p1)-Vector(p0)).to_track_quat('Z','Y').to_euler();return o

def light(name,loc,power,color,size,target=None,kind='AREA'):
    d=bpy.data.lights.new(name,kind);d.energy=power;d.color=color
    if kind=='AREA':d.shape='DISK';d.size=size
    elif kind=='POINT':d.shadow_soft_size=size
    o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o);o.location=loc
    if target:o.rotation_euler=(Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    return o

def api():return dict(root=root,box=box,cylinder=cylinder,sphere=sphere,tube=tube,mesh=mesh,text=text,mats=M)


def lathe(name,profile,ma,parent=None,segments=96):
    verts=[]; faces=[]
    for radius,z in profile:
        for i in range(segments):
            a=2*math.pi*i/segments;verts.append((radius*math.cos(a),radius*math.sin(a),z))
    for j in range(len(profile)-1):
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    o=mesh(name,verts,faces,ma,parent)
    for f in o.data.polygons:f.use_smooth=True
    return o

def screw(name,loc,ma,parent=None,rotation=(math.pi/2,0,0),r=.018):
    o=cylinder(name,loc,r,.008,ma,parent,24);o.rotation_euler=rotation
    return o

def panel_label(name,body,loc,w,h,parent=None):
    p=box(name+'.plaque',loc,(w,.014,h),M['brass'],parent,.008)
    text(name+'.text',body,(loc[0],loc[1]-.009,loc[2]),min(h*.37,w/max(len(body),1)*.85),M['ink'],parent)
    for dx in [-w*.43,w*.43]: screw(name+'.rivet',(loc[0]+dx,loc[1]-.012,loc[2]),M['brass'],parent,r=.006)
    return p
