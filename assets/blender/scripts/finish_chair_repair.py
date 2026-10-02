import bpy,json,struct,hashlib
from pathlib import Path
ROOT=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio');s=bpy.data.scenes['WEB_CHAIR_REBAKE'];scene=bpy.data.scenes['WEB_BAKE_V4']
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
path=ROOT/'assets/textures/baked/room-chair-repaired.png';bpy.data.images['ROOM_CHAIR_REPAIRED'].save_render(str(path),scene=s)
im=bpy.data.images.load(str(path),check_existing=False);im.colorspace_settings.name='sRGB';im.pack()
mat=bpy.data.materials.new('WEB_BAKED_CHAIR_REPAIRED');mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im;uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='BakeUV'
nt.links.new(uv.outputs[0],tex.inputs[0]);nt.links.new(tex.outputs[0],em.inputs[0]);nt.links.new(em.outputs[0],out.inputs[0])
source=bpy.data.objects['WEB_CHAIR_HIGH_BAKE'];target=next(o for o in scene.objects if o.get('web_kind') and o.parent and o.parent.get('asset_id')=='furniture.lounge')
target.data=source.data.copy();target.matrix_world=source.matrix_world.copy();target.data.materials.clear();target.data.materials.append(mat)
for p in target.data.polygons:p.material_index=0
for layer in list(target.data.uv_layers):
 if layer.name!='BakeUV':target.data.uv_layers.remove(layer)
target['web_chair_repair']='Full source silhouette and stitching, dedicated 2048 atlas,32px adjacent-face padding'
bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
 if o.type=='EMPTY' or o.get('web_kind'):o.select_set(True)
script=(ROOT/'assets/blender/scripts/export_baked_web.py').read_text();exec(compile(script[script.index("path=ROOT/'public/models"):],'export_baked_web.py','exec'))
result['chair_repair']='High resolution source silhouette + dedicated 2048 atlas with 32px padding'
(ROOT/'assets/blender/web-baked-export-report.json').write_text(json.dumps(result,indent=2)+'\n')
