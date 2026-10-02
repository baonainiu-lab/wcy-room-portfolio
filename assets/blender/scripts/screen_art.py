"""Original layered orange/ice-blue ribbon sculpture for the main display.

Creates a separate Cycles scene. No render invocation, external assets, scene
switch, or modifications to the room. All surfaces have real folded depth.
"""
import math
import random
import bpy
from mathutils import Vector


def build_screen_art(output_path, width=1200, height=500):
    rng = random.Random(909024)
    scene = bpy.data.scenes.new("SCREEN_ART")
    collection = bpy.data.collections.new("SCREEN_ART_CONTENT")
    scene.collection.children.link(collection)

    def mesh(name, vertices, faces, material):
        data=bpy.data.meshes.new(name+"_Mesh")
        data.from_pydata(vertices,[],faces)
        data.update()
        obj=bpy.data.objects.new(name,data)
        collection.objects.link(obj)
        data.materials.append(material)
        for polygon in data.polygons:
            polygon.use_smooth=True
        return obj

    def material(name,color,metallic,transmission,roughness=.14):
        mat=bpy.data.materials.new("SCREEN_"+name)
        mat.use_nodes=True
        bs=mat.node_tree.nodes.get("Principled BSDF")
        bs.inputs["Base Color"].default_value=(*color,1)
        bs.inputs["Metallic"].default_value=metallic
        bs.inputs["Roughness"].default_value=roughness
        bs.inputs["Transmission Weight"].default_value=transmission
        bs.inputs["IOR"].default_value=1.46
        bs.inputs["Coat Weight"].default_value=.55
        bs.inputs["Coat Roughness"].default_value=.10
        if "Anisotropic IOR Level" in bs.inputs:
            bs.inputs["Anisotropic IOR Level"].default_value=.35
        return mat

    copper=material("Burnished_Amber",(.80,.19,.029),.60,.20,.13)
    amber_glass=material("Honey_Glass",(.72,.26,.065),.25,.70,.105)
    gold=material("Pale_Gold_Folds",(.86,.49,.15),.68,.12,.16)
    ice=material("Ice_Blue_Glass",(.29,.64,.86),.36,.56,.115)
    blue=material("Blue_Silver",(.16,.43,.65),.66,.20,.15)
    silver=material("Frosted_Platinum",(.63,.83,.91),.72,.12,.15)

    def emissive(name,color,strength):
        mat=bpy.data.materials.new("SCREEN_"+name)
        mat.use_nodes=True
        n=mat.node_tree.nodes
        n.clear()
        out=n.new("ShaderNodeOutputMaterial")
        em=n.new("ShaderNodeEmission")
        em.inputs["Color"].default_value=(*color,1)
        em.inputs["Strength"].default_value=strength
        mat.node_tree.links.new(em.outputs[0],out.inputs[0])
        return mat

    edge_orange=emissive("Amber_Edge",(1,.31,.055),.8)
    edge_blue=emissive("Ice_Edge",(.37,.77,1),.85)
    star_mat=emissive("Tiny_Stars",(.54,.69,.80),1.1)

    def curve(name,points,radius,mat):
        data=bpy.data.curves.new(name+"_Curve","CURVE")
        data.dimensions="3D"
        data.bevel_depth=radius
        data.bevel_resolution=2
        spline=data.splines.new("POLY")
        spline.points.add(len(points)-1)
        for p,co in zip(spline.points,points):
            p.co=(*co,1)
        obj=bpy.data.objects.new(name,data)
        collection.objects.link(obj)
        data.materials.append(mat)
        return obj

    def sphere(name,position,radius,mat,segments=40,rings=24):
        vertices=[]
        faces=[]
        for j in range(rings+1):
            v=math.pi*j/rings
            for i in range(segments):
                u=math.tau*i/segments
                vertices.append((position[0]+radius*math.sin(v)*math.cos(u),
                                 position[1]+radius*math.sin(v)*math.sin(u),
                                 position[2]+radius*math.cos(v)))
        for j in range(rings):
            for i in range(segments):
                faces.append((j*segments+i,(j+1)*segments+i,
                              (j+1)*segments+(i+1)%segments,j*segments+(i+1)%segments))
        return mesh(name,vertices,faces,mat)

    def ribbon(name,angle,length,spread,depth,twist,material_,edge_material,
               curl=.6,offset=0,arch=.0,steps=68,cross_steps=10):
        """A twisted leaf with a curved Bezier-like spine and folded cross section.

        Width and cross-section curl are independent. This creates thin pointed
        leaves that alternately expose their broad face and reflective edge.
        """
        vertices=[]
        left=[]
        right=[]
        for i in range(steps+1):
            t=i/steps
            # Swirl around the shared knot before opening into a long tip.
            direction=angle+curl*(1-t)**1.8
            radial=length*(.04+.96*t)
            x=radial*math.cos(direction)-.38
            z=radial*math.sin(direction)*.70+arch*math.sin(t*math.pi)
            y=depth*math.sin(math.pi*t)+.27*math.sin(t*math.tau+offset)
            y+=.22*(1-t)*math.sin(offset)
            # Controlled sigmoid twist: thick folded base, opening leaf, tip flip.
            rotation=twist*(t-.45)+.40*math.sin(t*math.tau+offset)
            width_=spread*(math.sin(math.pi*t)**.78)*(.55+.7*t)+.006
            perp=Vector((-math.sin(direction),0,math.cos(direction)))
            broad=perp*math.cos(rotation)+Vector((0,math.sin(rotation),0))
            normal=Vector((0,math.cos(rotation),0))-perp*math.sin(rotation)
            center=Vector((x,y,z))
            for j in range(cross_steps+1):
                s=2*j/cross_steps-1
                # A folded central vein and two curled edges make real highlights.
                fold=.18*spread*(abs(s)**1.45)*math.sin(math.pi*t)
                fold+=.055*spread*math.sin(s*math.pi*2+t*math.pi*3+offset)*math.sin(math.pi*t)
                fold+=.15*spread*s*s*math.sin(t*math.pi*1.35+offset)
                point=center+broad*(s*width_)+normal*fold
                vertices.append(tuple(point))
                if j==0:
                    left.append(tuple(point))
                elif j==cross_steps:
                    right.append(tuple(point))
        faces=[]
        stride=cross_steps+1
        for i in range(steps):
            for j in range(cross_steps):
                k=i*stride+j
                faces.append((k,k+1,k+stride+1,k+stride))
        obj=mesh(name,vertices,faces,material_)
        solid=obj.modifiers.new("Real thin glass-metal wall","SOLIDIFY")
        solid.thickness=.014
        solid.offset=0
        solid.use_even_offset=True
        # These barely luminous edges emphasize the leaf's 3D contour.
        curve(name+"_Rim_A",left,.0042,edge_material)
        curve(name+"_Rim_B",right,.0034,edge_material)
        return obj

    # Deliberately uneven: broad overlapping petals, long needle tips, and
    # several folded sheets pointing partly at the camera rather than a flat fan.
    warm_specs=[
        (89,2.25,.48,-.40,2.0,.84,.38),
        (108,2.42,.48,.26,-1.5,.72,.20),
        (130,2.30,.66,-.10,2.4,.98,.04),
        (150,2.92,.48,.62,-1.8,.62,.00),
        (170,3.35,.43,-.30,1.2,.57,.10),
        (191,3.02,.35,.15,-2.7,.85,.00),
        (207,2.40,.60,-.50,1.9,.85,-.02),
        (227,2.57,.32,.54,-1.8,.90,.00),
        (251,1.84,.43,-.18,2.3,1.08,.06),
        (276,1.48,.23,.70,-1.4,.75,.03),
        (117,1.73,.58,-.64,3.8,1.30,.05),
        (153,1.94,.22,-.71,-2.5,1.34,.10),
        (203,1.65,.25,-.66,2.8,1.45,.00),
    ]
    cool_specs=[
        (77,2.59,.47,.30,-1.4,-.49,.20),
        (59,3.06,.44,-.40,1.7,-.75,.10),
        (42,3.37,.47,.55,-2.8,-.76,.08),
        (23,3.51,.45,-.22,1.8,-.73,.03),
        (6,3.74,.30,.42,-2.2,-.66,.08),
        (-12,3.55,.39,-.60,2.6,-.82,.00),
        (-30,2.87,.46,.15,-1.2,-.74,-.05),
        (-49,2.63,.37,-.32,1.9,-.60,.00),
        (-67,1.77,.35,.58,-2.5,-1.1,.00),
        (45,2.14,.54,-.72,3.3,-.80,.05),
        (16,2.25,.37,-.64,-2.9,-1.2,.00),
        (-21,1.98,.27,-.69,2.2,-1.0,.00),
        (85,1.73,.26,-.53,-3.1,-.70,.00),
    ]
    for group,specs,mats,edge in [
        ("Amber",warm_specs,[copper,amber_glass,gold],edge_orange),
        ("Ice",cool_specs,[ice,blue,silver],edge_blue),
    ]:
        for index,(degrees,length,spread,depth,twist,curl,arch) in enumerate(specs):
            ribbon("%s_Folded_Petal_%02d"%(group,index),math.radians(degrees),
                   length,spread,depth,twist,mats[index%3],edge,curl,
                   offset=index*.87,arch=arch)

    # Two elegant, thinner curling strands connect the tips across the knot.
    for index,(color_,phase) in enumerate([(edge_orange,.2),(edge_blue,2.8)]):
        pts=[]
        for j in range(140):
            t=j/139
            a=t*math.tau*.88+phase
            radius=.22+1.95*t
            pts.append((-.38+radius*math.cos(a),-.42+.26*math.sin(a*1.5),
                        radius*.59*math.sin(a)))
        curve("Free_Floating_Filament_%d"%index,pts,.007,color_)

    # Tiny satellite droplets echo the reference without reading as UI graphics.
    sphere("Blue_Orbit_Droplet",(3.13,.12,1.60),.205,silver)
    sphere("Amber_Orbit_Droplet",(-3.33,.22,-.78),.094,copper)
    sphere("Small_Silver_Droplet",(2.45,-.13,-1.34),.055,ice)
    for i in range(48):
        x=rng.uniform(-4.7,4.7)
        z=rng.uniform(-2.2,2.2)
        # Keep the delicate pinpoints mostly outside the solid sculpture.
        if abs(x)<2.5 and abs(z)<1.25:
            continue
        sphere("Distant_Mote_%02d"%i,(x,1.4,z),rng.uniform(.003,.010),
               star_mat,8,4)

    backdrop=emissive("Near_Black_Backdrop",(.0020,.0045,.0067),1)
    mesh("Black_Backdrop",[(-30,3,-15),(30,3,-15),(30,3,15),(-30,3,15)],
         [(0,1,2,3)],backdrop)

    def aim(obj,target):
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

    def area(name,location,target,power,size,color,size_y=None):
        data=bpy.data.lights.new("SCREEN_"+name,"AREA")
        data.energy=power
        data.color=color
        data.shape="RECTANGLE"
        data.size=size
        data.size_y=size_y if size_y is not None else size
        obj=bpy.data.objects.new("SCREEN_"+name,data)
        collection.objects.link(obj)
        obj.location=location
        aim(obj,target)
        return obj

    area("Upper_Softbox",(-1.5,-4.8,5.5),(0,0,0),650,5,(.87,.94,1),2)
    area("Warm_Left_Strip",(-4,-2,1.4),(-1,0,0),420,3,(1,.55,.22),.55)
    area("Ice_Right_Strip",(4.2,-.8,2.2),(1,0,0),550,3.5,(.49,.76,1),.6)
    area("Lower_Rim",(.5,.7,-4),(0,0,0),400,4,(.55,.79,1),.8)
    area("Back_Highlight",(0,2,3),(0,0,0),750,3,(1,.91,.75),1)
    area("Front_Reflection",(0,-5,-.5),(0,0,0),100,4,(.71,.82,1),3)

    world=bpy.data.worlds.new("SCREEN_Black_Studio")
    world.use_nodes=True
    world.node_tree.nodes["Background"].inputs["Color"].default_value=(.028,.045,.065,1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value=.16
    scene.world=world
    data=bpy.data.cameras.new("SCREEN_Camera")
    camera=bpy.data.objects.new("SCREEN_Camera",data)
    collection.objects.link(camera)
    camera.location=(0,-14,.6)
    aim(camera,(0,0,.10))
    data.type="ORTHO"
    data.ortho_scale=9.5
    data.clip_end=100
    scene.camera=camera
    scene.render.engine="CYCLES"
    scene.cycles.device="GPU"
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8
    scene.cycles.transmission_bounces=6
    scene.cycles.transparent_max_bounces=8
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.resolution_percentage=100
    scene.render.film_transparent=False
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.render.filepath=output_path
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=-.20
    return {"scene_name":scene.name,"camera":camera.name,
            "collection":collection.name,"output_path":output_path,
            "width":width,"height":height,"objects":len(collection.objects),
            "license":"Original procedural 3D artwork; no third-party assets"}
