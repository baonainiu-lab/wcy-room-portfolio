"""Window-side collection and physically detailed finishing pass."""
import bpy, math, importlib
from pathlib import Path
from mathutils import Matrix
from common import M,box,tube,cylinder,material
import build_room
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')

def apply():
    scene=bpy.data.scenes['ORBITAL_ATELIER_V2'];bpy.context.window.scene=scene
    arch=bpy.data.collections['ARCHITECTURE'];tech=bpy.data.collections['WORKSTATION']
    # Window furniture is independent from the structural shell.
    for name in ['A_WindowDisplayLedge','A_WindowDisplayInlay','A_WindowDisplayRecessGlow']:
        old=bpy.data.objects.get(name)
        if old:bpy.data.objects.remove(old,do_unlink=True)
    ledge=build_room.extrude('A_WindowDisplayLedge',build_room.rr(.35,2.82,5.95,.82,.16),1.345,1.42,M['titanium'],arch)
    bevel=ledge.modifiers.new('Rounded shelf edge','BEVEL');bevel.width=.015;bevel.segments=3
    top=build_room.extrude('A_WindowDisplayInlay',build_room.rr(.35,2.81,5.85,.74,.15),1.419,1.427,M['graphite'],arch)
    tube('A_WindowDisplayRecessGlow',[(-2.45,2.45,1.355),(3.10,2.45,1.355)],.006,M['warm_light'],arch)
    for ob in arch.objects:
        if ob.name.startswith('A_UnderWindow_Panel_'):
            ob.location.y=2.98;ob.dimensions.y=.45
    import density_assets
    importlib.reload(density_assets);added=density_assets.build()
    # Actual rendered original 3D artwork becomes the monitor image texture.
    art=ROOT/'assets/textures/screen-art-render.png'
    im=bpy.data.images.load(str(art),check_existing=True);im.pack()
    front=bpy.data.objects['T_DisplayGlass'];front.data.materials.clear();front.data.materials.append(build_room.emission_image('MAT_Rendered_3D_ScreenArtwork',im,.72))
    # Make the compute core a transparent, assembled object, not a printed ring on a box.
    case=bpy.data.objects['T_Compute_Chassis'];core=bpy.data.objects['T_ComputeCore']
    smoke=material('Compute_Smoked_Optical_Glass',(.25,.35,.40),.05,.12,transmission=.92)
    case.data.materials.clear();case.data.materials.append(smoke)
    casefront=bpy.data.objects['T_Compute_Glass'];casefront.hide_render=True
    # New parts use local coordinates of the independent compute_core root.
    for ob in list(tech.objects):
        if ob.name.startswith('T_Compute_Detail_'):bpy.data.objects.remove(ob,do_unlink=True)
    corners=[(x,y,z) for x in [-4.105,-3.255] for y in [.635,1.285] for z in [.22,1.44]]
    for i,a in enumerate(corners):
        for j,b in enumerate(corners):
            if j<=i:continue
            if sum(abs(a[k]-b[k])>.01 for k in range(3))==1:
                ob=tube('T_Compute_Detail_Frame_%d_%d'%(i,j),[a,b],.018,M['titanium'],tech);ob.parent=core
    ob=box('T_Compute_Detail_RearPlate',(-3.68,1.27,.83),(.70,.025,1.05),M['graphite'],tech,.035);ob.parent=core
    for ob in tech.objects:
        if ob.name.startswith('T_Compute_InductionRing'):
            ob.location.y=.81
            ob.rotation_euler=(math.pi/2,0,0)
    for i in range(6):
        ob=box('T_Compute_Detail_Fin_%d'%i,(-3.91+i*.092,.93,.40),(.022,.30,.10),M['titanium'],tech,.003);ob.parent=core
    # Upholstery should read as cloth, with a low broad highlight and fine weave.
    p=M['orange_fabric'].node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value=(.27,.040,.008,1)
    for link in list(p.inputs['Roughness'].links):M['orange_fabric'].node_tree.links.remove(link)
    p.inputs['Roughness'].default_value=.83
    p.inputs['Specular IOR Level'].default_value=.23
    p.inputs['Sheen Weight'].default_value=.25
    for node in M['orange_fabric'].node_tree.nodes:
        if node.type=='BUMP':node.inputs['Strength'].default_value=.32;node.inputs['Distance'].default_value=.018
    # Keep the window contents background-like, leaving the new collectibles legible.
    for name in ['MAT_Original_Window_City_V2']:
        m=bpy.data.materials.get(name)
        if m:
            for node in m.node_tree.nodes:
                if node.type=='EMISSION':node.inputs['Strength'].default_value=.73
    scene['visible_asset_revision']='window_display_collections_added'
    bpy.context.view_layer.update()
    return {'additions':added,'window_display':True,'monitor_art':'actual SCREEN_ART Blender render'}
