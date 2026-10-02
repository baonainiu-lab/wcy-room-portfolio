import './gallery-navigation.scss';
import { getGalleryExhibit } from './gallery-catalog.js';

/** Compact controls shared by the six gallery viewpoints. Progress is 0–1, or null. */
export function createGalleryNavigation({ onBack = () => {}, onRetry = () => {}, onSelect = () => {} } = {}) {
  const layer = document.createElement('section');
  layer.className = 'gallery-nav';
  layer.setAttribute('aria-label', '作品场景导航');
  layer.hidden = true;

  const controls = document.createElement('div');
  controls.className = 'gallery-nav__controls';
  const heading = document.createElement('div');
  heading.className = 'gallery-nav__heading';

  const button = (className, label, callback) => {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = `gallery-nav__button ${className}`;
    element.textContent = label;
    element.addEventListener('click', callback);
    return element;
  };

  let state = { active: false, busy: false, loading: false, error: null, progress: null, sceneTitle: '日光长廊', selected: null };
  let disposed = false;
  const back = () => {
    if (!state.busy && !disposed) onBack();
  };
  const caption = document.createElement('div');
  caption.className = 'gallery-nav__caption';
  const title = document.createElement('p');
  title.className = 'gallery-nav__title';
  title.textContent = '日光长廊';
  const note = document.createElement('p');
  note.className = 'gallery-nav__note';
  note.textContent = '游戏 / 三维 / 特效 / AI 产品';
  caption.append(title, note);
  heading.append(caption);

  const bays = document.createElement('nav');
  bays.className = 'gallery-nav__bays';
  bays.setAttribute('aria-label', '选择作品展位');
  const bayButtons = Array.from({ length: 6 }, (_, index) => {
    const number = index + 1;
    const bay = button('gallery-nav__bay', String(number).padStart(2, '0'), () => {
      if (state.active && !state.busy && !state.loading && !disposed) onSelect(number);
    });
    const exhibit = getGalleryExhibit(number);
    const label = exhibit ? `作品 ${String(number).padStart(2, '0')} · ${exhibit.title} · ${exhibit.subtitle}` : `作品展位 ${String(number).padStart(2, '0')} · 资料待补充`;
    bay.setAttribute('aria-label', label);
    bay.title = label;
    bay.dataset.content = exhibit ? 'available' : 'pending';
    bay.dataset.bay = String(number);
    bays.append(bay);
    return bay;
  });
  controls.append(heading, bays);

  const status = document.createElement('div');
  status.className = 'gallery-nav__status';
  const statusText = document.createElement('p');
  statusText.className = 'gallery-nav__status-text';
  const announcement = document.createElement('p');
  announcement.className = 'gallery-nav__announcement';
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', 'polite');
  announcement.setAttribute('aria-atomic', 'true');
  const meter = document.createElement('progress');
  meter.className = 'gallery-nav__progress';
  meter.max = 1;
  meter.setAttribute('aria-label', '作品展厅加载进度');
  const errorActions = document.createElement('div');
  errorActions.className = 'gallery-nav__error-actions';
  const retryButton = button('gallery-nav__retry', '重新加载', () => {
    if (!state.busy && !state.loading && state.error && !disposed) onRetry();
  });
  const stayButton = button('gallery-nav__stay', '留在房间', back);
  errorActions.append(retryButton, stayButton);
  status.append(statusText, meter, errorActions);
  layer.append(controls, status, announcement);
  document.body.append(layer);

  // A click on the floating controls must not also pick a mesh underneath them.
  const stopScenePointer = (event) => event.stopPropagation();
  for (const type of ['pointerdown', 'pointerup', 'click', 'dblclick']) {
    layer.addEventListener(type, stopScenePointer);
  }

  const setState = (next = {}) => {
    if (disposed) return;
    state = { ...state, ...next };
    title.textContent = state.sceneTitle;
    const selected = getGalleryExhibit(state.selected);
    note.textContent = selected ? `${String(selected.index).padStart(2, '0')} · ${selected.short || selected.title}` : '游戏 / 三维 / 特效 / AI 产品';
    bayButtons.forEach(bay => {
      if (Number(bay.dataset.bay) === state.selected) bay.setAttribute('aria-current', 'true');
      else bay.removeAttribute('aria-current');
    });
    layer.setAttribute('aria-label', `${state.sceneTitle}场景导航`);
    meter.setAttribute('aria-label', `${state.sceneTitle}加载进度`);
    const active = Boolean(state.active);
    const loading = Boolean(state.loading);
    const busy = Boolean(state.busy);
    const error = Boolean(state.error) && !loading;
    const progress = typeof state.progress === 'number' && Number.isFinite(state.progress)
      ? Math.min(1, Math.max(0, state.progress))
      : null;

    layer.hidden = !(active || loading || busy || error);
    layer.dataset.state = error ? 'error' : loading ? 'loading' : busy ? 'busy' : 'ready';
    controls.hidden = !active;
    controls.setAttribute('aria-busy', String(busy));
    bayButtons.forEach((bay) => { bay.disabled = busy || loading; });

    // Camera travel is announced without placing a status pill over the scene.
    status.hidden = !(loading || error);
    meter.hidden = !loading;
    errorActions.hidden = !error;
    retryButton.disabled = busy || loading;
    stayButton.disabled = busy;
    if (progress === null) meter.removeAttribute('value');
    else meter.value = progress;

    // Announce stages, not every percentage update. The progress element exposes
    // the exact value without making assistive technology speak on each packet.
    const message = error
      ? state.error
      : loading
        ? `正在准备${state.sceneTitle}`
        : busy
          ? '正在切换视角'
          : '';
    const visibleMessage = loading || error ? message : '';
    if (statusText.textContent !== visibleMessage) statusText.textContent = visibleMessage;
    if (announcement.textContent !== message) announcement.textContent = message;
    if (loading && progress !== null) {
      meter.setAttribute('aria-valuetext', `${Math.round(progress * 100)}%`);
      status.dataset.progress = `${Math.round(progress * 100)}%`;
    } else {
      meter.removeAttribute('aria-valuetext');
      delete status.dataset.progress;
    }
  };

  const dispose = () => {
    if (disposed) return;
    disposed = true;
    layer.remove();
  };

  setState();
  return { setState, dispose };
}
