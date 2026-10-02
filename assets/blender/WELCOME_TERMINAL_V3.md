# Welcome terminal V3 material release

This is a material-only derivative of the approved V2 terminal. The 27 meshes,
26,868 triangles, all original positions/normals/UV0, four carrier nodes, three
interactive component IDs and the complete `TerminalUnfold` clip remain identical.
No changes were made to the old portfolio project or the active courtyard scene.

## Production and files

All Blender preparation, UV work, material adjustment, real baking, saving and
export used the connected **Blender MCP file-targeted execution tool**. That MCP
tool executes a targeted background Blender process internally; this work is
script-assisted Blender production, not a claim of manual interactive modeling.
The unrelated interactive `Iron_Flower_Courtyard_v03.blend` was checked as saved
and clean and was left unchanged. No direct Blender CLI was launched by the agent.

- Authoring graphs: `welcome-terminal-v3-material-source.blend`.
- Packed editable runtime source: `welcome-terminal-v3.blend`.
- Runtime asset: `../../public/models/welcome-terminal-v3-compressed.glb`.
- Uncompressed export: `../../public/models/welcome-terminal-v3.glb`.
- Real material maps: `../../public/textures/welcome-terminal-v3/`.
- Blender preview: `../../renders/welcome-terminal-v3-materials.png`.
- Reproducible MCP script: `scripts/terminal_material_v3.py`.
- Bake/provenance records: `welcome-terminal-v3-material-report.json`.
- Compression records: `welcome-terminal-v3-compression.json`.

Six body finishes now have independent base colour, roughness/metalness and tangent
normal detail: deep blue anodized/enamel metal, satin titanium, dark rubber, warm
metal trim, ivory ceramic and orange coated controls. Native glTF clearcoat remains
where authored. The display keeps its exact original artwork and emission, with
native dielectric/coat reflection. The procedural material graphs are original
project work; no additional third-party scans or images were introduced here.

## Texture contract and size

A new `SurfaceUV` exports as glTF UV1 while original UV0 is untouched. Three actual
2048×2048 Blender bakes supply sRGB base colour, linear ORM (R=1, G=roughness,
B=metalness), and linear OpenGL tangent normals. Very small ceramic dial markings
receive additional UV area to avoid black, subpixel bake coverage. All six colour
families were sampled from their actual PNGs and compared against V2's palette.

KTX-Software compresses the three maps to UASTC quality 3, RDO .5, Zstd 9, with all
12 mip levels. The screen image remains byte-identical PNG. The compressed model
is 9,317,240 bytes (8.89 MiB), within the explicit V3 budget of 10 MiB. This increased
budget is for new PBR surface data; V2's default 8 MiB test remains unchanged.
Use the existing configured KTX2Loader with GLTFLoader. The runtime source is not
an RGBM scene bake and must retain native glTF standard/physical materials.

## Validation

- `../../docs/validation/terminal-v3-material-data.json`: exact expanded triangles,
  normals, UV0, material assignment, hierarchy, transforms, IDs and clip samples;
  real colour-map sampling and ceramic dial UV coverage.
- `../../docs/validation/terminal-v3-controller.json`: 5/5 controller/asset checks.
- `../../docs/validation/terminal-dock-v3-room-v16.json`: 10/10 actual controller,
  transition, mobile/desktop and desk placement checks against the V16 room.

Run the material audit with the bundled Python runtime (Pillow is required):
`python scripts/verify-terminal-v3.py`. The controller test accepts
`node scripts/check-terminal-v2.mjs public/models/welcome-terminal-v3-compressed.glb --max-mib 10`.

The 64-sample Cycles preview was inspected. These data/controller checks substitute
browser image decoding and PMREM rendering; actual webpage rendering and quality
acceptance remain the integration owner's browser check. No frame-rate guarantee
or completed website replacement is claimed by this asset handoff.
