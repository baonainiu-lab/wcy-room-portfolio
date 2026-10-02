import './scene-callout.scss';
import './resume-entry-labels.scss';

const SVG_NS = 'http://www.w3.org/2000/svg';
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const pixel = value => Math.round(value * 2) / 2;
const COPY = {
  room: { title: '关于我', action: '点击查看', kind: 'about' },
  about: { title: '个人简历', action: '点击翻阅', kind: 'resume' },
};

/** Persistent, object-bound entry cues, separate from the transient hover callout. */
export function createResumeEntryLabels({ THREE, camera, onActivate = () => {} }) {
  const layer = document.createElement('div');
  layer.className = 'scene-callout resume-entry-label';
  layer.dataset.visible = 'false';
  layer.dataset.interactive = 'true';
  layer.setAttribute('aria-hidden', 'true');
  const leader = document.createElementNS(SVG_NS, 'svg');
  leader.classList.add('scene-callout__leader');
  leader.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('vector-effect', 'non-scaling-stroke');
  path.setAttribute('pathLength', '1');
  leader.append(path);
  const marker = document.createElement('button');
  marker.type = 'button';
  marker.className = 'scene-callout__marker';
  marker.tabIndex = -1;
  marker.setAttribute('aria-hidden', 'true');
  marker.append(document.createElement('span'));
  const label = document.createElement('button');
  label.type = 'button';
  label.className = 'scene-callout__label';
  label.tabIndex = -1;
  const title = document.createElement('span');
  title.className = 'scene-callout__title';
  const action = document.createElement('span');
  action.className = 'scene-callout__action';
  label.append(title, action);
  layer.append(leader, marker, label);
  document.body.append(layer);

  const targets = { room: null, about: null };
  const anchors = new WeakMap();
  const box = new THREE.Box3();
  const size = new THREE.Vector3();
  const world = new THREE.Vector3();
  const view = new THREE.Vector3();
  const projected = new THREE.Vector3();
  let activeScene = null;
  let object = null;
  let visible = false;
  let disposed = false;
  let width = window.innerWidth;
  let height = window.innerHeight;
  let screen = null;
  let bounds = null;
  let direction = 'right';
  let lastPath = '';
  let lastLabel = '';
  let lastMarker = '';
  let lastWidth = '';

  const setVisible = next => {
    if (next === visible) return;
    visible = next;
    layer.dataset.visible = String(next);
    layer.setAttribute('aria-hidden', String(!next));
    label.disabled = marker.disabled = !next;
    label.tabIndex = next ? 0 : -1;
  };
  label.disabled = marker.disabled = true;

  const setTargets = (next = {}) => {
    if (disposed) return;
    for (const scene of Object.keys(targets)) {
      if (Object.hasOwn(next, scene)) targets[scene] = next[scene] ?? null;
    }
  };

  const activate = event => {
    event.stopPropagation();
    if (!visible || !object || !COPY[activeScene]) return;
    event.preventDefault();
    onActivate(COPY[activeScene].kind, object);
  };
  const stopScenePointer = event => event.stopPropagation();
  for (const button of [label, marker]) {
    button.addEventListener('click', activate);
    for (const event of ['pointerdown', 'pointerup', 'dblclick']) button.addEventListener(event, stopScenePointer);
  }
  const resize = () => { width = window.innerWidth; height = window.innerHeight; };
  window.addEventListener('resize', resize, { passive: true });

  const anchorFor = node => {
    const cached = anchors.get(node);
    if (cached) return cached;
    node.updateWorldMatrix(true, true);
    // Wait until the entrance has restored the original scale before measuring.
    if (Math.abs(node.matrixWorld.determinant()) < 1e-12) return null;
    box.setFromObject(node);
    const anchor = new THREE.Vector3();
    if (box.isEmpty()) node.getWorldPosition(anchor);
    else {
      box.getCenter(anchor);
      box.getSize(size);
      anchor.y += size.y * .4;
    }
    node.worldToLocal(anchor);
    anchors.set(node, anchor);
    return anchor;
  };

  const update = ({ scene, visible: enabled = true } = {}) => {
    if (disposed) return;
    const nextObject = targets[scene] ?? null;
    if (scene !== activeScene || nextObject !== object) {
      setVisible(false);
      activeScene = scene;
      object = nextObject;
      const copy = COPY[scene];
      if (copy) {
        title.textContent = copy.title;
        action.textContent = copy.action;
        label.setAttribute('aria-label', `${copy.title}，${copy.action}`);
        layer.dataset.kind = copy.kind;
        layer.dataset.scene = scene;
      }
    }
    if (!enabled || !object || !COPY[scene] || width < 240 || height < 240) {
      setVisible(false);
      return;
    }
    const anchor = anchorFor(object);
    if (!anchor) { setVisible(false); return; }
    object.updateWorldMatrix(true, false);
    camera.updateWorldMatrix(true, false);
    world.copy(anchor).applyMatrix4(object.matrixWorld);
    view.copy(world).applyMatrix4(camera.matrixWorldInverse);
    projected.copy(world).project(camera);
    // If the book has left the actual frame, don't point at an unrelated asset.
    if (view.z >= 0 || projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) {
      setVisible(false);
      return;
    }
    const x = pixel((projected.x * .5 + .5) * width);
    const y = pixel((-projected.y * .5 + .5) * height);
    screen = [x, y];
    const compact = width <= 600;
    const inset = compact ? 16 : 28;
    const labelWidth = compact ? 110 : 124;
    const diagonal = compact ? 25 : 34;
    const below = compact ? 32 : 40;
    // Hover callouts live above the object. Keep the permanent entry cue below
    // and to the right; flip only when the screen edge leaves too little room.
    direction = width - x - inset >= labelWidth + diagonal ? 'right' : 'left';
    const labelX = pixel(clamp(direction === 'right' ? x + diagonal : x - diagonal - labelWidth, inset, width - inset - labelWidth));
    const labelY = pixel(clamp(y + below, 76, height - (compact ? 100 : 76)));
    const elbowY = labelY - 4;
    const elbowX = direction === 'right' ? labelX : labelX + labelWidth;
    const lineEnd = direction === 'right' ? labelX + labelWidth : labelX;
    const nextPath = `M${x} ${y} L${elbowX} ${elbowY} L${lineEnd} ${elbowY}`;
    const nextMarker = `translate3d(${x - 22}px,${y - 22}px,0)`;
    const nextLabel = `translate3d(${labelX}px,${labelY}px,0)`;
    if (lastPath !== nextPath) { path.setAttribute('d', nextPath); lastPath = nextPath; }
    if (lastMarker !== nextMarker) { marker.style.transform = nextMarker; lastMarker = nextMarker; }
    if (lastLabel !== nextLabel) { label.style.transform = nextLabel; lastLabel = nextLabel; }
    const nextWidth = `${labelWidth}px`;
    if (lastWidth !== nextWidth) { label.style.width = nextWidth; lastWidth = nextWidth; }
    if (layer.dataset.direction !== direction) layer.dataset.direction = direction;
    bounds = { x: labelX, y: labelY, width: labelWidth, height: 44 };
    setVisible(true);
  };

  const dispose = () => {
    if (disposed) return;
    setVisible(false);
    disposed = true;
    window.removeEventListener('resize', resize);
    for (const button of [label, marker]) {
      button.removeEventListener('click', activate);
      for (const event of ['pointerdown', 'pointerup', 'dblclick']) button.removeEventListener(event, stopScenePointer);
    }
    layer.remove();
  };

  return {
    setTargets,
    update,
    dispose,
    ownsObject: node => Boolean(node && (node === targets.room || node === targets.about)),
    getState: () => ({ visible, scene: activeScene, id: object?.userData.asset_id ?? null,
      title: COPY[activeScene]?.title ?? null, action: COPY[activeScene]?.action ?? null,
      screen, bounds, direction }),
  };
}
