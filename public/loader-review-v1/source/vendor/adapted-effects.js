/*
 * Adapted animation code, not a redistribution of the upstream demonstration sites.
 * A: Copyright (c) 2023 Olaf, MIT. See ../licenses/olaf-MIT.txt.
 * B/D: SVGLoader / PageLoadingEffects, Copyright 2014 Codrops, MIT code header.
 * C: PathLoader / PagePreloadingEffect, Copyright 2014 Codrops, MIT code header.
 * See ../licenses/Codrops-MIT.txt, preserved upstream README terms and ../ATTRIBUTION.md.
 * Source commits and file hashes are pinned in ../provenance.json.
 * Changes: local GSAP 3, scoped lifecycle, progress input, current brand, reduced motion,
 * replay/cancellation, no upstream fonts/images, no Snap.svg/classie/Modernizr.
 */

const BRAND = '/media/brand/atelier-fold-v2.svg';
const OUTLINE = 'M39 5 68 22V35L56 28 39 18 21 28V49L39 60 56 50V44L69 36V57L39 75 9 57V23L39 5Z';
const FOLD = 'M39 36 53 28 68 37V48L54 56 39 47V36L54 45 68 37M54 45V56';

// Origami (index12.html): relative paths normalized to identical absolute commands
// so GSAP core's numeric string interpolation replaces Snap.svg without another library.
export const SHAPES = Object.freeze({
  B: {
    closed: 'M -10 -10 L -10 70 L 90 70 L 90 -10 Z M 40 -40.5 L 40 30 L 40 100 L 40 30 Z',
    open: 'M -10 -10 L -10 70 L 90 70 L 90 -10 Z M 40 -40.5 L 120 30 L 40 100 L -40 30 Z',
  },
  // Frame it (index4.html): original compound rectangles, now explicit evenodd fill.
  D: {
    closed: 'M 0 0 L 0 60 L 80 60 L 80 0 Z M 40 30 L 40 30 L 40 30 L 40 30 Z',
    open: 'M 0 0 L 0 60 L 80 60 L 80 0 Z M 80 0 L 80 60 L 0 60 L 0 0 Z',
  },
});

// Directly adapted from Codrops pathLoader.js _draw / constructor (MIT, 2014).
export class PathLoader {
  constructor(el) {
    this.el = el;
    this.length = el.getTotalLength();
    el.style.strokeDasharray = el.style.strokeDashoffset = this.length;
  }
  setProgress(value) { this.el.style.strokeDashoffset = this.length * (1 - Math.max(0, Math.min(1, value))); }
}

const number = '<div class="effect-number"><b data-number>00</b><span>%</span></div>';
const top = `<div class="effect-top"><img src="${BRAND}" alt=""><span>CREATIVE SPACE / 正在准备</span></div>`;
const bottom = `<div class="effect-bottom"><div><p data-loading-copy>载入创作空间</p><small>房间 · 长廊 · 档案</small></div>${number}</div>`;
const shape = (id) => `<svg class="shape-overlay" viewBox="0 0 80 60" preserveAspectRatio="none" aria-hidden="true"><path fill-rule="evenodd" d="${SHAPES[id].closed}"></path></svg>`;

function markup(id) {
  if (id === 'A') return `<div class="effect effect-A"><div class="a-brand-screen"><div><div class="loading-word" aria-label="创作空间"><span>创</span><span>作</span><span>空</span><span>间</span></div><p class="micro-copy">一个小小的开始</p></div></div><div class="a-preloader">${top}<div class="effect-center"><div class="a-gauge"><div class="a-fill"></div></div><p class="a-center-note">把想法，装进一个空间</p></div>${bottom}</div><div class="a-revealer"></div></div>`;
  if (id === 'B') return `<div class="effect effect-B">${shape(id)}<div class="shape-ui">${top}<div class="effect-center"><div class="b-fold"><i class="b-axis"></i><img src="${BRAND}" alt=""></div><div class="loading-word">创作空间</div><div class="b-progress"><span></span></div><p class="micro-copy">每一个折角，都通向新的想法</p></div>${bottom}</div></div>`;
  if (id === 'C') return `<div class="effect effect-C"><div class="c-header">${top}<div class="c-load-copy"><p>创作空间</p><small>正在描绘进入的方式</small></div>${bottom}</div><div class="c-logo"><svg viewBox="0 0 80 80" aria-hidden="true"><path class="outline-bg" d="${OUTLINE}"></path><path class="outline" d="${OUTLINE}"></path><path class="outline fold-trace" d="${FOLD}"></path></svg><img src="${BRAND}" alt="创作空间标志"></div></div>`;
  return `<div class="effect effect-D">${shape(id)}<div class="shape-ui">${top}<svg class="d-frame" viewBox="0 0 800 600" preserveAspectRatio="none" aria-hidden="true"><rect x="0" y="0" width="800" height="600"></rect><rect class="d-frame-progress" x="0" y="0" width="800" height="600" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100"></rect></svg><div class="effect-center d-center">${number}<div class="loading-word">即将，为你打开</div></div><div class="effect-bottom"><div><p data-loading-copy>载入创作空间</p><small>让所有场景，先一步就绪</small></div><small>CREATIVE SPACE — 01</small></div></div></div>`;
}

export function createEffect({ mount, home, id, gsap, reduced, onComplete }) {
  mount.innerHTML = markup(id);
  const el = mount.firstElementChild;
  const q = (selector) => el.querySelector(selector);
  const qa = (selector) => [...el.querySelectorAll(selector)];
  const paths = id === 'C' ? qa('.outline').map((path) => new PathLoader(path)) : [];
  let timeline;
  let entrance;
  const ctx = gsap.context(() => {
    gsap.set(home, { clearProps: 'transform,opacity,visibility' });
    gsap.set(mount, { autoAlpha: 1 });
    if (id === 'C') gsap.set(q('.c-logo'), { x: 0, y: 0, xPercent: -50, yPercent: -65 });
    if (!reduced) {
      entrance = gsap.timeline();
      if (id === 'A') entrance.from(q('.a-gauge'), { scale: .8, duration: 1, ease: 'power1.inOut' });
      else entrance.from(qa('.effect-top, .effect-bottom'), { opacity: 0, duration: .6 });
    }
  }, mount);

  function setProgress(progress) {
    const value = Math.max(0, Math.min(100, progress));
    qa('[data-number]').forEach((node) => { node.textContent = Math.floor(value).toString().padStart(2, '0'); });
    if (id === 'A') q('.a-fill').style.transform = `translateY(${100 - value}%)`;
    if (id === 'B') q('.b-progress span').style.transform = `scaleX(${value / 100})`;
    if (id === 'C') {
      paths.forEach((path) => path.setProgress(value / 100));
      q('.c-logo img').style.opacity = Math.max(0, (value - 82) / 18);
    }
    if (id === 'D') q('.d-frame-progress').style.strokeDashoffset = 100 - value;
  }

  function reveal() {
    // One scoped timeline: switching/replaying destroys every delayed callback.
    ctx.add(() => {
      gsap.killTweensOf([el, ...el.querySelectorAll('*')]);
      timeline = gsap.timeline({ onComplete });
      if (reduced) {
        timeline.to(mount, { autoAlpha: 0, duration: .16 });
        return;
      }
      if (id === 'A') {
        // Olaf script.js: pre-loader zoom-out, staggered letters, revealer scale then exit.
        timeline.to(q('.a-gauge'), { scale: 1.5, opacity: 0, duration: .4, ease: 'power3.inOut' }, .12)
          .to(q('.a-preloader'), { autoAlpha: 0, duration: .5, ease: 'power3.inOut' }, .22)
          .fromTo(qa('.loading-word span'), { x: 40, opacity: 0 }, { x: 0, opacity: 1, stagger: .08, duration: .7, ease: 'expo.out' }, .4)
          .fromTo(q('.a-brand-screen .micro-copy'), { opacity: 0 }, { opacity: .6, duration: .4 }, .85)
          .to(q('.a-revealer'), { scaleX: 1, duration: .65, ease: 'power3.inOut' }, 1.25)
          .set(q('.a-brand-screen'), { autoAlpha: 0 })
          .set(el, { background: 'transparent' })
          .to(q('.a-revealer'), { xPercent: 100, duration: .75, ease: 'power3.inOut' })
          .fromTo(home, { x: -25, opacity: .8 }, { x: 0, opacity: 1, duration: .75, ease: 'power3.out' }, '<');
      } else if (id === 'B' || id === 'D') {
        // SVGLoader.hide(): animate closing path, then release/reset overlay.
        timeline.to(q('.shape-ui'), { opacity: 0, scale: id === 'B' ? .96 : 1, duration: .28 }, .14)
          .to(q('.shape-overlay path'), { attr: { d: SHAPES[id].open }, duration: id === 'B' ? 1.3 : 1.2, ease: 'power3.inOut' }, .3)
          .fromTo(home, { scale: id === 'B' ? 1.065 : .94 }, { scale: 1, duration: 1.25, ease: 'power3.out' }, .3);
      } else {
        // effect1.css animLoadedLoader/Header/Logo/Content, ported into one GSAP timeline.
        timeline.to(qa('.c-load-copy, .effect-bottom, .effect-top'), { opacity: 0, y: -24, duration: .4, ease: 'power3.in' }, .12)
          .to(q('.c-logo'), { left: '6%', top: '7%', xPercent: 0, yPercent: 0, width: 32, height: 32, duration: 1.05, ease: 'power3.inOut' }, .2)
          .to(q('.c-header'), { yPercent: -100, duration: 1.1, ease: 'power3.inOut' }, .35)
          .fromTo(home, { y: 65, opacity: .55 }, { y: 0, opacity: 1, duration: 1, ease: 'power3.out' }, .45)
          .to(q('.c-logo'), { opacity: 0, duration: .18 }, 1.4);
      }
      timeline.set(mount, { autoAlpha: 0 });
    });
  }

  return {
    setProgress, reveal,
    pause() { entrance?.pause(); timeline?.pause(); },
    play() { entrance?.play(); timeline?.play(); },
    destroy() { ctx.revert(); mount.replaceChildren(); },
  };
}
