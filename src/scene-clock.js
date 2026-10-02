// One clock drives every baked and live surface. No timers or tweens are
// created while it runs; pausing also freezes the phase rather than catching up.
export const SCENE_DAY_SECONDS = 60;
export const SCENE_SUNRISE_HOURS = Object.freeze([4, 10]);
export const SCENE_SUNSET_HOURS = Object.freeze([16, 22]);
export const SCENE_LIGHT_GAMMA = 2.2;
const clamp01 = value => Math.min(1, Math.max(0, value));
const smoother = value => { const x = clamp01(value); return x * x * x * (x * (x * 6 - 15) + 10); };
const wrapHour = value => ((value % 24) + 24) % 24;

export function daylightAtHour(hour) {
  const h = wrapHour(hour);
  if (h < SCENE_SUNRISE_HOURS[0] || h >= SCENE_SUNSET_HOURS[1]) return 0;
  let brightness = 1;
  if (h < SCENE_SUNRISE_HOURS[1]) brightness = smoother((h - SCENE_SUNRISE_HOURS[0]) / 6);
  else if (h > SCENE_SUNSET_HOURS[0]) brightness = 1 - smoother((h - SCENE_SUNSET_HOURS[0]) / 6);
  // Baked textures and sky are blended in linear light. Easing that weight
  // directly makes the darkest part brighten too abruptly on an sRGB display.
  // Shape perceived brightness first; every consumer still gets one weight.
  return brightness ** SCENE_LIGHT_GAMMA;
}

export function createSceneClock({ reducedMotion = false, startHour = 10,
  cycleSeconds = SCENE_DAY_SECONDS, element = null, onDayMix = () => {} } = {}) {
  const duration = Number.isFinite(cycleSeconds) && cycleSeconds > 0 ? cycleSeconds : SCENE_DAY_SECONDS;
  const initialHour = reducedMotion ? 10 : Number.isFinite(startHour) ? wrapHour(startHour) : 10;
  const periodLabel = duration % 60 === 0 ? `${duration / 60} 分钟一昼夜` : `${duration} 秒一昼夜`;
  const time = element?.querySelector('[data-scene-time]');
  const phase = element?.querySelector('[data-scene-phase]');
  const period = element?.querySelector('[data-scene-period]');
  let elapsed = 0, hour = initialHour, dayMix = daylightAtHour(hour), lastMinute = -1;
  let enabled = false, disposed = false;
  if (period) period.textContent = reducedMotion ? '静态日光' : periodLabel;
  element?.setAttribute('title', reducedMotion ? '减少动态效果 · 场景时间固定为 10:00' : `场景内时间 · ${periodLabel}`);
  function display() {
    const minute = Math.floor(hour * 60) % 1440;
    if (minute === lastMinute) return;
    lastMinute = minute;
    const value = `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
    const phaseName = hour >= 4 && hour < 10 ? '晨光' : hour >= 10 && hour < 16 ? '日光' : hour >= 16 && hour < 22 ? '暮光' : '夜色';
    if (time) { time.textContent = value; time.setAttribute('datetime', value); }
    if (phase) phase.textContent = phaseName;
    // This is a timer, not a live region: screen readers must not announce
    // twenty-four scene minutes per real second.
    element?.setAttribute('aria-label', `场景时间 ${value}，${phaseName}，${reducedMotion ? '减少动态效果，时间固定' : `自动运行，${periodLabel}`}`);
  }
  display(); onDayMix(dayMix);
  return {
    get hour() { return hour; },
    get dayMix() { return dayMix; },
    update(delta, options = {}) {
      if (disposed) return;
      enabled = options.enabled !== false && !reducedMotion;
      if (!enabled || !Number.isFinite(delta) || delta <= 0) return;
      // A delayed browser frame must not skip directly across dawn or dusk.
      elapsed += Math.min(delta, .25);
      hour = wrapHour(initialHour + elapsed * 24 / duration);
      const nextMix = daylightAtHour(hour);
      if (nextMix !== dayMix) { dayMix = nextMix; onDayMix(dayMix); }
      display();
    },
    getState: () => ({ revision: 2, hour, dayMix, brightnessMix: dayMix ** (1 / SCENE_LIGHT_GAMMA), elapsed, cycleSeconds: duration,
      paused: !enabled || disposed, reducedMotion, startHour: initialHour,
      sunriseHours: SCENE_SUNRISE_HOURS, sunsetHours: SCENE_SUNSET_HOURS, transitionSeconds: duration / 4,
      blendCurve: 'perceptual-quintic', lightGamma: SCENE_LIGHT_GAMMA,
      manualControls: false }),
    dispose() { disposed = true; enabled = false; },
  };
}
