import bpy, math, json
from pathlib import Path
from mathutils import Vector
P=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
parts=[]
def mat(n,h,r=.4,m=0):
 c=tuple(int(h[i:i+2],16)/255 for i in (0,2,4)); c=tuple(v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4 for v in c)
 a=bpy.data.materials.new(n);a.diffuse_color=(*c,1);a.use_nodes=True;b=a.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*c,1);b.inputs['Roughness'].default_value=r;b.inputs['Metallic'].default_value=m;return a
iv=mat('Pearl ceramic · warm ivory','EEE8D8',.3,.12)
teal=mat('Ink teal · technical wool','244B4C',.6)
edge=mat('Cape shadow folds','153436',.6)
orange=mat('Burnt persimmon lining','D9753F',.4)
black=mat('Graphite articulated undersuit','263136',.5)
glass=mat('Smoked visor','0F2026',.2,.3)
white=mat('Warm white light','FFF5DB',.27)
b=white.node_tree.nodes.get('Principled BSDF');b.inputs['Emission Color'].default_value=white.diffuse_color;b.inputs['Emission Strength'].default_value=.6
silver=mat('Satin titanium','A8ADAA',.28,.7)
soil=mat('Studio background','D6D1C7',.78)
def reg(o,n,m):
 o.name=n;o.data.materials.append(m);parts.append(o)
 for p in o.data.polygons:p.use_smooth=True
 return o
def sph(n,l,sc,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,location=l);o=bpy.context.object;o.scale=sc;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return reg(o,n,m)
def cube(n,l,d,m,bev=.04):
 bpy.ops.mesh.primitive_cube_add(size=1,location=l);o=bpy.context.object;o.dimensions=d;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 mod=o.modifiers.new('Soft manufactured edge','BEVEL');mod.width=bev;mod.segments=4;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 mod=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=mod.name);return reg(o,n,m)
def cyl(n,l,r,d,m,axis='Z'):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=d,location=l);o=bpy.context.object
 if axis=='Y':o.rotation_euler[0]=math.pi/2
 if axis=='X':o.rotation_euler[1]=math.pi/2
 mod=o.modifiers.new('Turned bevel','BEVEL');mod.width=.012;mod.segments=3;bpy.ops.object.modifier_apply(modifier=mod.name);return reg(o,n,m)
def line(n,pts,r,m):
 c=bpy.data.curves.new(n,'CURVE');c.dimensions='3D';c.resolution_u=2;c.bevel_depth=r;c.bevel_resolution=4;c.use_fill_caps=True
 closed=(Vector(pts[0])-Vector(pts[-1])).length < .000001
 if closed:pts=pts[:-1]
 p=c.splines.new('POLY');p.points.add(len(pts)-1);p.use_cyclic_u=closed;c.use_fill_caps=not closed
 for v,co in zip(p.points,pts):v.co=(*co,1)
 o=bpy.data.objects.new(n,c);s.collection.objects.link(o);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o=bpy.context.object;o.select_set(False);return reg(o,n,m)
def rod(n,a,b,r,m):
 a,b=Vector(a),Vector(b);o=cyl(n,(a+b)/2,r,(b-a).length,m);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o
# A sculptural hood, not a generic space helmet: oversized flared crescent opening.
hood=[];rim=[]
for i in range(161):
 a=2*math.pi*i/160
 hood.append((.406*math.sin(a),.018+.045*math.cos(a),2.105+.464*math.cos(a)))
 rim.append((.398*math.sin(a),-.123+.030*math.cos(a),2.11+.456*math.cos(a)))
line('Crescent hood padded body',hood,.105,teal)
line('Moonstone hood front piping',rim,.032,iv)
# Upper half rear hood cover, intentionally a strong uninterrupted ivory crescent.
rear=[]
for i in range(81):
 a=-math.pi*.66+math.pi*1.32*i/80;rear.append((.432*math.sin(a),.14+.045*math.cos(a),2.10+.474*math.cos(a)))
line('Sculpted ivory lunar crest',rear,.032,iv)
sph('Oval pearl face',(0,-.062,2.11),(.326,.267,.402),iv)
sph('Single horizontal charcoal visor',(0,-.302,2.208),(.302,.079,.157),glass)
# Closed lower edge eyes make a reserved, calm look; precisely reproducible geometry.
for x in [-.11,.11]:
 line('Calm luminous eyelid '+str(x),[(x-.034+i*.068/20,-.381- .006*(1-(i/10-1)**2),2.228+.010*math.sin(i/20*math.pi)) for i in range(21)],.012,white)
# One orange navigation marker, no busy face decals.
cube('Small temple amber dash',(.248,-.342,2.190),(.019,.014,.045),orange,.008)
# Two chin shell seams echo the lunar concept.
line('Chin softly raised seam',[(-.14+i*.28/40,-.309+.026*abs(i/20-1),1.976-.025*math.sin(i/40*math.pi)) for i in range(41)],.004,silver)
cyl('Neck rotation joint',(0,0,1.705),.105,.16,black)
cyl('Persimmon scarf collar',(0,0,1.697),.216,.093,orange)
cyl('Scarf ivory collar rim',(0,0,1.735),.195,.026,iv)
# Hidden narrow human torso, articulated arms.
sph('Inner torso',(0,.02,1.313),(.239,.18,.382),black)
cube('Pelvis',(0,.02,.95),(.38,.29,.22),black,.085)
# Cape with deliberate low-poly folds and unequal hem heights.
N=32;verts=[];faces=[]
for ring in range(4):
 for j in range(N):
  a=2*math.pi*j/N;sa,ca=math.sin(a),math.cos(a)
  if ring==0: rx,ry,z=.18,.145,1.715
  elif ring==1:rx,ry,z=.43,.23,1.584
  elif ring==2:rx,ry,z=.48,.276,1.29
  else:rx,ry,z=.55,.31,1.092-.10*sa-.025*ca
  pleat=(.018 if j%4==0 else -.009 if j%4==2 else 0)*(ring/3)
  verts.append(((rx+pleat)*sa,-(ry+pleat)*ca,z))
for k in range(3):
 for j in range(N):faces.append(((k+1)*N+j,(k+1)*N+(j+1)%N,k*N+(j+1)%N,k*N+j))
me=bpy.data.meshes.new('Structured cape mesh');me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new('Asymmetric sculptural poncho',me);s.collection.objects.link(o);o.data.materials.append(teal);o.data.materials.append(edge);o.data.materials.append(orange)
for p in o.data.polygons:p.material_index=1 if p.index%N in [4,12,20,28] else 0;p.use_smooth=False
sol=o.modifiers.new('Visible orange inner thickness','SOLIDIFY');sol.thickness=.018;sol.material_offset=2
bev=o.modifiers.new('Subtle folded edges','BEVEL');bev.width=.008;bev.segments=2
parts.append(o)
# Beautiful controlled hem line echoes the whole asymmetric cape outline.
line('Burnt orange continuous cape hem',[tuple(verts[3*N+j%N][k] + (0 if k!=1 else -.004) for k in range(3)) for j in range(N+1)],.012,orange)
# Offcenter broad ivory shoulder sweep, a second crescent motif.
line('Moonstone shoulder arc',[(-.39+.25*i/48,-.09-.11*math.sin(i/48*math.pi),1.568+.072*math.sin(i/48*math.pi)) for i in range(49)],.045,iv)
# Architectural lapel that resolves diagonally into the mapping lens.
line('Cape folded lapel',[(-.10,-.152,1.68),(-.02,-.20,1.58),(.095,-.264,1.38),(.21,-.292,1.19)],.027,edge)
line('Lapel tiny orange seam',[(-.112,-.170,1.662),(-.024,-.22,1.55),(.09,-.285,1.36)],.004,orange)
# Arms are slim and human-proportioned; cape partially covers shoulders.
for sign in [-1,1]:
 shoulder=(sign*.34,.025,1.495);elbow=(sign*.47,-.008,1.15);wrist=(sign*.52,-.075,.915)
 rod('Upper arm '+str(sign),shoulder,elbow,.068,black);sph('Elbow '+str(sign),elbow,(.068,.069,.071),black)
 rod('Sleeve cuff '+str(sign),elbow,wrist,.070,teal)
 cyl('Ivory wrist cuff '+str(sign),(sign*.52,-.075,.963),.077,.045,iv)
 sph('Warm ceramic glove '+str(sign),(sign*.524,-.094,.877),(.078,.077,.115),iv)
 sph('Integrated glove thumb '+str(sign),(sign*.459,-.128,.879),(.035,.044,.060),iv)
 # Harem thighs and tapered shins, visible knee segmentation.
 sph('Tailored graphite trouser thigh '+str(sign),(sign*.128,.027,.775),(.14,.145,.235),black)
 sph('Trouser tapered lower leg '+str(sign),(sign*.14,.04,.431),(.107,.116,.221),black)
 cyl('Technical shin band '+str(sign),(sign*.14,.041,.344),.110,.067,teal)
 cube('Moonstone boot '+str(sign),(sign*.148,-.023,.18),(.232,.342,.276),iv,.077)
 cube('Graphite boot sole '+str(sign),(sign*.148,-.048,.055),(.247,.365,.075),black,.028)
 cube('Boot graphite upper inset '+str(sign),(sign*.148,-.147,.22),(.159,.107,.11),black,.030)
 cube('Tiny orange boot pull '+str(sign),(sign*.148,.153,.27),(.045,.038,.10),orange,.012)
# Only one tool: portable circular mapping lens / portfolio portal.
# Tilted outboard on the left; readable carved concentric circles, retained for raycast.
cyl('Circular mapping lens leather housing',(-.30,-.324,1.16),.124,.069,orange,'Y')
cyl('Mapping lens satin rim',(-.30,-.368,1.16),.108,.025,iv,'Y')
cyl('Mapping lens recessed glass',(-.30,-.385,1.16),.083,.018,glass,'Y')
pts=[(-.30+.061*math.cos(2*math.pi*i/80),-.398,1.16+.061*math.sin(2*math.pi*i/80)) for i in range(81)]
line('Mapping circular reticle',pts,.004,silver)
line('Mapping orbital meridian',[(-.30+.048*math.cos(2*math.pi*i/80),-.400,1.16+.026*math.sin(2*math.pi*i/80)) for i in range(81)],.003,silver)
sph('Mapping coordinate point',(-.266,-.408,1.19),(.009,.005,.009),orange)
# Rear identifying stripe and simple volume add intentional back design.
cube('Rear cape center folded strip',(0,.283,1.34),(.073,.036,.374),edge,.02)
for k in range(3):cube('Rear tracking stitch '+str(k),(0,.309,1.448-.055*k),(.032,.010,.016),orange,.004)
# Register a single root, preserving world transforms; export only the character.
root=bpy.data.objects.new('Moonphase Navigator · Concept B',None);s.collection.objects.link(root)
root['design']='Original deterministic Blender character. Approval only. No website integration.'
for o in parts:
 o.parent=root
root['interaction_anchors']='head; visor eyelids; mapping lens; collar; arms. Animation not included in this approval prototype.'
bpy.ops.object.select_all(action='DESELECT')
for o in parts+[root]:o.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(P/'moonphase-navigator.glb'),export_format='GLB',use_selection=True,export_apply=True)
# Neutral gallery photography, character asset itself unchanged.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,.014));floor=bpy.context.object;floor.name='Studio ground';floor.data.materials.append(soil)
s.world=bpy.data.worlds.new('Warm grey studio');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.52,.50,.46,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.35

def area(n,loc,pow,size,color):
 d=bpy.data.lights.new(n,'AREA');d.energy=pow;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(n,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.2))-o.location).to_track_quat('-Z','Y').to_euler()
area('Large softbox',(-3,-4,6),700,4,(1,.92,.81));area('Cool fill',(4,-1,3),380,3,(.80,.90,1));area('Ivory rim',(-1,3,4),850,3,(1,.91,.74))
d=bpy.data.cameras.new('Portrait camera');cam=bpy.data.objects.new('Portrait camera',d);s.collection.objects.link(cam);s.camera=cam;d.type='ORTHO';d.ortho_scale=3.35
s.render.engine='CYCLES';s.cycles.samples=72;s.cycles.use_denoising=True
s.render.resolution_x=1200;s.render.resolution_y=1500;s.render.resolution_percentage=100
s.view_settings.view_transform='AgX'
s.render.image_settings.file_format='PNG';s.render.film_transparent=False

def camera(loc,target=(0,0,1.34)):
 cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
camera((4,-7,3.45));s.render.filepath=str(P/'hero.png');bpy.ops.wm.save_as_mainfile(filepath=str(P/'moonphase-navigator.blend'));bpy.ops.render.render(write_still=True)
s.render.resolution_x=900;s.render.resolution_y=1200;s.cycles.samples=32
camera((0,-7,2.70));s.render.filepath=str(P/'front.png');bpy.ops.render.render(write_still=True)
camera((-4,7,3.25));s.render.filepath=str(P/'back.png');bpy.ops.render.render(write_still=True)
(P/'design.json').write_text(json.dumps({'name':'月相领航员','english':'Moonphase Navigator','dimensions_xyz_units':[1.2311,.7489,2.6565],'concept':'A quiet adult explorer: crescent pearl hood, disciplined asymmetrical teal cape, persimmon lining, circular mapping lens.','approval_only':True,'actual_geometry':True,'not_rigged':True,'palette':['#EEE8D8','#244B4C','#D9753F','#263136'],'files':['moonphase-navigator.blend','moonphase-navigator.glb','hero.png','front.png','back.png']},ensure_ascii=False,indent=2))
