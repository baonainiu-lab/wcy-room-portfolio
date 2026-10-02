import './work-detail.scss';

const media = '/media/works/sugar-shell-glutton';
const chapters = [
  [0, '作品预览'], [3, '战斗与技能'], [23, '道具构筑'],
  [31, '区域探索'], [39, '成长与工坊'], [47, '开发过程'],
];
const features = [
  ['01', '战斗与技能', '把技能连成一套打法。', '观察敌人预警，通过位移规避，再把聚怪、破甲与范围攻击组合起来。重击通过蓄压、前冲、落地与收势组织节奏，在接触点结算伤害。', 'combat', '技能组合：聚怪、破甲与范围攻击的实机画面', 7],
  ['02', '随机道具构筑', '每次选择，改变这一局。', '通过随机道具选择与组合，形成不同的局内打法。战斗后的选择继续影响接下来的探索，让技能与道具之间形成联系。', 'build', '实机中的随机道具选择界面', 23],
  ['03', '三片区域探索', '把战斗带进更大的世界。', '演示依次展示草莓、可可与琥珀区域的场景探索，包含宝箱与导航路线。不同环境串起探索过程，给局内成长提供空间。', 'exploration', '琥珀猎场的场景探索画面', 31],
  ['04', '永久成长与工坊', '这一局之后，仍有积累。', '永久成长与工坊扩建承接每次冒险的收获。通过工坊界面查看成长与扩建，让战斗、资源和后续发展形成循环。', 'workshop', '永久成长与工坊扩建界面', 39],
];
const stamp = seconds => `00:${String(seconds).padStart(2, '0')}`;

/**
 * Shared by the gallery and direct work page. open({ origin }) accepts a screen
 * rectangle in viewport pixels. open/close return promises for their animations;
 * isOpen stays true until the closing animation and native dialog close finish.
 */
export function createWorkDetail({ standalone = false, reducedMotion = false, onClose = () => {}, onPlaybackChange = () => {} } = {}) {
  const root = document.createElement(standalone ? 'main' : 'dialog');
  root.className = 'work-detail';
  root.dataset.presentation = standalone ? 'document' : 'exhibit';
  root.dataset.phase = standalone ? 'open' : 'closed';
  root.setAttribute('aria-labelledby', 'sugar-work-title');
  if (!standalone) root.setAttribute('aria-modal', 'true');
  root.innerHTML = `
    ${standalone ? '' : '<div class="work-detail__frame" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'}
    <header class="work-detail__bar">
      ${standalone ? '<a class="work-detail__back" href="/">← 返回创作空间</a>' : '<button class="work-detail__back" type="button" data-work-close autofocus>← 返回长廊</button>'}
      <span class="work-detail__archive">SELECTED WORK <i>／</i> 01</span>
      <a class="work-detail__jump" href="#work-contribution" data-work-anchor="work-contribution">个人贡献 <span aria-hidden="true">↗</span></a>
    </header>
    <div class="work-detail__viewport">
    <article class="work-detail__body">
      <div class="work-detail__lead">
      <section class="work-detail__hero" aria-labelledby="sugar-work-title">
        <div class="work-detail__hero-top"><p class="work-detail__eyebrow">游戏原型 <span>·</span> VIBE CODING</p><span class="work-detail__edition">王丞业 / 个人作品</span></div>
        <div class="work-detail__heading"><h1 id="sugar-work-title">糖壳<span>暴食兽</span><b aria-hidden="true">.</b></h1><p>战斗、构筑、探索。<br>一个从玩法想法走向实机的 3D 原型。</p></div>
        <dl class="work-detail__meta"><div><dt>项目类型</dt><dd>3D 玩法原型</dd></div><div><dt>开发工具</dt><dd>Godot 4 / GDScript</dd></div><div><dt>制作方式</dt><dd>Blender / AI Coding</dd></div><div><dt>演示时长</dt><dd>60 秒 · 1080p</dd></div></dl>
        ${standalone ? '' : '<a class="work-detail__reading" href="/works/sugar-shell-glutton/">打开独立作品页 <span aria-hidden="true">↗</span></a>'}
      </section>
      <section class="work-detail__screen" id="work-film" aria-label="作品演示视频">
        <div class="work-detail__player">
          <video controls playsinline muted preload="none" poster="${media}/poster.webp" aria-label="糖壳暴食兽，60秒1080p实机演示" tabindex="0"><source src="${media}/demo-1080p.mp4" type="video/mp4">浏览器不支持视频播放，请下载原片观看。</video>
          <button type="button" class="work-detail__play" aria-label="播放糖壳暴食兽演示"><span aria-hidden="true">▶</span>播放实机演示 <small>01:00</small></button>
        </div>
        <p class="work-detail__video-status" role="status" hidden>视频暂时无法播放。<button type="button" data-work-retry>重新加载</button><a href="${media}/demo-1080p.mp4" download>下载原片</a></p>
        <div class="work-detail__film-caption"><span>实机画面 · 独立演示存档编排</span><a href="${media}/demo-1080p.mp4" download>下载 1080p 原片 ↗</a></div>
        <nav class="work-detail__chapters" aria-label="视频章节">${chapters.map(([time, title]) => `<button type="button" data-work-seek="${time}"><span>${stamp(time)}</span>${title}</button>`).join('')}</nav>
      </section>
      </div>
      <section class="work-detail__intro" data-work-reveal><p class="work-detail__eyebrow">THE PROTOTYPE</p><h2>从一次战斗，<br>到一段完整的成长。</h2><p>以战斗技能组合、随机道具构筑和三片区域探索为核心，串联永久成长与工坊扩建。这份演示展示当前可运行的玩法，以及它背后的原型搭建与迭代过程。</p></section>
      <section class="work-detail__features" aria-label="玩法拆解">${features.map(([number, category, title, description, image, alt, time]) => `
        <section class="work-detail__feature" data-work-reveal>
          <div class="work-detail__feature-copy"><p class="work-detail__eyebrow"><span>${number}</span> ${category}</p><h2>${title}</h2><p>${description}</p><button class="work-detail__timestamp" type="button" data-work-seek="${time}">观看对应片段 <span>${stamp(time)} ↗</span></button></div>
          <figure><img src="${media}/${image}.webp" width="1920" height="1080" loading="lazy" decoding="async" alt="${alt}" /><figcaption><span>实机截图 / ${category}</span><span>${number}—04</span></figcaption></figure>
        </section>`).join('')}</section>
      <section class="work-detail__contribution" id="work-contribution" data-work-reveal>
        <div><p class="work-detail__eyebrow">MY CONTRIBUTION</p><h2>我在项目中<br>做了什么。</h2><p>主导玩法原型的搭建与迭代，让设计落在可运行、可验证的实机流程中。</p></div>
        <div class="work-detail__roles"><section><span>01</span><div><h3>玩法与数值设计</h3><p>技能组合、道具构筑、区域探索，以及永久成长与工坊扩建的玩法组织。</p></div></section><section><span>02</span><div><h3>原型与资产接入</h3><p>Godot / GDScript 原型搭建、三维资产接入，打通从场景到交互的实机流程。</p></div></section><section><span>03</span><div><h3>测试与迭代</h3><p>结合问题定位与回归验证持续调整。视频中的代码与测试片段记录了已有的开发过程。</p></div></section></div>
      </section>
      <aside class="work-detail__production"><p class="work-detail__eyebrow">制作说明</p><p>AI Coding 辅助需求拆分、代码实现、问题定位和回归验证。美术与开发结合 AI、Blender 脚本及 CC0 特效素材；演示使用独立存档编排实机流程。Agent NPC 与多路线任务属于后续设计。</p><p class="work-detail__pending">可玩版本与项目源码链接：待补充。</p></aside>
      <footer class="work-detail__footer"><span>01 / 糖壳暴食兽</span>${standalone ? '<a href="/">返回创作空间 ↗</a>' : '<button type="button" data-work-close>继续逛长廊 ↗</button>'}</footer>
    </article>
    </div>`;
  document.body.append(root);
  const video = root.querySelector('video');
  const playButton = root.querySelector('.work-detail__play');
  const error = root.querySelector('.work-detail__video-status');
  const viewport = root.querySelector('.work-detail__viewport');
  const cleanups = [];
  const listen = (target, name, fn) => { target.addEventListener(name, fn); cleanups.push(() => target.removeEventListener(name, fn)); };
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const motionReduced = () => reducedMotion || motionPreference.matches;
  let phase = standalone ? 'open' : 'closed', pendingSeek = null, observer, priorTitle;
  let origin = null, operation = 0, animations = [], transition = Promise.resolve(), disposed = false;
  const setPhase = value => { phase = value; root.dataset.phase = value; };
  const scrollTo = id => root.querySelector(`#${id}`).scrollIntoView({ behavior: motionReduced() ? 'instant' : 'smooth', block: 'start' });
  const showError = () => { error.hidden = false; playButton.hidden = true; onPlaybackChange(false); };
  const play = () => {
    error.hidden = true;
    if (video.error) video.load();
    const promise = video.play();
    promise?.catch(reason => { if (reason.name !== 'AbortError') { if (video.error) showError(); else playButton.hidden = false; } });
  };
  listen(video, 'error', showError);
  listen(video.querySelector('source'), 'error', showError);
  listen(video, 'loadedmetadata', () => { if (pendingSeek !== null) { video.currentTime = Math.min(pendingSeek, video.duration || 60); pendingSeek = null; } });
  listen(video, 'play', () => { playButton.hidden = true; onPlaybackChange(true); });
  listen(video, 'pause', () => onPlaybackChange(false));
  listen(video, 'ended', () => { playButton.hidden = false; onPlaybackChange(false); });
  listen(root, 'click', event => {
    if (event.target.closest('[data-work-close]')) api.close();
    if (event.target.closest('.work-detail__play')) play();
    if (event.target.closest('[data-work-retry]')) { video.load(); play(); }
    const chapter = event.target.closest('[data-work-seek]');
    if (chapter) {
      const time = Number(chapter.dataset.workSeek);
      if (video.readyState >= 1) video.currentTime = time; else pendingSeek = time;
      scrollTo('work-film'); play();
    }
    const anchor = event.target.closest('[data-work-anchor]');
    if (anchor) { event.preventDefault(); scrollTo(anchor.dataset.workAnchor); }
  });
  // Native dialog handles focus containment. Stop scene shortcuts reaching main.
  listen(root, 'keydown', event => event.stopPropagation());
  listen(root, 'cancel', event => { event.preventDefault(); api.close(); });
  listen(document, 'visibilitychange', () => { if (document.hidden) video.pause(); });
  const reveal = () => {
    observer?.disconnect();
    if (motionReduced() || !('IntersectionObserver' in window)) return;
    root.dataset.motion = 'ready';
    observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.dataset.revealed = 'true'; observer.unobserve(entry.target); }
    }), { root: standalone ? null : viewport, threshold: .06 });
    root.querySelectorAll('[data-work-reveal]').forEach(node => observer.observe(node));
  };
  const cancelAnimations = () => { animations.forEach(animation => animation.cancel()); animations = []; };
  const animate = (node, frames, options) => {
    if (!node || !node.animate) return;
    const animation = node.animate(frames, { fill: 'both', easing: 'cubic-bezier(.22,1,.36,1)', ...options });
    // A new open/close request can cancel every layer without rejected promises.
    animation.finished.catch(() => {});
    animations.push(animation);
  };
  const normalizeOrigin = value => {
    if (!value || !['x', 'y', 'width', 'height'].every(key => Number.isFinite(value[key])) || value.width <= 0 || value.height <= 0) return null;
    return { x: value.x, y: value.y, width: value.width, height: value.height };
  };
  const resolvedOrigin = () => {
    if (!origin) return null;
    // The gallery projection may come from a larger viewport before a resize.
    const width = Math.min(origin.width, Math.max(1, window.innerWidth - 16));
    const height = Math.min(origin.height, Math.max(1, window.innerHeight - 16));
    return { x: Math.max(8, Math.min(origin.x, window.innerWidth - width - 8)), y: Math.max(8, Math.min(origin.y, window.innerHeight - height - 8)), width, height };
  };
  const sourceTransform = () => {
    // The root is in its final layout before animation. Projection coordinates
    // and getBoundingClientRect use the same viewport-pixel coordinate space.
    const width = root.offsetWidth, height = root.offsetHeight;
    const left = root.offsetLeft, top = root.offsetTop;
    const source = resolvedOrigin();
    if (!source || !width || !height) return 'translate(0, 20px) scale(.94, .96)';
    const dx = source.x + source.width / 2 - left - width / 2;
    const dy = source.y + source.height / 2 - top - height / 2;
    return `translate(${dx}px, ${dy}px) scale(${source.width / width}, ${source.height / height})`;
  };
  const finishClose = () => {
    if (phase === 'closed' || disposed) return;
    cancelAnimations(); video.pause(); observer?.disconnect(); root.removeAttribute('data-motion');
    setPhase('closed');
    if (root.open) root.close();
    if (priorTitle) document.title = priorTitle;
    priorTitle = undefined;
    onPlaybackChange(false); onClose();
  };
  if (!standalone) listen(root, 'close', () => {
    // Native close events are queued; an already reopened dialog stays open.
    if (!root.open && phase !== 'closed') { operation++; finishClose(); }
  });
  listen(motionPreference, 'change', () => {
    if (!motionReduced()) return;
    root.removeAttribute('data-motion'); observer?.disconnect();
    animations.forEach(animation => animation.finish());
  });
  const api = {
    open({ origin: nextOrigin } = {}) {
      if (disposed || standalone || phase === 'open' || phase === 'opening') return transition;
      const reopening = phase === 'closing';
      const current = reopening ? { transform: getComputedStyle(root).transform, opacity: getComputedStyle(root).opacity } : null;
      const token = ++operation;
      cancelAnimations();
      if (!reopening) {
        priorTitle = document.title; document.title = '糖壳暴食兽 · 王丞业作品';
        origin = normalizeOrigin(nextOrigin);
      } else if (nextOrigin) origin = normalizeOrigin(nextOrigin);
      setPhase('opening');
      if (!root.open) root.showModal();
      if (!reopening) {
        viewport.scrollTop = 0;
        root.querySelectorAll('[data-work-reveal]').forEach(node => node.removeAttribute('data-revealed'));
      }
      reveal();
      if (!motionReduced()) {
        animate(root, [current || { transform: sourceTransform(), opacity: .42 }, { transform: 'none', opacity: 1 }], { duration: reopening ? 320 : 590 });
        root.querySelectorAll('.work-detail__frame i').forEach((node, index) => {
          animate(node, [{ transform: index % 2 ? 'scaleY(0)' : 'scaleX(0)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 420, delay: 65 + index * 32 });
        });
        if (!reopening) {
          animate(root.querySelector('.work-detail__bar'), [{ opacity: 0, transform: 'translateY(-7px)' }, { opacity: 1, transform: 'none' }], { duration: 290, delay: 160 });
          animate(root.querySelector('.work-detail__player'), [{ clipPath: 'inset(0 0 100% 0)', transform: 'translateY(8px)' }, { clipPath: 'inset(0 0 0 0)', transform: 'none' }], { duration: 480, delay: 130 });
          ['.work-detail__hero-top', '.work-detail__heading', '.work-detail__meta', '.work-detail__film-caption', '.work-detail__chapters'].forEach((selector, index) => {
            animate(root.querySelector(selector), [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], { duration: 330, delay: 165 + index * 38 });
          });
        }
      }
      transition = Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
        if (token !== operation || disposed) return;
        cancelAnimations(); setPhase('open');
      });
      return transition;
    },
    close() {
      if (disposed || standalone || phase === 'closed' || phase === 'closing') return transition;
      const current = { transform: getComputedStyle(root).transform, opacity: getComputedStyle(root).opacity };
      const token = ++operation;
      cancelAnimations(); video.pause(); setPhase('closing');
      if (!motionReduced()) {
        animate(root.querySelector('.work-detail__viewport'), [{ opacity: 1 }, { opacity: 0 }], { duration: 155, easing: 'ease-out' });
        animate(root.querySelector('.work-detail__bar'), [{ opacity: 1 }, { opacity: 0 }], { duration: 140, easing: 'ease-out' });
        animate(root, [current, { transform: sourceTransform(), opacity: 0 }], { duration: 310, easing: 'cubic-bezier(.55,0,.8,.45)' });
      }
      transition = Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
        if (token === operation && !disposed) finishClose();
      });
      return transition;
    },
    isOpen: () => !disposed && phase !== 'closed',
    getState: () => {
      const bounds = root.getBoundingClientRect();
      return { phase, standalone, nativeOpen: !disposed && (standalone || root.open), isOpen: api.isOpen(), origin: origin && { ...origin }, resolvedOrigin: resolvedOrigin(), bounds: { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height }, scrollTop: standalone ? window.scrollY : viewport.scrollTop, videoPaused: video.paused, videoMuted: video.muted, videoTime: video.currentTime, activeAnimations: animations.length, reducedMotion: motionReduced() };
    },
    dispose() {
      if (disposed) return;
      operation++; cancelAnimations(); video.pause(); observer?.disconnect();
      cleanups.forEach(fn => fn());
      if (!standalone && root.open) { root.close(); if (priorTitle) document.title = priorTitle; }
      disposed = true; setPhase('closed'); root.remove();
    },
  };
  if (standalone) reveal();
  return api;
}
