# Scene life V8 / connected-room patrol V9

After the V7 opening has finished, the existing Blender room now has **13 independent activity loops across 16 addressable parts**. The opening terminal still lands permanently on the desk as described in `docs/ENTRY_DOCK_V7.md`; this change adds life to the normal room view and does not replace that opening.

| Existing asset | Ongoing action | Timing |
| --- | --- | --- |
| Work chair | Continuous parent-vertical swivel; its authored position and scale stay fixed | One full turn every 18 seconds |
| Tripod robot and its three legs | Leaves the desk edge, patrols the connected room floor, folds its hips to side-step narrow passages, and pauses to observe | 2.5-second departure, then a measured 38.49 m round trip of approximately 131.5 seconds; 0.42 m/s cruise, 0.35 m/s narrow-passage cap, advance slowdown for bends and stops |
| Three mechanical petals | Open and fold successively, with 0.45-second offsets | 10.8-second loops |
| Ring speaker | Damped-looking ring swing followed by a rest | 8.4 seconds |
| Scout drone | World-vertical hover with a small bank | 6.4 seconds; at most 0.052 m lift |
| Orbital-clock dial | Follows the automatic scene hour around its authored spindle | One turn per 12 simulated hours; 7.5-second indexing fallback if no scene hour is supplied |
| Projector lens | Extends, turns to focus, then retracts | 9.2 seconds; at most 0.01 m extension |
| Data selector | Two-stage dial motion | 8.8 seconds |
| Enclosed sculpture | Continuous rotation about the enclosure's vertical axis | 24 seconds |
| Floor-lamp head | Slow downward glance and return | 12.5 seconds |
| Communicator panel | Slight opening, hold and soft closure | 11.4 seconds |

The chair is a single baked mesh in the actual GLB, so the whole authored chair rotates; a separate seat pivot is not invented. V9 replaces the earlier 1 m front-aisle robot loop with a measured connected-floor route: front aisle → lounge front edge → right wall → rear window/work area, then back along those real passages. The desk's low supports are treated as obstacles rather than a shortcut. The existing three rigid hip assemblies fold inward by at most 0.16 radians for narrow passages; the body maintains a measured fixed heading while side-stepping and restores ordinary walking in open space. It is not inverse kinematics with world-locked feet. No head mesh, character, geometry, material, texture or light is added.

`src/robot-patrol.js` rounds the measured waypoint path, precomputes arc length, limits acceleration before turns, and inserts observation stops. The initial route point is exactly `[-3.23, 2.84]`, so the 2.5-second departure advances only 0.26 m from the original dock instead of crossing diagonally to a loop midpoint. Even that departure has a small real leg gait. The three-foot support footprint determines when to rise onto the existing rug; its 3.663 cm height difference is measured from actual geometry. No per-frame navmesh construction, raycasting, extra geometry or transform hierarchy changes are introduced.

## Ownership and interaction

`src/scene-motion.js` maintains a clock for each mechanism. Hovering a child leg pauses the complete robot and all three legs. Hover, click holds, and related GSAP position/rotation/quaternion/scale tweens retain ownership of their transforms. Resuming uses exponential following rather than snapping to a cached pose. Deltas are bounded at 0.05 seconds; disabled/reduced-motion updates perform no transform writes. Modals, camera drags/resets and transitions suspend ordinary motion through the existing main-loop gate.

`getInteractionPose(node, original, active)` records the current patrol position when hover begins, then returns that same anchor when the enlarged object shrinks. `src/main.js` passes that dynamic pose to hover clearance. `src/tracked-hitboxes.js` synchronizes the already existing pick boxes before raycasting, so the visible moving robot and its legs remain clickable at their current positions. It changes no model hierarchy and creates no extra pick geometry or draw calls. Room motion freezes during room/gallery camera transitions.

The automatic lighting cycle is documented in `docs/SCENE_TIME_V1.md`. Following the latest user adjustment, a full day lasts 60 real seconds, with 7.5-second dawn and dusk transitions starting from 10:00. The user's latest choice, **“隐藏底部时间，继续自动昼夜”**, hides the bottom timer and its separator while keeping the background clock, physical orbital-clock movement, and lighting cycle active. Every opening now starts in daylight at 10:00; legacy night QA links cannot force a night opening. The manual day/night buttons remain removed.

## Verification

The final expanded V9 patrol has **16 passing motion/geometry checks**:

- `scripts/check-scene-motion.mjs` — **13/13**, recorded in `docs/validation/scene-motion-v9.json`. Real Three.js/GSAP ownership, reduced-motion zero writes, pause/resume, delta bounds, independent IDs, scale/hierarchy preservation, continuous chair rotation, actual pivots, room-wide visitation and narrow-passage hover protection are checked.
- `scripts/check-scene-motion-clearance.mjs` — **3/3**, recorded in `docs/validation/scene-motion-clearance-v9.json`. The actual animation was sampled at **2,666 poses over 266.538 seconds**, including departure and two complete patrols, against **91 room obstacle meshes** and **63,984 independent chair-phase samples**. There were no sampled surface intersections. Foot/rug/platform checks measured a minimum floor gap of **0.0118768 m** and a minimum platform-edge margin of **0.0488746 m**. The short anticipatory rise at the rug edge reaches a maximum lowest-support gap of **0.0546395 m**; this is a stylized rigid-hip step, not IK foot planting. The robot reaches X **[-3.30, 4.50]** and Z **[-1.65, 2.99]**. A one-hour simulation remained bounded and added no meshes or geometry.

The previous V8 1 m aisle-motion reports (`scene-motion-v8.json` and `scene-motion-clearance-v8.json`) remain untouched as history. V9 source hashes in both current reports were checked against the final implementation files.
Additional integration checks:

- `scripts/check-tracked-hitboxes.mjs` — **3/3**, structured command output: transformed-parent tracking, ray hits at the new location rather than the old one, and unchanged hierarchy/geometry.
- `scripts/check-scene-clock.mjs` — **7/7**, recorded in `docs/validation/scene-clock-v1.json`; timing, pause/reduced-motion behavior, shared lighting mix, no per-frame resource creation, and room-only night readability.
- Production build passed with the existing large-chunk advisory only.
- Live browser checks confirmed movement from the front aisle into the right/rear area, leg clicks at the current position, whole-robot hover pause, and factor-1 hover protection in compact passages. Final observations and integrated source hashes are recorded by the parent task in `renders/scene-life-v8/web-verification.json`.

Collision checks are sampled surface tests, not a proof covering every possible user-scaled pose. Existing authored assembly contacts remain. CPU timing/tests do not establish hardware-presented 120 FPS; no new stable-120-FPS claim is made.

## Homepage and font review remain separate

The revised homepage concept is `renders/homepage-background-concept-v2/concept.png`, with `prompt.txt` and `metadata.json` in the same directory. It uses a game-portfolio launch-screen direction: large sculptural Chinese type, diagonal composition, titanium tracks, a navy industrial surface and warm orange accents around the existing terminal. It remains **pending user approval and is not a runtime background**.

The audience is game-job recruiters. The user's specific role, name, project history and experience remain unprovided rather than invented. Following the request to reconsider the typeface, `http://127.0.0.1:5173/font-review-v4/index.html` previews four real local fonts: 抖音美好体 Bold, 站酷快乐体, 荆南波波黑 Bold and 得意黑. Their source/license/subset records are in `public/font-review-v4/candidates.json` and `docs/FONT_REVIEW_V4.md`. The user subsequently selected A, 抖音美好体 Bold with extruded thickness. This font is now integrated in production as `Atelier Forge Display` with CSS weight 700 and `font-synthesis: none`. The upstream Bold face preserves its original OS/2 weight value 400; it is not synthetically emboldened. The 66,008-byte WOFF2 covers all 507 current Chinese source characters. Details are in `docs/FONT_PRODUCTION_A_V1.md`; the background concept still awaits approval.

Everything remains in this independent local project. No deployment, remote push or legacy-project modification is part of this revision.
