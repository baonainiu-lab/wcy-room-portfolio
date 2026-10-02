import './exhibit-detail.scss';

const text = value => value == null ? '' : String(value);
const number = value => String(value ?? '').padStart(2, '0');
const node = (tag, className, content) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined) element.textContent = text(content);
  return element;
};
const safeURL = value => {
  if (!value) return '';
  try {
    const url = new URL(text(value), document.baseURI);
    return ['http:', 'https:', 'blob:'].includes(url.protocol) ? url.href : '';
  } catch { return ''; }
};
const normalizeOrigin = value => value && ['x', 'y', 'width', 'height'].every(key => Number.isFinite(value[key])) && value.width > 0 && value.height > 0 ? { x: value.x, y: value.y, width: value.width, height: value.height } : null;
let detailSequence = 0;

/** A single bounded exhibit. Only the selected project's selected media is requested. */
export function createExhibitDetail({ reducedMotion = false, onClose = () => {}, onPlaybackChange = () => {} } = {}) {
  const id = `exhibit-detail-${++detailSequence}`;
  const root = node('dialog', 'exhibit-detail');
  root.setAttribute('aria-labelledby', `${id}-title`);
  root.setAttribute('aria-modal', 'true');
  root.dataset.phase = 'closed';
  // This skeleton is constant; all incoming project content is assigned with textContent.
  root.innerHTML = `
    <div class="exhibit-detail__frame" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
    <header class="exhibit-detail__bar"><button type="button" class="exhibit-detail__back" data-exhibit-close autofocus>← 返回长廊</button><span class="exhibit-detail__archive"></span><span class="exhibit-detail__count"></span></header>
    <div class="exhibit-detail__scroll">
      <section class="exhibit-detail__intro"><div><p class="exhibit-detail__eyebrow"></p><h1 id="${id}-title"></h1></div><div class="exhibit-detail__summary"><p class="exhibit-detail__subtitle"></p><p class="exhibit-detail__description"></p></div></section>
      <nav class="exhibit-detail__projects" aria-label="本展位项目"></nav>
      <article class="exhibit-detail__project" aria-labelledby="${id}-project">
        <section class="exhibit-detail__visual" aria-label="项目图像与视频"><div class="exhibit-detail__media"></div><div class="exhibit-detail__media-foot"><p class="exhibit-detail__caption"></p><a class="exhibit-detail__download" hidden download>下载原片 ↗</a><span class="exhibit-detail__media-count"></span></div><nav class="exhibit-detail__media-nav" aria-label="切换作品细节"></nav></section>
        <div class="exhibit-detail__copy"><p class="exhibit-detail__kicker"></p><h2 id="${id}-project" tabindex="-1"></h2><p class="exhibit-detail__project-description"></p><ul class="exhibit-detail__tools" aria-label="制作工具与技术"></ul><dl class="exhibit-detail__facts"></dl><aside class="exhibit-detail__note"></aside></div>
      </article>
      <footer class="exhibit-detail__footer"><p class="exhibit-detail__tags"></p><button type="button" data-exhibit-close>继续逛长廊 <span aria-hidden="true">↗</span></button></footer>
    </div><p class="exhibit-detail__status" role="status" aria-live="polite"></p>`;
  document.body.append(root);
  const find = selector => root.querySelector(selector);
  const scroll = find('.exhibit-detail__scroll');
  const mediaRoot = find('.exhibit-detail__media');
  const project = find('.exhibit-detail__project');
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const motionReduced = () => reducedMotion || motionPreference.matches;
  const cleanup = [];
  const listen = (target, event, fn) => { target.addEventListener(event, fn); cleanup.push(() => target.removeEventListener(event, fn)); };
  let phase = 'closed', disposed = false, origin = null, exhibit = null, itemIndex = 0, mediaIndex = 0;
  let media = [], video = null, image = null, mediaError = false, priorTitle, priorFocus;
  let operation = 0, animations = [], itemAnimations = [], transition = Promise.resolve();
  const setPhase = value => { phase = value; root.dataset.phase = value; };
  const cancel = list => { list.forEach(animation => animation.cancel()); list.length = 0; };
  const animate = (target, frames, options, list = animations) => {
    if (!target?.animate || motionReduced()) return;
    const animation = target.animate(frames, { fill: 'both', easing: 'cubic-bezier(.22,1,.36,1)', ...options });
    animation.finished.catch(() => {}); list.push(animation);
  };
  const resolvedOrigin = () => {
    if (!origin) return null;
    const width = Math.min(origin.width, Math.max(1, innerWidth - 16)), height = Math.min(origin.height, Math.max(1, innerHeight - 16));
    return { width, height, x: Math.max(8, Math.min(origin.x, innerWidth - width - 8)), y: Math.max(8, Math.min(origin.y, innerHeight - height - 8)) };
  };
  const sourceTransform = () => {
    const source = resolvedOrigin(), width = root.offsetWidth, height = root.offsetHeight;
    if (!source || !width || !height) return 'translateY(20px) scale(.94)';
    return `translate(${source.x + source.width / 2 - root.offsetLeft - width / 2}px,${source.y + source.height / 2 - root.offsetTop - height / 2}px) scale(${source.width / width},${source.height / height})`;
  };
  const pauseVideo = () => { video?.pause(); onPlaybackChange(false); };
  const releaseMedia = () => {
    const previous = video;
    video = null; image = null;
    if (previous) { previous.pause(); previous.removeAttribute('src'); previous.load(); }
    onPlaybackChange(false); mediaRoot.replaceChildren();
  };
  const setText = (selector, value) => { find(selector).textContent = text(value); };
  const currentItem = () => exhibit?.items?.[itemIndex];
  const selectButtons = (selector, selected) => root.querySelectorAll(selector).forEach((button, index) => {
    button.setAttribute('aria-pressed', index === selected ? 'true' : 'false');
    if (index === selected) button.setAttribute('aria-current', 'true'); else button.removeAttribute('aria-current');
  });
  const errorPanel = (message, retry, downloadURL) => {
    const panel = node('div', 'exhibit-detail__media-error');
    panel.setAttribute('role', 'status'); panel.append(node('span', '', '—'), node('p', '', message));
    const button = node('button', '', '重新加载'); button.type = 'button'; button.addEventListener('click', retry); panel.append(button);
    if (downloadURL) { const link = node('a', '', '下载原片 ↗'); link.href = downloadURL; link.download = ''; panel.append(link); }
    return panel;
  };
  const showMedia = (index, announce = false) => {
    if (!media[index]) return;
    releaseMedia(); mediaIndex = index; mediaError = false;
    const entry = media[index];
    mediaRoot.dataset.kind = entry.kind;
    setText('.exhibit-detail__caption', entry.caption || entry.alt || currentItem()?.title);
    setText('.exhibit-detail__media-count', `${number(index + 1)} / ${number(media.length)}`);
    selectButtons('[data-exhibit-media]', index);
    const download = find('.exhibit-detail__download');
    download.hidden = entry.kind !== 'video';
    if (entry.kind === 'video') download.href = entry.src; else download.removeAttribute('href');
    if (entry.kind === 'video') {
      const player = node('video');
      video = player; player.controls = true; player.playsInline = true; player.muted = true; player.defaultMuted = true; player.preload = 'none';
      player.setAttribute('aria-label', entry.alt || `${currentItem().title}视频`);
      if (entry.poster) player.poster = entry.poster;
      player.src = entry.src;
      const play = node('button', 'exhibit-detail__play', '▶ 播放作品演示'); play.type = 'button';
      const start = () => {
        if (video !== player) return;
        player.play().catch(reason => { if (video === player && reason.name !== 'AbortError') { if (player.error) showError(); else play.hidden = false; } });
      };
      const showError = () => {
        if (video !== player || mediaError) return;
        mediaError = true; play.hidden = true; onPlaybackChange(false);
        mediaRoot.append(errorPanel('视频暂时无法播放，可以重新加载或下载原片。', () => { showMedia(index); video?.load(); }, entry.src));
      };
      play.addEventListener('click', start);
      player.addEventListener('play', () => { if (video === player) { play.hidden = true; onPlaybackChange(true); } });
      player.addEventListener('pause', () => { if (video === player) { onPlaybackChange(false); if (!player.ended && !mediaError) play.hidden = false; } });
      player.addEventListener('ended', () => { if (video === player) { play.hidden = false; onPlaybackChange(false); } });
      player.addEventListener('error', showError);
      mediaRoot.append(player, play);
    } else {
      const photo = node('img'); image = photo; photo.alt = entry.alt || currentItem().title; photo.decoding = 'async'; photo.draggable = false;
      photo.addEventListener('error', () => {
        if (image !== photo) return;
        mediaError = true; photo.hidden = true;
        mediaRoot.append(errorPanel('这张作品图片暂时无法加载。', () => showMedia(index)));
      }, { once: true });
      photo.src = entry.src; mediaRoot.append(photo);
    }
    if (announce) setText('.exhibit-detail__status', `${currentItem().title}，${entry.kind === 'video' ? '视频' : '图片'} ${index + 1} / ${media.length}`);
  };
  const buildMedia = item => {
    const result = [], seen = new Set();
    const addImage = entry => {
      const src = safeURL(entry.src);
      if (!src || seen.has(src)) return;
      seen.add(src); result.push({ kind: 'image', ...entry, src });
    };
    const film = typeof item.video === 'string' ? { src: item.video } : item.video;
    if (safeURL(film?.src)) result.push({ kind: 'video', src: safeURL(film.src), poster: safeURL(film.poster || item.image || exhibit.cover), alt: item.title + ' · 作品演示', caption: film.caption || '作品视频 · 点击播放' });
    // Keep the still render available for close inspection after playing a film.
    addImage({ src: item.image || exhibit.cover, alt: item.imageAlt || exhibit.coverAlt || item.title, caption: item.imageAlt || item.title });
    (item.gallery || []).forEach(entry => addImage(entry));
    return result;
  };
  const selectItem = (index, { animateChange = true, focus = false } = {}) => {
    if (!exhibit?.items?.[index]) return;
    cancel(itemAnimations); itemIndex = index;
    const item = currentItem();
    selectButtons('[data-exhibit-item]', index);
    setText('.exhibit-detail__count', `${number(index + 1)} / ${number(exhibit.items.length)} 项目`);
    setText('.exhibit-detail__kicker', item.kicker || `${number(index + 1)} / ${number(exhibit.items.length)}`);
    setText(`#${id}-project`, item.title);
    setText('.exhibit-detail__project-description', item.description);
    const tools = find('.exhibit-detail__tools'); tools.replaceChildren(...(item.tools || []).map(tool => node('li', '', tool))); tools.hidden = !tools.children.length;
    const facts = find('.exhibit-detail__facts'); facts.replaceChildren();
    (item.facts || []).forEach(fact => { const pair = node('div'); pair.append(node('dt', '', fact.label), node('dd', '', fact.value)); facts.append(pair); });
    facts.hidden = !facts.children.length;
    const note = find('.exhibit-detail__note'); note.replaceChildren(); note.hidden = !item.note;
    if (item.note) note.append(node('span', '', '制作说明'), node('p', '', item.note));
    media = buildMedia(item); mediaIndex = 0; mediaError = false;
    const mediaNav = find('.exhibit-detail__media-nav'); mediaNav.replaceChildren();
    media.forEach((entry, mediaPosition) => {
      const button = node('button'); button.type = 'button'; button.dataset.exhibitMedia = mediaPosition;
      button.append(node('span', '', entry.kind === 'video' ? '▶' : number(mediaPosition + 1)), node('span', '', entry.kind === 'video' ? '作品演示' : entry.caption || `细节 ${mediaPosition + 1}`));
      button.setAttribute('aria-label', entry.kind === 'video' ? '查看作品视频' : `查看图片 ${mediaPosition + 1}：${entry.caption || entry.alt || item.title}`);
      mediaNav.append(button);
    });
    mediaNav.hidden = media.length < 2;
    if (media.length) showMedia(0); else { releaseMedia(); mediaRoot.append(node('p', 'exhibit-detail__empty', '作品素材待补充')); setText('.exhibit-detail__caption', '作品素材待补充'); setText('.exhibit-detail__media-count', ''); }
    if (animateChange && phase !== 'closed') {
      animate(project, [{ opacity: .45, transform: 'translateY(9px)' }, { opacity: 1, transform: 'none' }], { duration: 270 }, itemAnimations);
      const current = [...itemAnimations];
      Promise.allSettled(current.map(animation => animation.finished)).then(() => { current.forEach(animation => animation.cancel()); itemAnimations = itemAnimations.filter(animation => !current.includes(animation)); });
      const nav = find('.exhibit-detail__projects');
      if (scroll.scrollTop > nav.offsetTop) scroll.scrollTop = Math.max(0, nav.offsetTop - 16);
    }
    setText('.exhibit-detail__status', `${item.title}，项目 ${index + 1} / ${exhibit.items.length}`);
    if (focus) find(`#${id}-project`).focus({ preventScroll: true });
  };
  const populate = nextExhibit => {
    exhibit = nextExhibit;
    setText('.exhibit-detail__archive', `SELECTED WORK ／ ${number(exhibit.index)}`);
    setText('.exhibit-detail__eyebrow', exhibit.eyebrow || `EXHIBIT ${number(exhibit.index)}`);
    setText(`#${id}-title`, exhibit.title);
    setText('.exhibit-detail__subtitle', exhibit.subtitle);
    setText('.exhibit-detail__description', exhibit.description);
    setText('.exhibit-detail__tags', (exhibit.tags || []).join(' · '));
    const projects = find('.exhibit-detail__projects'); projects.replaceChildren();
    (exhibit.items || []).forEach((item, index) => {
      const button = node('button'); button.type = 'button'; button.dataset.exhibitItem = index;
      button.append(node('span', '', number(index + 1)), node('strong', '', item.title)); projects.append(button);
    });
    projects.hidden = exhibit.items.length < 2;
    selectItem(0, { animateChange: false });
    scroll.scrollTop = 0;
  };
  const finishClose = () => {
    if (phase === 'closed' || disposed) return;
    cancel(animations); cancel(itemAnimations); releaseMedia(); setPhase('closed');
    if (root.open) root.close();
    if (priorTitle !== undefined) document.title = priorTitle;
    priorTitle = undefined;
    if (priorFocus?.isConnected) priorFocus.focus({ preventScroll: true });
    priorFocus = null; onClose();
  };
  const api = {
    open({ exhibit: nextExhibit, origin: nextOrigin } = {}) {
      if (disposed) return Promise.resolve();
      if (!nextExhibit?.items?.length) return Promise.reject(new Error('Exhibit requires at least one item.'));
      if ((phase === 'open' || phase === 'opening') && exhibit === nextExhibit) return transition;
      const wasActive = phase !== 'closed', reopening = phase === 'closing';
      const current = wasActive ? { opacity: getComputedStyle(root).opacity, transform: getComputedStyle(root).transform } : null;
      const token = ++operation;
      cancel(animations); cancel(itemAnimations);
      if (!wasActive) { priorTitle = document.title; priorFocus = document.activeElement; }
      origin = normalizeOrigin(nextOrigin) || (wasActive ? origin : null);
      populate(nextExhibit); document.title = `${exhibit.title} · 王丞业作品`;
      setPhase('opening'); if (!root.open) root.showModal();
      // A hidden dialog has no scroll geometry; reset after showModal as well.
      scroll.scrollTop = 0;
      animate(root, [current || { opacity: .38, transform: sourceTransform() }, { opacity: 1, transform: 'none' }], { duration: wasActive ? 300 : 590 });
      if (!wasActive || !reopening) {
        root.querySelectorAll('.exhibit-detail__frame i').forEach((line, index) => animate(line, [{ opacity: 0, transform: index % 2 ? 'scaleY(0)' : 'scaleX(0)' }, { opacity: 1, transform: 'none' }], { duration: 380, delay: 60 + index * 35 }));
        ['.exhibit-detail__bar', '.exhibit-detail__intro', '.exhibit-detail__projects', '.exhibit-detail__visual', '.exhibit-detail__copy'].forEach((selector, index) => animate(find(selector), [{ opacity: 0, transform: 'translateY(13px)' }, { opacity: 1, transform: 'none' }], { duration: 330, delay: 100 + index * 45 }));
      }
      transition = Promise.allSettled(animations.map(animation => animation.finished)).then(() => { if (token !== operation || disposed) return; cancel(animations); setPhase('open'); });
      return transition;
    },
    close() {
      if (disposed || phase === 'closed' || phase === 'closing') return transition;
      const token = ++operation, current = { opacity: getComputedStyle(root).opacity, transform: getComputedStyle(root).transform };
      cancel(animations); cancel(itemAnimations); pauseVideo(); setPhase('closing');
      animate(scroll, [{ opacity: 1 }, { opacity: 0 }], { duration: 145, easing: 'ease-out' });
      animate(root, [current, { opacity: 0, transform: sourceTransform() }], { duration: 330, easing: 'cubic-bezier(.55,0,.8,.45)' });
      transition = Promise.allSettled(animations.map(animation => animation.finished)).then(() => { if (token === operation && !disposed) finishClose(); });
      return transition;
    },
    isOpen: () => !disposed && phase !== 'closed',
    getState() {
      const bounds = root.getBoundingClientRect();
      return { index: exhibit?.index ?? null, slug: exhibit?.slug ?? null, itemCount: exhibit?.items?.length || 0, itemId: currentItem()?.id ?? null, itemIndex, phase, nativeOpen: root.open, mediaIndex, mediaCount: media.length, mediaKind: media[mediaIndex]?.kind ?? null, mediaError, videoPaused: video?.paused ?? true, videoMuted: video?.muted ?? true, videoTime: video?.currentTime ?? 0, imageLoaded: !!(image?.complete && image?.naturalWidth), origin, resolvedOrigin: resolvedOrigin(), bounds: { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height }, scrollTop: scroll.scrollTop, activeAnimations: animations.length + itemAnimations.length, reducedMotion: motionReduced() };
    },
    dispose() {
      if (disposed) return;
      operation++; cancel(animations); cancel(itemAnimations); releaseMedia(); cleanup.forEach(fn => fn());
      if (root.open) root.close();
      if (priorTitle !== undefined) document.title = priorTitle;
      disposed = true; setPhase('closed'); root.remove();
    },
  };
  listen(root, 'click', event => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest('[data-exhibit-close]')) { api.close(); return; }
    if (!['open', 'opening'].includes(phase)) return;
    const item = event.target.closest('[data-exhibit-item]');
    if (item && Number(item.dataset.exhibitItem) !== itemIndex) selectItem(Number(item.dataset.exhibitItem));
    const mediaButton = event.target.closest('[data-exhibit-media]');
    if (mediaButton && Number(mediaButton.dataset.exhibitMedia) !== mediaIndex) showMedia(Number(mediaButton.dataset.exhibitMedia), true);
  });
  listen(root, 'keydown', event => event.stopPropagation());
  listen(root, 'cancel', event => { event.preventDefault(); api.close(); });
  listen(root, 'close', () => { if (!root.open && phase !== 'closed') { operation++; finishClose(); } });
  listen(document, 'visibilitychange', () => { if (document.hidden) pauseVideo(); });
  const finishMotion = () => [...animations, ...itemAnimations].forEach(animation => { try { animation.finish(); } catch { /* Canceled between resize and this callback. */ } });
  listen(window, 'resize', finishMotion);
  listen(motionPreference, 'change', () => { if (motionReduced()) finishMotion(); });
  return api;
}
