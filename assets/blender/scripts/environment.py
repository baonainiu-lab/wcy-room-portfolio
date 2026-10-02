"""Original procedural window vista for the orbital studio.

All geometry, shaders and compositing are original. No third-party textures.
Run build_environment(...), then render the returned scene from the caller.
Blender 5.1 / EEVEE. Objects are exclusively linked to ENV_CITY_CONTENT.
"""
import bpy
import math
import random
from mathutils import Vector


def build_environment(output_path, width=1536, height=672):
    previous_scene = bpy.context.scene
    rng = random.Random(90117)
    scene = bpy.data.scenes.new("ENV_CITY")
    collection = bpy.data.collections.new("ENV_CITY_CONTENT")
    scene.collection.children.link(collection)

    def mesh(name, vertices, faces, material=None):
        data = bpy.data.meshes.new(name + "_Mesh")
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        collection.objects.link(obj)
        if material:
            data.materials.append(material)
        return obj

    def mat(name, color, metallic=0.0, roughness=0.65, emission=0.0):
        material = bpy.data.materials.new("ENV_" + name)
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*color, 1)
            bsdf.inputs["Emission Strength"].default_value = emission
        return material

    titanium = mat("Titanium", (.18, .29, .38), .50, .31)
    porcelain = mat("Porcelain", (.47, .57, .62), .30, .36)
    dark = mat("Structural_Shadow", (.055, .095, .14), .35, .50)
    windows = mat("Glass", (.025, .092, .16), .64, .19)
    light = mat("Fine_Cyan_Lines", (.65, .88, 1), .2, .28, 1.0)
    far1 = mat("Haze_Layer_1", (.33, .47, .60), 0, .9, .18)
    far2 = mat("Haze_Layer_2", (.45, .59, .69), 0, .9, .26)
    far3 = mat("Haze_Layer_3", (.57, .67, .74), 0, .9, .30)
    stone = mat("Cliff_Stone", (.065, .12, .145), .0, .98)
    vegetation = mat("Cliff_Vegetation", (.05, .12, .075), .0, 1)

    # Facade windows vary per floor without relying on photographic textures.
    # Window walls remain dark enough for the silver mullions to read at 1536px.
    facade = mat("Curtain_Wall_Glass", (.035,.12,.21), .48,.24)
    fn=facade.node_tree.nodes
    fl=facade.node_tree.links
    fbs=fn.get("Principled BSDF")
    fc=fn.new("ShaderNodeTexCoord")
    fw=fn.new("ShaderNodeTexWave")
    fw.wave_type="BANDS"
    fw.bands_direction="Z"
    fw.inputs["Scale"].default_value=17
    fw.inputs["Distortion"].default_value=0
    fr=fn.new("ShaderNodeValToRGB")
    fr.color_ramp.elements[0].position=.12
    fr.color_ramp.elements[0].color=(.018,.055,.085,1)
    fr.color_ramp.elements[1].position=.35
    fr.color_ramp.elements[1].color=(.10,.25,.36,1)
    fl.new(fc.outputs["Generated"],fw.inputs["Vector"])
    fl.new(fw.outputs["Fac"],fr.inputs[0])
    fl.new(fr.outputs[0],fbs.inputs["Base Color"])

    def lathe(name, x, y, z, profile, material, sides=16):
        verts = []
        for radius, height_ in profile:
            for i in range(sides):
                a = i * math.tau / sides
                verts.append((x + radius * math.cos(a), y + radius * math.sin(a), z + height_))
        faces = []
        for j in range(len(profile) - 1):
            for i in range(sides):
                faces.append((j*sides+i, j*sides+(i+1)%sides,
                              (j+1)*sides+(i+1)%sides, (j+1)*sides+i))
        faces.append(tuple(range(sides-1, -1, -1)))
        faces.append(tuple((len(profile)-1)*sides+i for i in range(sides)))
        obj = mesh(name, verts, faces, material)
        for poly in obj.data.polygons:
            poly.use_smooth = sides >= 24
        return obj

    def box(name, position, size, material, bevel=0.0):
        x, y, z = position
        a, b, c = [v*.5 for v in size]
        verts = [(x+dx*a,y+dy*b,z+dz*c) for dx,dy,dz in
                 [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),
                  (1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
        obj = mesh(name, verts, [(0,4,6,2),(1,3,7,5),(0,1,5,4),
                                (2,6,7,3),(0,2,3,1),(4,5,7,6)], material)
        if bevel:
            mod = obj.modifiers.new("Soft architectural edges", "BEVEL")
            mod.width = bevel
            mod.segments = 2
        return obj

    def line(name, points, radius, material):
        data = bpy.data.curves.new(name + "_Curve", "CURVE")
        data.dimensions = "3D"
        data.resolution_u = 2
        data.bevel_depth = radius
        data.bevel_resolution = 2
        spline = data.splines.new("POLY")
        spline.points.add(len(points)-1)
        for point, co in zip(spline.points, points):
            point.co = (*co, 1)
        obj = bpy.data.objects.new(name, data)
        collection.objects.link(obj)
        data.materials.append(material)
        return obj

    def ellipsoid(name, position, scale, material, segments=24, rings=12):
        vertices, faces = [], []
        for j in range(rings+1):
            v = j*math.pi/rings
            for i in range(segments):
                u = i*math.tau/segments
                vertices.append((position[0]+scale[0]*math.sin(v)*math.cos(u),
                                 position[1]+scale[1]*math.sin(v)*math.sin(u),
                                 position[2]+scale[2]*math.cos(v)))
        for j in range(rings):
            for i in range(segments):
                faces.append((j*segments+i,(j+1)*segments+i,
                              (j+1)*segments+(i+1)%segments,j*segments+(i+1)%segments))
        obj = mesh(name, vertices, faces, material)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        return obj

    def tower(name, x, y, base, h, radius, material, detailed=True):
        # A dark curtain-wall tower inside slender silver exoskeleton ribs.
        # Strongly vertical facades distinguish architecture from stacked cones.
        profile = [(radius*1.25,0), (radius*1.25,h*.035),
                   (radius,h*.09),(radius,h*.55),
                   (radius*.79,h*.57),(radius*.72,h*.76),
                   (radius*.49,h*.79),(radius*.45,h*.89),
                   (radius*.22,h*.92),(radius*.07,h*1.07),(.009,h*1.14)]
        lathe(name, x,y,base,profile,material,12 if detailed else 8)
        if detailed:
            pv,pf=[],[]
            for r1,r2,z1,z2 in [(1,1,.10,.545),(.787,.724,.579,.755),
                                (.485,.455,.795,.886)]:
                for side in range(12):
                    a1=(side+.09)*math.tau/12
                    a2=(side+.91)*math.tau/12
                    start=len(pv)
                    for a,rr,zz in [(a1,r1,z1),(a2,r1,z1),(a2,r2,z2),(a1,r2,z2)]:
                        # Face-coincident vertices are nudged out by 0.8%.
                        pv.append((x+radius*rr*1.008*math.cos(a),
                                   y+radius*rr*1.008*math.sin(a),base+h*zz))
                    pf.append((start,start+1,start+2,start+3))
            mesh(name+"_Blue_Glass_Facades",pv,pf,facade)
            for side in range(12):
                a=side*math.tau/12
                points=[(x+radius*rr*math.cos(a),y+radius*rr*math.sin(a),base+h*zz)
                        for rr,zz in [(1.01,.08),(1.01,.55),(.79,.575),
                                      (.73,.76),(.495,.79),(.46,.89),(.06,1.07)]]
                line(name+"_Vertical_Rib_%d"%side,points,max(.012,radius*.026),porcelain)
            for i in range(4):
                a = i*math.pi*.5+math.pi*.25
                fx, fy = x+math.cos(a)*radius*.99,y+math.sin(a)*radius*.99
                lathe(name+"_Fin_%d"%i,fx,fy,base,
                      [(radius*.14,0),(radius*.14,h*.47),(.02,h*.77)],porcelain,4)
                if radius>.65:
                    line(name+"_Light_%d"%i,
                         [(fx,fy,base+h*.12),(fx,fy,base+h*.46)], .012,light)
            for j in range(3,11):
                zz = h*j/20
                lathe(name+"_Floor_%d"%j,x,y,base+zz,
                      [(radius*1.012,0),(radius*1.012,.025)],dark,12)

    def platform(name, x, y, z, rx, ry, material=porcelain):
        # An elongated aerodynamically tapered platform, with fine banded edge.
        obj = lathe(name,x,y,z,[(rx*.58,-1.2),(rx*.85,-.46),(rx,-.12),
                              (rx,.12),(rx*.96,.32)],material,64)
        # Shape generated vertex positions without moving its origin.
        for vertex in obj.data.vertices:
            vertex.co.y = y+(vertex.co.y-y)*ry/rx
        for i, zz in enumerate([-.15,.18]):
            pts = [(x+rx*math.cos(a*math.tau/96),
                    y+ry*math.sin(a*math.tau/96),z+zz) for a in range(97)]
            line(name+"_Edge_%d"%i,pts,.05, titanium)
        return obj

    # Muted background architecture is physically distant, with haze encoded in
    # its materials. It remains legible through a small room window.
    for layer, y, material in [(0,71,far3),(1,52,far2),(2,36,far1)]:
        for i in range(38):
            x = -66+i*3.5+rng.uniform(-.8,.8)
            h = rng.uniform(1.0,5.5)*(1+layer*.06)
            tower("Distant_%d_%02d"%(layer,i),x,y+rng.uniform(-4,4),
                  1.2,h,rng.uniform(.19,.52),material,False)
        platform("Distant_Deck_%d"%layer,0,y,1,65,1.2,material)

    # Main right-hand city is elevated on colossal thin supports.
    platform("Main_City_Terrace",19,12,6.4,16,6.0)
    platform("Lower_Terrace",22,14,4.8,12,5.8,dark)
    for i in range(10):
        x = 5+i*2.8
        y = 11 + (i%3)*1.0
        lathe("Terrace_Pier_%02d"%i,x,y,-8,
              [(.24,0),(.24,11.2),(.40,13),(.87,14.5)], titanium,12)
        for offset in [-.27,.27]:
            line("Pier_Groove_%d_%s"%(i,offset),[(x+offset,y-.26,-4),
                 (x+offset,y-.26,5.2)],.025,porcelain)
    tower("Principal_Spire",18.8,14.1,6.7,22,1.48,titanium)
    tower("Crown_East",25.1,15.2,6.7,16.5,1.03,porcelain)
    tower("Crown_West",13.8,15.1,6.7,13.0,.83,porcelain)
    for i in range(27):
        x = rng.uniform(7,31)
        y = rng.uniform(10,16.5)
        if abs(x-18.8)<2.5 and abs(y-14.1)<2.5:
            continue
        h = rng.uniform(1.4,7.8)
        tower("Terrace_Secondary_%02d"%i,x,y,6.7,h,
              rng.uniform(.20,.68),titanium if i%2 else porcelain,i%2==0)
    for i in range(42):
        x=rng.uniform(7,30)
        y=rng.uniform(9,16)
        box("Terrace_Pavilion_%02d"%i,(x,y,6.85+rng.uniform(.12,.35)),
            (rng.uniform(.4,1.1),rng.uniform(.3,.8),rng.uniform(.22,.65)),
            dark if i%3 else porcelain,.045)
    # Monumental ring suspended above the left end of the main city.
    ring_center=(7.2,14,10.2)
    for yy, rr, material in [(0,2.20,titanium),(-.12,2.06,porcelain),
                             (-.19,1.92,light)]:
        pts=[(ring_center[0]+rr*math.cos(a*math.tau/96),ring_center[1]+yy,
              ring_center[2]+rr*math.sin(a*math.tau/96)) for a in range(97)]
        line("Orbital_Gate_Ring",pts,.10 if material!=light else .018,material)
    lathe("Orbital_Gate_Pedestal",7.2,14,6.6,[(.7,0),(.32,3.5)],porcelain,12)

    # Smaller city platform left, joined by gracefully tapering high viaducts.
    platform("Left_City_Terrace",-23,25,3.9,8.8,3.7)
    tower("Left_City_Tall_Spire",-24,26,4.2,13.0,.85,titanium)
    for i in range(16):
        x=rng.uniform(-29,-17)
        y=rng.uniform(23,27)
        tower("Left_Tower_%02d"%i,x,y,4.2,rng.uniform(1.4,6),
              rng.uniform(.2,.55),porcelain,i%3==0)
    for i,x in enumerate([-29,-24,-21,-17]):
        lathe("Left_Pier_%d"%i,x,25,-8,[(.22,0),(.25,10),(.9,12)],titanium,12)

    def bridge(name,x1,x2,y,z):
        box(name+"_Deck",((x1+x2)/2,y,z),(x2-x1,1.05,.16),porcelain,.08)
        for dy in [-.47,.47]:
            line(name+"_Rail",[(x1,y+dy,z+.20),(x2,y+dy,z+.20)],.038,titanium)
        n=max(2,int((x2-x1)/5))
        for i in range(n):
            x=x1+(i+.5)*(x2-x1)/n
            lathe(name+"_Support_%d"%i,x,y,-7,
                  [(.11,0),(.13,z+4.4),(.24,z+6),(.63,z+7)],titanium,12)
            pts=[]
            for j in range(25):
                t=j/24
                pts.append((x-2.7+5.4*t,y,z-.15-2.2*math.sin(math.pi*t)))
            line(name+"_Arch_%d"%i,pts,.095,porcelain)
    bridge("Foreground_Skyway",-35,7,7,3.45)
    bridge("Mid_Distance_Skyway",-10,5,22,5.1)
    bridge("Horizon_Skyway",-37,23,35,3.5)

    # Foreground cliff at the right edge, with irregular geological layering.
    for i in range(44):
        x=rng.uniform(35,48)
        y=rng.uniform(3,17)
        h=rng.uniform(3,10)
        r=rng.uniform(1.8,4.2)
        profile=[(r*(1-.76*j/18)*rng.uniform(.88,1.10),-8+(h+8)*j/18)
                 for j in range(19)]
        rock=lathe("Cliff_Rock_%02d"%i,x,y,0,profile,stone,24)
        for vert in rock.data.vertices:
            jitter=.14*math.sin(vert.co.x*8.2+vert.co.z*3.1)*math.cos(vert.co.y*9.7)
            vert.co.x+=jitter
            vert.co.y+=jitter*.8
        if i%2==0:
            for j in range(5):
                ellipsoid("Cliff_Green_Crown_%02d_%d"%(i,j),
                          (x+rng.uniform(-r*.5,r*.5),y+rng.uniform(-r*.5,r*.5),h*.72+rng.uniform(-.3,.4)),
                          (r*.30,r*.30,r*.23),vegetation,12,8)

    # Blue atmosphere, a physically modelled hazy planet and a soft sky wall.
    sky=bpy.data.materials.new("ENV_Gradient_Sky")
    sky.use_nodes=True
    ns=sky.node_tree.nodes
    ns.clear()
    out=ns.new("ShaderNodeOutputMaterial")
    emit=ns.new("ShaderNodeEmission")
    tex=ns.new("ShaderNodeTexCoord")
    sep=ns.new("ShaderNodeSeparateXYZ")
    ramp=ns.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position=.18
    ramp.color_ramp.elements[0].color=(.59,.70,.77,1)
    ramp.color_ramp.elements[1].position=.72
    ramp.color_ramp.elements[1].color=(.16,.34,.58,1)
    mid=ramp.color_ramp.elements.new(.38)
    mid.color=(.30,.51,.71,1)
    sky.node_tree.links.new(tex.outputs["Generated"],sep.inputs[0])
    sky.node_tree.links.new(sep.outputs["Z"],ramp.inputs[0])
    sky.node_tree.links.new(ramp.outputs[0],emit.inputs[0])
    sky.node_tree.links.new(emit.outputs[0],out.inputs[0])
    box("Infinite_Sky",(0,150,28),(320,.1,130),sky)

    planet=mat("Distant_Planet",(.59,.73,.85),0,.95,.55)
    n=planet.node_tree.nodes
    l=planet.node_tree.links
    bsdf=n.get("Principled BSDF")
    noise=n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=3.6
    noise.inputs["Detail"].default_value=5
    noise.inputs["Roughness"].default_value=.7
    cr=n.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color=(.21,.40,.59,1)
    cr.color_ramp.elements[1].color=(.63,.76,.86,1)
    l.new(noise.outputs["Fac"],cr.inputs[0])
    l.new(cr.outputs[0],bsdf.inputs["Base Color"])
    l.new(cr.outputs[0],bsdf.inputs["Emission Color"])
    ellipsoid("Large_Distant_Planet",(-11,112,34),(18,18,18),planet,96,64)

    # A low volume cloud bank, leaving pier tops and bridges clearly visible.
    cloud=bpy.data.materials.new("ENV_Cloud_Sea_Volume")
    cloud.use_nodes=True
    ns=cloud.node_tree.nodes
    ns.clear()
    out=ns.new("ShaderNodeOutputMaterial")
    vol=ns.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value=(.66,.77,.88,1)
    vol.inputs["Anisotropy"].default_value=.28
    tex=ns.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value=4.6
    tex.inputs["Detail"].default_value=4
    ramp=ns.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position=.34
    ramp.color_ramp.elements[0].color=(0,0,0,1)
    ramp.color_ramp.elements[1].position=.67
    ramp.color_ramp.elements[1].color=(.85,.85,.85,1)
    cloud.node_tree.links.new(tex.outputs["Fac"],ramp.inputs[0])
    cloud.node_tree.links.new(ramp.outputs[0],vol.inputs["Density"])
    cloud.node_tree.links.new(vol.outputs[0],out.inputs["Volume"])
    for i in range(28):
        x=-55+i*4.2+rng.uniform(-2,2)
        y=rng.uniform(2,46)
        ellipsoid("Cloud_Bank_%02d"%i,(x,y,-1+rng.uniform(-1.7,.8)),
                  (rng.uniform(5,9),rng.uniform(6,13),rng.uniform(1.8,3.6)),cloud,20,10)

    world=bpy.data.worlds.new("ENV_Atmosphere")
    world.use_nodes=True
    world.node_tree.nodes["Background"].inputs["Color"].default_value=(.51,.66,.83,1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value=.28
    scene.world=world

    def aim(obj, target):
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

    sun_data=bpy.data.lights.new("ENV_Sun", "SUN")
    sun_data.energy=2.0
    sun_data.angle=math.radians(3)
    sun=bpy.data.objects.new("ENV_Sun",sun_data)
    collection.objects.link(sun)
    sun.rotation_euler=(math.radians(35),math.radians(-20),math.radians(-35))
    area_data=bpy.data.lights.new("ENV_Sky_Fill","AREA")
    area_data.energy=1600
    area_data.shape="DISK"
    area_data.size=60
    area=bpy.data.objects.new("ENV_Sky_Fill",area_data)
    collection.objects.link(area)
    area.location=(-15,-15,55)
    aim(area,(0,15,4))
    camera_data=bpy.data.cameras.new("ENV_Camera")
    camera=bpy.data.objects.new("ENV_Camera",camera_data)
    collection.objects.link(camera)
    camera.location=(0,-82,16)
    aim(camera,(0,20,15))
    camera_data.type="PERSP"
    camera_data.lens=40
    camera_data.sensor_width=36
    camera_data.clip_end=500
    scene.camera=camera
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=False
    scene.render.filepath=output_path
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=-.25
    # Deliberately do not render, save a blend file or mutate another scene.
    if bpy.context.window and bpy.context.window.scene != previous_scene:
        bpy.context.window.scene=previous_scene
    return {"scene_name":scene.name,"camera":camera.name,
            "collection":collection.name,"output_path":output_path,
            "width":width,"height":height,"objects":len(collection.objects),
            "license":"Original procedural geometry and materials; no third-party assets"}
