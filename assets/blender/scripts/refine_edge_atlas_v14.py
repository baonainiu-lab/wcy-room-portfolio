"""Local architecture lightmap precision, preserving every source triangle.

V13 geometry is already sufficient at the architectural silhouette. Its broad
walls, hidden platform caps and thin metal rails share one 4K lightmap. This
revision moves selected rails / rims into one 3K atlas with deliberate strips.
The old surfaces retain their exact UVs and maps; source PBR and all IDs stay.
"""
import bpy, json, math, sys, time, hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
SIZE=3072
NEW_ATLAS=8
sys.path.insert(0,str(ROOT/'assets/blender/scripts'))
from refine_architecture_uv_v12 import _islands, _uv_area, _strip_ring

def activate(scene):
    # Normal Blender CLI has a background Window; MCP may not.
    if bpy.context.window:
        bpy.context.window.scene=scene
    scene.view_layers[0].update()

def components(obj):
    mesh=obj.data;p=list(range(len(mesh.vertices)))
    def root(i):
        while p[i]!=i:p[i]=p[p[i]];i=p[i]
        return i
    for edge in mesh.edges:
        a,b=edge.vertices;p[root(a)]=root(b)
    result={}
    for face in mesh.polygons:result.setdefault(root(face.vertices[0]),[]).append(face.index)
    return list(result.values())

def bounds(obj,faces):
    points=[obj.matrix_world@obj.data.vertices[v].co for f in faces for v in obj.data.polygons[f].vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return lo,hi

def copy_faces(obj, faces, suffix):
    old=obj.data; faces=sorted(faces)
    ids=sorted({v for f in faces for v in old.polygons[f].vertices});remap={v:i for i,v in enumerate(ids)}
    mesh=bpy.data.meshes.new(old.name+suffix)
    mesh.from_pydata([old.vertices[v].co for v in ids],[],[tuple(remap[v] for v in old.polygons[f].vertices) for f in faces])
    for mat in old.materials:mesh.materials.append(mat)
    for new_index,old_index in enumerate(faces):
        mesh.polygons[new_index].material_index=old.polygons[old_index].material_index
        mesh.polygons[new_index].use_smooth=old.polygons[old_index].use_smooth
    for old_uv in old.uv_layers:
        new_uv=mesh.uv_layers.new(name=old_uv.name)
        for nf,of in zip(mesh.polygons,faces):
            for nl,ol in zip(nf.loop_indices,old.polygons[of].loop_indices):new_uv.data[nl].uv=old_uv.data[ol].uv
    normals=[]
    for index in faces:
        normals.extend(tuple(old.corner_normals[li].vector) for li in old.polygons[index].loop_indices)
    mesh.normals_split_custom_set(normals)
    mesh.update()
    new=obj.copy();new.data=mesh;new.name=obj.name+suffix
    for coll in obj.users_collection:coll.objects.link(new)
    # A split mesh is another surface within the same owner, not a new asset.
    new.pop('asset_id',None)
    return new, {old_index:new_index for new_index,old_index in enumerate(faces)}

def rr(cx,cy,w,h,r,n=48):
    pts=[]
    for x,y,a in [(cx+w/2-r,cy+h/2-r,0),(cx-w/2+r,cy+h/2-r,90),(cx-w/2+r,cy-h/2+r,180),(cx+w/2-r,cy-h/2+r,270)]:
        for i in range(n+1):
            t=math.radians(a+90*i/n);pts.append(Vector((x+r*math.cos(t),y+r*math.sin(t))))
    return pts

def ring_coordinates(obj, faces, plane, center, wh, radius, cross_center, cross_half):
    """Unwrap a rounded rectangular rail along perimeter and cross-section.

    Four perimeter quarters keep strips packable. Cross section cuts lie at the
    rear/underside and share vertex coordinates elsewhere. No geometry edits.
    """
    axis_a,axis_b,axis_depth=plane
    path=rr(*center,*wh,radius)
    edges=[];length=0
    for a,b in zip(path,path[1:]+path[:1]):
        d=b-a;l=d.length
        if l<1e-9:continue
        edges.append((a,d,l,length));length+=l
    ids={v for f in faces for v in obj.data.polygons[f].vertices}
    coords={}
    for v in ids:
        p=obj.matrix_world@obj.data.vertices[v].co;q=Vector((p[axis_a],p[axis_b]))
        best=None
        for a,d,l,s in edges:
            t=max(0,min(1,(q-a).dot(d)/(l*l)));near=a+d*t;error=(q-near).length_squared
            if best is None or error<best[0]:best=(error,s+l*t,q-near,Vector((d.y,-d.x)).normalized())
        _,u,delta,outward=best
        radial=delta.dot(outward)
        # Elliptical angle follows the rail's front, outer, back and inner faces.
        vangle=math.atan2((p[axis_depth]-cross_center)/cross_half[1],radial/cross_half[0])%math.tau
        coords[v]=(u,vangle*sum(cross_half)/2)
    vlength=math.tau*sum(cross_half)/2
    uv=obj.data.uv_layers['BakeUV'].data
    labels={}
    for fi in faces:
        f=obj.data.polygons[fi];points=[coords[v] for v in f.vertices]
        us=[p[0] for p in points];vs=[p[1] for p in points]
        if max(us)-min(us)>length*.5:us=[u+length if u<length*.5 else u for u in us]
        if max(vs)-min(vs)>vlength*.5:vs=[v+vlength if v<vlength*.5 else v for v in vs]
        section=min(3,int((sum(us)/len(us)%length)/(length/4)))
        # Separate sections by a translation. pack_islands subsequently handles scale.
        for li,u,v in zip(f.loop_indices,us,vs):uv[li].uv=(u-section*length/4, v+section*(vlength+1))
        labels[fi]=section
    return {'method':'perimeter_cross_section_strips','sections':4,'perimeter_m':length}

def projected_strips(obj, faces):
    """Six connected projections retain broad metal faces and their bevels.

    Unlike angle-cluster Smart Project, subdivisions on a planar/swept band
    stay in one projection until the main surface orientation changes.
    """
    mesh=obj.data;uv=mesh.uv_layers['BakeUV'].data
    normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
    for fi in faces:
        face=mesh.polygons[fi];normal=normal_matrix@face.normal
        axis=max(range(3),key=lambda a:abs(normal[a]));direction=1 if normal[axis]>=0 else -1
        axes=[a for a in range(3) if a!=axis]
        label=axis*2+(1 if direction<0 else 0)
        for li in face.loop_indices:
            p=obj.matrix_world@mesh.vertices[mesh.loops[li].vertex_index].co
            uv[li].uv=(p[axes[0]]*direction+label*25,p[axes[1]])
    return {'method':'continuous_dominant_axis_projection'}

def metrics(obj,faces,size):
    faces=set(faces);mesh=obj.data;mesh.calc_loop_triangles();area=uv_area=0.;small=0
    for tri in mesh.loop_triangles:
        if tri.polygon_index not in faces:continue
        a,b,c=[obj.matrix_world@mesh.vertices[v].co for v in tri.vertices]
        area+=(b-a).cross(c-a).length*.5
        value=_uv_area(mesh,tri);uv_area+=value
        small+=value*size*size<1
    return {'worldArea':area,'uvArea':uv_area,'texelsPerMeter':size*math.sqrt(uv_area/area) if area else 0,'trianglesBelowOnePixel':small}

def validate_uv(obj):
    mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers['BakeUV'].data
    coords=[v for li in uv for v in li.uv]
    assert all(math.isfinite(v) and -1e-5<=v<=1.00001 for v in coords),obj.name
    islands=_islands(obj);folded=degenerate=0;details=[]
    for island in islands:
        positive=negative=0
        for index in island['triangles']:
            tri=mesh.loop_triangles[index];a,b,c=[uv[i].uv for i in tri.loops]
            area=((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
            positive+=area>1e-12;negative+=area< -1e-12;degenerate+=abs(area)<=1e-12
        folded+=bool(positive and negative)
        xs=[uv[i].uv.x for i in island['loops']];ys=[uv[i].uv.y for i in island['loops']]
        details.append({'faces':len(island['faces']),'firstFace':island['faces'][0],'positive':positive,'negative':negative,'bbox':[max(xs)-min(xs),max(ys)-min(ys)],'area':sum(_uv_area(mesh,mesh.loop_triangles[i]) for i in island['triangles'])})
    return {'islands':len(islands),'islandsWithMixedWinding':folded,'degenerateUVTriangles':degenerate,'finiteInBounds':True,'details':details}

def seam_from_layout(obj):
    mesh=obj.data;uv=mesh.uv_layers['BakeUV'].data;by_edge={}
    for face in mesh.polygons:
        loops=list(face.loop_indices)
        for a,b in zip(loops,loops[1:]+loops[:1]):
            va,vb=mesh.loops[a].vertex_index,mesh.loops[b].vertex_index
            ua,ub=tuple(round(v,6) for v in uv[a].uv),tuple(round(v,6) for v in uv[b].uv)
            record=(va,vb,ua,ub) if va<vb else (vb,va,ub,ua)
            by_edge.setdefault(mesh.loops[a].edge_index,[]).append(record)
    for edge in mesh.edges:
        rows=by_edge.get(edge.index,[])
        edge.use_seam=len(rows)!=2 or rows[0]!=rows[1]

def cut_folded_faces(obj):
    mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers['BakeUV'].data;cut=set()
    for island in _islands(obj):
        signed=[]
        for ti in island['triangles']:
            tri=mesh.loop_triangles[ti];a,b,c=[uv[i].uv for i in tri.loops]
            signed.append((tri.polygon_index,((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5))
        positive=sum(v>1e-12 for _,v in signed);negative=sum(v< -1e-12 for _,v in signed)
        if positive and negative:
            majority=1 if positive>=negative else -1
            cut.update(fi for fi,value in signed if value*majority< -1e-12)
        cut.update(fi for fi,value in signed if abs(value)<=1e-12)
    for fi in cut:
        for li in mesh.polygons[fi].loop_indices:mesh.edges[mesh.loops[li].edge_index].use_seam=True
    return len(cut)

def run(save=False):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/blender/orbital-dual-bake-v13.blend'))
    scene=bpy.data.scenes['WEB_DUAL_V8'];activate(scene)
    report={'revision':14,'input':'orbital-dual-bake-v13.blend','resolution':SIZE,'geometryUnchanged':True,'addedDrawPrimitives':2,'groups':[]}
    new_objects=[];material_cache={}
    for name in ['WEB8_room_static__baked__A0','WEB8_architecture.platform__baked__A0']:
        old=bpy.data.objects[name];selected=set();jobs=[]
        for faces in components(old):
            lo,hi=bounds(old,faces);d=hi-lo
            if old.get('owner_asset_id')=='room_static':
                label=None;spec=None
                if hi.z<.21 and d.x>9 and d.y>6:
                    label='floor_precision_rim';spec=((0,1,2),(0,0),(9.96,7.04),.54,.18,(.014,.014))
                elif lo.z>4.4 and d.x>9:label='sweeping_wall_cap'
                elif lo.x< -5.3 and lo.z>3.5 and d.y>6:label='left_wall_cap'
                elif lo.x< -5.3 and d.z>3 and d.y<.3:label='left_front_post'
                elif lo.x< -2.8 and lo.y>3.07 and 6.2<d.x<6.4 and d.z>2.7:
                    label='window_metal_frame';spec=((0,2,1),(.25,2.97),(6.13,2.655),.385,3.215,(.085,.135))
                elif lo.x< -2.7 and 5.9<d.x<6.1 and d.y<.03:
                    label='window_recess_light';spec=((0,2,1),(.25,2.97),(5.96,2.49),.32,3.073,(.018,.018))
                elif lo.x>3.1 and 1.6<d.x<1.7 and d.z>4:
                    label='display_tower_frame';spec=((0,2,1),(4,2.55),(1.535,4.155),.38,2.86,(.0625,.31))
                if label:
                    selected.update(faces);jobs.append((label,faces,spec))
            else:
                # Keep both horizontal caps on their old maps; only unwrap the
                # visible side walls and bevels of the three primary plinths.
                if d.x<10.2 and d.y>6.8:
                    side=[]
                    for fi in faces:
                        normal=old.matrix_world.to_3x3().inverted().transposed()@old.data.polygons[fi].normal
                        if abs(normal.z)<.9999:side.append(fi)
                    selected.update(side)
                    jobs.append(('platform_side_'+str(round(lo.z,2)),side,('platform',lo,hi)))
        assert selected and len(selected)<len(old.data.polygons)
        kept=sorted(set(range(len(old.data.polygons)))-selected)
        retained,_=copy_faces(old,kept,'__retained_v14')
        trims,remap=copy_faces(old,selected,'__precision_v14')
        trims['bake_atlas']=NEW_ATLAS;trims['geometry_atlas']=NEW_ATLAS;trims['precision_revision']=14
        retained['precision_revision']=14
        for index,mat in enumerate(list(trims.data.materials)):
            if mat is None:continue
            if mat not in material_cache:
                cp=mat.copy();cp.name=mat.name.replace('BAKE_A0','BAKE_A8');cp['bake_atlas']=8
                material_cache[mat]=cp
            trims.data.materials[index]=material_cache[mat]
        for label,faces,spec in jobs:
            nf=[remap[f] for f in faces];before=metrics(old,faces,4096)
            if spec and spec[0]=='platform':
                trims.data.calc_loop_triangles()
                face_set=set(nf)
                island={'faces':nf,'loops':[li for fi in nf for li in trims.data.polygons[fi].loop_indices],
                        'triangles':[t.index for t in trims.data.loop_triangles if t.polygon_index in face_set]}
                vertices=[trims.matrix_world@v.co for v in trims.data.vertices]
                method=_strip_ring(trims,island,vertices)
                if not method['applied']:raise RuntimeError('Platform side unwrap failed: '+str(method))
            elif spec:method=ring_coordinates(trims,nf,*spec)
            else:method=projected_strips(trims,nf)
            report['groups'].append({'label':label,'object':trims.name,'faces':nf,'before':before,'unwrap':method})
        bpy.data.objects.remove(old,do_unlink=True)
        retained.name=name;trims.name=name.replace('__A0','__A8')
        for item in report['groups']:
            if item['object'].endswith('__precision_v14') and item['object'].startswith(name):item['object']=trims.name
        new_objects.append(trims)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in new_objects:
        seam_from_layout(obj)
        obj.select_set(True);obj.data.uv_layers.active=obj.data.uv_layers['BakeUV'];obj.data.uv_layers['BakeUV'].active_render=True
    bpy.context.view_layer.objects.active=new_objects[0]
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED',margin=.001)
    bpy.ops.object.mode_set(mode='OBJECT')
    corrections=[]
    for attempt in range(3):
        cut=sum(cut_folded_faces(o) for o in new_objects)
        corrections.append(cut)
        if not cut:break
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED',margin=.001)
        bpy.ops.object.mode_set(mode='OBJECT')
    report['localCornerSeamCorrections']=corrections
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    for item in report['groups']:
        weight=1.15 if item['label'] in {'floor_precision_rim','window_recess_light','window_metal_frame'} else 1.08 if item['label'].startswith('platform_side') else 1.0
        item['linearTexelWeight']=weight
        obj=bpy.data.objects[item['object']];uv=obj.data.uv_layers['BakeUV'].data
        loops=[li for fi in item['faces'] for li in obj.data.polygons[fi].loop_indices]
        center=sum((uv[i].uv.copy() for i in loops),Vector((0,0)))/len(loops)
        for li in loops:uv[li].uv=center+(uv[li].uv-center)*weight
    bpy.ops.object.mode_set(mode='EDIT')
    # Bake uses 16-pixel extension; a 32-pixel requested inter-island gap
    # reserves both sides without changing old atlases' UV precision.
    bpy.ops.uv.pack_islands(rotate=True,rotate_method='ANY',scale=True,merge_overlap=False,margin_method='FRACTION',margin=32/SIZE,shape_method='CONCAVE',pin=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for item in report['groups']:
        obj=bpy.data.objects[item['object']];item['after']=metrics(obj,item['faces'],SIZE)
        item['densityFactor']=item['after']['texelsPerMeter']/item['before']['texelsPerMeter']
        item['faceCount']=len(item.pop('faces'))
    report['validation']={o.name:validate_uv(o) for o in new_objects}
    report['packGapPixelsSetting']=32
    report['bakeExtensionPixels']=16
    image=bpy.data.images.new('WEB8_ATLAS_8',width=SIZE,height=SIZE,alpha=False,float_buffer=True)
    image.colorspace_settings.name='Linear Rec.709'
    for mat in material_cache.values():
        target=mat.node_tree.nodes.get('WEB8_BAKE_TARGET');target.image=image;mat.node_tree.nodes.active=target
    scene['geometry_revision']=14;scene['lighting_revision']=14;scene['light_rig_inherited_from']=13
    scene['edge_atlas_revision']=14
    report['texturePolicy']='Atlases 0–7 and windows byte-identical; Atlas8 only added; no existing visible surface downweighted'
    report['triangles']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in scene.objects if o.type=='MESH' and o.get('web_export'))
    report['output']='assets/blender/orbital-dual-bake-v14.blend'
    (ROOT/'assets/blender/edge-atlas-v14-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if save:
        if any(v['islandsWithMixedWinding'] or v['degenerateUVTriangles'] for v in report['validation'].values()):
            raise RuntimeError('UV strip folding or degenerate triangle detected; inspect proof before saving')
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/report['output']),compress=True)
    return report

if __name__=='__main__':
    print(json.dumps(run(save='--save' in sys.argv),indent=2))
