# Room V18 — warm timber architecture

Current stage (2026-09-30): **locally integrated and verified; active by default**. The user explicitly approved colour revision **5b** with “可以，按这版继续” and then asked to continue. The prepared source stayed frozen through all 24 day/night and three clean-intro bakes, two reflection probes and the raw GLB export, completed through file-targeted Blender MCP. Source-bound CPU release validation and actual main-page WebGL checks passed separately. Ordinary visits now use Room V18 / Gallery V6 / Terminal V3; this does not include deployment.

The user clarified that warm timber belongs primarily on the room floor and walls, referring to the approved About atelier. The About scene is excluded. Gallery V6 and Terminal V3 retain the physical material work already completed.

The interior floor is converted from titanium to nonmetallic dark raw walnut. Interior wall faces and the continuous upper caps use the same deep timber family. Exterior platforms, glass, monitor content, equipment and the independent prop hierarchy retain their existing design. The source geometry and original bake UVs remain unchanged.

The walnut colour, roughness and height maps are read-only CC0 sources already used by About, recorded in `assets/textures/about-atelier-v3/texture-manifest.json`. No new third-party asset is introduced. Timber coordinates are calibrated in scene metres, with floor grain running lengthwise and wall grain vertically. Colour, surface relief and roughness are authored separately; this is not a colour overlay on metallic bakes.

Blender production uses the connected file-targeted MCP tools with scripts `assets/blender/scripts/room_warm_v18.py` and `photoreal_materials_v18.py`. The foreground courtyard file is not switched or saved. CPU texture encoding is recorded separately.

Changing these large surfaces also changes diffuse bounce light. All twelve day and twelve night radiance atlases, three clean-intro atlases and the two reflection probes were regenerated. Surface-data slots 0 and 8 were regenerated; the other ten slots are inherited with explicit material-node, geometry, UV and normal equivalence evidence in `assets/blender/room-v18-surface-inheritance.json`.

The active web release uses LogRGB32 gain256, separate surface maps, linear day/night blending and local AgX. The 60-second clock, day-first opening, independent interactions and original object transforms remain in place. The [main-page browser report](validation/room-v18-main-browser.json) records the combined release, including the complete startup preload before the terminal homepage.

Revision 3 preview: `renders/room-materials-v18/warm-review-day-3.png`. It removes the bright upper band, wraps the cap with warm brown timber and deepens the floor after explicit user feedback. Earlier preview bakes are archived, not mixed into this revision.

The archived revision 3 numerical source-bake evidence confirms nonzero warm diffuse response and neutral dielectric F0 near 0.039, replacing the prior coloured metallic F0. Final revision 5b has its own [floor-pixel validation](../assets/blender/room-v18-warm-pixels-validation.json), bound to its approved source and completed baked pixels. These checks verify data/UV propagation, not browser frame rate.


## Rejected colour revision 4 (history)

The user explicitly rejected revision 3 as too pale: “颜色太浅了 我要深色原木质感”. Floor, interior walls and upper caps now use the approved About walnut colour recipe (scan RGB, gamma 1.14, multiply .46/.33/.22), without the pale wall mixture. Roughness spans .40–.58 with restrained .035 coat. Geometry, UVs, object IDs, lighting and the approved About assets are unchanged.

Three separate 24-sample MCP renders are `warm-review-day-4.png`, `warm-review-close-day-4.png`, and `warm-review-night-4.png` under `renders/room-materials-v18/`. The original night lights remain; direct sunlight naturally lifts the lit timber even when the underlying wood is dark. These are Blender preview renders, not screenshots of an activated web release.

Archived revision 4 prepared SHA: `95937fcb228952eaf24659ff368f70f56c3dec1fe39041ace43af4e4e8a99c39`. Source, maps and compression records from previous colours are archived. No prior-colour lighting may be reused for the final source.

User response to the revision 4 colour question: **还要更深**. Revision 4 was not approved.

## Approved colour revision 5b

Explicit approval is recorded in `assets/blender/room-v18-colour-approval.json`. The final smoked raw-walnut floor uses linear RGB tint .18/.12/.075; walls and continuous upper caps use .23/.16/.10. Wood gamma is 1.14, roughness .48–.64 and coat weight .01. Plank joints use the local scanned timber colour multiplied by .72, avoiding pale artificial joint lines. Original lighting, geometry, UVs, IDs and the About assets remain unchanged.

Frozen prepared source SHA: `80fbfa84eb4cc2cf8beea3a4a44e5978823de49ac6227cfa1549a61dd776ab79`.
Editable source SHA: `be32f059cce1727251da6c43d55cb022174e0dc6d39451e1ae8cac060905e632`.

Only completed manifests matching this source and their actual output hashes may be consumed. Rejected-colour bakes cannot be reused for radiance. The complete bake, CPU encoding, geometry validation and actual browser review passed before enabling the web default. `?physicalPreview=0` retains the previous complete release for comparison.

## MCP production completion

`assets/blender/room-v18-mcp-bake-delivery.json` records all 27 source-bound radiance manifests, two 2048×1024 HDR probes, source fingerprints and raw export. Each radiance map used 96 Cycles samples; probes used 64. Actual night HDR multipliers are atlas 0: 2, atlas 2: 2, atlas 4: 8; all other atlases: 1. The 5,620 float channels above RGBM32's archival range are retained separately for exact restoration before LogRGB encoding, rather than accepted as clipped highlights.

The raw GLB is `public/models/orbital-atelier-v18.glb`, SHA `11e0449c84a38fc8458c81fc68eecdf92ddda26d99bcc5005add16b790622897`, 50,477,268 bytes. It has 413,855 triangles, 102 draw primitives, 197 nodes and the same 95 independent asset IDs as V16. The material audit covers 117 source materials, including five warm architectural overrides. Final CPU validation additionally compares actual geometry/UV buffers, hierarchy and transforms against V16 and checks the frozen About assets.

## Local integration verification

The [local release inventory](../assets/blender/room-v18-local-release.json) and [CPU release report](../assets/blender/photoreal-materials-v18-validation.json) record the final compressed model, 54 runtime textures and two HDR probes. The independent final runtime rerun passed 20 startup checks, seven material-release integration checks and ten LogRGB checks. All 38 approved About baseline hashes matched; About's assets and material configuration were not reauthored.

In the actual main page, normal `?qa` loaded Room18 / Gallery6 / Terminal3 and reached 100% with all startup stages ready and both satellite transitions prepared before revealing the welcome terminal. Daylight retained the deep walnut appearance. Night near dayMix 0 and zoomed-out inspection showed no broad black texture blocks in the observed views. Repeated wheel input triggered the opening once; keyboard Enter completed the opening at 390×844, and resizing to 1280×720 worked. The physical run recorded no console warnings or errors. The reduced-motion route also reached full readiness before welcome; skip completed once, restored controls and left the clock paused at daylight 10:00 without errors.

First Gallery and About entries kept observed asset requests at 82 and shader programs at 113. Gallery transition frame times were p50 8.4 ms, p95 17.6 ms and max 43.4 ms across 200 samples; About measured p50 8.4 ms, p95 16.8 ms and max 25.0 ms across 190 samples, retaining its −34 leftward offset. The legacy controlled About preload failure held the loader at 78% and recovered through retry. The final Vite build passed with 62 modules in 8.21 seconds. See [startup behavior and measurements](STARTUP_PRELOAD.md) and the [main-page browser report](validation/room-v18-main-browser.json).

These are local implementation QA observations, not a new user visual approval or a guarantee of 120 FPS or universally stutter-free rendering. Physical touch hardware was not exercised. The successful build retained the existing large-bundle advisory. Small-mip compression limitations remain documented in the [physical-surface contract](PHYSICAL_SURFACE_CONTRACT.md).
