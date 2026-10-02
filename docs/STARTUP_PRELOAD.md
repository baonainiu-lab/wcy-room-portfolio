# Startup preload

Status (2026-09-30): locally integrated and verified in the actual main-page WebGL renderer. Ordinary visits now select Room V18 revision 5b, Gallery V6 and Terminal V3 with `PHYSICAL_MATERIALS_DEFAULT=true`; `?physicalPreview=0` retains the previous complete release. All 20 CPU checks pass. The final Vite build passed with 62 modules in 8.21 seconds. This is a local release, not a deployment. See the [main-page browser report](validation/room-v18-main-browser.json).

Before exposing the welcome terminal, startup prepares the room and terminal, the works gallery, and the approved About scene. This includes each scene's model, material maps, day/night resources and background, plus fonts and the clean room-opening maps. Gallery and About use their existing factories and retained scene instances, so entering them does not intentionally defer their first resource load until the click. About's accepted material assets are preserved.

The progress meter reflects completed preparation stages:

| Stage | Weight |
| --- | ---: |
| Room and terminal | 60% |
| Works gallery | 18% |
| About | 17% |
| Final preparation | 5% |

These are stage weights, not downloaded-byte percentages or a timer. Each stage moves forward monotonically. The displayed value stays below 100% until every stage completes and `finish()` succeeds; an error cannot be overwritten by a late success event.

Behind the opaque loading screen, `warmSceneForStartup()` initializes discovered native material maps and shader-uniform textures, temporarily disables mesh frustum culling, compiles the native scene shaders and performs actual day/night draws. It restores the day mix, culling flags, render target, viewport, scissor and clear behavior, including resize or failure during compilation. Gallery and About also prepare their shared travel scenes, destination shaders and compositing shaders, then draw the transition render targets. Clean-opening shaders are compiled and maps uploaded; the terminal welcome composition is drawn before the final GPU fence. This covers actual uploads and target allocation beyond shader compilation alone.

`waitForStartupGpu()` flushes a WebGL completion fence and checks it across animation frames. Only a signalled fence releases the gate. A failed wait, lost context, missing fence handle or 30-second timeout rejects startup; contexts without fence support use `gl.finish()`. The welcome controller becomes ready after successful preparation. This reduces first-use work but is not a guarantee of sustained frame rate or stutter-free rendering on every device.

On failure, the loader names the failed stage, disables entering/skipping, keeps camera controls locked and disposes partial scene/material resources. The retry button reloads the page for a fresh attempt. Under `?qa`, retry also removes the controlled `failRoom` / `failStartup` failure parameters. `?qa` diagnostics expose the weighted stages, ready/error state, prepared transitions, program count and observed asset requests.

Run `node scripts/check-startup-readiness.mjs` for the 20 CPU checks: incomplete-stage combinations, monotonic progress, failure persistence, native/uniform texture discovery, restoration after upload/compile/draw errors and resize, and fence success/failure/context-loss/timeout/cleanup/fallback. These execute production control flow with real Three.js objects and explicit fake renderer/GL/frame-clock inputs. They do not certify actual GPU uploads, shader-driver compilation, browser layout, or visual smoothness; the separate main-page browser report records the observed rendering behavior.

The normal `?qa` route reached all four stages ready and 100% before exposing the terminal welcome, with both Gallery and About transitions already prepared. First entry measurements were:

| First entry | Observed asset requests | Shader programs | Transition p50 / p95 / max | Samples |
| --- | --- | --- | --- | ---: |
| Gallery | 82 → 82 | 113 → 113 | 8.4 / 17.6 / 43.4 ms | 200 |
| About | 82 → 82 | 113 → 113 | 8.4 / 16.8 / 25.0 ms | 190 |

These measured entries added no observed asset requests or shader programs. About retained its leftward −34 scene offset and all 38 baseline file hashes. In the legacy fallback, a controlled `failStartup=about` failure held the opaque loader at 78%; retry recovered successfully. Repeated wheel input started the physical opening only once. At 390×844, keyboard Enter completed the opening; resizing to 1280×720 also worked. The tested physical run recorded no console warnings or errors.

Under `?qa&motion=reduce`, all four stages were ready before welcome. Skipping reached the complete phase with one start and one completion, restored camera controls and kept the clock paused at daylight 10:00; no errors were recorded.

These observations cover the reported local viewport and interaction cases; physical touch hardware was not exercised. They are implementation QA, not a new user visual approval. Preloading increases initial waiting time and resident resource use. The measured frame times include occasional longer frames; they are not a 120 FPS claim or a guarantee that every device, later resize or interaction will be free of stutter. The successful build retained the existing large-bundle advisory.
