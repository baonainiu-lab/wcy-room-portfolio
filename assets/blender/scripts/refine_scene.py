"""Reference matching pass after the first genuine Blender test render."""
import bpy, math, importlib
from mathutils import Matrix, Vector
from pathlib import Path
import common
from common import M

ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')

def apply():
    s=bpy.data.scenes['ORBITAL_ATELIER_V2'];bpy.context.window.scene=s
    import furniture,props
    importlib.reload(furniture);importlib.reload(props)
    # Rebuild only our own newly-generated collections, never user content.
    for name in ['FURNITURE','PROPS']:
        c=bpy.data.collections.get(name)
        if c:
            for obj in list(c.objects):bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(c)
    f=furniture.build();p=props.build();bpy.context.view_layer.update()
    pivot=Vector((-2.4,1.7,.18));dest=Vector((-3.2,.25,.18))
    transform=Matrix.Translation(dest) @ Matrix.Rotation(math.radians(65),4,'Z') @ Matrix.Diagonal((1.14,1.14,1.14,1)) @ Matrix.Translation(-pivot)
    bpy.data.objects['F_Cantilever_Desk'].matrix_world=transform @ bpy.data.objects['F_Cantilever_Desk'].matrix_world
    for obj in bpy.data.collections['PROPS'].objects:
        if obj.parent is None and obj.name.startswith(('P_TERMINAL_','P_HEADPHONES_','P_SPEAKER_','P_KEYBOARD_','P_CAMERA_','P_CUP_','P_DESK_')):
            obj.matrix_world=transform @ obj.matrix_world
    prev=s.get('workstation_transform')
    if prev:
        old=Matrix([list(prev)[i:i+4] for i in range(0,16,4)])
    elif s.get('workstation_rotated_to_left_wall'):
        old=Matrix.Translation(Vector((-3.65,0,.18))) @ Matrix.Rotation(math.pi/2,4,'Z') @ Matrix.Diagonal((1.14,1.14,1.14,1)) @ Matrix.Translation(-pivot)
    else:old=Matrix.Identity(4)
    correction=transform @ old.inverted()
    for obj in bpy.data.collections['WORKSTATION'].objects:
        if obj.parent is None:obj.matrix_world=correction @ obj.matrix_world
    s['workstation_rotated_to_left_wall']=True
    s['workstation_transform']=[x for row in transform for x in row]
    for ob in bpy.data.collections['WORKSTATION'].objects:
        if ob.name.startswith('T_Compute_InductionRing'):ob.rotation_euler=(math.pi/2,0,0)
    chair=bpy.data.objects['F_Sculptural_Work_Chair'];chair.location=(-1.40,-.48,-.035);chair.rotation_euler.z=math.radians(127);chair.scale=(1.13,1.13,1.13)
    lounge=bpy.data.objects['F_Crescent_Orange_Lounge'];lounge.location=(2.75,-1.72,-.02);lounge.rotation_euler.z=math.radians(-20);lounge.scale=(1.14,1.14,1.14)
    table=bpy.data.objects['F_Smoked_Glass_Coffee_Table'];table.location=(-.10,-1.15,-.02);table.scale=(1.24,1.24,1.1)
    tableprops=bpy.data.objects.get('P_TABLE_OBJECTS_Root')
    if tableprops:
        old=Vector((.7,-.95,.88));new=Vector((-.10,-1.15,.948))
        tableprops.matrix_world=Matrix.Translation(new) @ Matrix.Diagonal((1.24,1.24,1.10,1)) @ Matrix.Translation(-old) @ tableprops.matrix_world
    rug=bpy.data.objects['F_Charcoal_Inlaid_Rug'];rug.location=(1.50,-1.25,0);rug.scale=(1.35,1.13,1)
    for name,pivot,scale in [('P_ROBOT_Root',(-3.05,-2,.18),1.32),('P_ARCHIVE_Root',(4,2.9,2),1.14),('P_FLOWER_Root',(4,2.9,3.25),1.15),('P_TERRARIUM_Root',(4,2.9,.75),1.16)]:
        obj=bpy.data.objects.get(name)
        if obj:
            t=Matrix.Translation(Vector(pivot)) @ Matrix.Diagonal((scale,scale,scale,1)) @ Matrix.Translation(-Vector(pivot))
            obj.matrix_world=t @ obj.matrix_world
    robot=bpy.data.objects.get('P_ROBOT_Root')
    if robot:robot.location.x-=.18;robot.location.y-=.58
    # Material coordinate correction: the source file texture uses each mesh's UV.
    for m in list(bpy.data.materials):
        if not m.use_nodes:continue
        for link in list(m.node_tree.links):
            if link.from_node.type=='TEX_COORD' and link.from_socket.name=='Generated':
                target=link.to_socket;node=link.from_node;m.node_tree.links.remove(link);m.node_tree.links.new(node.outputs['UV'],target)
    M['orange_fabric'].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.33,.055,.012,1)
    M['floor'].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.075,.09,.115,1)
    M['rug'].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.012,.019,.025,1)
    # Softer and darker than the washed-out first test, while preserving readable products.
    for name,power in [('L_Key_Softbox',1300),('L_Fill_Front',850),('L_Rim',1450),('L_Warm_Bounce',350),('L_WindowLight',160)]:
        bpy.data.lights[name].energy=power
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.24
    s.view_settings.exposure=.10
    cam=s.camera;cam.location=(11,-18,10.4);cam.rotation_euler=(Vector((0,.4,2.03))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=13.55
    # Attach the second actual Blender environment render if available.
    path=ROOT/'assets/textures/window-city-v2.png'
    if path.exists():
        import build_room
        im=bpy.data.images.load(str(path),check_existing=True);im.pack()
        win=bpy.data.objects['A_Window_CityPanel'];win.data.materials.clear();win.data.materials.append(build_room.emission_image('MAT_Original_Window_City_V2',im,.85))
    s['layout_revision']=3;s['render_review_status']='in_progress'
    bpy.context.view_layer.update()
    return {'furniture':f,'props':p,'objects':len(s.objects),'layout_revision':3}
