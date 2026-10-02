import './scene-callout.scss';

const SVG_NS = 'http://www.w3.org/2000/svg';
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const pixel = (value) => Math.round(value * 2) / 2;

/** A single, object-anchored annotation. Geometry is measured only on first use. */
export function createSceneCallout({ THREE, camera, onActivate = () => {} }) {
  const layer = document.createElement('div');
  layer.className = 'scene-callout';
  layer.dataset.visible = 'false';
  layer.dataset.interactive = 'false';
  layer.setAttribute('aria-hidden', 'true');

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.classList.add('scene-callout__leader');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('vector-effect', 'non-scaling-stroke');
  path.setAttribute('pathLength', '1');
  svg.append(path);

  const marker = document.createElement('button');
  marker.type = 'button';
  marker.className = 'scene-callout__marker';
  marker.tabIndex = -1;
  marker.setAttribute('aria-hidden', 'true');
  const dot = document.createElement('span');
  marker.append(dot);

  const labelButton = document.createElement('button');
  labelButton.type = 'button';
  labelButton.className = 'scene-callout__label';
  labelButton.tabIndex = -1;
  const title = document.createElement('span');
  title.className = 'scene-callout__title';
  const action = document.createElement('span');
  action.className = 'scene-callout__action';
  labelButton.append(title, action);
  layer.append(svg, marker, labelButton);
  document.body.append(layer);

  const anchors = new WeakMap();
  const box = new THREE.Box3();
  const size = new THREE.Vector3();
  const right = new THREE.Vector3();
  const world = new THREE.Vector3();
  const view = new THREE.Vector3();
  const projected = new THREE.Vector3();
  let target = null;
  let localAnchor = null;
  let width = window.innerWidth;
  let height = window.innerHeight;
  let visible = false;
  let disposed = false;
  let labelWidth = 64;
  let screenX = null;
  let screenY = null;
  let direction = 'left';
  let lastPath = '';
  let lastMarkerTransform = '';
  let lastLabelTransform = '';
  let lastLabelWidth = '';

  const syncAccessibility = () => {
    const enabled = visible && Boolean(target?.interactive);
    marker.disabled = !enabled;
    labelButton.disabled = !enabled;
    labelButton.tabIndex = enabled ? 0 : -1;
  };

  const setVisible = (next) => {
    if (next === visible) return;
    visible = next;
    layer.dataset.visible = String(next);
    layer.setAttribute('aria-hidden', String(!next));
    syncAccessibility();
  };

  const resize = () => {
    width = window.innerWidth;
    height = window.innerHeight;
  };
  window.addEventListener('resize', resize, { passive: true });

  const activate = (event) => {
    if (!visible || !target?.interactive) return;
    event.preventDefault();
    event.stopPropagation();
    onActivate(target.kind);
  };
  marker.addEventListener('click', activate);
  labelButton.addEventListener('click', activate);

  const anchorFor = (object) => {
    const cached = anchors.get(object);
    if (cached) return cached;
    object.updateWorldMatrix(true, true);
    // Entry animations briefly collapse roots to zero scale. Measure after that settles.
    if (Math.abs(object.matrixWorld.determinant()) < 1e-12) return null;
    box.setFromObject(object);
    const anchor = new THREE.Vector3();
    if (box.isEmpty()) {
      object.getWorldPosition(anchor);
    } else {
      box.getCenter(anchor);
      box.getSize(size);
      if (object.userData.asset_id === 'main_display') {
        camera.updateWorldMatrix(true, false);
        right.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
        const screenExtent = Math.abs(right.x) * size.x + Math.abs(right.y) * size.y + Math.abs(right.z) * size.z;
        anchor.addScaledVector(right, -screenExtent * 0.2);
        anchor.y += size.y * 0.15;
      } else {
        anchor.y += size.y * 0.16;
      }
    }
    object.worldToLocal(anchor);
    anchors.set(object, anchor);
    return anchor;
  };

  const clear = () => {
    target = null;
    localAnchor = null;
    screenX = null;
    screenY = null;
    setVisible(false);
    syncAccessibility();
  };

  const setTarget = (next) => {
    if (disposed) return;
    if (!next?.object) {
      clear();
      return;
    }
    const nextLabel = String(next.label ?? '');
    const nextAction = String(next.action ?? '');
    const interactive = Boolean(next.interactive);
    if (target?.object === next.object && target.label === nextLabel && target.action === nextAction && target.kind === next.kind && target.interactive === interactive) return;

    const objectChanged = target?.object !== next.object;
    target = { object: next.object, label: nextLabel, action: nextAction, kind: next.kind, interactive };
    if (objectChanged) localAnchor = anchors.get(next.object) ?? null;
    if (title.textContent !== nextLabel) title.textContent = nextLabel;
    if (action.textContent !== nextAction) action.textContent = nextAction;
    action.hidden = !nextAction;
    labelButton.setAttribute('aria-label', nextAction ? `${nextLabel}，${nextAction}` : nextLabel);
    layer.dataset.interactive = String(interactive);
    layer.dataset.kind = next.kind ?? '';
    // The fixed line box avoids layout reads while still allowing long labels to truncate.
    const estimatedWidth = (text, chinese, latin) => Array.from(text).reduce((total, character) => total + (/[^\u0000-\u00ff]/.test(character) ? chinese : latin), 0);
    labelWidth = clamp(Math.max(estimatedWidth(nextLabel, 14, 8), estimatedWidth(nextAction, 11, 6)) + 8, 64, 204);
    syncAccessibility();
  };

  const update = ({ visible: requested = true } = {}) => {
    if (disposed) return;
    if (!requested || !target || width < 240 || height < 300) {
      setVisible(false);
      return;
    }

    if (!localAnchor) localAnchor = anchorFor(target.object);
    if (!localAnchor) {
      setVisible(false);
      return;
    }

    target.object.updateWorldMatrix(true, false);
    camera.updateWorldMatrix(true, false);
    world.copy(localAnchor).applyMatrix4(target.object.matrixWorld);
    view.copy(world).applyMatrix4(camera.matrixWorldInverse);
    projected.copy(world).project(camera);
    if (view.z >= 0 || projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) {
      setVisible(false);
      return;
    }

    screenX = pixel((projected.x * 0.5 + 0.5) * width);
    screenY = pixel((-projected.y * 0.5 + 0.5) * height);
    const compact = width <= 600;
    const inset = compact ? 18 : 28;
    const diagonal = compact ? 30 : 42;
    const top = compact ? 124 : 112;
    const bottom = compact ? 162 : 134;
    const availableLeft = screenX - inset - diagonal;
    const availableRight = width - inset - screenX - diagonal;
    const nextDirection = availableLeft >= labelWidth || availableLeft >= availableRight ? 'left' : 'right';
    const available = nextDirection === 'left' ? availableLeft : availableRight;
    const textWidth = pixel(Math.min(labelWidth, Math.max(48, available)));
    const elbowY = pixel(clamp(screenY - (compact ? 44 : 50), top + 44, Math.max(top + 44, height - bottom)));
    const elbowX = pixel(screenX + (nextDirection === 'left' ? -diagonal : diagonal));
    const labelX = pixel(clamp(nextDirection === 'left' ? elbowX - textWidth : elbowX, inset, width - inset - textWidth));
    const lineEnd = nextDirection === 'left' ? labelX : labelX + textWidth;
    const nextPath = `M${screenX} ${screenY} L${elbowX} ${elbowY} L${lineEnd} ${elbowY}`;
    const markerTransform = `translate3d(${screenX - 22}px,${screenY - 22}px,0)`;
    const labelTransform = `translate3d(${labelX}px,${elbowY - 48}px,0)`;
    const nextWidth = `${textWidth}px`;

    if (nextPath !== lastPath) {
      path.setAttribute('d', nextPath);
      lastPath = nextPath;
    }
    if (markerTransform !== lastMarkerTransform) {
      marker.style.transform = markerTransform;
      lastMarkerTransform = markerTransform;
    }
    if (labelTransform !== lastLabelTransform) {
      labelButton.style.transform = labelTransform;
      lastLabelTransform = labelTransform;
    }
    if (nextWidth !== lastLabelWidth) {
      labelButton.style.width = nextWidth;
      lastLabelWidth = nextWidth;
    }
    if (nextDirection !== direction) {
      direction = nextDirection;
      layer.dataset.direction = direction;
    }
    setVisible(true);
  };

  const dispose = () => {
    if (disposed) return;
    clear();
    disposed = true;
    window.removeEventListener('resize', resize);
    marker.removeEventListener('click', activate);
    labelButton.removeEventListener('click', activate);
    layer.remove();
  };

  return {
    setTarget,
    update,
    clear,
    dispose,
    getState: () => ({ visible, interactive: Boolean(target?.interactive), id: target?.object.userData.asset_id ?? null, kind: target?.kind ?? null, label: target?.label ?? null, action: target?.action ?? null, screen: screenX === null ? null : [screenX, screenY], direction }),
  };
}
