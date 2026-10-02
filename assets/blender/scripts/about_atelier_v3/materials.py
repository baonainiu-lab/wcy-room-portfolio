"""Physically based material library for the approved About Atelier V3.

Blender 4.3+/5.1. No geometry or lights are created here. Texture maps are
licensed CC0; provenance is in assets/textures/about-atelier-v3/README.md.
Object-space metre coordinates deliberately survive independent prop motion.
Wood uses three explicit FLAT projections with object-normal blend weights;
other finishes use unrotated BOX projection. Scanned height supplies bump so
projected faces do not receive incorrect UV-tangent normal vectors. GL maps
are retained for a future UV-unwrapped, web-ready export.
"""
from pathlib import Path
import bpy

TEX = Path(__file__).resolve().parents[3] / 'textures' / 'about-atelier-v3'
PREFIX = 'ATELIER_V3_'


def _color(h):
    x = [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in x) + (1,)


def _base(name, color, rough=.4, metallic=0):
    material = bpy.data.materials.get(PREFIX + name) or bpy.data.materials.new(PREFIX + name)
    material.use_nodes = True
    material.diffuse_color = _color(color)
    material['asset_library'] = 'about-atelier-v3'
    nodes = material.node_tree.nodes
    nodes.clear()
    p = nodes.new('ShaderNodeBsdfPrincipled'); p.location = (520, 160)
    p.inputs['Base Color'].default_value = _color(color)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metallic
    out = nodes.new('ShaderNodeOutputMaterial'); out.location = (850, 160)
    material.node_tree.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    return material, p


def _mapping(mat, scale=(1, 1, 1), rotate=(0, 0, 0)):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new('ShaderNodeTexCoord'); tc.location = (-1020, 240)
    tc.label = 'Object coordinates in metres (applied geometry scale)'
    mapping = nodes.new('ShaderNodeMapping'); mapping.location = (-820, 240)
    mapping.vector_type = 'POINT'
    mapping.inputs['Scale'].default_value = scale
    mapping.inputs['Rotation'].default_value = rotate
    links.new(tc.outputs['Object'], mapping.inputs['Vector'])
    return mapping.outputs['Vector']


def _image(mat, filename, vector, color=False, location=(-560, 200), projection='BOX'):
    path = TEX / filename
    if not path.is_file():
        raise FileNotFoundError('Required verified Atelier PBR map is missing: ' + str(path))
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    if not im.packed_file:
        im.pack()
    im['license'] = 'CC0-1.0'
    im['provenance_manifest'] = 'assets/textures/about-atelier-v3/texture-manifest.json'
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = im
    node.projection = projection; node.projection_blend = .18
    node.extension = 'REPEAT'; node.interpolation = 'Linear'
    node.location = location
    mat.node_tree.links.new(vector, node.inputs['Vector'])
    return node


def _wood_coordinates(mat, repeat, grain_axis):
    """Explicit 2D projection on every face; never rotate a BOX vector.

    A rotated vector fed to BOX can collapse a face to a single row because
    BOX still chooses its plane using the original object normal. Instead,
    each axis receives its own two independent in-plane coordinates.
    """
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    vector = _mapping(mat, (repeat,) * 3)
    xyz = nodes.new('ShaderNodeSeparateXYZ'); xyz.location = (-1900, 100)
    links.new(vector, xyz.inputs['Vector'])
    if grain_axis == 'X':
        planes = {'X': ('Y', 'Z'), 'Y': ('Z', 'X'), 'Z': ('Y', 'X')}
    elif grain_axis == 'Z':
        planes = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}
    else:
        raise ValueError('Wood grain_axis must be X or Z')
    vectors = {}
    for i, (axis, (u, v)) in enumerate(planes.items()):
        combine = nodes.new('ShaderNodeCombineXYZ')
        combine.location = (-1650, 200 - i * 190)
        combine.label = axis + ' face: U=' + u + ', V=' + v
        links.new(xyz.outputs[u], combine.inputs['X'])
        links.new(xyz.outputs[v], combine.inputs['Y'])
        combine.inputs['Z'].default_value = 0
        vectors[axis] = combine.outputs['Vector']

    geo = nodes.new('ShaderNodeNewGeometry'); geo.location = (-2300, -700)
    local = nodes.new('ShaderNodeVectorTransform'); local.location = (-2100, -700)
    local.vector_type = 'NORMAL'; local.convert_from = 'WORLD'; local.convert_to = 'OBJECT'
    links.new(geo.outputs['Normal'], local.inputs['Vector'])
    absolute = nodes.new('ShaderNodeVectorMath'); absolute.operation = 'ABSOLUTE'
    absolute.location = (-1900, -700)
    links.new(local.outputs['Vector'], absolute.inputs[0])
    split = nodes.new('ShaderNodeSeparateXYZ'); split.location = (-1700, -700)
    links.new(absolute.outputs['Vector'], split.inputs['Vector'])
    powers = {}
    for i, axis in enumerate('XYZ'):
        power = nodes.new('ShaderNodeMath'); power.operation = 'POWER'
        power.location = (-1500, -700 - i * 150)
        power.inputs[1].default_value = 4.0
        links.new(split.outputs[axis], power.inputs[0]); powers[axis] = power.outputs[0]
    add_xy = nodes.new('ShaderNodeMath'); add_xy.operation = 'ADD'; add_xy.location = (-1270, -700)
    links.new(powers['X'], add_xy.inputs[0]); links.new(powers['Y'], add_xy.inputs[1])
    add_z = nodes.new('ShaderNodeMath'); add_z.operation = 'ADD'; add_z.location = (-1090, -700)
    links.new(add_xy.outputs[0], add_z.inputs[0]); links.new(powers['Z'], add_z.inputs[1])
    weights = {}
    for i, axis in enumerate('XYZ'):
        div = nodes.new('ShaderNodeMath'); div.operation = 'DIVIDE'
        div.location = (-900, -700 - i * 150); div.label = 'Normalized ' + axis + ' plane weight'
        links.new(powers[axis], div.inputs[0]); links.new(add_z.outputs[0], div.inputs[1])
        weights[axis] = div.outputs[0]
    return vectors, weights


def _triplanar_image(mat, filename, coordinates, color, y):
    """Sample three 2D images and normalize the object-normal weighted blend."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    vectors, weights = coordinates
    weighted = []
    for i, axis in enumerate('XYZ'):
        im = _image(mat, filename, vectors[axis], color,
                    (-700 - i * 330, y), projection='FLAT')
        im.label = ('Albedo ' if color else 'Data ') + axis + '-face projection'
        scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
        scale.location = (-660 - i * 330, y - 330)
        links.new(im.outputs['Color'], scale.inputs[0])
        links.new(weights[axis], scale.inputs['Scale'])
        weighted.append(scale.outputs['Vector'])
    add_xy = nodes.new('ShaderNodeVectorMath'); add_xy.operation = 'ADD'
    add_xy.location = (-410, y - 90)
    links.new(weighted[0], add_xy.inputs[0]); links.new(weighted[1], add_xy.inputs[1])
    result = nodes.new('ShaderNodeVectorMath'); result.operation = 'ADD'
    result.location = (-230, y - 90)
    links.new(add_xy.outputs['Vector'], result.inputs[0]); links.new(weighted[2], result.inputs[1])
    return result.outputs['Vector']


def _pbr(name, base_color, files, repeat, tint=(1, 1, 1), rough_range=(.25, .6),
         bump_distance=.0003, bump_strength=.25, rotation=(0, 0, 0), coat=0,
         albedo_gamma=1.0, grain_axis=None):
    mat, p = _base(name, base_color)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    if grain_axis:
        coordinates = _wood_coordinates(mat, repeat, grain_axis)
        albedo = _triplanar_image(mat, files[0], coordinates, True, 1150)
        rough = _triplanar_image(mat, files[1], coordinates, False, 1650)
        height = _triplanar_image(mat, files[2], coordinates, False, 2150)
    else:
        if any(abs(a) > 1e-8 for a in rotation):
            raise ValueError('Rotated BOX projection is not supported: use explicit plane coordinates')
        vector = _mapping(mat, (repeat,) * 3)
        albedo = _image(mat, files[0], vector, True, (-580, 440)).outputs['Color']
        rough = _image(mat, files[1], vector, False, (-580, 100)).outputs['Color']
        height = _image(mat, files[2], vector, False, (-580, -260)).outputs['Color']
    mult = nodes.new('ShaderNodeVectorMath'); mult.operation = 'MULTIPLY'
    mult.location = (-240, 460); mult.label = 'Linear-space finish tint; source image unchanged'
    mult.inputs[1].default_value = tint
    if albedo_gamma != 1.0:
        gamma = nodes.new('ShaderNodeGamma'); gamma.location = (-370, 640)
        gamma.inputs['Gamma'].default_value = albedo_gamma
        gamma.label = 'Finish density; preserve photographed grain variation'
        links.new(albedo, gamma.inputs['Color'])
        links.new(gamma.outputs['Color'], mult.inputs[0])
    else:
        links.new(albedo, mult.inputs[0])
    links.new(mult.outputs['Vector'], p.inputs['Base Color'])
    remap = nodes.new('ShaderNodeMapRange'); remap.location = (-240, 140)
    remap.inputs['To Min'].default_value = rough_range[0]
    remap.inputs['To Max'].default_value = rough_range[1]
    links.new(rough, remap.inputs['Value']); links.new(remap.outputs['Result'], p.inputs['Roughness'])
    bump = nodes.new('ShaderNodeBump'); bump.location = (210, -80)
    bump.inputs['Strength'].default_value = bump_strength
    bump.inputs['Distance'].default_value = bump_distance
    links.new(height, bump.inputs['Height']); links.new(bump.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = .32
    mat['coordinates'] = ('Object space, explicit three-FLAT triplanar projection, normalized object-normal weights'
                          if grain_axis else 'Object space, metre-based unrotated BOX projection')
    if grain_axis:
        mat['grain_axis'] = grain_axis
    mat['normal_method'] = 'Scanned height through bump; GL tangent normal maps retained separately'
    mat['physical_bump_distance_m'] = bump_distance
    mat['albedo_gamma'] = albedo_gamma
    mat['source_maps'] = ';'.join(files)
    return mat


def _finish(name, color, rough=.4, metallic=0, grain_scale=260, bump=.000025,
            rough_variation=.035, anisotropic=0):
    mat, p = _base(name, color, rough, metallic)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    vector = _mapping(mat)
    noise = nodes.new('ShaderNodeTexNoise'); noise.location = (-540, 200)
    noise.inputs['Scale'].default_value = grain_scale
    noise.inputs['Detail'].default_value = 2
    noise.inputs['Roughness'].default_value = .6
    links.new(vector, noise.inputs['Vector'])
    remap = nodes.new('ShaderNodeMapRange'); remap.location = (-220, 190)
    remap.inputs['To Min'].default_value = rough - rough_variation
    remap.inputs['To Max'].default_value = rough + rough_variation
    links.new(noise.outputs['Fac'], remap.inputs['Value']); links.new(remap.outputs['Result'], p.inputs['Roughness'])
    if bump:
        bump_node = nodes.new('ShaderNodeBump'); bump_node.location = (180, -120)
        bump_node.inputs['Strength'].default_value = .15
        bump_node.inputs['Distance'].default_value = bump
        links.new(noise.outputs['Fac'], bump_node.inputs['Height']); links.new(bump_node.outputs['Normal'], p.inputs['Normal'])
    if 'Anisotropic IOR Level' in p.inputs:
        p.inputs['Anisotropic IOR Level'].default_value = anisotropic
    mat['source'] = 'Original procedural physical surface finish; no third-party image'
    return mat


def materials():
    """Return the complete material-key contract expected by kit.materials()."""
    wood = ('walnut_veneer/walnut_veneer_diff_2k.jpg',
            'walnut_veneer/walnut_veneer_rough_2k.jpg',
            'walnut_veneer/walnut_veneer_disp_2k.jpg')
    leather = ('brown_leather/brown_leather_albedo_2k.jpg',
               'brown_leather/brown_leather_rough_2k.jpg',
               'brown_leather/brown_leather_disp_2k.jpg')
    stone = ('Terrazzo001/Terrazzo001_2K-JPG_Color.jpg',
             'Terrazzo001/Terrazzo001_2K-JPG_Roughness.jpg',
             'Terrazzo001/Terrazzo001_2K-JPG_Displacement.jpg')
    fabric = ('hessian_230/hessian_230_diff_2k.jpg',
              'hessian_230/hessian_230_rough_2k.jpg',
              'hessian_230/hessian_230_disp_2k.jpg')
    m = {}
    # Veneer grain runs along image V. Every local face has its own independent
    # two-axis projection; no rotated BOX input can collapse a broad wood face.
    m['wood'] = _pbr('WalnutHorizontal', '56331D', wood, 1/1.65,
                    (.46, .33, .22), (.29, .43), .00032, .32, coat=.08,
                    albedo_gamma=1.14, grain_axis='X')
    m['wood_z'] = _pbr('WalnutVertical', '56331D', wood, 1/1.65,
                      (.46, .33, .22), (.29, .43), .00032, .32, coat=.08,
                      albedo_gamma=1.14, grain_axis='Z')
    m['wood_dark'] = _pbr('WalnutDark', '452A1C', wood, 1/1.35,
                         (.26, .19, .135), (.32, .49), .00032, .28, coat=.05,
                         albedo_gamma=1.12, grain_axis='X')
    m['leather'] = _pbr('CognacLeather', '864923', leather, 1.8,
                       (1.12, .78, .54), (.35, .53), .00075, .42, coat=.035,
                       albedo_gamma=1.06)
    m['desk_leather'] = _pbr('DarkLeatherWritingSurface', '33271E', leather, 1.8,
                            (.26, .25, .24), (.43, .64), .0006, .38, coat=.015,
                            albedo_gamma=1.08)
    m['stone'] = _pbr('IvoryTerrazzo', 'C8BCA2', stone, 1/1.35,
                     (.86, .77, .63), (.24, .39), .00022, .2, coat=.035)
    # Larger visible yarns keep a genuine woven surface readable in the hero
    # camera instead of being reduced below a pixel by render denoising.
    m['fabric'] = _pbr('NaturalWovenLinen', '968069', fabric, 1.2,
                      (.68, .59, .48), (.78, .96), .0018, .48,
                      albedo_gamma=1.08)
    mp = m['fabric'].node_tree.nodes.get('Principled BSDF')
    mp.inputs['Sheen Weight'].default_value = .1
    mp.inputs['Sheen Roughness'].default_value = .7
    m['brass'] = _finish('SatinBrass', 'BE9250', .24, 1, 410, .000012, .045, .32)
    m['navy'] = _finish('BlueBlackPowderCoat', '1D2931', .32, .55, 450, .00002, .025)
    m['dark'] = _finish('Graphite', '131718', .39, .2, 480, .000025, .035)
    m['metal'] = _finish('BrushedSteel', '92928B', .24, 1, 680, .000009, .03, .4)
    m['ivory'] = _finish('WarmIvory', 'DAD7CB', .43, 0, 350, .00002)
    m['paper'] = _finish('CottonPaper', 'E3DAC4', .76, 0, 720, .000018, .025)
    m['rubber'] = _finish('BlackRubber', '161B1C', .69, 0, 390, .000045, .045)
    m['orange'] = _finish('BurntOrangeEnamel', 'AC552D', .33, .12, 420, .00001, .025)
    m['ink'] = _finish('PrintedCharcoal', '182025', .78, 0, 200, 0, .005)
    m['soil'] = _finish('PottingSoil', '29241B', .92, 0, 120, .001, .045)
    m['ceramic'] = _finish('SandstoneCeramic', 'AFA58C', .6, 0, 390, .0007, .08)
    m['leaf'] = _finish('LeafDeepOlive', '3B4825', .48, 0, 120, .000075, .08)
    m['leaf_light'] = _finish('LeafSunlitOlive', '788041', .44, 0, 120, .000075, .08)
    for k in ('leaf', 'leaf_light'):
        p = m[k].node_tree.nodes.get('Principled BSDF')
        p.inputs['Subsurface Weight'].default_value = .08
        p.inputs['Subsurface Radius'].default_value = (.25, .8, .1)
    m['glass'], p = _base('OpticalGlass', 'FAFEFF', .055)
    p.inputs['Transmission Weight'].default_value = 1
    p.inputs['IOR'].default_value = 1.46
    m['glass']['physical_thickness_required'] = True
    m['light'], p = _base('WarmDiffuser', 'FFE9BC', .33)
    p.inputs['Emission Color'].default_value = _color('FFE4AC')
    p.inputs['Emission Strength'].default_value = 2.8
    m['light']['role'] = 'Visible warm diffuser only; actual scene illumination is controlled by separate lights'
    return m
