import { SCENE_LIGHT_GAMMA } from './scene-clock.js';

// CSS colours live in display space; recover the brightness ramp that produced
// the shared linear-light weight. The overlay must never toggle at mix = 0.5.
export function createSceneTimeTheme({ body, themeMeta = null }) {
  let dayMix = 1, brightnessMix = 1, lastMeta = '';
  const night = [16, 23, 28], day = [227, 232, 229];
  body.classList.add('scene-time-colors');
  return {
    apply(value) {
      if (!Number.isFinite(value)) return;
      dayMix = Math.max(0, Math.min(1, value));
      brightnessMix = dayMix ** (1 / SCENE_LIGHT_GAMMA);
      body.style.setProperty('--scene-day-percent', `${brightnessMix * 100}%`);
      const color = `#${night.map((v, i) => Math.round(v + (day[i] - v) * brightnessMix).toString(16).padStart(2, '0')).join('')}`;
      if (themeMeta && color !== lastMeta) { themeMeta.content = color; lastMeta = color; }
    },
    getState: () => ({ revision: 1, dayMix, backgroundMix: brightnessMix, discreteThemeSwitch: false }),
  };
}
