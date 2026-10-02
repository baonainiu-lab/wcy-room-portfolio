# Room V17 physical material release

V17 replaces the material response of all 117 material slots actually used by the room web scene. This includes exterior parts, leaves, stems, soil, moss, bark, paper edges, bookcloth, stitches, optical coatings, display details, glass, furniture and metal structure. The two existing image-content materials keep their original pixels. Geometry, object IDs, hierarchy, transforms, normals and BakeUVs are inherited from V16.

## Source and provenance

- Editable source: `assets/blender/orbital-atelier-v17.blend`.
- Fixed prepared source: `assets/blender/orbital-dual-bake-v17.blend`, SHA-256 `ec777d4d2beaa6655b3d3899f8a0317f54931f2230cebd78e2ebec560f34341c`.
- Source replacement and per-pass MCP entry points: `assets/blender/scripts/photoreal_materials_v17.py`.
- Actual material inventory, explicit mapping, scanned-image hashes and unchanged-geometry checks are in `assets/blender/photoreal-materials-v17-{inventory,plan,prepared,source}.json`.
- Existing verified CC0 hessian, brown leather and walnut veneer maps come from `assets/textures/about-atelier-v3/texture-manifest.json`. Their assigned world-space footprints are artistic metre calibrations; the vendor manifests do not supply physical scale metadata.
- All other finishes use project-authored deterministic shader patterns. They are not described as scanned surfaces. There are no new downloaded texture licences.

Materials combine visible centimetre-scale variation with smaller surface structure. Actual metals use metallic 1; paint, ceramic, paper and polymer use metallic 0. Ceramic chair surfaces retain continuous source normals, with roughness and coating variation instead of a displacement seam. Upholstery, rugs and book covers use separate calibrated repeats of the verified fabric maps.

## Web texture contract

The lighting maps contain scene-linear diffuse, indirect light and emission. Glossy response is excluded from baking so the web shader can respond to the camera with the separately baked physical surface data.

| Assets | Data |
| --- | --- |
| `lighting-v17/day-{0..11}.ktx2` and `night-{0..11}.ktx2` | LogRGB32 gain 256, constant alpha 1; no colour-space conversion |
| `lighting-v17/specular-{0..11}.ktx2` | Scene-linear F0 in RGB; perceptual roughness in alpha |
| `lighting-v17/normal-{0..11}.ktx2` | Tangent-space OpenGL normal, BakeUV exported as UV0 |
| `intro-clean-v17/day-{0,1,8}.ktx2` | Matching LogRGB32 receiver-only intro lighting |
| `lighting-v17/reflection-day.hdr`, `reflection-night.hdr` | Matching linear HDR panoramic reflections |
| Window and screen assets | Original sRGB pixels, preserved from V16 |

Raw `day-N.png` / `night-N.png` files retain RGBM32 as the archived bake representation. The web PNG fallback and GLB use the separate `day-N.logrgb.png` / `night-N.logrgb.png` files. Their shader decode is `(exp2(rgb * log2(8193)) - 1) / 256`. This avoids the measured UASTC failure that rounded small RGBM alpha multipliers to zero. Conversion records bind the original RGBM hash, encoded PNG hash and final KTX2 hash.

Night atlases with values above 32 also retain exact source float values and indices in a separate NPZ. The encoder restores those values, divides by a recorded power-of-two `radianceScale`, and then LogRGB encodes. The runtime multiplies the decoded night radiance by the same scale **before** mixing day and night. This is reversible storage scaling, not a change to artistic exposure. The release reports supply the exact per-slot map.

The F0 bake evaluates the source Principled IOR, specular level, specular tint, metallic value and base colour. It is not reconstructed from a lit diffuse image. Hero and small-prop data maps are 2K; exterior slots 5 and 6 use 1K. Light atlases retain the established 2K–4K dimensions and UV layout.

The shared helper is `assets/blender/scripts/pbr_bake_channels.py`. Each file-targeted Blender MCP invocation can execute one normal, F0, roughness or lighting pass. Lossless numeric intermediate buffers stay under `assets/blender/linear-intermediates`, outside the deployable public directory. The original interactive Blender session is never opened or changed.

## Encoding and verification

`scripts/compress-linear-surface.py` builds mipmaps before KTX2 encoding: raw RGBM is decoded to linear radiance, filtered and LogRGB encoded at every level; normals are filtered as vectors and renormalized; roughness filtering uses squared roughness. Encoded alpha is never premultiplied. Linear-data textures use an explicit linear transfer function. UASTC quality 2 plus Zstd preserves complete mip chains. Release codec revision is `linear-surface-v2-logrgb256`; older RGBM KTX2 files are not accepted.

Blender's small normal-component roundoff is recorded separately from true invalid values. Filtered nonzero normal vectors are normalized before PNG quantization. Unoccupied texels use the neutral +Z normal and roughness 1. Reports retain raw ranges, vector-length percentiles and the count of very short filtered boundary vectors.

`scripts/verify-room-v17.py` is the release gate. It checks current source and texture hashes, the complete atlas set, all 54 runtime texture records, zero daytime RGBM clipping, recovery of every recorded night value above 32, matching probe orientation, exact V16 geometry/UV buffers and hierarchy, and unchanged V16 resources. The source overflow, scaling metadata and exported per-slot scaling map must all match. Its successful output is `assets/blender/photoreal-materials-v17-validation.json`; the presence of an intermediate texture alone is not a release approval.

The initial highlight audit located small bright light faces on `room_static` and `compute_core`, and brighter lamp diffusers on slot 4. Most affected texels of the first two atlases were copies within the original 16-pixel bake margin. The first night-0 result, which predated float-overflow recording, is preserved in `assets/blender/room-v17-highlight-audit-history`; night 0 is rebaked from the unchanged prepared source to complete the recoverable data chain. Final delivery does not rely on the initially considered clipping exception.

The runtime surface approximation has one base GGX lobe. Source coat, sheen, anisotropy and transmission settings remain editable, but are not separate baked data channels. Thin glass uses the runtime reflection treatment described in `PHYSICAL_SURFACE_CONTRACT.md`.
