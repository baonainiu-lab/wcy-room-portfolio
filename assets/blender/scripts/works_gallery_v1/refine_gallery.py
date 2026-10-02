"""Polish approved gallery: structural profiles and existing authored city vista."""
import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector,Matrix
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from gallery_common import M,ROOT,mesh,box,group,outline

def run(scene=None):
    scene=scene or bpy.data.scenes['WORKS_GALLERY_V1']
    if scene.get('city_and_profiles_refined'):return
    bpy.context.window.scene=scene
    for name in ['silver','navy','bronze','ivory','black','glass','warm','leather','leaf','soil','paper','ink','terrazzo']:M[name]=bpy.data.materials['GALLERY_'+name]
    # Roof joists have flat machined faces and a rounded rectangular cross-section.
    profile_data=bpy.data.curves.new('Gallery structural section','CURVE');profile_data.dimensions='2D';profile_data.resolution_u=1
    sp=profile_data.splines.new('POLY');points=outline(.34,.15,.035,5);sp.points.add(len(points)-1)
    for p,(x,y) in zip(sp.points,points):p.co=(x,y,0,1)
    sp.use_cyclic_u=True
    profile=bpy.data.objects.new('Gallery structural bevel profile',profile_data);scene.collection.objects.link(profile);profile.hide_render=True;profile.hide_set(True);profile['export_exclude']=True
    for obj in scene.objects:
        if obj.name.startswith(('Silver roof rib','Front canopy continuous rail')):
            obj.data.bevel_mode='OBJECT';obj.data.bevel_object=profile;obj.data.use_fill_caps=True
    for obj in list(scene.objects):
        if obj.name.startswith(('Distant rounded city tower','City vertical glazed fin','City spire','City elevated transit edge','Landscape leaf')):
            bpy.data.objects.remove(obj,do_unlink=True)
    ground=next(obj for obj in scene.objects if obj.name.startswith('Urban landscape base'))
    ground.dimensions=(1800,1800,1.2)
    ground['export_exclude']=True
    ground['context_note']='Large render ground is excluded from atlases; runtime infinite ground supplied by scene environment.'
    # Reuse the original modeled city behind the first room, not a new flat bitmap.
    source=bpy.data.scenes.get('ENV_CITY.001')
    if source is None:
        old=set(bpy.data.scenes)
        with bpy.data.libraries.load(str(ROOT/'assets/blender/orbital-atelier-v14.blend'),link=False) as (src,dst):
            dst.scenes=['ENV_CITY.001'] if 'ENV_CITY.001' in src.scenes else ['ENV_CITY']
        source=next(s for s in bpy.data.scenes if s not in old and s.name.startswith('ENV_CITY'))
    bpy.context.window.scene=source;source.view_layers[0].update()
    saved=[(obj,obj.matrix_world.copy()) for obj in source.objects if obj.type in {'MESH','CURVE'} and not obj.name.startswith(('Cloud','Infinite_Sky','Large_Distant_Planet'))]
    bpy.context.window.scene=scene
    root=bpy.data.objects['gallery.environment.city'];mat_cache={};transform=Matrix.Translation((-2,18,-1.35))@Matrix.Diagonal((.57,.57,.57,1))
    for original,matrix in saved:
        obj=original.copy();obj.data=original.data.copy();obj.name='Gallery reused city '+original.name;scene.collection.objects.link(obj)
        obj.parent=root;obj.matrix_world=transform@matrix;obj['source_original_city']=original.name
        for key in ['asset_id','stableAssetId','stable_asset_id']:
            if key in obj:del obj[key]
        for i,mat in enumerate(list(obj.data.materials)):
            if not mat:continue
            if mat not in mat_cache:
                clone=mat.copy();clone.name='GALLERY_CITY_'+mat.name;clone['gallery_city']=True
                if clone.node_tree:
                    for n in clone.node_tree.nodes:
                        if n.type=='BSDF_PRINCIPLED':clone['day_emission']=n.inputs['Emission Strength'].default_value
                mat_cache[mat]=clone
            obj.data.materials[i]=mat_cache[mat]
    # Repeat fine compound-leaf plants as mid-distance green terraces.
    import gallery_furnishings as furn
    for i,(x,y) in enumerate([(-10,7),(-7.8,8),(-4.2,7.8),(-1.2,8.4),(2,7.8),(5,8.2),(8.5,8),(10.5,6.7)]):
        before=set(scene.objects);plant=furn.planter('gallery.environment.plant.%02d'%i,x,y,1.95,.36,81+i)
        for obj in set(scene.objects)-before:
            if obj.get('asset_id'):
                obj['bake_atlas']=1;obj['interactive']=False
    # Camera stays tightly focused on the gallery; distant architecture now has perspective depth.
    c=scene.camera;c.data.lens=57;c.location=(17,-28,15.5);c.rotation_euler=(Vector((-.3,.3,1.9))-c.location).to_track_quat('-Z','Y').to_euler()
    scene['city_and_profiles_refined']=True
    scene['reused_city_source']='Original ENV_CITY.001 from orbital-atelier-v14.blend; copied geometry and materials, no source changes'
    return {'cityObjects':len(saved),'newPlantGroups':8,'reusedOriginalGeometry':True}

if __name__=='__main__':print(run())
