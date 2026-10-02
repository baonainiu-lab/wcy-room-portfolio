# Gallery V5 lighting restoration

The user's latest main-page feedback was that the gallery lighting had changed and should return to its previous appearance. This change restores only the gallery's complete V5 display path. The Room and Terminal remain on their physical-material path; About is untouched. No Blender operation, new bake, model edit or GPU job was performed for this restoration.

`src/material-release.js` selects `/models/works-gallery-v5-compressed.glb`, `/textures/works-gallery-v5` and revision `gallery-5`, with `galleryPhysical=false`. The configured release at this step is `room18-gallery5-terminal3`; `physical=true` continues to control the Room and Terminal. `src/works-gallery.js` reads the independent gallery flag so Room's LogRGB profile cannot be applied to V5's sRGB textures. The complete legacy release remains available through `?physicalPreview=0`.

The restored gallery uses the original baked day and night maps through the existing linear-space `createDualLighting` blend, plus `createGalleryGlass` and its original sRGB day/night reflection captures with local box projection. It does not add V6's separate F0/normal/GGX layer or local AgX to the V5 bakes. The floor/sky factory, gallery framing, interaction behavior, loader cleanup and existing startup/transition preloading calls are unchanged. The V6 files remain available on disk for controlled future comparison.

## Geometry and interaction preservation

Independent CPU comparison of the actual compressed V5 and V6 GLBs found:

- 142 nodes, 80 meshes, 303 accessors and one scene have identical JSON, including node hierarchy, transforms and extras.
- All 303 accessor payloads match byte-for-byte after respecting buffer-view offsets and strides. The geometry has 542,976 triangles, with unchanged positions, normals and UV0.
- All 77 unique asset IDs match. Interaction metadata is unchanged: 57 nodes explicitly interactive, five explicitly noninteractive.
- Of 307 buffer views, only the four embedded night atlas payloads differ: views 4, 17, 66 and 156. The six material definitions match apart from lightmap metadata; glass materials match completely.

V5 SHA-256: `ca1c285f7198705f972e94bce1d6ffd2d71aaea32a66577f471edc993a712e24`.

Retained V6 SHA-256: `67d1bd18bef30fbd989c3fa77de0dab1d182dfd835c29e180a3065cd6d6d59dc`.

## Validation

`node scripts/check-material-preview.mjs` executes the production factory with the actual V5 and V6 model data. The ten CPU checks cover independent release selection, exact geometry/metadata preservation, the actual V5 glass helper, sRGB endpoints without LogRGB decode or local AgX, fractional day/night synchronization, matching current/fallback V5 requests and shaders, decoder ownership and missing-map/reflection cleanup. Historical V6 LogRGB data and lifecycle coverage remain in the same script. Results are in [material-preview-integration.json](validation/material-preview-integration.json).

Texture decoding, PMREM and environment rendering are explicit CPU test substitutes. Main-page browser validation of the restored appearance and scene switches is handled separately by the integration owner; CPU success is not visual approval or a frame-rate guarantee. The existing complete startup readiness gate remains in place.
