# Room / Gallery physical-surface contract

Current local release (2026-10-01): **Room20 / Gallery5 original sRGB lighting / Terminal3**, status `locally_integrated_browser_checked`. Room20 uses white Marble005 walls with grey mineral veining and black Marble002 textured upper caps, preserving V19 floor, ceiling fixture, geometry, UVs, normals, hierarchy and all 96 asset IDs. Source authoring, all fresh bakes, both probes and raw export were completed through file-targeted Blender MCP with Python helpers; no offline CLI fallback was used. CPU verification passed for all 58 KTX textures, 29 fresh lightmaps, two HDR probes, raw/compressed models, official CC0 texture inputs and 434 frozen files including the approved About 38. The default release switch is active and the production build passed. Current desktop browser day/night, intermediate blends, arrow entry, orbit/zoom and both scene round trips passed the reported scope; see [V20 browser evidence](validation/room-v20-main-browser.json). This is local QA, not user visual acceptance or a 120 FPS guarantee. See [Room20 and final hashes](ROOM_V20_WHITE_MARBLE.md), [CPU gate](../assets/blender/photoreal-materials-v20-validation.json) and [execution method](../assets/blender/room-v20-execution-method.json). Current Room directories are `/textures/lighting-v20` and `/textures/intro-clean-v20`; Gallery remains `/textures/works-gallery-v5`. The release records and revision-specific examples below are retained as history.

Update (2026-10-01): current local release is **Room19 / Gallery5 original sRGB lighting / Terminal3**. Room19 adds the3000K ceiling wall-wash, removes9solid floor strips and reduces wood glare. All58 textures,29fresh lightmaps,2HDR probes and the final GLB passed source-bound verification; main-page browser checks cover day/night, opening and first satellite entries. Approved Logo C “轨道星核” is now the native SVG mark and loading background. See [Room19](ROOM_V19_WALL_LIGHT_AND_FLOOR.md), [browser evidence](validation/room-v19-main-browser.json), [logo](BRAND_MARK_V4.md). Following V18/Gallery6 notes are historical.

Status (2026-09-30): the complete Room V18 rev5b / Gallery V6 / Terminal V3 release is locally integrated and verified on the actual main page. Room V18 rev5b is the approved dark-wood direction: all 54 runtime textures, two HDR probes and the final GLB have completed source-bound CPU verification. The combined release passed main-page WebGL and visual checks after the independent Gallery V6 and Terminal V3 checks. `PHYSICAL_MATERIALS_DEFAULT=true` now selects the three-part release on ordinary visits, including `?qa`; `?physicalPreview=0` selects the previous complete Room V16 / Gallery V5 / Terminal V2 release. The approved About scene's source assets, materials, lighting and visual configuration remain unchanged; its existing resources now participate in startup preloading. No deployment is included.

The Room prepared-source SHA is `80fbfa84eb4cc2cf8beea3a4a44e5978823de49ac6227cfa1549a61dd776ab79`. Its 24 day/night and three clean-intro maps were freshly baked through Blender MCP; earlier colour-review GI was not reused. Ten surface-data pairs were inherited only after matching material/geometry/UV proof, and slots 0/8 were rebaked. The final model preserves all 95 asset IDs, 197 nodes and 413,855 triangles, with geometry/UV/hierarchy buffers matching V16. The 38 approved About baseline files remain unchanged. See the [resource list and hashes](../assets/blender/room-v18-local-release.json), [complete CPU release validation](../assets/blender/photoreal-materials-v18-validation.json) and [current floor-pixel measurement](../assets/blender/room-v18-warm-pixels-validation.json). These checks establish source integrity, not main-page visual approval or a frame-rate guarantee.

Independent browser evidence: [Gallery V6](validation/gallery-v6-browser.json) covers day, night, a 50% blend, closer leather/metal views and the absence of the previous black blocks; [Terminal V3](validation/terminal-v3-browser.json) covers the closed and unfolded poses, night emission and local AgX. Both used actual ASTC WebGL textures and reported no shader errors. The [combined main-page report](validation/room-v18-main-browser.json) records startup at 100% before terminal welcome, prepared Gallery/About transitions, first entries without additional observed asset requests or shader programs, single-trigger opening, mobile keyboard entry and resize. Actual Room daylight retained the deep walnut appearance; night near dayMix 0 and zoomed-out inspection showed no broad black texture blocks in the observed views. Console warnings and errors were empty. See [startup measurements and limitations](STARTUP_PRELOAD.md).

The only rollout switch is `PHYSICAL_MATERIALS_DEFAULT` in `src/material-release.js`, now `true` after browser validation; `?physicalPreview=0` continues to force the previous complete release. `main.js` passes the same immutable release object to `createWorksGallery`. The welcome GLTFLoader uses the existing room KTX2Loader for V3; that decoder is released before the live surfaces start their own pool, and clean-intro maps use a separately owned decoder. Runtime diagnostics expose `materialRelease`, `physicalSurface` and each actual model URL through `__roomPreview.getState()` / the existing `?qa` JSON output. New asset load errors stay explicit, dispose partial resources and never silently combine LogRGB and legacy sRGB maps.

Terminal V3 uses native glTF PBR rather than encoded scene-lighting bakes. Its opt-in `src/terminal-tone.js` applies local AgX to the completed native PBR output before sRGB conversion, with exposure 1. It keeps all original roughness, metalness, clearcoat, image maps, emission, light strengths and PMREM intensity. Existing welcome strengths are hemisphere 2.1, directional 3.1 and reflection .9; after docking, its local lights are off and reflection follows 1.1 by day / .3 by night. Such radiance can exceed the display range: global NoToneMapping would clip highlights. AgX compresses that range instead of simply dimming every light. The hook binds only `TERMINAL_*` native PBR materials and is installed only for the physical release; About and the fallback V2 terminal remain unchanged. Diagnostics expose `terminalTone`; its ownership is released before terminal materials. See [terminal-tone-v1.json](validation/terminal-tone-v1.json), five CPU checks, the independent [Terminal WebGL report](validation/terminal-v3-browser.json), and the [completed main-page opening checks](validation/room-v18-main-browser.json).

## Asset data

| File | Encoding | Contents |
| --- | --- | --- |
| Authoring `day-{slot}.png`, `night-{slot}.png` | Raw RGBM32, unchanged | `linearRadiance = 32 * rgb * alpha`; original direct/indirect diffuse + emission, no glossy; not the new web texture representation |
| Web `day-{slot}.ktx2`, `night-{slot}.ktx2` | NoColorSpace, LogRGB32 k256, alpha1 | `(exp2(rgb * log2(8193)) - 1) / 256`; UASTC quality2 + Zstd9, full explicit mip chain |
| `day-{slot}.logrgb.png`, `night-{slot}.logrgb.png` | Same LogRGB as the KTX input | Permanent same-encoding PNG for compatibility/inspection; never substitute the raw RGBM PNG for this file |
| `specular-{slot}.ktx2` | NoColorSpace | RGB = actual linear F0; A = perceptual roughness |
| `normal-{slot}.ktx2` | NoColorSpace | RGB = OpenGL tangent-space normal, A = 1 |
| `reflection-day.hdr`, `reflection-night.hdr` | Linear radiance, same size/orientation | Actual scene probes; prefiltered once with Three PMREM |
| Intro `day-{0,1,8}.ktx2` / `.logrgb.png` | NoColorSpace, LogRGB32 k256, alpha1 | Same source/UVs as room, receiver-only diffuse + emission without absent prop shadows; original authoring `.png` remains RGBM32 |

Directories: `/textures/lighting-v18`, `/textures/works-gallery-v6`, `/textures/intro-clean-v18`. Window and screen art remain their existing sRGB assets. Do not LogRGB- or RGBM-encode the window under its existing material name.

### Encoding and compression evidence

The source Blender bakes remain untouched RGBM32 PNGs. `scripts/compress-linear-surface.py` accepts `kind="logrgb32-k256"`, decodes those sources to floating linear radiance, writes a permanent `.logrgb.png` for level0, then BOX-filters **linear radiance** and re-encodes every lower mip. It never builds level0 from the original RGBM bytes, and never averages encoded LogRGB values when authoring mips. Each manifest records `codecRevision="linear-surface-v2-logrgb256"`, `sourceEncoding="RGBM32"`, the original source SHA and `encodedSource` path/SHA. The old RGBM path remains available for controlled comparisons; new Room/Gallery/intro releases use LogRGB.

The previous RGBM multiplier lived in alpha. UASTC quantized low alpha values to zero, producing large black blocks despite valid source bakes. In the actual Gallery atlas1 comparison, with reference peak radiance >0.005, the old day/night blackened-pixel rates were 10.888% / 11.208%. The new constant-alpha LogRGB rates were **0 / 0**. Level0 peak-relative P99 error is 7.636% / 7.682%; average signed luminance bias is −0.200% / −0.160%. Audited levels 0, 2, 4 and 8 all retained alpha255 and had zero blackened pixels in that domain. The eight recompressed Gallery lightmaps total 17,004,386 bytes.

These are actual CPU `ktx extract --transcode rgba8` comparisons, not an ASTC/BC7 browser claim. Lower mip levels retain larger lossy errors around sparse UV islands and strong contrast. Hardware bilinear filtering also interpolates encoded LogRGB before decoding, an approximation; explicit authored mips correctly average linear radiance. See [linear-surface-logrgb256.json](validation/linear-surface-logrgb256.json) for full candidate comparisons, source/output hashes and the eleven-group codec self-check. No Blender bake was rerun to repair compression. The separate browser checks are local implementation QA, not a new user visual approval.

### Per-atlas HDR overflow

LogRGB range 32 remains global to the codec. A source atlas with retained values above 32 can instead pass `radiance_scale=8` and `radiance_overflow={"path": "...npz", "sha256": "..."}` to `compress`. The NPZ stores float32 values at uint32 indices of the original bottom-up Blender RGB buffer, plus int64 `[H,W,3]`. The compressor verifies the neighboring bake manifest binds both NPZ and raw PNG, converts indices to top-down PNG rows, restores those exact saved channels, and only then divides by the supplied scale. Non-overflow channels retain the original RGBM quantization. It rejects bad hashes, dimensions, duplicate/out-of-range indices, nonfinite values and a scale too small for the restored peak; the recommended scale is the next power of two above `peak/32`.

Each output records `radianceScale`, `radianceOverflow` including source-manifest hashes, `scalingRevision="linear-radiance-overflow-v1"`, source/encoded peaks and the reconstruction formula. Cache reuse must compare the requested scale and overflow SHA in addition to existing kind/source/output checks. Legacy records without these fields mean scale 1/no overflow. The encoding formula and `codecRevision` remain unchanged, so ordinary scale 1 assets are unaffected; a full Gallery day 1 recompression was byte-identical.

Runtime applies `profile.nightRadianceScale[slot]` only to the decoded night endpoint, before mixing it with day. This is stored light-energy normalization, not a brightness redesign. Daylight, clean-intro textures, unscaled slots and Gallery keep their existing energy. The final V18 rev5b manifests independently confirm `{0: 2, 2: 2, 4: 8}`; every other slot uses 1. This is now measured release data, not a placeholder inherited from V17.

For the current V18 night4, all 5,027 saved overflow channels were restored: source peak 143.501, compressed level0 peak 145.429 at scale8. Level0 has no blackened pixels above scene radiance .005; mip2 has 14/243,846 (0.0057%), mip4 has 49/17,774 (0.276%), and mip8 has 2/162 (1.235%). All audited alpha values remain 255. The current [night4 codec audit](../assets/blender/room-v18-night4-codec-audit.json) records these dark/high-contrast small-mip limitations; the [day0 audit](../assets/blender/room-v18-day0-codec-audit.json) has zero blackened pixels at all four audited levels. The earlier Gallery zero-blackout result must not be generalized to every scaled Room mip. Main-page night and zoomed-out inspection found no broad black texture blocks in the observed views; this does not erase the measured small-mip errors or certify every angle and device.

The archived V17 case (5,022 channels, source peak139.899) remains separate evidence in [logrgb-overflow.json](validation/logrgb-overflow.json), including the sixteen-group codec check and scale1 byte comparison. It is not the current V18 bake report.

F0 comes from the original material's base colour, metalness, IOR, Specular IOR Level and tint. A metal can have black diffuse while retaining coloured specular F0. Roughness and normal maps must be baked from original face material assignments, since each lighting atlas contains several surface types. Do not apply one surface value to an entire atlas. Preserve its existing UVs, transforms and independent object IDs. Data maps need padded borders and complete mip chains. Atlas normal direction must use the same tangent UV basis as runtime UV0.

## Activation order

```js
const surface = await createPhysicalSurface({
  THREE, renderer, objects: [room], loader: roomTextureLoader,
  profile: {
    family: 'room', // or 'gallery'; About is rejected
    directory: '/textures/lighting-v18',
    encoding: 'logrgb', radianceRange: 32, logGain: 256,
    slots: Array.from({ length: 12 }, (_, i) => i),
    exposure: 1, reflectionStrength: 1, reflectionYawDegrees: 0,
    glass: { enabled: true }, // optional; default leaves existing glass intact
  },
});
const lighting = await createDualLighting({
  THREE, renderer, objects: [room],
  profile: {
    revision: 18, directory: '/textures/lighting-v18',
    slots: [...Array.from({ length: 12 }, (_, i) => i), 'window'],
    extension: 'ktx2', loader: roomTextureLoader,
    encoding: 'logrgb', radianceRange: 32, logGain: 256,
    exteriorNightExposure: {}, interiorNightReadability: 0,
    nightRadianceScale: materialRelease.roomNightRadianceScale, // optional Room-only per-atlas normalization
    dayMixUniform: surface.getDayMixUniform(),
  },
});
const cleanOpening = await createIntroLighting({
  THREE, renderer, room, loader: introTextureLoader, // separately owned after the room decoder is released
  profile: { revision: 18, directory: '/textures/intro-clean-v18', encoding: 'logrgb', radianceRange: 32, logGain: 256 },
});
```

Gallery uses `family: 'gallery'`, slots 0–3, `materialPattern: /^GALLERY_LIGHTMAP_(\d+)/` for dual lighting, and its directory/revision. It has no room-intro receiver layer. Both regular and transition-clone materials share the same uniform and resources.

Call the existing `lighting.setDayMix(value)` from the shared clock; the surface reads the same uniform object, with no second animation clock. It decodes diffuse/clean maps before blending, adds view-dependent GGX prefiltered reflection using F0/roughness and perturbed normals, then applies AgX exactly once in the material. Global renderer tone mapping stays unchanged, preserving About.

Dispose in reverse order: clean opening, dual lighting, physical surface, then the model's owned resources. The helpers also guard against stale outer compile hooks after out-of-order disposal. A failed data/probe load rejects initialization, releases its partial resources and leaves previous materials intact; the caller must keep or restore the previous complete asset release instead of displaying LogRGB maps through an unlit sRGB path. A failed KTX request remains explicit; the presence of a `.logrgb.png` file does not itself imply automatic runtime fallback.

No ongoing reflection rendering, postprocessing pass, or extra draw call is introduced by this helper. It adds normal/specular lookups and up to two PMREM lookups per fragment. Two 1K BC7/ASTC4×4 data maps with mip chains cost approximately 2.67 MiB per atlas; sixteen atlas slots add about 42.7 MiB, excluding probes and larger hero maps. This is not a 120 FPS guarantee. The probe is a static local environment approximation, not ray-traced reflections.

Optional glass matches only the five `WEB8_GLASS_…` families (including their old `WEB8_CLEAR_` prefix), or Gallery's `GALLERY_ARCH_GLASS` / `GALLERY_CLEAR`. It uses the same probes and shared day mix, Fresnel F0=.04, authored roughness when available, and low absorption. Ordinary alpha blending approximates transmission; it does not render refraction, volumetric thickness, dispersion or another scene target. Grazing angles become more reflective. Replacements preserve geometry, independent node IDs, the original material arrays and original materials. `getReplacedMaterials()` exposes `{original, material}` pairs; disposal restores originals before releasing only the new materials. Dispose the helper before disposing model resources. When this option is active, skip the previous `createGalleryGlass` decorator to avoid overlapping reflection treatments. About glass and arbitrary transparent decoration are excluded.

CPU reports: [physical-surface-v1.json](validation/physical-surface-v1.json) retains RGBM compatibility/ownership coverage; [logrgb-runtime.json](validation/logrgb-runtime.json) adds ten checks for the current production LogRGB path. The latter evaluates the scalar form extracted from the actual composed GLSL decoder, verifies linear day/night and clean-intro composition before one AgX, window/About sRGB isolation, constant uniform ownership, bad-profile rejection, night-only HDR scale restoration before mixing, missing-map and upload-failure cleanup, and stale outer-hook disposal. It does not emulate GPU filtering or certify GLSL driver compilation.

Integration report: [material-preview-integration.json](validation/material-preview-integration.json), seven CPU checks executing the real Gallery factory, real 77-ID geometry and physical/dual-lighting lifecycle with explicit network/GPU substitutes. It covers atomic release selection, actual selected V5/V6 GLBs, V6 embedded night KTX bytes/hashes, day-map and PNG-fallback metadata/hashes, 77 independent IDs, shared fractional LogRGB day mix, native legacy behavior, missing normal-map cleanup, missing day-map cleanup, and decoder release before/after initialization. The KTX2 decoder releases once on ready or failure and is not released again by scene disposal. GPU image decode, PMREM and network are explicit substitutes; this CPU report does not certify browser rendering. The final independent rerun passed all seven integration checks, ten LogRGB checks and twenty startup checks; all 38 About baseline hashes matched. Actual GPU/browser evidence is recorded separately in the [main-page report](validation/room-v18-main-browser.json). The final Vite build passed with 62 modules in 8.21 seconds. These local checks do not establish a universal 120 FPS or stutter-free guarantee.
