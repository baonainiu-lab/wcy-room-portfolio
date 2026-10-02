/** One-shot entry gesture. The lock remains until completion, so trackpad
 * momentum cannot leak into OrbitControls during the automatic sequence. */
export function bindIntroInput({ view, element, canEnter, onEnter, onSkip }) {
  let touchStart = null, pointerStart = null, disposed = false;
  const options = { capture: true, passive: false };
  const lock = event => { if (event.cancelable) event.preventDefault(); event.stopImmediatePropagation(); };
  const wheel = event => {
    lock(event);
    if (!event.ctrlKey && event.deltaY > 0 && canEnter()) onEnter('wheel');
  };
  const touchstart = event => { touchStart = event.touches.length === 1 ? event.touches[0].clientY : null; };
  const touchmove = event => {
    lock(event);
    if (event.touches.length !== 1) { touchStart = null; return; }
    if (touchStart !== null && touchStart - event.touches[0].clientY > 16 && canEnter()) {
      touchStart = null; onEnter('touch');
    }
  };
  const touchend = () => { touchStart = null; };
  // Also usable with a pointer in a compact viewport, e.g. a tablet pen or
  // desktop's responsive preview. Actual phone touch uses the handlers above.
  const pointerdown = event => {
    pointerStart = event.pointerType !== 'touch' && view.innerWidth <= 700 && event.isPrimary !== false && event.button === 0
      ? { id: event.pointerId, x: event.clientX, y: event.clientY } : null;
  };
  const pointermove = event => {
    if (!pointerStart || pointerStart.id !== event.pointerId) return;
    const dy = pointerStart.y - event.clientY, dx = Math.abs(pointerStart.x - event.clientX);
    if (dy > 24 && dy > dx && canEnter()) { pointerStart = null; onEnter('swipe'); }
  };
  const pointerup = () => { pointerStart = null; };
  const keydown = event => {
    if (event.key === 'Escape') { lock(event); onSkip(); return; }
    if (!['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', ' ', 'Home', 'End'].includes(event.key)) return;
    if (event.target?.closest?.('button') && event.key === ' ') return;
    lock(event);
    if (['ArrowDown', 'PageDown', ' '].includes(event.key) && canEnter()) onEnter('keyboard');
  };
  const listeners = { wheel, touchstart, touchmove, touchend, touchcancel: touchend, keydown };
  for (const [name, handler] of Object.entries(listeners)) view.addEventListener(name, handler, options);
  const pointerListeners = { pointerdown, pointermove, pointerup, pointercancel: pointerup };
  for (const [name, handler] of Object.entries(pointerListeners)) element.addEventListener(name, handler);
  return () => {
    if (disposed) return;
    disposed = true;
    for (const [name, handler] of Object.entries(listeners)) view.removeEventListener(name, handler, options);
    for (const [name, handler] of Object.entries(pointerListeners)) element.removeEventListener(name, handler);
    touchStart = pointerStart = null;
  };
}
