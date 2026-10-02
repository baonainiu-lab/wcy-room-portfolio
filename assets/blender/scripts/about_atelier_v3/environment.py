"""Physical architecture, distant terrain and daylight. No image backdrop."""
import bpy, math, random
from mathutils import Vector
import kit as K
from dressing import plant

def slab(name,points,z0,z1,ma,edge=.012):
    n=len(points);v=[(x,y,z) for z in [z0,z1] for x,y in points]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=K.mesh(name,v,faces,ma);K.bevel(o,edge,3);return o

def platform():
    outline=[(-3.75,-2.26),(-3.40,-2.67),(3.34,-2.67),(3.78,-2.20),(3.78,1.99),(3.40,2.33),(-3.40,2.33),(-3.75,1.99)]
    K.box('atelier.plinth.recessed.support',(0,0,.023),(6.80,4.40,.054),K.M['dark'],None,.01)
    slab('atelier.plinth.brass.foot',outline,.035,.062,K.M['brass'],.009)
    slab('atelier.plinth.navy.body',outline,.062,.269,K.M['navy'],.014)
    slab('atelier.plinth.terrazzo',outline,.269,.36,K.M['stone'],.009)
    p=K.root('atelier.return.interface',(2.80,-2.679,.169));p['interaction']='return_room'
    K.panel_label('return','返回房间  →',(0,0,0),1.02,.15,p)
    bt=K.cylinder('return.physical.button',(.59,-.002,0),.048,.018,K.M['brass'],p);bt.rotation_euler.x=math.pi/2
    led=K.cylinder('return.indicator',(.59,-.014,0),.022,.005,K.M['light'],p);led.rotation_euler.x=math.pi/2

def surface_mat(name,c0,c1,rough=.4,scale=1):
    m=K.mat(name,c0,0,rough);n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
    co=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=4;noise.inputs['Roughness'].default_value=.7
    l.new(co.outputs['Object'],noise.inputs['Vector']);r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=K.srgb(c0);r.color_ramp.elements[1].color=K.srgb(c1)
    l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color']);b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.17;b.inputs['Distance'].default_value=.002
    l.new(noise.outputs['Fac'],b.inputs['Height']);l.new(b.outputs['Normal'],p.inputs['Normal']);return m

def mountains(name,y,height,ma,seed):
    rng=random.Random(seed);nx,ny=160,30;verts=[];faces=[]
    peaks=[(rng.uniform(-65,65),rng.uniform(5,17),rng.uniform(.4,1)) for _ in range(12)]
    for j in range(ny+1):
        yy=y+j*.85
        for i in range(nx+1):
            x=-80+i;ridge=.64+.18*math.sin(x*.18+seed)+.11*math.sin(x*.47)+.065*math.sin(x*1.21)+.028*math.sin(x*2.72)
            wave=math.sin(j/ny*math.pi)**.7
            z=-1.8+height*ridge*wave+math.sin(x*1.7+j)*.09
            verts.append((x,yy,z))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
    o=K.mesh(name,verts,faces,ma)
    for f in o.data.polygons:f.use_smooth=True

def surroundings():
    floor=surface_mat('atrium.honed.limestone','8D8275','C1B4A1',.29,1.7)
    concrete=surface_mat('atrium.limestone.wall','948573','C8B599',.58,3.4)
    for i in range(-3,4):
        for j in range(-2,2):K.box('context.limestone.tile',(i*3.5,j*3.5,-.044),(3.495,3.495,.080),floor,None,.002)
    for x in [-5.5,.0,5.5]:
        # The central pier is shifted left of the award feature to keep a clean silhouette.
        xx=-4.7 if x==0 else x
        K.box('context.window.pier',(xx,5.0,3.6),(.28,.40,7.3),concrete,None,.014)
    for x in [-6.1,-2.8,.5,3.8,7.1]:
        K.box('context.window.mullion',(x,5.0,3.6),(.054,.105,7.2),K.M['navy'],None,.005)
    for z in [.09,6.8]:K.box('context.window.horizontal',(.5,5.0,z),(14.0,.1,.058),K.M['navy'],None,.004)
    for x in [-4.45,-1.15,2.15,5.45]:
        K.box('context.window.glazing',(x,5.035,3.5),(3.25,.014,6.88),K.M['glass'],None,.001)
    # A side window catches sunlight and casts the long narrow shadow bands.
    for y in [-5.6,-2.95,-.3,2.35,5.0]:K.box('context.side.mullion',(-5.5,y,3.5),(.09,.055,7),K.M['navy'],None,.004)
    for y in [-4.275,-1.625,1.025,3.675]:K.box('context.side.glazing',(-5.52,y,3.5),(.014,2.59,6.9),K.M['glass'],None,.001)
    # Low-iron panes retain camera/reflection transmission; shadow rays pass
    # straight through so the architecture's mullions form readable sunlight.
    for pane in bpy.context.scene.objects:
        if 'context.' in pane.name and 'glazing' in pane.name:pane.visible_shadow=False
    plant('context.plant.right',(5.6,3.4,0),2.5,.45)
    plant('context.plant.left',(-4.65,3.4,0),2.1,.40)
    # Low bench at right background, kept separate from the actual portfolio assets.
    K.box('context.bench.wood',(6.0,4.0,.46),(1.7,.56,.12),K.M['wood'],None,.026)
    K.box('context.bench.fabric',(6.0,4.0,.56),(1.72,.58,.12),K.M['fabric'],None,.048)
    for x in [5.3,6.7]:K.box('context.bench.leg',(x,4,.24),(.08,.45,.4),K.M['navy'],None,.012)
    for name,loc,dims in [('front.left',(-3.5,-3.5,.006),(3.7,1.5,.012)),('right',(4.4,-.4,.006),(1.1,3.5,.012))]:
        rug=K.box('context.rug.'+name,loc,dims,K.M['fabric'],None,.006)
        for i in range(52):
            x=loc[0]-dims[0]*.48+dims[0]*.96*i/51
            K.tube('rug.fringe',[(x,loc[1]-dims[1]/2,.011),(x+.01,loc[1]-dims[1]/2-.055,.006)],.003,K.M['fabric'])

def lighting():
    s=bpy.context.scene;s.world=bpy.data.worlds.new('Atelier physical daylight');s.world.use_nodes=True
    n=s.world.node_tree.nodes;l=s.world.node_tree.links;n.clear()
    out=n.new('ShaderNodeOutputWorld');bg=n.new('ShaderNodeBackground')
    env=n.new('ShaderNodeTexEnvironment');env.name='CC0 Lake Pier Environment'
    im=bpy.data.images.load(str(K.PROJECT/'assets/textures/about-atelier-v3/landscape/lake_pier_2k.hdr'));im.pack();im['license']='CC0-1.0';im['author']='Alexander Scholten / Poly Haven';env.image=im
    tc=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeMapping');mapping.name='Lake panorama orientation';mapping.inputs['Rotation'].default_value=(math.radians(12),0,math.radians(90))
    l.new(tc.outputs['Generated'],mapping.inputs[0]);l.new(mapping.outputs[0],env.inputs['Vector'])
    bg.inputs['Strength'].default_value=.50;l.new(env.outputs['Color'],bg.inputs['Color']);l.new(bg.outputs[0],out.inputs['Surface'])
    sun=K.light('day.sun',(-8,-4.5,6.1),4.0,(1,.81,.59),.1,(0,0,0),'SUN');sun.data.angle=math.radians(.8)
    K.light('day.window.skyfill',(-5,-.5,6),120,(.73,.85,1),5,(0,0,1.3))
    K.light('day.camera.bounce',(2,-6,5),80,(1,.93,.83),5,(0,0,1.8))
    K.light('day.glass.rim',(-3,4.2,5.4),80,(1,.77,.48),3,(-1,1,2.5))
    for ob in list(s.objects):
        if ob.type=='LIGHT' and ob.name.startswith('day.') and ob.data.type=='AREA':bpy.data.objects.remove(ob,do_unlink=True)
    K.light('warm.awards',(-1.15,.56,3.70),28,(1,.65,.29),.55,(-1,.85,2.15))
    K.light('warm.desk',(.95,.74,2.8),38,(1,.72,.39),.32,(1.1,-.2,1.65))

def build():
    platform();surroundings();lighting()
