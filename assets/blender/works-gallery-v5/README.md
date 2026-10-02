# Gallery V5 material refinement

V5 is a material-only derivative of the approved Gallery V4. It preserves all
77 independent asset IDs, exact geometry, hierarchy, original transforms, and
all existing UV coordinates. No preparation/unwrapping pass is run again.

- Stone inset floor and display table: photographed ambientCG Terrazzo001,
  0.5 m repeat, restrained cool mineral tint, scanned roughness and height.
- Saddle-brown bench: Poly Haven Brown Leather, 0.4 m repeat, photographed
  roughness and fine height, original warm-brown design retained.
- Silver/champagne trims: stable metre-based brushing with 25 micrometre bump;
  navy and paper retain their colours with restrained fine roughness.
- World-space explicit triplanar projections keep the source and disposable
  joined bake proxies consistent. Tangent normal images are retained in the
  source library; projected surfaces use scanned height rather than invalid
  UV-tangent normal vectors.

Both texture libraries are CC0 1.0. Creators: ambientCG / Lennart Demes
(Terrazzo001), Rob Tuytel / Poly Haven (Brown Leather). Existing official
source URLs, download hashes, and license evidence remain in
`assets/textures/about-atelier-v3/texture-manifest.json`, its README, and
`LICENSE-CC0-1.0.txt`. Original photographs are unmodified; colour tints are
material parameters. The source maps are packed into the V5 derivatives.

Editable source: `assets/blender/works-gallery-v5.blend`.
UV-preserving bake source: `assets/blender/works-gallery-bake-v5.blend`.
Scene names intentionally remain `WORKS_GALLERY_V4` / `WEB_WORKS_GALLERY_V4`
for the established exporter interface.

Build order: `refine_materials.py`, `render_material_review.py` (inspect true
Cycles close-up), `bake_and_export.py`, `render_reflection_probes.py --render`,
`scripts/compress-works-gallery-v5.py`, `compress_reflection_probes.py`, then
`validate_delivery.py`. Scripts live in `assets/blender/scripts/works_gallery_v5`.
Each GPU atlas/render obtains `/tmp/room-portfolio-blender-gpu.lock` and releases
it afterwards. V4 files and interactive Blender are never overwritten.

The final delivery audit records exact non-image GLB buffer equality with V4,
the 77 IDs, 64-sample paired atlas provenance, and compressed artifact hashes.
The runtime continues to use paired baked lightmaps and existing independent
hover behaviour; no performance claim is made by this offline material audit.
