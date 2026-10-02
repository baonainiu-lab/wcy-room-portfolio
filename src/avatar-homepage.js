// Playback of model-drawn RGBA frames. No pose interpolation or cutout animation.
const motions = [
  { id: 'greeting', frameMs: 180 },
  { id: 'tap', frameMs: 170 },
  { id: 'present', frameMs: 180 },
];
const ease = x => { const t = Math.max(0, Math.min(1, x)); return t * t * (3 - 2 * t); };
const ASSET_ROOT = '/media/avatar-home-v1/';
const ASSET_TIMEOUT_MS = 20000;
const NEUTRAL_HOLD_MS = 2800;

export function createAvatarHomepage({ element, reducedMotion = false }) {
  const stage = element.querySelector('.avatar-home');
  const figure = element.querySelector('.avatar-figure');
  const backdrop = element.querySelector('.avatar-backdrop');
  const sprite = element.querySelector('.avatar-sprite');
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  let available = false, started = false, finished = false, action = 0, frame = 0;
  let elapsed = 0, previous = 0, lastPaint = '', layout;
  let staticMotion = reducedMotion || media.matches;
  const images = [];
  const pendingLoads = new Set();
  const readyMotions = new Set(), motionUrls = new Map();
  const failureUrls = new Set(), assetFailures = [];
  let preparation, retrySequence = 0;
  figure.style.opacity = backdrop.style.opacity = '';
  function paint() {
    if (!available || finished || !readyMotions.has(motions[action].id)) return;
    const key = `${action}:${frame}`;
    if (key === lastPaint) return;
    lastPaint = key;
    sprite.style.backgroundImage = `url('${motionUrls.get(motions[action].id)}')`;
    sprite.style.backgroundPosition = `${(frame % 7) / 6 * 100}% ${Math.floor(frame / 7) * 100}%`;
    stage.dataset.action = motions[action].id;
    stage.dataset.frame = String(frame);
  }
  function measure() {
    if (!available || finished) return;
    const box = sprite.getBoundingClientRect();
    // Measured on the standardized 480x640 source: the blue hinged terminal.
    // The hand stays on the same side in every generated frame.
    const shift = motions[action].id === 'present' ? 5 : 0;
    layout = { x: (box.left + (173 + shift) / 480 * box.width) / innerWidth,
      y: (box.top + 244 / 640 * box.height) / innerHeight,
      width: 68 / 480 * box.width / innerWidth };
  }
  function preference(event) {
    staticMotion = reducedMotion || event.matches;
    if (staticMotion && !started) { action = 0; frame = 0; elapsed = 0; paint(); }
  }
  function loadAsset(file, attempt) {
    if (finished) return Promise.resolve({ cancelled: true });
    const url = `${ASSET_ROOT}${file}`;
    // Reuse the successful retry URL in CSS too, rather than requesting a URL
    // whose earlier failure may still be cached in an already-open tab.
    const requestUrl = attempt === 1 ? url : `${url}?avatarRetry=${Date.now()}-${++retrySequence}`;
    return new Promise(resolve => {
      const image = new Image(); images.push(image);
      let settled = false;
      const done = (reason = null, cancelled = false) => {
        if (settled) return;
        settled = true; clearTimeout(timeout); image.onload = image.onerror = null;
        pendingLoads.delete(cancel);
        if (reason && !finished) {
          failureUrls.add(url);
          assetFailures.push({ url, requestUrl, reason, attempt });
        }
        if (reason || cancelled) image.src = '';
        resolve({ url: requestUrl, ready: !reason && !cancelled, cancelled });
      };
      const cancel = () => done(null, true);
      const timeout = setTimeout(() => done('timeout'), ASSET_TIMEOUT_MS);
      pendingLoads.add(cancel);
      image.onload = () => { image.decode().then(() => done(), () => done('decode')); };
      image.onerror = () => done('unavailable');
      image.src = requestUrl;
    });
  }
  async function loadWithRetry(file) {
    for (let attempt = 1; attempt <= 2; attempt++) {
      const result = await loadAsset(file, attempt);
      if (finished || result.cancelled) return null;
      if (result.ready) return result.url;
    }
    return null;
  }
  async function prepareAssets() {
    // Only the background and neutral greeting are needed for the first view.
    const [backgroundUrl, greetingUrl] = await Promise.all([
      loadWithRetry('studio.webp'), loadWithRetry('greeting.webp'),
    ]);
    if (finished) return false;
    if (!backgroundUrl || !greetingUrl) {
      stage.hidden = true; element.dataset.avatar = 'fallback';
      console.warn('Character homepage unavailable after retry; using the original 3D terminal opening.', [...failureUrls]);
      return false;
    }
    motionUrls.set('greeting', greetingUrl); readyMotions.add('greeting');
    backdrop.style.backgroundImage = `url('${backgroundUrl}')`;
    available = true; stage.hidden = false; element.dataset.avatar = 'ready'; paint(); measure();
    for (const motion of motions.slice(1)) {
      void loadWithRetry(`${motion.id}.webp`).then(url => {
        if (!url || finished) return;
        motionUrls.set(motion.id, url); readyMotions.add(motion.id);
      });
    }
    return true;
  }
  function nextReadyAction() {
    for (let step = 1; step <= motions.length; step++) {
      const candidate = (action + step) % motions.length;
      if (readyMotions.has(motions[candidate].id)) return candidate;
    }
    return 0;
  }
  media.addEventListener('change', preference);
  return {
    prepare() {
      if (finished) return Promise.resolve(false);
      return preparation ||= prepareAssets();
    },
    get available() { return available && !finished; },
    begin() { if (!available || finished) return; started = true; measure(); },
    anchor() { return available && !finished ? layout : null; },
    resize: measure,
    update(timestamp, release = 0, phase = 'welcome') {
      if (!available || finished) return;
      if (!started && phase === 'welcome' && !staticMotion) {
        const delta = previous && !document.hidden ? Math.min(timestamp - previous, 100) : 0;
        elapsed += delta;
        const duration = motions[action].frameMs * 14;
        // Neutral holds make each small gesture a readable independent action.
        if (elapsed >= duration + NEUTRAL_HOLD_MS) { elapsed = 0; action = nextReadyAction(); }
        frame = elapsed < motions[action].frameMs * 14 ? Math.min(13, Math.floor(elapsed / motions[action].frameMs)) : 13;
        paint();
      }
      previous = timestamp;
      if (started) {
        // Only the page layers dissolve. The live GLB continues from the hand.
        figure.style.opacity = String(1 - ease(release / .56));
        backdrop.style.opacity = String(1 - ease(release));
        stage.style.pointerEvents = 'none';
      }
    },
    finish() {
      if (finished) return;
      finished = true; stage.hidden = true; sprite.style.backgroundImage = 'none';
      pendingLoads.forEach(cancel => cancel());
      images.forEach(image => { image.src = ''; });
      media.removeEventListener('change', preference);
    },
    getState: () => ({ available, started, finished, action: motions[action].id, frame,
      staticMotion, layout, mode: 'model-generated-rgba-frames', frameCount: 14,
      timing: { currentFrameMs: motions[action].frameMs, neutralHoldMs: NEUTRAL_HOLD_MS,
        actions: motions.map(motion => ({ id: motion.id, frameMs: motion.frameMs,
          animationMs: motion.frameMs * 14, cycleMs: motion.frameMs * 14 + NEUTRAL_HOLD_MS })) },
      loadedActions: motions.filter(motion => readyMotions.has(motion.id)).map(motion => motion.id),
      pendingAssets: pendingLoads.size, failureUrls: [...failureUrls], assetFailures: assetFailures.map(failure => ({ ...failure })) }),
  };
}
