# Automatic scene time — continuous transition revision 2

The manual day/night buttons are removed. Scene time continues automatically with the bottom readout hidden, as requested. Scene time starts at **10:00**, runs through a full day every **60 seconds**, and also drives the existing Blender orbital-clock hand. This is scene time, not the visitor's local system clock.

- Sunrise is now 04:00–10:00 and sunset 16:00–22:00; each transition takes **15 real seconds**. Full daylight and full night each last 15 seconds. The full cycle remains 60 seconds. This replaces the previous 7.5-second dawn/dusk ramps, without lengthening the cycle.
- A quintic brightness curve has zero speed and acceleration at both ends. Its value is raised to 2.2 once, in the clock, to create the shared linear-light weight. This slows the conspicuous dark-end brightness change caused by directly easing linear light. Exact day and night endpoints are unchanged.
- The clock starts only after the opening completes. Intro, modal reading, scene transition, gallery loading and a hidden document freeze elapsed time. Resuming does not catch up or jump across a lighting phase.
- Reduced-motion mode stays at 10:00 and labels the readout `静态日光`.
- The readout is `role="timer"` with `aria-live="off"`, so it does not continuously interrupt screen readers.

`src/scene-clock.js` owns elapsed time. A single `dayMix` writes through `setDayMix` to the room's actual day/night Cycles bakes, its window panorama, live computer screen brightness, resident terminal PBR appearance, sky/fog, warm exterior halos, and the gallery's bakes, glass and sky/floor atmosphere. No per-frame tweens, materials, textures or lights are created. Existing `setTheme` helpers remain for initialization/internal use; users have no manual day/night control.

## Abrupt overlay change corrected

The render modules already consumed the same fractional weight synchronously. The proven discontinuity was in `main.js`: at `dayMix = 0.5`, it swapped `day-theme` / `night-theme` classes. That instantly replaced the full viewport's top and bottom CSS wash gradients, alongside control colors. This could look like a lighting jump even while the 3D textures were blending continuously.

`src/scene-time-theme.js` and `src/scene-time-theme.scss` now derive a display-space brightness percentage from the shared weight and blend the existing UI palette and wash gradients continuously. Browser theme metadata follows the same brightness. `state.isDay` remains an internal diagnostic/loading snapshot; it no longer changes visible theme classes during a cycle. The room and gallery retain their respective wash endpoints. Layout, fonts, logo, hidden controls and the intro's `body.intro-active::before { display: none; }` rule are untouched.

For live inspection, `__roomPreview.getState().sceneClock` reports revision 2, `transitionSeconds: 15`, `dayMix`, `brightnessMix` and the phase ranges. `sceneTimeTheme.backgroundMix` reports the actual CSS-wash brightness weight. These are diagnostics, not new user controls.

## Night room legibility

The room lighting profile enables `interiorNightReadability: 1`. The final night sampler uses a shared scalar exposure gain: `color.rgb *= 1 + 2.4 * pow(1 - clamp(peak / 0.45, 0, 1), 2)`, where `peak` is the maximum RGB channel. There is no constant color offset: true black remains black, baked hue ratios and spatial light pools are preserved, and even saturated warm emitters with a peak channel at or above 0.45 stay unchanged. This replaces the earlier constant warm RGB lift, which made dark materials look gray or self-lit. Outdoor atlases 5/6 and the window panorama are excluded, and the day endpoint is unchanged. No new point light, draw call, geometry or rebake is introduced. Additional actual-asset UV diagnostics are recorded in `docs/validation/night-grade-diagnostic-v1.json`.

## Verification

- `scripts/check-scene-clock.mjs`: **9/9**; report `docs/validation/scene-clock-v1.json`.
- Full 60-second cycle sampled at 120 Hz: maximum dayMix step 0.00137653; both dawn/dusk are 15 seconds. Complete-cycle timing and step bounds also checked at 24, 30 and 60 Hz. These numerical sample rates are not measured browser frame rates.
- Representative linear-light channel pairs passed through the sRGB output response show 32–46% smaller maximum brightness steps than the old 7.5-second curve. This is a numerical response comparison, not a GPU visual benchmark.
- Actual theme helper and compiled SCSS checked: continuous wash progression, exact metadata endpoints, no midpoint class toggle, and no override of the intro overlay's display rule.
- Pause/resume, large-frame clamp, invalid deltas, disposal and reduced-motion static hour checked.
- Actual application initialization and intro gate checked for the normal URL plus three old QA URL combinations: all start at 10:00/dayMix 1, remain there before intro completion, and advance through the same automatic cycle afterward.
- Actual GLTF material hooks: 117 intermediate/end-point checks across 13 lighting materials; screen, environment and retained terminal share the same fractional value.
- 1001 consecutive writes: no additional tween, texture upload or material-version increment.
- Room-only shadow grade preserves 3 excluded exterior/window materials; neutral linear 0.02 becomes 0.0638281 while true black, baked hue ratios and bright values remain unchanged.
- Production build and live room/gallery inspection are completed separately by the parent task. CPU tests do not claim GPU compilation, visual approval or 120 FPS performance.

Every opening now explicitly initializes scene time to **10:00 daylight**, including previously shared `?qa&sceneHour=22&timeHold` or `?qa&sceneHour=18.5` links. The old `sceneHour` and `timeHold` URL overrides have been removed; they cannot force a night opening or freeze the ordinary cycle. The clock stays at 10:00 throughout loading, welcome and entry, then starts the 60-second automatic cycle only after entry completes. Reduced-motion mode remains fixed at 10:00. The CPU check executes the actual initialization and render-gate statements against these old URLs; live browser checks remain a separate verification.

## Latest UI choice — timer hidden, automatic cycle retained

The user subsequently chose **“隐藏底部时间，继续自动昼夜”**. This supersedes the earlier visible clock-readout design. The existing timer element now has `hidden` and `aria-hidden="true"`; CSS also removes its adjacent separator. The old manual day/night controls remain absent. Hiding the readout does not disable the scene clock: the 60-second cycle, updated 15-second dawn/dusk blends, 10:00 starting phase, and physical orbital-clock hand all continue normally. Reduced-motion mode still holds static daylight at 10:00, without a visible time label.

The final room-only night adjustment uses the black-preserving exposure curve described above; the earlier fixed warm offset has been removed. It grades the existing bake without new lamp geometry or a rebake. Prior hidden-timer UI and live lighting observations are tracked in `renders/scene-life-v8/web-verification.json`; the clock's current 9/9 CPU checks are in `docs/validation/scene-clock-v1.json`.

## 2026-09-28 browser verification

The final local page completed a full automatic cycle, observed at night, mid-dawn (hour 7.003, perceived brightness 0.501, shared linear weight 0.218), and back at day after 67.5 seconds. No captured application errors. The intro background remained intact; the new logo was legible at both endpoints. Browser diagnostics: `docs/validation/scene-time-v2-browser.json`. Production build passed. This observation does not establish a frame-rate guarantee.
