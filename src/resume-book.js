import './resume-book.scss';
import './resume-book-cover.scss';
import { resumePages as pages } from './resume-book-content.js';

let nextBookId = 0;
const STRIP_COUNT = 18;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const easing = t => t * t * (3 - 2 * t);

/**
 * A native, focus-contained dialog. Coordinates passed to open are viewport pixels.
 * open/close resolve after their motion; onClose runs once, after the book is closed.
 * No scene objects or renderer are created by this presentation.
 */
export function createResumeBook({ reducedMotion = false, onClose = () => {} } = {}) {
  const id = `resume-book-${++nextBookId}`;
  const mediaQuery = window.matchMedia('(max-width: 760px), (max-height: 520px)');
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.createElement('dialog');
  root.className = 'resume-book';
  root.setAttribute('aria-labelledby', `${id}-title`);
  root.setAttribute('aria-describedby', `${id}-help`);
  root.innerHTML = `<div class="resume-book__shell">
    <header class="resume-book__bar"><div><span>CREATOR’S NOTEBOOK</span><h2 id="${id}-title">王丞业的简历书</h2></div><nav class="resume-book__downloads" aria-label="下载完整简历"><a href="/media/resume-book/resume-game-design.pdf" download="王丞业_游戏策划_简历.pdf">策划简历 ↓</a><a href="/media/resume-book/resume-game-operations.pdf" download="王丞业_AI游戏运营_简历.pdf">运营简历 ↓</a></nav><button type="button" class="resume-book__close" data-book-close aria-label="合上简历书，返回书桌" autofocus><span>合上书</span><b aria-hidden="true">×</b></button></header>
    <div class="resume-book__stage"><div class="resume-book__cover" aria-hidden="true"></div><div class="resume-book__leaves"><div class="resume-book__slot resume-book__slot--left"></div><div class="resume-book__slot resume-book__slot--right"></div></div><div class="resume-book__gutter" aria-hidden="true"></div><div class="resume-book__turn-layer" aria-hidden="true" inert></div><div class="resume-book__cast-shadow" aria-hidden="true"></div><button type="button" class="resume-book__corner resume-book__corner--previous" data-book-step="-1" aria-label="翻到前一页"><span aria-hidden="true">↶</span></button><button type="button" class="resume-book__corner resume-book__corner--next" data-book-step="1" aria-label="翻到后一页"><span aria-hidden="true">↷</span></button></div>
    <footer class="resume-book__controls"><button type="button" class="resume-book__step" data-book-step="-1" aria-label="上一页"><span aria-hidden="true">←</span> 前一页</button><nav class="resume-book__index" aria-label="简历章节">${pages.map((page, index) => `<button type="button" data-book-page="${index}" aria-label="第 ${index + 1} 页，${page.title}"><span>${String(index + 1).padStart(2, '0')}</span></button>`).join('')}</nav><button type="button" class="resume-book__step" data-book-step="1" aria-label="下一页">后一页 <span aria-hidden="true">→</span></button></footer>
    <p class="resume-book__help" id="${id}-help"><span class="resume-book__help--desktop">点击页角或使用 ← → 翻页</span><span class="resume-book__help--mobile">轻扫书页或点页角翻页</span><i>·</i> Esc 合上书</p>
    <p class="resume-book__status" role="status" aria-live="polite" aria-atomic="true"></p>
  </div>`;
  document.body.append(root);
  const shell = root.querySelector('.resume-book__shell');
  const stage = root.querySelector('.resume-book__stage');
  const leftSlot = root.querySelector('.resume-book__slot--left');
  const rightSlot = root.querySelector('.resume-book__slot--right');
  const layer = root.querySelector('.resume-book__turn-layer');
  const shadow = root.querySelector('.resume-book__cast-shadow');
  const status = root.querySelector('.resume-book__status');
  const jacket = document.createElement('div');
  jacket.className = 'resume-book__jacket-layer';
  jacket.setAttribute('aria-hidden', 'true');
  jacket.inert = true;
  jacket.hidden = true;
  jacket.innerHTML = `<div class="resume-book__jacket-bed"></div><div class="resume-book__jacket-hinge"><div class="resume-book__jacket-front"><div class="resume-book__jacket-imprint"><span>CREATOR’S NOTEBOOK</span><i aria-hidden="true">W</i><strong>创作履历</strong><p>王丞业</p><small>GAME DESIGN · VISUAL CONTENT</small></div></div><div class="resume-book__jacket-inside"></div><div class="resume-book__jacket-edge"></div></div>`;
  stage.append(jacket);
  const hinge = jacket.querySelector('.resume-book__jacket-hinge');
  const jacketInside = jacket.querySelector('.resume-book__jacket-inside');
  const listeners = [];
  const listen = (target, type, callback, options) => {
    target.addEventListener(type, callback, options);
    listeners.push(() => target.removeEventListener(type, callback, options));
  };
  let phase = 'closed', page = 0, single = mediaQuery.matches, origin = null;
  let priorFocus = null, priorOverflow = '', turnFrame = 0;
  let turnProgress = 0, turnTarget = null, turnResolve = null, turnPromise = null;
  let openPromise = null, closePromise = null, closeRequested = false, operation = 0;
  let pointerStart = null, lastTurnDuration = 0, lastTurnFrames = 0, strips = [];
  let lifecycleFrame = 0, lifecycleMotion = null, lifecycleResolve = null;
  let flight = 0, aperture = 0, geometry = null, motionStage = 'rest';
  // Text-only editions have no image field; existing illustrated editions can
  // still preload their media through the same public readiness promise.
  const imageWarmup = pages.filter(data => data.image).map(data => {
    const image = new Image();
    image.src = `/media/resume-book/${data.image}.webp`;
    return image;
  });
  const ready = Promise.all(imageWarmup.map(image => image.decode()));
  ready.catch(() => {}); // Startup owns the visible retry/error state.
  const reduce = () => Boolean(reducedMotion || motionQuery.matches);
  const active = () => phase !== 'closed' && phase !== 'disposed';
  const stepSize = () => single ? 1 : 2;
  const maxPage = () => single ? pages.length - 1 : pages.length - 2;
  const rectData = rect => ({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });

  function article(index, side) {
    const data = pages[index];
    const element = document.createElement('article');
    element.className = `resume-page resume-page--${data.id} resume-page--${side}`;
    element.dataset.page = String(index + 1);
    element.setAttribute('aria-label', `第 ${index + 1} 页：${data.title}`);
    element.innerHTML = `<div class="resume-page__print"><header class="resume-page__header"><span>${data.label}</span><h3>${data.title}</h3></header><div class="resume-page__body">${data.content}</div><footer class="resume-page__footer"><span>王丞业 / 创作履历</span><b>${String(index + 1).padStart(2, '0')}</b></footer></div>`;
    element.querySelectorAll('img').forEach(image => { image.draggable = false; });
    return element;
  }

  function render() {
    if (leftSlot.contains(document.activeElement) || rightSlot.contains(document.activeElement)) {
      root.querySelector('[data-book-close]').focus({ preventScroll: true });
    }
    root.dataset.layout = single ? 'single' : 'spread';
    leftSlot.replaceChildren(article(page, 'left'));
    rightSlot.replaceChildren(...(single ? [] : [article(page + 1, 'right')]));
    rightSlot.hidden = single;
    updateControls();
  }

  function updateControls() {
    const busy = phase === 'turning' || phase === 'opening' || closeRequested;
    root.dataset.phase = phase;
    root.querySelectorAll('[data-book-step]').forEach(button => {
      const direction = Number(button.dataset.bookStep);
      const unavailable = direction < 0 ? page === 0 : page >= maxPage();
      button.setAttribute('aria-disabled', String(unavailable || busy));
      button.dataset.boundary = String(unavailable);
    });
    root.querySelectorAll('[data-book-page]').forEach(button => {
      const index = Number(button.dataset.bookPage);
      const selected = index === page || (!single && index === page + 1);
      if (selected) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
      button.setAttribute('aria-disabled', String(busy));
    });
    if (phase === 'idle') status.textContent = single
      ? `第 ${page + 1} 页，共 ${pages.length} 页。${pages[page].title}`
      : `第 ${page + 1} 至 ${page + 2} 页，共 ${pages.length} 页。${pages[page].title}，${pages[page + 1].title}`;
  }

  function measureBook() {
    // Layout metrics remain stable while the stage is flying. Reading its
    // transformed client rectangle would compound scale on Escape or resize.
    const box = root.getBoundingClientRect();
    geometry = {
      width: stage.offsetWidth, height: stage.offsetHeight,
      left: box.left + stage.offsetLeft, top: box.top + stage.offsetTop,
    };
  }

  function paintJacket() {
    if (!geometry) measureBook();
    const { width, height, left, top } = geometry;
    const pivotX = width * (single ? .5 : .75);
    const pageWidth = single ? width : width / 2;
    const homeX = origin ? clamp(origin.x + origin.width / 2, 0, window.innerWidth) : left + width / 2;
    const homeY = origin ? clamp(origin.y + origin.height / 2, 0, window.innerHeight) : top + height / 2 + 42;
    const initialScale = origin ? clamp(origin.width / pageWidth, .035, .82) : .38;
    const initialTilt = origin ? Math.acos(clamp(origin.height / (height * initialScale), .12, .95)) * 180 / Math.PI : 56;
    const closedCenterOffset = single ? 0 : -width / 4;
    const dx = (homeX - left - pivotX) * (1 - flight) + closedCenterOffset * flight * (1 - aperture);
    const dy = (homeY - top - height / 2) * (1 - flight);
    const scale = initialScale + (1 - initialScale) * flight;
    stage.style.transformOrigin = `${single ? 50 : 75}% 50%`;
    stage.style.transform = `translate3d(${dx}px, ${dy}px, 0) scale(${scale}) rotateX(${initialTilt * (1 - flight)}deg) rotateZ(${-5 * (1 - flight)}deg)`;
    stage.style.opacity = String(clamp(flight / .12, 0, 1));
    hinge.style.transform = `rotateY(${-180 * aperture}deg)`;
    hinge.style.setProperty('--jacket-light', String(Math.sin(aperture * Math.PI) * .24));
    root.style.setProperty('--book-ui-reveal', String(clamp((aperture - .68) / .32, 0, 1)));
    root.dataset.motionStage = motionStage;
  }

  function prepareJacket() {
    jacketInside.replaceChildren(article(page, 'left'));
    jacketInside.querySelectorAll('a, button').forEach(node => { node.tabIndex = -1; });
    jacket.hidden = false;
    root.dataset.jacket = 'active';
    measureBook();
    paintJacket();
  }

  function releaseJacket() {
    jacket.hidden = true;
    jacketInside.replaceChildren();
    delete root.dataset.jacket;
    delete root.dataset.motionStage;
    root.style.removeProperty('--book-ui-reveal');
    stage.style.removeProperty('transform');
    stage.style.removeProperty('transform-origin');
    stage.style.removeProperty('opacity');
    motionStage = 'rest';
  }

  function cancelLifecycle() {
    cancelAnimationFrame(lifecycleFrame); lifecycleFrame = 0;
    const resolve = lifecycleResolve;
    lifecycleMotion = null; lifecycleResolve = null;
    resolve?.(false);
  }

  function finishLifecycle() {
    if (!lifecycleMotion) return;
    const { property, target } = lifecycleMotion;
    if (property === 'flight') flight = target; else aperture = target;
    paintJacket();
    cancelAnimationFrame(lifecycleFrame); lifecycleFrame = 0;
    const resolve = lifecycleResolve;
    lifecycleMotion = null; lifecycleResolve = null;
    resolve?.(true);
  }

  function animateLifecycle(property, target, fullDuration, name) {
    cancelLifecycle();
    const from = property === 'flight' ? flight : aperture;
    motionStage = name;
    if (reduce() || Math.abs(target - from) < .001) {
      if (property === 'flight') flight = target; else aperture = target;
      paintJacket();
      return Promise.resolve(true);
    }
    const duration = Math.max(180, fullDuration * Math.abs(target - from));
    const started = performance.now();
    lifecycleMotion = { property, target, name };
    return new Promise(resolve => {
      lifecycleResolve = resolve;
      const frame = now => {
        const progress = clamp((now - started) / duration, 0, 1);
        const t = property === 'flight' && target === 1 ? 1 - (1 - progress) ** 3 : easing(progress);
        const value = from + (target - from) * t;
        if (property === 'flight') flight = value; else aperture = value;
        paintJacket();
        if (progress < 1) lifecycleFrame = requestAnimationFrame(frame);
        else finishLifecycle();
      };
      lifecycleFrame = requestAnimationFrame(frame);
    });
  }

  function stripFace(source, offset, width, height, back = false) {
    const face = document.createElement('div');
    face.className = `resume-book__strip-face${back ? ' resume-book__strip-face--back' : ''}`;
    if (source) {
      const clone = source.cloneNode(true);
      clone.classList.add('resume-page--slice');
      clone.style.cssText = `width:${width}px;height:${height}px;left:${-offset}px;`;
      clone.querySelectorAll('a, button').forEach(node => node.setAttribute('tabindex', '-1'));
      face.append(clone);
    } else face.classList.add('resume-book__strip-face--blank');
    const shade = document.createElement('i');
    shade.className = 'resume-book__strip-shade';
    face.append(shade);
    return { face, shade };
  }

  // A chain of narrow paper sections follows a continuous curved cross-section.
  // Front and back have separately clipped printing. Back-face culling means no
  // reader ever sees mirrored letters, including at the middle of a turn.
  function buildStrips(front, back, width, height) {
    const fragment = document.createDocumentFragment();
    strips = Array.from({ length: STRIP_COUNT }, (_, index) => {
      const strip = document.createElement('div');
      strip.className = 'resume-book__strip';
      const segment = width / STRIP_COUNT;
      const frontFace = stripFace(front, index * segment, width, height);
      const backFace = stripFace(back, width - (index + 1) * segment, width, height, true);
      strip.style.width = `${segment + .65}px`;
      strip.style.height = `${height}px`;
      strip.append(frontFace.face, backFace.face);
      fragment.append(strip);
      return { element: strip, frontShade: frontFace.shade, backShade: backFace.shade, segment };
    });
    layer.replaceChildren(fragment);
  }

  function paintTurn(progress, width) {
    turnProgress = progress;
    root.dataset.turnPhase = progress > .3 && progress < .7 ? 'curling' : 'settling';
    let x = 0, z = 0;
    const arch = Math.sin(progress * Math.PI);
    const base = single ? 0 : width;
    strips.forEach(({ element, frontShade, backShade, segment }, index) => {
      const along = (index + .5) / STRIP_COUNT;
      const angle = Math.PI * progress + .92 * arch * (along - .5);
      const lift = arch * Math.sin(along * Math.PI) * 5;
      element.style.transform = `translate3d(${base + x}px, ${-lift}px, ${z + 2}px) rotateY(${-angle}rad)`;
      const lighting = Math.abs(Math.sin(angle));
      frontShade.style.opacity = String(.025 + lighting * .19);
      backShade.style.opacity = String(.035 + lighting * .24);
      x += Math.cos(angle) * segment;
      z += Math.sin(angle) * segment;
    });
    shadow.style.opacity = String(arch * .25);
    shadow.style.transform = `translateX(${(progress - .5) * width * .7}px) scaleX(${.3 + arch * .7})`;
  }

  function finishTurn() {
    if (phase !== 'turning') return;
    cancelAnimationFrame(turnFrame); turnFrame = 0;
    page = turnTarget;
    turnTarget = null;
    layer.replaceChildren(); strips = [];
    delete root.dataset.turnPhase;
    shadow.style.opacity = '0';
    phase = 'idle';
    render();
    const resolve = turnResolve;
    turnResolve = null; turnPromise = null;
    resolve?.(true);
  }

  function turnTo(requested) {
    if (phase !== 'idle' || closeRequested) return Promise.resolve(false);
    const target = clamp(single ? requested : Math.floor(requested / 2) * 2, 0, maxPage());
    if (target === page) return Promise.resolve(false);
    // Rapid requests are intentionally ignored until this physical sheet settles.
    // Keeping one committed target avoids out-of-order page and focus changes.
    if (reduce()) { page = target; render(); return Promise.resolve(true); }
    const forward = target > page;
    if (leftSlot.contains(document.activeElement) || rightSlot.contains(document.activeElement)) {
      root.querySelector(`.resume-book__step[data-book-step="${forward ? 1 : -1}"]`).focus({ preventScroll: true });
    }
    const width = leftSlot.getBoundingClientRect().width;
    const height = leftSlot.getBoundingClientRect().height;
    if (!width || !height) return Promise.resolve(false);
    let front, back;
    if (single) {
      front = article(forward ? page : target, 'left');
      back = null;
      leftSlot.replaceChildren(article(forward ? target : page, 'left'));
    } else if (forward) {
      front = article(page + 1, 'right'); back = article(target, 'left');
      rightSlot.replaceChildren(article(target + 1, 'right'));
    } else {
      front = article(target + 1, 'right'); back = article(page, 'left');
      leftSlot.replaceChildren(article(target, 'left'));
    }
    phase = 'turning'; turnTarget = target; lastTurnFrames = 0;
    updateControls();
    buildStrips(front, back, width, height);
    paintTurn(forward ? 0 : 1, width);
    const started = performance.now();
    const duration = single ? 780 : 980;
    turnPromise = new Promise(resolve => { turnResolve = resolve; });
    const frame = now => {
      if (phase !== 'turning') return;
      const time = clamp((now - started) / duration, 0, 1);
      paintTurn(forward ? easing(time) : 1 - easing(time), width);
      lastTurnFrames += 1;
      if (time < 1) turnFrame = requestAnimationFrame(frame);
      else { lastTurnDuration = now - started; finishTurn(); }
    };
    turnFrame = requestAnimationFrame(frame);
    return turnPromise;
  }

  function finalizeClose(notify = true) {
    if (phase === 'closed' || phase === 'disposed') return;
    phase = 'closed'; closeRequested = false; operation += 1;
    document.body.style.overflow = priorOverflow;
    cancelLifecycle(); releaseJacket();
    if (root.open) root.close();
    if (priorFocus?.isConnected && typeof priorFocus.focus === 'function') priorFocus.focus({ preventScroll: true });
    priorFocus = null;
    updateControls();
    if (notify) onClose();
  }

  const api = {
    ready,
    open({ origin: rectangle } = {}) {
      if (phase === 'disposed') return Promise.resolve(false);
      if (phase === 'closing' || closeRequested) return Promise.resolve(false);
      if (phase !== 'closed') return phase === 'opening' ? openPromise : Promise.resolve(true);
      const valid = rectangle && ['x', 'y', 'width', 'height'].every(key => Number.isFinite(rectangle[key]));
      origin = valid ? { x: rectangle.x, y: rectangle.y, width: Math.max(1, rectangle.width), height: Math.max(1, rectangle.height) } : null;
      priorFocus = document.activeElement;
      priorOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      single = mediaQuery.matches;
      page = 0; turnProgress = 0; closeRequested = false; closePromise = null;
      flight = 0; aperture = 0;
      phase = 'opening'; const token = ++operation;
      render(); root.showModal();
      prepareJacket();
      openPromise = (async () => {
        if (!await animateLifecycle('flight', 1, 820, 'lifting')) return false;
        if (phase !== 'opening' || token !== operation) return false;
        if (!await animateLifecycle('aperture', 1, 1280, 'opening-cover')) return false;
        if (phase !== 'opening' || token !== operation) return false;
        releaseJacket();
        phase = 'idle'; updateControls();
        return true;
      })();
      return openPromise;
    },
    close() {
      if (!active()) return Promise.resolve(false);
      if (closePromise) return closePromise;
      closeRequested = true; const token = ++operation;
      cancelLifecycle(); updateControls();
      closePromise = (async () => {
        if (turnPromise) await turnPromise;
        if (!active()) return false;
        phase = 'closing'; updateControls();
        if (jacket.hidden) { flight = 1; aperture = 1; prepareJacket(); }
        if (!await animateLifecycle('aperture', 0, 1540, 'closing-cover')) return false;
        if (phase === 'disposed' || token !== operation) return false;
        if (!await animateLifecycle('flight', 0, 1020, 'returning-to-desk')) return false;
        if (phase === 'disposed' || token !== operation) return false;
        finalizeClose(); return true;
      })();
      return closePromise;
    },
    isOpen: active,
    getState() {
      return {
        open: active(), phase, page: page + 1, pageCount: pages.length,
        visiblePages: single ? [page + 1] : [page + 1, page + 2],
        layout: single ? 'single' : 'spread', reducedMotion: reduce(),
        targetPage: turnTarget === null ? null : turnTarget + 1,
        turnProgress: Number(turnProgress.toFixed(4)), stripCount: strips.length,
        animationActive: Boolean(lifecycleFrame || turnFrame), closeRequested,
        motionStage, coverOpenProgress: Number(aperture.toFixed(4)),
        flightProgress: Number(flight.toFixed(4)), jacketVisible: !jacket.hidden,
        lastTurnDuration: Math.round(lastTurnDuration), lastTurnFrames,
        origin: origin ? { ...origin } : null,
        bounds: active() ? rectData(stage.getBoundingClientRect()) : null,
        focusedWithin: root.contains(document.activeElement),
      };
    },
    dispose() {
      if (phase === 'disposed') return;
      if (phase === 'turning') finishTurn();
      finalizeClose(false);
      phase = 'disposed'; operation += 1;
      cancelAnimationFrame(turnFrame); cancelLifecycle();
      listeners.forEach(remove => remove());
      imageWarmup.length = 0;
      layer.replaceChildren(); strips = [];
      root.remove();
    },
  };

  listen(root, 'click', event => {
    const element = event.target instanceof Element ? event.target : null;
    if (element?.closest('[data-book-close]')) api.close();
    const step = element?.closest('[data-book-step]');
    if (step) turnTo(page + Number(step.dataset.bookStep) * stepSize());
    const selected = element?.closest('[data-book-page]');
    if (selected) turnTo(Number(selected.dataset.bookPage));
    if (event.target === root) {
      const bounds = shell.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) api.close();
    }
  });
  listen(root, 'cancel', event => { event.preventDefault(); api.close(); });
  listen(root, 'close', () => { if (!root.open && active()) { if (phase === 'turning') finishTurn(); finalizeClose(); } });
  listen(root, 'keydown', event => {
    event.stopPropagation();
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); turnTo(page + (event.key === 'ArrowRight' ? 1 : -1) * stepSize());
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault(); turnTo(event.key === 'Home' ? 0 : maxPage());
    } else if (event.key === 'Escape') { event.preventDefault(); api.close(); }
  });
  listen(stage, 'pointerdown', event => {
    if (phase !== 'idle' || event.button !== 0 || event.target.closest('a, button')) return;
    pointerStart = { x: event.clientX, y: event.clientY, id: event.pointerId, time: performance.now() };
    stage.setPointerCapture?.(event.pointerId);
  });
  listen(stage, 'pointerup', event => {
    if (!pointerStart || pointerStart.id !== event.pointerId) return;
    const dx = event.clientX - pointerStart.x, dy = event.clientY - pointerStart.y;
    const elapsed = performance.now() - pointerStart.time;
    pointerStart = null;
    if (Math.abs(dx) > 42 && Math.abs(dx) > Math.abs(dy) * 1.35 && elapsed < 1400) turnTo(page + (dx < 0 ? 1 : -1) * stepSize());
  });
  listen(stage, 'pointercancel', () => { pointerStart = null; });
  listen(stage, 'pointerleave', event => { if (event.pointerType === 'mouse') pointerStart = null; });
  listen(window, 'resize', () => {
    if (phase === 'turning') finishTurn();
    const next = mediaQuery.matches;
    if (single !== next) { single = next; if (!single) page = Math.floor(page / 2) * 2; render(); }
    if (!jacket.hidden) prepareJacket();
  });
  listen(motionQuery, 'change', () => {
    if (reduce()) { if (phase === 'turning') finishTurn(); finishLifecycle(); }
  });
  render();
  return api;
}
