"""V4 closed architectural walls and solid glazing; preserve 77 independent IDs."""
import bpy,bmesh,sys,json,math,time,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'assets/blender/scripts/works_gallery_v1'))
import gallery_common as g
import prepare_gallery as p
REPORT=ROOT/'assets/blender/works-gallery-v4';SOURCE=ROOT/'assets/blender/works-gallery-v4.blend';REPORT.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,r):(REPORT/name).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def owner(o):
 while o:
  if o.get('asset_id'):return o['asset_id']
  o=o.parent
 return None
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/works-gallery-v3.blend'));s=bpy.data.scenes['WORKS_GALLERY_V3'];bpy.context.window.scene=s
before_ids=p._hierarchy(o for o in s.objects if not p._excluded(o))
for k in ('silver','navy','bronze','ivory','black','glass','warm','leather','leaf','soil','paper','ink','terrazzo'):g.M[k]=bpy.data.materials['GALLERY_'+k]
arch=bpy.data.objects['gallery.architecture'];portal=bpy.data.objects['gallery.architecture.portal'];glazing=bpy.data.objects['gallery.architecture.glazing']
preserve=('Substantial silver foundation','Blue platform fascia','Pale terrazzo inset','Floor inlay border','Floor metal perimeter','Long stone seam','Cross stone seam','Entry step')
deleted=[]
for o in list(s.objects):
 oid=owner(o)
 if o.get('asset_id') or o.type in {'LIGHT','CAMERA'}:continue
 if oid in {'gallery.architecture.portal','gallery.architecture.glazing'} or (oid=='gallery.architecture' and not o.name.startswith(preserve)):
  deleted.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
created=[];ring_records=[]
def mesh_obj(name,verts,faces,mat,root):
 obj=g.mesh(name,verts,faces,mat,root);bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
 bm.to_mesh(obj.data);bm.free();obj.data.update();created.append(obj);return obj

def bevel(obj,width=.025,segments=3):
 mod=obj.modifiers.new('V4 manufactured continuous edge radius','BEVEL');mod.width=width;mod.segments=segments;mod.limit_method='ANGLE';mod.angle_limit=.35
 normal=obj.modifiers.new('V4 face weighted clean normals','WEIGHTED_NORMAL');normal.keep_sharp=True;normal.weight=50
 return obj

def ring(name,center,width,height,radius,inset,depth,axis,mat,root,edge=.025):
 outer=g.outline(width,height,radius,20);inner=g.outline(width-2*inset,height-2*inset,max(.03,radius-inset),20);N=len(outer);verts=[]
 def pos(u,v,d):
  return (center[0]+d,center[1]+u,center[2]+v) if axis=='X' else (center[0]+u,center[1]+d,center[2]+v)
 for d in (-depth/2,depth/2):
  for loop in (outer,inner):verts.extend(pos(u,v,d) for u,v in loop)
 faces=[]
 for i in range(N):
  j=(i+1)%N
  faces.extend([(i,j,N+j,N+i),(2*N+i,3*N+i,3*N+j,2*N+j),(i,2*N+i,2*N+j,j),(N+i,N+j,3*N+j,3*N+i)])
 obj=mesh_obj(name,verts,faces,mat,root);obj['quad_shell']=True;obj['wall_depth']=depth;obj['profile_width']=inset
 ring_records.append({'name':name,'axis':axis,'center':center,'outer_size':[width,height],'depth':depth,'section':inset,'quads':len(faces),'all_faces_quads':True})
 if edge:bevel(obj,edge)
 return obj

def solid_poly(name,points,center_axis,depth,axis,mat,root,edge=.002):
 verts=[];N=len(points)
 for d in (-depth/2,depth/2):
  for u,v in points:verts.append((u,center_axis+d,v) if axis=='Y' else (center_axis+d,u,v))
 faces=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
 obj=mesh_obj(name,verts,faces,mat,root)
 if edge:bevel(obj,edge,3)
 return obj

def closed_box(name,loc,dims,mat,root,edge=.025):
 obj=g.box(name,loc,dims,mat,root,radius=0);created.append(obj)
 if edge:bevel(obj,edge)
 return obj

def apply_mods(obj):
 bpy.context.view_layer.objects.active=obj
 for mod in list(obj.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)

def union(base,parts):
 # Structural cores are actually unioned: no floating seam cover or buried tubes.
 for mod in list(base.modifiers):base.modifiers.remove(mod)
 for other in parts:
  apply_mods(other);mod=base.modifiers.new('V4 welded joint '+other.name,'BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=other
  bpy.context.view_layer.objects.active=base;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(other,do_unlink=True)
 bm=bmesh.new();bm.from_mesh(base.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.0000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(base.data);bm.free();base.data.update();bevel(base,.027,3);return base
# Main U-shaped load-bearing shell: back frame and both end loops join in volume.
back=ring('V4 continuous back structural wall',(0,3.425,2.77),15.14,5.28,1.10,.37,.39,'Y',g.M['navy'],arch,edge=0)
left=ring('V4 left continuous end wall',(-7.35,.59,2.77),6.06,5.28,.98,.36,.44,'X',g.M['navy'],arch,edge=0)
right=ring('V4 right continuous end wall',(7.35,.59,2.77),6.06,5.28,.98,.36,.44,'X',g.M['navy'],arch,edge=0)
right_low=closed_box('V4 right integrated lower wall',(7.35,.72,.51),(.40,5.37,.74),g.M['navy'],arch,0)
# Both vertical legs extend into the existing floor top (z=.1735), not above it.
# Header and roof beams have finite rectangular sections and closed welded ends.
header=closed_box('V4 front canopy welded header',(0,1.18,5.00),(14.92,.24,.24),g.M['silver'],arch,0)
beams=[]
for i,x in enumerate((-7.35,-4.9,-2.45,0,2.45,4.9,7.35)):
 outer=abs(x)>7; cy=2.03 if outer else 2.34; length=1.98 if outer else 2.60; cz=5.12+(cy-2.34)*(.20/2.60)
 obj=closed_box('V4 closed rectangular roof beam %02d'%i,(x,cy,cz),(.16,length,.18),g.M['silver'],arch,0);obj.rotation_euler.x=math.atan2(.20,2.60);beams.append(obj)
body=union(back,[left,right,right_low,header]+beams);body.name='V4 unified continuous structural shell';body['replaces']='Separate back circles, open corner columns and un-welded roof tubes';body['architectural_owner']='gallery.architecture'
# Flush silver face trims are true closed ribbon shells, not round outline tubes.
# Back-face trim intentionally stops at the welded side wall; no cross-corner overlay.
for x,sign in ((-7.587,-1),(7.587,1)):
 ring('V4 end silver face reveal '+str(sign),(x,.59,2.77),6.02,5.24,.96,.085,.035,'X',g.M['silver'],arch,.007)
# Portal remains its own stable owner and has a thick, continuous tunnel shell.
portalbody=ring('V4 solid return doorway shell',(-8.075,-.05,2.55),3.98,4.91,.87,.365,1.85,'X',g.M['navy'],portal,.04)
portalbody['portal_return_interface_preserved']=True
threshold=closed_box('V4 doorway grounded threshold',(-8.075,-.05,-.065),(2.02,3.99,.69),g.M['navy'],portal,0)
portalbody=union(portalbody,[threshold]);portalbody.name='V4 continuous door tunnel and threshold'
ring('V4 door silver front reveal',(-7.13,-.05,2.55),3.91,4.84,.84,.10,.040,'X',g.M['silver'],portal,.009)
ring('V4 door silver back reveal',(-9.02,-.05,2.55),3.91,4.84,.84,.10,.040,'X',g.M['silver'],portal,.009)
ring('V4 door warm recessed inner reveal',(-7.106,-.05,2.55),3.31,4.24,.55,.018,.016,'X',g.M['warm'],portal,.003)
# Closed back wall retains the authored return interface plane; shell connects to it.
closed_box('V4 return portal back wall',(-9.19,-.05,2.4),(.20,3.40,4.38),g.M['navy'],portal,.045)
closed_box('V4 doorway brushed threshold tread',(-8.04,-.05,.290),(1.95,3.30,.05),g.M['silver'],portal,.014)
label=g.label('V4 Works return doorway label','MY\nWORKS',(-7.10,-1.988,2.51),.18,g.M['ivory'],portal,rotation=(math.pi/2,0,math.pi/2));created.append(label)
# Separate architectural dielectric with real thickness and pale green absorption.
archglass=bpy.data.materials.new('GALLERY_ARCH_GLASS_PBR');archglass.use_nodes=True;archglass['architecture_glass']=True
bsdf=archglass.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.78,.92,.88,1);bsdf.inputs['Metallic'].default_value=0;bsdf.inputs['Roughness'].default_value=.095;bsdf.inputs['IOR'].default_value=1.46;bsdf.inputs['Transmission Weight'].default_value=1
absorb=archglass.node_tree.nodes.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.62,.86,.76,1);absorb.inputs['Density'].default_value=.35;archglass.node_tree.links.new(absorb.outputs['Volume'],archglass.node_tree.nodes.get('Material Output').inputs['Volume'])
edge_mat=g.M['silver'].copy();edge_mat.name='GALLERY_v4_glass_edge_trim';pr=edge_mat.node_tree.nodes.get('Principled BSDF');pr.inputs['Base Color'].default_value=(.44,.65,.60,1);pr.inputs['Metallic'].default_value=.60;pr.inputs['Roughness'].default_value=.28
# Clip the glass silhouette to the actual rounded aperture, overlap 25mm inside its groove.
opening=[(u,v+2.77) for u,v in g.outline(14.48,4.59,.75,28)]
def clip(poly,x,bound_greater):
 result=[]
 for i,a in enumerate(poly):
  b=poly[(i+1)%len(poly)];inside_a=(a[0]>=x) if bound_greater else (a[0]<=x);inside_b=(b[0]>=x) if bound_greater else (b[0]<=x)
  if inside_a:result.append(a)
  if inside_a!=inside_b:
   t=(x-a[0])/(b[0]-a[0]);result.append((x,a[1]+t*(b[1]-a[1])))
 return result
edges=[-7.24,-4.82,-2.40,0,2.40,4.82,7.24]
for i,(a,b) in enumerate(zip(edges,edges[1:])):
 poly=clip(clip(opening,a+.010 if i else a,True),b-.010 if i<5 else b,False)
 obj=solid_poly('V4 inset rear glazing pane %02d'%i,poly,3.45,.032,'Y',archglass,glazing,.003);obj['glass_thickness_m']=.032;obj['architecture_glass']=True;obj['glazing_panel']=i
for i,x in enumerate(edges[1:-1]):
 closed_box('V4 sealed window mullion %02d'%i,(x,3.397,2.77),(.050,.11,4.69),g.M['silver'],arch,.014)
 # Fine pale-green rear edge line, 12mm, no black contour.
 closed_box('V4 inset glazing edge strip %02d'%i,(x,3.326,2.77),(.012,.012,4.58),edge_mat,arch,.003)
# Canopy panes are closed solid prisms with outward top normals, never 2-triangle sheets.
for i,(xa,xb) in enumerate(zip((-7.35,-4.9,-2.45,0,2.45,4.9),(-4.9,-2.45,0,2.45,4.9,7.35))):
 xa+=.065;xb-=.065; footprint=[(xa,1.285),(xb,1.285),(xb,3.48),(xa,3.48)]
 if i==5:footprint=[(xa,1.285),(xb,1.285),(xb,3.00),(6.83,3.48),(xa,3.48)]
 if i==0:footprint=[(xa,1.285),(xb,1.285),(xb,3.48),(-6.83,3.48),(xa,3.00)]
 verts=[(x,y,5.022+(y-1.285)*(.169/2.195)) for x,y in footprint];N=len(verts);normal=(Vector(verts[1])-Vector(verts[0])).cross(Vector(verts[2])-Vector(verts[0])).normalized();verts=verts+[tuple(Vector(v)-normal*.030) for v in verts];faces=[tuple(range(N)),tuple(range(2*N-1,N-1,-1))]+[(j,j+N,(j+1)%N+N,(j+1)%N) for j in range(N)]
 obj=mesh_obj('V4 solid canopy glass %02d'%i,verts,faces,archglass,glazing);bevel(obj,.0025,3);obj['glass_thickness_m']=.03;obj['architecture_glass']=True;obj['canopy_top_normal']=list(normal)
# Original terrace glass is architectural too, but its geometry/positions are retained.
for o in s.objects:
 if owner(o)=='gallery.environment.terrace' and o.type=='MESH':
  for i,mat in enumerate(list(o.data.materials)):
   if p._glass(mat):o.data.materials[i]=archglass;o['architecture_glass']=True
# Persist a V4-only source; all independent IDs and original pivots remain unchanged.
bpy.context.view_layer.update();after_ids=p._hierarchy(o for o in s.objects if not p._excluded(o));assert after_ids==before_ids and len(after_ids)==77
s.name='WORKS_GALLERY_V4';s['model_revision']=4;s['architecture_rebuilt']=True;s['glass_architecture_material']='GALLERY_ARCH_GLASS_PBR';s['new_city_geometry']=False
# Real topology verification of the evaluated new major shells and glass.
dg=bpy.context.evaluated_depsgraph_get();records=[]
for o in s.objects:
 if not o.name.startswith('V4') or o.type not in {'MESH','CURVE','FONT'}:continue
 data=bpy.data.meshes.new_from_object(o.evaluated_get(dg),depsgraph=dg);bm=bmesh.new();bm.from_mesh(data);bounds=[o.matrix_world@v.co for v in data.vertices]
 record={'name':o.name,'owner':owner(o),'triangles':sum(len(f.vertices)-2 for f in data.polygons),'boundary_edges':sum(e.is_boundary for e in bm.edges),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'volume':bm.calc_volume(signed=True),'bounds':{'min':[min(v[i] for v in bounds) for i in range(3)],'max':[max(v[i] for v in bounds) for i in range(3)]},'architecture_glass':bool(o.get('architecture_glass'))}
 if o.type=='MESH':assert record['boundary_edges']==record['non_manifold_edges']==0,(o.name,record)
 bm.free();bpy.data.meshes.remove(data);records.append(record)
bpy.data.libraries.write(str(SOURCE),{s},fake_user=True,compress=True)
write('architecture-rebuild-report.json',{'complete':True,'source':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'v3_source_sha256':sha(ROOT/'assets/blender/works-gallery-v3.blend'),'asset_count':77,'asset_hierarchy':after_ids,'removed_old_architectural_nodes':deleted,'quad_shell_designs':ring_records,'new_geometry_checks':records,'sun_and_local_lights_preserved':True,'source_floor_and_exhibits_unchanged':True,'rear_glass_thickness_m':.032,'canopy_glass_thickness_m':.030,'architecture_glass_material':'GALLERY_ARCH_GLASS_PBR','return_interface':'gallery.architecture.portal'})
print(json.dumps({'complete':True,'ids':len(after_ids),'new_objects':len(records),'new_triangles':sum(r['triangles'] for r in records),'source':str(SOURCE)}))
