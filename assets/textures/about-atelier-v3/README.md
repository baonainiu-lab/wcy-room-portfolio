# About Atelier V3 — texture sources and material preparation

Checked and downloaded 2026-09-29 for the user-approved archive-workshop
reference. These files belong only to the new offline Blender approval scene.
They have not been copied into the website runtime or approved for web performance.

## Sources

| Surface | Official asset | Creator | Files kept | Colour treatment |
| --- | --- | --- | --- | --- |
| Cabinet, desk trim, slatted divider | [Walnut Veneer](https://polyhaven.com/a/walnut_veneer) | Jenelle van Heerden / Poly Haven | Diffuse, Rough, Displacement, OpenGL normal; 2K JPG | Dark walnut finish via linear shader tint; original files unchanged |
| Chair, tool roll, desk writing surface | [Brown Leather](https://polyhaven.com/a/brown_leather) | Rob Tuytel / Poly Haven | Diffuse, Rough, Displacement, OpenGL normal; 2K JPG | Cognac seat and darker desk variants; original files unchanged |
| Fabric samples and woven rug | [Hessian 230](https://polyhaven.com/a/hessian_230) | Photography: colormass; processing: Rico Cilliers / Poly Haven | Diffuse, Rough, Displacement, OpenGL normal; 2K JPG | Neutral warm woven finish |
| Platform and trophy plinths | [Terrazzo 001](https://ambientcg.com/view?id=Terrazzo001) | ambientCG / Lennart Demes | Color, Roughness, Displacement, NormalGL; 2K JPG | Warm ivory tint; polished roughness range |
| Lake panorama and environment lighting | [Lake Pier](https://polyhaven.com/a/lake_pier) | Alexander Scholten / Poly Haven | Equirectangular HDR; 2048 × 1024 | Original pixels unchanged; orientation and intensity set in the world shader |

The four PBR sets contain **16 source maps, 42.36 MiB**. Poly Haven walnut and leather maps
are 2048 × 2048; Hessian maps are 2048 × 2036; ambientCG maps are 2048 × 2048.
Exact individual byte counts, source URLs, SHA-256 hashes, dimensions and
original source MD5 hashes where supplied are recorded in
[`texture-manifest.json`](texture-manifest.json). Poly Haven official download
metadata is retained as `official-files.json` in each source subfolder.

Lake Pier is recorded separately in
[`landscape/manifest.json`](landscape/manifest.json), including its official
source and download URLs, author, CC0 license, dimensions, byte count and hashes.
The local `landscape/lake_pier_2k.hdr` is **6,412,039 bytes**. This is a
photographed lake panorama used for the offline Blender world background and
environment lighting; the visible lake and distant scenery are not modeled,
walkable terrain. The surrounding windows, floor, columns, rugs and plants are
separate scene geometry.

## License evidence

All four PBR texture sets and the Lake Pier HDRI are **CC0 1.0 Universal**. The local
[`LICENSE-CC0-1.0.txt`](LICENSE-CC0-1.0.txt) is the complete official legal text,
downloaded from
<https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt>.

- [Poly Haven official license](https://polyhaven.com/license) states:
  “Our assets are all licensed as CC0”. Each linked texture page separately
  identifies its CC0 status; the Lake Pier record retains the same license
  evidence for the HDRI. Asset files may be used, modified and redistributed
  commercially. Poly Haven website text and example renders have separate terms;
  no site screenshots or example renders are used as project textures.
- [ambientCG official license](https://docs.ambientcg.com/license/) states:
  “All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License.”
  The Terrazzo001 download was obtained through the official asset page and
  official redirected download host. Its ZIP hash is retained in the manifest.

Credits are retained for provenance even though attribution is not required by CC0.
No paid stock, third-party model geometry, or unverified HDRI is included.

## Blender material implementation

`assets/blender/scripts/about_atelier_v3/materials.py` returns the full
22-key material contract used by the geometry builder:
`wood`, `wood_z`, `wood_dark`, `brass`, `navy`, `dark`, `metal`, `ivory`,
`paper`, `leather`, `desk_leather`, `rubber`, `stone`, `glass`, `light`,
`leaf`, `leaf_light`, `soil`, `ceramic`, `fabric`, `orange`, `ink`.

- Actual-size Object coordinates keep surface detail fixed to each independent
  prop during its future motion. Walnut uses three explicit **FLAT** image
  projections, each with independent coordinates for its plane. Their blend
  weights are the fourth powers of the absolute object-space normal components,
  normalized by their sum: `w_i = |n_i|^4 / (|n_x|^4 + |n_y|^4 + |n_z|^4)`.
  The horizontal and dark walnut variants use local X grain; vertical walnut
  uses local Z grain. Leather, terrazzo and fabric retain unrotated BOX
  projection with blended seams. This avoids the collapsed wood sampling that
  occurred when rotating the input vector of a BOX projection.
- Albedo is sRGB. Roughness and height are Non-Color. Original GL normal maps
  are preserved for a future UV-unwrapped export; the current triplanar material
  uses the real source height in a subtle Bump node, avoiding incorrect
  UV-tangent normal directions across differently projected faces.
- Geometry relief is not exaggerated: walnut bump distance 0.32 mm, leather
  0.6–0.75 mm, polished terrazzo 0.22 mm and woven fabric 1.8 mm, each with
  reduced strength. The material deliberately adds no displacement subdivision.
- Walnut has shallow satin clearcoat. Leather has a softer coat and broad
  highlights. Stone retains fleck colour variation and smooth polished response.
- Original procedural finishes add restrained microroughness to brass, steel,
  enamel, paper, ceramic and foliage. These are original shader graphs, not
  downloaded third-party maps.
- Glass uses real transmission **1.0**, **IOR 1.46**, **roughness 0.055** and
  requires actual closed thickness in the geometry. It is not an alpha-only
  stand-in. The warm diffuser emits softly; light-object energy is configured
  by the scene builder.
- Referenced albedo, roughness and height images are packed automatically when
  the material builder loads them. `environment.py` also packs the Lake Pier
  HDRI and records its author and CC0 license on the image. The current scene
  contains **12 referenced PBR images plus 1 HDRI**, so the `.blend` remains
  portable; the four retained GL normal maps are not currently connected.

Source images have been visually checked. Python syntax and file/hash/size
validation passed. Final Blender shader rendering and model approval belong to
the root task's scene validation; this preparation step makes no FPS claim.

## First-render review adjustment

The initial scene was too evenly illuminated and the finishes read as pale
plastic. The root scene task reduced fill/exposure; the material pass independently
deepened walnut to `(0.46, 0.33, 0.22)` linear tint with gamma 1.14, deepened the
cognac leather to `(1.12, 0.78, 0.54)` with gamma 1.06, reduced broad clearcoat
highlights, warmed stone to `(0.86, 0.77, 0.63)`, and increased visible fabric yarn
size to approximately 8–10 mm for the hero camera (1.2 texture repetitions/m).
No source bitmap pixels were edited. All corrections are reversible shader
nodes. Glass optical parameters remain physical; strong capsule distortion
was flagged to the geometry author as a potential smooth-normal problem at
the joined bottom shell rim, requiring a support ring or normal boundary.
