import bpy, math
from mathutils import Vector
from common import M,mesh_object,bevel

def catmull(points,steps=10):
    ps=[Vector(p) for p in points];out=[]
    for i in range(len(ps)-1):
        a,b,c,d=ps[max(0,i-1)],ps[i],ps[i+1],ps[min(len(ps)-1,i+2)]
        for j in range(steps):
            t=j/steps
            out.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    out.append(ps[-1]);return out

def beam(name,points,width,depth,normal):
    old=bpy.data.objects.get(name)
    if old:bpy.data.objects.remove(old,do_unlink=True)
    path=catmull(points);n=Vector(normal);verts=[];faces=[]
    for i,p in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(i-1,0)]).normalized();side=n.cross(tangent).normalized()
        for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]:verts.append(tuple(p+side*a*width*.5+n*b*depth*.5))
    for i in range(len(path)-1):
        for k in range(4):faces.append((i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4,(i+1)*4+k))
    faces.extend([(3,2,1,0),tuple((len(path)-1)*4+k for k in range(4))])
    o=mesh_object(name,verts,faces,M['titanium'],bpy.data.collections['ARCHITECTURE']);bevel(o,.028,4)
    try:o.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')
    except:pass
    return o

def apply():
    beam('A_SweepingTopBand',[(-4.88,3.25,4.23),(-3.05,3.25,4.69),(-2.45,3.25,4.71),(-.4,3.25,4.49),(2.15,3.25,4.15),(2.65,3.25,4.18),(3.3,3.25,4.65),(3.72,3.25,4.73),(4.52,3.25,4.67),(4.85,3.25,4.48)],.24,.26,(0,1,0))
    beam('A_LeftTopRail',[(-4.88,-2.45,3.5),(-4.89,-1.6,3.64),(-4.89,.4,3.96),(-4.89,2.15,4.19),(-4.88,3.26,4.26)],.21,.24,(1,0,0))
    beam('A_LeftFrontRail',[(-4.88,-2.45,.22),(-4.88,-2.45,3.45),(-4.88,-2.4,3.5)],.19,.24,(1,0,0))
    light=bpy.data.objects.get('A_WindowRecessLight')
    if light:light.data.bevel_depth=.008
    M['cool_light'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=2.2
    # Shift the plant to cascade over the exterior edge rather than hide inside the vitrine.
    vine=bpy.data.objects.get('P_VINES_Root')
    if vine:vine.location.x+=.25;vine.location.y-=.35
    return {'structural_band':'smooth broad titanium ribbon','window_light':'recessed narrow seam'}
