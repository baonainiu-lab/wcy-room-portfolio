# Room V18 dark timber material review

Current colour revision **5b awaits the user's explicit colour confirmation**. Bulk baking and CPU compression remain paused. No V18 web model has been exported or activated.

The user requested dark raw wood on the interior floor, wall faces and upper trim, then asked twice for a darker result. Revision 5b is near-black brown smoked walnut. It changes the actual material shader, not the lights, exposure or whole rendered image. The exterior platforms/frame, metal trim, screen/window artwork, chairs, robots and all small props retain their comprehensive V17 materials. About is approved and unchanged.

## Current editable and prepared sources

- `assets/blender/orbital-dual-bake-v18.blend`: `80fbfa84eb4cc2cf8beea3a4a44e5978823de49ac6227cfa1549a61dd776ab79`.
- `assets/blender/orbital-atelier-v18.blend`: `be32f059cce1727251da6c43d55cb022174e0dc6d39451e1ae8cac060905e632`.
- Material derivation: `assets/blender/scripts/room_warm_v18.py`.
- Per-atlas MCP bake/export functions: `assets/blender/scripts/photoreal_materials_v18.py`.
- Reports: `assets/blender/photoreal-materials-v18-{prepared,source}.json`, including recipe hashes and pending-colour approval state.

Geometry, hierarchy, object IDs, material-slot indices, transforms, normals and BakeUVs remain exactly unchanged from V17. The prepared geometry fingerprint is `ce76d4db5bbc10aee7eb1fa212d83a62a1be20954ce73b4567753cccecff8f1b`.

All Blender work uses file-targeted Blender MCP isolated processes. This task does not switch, open, save or modify the unrelated interactive courtyard file; the user or other tasks may independently edit that foreground project.

## Actual physical finish

Verified CC0 walnut RGB/roughness/height maps are read-only inputs from `assets/textures/about-atelier-v3/walnut_veneer`. No About source, image or runtime files are modified. The scene uses the actual scanned RGB colour rather than grayscale multiplied by the previous blue-gray material.

All timber uses albedo gamma 1.14, roughness .48–.64 and coat .01. Floor RGB tint is (.18, .12, .075); wall/cap tint is (.23, .16, .10). No pale cream mix remains. The 1.65 m footprint is an authored physical calibration; vendor physical-size metadata is unavailable. Grain follows world X on the floor, world Z on wall faces and the length of each top beam. World-space mapping remains stable on joined bake proxies.

Only interior floor/wall/cap materials in atlas 0/8 are changed. Bounded shader masks preserve every original face/material index. Original six-millimetre floor grid tubes keep their geometry but receive timber colour. Narrow procedural plank joints use local timber RGB multiplied by .72, so they cannot become pale lines when the wood darkens. There is no geometry displacement. The prior white-beige caps are replaced by continuous dark timber.

## Review images

The current independent real 24-sample MCP review images are in `renders/room-materials-v18`:

- `warm-review-day-5b.png`: overall daylight, 1100×825.
- `warm-review-close-day-5b.png`: visible wall/floor grain, 1400×1050.
- `warm-review-night-5b.png`: original night lights, 1100×825.

Revision 5b changes only the narrow plank-joint colour relative to revision 5. All revision 4/5 images remain untouched. Earlier source revisions and any superseded bakes are preserved under `assets/blender/room-v18-review-history/review1…review5` (the first review uses `review1-` file prefixes). Revision 3 had twelve day and two night atlases completed before the user requested darker wood; those maps and exact float overflow intermediates were archived together and are not valid current-revision lighting.

## Work after explicit colour approval

The changed large diffuse floor/walls affect indirect light throughout the scene. Recompute all twelve day and twelve night diffuse/emission atlases at 96 samples, the three receiver-only intro atlases and two 2K HDR probes. Rebake surface-data slots 0/8. Other ten F0/roughness/normal pairs can be inherited only after full shader-node graph/image/parameter and receiving geometry/BakeUV/normal/world-transform equality is revalidated and explicit inheritedFrom provenance is written. `room-v18-surface-reuse-proof.json` currently provides that read-only source comparison; no current-revision lighting reuse is permitted.

Runtime contract stays LogRGB32 gain256 with constant alpha, restored source float overflow plus recorded per-atlas radiance scales, linear F0 RGB/perceptual roughness alpha, OpenGL tangent normals, and matching true scene-linear HDR probes. Original raw RGBM PNGs are retained; web fallbacks use `.logrgb.png`. Complete KTX2 mip chains are filtered in decoded linear radiance before encoding. The actual final night scales must be computed from the approved source, not assumed from V17 or rejected colour revisions.

Future paths remain `public/textures/lighting-v18`, `public/textures/intro-clean-v18` and `public/models/orbital-atelier-v18[-compressed].glb`. Source-bound complete manifests, texture/model hashes, geometry/UV/ID validation and browser QA are required before activation. The pause marker `assets/blender/room-v18-PAUSED` remains present until colour approval is explicit.
