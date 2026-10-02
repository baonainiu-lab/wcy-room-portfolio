# Works gallery V6 material release

Current selection (2026-09-30, after main-page review): the user requested the previous Gallery lighting. The configured local release now restores Gallery V5's original sRGB day/night bakes and box-projected glass reflections, independently of the physical Room and Terminal. V6 assets and the implementation below are retained for later comparison; they are no longer the default Gallery. See [the focused V5 restoration record](GALLERY_V5_LIGHTING_RESTORE.md). Earlier V6 browser observations below remain historical evidence, not approval of the restored main-page appearance.

The 2026-09-30 material request covers the main room, works gallery and terminal. The user explicitly approved the existing About atelier and excluded it from this work.

V6 reauthors all 15 used gallery material families through file-targeted Blender MCP operations. The editable source is `assets/blender/works-gallery-v6.blend`; the fixed bake source is `assets/blender/works-gallery-bake-v6.blend`. The connected interactive courtyard file was not switched or modified. Script-assisted node authoring and Cycles bakes are recorded in `assets/blender/works-gallery-v6`; this is not described as manual modeling.

The finishes include petrol powder coating, brushed aluminium, champagne brass, photographed leather and mineral aggregate, glazed porcelain, cotton paper, rubber, leaves, soil and low-iron glass. Existing CC0 texture provenance remains in `assets/textures/about-atelier-v3/texture-manifest.json`. The About scene itself is not changed.

Four atlases retain their geometry, UV layout, hierarchy and 77 independent asset IDs. Eight 64-sample day/night diffuse-and-emission maps exclude baked glossy response. Four F0/roughness maps and four tangent normal maps provide camera-dependent surface response, with matching linear HDR environment captures. Runtime GGX and Fresnel glass use those probes without additional per-frame scene renders. Geometry and all non-atlas GLB buffers are byte-checked against V5.

The original linear radiance is archived as RGBM32 PNG. Direct lossy compression of its multiplier alpha created black blocks in a real browser. The final web files use LogRGB32 gain256 with constant alpha one. Both the base level and every mip are encoded from linear radiance; normal and roughness mips use their respective vector and squared-roughness filtering. The permanent `.logrgb.png` files and KTX2 carry the same encoding. See `validation/linear-surface-logrgb256.json` for measured compression errors and the rejected codecs.

Runtime surfaces decode to linear radiance before day/night and intro mixing, add the independent GGX environment response and apply AgX once. Global renderer tone mapping remains unchanged, protecting the approved About appearance. This is a real-time single-base-lobe approximation; separate source anisotropy, sheen, clearcoat lobes and refractive ray tracing are not reproduced independently.

Local browser review at 1280×720 verified the actual ASTC-compatible KTX2 path, day, night, 50% blend, and a closer tabletop view. There were no shader errors or visible black compression blocks. The scene reported 77 assets, eight surface data textures, two reflection probes, 15 glass meshes, 82 draw calls and 544,818 rendered triangles including the surrounding runtime surfaces. These observations are not a promise of sustained 120 FPS on every device.

Files are local only. Release hashes and preserved-buffer checks are in `assets/blender/works-gallery-v6/release.json`; runtime/ownership tests are in `validation/material-preview-integration.json`, `validation/logrgb-runtime.json` and `validation/physical-surface-v1.json`.
