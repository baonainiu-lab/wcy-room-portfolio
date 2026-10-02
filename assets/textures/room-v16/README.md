# Room V16 material inputs

These inputs refine the existing V15 room surfaces. No geometry, object IDs,
parenting, transforms, normals or UV layouts are changed by preparation.

- `directional-brush-2k.png`: project-authored, deterministic seamless 2048²
  machining grain, seed 16092026. Used at a fixed physical scale for satin
  titanium, the graphite finish and the titanium floor.
- `ceramic-microfinish-2k.png`: project-authored, deterministic seamless 2048²
  roughness variation. Ceramic normals remain smooth, including the repaired
  continuous white work-chair shell.
- Cloth reuses the verified existing CC0 `hessian_230` height and roughness
  scans in `assets/textures/about-atelier-v3/hessian_230`. Only luminance
  modulates the authored orange/charcoal color; the beige scan color is not
  applied. The original license and source hashes are copied into
  `manifest.json`.

The shader uses world positions in metres and explicit three-plane image
sampling weighted by world normals. It remains stable when temporary bake
meshes with different transforms are joined; Blender's object-normal BOX
projection is not used. The existing `UVMap` and `BakeUV` remain untouched.
Normal perturbations are restrained to 18–40 micrometres for finishes and
0.9–1.2 mm for textile height at 0.35 strength; the scan repeat keeps yarns
readable above the atlas texel scale. Final output is a paired set of Cycles day
and night combined lightmaps, using the existing 12 atlas slots.

Production record: this completed V16 batch used background Blender and
`assets/blender/scripts/photoreal_materials_v16.py`, before the user's latest
MCP-first workflow instruction. For future Blender changes, inspect and use
the connected Blender MCP first; the commands below document this batch's
provenance, not a default instruction to bypass MCP.

1. `--prepare` creates the V16 editable and prepared derivatives from V15.
2. `--preview` renders the ceramic, textile and metal inspection views.
3. `--bake` bakes both states with 96 samples, resuming verified completed slots.
4. `--export` exports the existing hierarchy with embedded night lightmaps.
5. `python3 scripts/compress-room-v16.py` encodes the runtime model and textures.
6. `python3 scripts/verify-room-v16.py` compares mesh buffers, UVs, IDs and
   transforms against the released V15 model.
7. Run background Blender with `assets/blender/scripts/bake_intro_clean_v16.py`
   to produce matching 96-sample clean receiver maps for slots 0, 1 and 8.
   This reuses the original intro lighting and receiver isolation without
   changing the prepared source or the existing intro-clean-v1 release.
8. `python3 scripts/compress-intro-clean-v16.py` verifies all three maps share
   the current prepared source hash, then encodes their KTX2 textures.

The runtime contract remains `WEB8_LIGHTMAP_0` through `WEB8_LIGHTMAP_11`,
with paired maps in `public/textures/lighting-v16/` and the clean intro maps
in `public/textures/intro-clean-v16/`. The window and screen inputs are copied
byte-for-byte from V15. The existing 60-second day/night controller consumes
the matching states without a geometry or material-slot migration.

Every render and bake acquires `/tmp/room-portfolio-blender-gpu.lock` with
`fcntl.flock`, releasing it between individual jobs. The interactive Blender
session and all V15 files remain untouched.
