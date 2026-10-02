"""Reproducible Blender scene assembly for the approved V2 concept.
Executed via the Blender MCP bridge. No website assets are replaced here.
"""
import bpy, math, os, json, importlib
import numpy as np
from mathutils import Vector
from pathlib import Path
import common
from common import *


def rr(cx,cy,w,h,r,n=12):
    p=[]
    for x,y,a in [(cx+w/2-r,cy+h/2-r,0),(cx-w/2+r,cy+h/2-r,90),(cx-w/2+r,cy-h/2+r,180),(cx+w/2-r,cy-h/2+r,270)]:
        for i in range(n+1):
            t=math.radians(a+90*i/n);p.append((x+r*math.cos(t),y+r*math.sin(t)))
    return p

def extrude(name,path,z0,z1,mat,coll):
    n=len(path);verts=[(x,y,z) for z in [z0,z1] for x,y in path]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh_object(name,verts,faces,mat,coll)

def xz_panel(name,path,y0,y1,mat,coll):
    n=len(path);verts=[(x,y,z) for y in [y0,y1] for x,z in path]
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
    return mesh_object(name,verts,faces,mat,coll)

def xz_ring(name,outer,inner,y0,y1,mat,coll):
    n=len(outer);verts=[(x,y,z) for y in [y0,y1] for path in [outer,inner] for x,z in path];f=[]
    for i in range(n):
        j=(i+1)%n
        f.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)])
    ob=mesh_object(name,verts,f,mat,coll);bevel(ob,.025,3);return ob

def emission_image(name,image,strength=1):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission');tx=n.new('ShaderNodeTexImage');tx.image=image
    m.node_tree.links.new(tx.outputs['Color'],em.inputs['Color']);em.inputs['Strength'].default_value=strength;m.node_tree.links.new(em.outputs[0],out.inputs['Surface']);return m

def screen_texture():
    h,w=480,1024;y,x=np.mgrid[0:h,0:w];xx=(x-w*.5)/(w*.5);yy=(y-h*.5)/(h*.5)
    radius=np.sqrt(xx**2+(yy*.65)**2);ang=np.arctan2(yy*.65,xx)
    arr=np.zeros((h,w,3),dtype=np.float32);arr[:]=(.006,.012,.022)
    glow=np.zeros((h,w));colour=np.zeros((h,w,3))
    for i in range(13):
        a=i*math.tau/13+.22
        d=(ang-a+math.pi)%math.tau-math.pi
        center=.28+.11*np.sin(d*4+i)
        vein=np.exp(-((radius-(.13+.45*np.cos(d*.9)**2))/.011)**2)*np.exp(-(d/.19)**2)
        inner=np.exp(-((d-(radius-.3)*(.65 if i%2 else -.8))/.028)**2)*np.exp(-((radius-.4)/.29)**2)
        petal=(vein*.8+inner*.9)
        c=np.array([1,.28,.04]) if i<6 else np.array([.24,.7,1])
        arr+=petal[:,:,None]*c
    core=np.exp(-radius**2/.004);arr+=core[:,:,None]*np.array([1,.55,.12])
    rng=np.random.default_rng(315)
    for _ in range(55):
        px=rng.integers(0,w);py=rng.integers(0,h);rrr=rng.uniform(.4,1.1)
        star=np.exp(-((x-px)**2+(y-py)**2)/(rrr*rrr));arr+=star[:,:,None]*.25
    arr=np.clip(arr,0,1)
    return make_image('Original_Generative_Screen',arr,ROOT/'assets/textures/screen-art.png',False)

def area(name,loc,target,power,size,color,coll):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    ob=bpy.data.objects.new(name,d);coll.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();return ob

def build():
    scene=bpy.data.scenes.new('ORBITAL_ATELIER_V2');bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    init_materials()
    arch=collection('ARCHITECTURE');lights=collection('LIGHTING');tech=collection('WORKSTATION');stage=collection('STUDIO_NON_EXPORT')
    # Full soft-corner platform and the narrow floating shadow gap.
    floorroot=group('A_Platform',coll=arch);floorroot['asset_id']='architecture.platform'
    for o in [extrude('A_LowerShadow',rr(0,0,9.75,6.9,.55),-.18,-.06,M['black'],arch),extrude('A_SilverPlinth',rr(0,0,10.15,7.2,.62),-.06,.11,M['titanium'],arch),extrude('A_FloorSurface',rr(0,0,9.95,7.02,.53),.11,.18,M['floor'],arch)]:
        bevel(o,.028,3);parent_keep(o,floorroot)
    outline=rr(0,0,9.96,7.04,.54)
    tube('A_FloorEdgePrecisionSeam',[(x,y,.18) for x,y in outline],.014,M['titanium'],arch,True)
    for x in [-3.8,-1.9,0,1.9,3.8]:
        tube('A_FloorJointX',[(x,-3.12,.185),(x,3.0,.185)],.003,M['graphite'],arch)
    for y in [-2.2,-.65,.9,2.45]:
        tube('A_FloorJointY',[(-4.55,y,.185),(4.55,y,.185)],.003,M['graphite'],arch)
    # Sculptural two-wall enclosure: dark backing + satin exposed structural bands.
    back_outline=[(-4.96,.18),(4.96,.18),(4.96,4.48),(4.72,4.66),(4.32,4.74),(3.62,4.78),(3.28,4.68),(2.76,4.29),(2.30,4.19),(-.4,4.54),(-2.45,4.77),(-3.05,4.73),(-4.7,4.35),(-4.96,4.16)]
    backing=xz_panel('A_BackWall_Graphite',back_outline,3.31,3.58,M['graphite'],arch);bevel(backing,.16,6)
    backouter=tube('A_SweepingTopBand',[(x,3.26,z) for x,z in back_outline[2:]],.11,M['titanium'],arch)
    leftverts=[(-4.93,-2.45,.18),(-4.93,3.4,.18),(-4.93,3.4,4.26),(-4.93,-2.45,3.50)]
    left=mesh_object('A_LeftWallInner',leftverts,[(0,1,2,3)],M['graphite'],arch)
    sol=left.modifiers.new('Structural wall thickness','SOLIDIFY');sol.thickness=.22;bevel(left,.12,6)
    tube('A_LeftTopRail',[(-4.88,-2.39,3.53),(-4.9,-1.4,3.67),(-4.9,.4,3.95),(-4.9,2,4.17),(-4.9,3.36,4.32)],.11,M['titanium'],arch)
    tube('A_LeftFrontRail',[(-4.88,-2.43,.2),(-4.88,-2.43,3.5)],.075,M['titanium'],arch)
    tube('A_LeftSkirting',[(-4.77,-2.35,.32),(-4.77,3.17,.32),(4.7,3.17,.32)],.045,M['titanium'],arch)
    # The window is a physical recessed rounded frame with a Blender-rendered city plate.
    outer=rr(.25,2.97,6.30,2.82,.45);inner=rr(.25,2.97,5.96,2.49,.32)
    xz_ring('A_PanoramaTitaniumBezel',outer,inner,3.08,3.35,M['titanium'],arch)
    tube('A_WindowRecessLight',[(x,3.073,z) for x,z in inner],.018,M['cool_light'],arch,True)
    plane_path=rr(.25,2.97,5.92,2.45,.30)
    window=xz_panel('A_Window_CityPanel',plane_path,3.12,3.125,M['black'],arch)
    # Explicit front UVs normalized in XZ, independent from the mesh helper fallback.
    uv=window.data.uv_layers.active
    for poly in window.data.polygons:
        for li in poly.loop_indices:
            v=window.data.vertices[window.data.loops[li].vertex_index].co
            uv.data[li].uv=((v.x-.25+2.96)/5.92,(v.z-(2.97-1.225))/2.45)
    window['texture_role']='Blender-rendered original future city'
    # Under-window continuous cladding.
    for i in range(5):
        x=-2.54+i*1.15
        ob=box('A_UnderWindow_Panel_%02d'%i,(x,3.15,.85),(1.10,.12,1.13),M['graphite'],arch,.035)
    # Narrow sculptural right display tower with three separate lit shelves.
    tower=xz_panel('A_DisplayTowerBack',rr(4.0,2.55,1.55,4.20,.4),3.06,3.30,M['graphite'],arch);bevel(tower,.065,4)
    towerframe=xz_ring('A_DisplayTowerFrame',rr(4.0,2.55,1.65,4.28,.42),rr(4.0,2.55,1.42,4.03,.34),2.55,3.17,M['titanium'],arch)
    for i,z in enumerate([.75,2.0,3.25]):
        shelf=extrude('A_DisplayShelf_%d'%i,rr(4,2.84,1.49,.75,.19),z-.075,z,M['titanium'],arch);bevel(shelf,.018,3)
        tube('A_ShelfWarmStrip_%d'%i,[(3.44,3.03,z+.92),(4.56,3.03,z+.92)],.014,M['warm_light'],arch)
        area('L_Niche_%d'%i,(4,2.70,z+.90),(4,2.84,z+.3),30,.68,(1,.75,.49),lights)
    tube('A_RightSpine_Light',[(4.87,3.01,.65),(4.92,3.0,1.3),(4.77,3.0,2.25),(4.71,3.0,3.5),(4.7,3.0,4.3)],.022,M['cool_light'],arch)
    # Main precision-built display and its independent articulated arm.
    mainroot=group('T_MainDisplay',coll=tech);mainroot['asset_id']='main_display';mainroot['interactive']=True
    bezel=box('T_DisplayBack',(-2.75,2.23,2.68),(3.06,.15,1.35),M['graphite'],tech,.08);parent_keep(bezel,mainroot)
    front=xz_panel('T_DisplayGlass',rr(-2.75,2.68,2.91,1.2,.038),2.139,2.142,emission_image('MAT_MainDisplay_Art',screen_texture(),.8),tech);parent_keep(front,mainroot)
    for poly in front.data.polygons:
        for li in poly.loop_indices:
            v=front.data.vertices[front.data.loops[li].vertex_index].co
            front.data.uv_layers.active.data[li].uv=((v.x+4.205)/2.91,(v.z-2.08)/1.2)
    tube('T_DisplaySilverRim',[(x,2.135,z) for x,z in rr(-2.75,2.68,3.02,1.31,.066)],.018,M['titanium'],tech,True)
    for i,(p0,p1) in enumerate([((-4.28,2.05,1.68),(-4.30,2.4,2.32)),((-4.3,2.4,2.32),(-3.90,2.43,2.80))]):
        tube('T_ArticulatedArm_%d'%i,[p0,p1],.07,M['titanium'],tech)
        uv_sphere('T_ArmPivot_%d'%i,p1,(.11,.11,.11),M['graphite'],tech)
    # Visible glass computer core; core and chassis remain independently accessible.
    core=group('T_ComputeCore',coll=tech);core['asset_id']='compute_core';core['interactive']=True
    ob=box('T_Compute_Chassis',(-3.68,.96,.83),(.85,.65,1.22),M['graphite'],tech,.13);parent_keep(ob,core)
    ob=box('T_Compute_Glass',(-3.68,.607,.83),(.73,.016,1.06),M['glass'],tech,.08);parent_keep(ob,core)
    for r in [.255,.225]:
        ob=torus('T_Compute_InductionRing',(-3.68,.579,.88),r,.018,M['amber_light'],tech,(math.pi/2,0,0));parent_keep(ob,core)
    cylinder('T_Compute_Disc',(-3.68,.59,.88),.18,.022,M['titanium'],tech,(math.pi/2,0,0))
    for x in [-3.98,-3.38]:
        for z in [.40,1.25]:uv_sphere('T_Compute_Bolt',(x,.567,z),(.018,.011,.018),M['titanium'],tech)
    # Camera, environment and physical softboxes.
    world=bpy.data.worlds.new('Orbital_Studio_World');world.use_nodes=True;scene.world=world
    world.node_tree.nodes['Background'].inputs[0].default_value=(.095,.13,.19,1);world.node_tree.nodes['Background'].inputs[1].default_value=.38
    area('L_Key_Softbox',(-3,-5,10),(0,.5,1.3),1800,7,(.82,.91,1),lights)
    area('L_Fill_Front',(7,-5,6),(0,0,1.5),1400,6,(.74,.84,1),lights)
    area('L_Rim',(-2,5,8),(0,0,2),2100,5,(.6,.78,1),lights)
    area('L_Warm_Bounce',(-5,1,5),(-2,1,1),550,3,(1,.75,.51),lights)
    area('L_WindowLight',(.4,2.85,3.45),(0,-1,1),220,3,(.55,.76,1),lights)
    ground=box('STUDIO_Ground',(0,0,-.27),(200,200,.08),material('Studio_Backdrop',(.029,.041,.06),0,.88),stage,.02);ground['export']=False
    camdat=bpy.data.cameras.new('Camera_Reference');cam=bpy.data.objects.new('Camera_Reference',camdat);lights.objects.link(cam)
    cam.location=(12,-18,12.5);target=Vector((0,.35,1.75));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdat.type='ORTHO';camdat.ortho_scale=13.65;camdat.lens=50;scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=64;scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=6
    scene.render.resolution_x=1800;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.render.film_transparent=False;scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.5
    try:scene.view_settings.look='AgX - Medium High Contrast'
    except:pass
    import furniture, props
    importlib.reload(furniture);importlib.reload(props)
    f=furniture.build();p=props.build()
    scene['reference_image']='docs/concepts/v2/room.png';scene['approval_stage']='render_review_pending'
    scene['website_assets_replaced']=False
    bpy.context.view_layer.update()
    return {'scene':scene.name,'furniture':f,'props':p,'objects':len(scene.objects),'camera':cam.name}

if __name__=='__main__':
    result=build()
