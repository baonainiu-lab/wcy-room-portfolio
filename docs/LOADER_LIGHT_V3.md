# Loading light V3 — 2026-10-02

Local implementation of the requested broader, varied and more animated loading effects.

## Visual change

- Two filled SVG light ribbons have tapered silhouettes and separate opposing rotations (9.2 / 13 seconds).
- Cold and champagne trails have unequal weights (15 / 4 px), beside a 9 px true-progress arc.
- A filled illuminated lens, three drifting colour fields, eight varied bright motes and a 3.8 second logo sweep add surface and volume beyond outlines.
- Decorative layers contract and fade on completion, preserving the existing logo lift into the terminal welcome screen.
- Original SVG/CSS work; no AI bitmap, new 3D model, or third-party visual asset was introduced in this revision.

## Lifecycle

Existing weighted room / gallery / about / GPU warmup readiness remains authoritative. No artificial delay was added. Loading and welcome remain silent. Reduced-motion, error and finished states stop decorative animation. A visibilitychange listener pauses it when document.hidden is true.

## Verification

- Production build passed (existing large-bundle advisory remains).
- Existing loader lifecycle checks: 9/9. Existing startup readiness checks: 20/20.
- Chrome desktop 1512×797, mobile-sized 390×844 and short landscape 844×390 checked: no horizontal overflow, errors and retry visible.
- Reduced-motion and error modes: all decorative element/pseudo-element computed animation names were none.
- Actual main page reached 100%, all four readiness stages ready, welcome shown, loading reveal complete. Audio context not created, ambient sources 0, console errors empty.
- Browser debugging environment continued reporting document.hidden=false even after native tab switching. Hidden-state pause was code-reviewed but is not claimed as an observed runtime pass.
- Impeccable detector reported existing global typography/contrast issues outside the loader, plus decorative border/shadow advisories. Loader functional type uses at least 11 px; light depth is intentional for this brief.
- No real-device mobile or 120 FPS guarantee is implied.

Evidence: `output/loader-v3-main-loading.png`, `output/loader-v3-desktop.png`, `output/loader-v3-mobile.png`.

The isolated `output/qa-startup-light-show.html` fixture allows inspecting visual states at representative percentages; it does not alter production loading progress.
