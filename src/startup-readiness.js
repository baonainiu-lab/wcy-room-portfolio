// Progress represents completed preparation stages, not a simulated download.
const STAGES = Object.freeze([
  { id: 'room', weight: 60 }, { id: 'gallery', weight: 18 },
  { id: 'about', weight: 17 }, { id: 'warmup', weight: 5 },
]);

export function createStartupReadiness({ onUpdate = () => {} } = {}) {
  const tasks = new Map(STAGES.map(stage => [stage.id, { ...stage, progress: 0, state: 'pending' }]));
  let ready = false, error = null, current = 'room', message = '正在准备创作空间…';
  const getState = () => ({ ready, error, current, message,
    percent: ready ? 100 : Math.min(99, Math.floor([...tasks.values()].reduce((sum, task) => sum + task.weight * task.progress, 0))),
    stages: [...tasks.values()].map(({ id, progress, state }) => ({ id, progress, state })),
  });
  const emit = () => onUpdate(getState());
  return {
    update(id, progress, text) {
      if (ready || error) return;
      const task = tasks.get(id);
      if (!task) throw new Error(`Unknown startup stage: ${id}`);
      current = id;
      if (Number.isFinite(progress)) task.progress = Math.max(task.progress, Math.min(1, Math.max(0, progress)));
      task.state = task.progress === 1 ? 'ready' : 'loading';
      if (text) message = text;
      emit();
    },
    finish() {
      if (error || [...tasks.values()].some(task => task.progress !== 1)) throw new Error('All scenes and GPU preparation must complete before welcome.');
      ready = true; message = '全部就绪'; emit();
    },
    fail(text) { ready = false; error = text; message = text; emit(); },
    getState,
  };
}

// Render every mesh once behind the opaque loader. Shader compilation alone
// doesn't upload all geometry/textures or allocate native transmission targets.
export async function warmSceneForStartup({ THREE, renderer, scene, camera, setDayMix, restoreMix = 1 }) {
  const visibility = [], textures = new Set();
  const visitTexture = value => {
    if (value?.isTexture && !value.isRenderTargetTexture) textures.add(value);
    else if (Array.isArray(value)) value.forEach(visitTexture);
  };
  scene.traverse(node => {
    if (!node.isMesh) return;
    visibility.push([node, node.frustumCulled]); node.frustumCulled = false;
    for (const material of [].concat(node.material)) {
      Object.values(material).forEach(visitTexture);
      Object.values(material.uniforms ?? {}).forEach(uniform => visitTexture(uniform.value));
    }
  });
  const target = renderer.getRenderTarget(), viewport = new THREE.Vector4(), scissor = new THREE.Vector4();
  const initialSize = renderer.getSize?.(new THREE.Vector2());
  renderer.getViewport(viewport); renderer.getScissor(scissor);
  const scissorTest = renderer.getScissorTest(), autoClear = renderer.autoClear;
  try {
    textures.forEach(texture => renderer.initTexture(texture));
    renderer.setRenderTarget(null); renderer.setScissorTest(false); renderer.autoClear = true;
    for (const mix of [1, 0]) {
      setDayMix?.(mix);
      await renderer.compileAsync(scene, camera);
      renderer.render(scene, camera);
      await new Promise(resolve => requestAnimationFrame(resolve));
    }
  } finally {
    setDayMix?.(restoreMix);
    visibility.forEach(([node, culled]) => { node.frustumCulled = culled; });
    renderer.setRenderTarget(target);
    const currentSize = renderer.getSize?.(new THREE.Vector2());
    if (!target && initialSize && currentSize && !initialSize.equals(currentSize)) {
      renderer.setViewport(0, 0, currentSize.x, currentSize.y);
      renderer.setScissor(0, 0, currentSize.x, currentSize.y);
    } else { renderer.setViewport(viewport); renderer.setScissor(scissor); }
    renderer.setScissorTest(scissorTest); renderer.autoClear = autoClear;
  }
}

export async function waitForStartupGpu(renderer) {
  const gl = renderer.getContext();
  if (!gl.fenceSync) { gl.finish(); return; }
  const fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
  if (!fence) throw new Error('GPU preparation could not create its completion fence.');
  gl.flush();
  try {
    const started = performance.now();
    while (true) {
      const status = gl.clientWaitSync(fence, 0, 0);
      if (status === gl.ALREADY_SIGNALED || status === gl.CONDITION_SATISFIED) return;
      if (status === gl.WAIT_FAILED || gl.isContextLost()) throw new Error('GPU preparation failed; please retry.');
      if (performance.now() - started > 30000) throw new Error('GPU preparation timed out; please retry.');
      await new Promise(resolve => requestAnimationFrame(resolve));
    }
  } finally { gl.deleteSync(fence); }
}
