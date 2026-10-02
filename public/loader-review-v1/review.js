import { DemoProgress } from './source/demo-progress.js';
import { createEffect } from './source/vendor/adapted-effects.js';

const $ = (selector) => document.querySelector(selector);
const gsap = window.gsap;
if (!gsap) throw new Error('本地 GSAP 未能加载，请刷新页面重试。');
const variants = {
  A: { title: '斜线启幕', source: 'Olaf · Website Reveal', url: 'https://github.com/olaf-wilkosz/gsap-website-reveal-animation/tree/5fc869e418af5b7df8baece5032df16483773f5b', note: '保留斜线填充、逐字进入与横向揭幕的原始编排。', license: 'MIT · Olaf, 2023' },
  B: { title: '折页开场', source: 'Codrops · Page Loading Effects', url: 'https://github.com/codrops/PageLoadingEffects/tree/d4348fe750a3903d962775f76b77fc41d203b0d4', note: '直接适配 Origami 的复合 SVG 路径，以折角打开整个页面。', license: 'MIT 核心代码 · 整合许可 · Codrops, 2014' },
  C: { title: '标志升起', source: 'Codrops · Page Preloading Effect', url: 'https://github.com/codrops/PagePreloadingEffect/tree/7a7893f4145f1dcfcf5dccd1ec893b24170fc987', note: '保留 PathLoader 描边算法与品牌、幕布、内容分层上移的原始结构。', license: 'MIT 核心代码 · 整合许可 · Codrops, 2014' },
  D: { title: '为你开窗', source: 'Codrops · Page Loading Effects', url: 'https://github.com/codrops/PageLoadingEffects/tree/d4348fe750a3903d962775f76b77fc41d203b0d4', note: '直接适配 Frame it 的双矩形路径，由中央开窗揭示首页。', license: 'MIT 核心代码 · 整合许可 · Codrops, 2014' },
};
const model = new DemoProgress();
const preview = $('#preview');
const mount = $('#effect-mount');
const mediaQuery = matchMedia('(prefers-reduced-motion: reduce)');
$('#reduce-motion').checked = mediaQuery.matches;
let id = /^[ABCD]$/.test(location.hash.slice(1)) ? location.hash.slice(1) : 'A';
let effect;
let lastPhase;
let revealStarted = false;
let revealPaused = false;
let generation = 0;
let reducedUserChoice = false;
let lastDiagnosticsAt = -Infinity;
let lastDiagnosticsPhase = '';

function writeDiagnostics() {
  const now = performance.now();
  const phaseKey = `${id}:${model.phase}:${model.playing}:${revealPaused}:${generation}`;
  if (phaseKey === lastDiagnosticsPhase && now - lastDiagnosticsAt < 100) return;
  lastDiagnosticsAt = now;
  lastDiagnosticsPhase = phaseKey;
  const style = getComputedStyle(mount);
  $('#loader-review-diagnostics').textContent = JSON.stringify({
    ...model.snapshot(), progress: Math.round(model.progress * 100) / 100,
    variant: id, reduced: $('#reduce-motion').checked, generation, revealPaused,
    overlayVisible: style.visibility !== 'hidden' && Number(style.opacity) > 0,
    overlayOpacity: Number(style.opacity), homeImageReady: $('.home-image').complete && $('.home-image').naturalWidth > 0,
    simulated: true, updatedAtMs: Math.round(now),
  });
}

function makeEffect() {
  generation++;
  const currentGeneration = generation;
  effect?.destroy();
  effect = createEffect({ mount, home: $('.home-demo'), id, gsap, reduced: $('#reduce-motion').checked, onComplete: () => {
    if (generation !== currentGeneration) return;
    model.complete();
    render();
  } });
  if (!model.playing) effect.pause();
  revealStarted = false;
  revealPaused = false;
}

function select(next, { play = true } = {}) {
  if (!variants[next]) return;
  id = next;
  model.reset();
  model.playing = play;
  model.setOptions({ wait: $('#simulate-wait').checked, fail: $('#simulate-failure').checked });
  makeEffect();
  document.querySelectorAll('[data-variant][role=tab]').forEach((button) => {
    const active = button.dataset.variant === id;
    button.setAttribute('aria-selected', active);
    button.tabIndex = active ? 0 : -1;
  });
  preview.dataset.variant = id;
  preview.setAttribute('aria-labelledby', `tab-${id}`);
  $('#variant-caption').textContent = `${id} / ${variants[id].title}`;
  $('#source-link').textContent = `${variants[id].source} ↗`;
  $('#source-link').href = variants[id].url;
  $('#source-note').textContent = variants[id].note;
  $('#source-license').textContent = variants[id].license;
  history.replaceState(null, '', `#${id}`);
  lastPhase = null;
  render();
}

function render() {
  const rounded = Math.floor(model.progress);
  effect.setProgress(model.progress);
  $('#progress').value = rounded;
  $('#progress-output').textContent = `${rounded}%`;
  preview.dataset.phase = model.phase;
  const message = model.phase === 'waiting' || model.phase === 'error';
  $('.stage-message').hidden = !message;
  $('#stage-retry').hidden = model.phase !== 'error';
  $('#stage-message-copy').textContent = model.phase === 'waiting' ? '模拟等待中，取消勾选后继续' : '模拟加载失败，画面保持遮挡';
  const paused = model.phase === 'revealing' ? revealPaused : !model.playing;
  $('#play').innerHTML = model.phase === 'complete' ? '再看一次 <span>↻</span>' : paused ? '继续 <span>▶</span>' : '暂停 <span>Ⅱ</span>';
  $('#play').setAttribute('aria-label', model.phase === 'complete' ? '重播当前方案' : paused ? '继续演示' : '暂停演示');
  $('#play').disabled = model.phase === 'error';
  const phaseLabel = model.phase === 'loading' ? model.playing ? '正在演示加载' : '已暂停 · 可拖动进度' : ({ waiting: '模拟等待 · 保持遮挡', error: '模拟失败 · 等待重试', revealing: revealPaused ? '退场已暂停' : '加载完成 · 正在揭幕', complete: '已到达终端首页示意' })[model.phase];
  if (phaseLabel !== lastPhase) { $('#phase-label').textContent = phaseLabel; lastPhase = phaseLabel; }
  if (model.phase === 'revealing' && !revealStarted) { revealStarted = true; effect.reveal(); }
  writeDiagnostics();
}

function scrub(value) {
  const wasRevealed = revealStarted || model.phase === 'complete';
  model.scrub(value);
  if (wasRevealed) makeEffect();
  effect.pause();
  render();
}

document.querySelectorAll('[data-variant][role=tab]').forEach((button) => button.addEventListener('click', () => select(button.dataset.variant)));
$('.variant-tabs').addEventListener('keydown', (event) => {
  const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  const choices = Object.keys(variants);
  const index = choices.indexOf(id);
  const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? 3 : (index + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + 4) % 4;
  select(choices[nextIndex]);
  $(`#tab-${id}`).focus();
});
$('#progress').addEventListener('input', (event) => scrub(event.target.value));
$('#replay').addEventListener('click', () => select(id));
$('#play').addEventListener('click', () => {
  if (model.phase === 'complete') select(id);
  else if (model.phase === 'revealing') { revealPaused = !revealPaused; revealPaused ? effect.pause() : effect.play(); }
  else if (model.phase !== 'error') { model.playing = !model.playing; model.playing ? effect.play() : effect.pause(); }
  render();
});
$('#stage-retry').addEventListener('click', () => { $('#simulate-failure').checked = false; select(id); });
for (const name of ['simulate-wait', 'simulate-failure']) {
  $(`#${name}`).addEventListener('change', () => {
    if ($(`#${name}`).checked || revealStarted || model.phase === 'complete') select(id);
    else { model.setOptions({ wait: $('#simulate-wait').checked, fail: $('#simulate-failure').checked }); render(); }
  });
}
$('#reduce-motion').addEventListener('change', () => { reducedUserChoice = true; select(id); });
mediaQuery.addEventListener('change', (event) => { if (!reducedUserChoice) { $('#reduce-motion').checked = event.matches; select(id); } });
$('#fullscreen').addEventListener('click', async () => {
  if (!preview.requestFullscreen) return;
  try { await preview.requestFullscreen(); select(id); } catch { $('#fullscreen').textContent = '当前浏览器不支持全屏'; }
});
if (!preview.requestFullscreen) $('#fullscreen').hidden = true;
$('#exit-fullscreen').addEventListener('click', () => document.exitFullscreen?.());
window.addEventListener('hashchange', () => { if (variants[location.hash.slice(1)]) select(location.hash.slice(1)); });

// Read-only diagnostics live in the DOM; all testing actions use visible controls.
select(id);
gsap.ticker.add((_time, deltaMs) => { if (document.hidden) return; model.advance(deltaMs / 1000); if (model.phase !== 'complete') render(); });
