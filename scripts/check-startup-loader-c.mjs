import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createStartupReadiness } from '../src/startup-readiness.js';
import { parseModelForCPU, introFixture, emit } from './lib/intro-controller-fixture.mjs';

const read = (file) => readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');
const html = read('index.html'), main = read('src/main.js'), css = read('src/cube-intro.scss');
let passed = 0;
async function check(name, fn) { await fn(); passed++; console.log(`PASS ${name}`); }
async function fixture(options = {}) {
  const [welcomeGltf, roomGltf] = await Promise.all([
    parseModelForCPU('public/models/welcome-terminal-v1.glb'), parseModelForCPU('public/models/orbital-atelier-v16.glb'),
  ]);
  return introFixture({ welcomeGltf, roomGltf, ...options });
}

await check('actual main onUpdate maps real weighted readiness to all logo paths and ARIA, including failure', () => {
  const begin = main.indexOf('onUpdate: progress => {');
  const end = main.indexOf('\n} });', begin);
  assert(begin >= 0 && end > begin);
  const source = main.slice(begin + 'onUpdate: '.length, end + 2);
  const makeNode = () => ({ textContent: '', dataset: {}, attributes: {}, style: { setProperty(name, value) { this[name] = value; } }, setAttribute(name, value) { this.attributes[name] = String(value); } });
  const traces = Array.from({ length: 3 }, makeNode), nodes = new Map();
  const get = (selector) => { if (!nodes.has(selector)) nodes.set(selector, makeNode()); return nodes.get(selector); };
  const screen = makeNode(); screen.querySelectorAll = (selector) => selector === '[data-loading-trace]' ? traces : [];
  const callback = vm.runInNewContext(`(${source})`, { $: get, meter: get('.loading-meter'), loadingStatus: get('#loading-status'), loadingScreen: screen, document: { querySelector: get } });
  const ready = createStartupReadiness({ onUpdate: callback });
  const verify = (percent) => {
    assert.equal(get('#loading-percent').textContent, `${percent}%`);
    assert.equal(get('.loading-meter').attributes['aria-valuenow'], String(percent));
    assert.equal(screen.style['--startup-progress'], String(percent / 100));
    traces.forEach((path) => assert.equal(path.style.strokeDashoffset, String(100 - percent)));
  };
  ready.update('room', .5, '真实房间阶段'); verify(30);
  ready.update('room', 1); ready.update('gallery', 1); ready.update('about', 1); ready.update('warmup', 1); verify(99);
  assert.equal(ready.getState().ready, false);
  ready.finish(); verify(100);
  const failed = createStartupReadiness({ onUpdate: callback });
  failed.update('room', 1); failed.update('gallery', 1); failed.fail('关于场景失败'); verify(78);
  failed.update('about', 1); failed.update('warmup', 1); assert.throws(() => failed.finish()); verify(78);
  assert.equal(get('#loading-status').textContent, '关于场景失败');
});

await check('approved orbital logo faces exactly match loader traces and every main brand uses the new asset', () => {
  const logo = read('public/media/brand/atelier-orbit-v4.svg');
  const faces = [...logo.matchAll(/<path data-brand-face="[^"]+" d="([^"]+)"/g)].map((match) => match[1]);
  const traces = [...html.matchAll(/<path data-loading-trace[^>]* d="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(faces.length, 3); assert.deepEqual(traces, faces);
  assert.equal((html.match(/src="\/media\/brand\/atelier-orbit-v4.svg"/g) ?? []).length, 3);
  assert(!html.includes('atelier-fold-v2'));
  assert(!/<script|<image|https?:\/\/(?!www.w3.org)/.test(logo));
  assert.match(css, /\.loading-meter \{[^}]*clip-path: inset\(50%\)/);
  assert.match(css, /\.cube-intro\[data-motion="reduce"\] \.startup-mark-sheen::after/);
});

await check('real controller locks wheel, click and skip until C reveal completes, then enters exactly once', async () => {
  const f = await fixture();
  try {
    const timeline = f.ready();
    assert.equal(f.intro.getState().loadingReveal, true);
    assert.equal(f.element.querySelector('.intro-enter').disabled, true);
    assert.equal(f.element.querySelector('.intro-skip').disabled, true);
    timeline.time(.65);
    for (let i = 0; i < 3; i++) {
      emit(f.view, 'wheel', { deltaY: 80 }); emit(f.element.querySelector('.intro-enter'), 'click');
      emit(f.view, 'keydown', { key: 'Escape' }); f.intro.skip();
    }
    assert.equal(f.counts.start, 0); assert.equal(f.counts.complete, 0);
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 1);
    timeline.progress(1); f.intro.update();
    assert.equal(f.intro.getState().loadingReveal, false);
    assert.equal(f.element.dataset.loadingReveal, 'complete');
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 0);
    assert.equal(f.element.querySelector('.intro-enter').disabled, false);
    f.enter('wheel'); emit(f.view, 'wheel', { deltaY: 50 }); assert.equal(f.counts.start, 1);
    f.intro.skip(); f.assertRestored(); assert.equal(f.counts.complete, 1);
  } finally { f.cleanup(); }
});

await check('reduced motion uses a short fade without moving the logo or curtain, with the same input lock', async () => {
  const f = await fixture({ reducedMotion: true });
  try {
    const timeline = f.ready(); assert(timeline.duration() <= .17); assert.equal(f.intro.getState().loadingReveal, true);
    timeline.progress(1); f.intro.update();
    assert.equal(f.element.querySelector('.startup-mark').x, 0);
    assert.equal(f.element.querySelector('.startup-mark').scale, 1);
    assert.equal(f.element.querySelector('.startup-curtain').yPercent, 0);
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 0);
    assert.equal(f.intro.getState().loadingReveal, false);
    f.enter(); f.assertRestored(); assert.equal(f.counts.complete, 1);
  } finally { f.cleanup(); }
});

await check('motion preference change during reveal finishes it before enabling entry', async () => {
  const f = await fixture();
  try {
    const timeline = f.ready(); timeline.time(.4);
    emit(f.media, 'change', { matches: true });
    assert.equal(f.intro.getState().loadingReveal, false); assert.equal(f.intro.getState().reducedMotion, true);
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 0);
    f.enter(); f.assertRestored();
  } finally { f.cleanup(); }
});

await check('resize before readiness stays covered; resize during reveal completes the handoff at the new layout', async () => {
  const f = await fixture();
  try {
    let viewport = { width: 1280, height: 720 };
    const layout = () => {
      const mobile = viewport.width <= 700;
      const size = mobile ? 150 : Math.max(170, Math.min(240, viewport.width * .19));
      const center = [viewport.width / 2, viewport.height * (mobile ? .38 : .4)];
      const inset = mobile ? 24 : Math.max(28, Math.min(96, viewport.width * .06));
      return { mark: { left: center[0] - size / 2, top: center[1] - size / 2, width: size, height: size },
        brand: { left: inset + 8, top: (mobile ? 23 : 33) + 8, width: mobile ? 44 : 52, height: mobile ? 44 : 52 } };
    };
    const mark = f.element.querySelector('.startup-mark');
    const brandImage = f.element.querySelector('.intro-brand img');
    mark.getBoundingClientRect = () => layout().mark;
    brandImage.getBoundingClientRect = () => layout().brand;
    f.intro.resize();
    assert.equal(f.intro.getState().phase, 'prepared');
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 1);
    const timeline = f.ready(); timeline.time(.45);
    assert.equal(f.intro.getState().loadingReveal, true);
    viewport = { width: 390, height: 844 };
    f.view.innerWidth = viewport.width; f.view.innerHeight = viewport.height;
    f.camera.aspect = viewport.width / viewport.height;
    f.intro.resize();
    assert.equal(timeline.progress(), 1);
    assert.equal(f.intro.getState().loadingReveal, false);
    assert.equal(f.element.querySelector('.intro-loader').autoAlpha, 0);
    assert.equal(mark.autoAlpha, 0, 'the old-layout moving copy is hidden');
    assert.equal(f.element.querySelector('.intro-brand').autoAlpha, 1);
    const brand = brandImage.getBoundingClientRect();
    assert.deepEqual([brand.left + brand.width / 2, brand.top + brand.height / 2], [54, 53]);
    assert.equal(brand.width, 44);
    assert.equal(f.counts.start, 0); assert.equal(f.counts.complete, 0);
    f.intro.resize(); assert.equal(timeline.progress(), 1);
    f.enter('wheel'); emit(f.view, 'wheel', { deltaY: 80 }); assert.equal(f.counts.start, 1);
    f.intro.skip(); f.assertRestored();
  } finally { f.cleanup(); }
});

await check('ready re-reads a reduced preference missed during asset loading and keeps CSS/controller aligned', async () => {
  const f = await fixture({ reducedMotion: false });
  try {
    assert.equal(f.intro.getState().reducedMotion, false);
    // No change event: the preference is already true when the late-created
    // controller first reads its MediaQueryList, while main captured false.
    f.media.matches = true;
    const timeline = f.ready();
    assert.equal(f.intro.getState().reducedMotion, true);
    assert.equal(f.element.dataset.motion, 'reduce');
    assert(timeline.duration() <= .17);
    f.media.matches = false; emit(f.media, 'change', { matches: false });
    assert.equal(f.intro.getState().reducedMotion, true);
    assert.equal(f.element.dataset.motion, 'reduce', 'CSS stays reduced with the conservative controller flag');
    timeline.progress(1); f.intro.update();
    assert.equal(f.element.querySelector('.startup-mark').x, 0);
    assert.equal(f.element.querySelector('.startup-curtain').yPercent, 0);
    f.enter(); f.assertRestored();
  } finally { f.cleanup(); }
});

await check('disposing during logo movement cannot enable input through a stale completion callback', async () => {
  const f = await fixture();
  try {
    const timeline = f.ready(); timeline.time(.45); f.intro.dispose();
    assert.equal(f.intro.getState().phase, 'disposed'); assert.equal(f.intro.getState().loadingReveal, false);
    assert.equal(f.element.dataset.loadingReveal, 'cancelled');
    timeline.progress(1);
    assert.equal(f.element.querySelector('.intro-enter').disabled, true);
    assert.equal(f.counts.start, 0); assert.equal(f.counts.complete, 0);
  } finally { f.cleanup(); }
});

await check('main still fences GPU work and finishes all stages before calling C ready()', () => {
  const create = main.indexOf('cubeIntro = createCubeIntro(');
  const compile = main.indexOf('await renderer.compileAsync(scene, camera)', create);
  const render = main.indexOf('renderer.render(scene, camera)', compile);
  const fence = main.indexOf('await waitForStartupGpu(renderer)', render);
  const finish = main.indexOf('startupReadiness.finish()', fence);
  const reveal = main.indexOf('cubeIntro.ready()', finish);
  assert(create > 0 && compile > create && render > compile && fence > render && finish > fence && reveal > finish);
  assert(!main.includes('DemoProgress'));
});

console.log(`\n${passed} C integration CPU checks passed. Real controller/GSAP/Three hierarchy; DOM layout and image decode are explicit substitutes. No browser, WebGL, visual or frame-rate claim.`);
