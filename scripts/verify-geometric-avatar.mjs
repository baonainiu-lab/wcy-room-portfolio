import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from '/Users/a90/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';

// Run against the actual local V8 room. This checks user events and real scene
// transforms; the headless browser's cadence is not a 120 Hz performance test.
const baseURL = process.env.AVATAR_PREVIEW_URL || 'http://127.0.0.1:5180/';
const outputDir = path.resolve('renders/avatar-geometric');
await fs.mkdir(outputDir, { recursive: true });
const report = { url: baseURL, timestamp: new Date().toISOString(), checks: [], scenarios: {}, performanceCaveat: 'Headless browser cadence is diagnostic only; it does not verify a 120 FPS target on a 120 Hz display.' };
const browser = await chromium.launch({
  headless: true,
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args: ['--enable-webgl', '--ignore-gpu-blocklist'],
});

function assert(condition, message) { if (!condition) throw new Error(message); }
async function check(name, task) {
  try { const details = await task(); report.checks.push({ name, passed: true, details }); console.log(`PASS ${name}`); }
  catch (error) { report.checks.push({ name, passed: false, error: String(error) }); console.error(`FAIL ${name}: ${error}`); }
}
async function scenario(name, options = {}, blockedAvatar = false) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const log = report.scenarios[name] = { pageErrors: [], consoleErrors: [], failedRequests: [], badResponses: [], warnings: [] };
  page.on('pageerror', error => log.pageErrors.push(String(error)));
  page.on('console', message => {
    if (message.type() === 'error') log.consoleErrors.push(message.text());
    if (message.type() === 'warning') log.warnings.push(message.text());
  });
  page.on('requestfailed', request => log.failedRequests.push({ url: request.url(), error: request.failure()?.errorText, expected: blockedAvatar && request.url().includes('/models/avatar/geometric-creator-v1.glb') }));
  page.on('response', response => { if (response.status() >= 400) log.badResponses.push({ url: response.url(), status: response.status() }); });
  if (blockedAvatar) await page.route('**/models/avatar/geometric-creator-v1.glb', route => route.abort('failed'));
  await page.goto(baseURL, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__roomPreview?.getState().loaded, null, { timeout: 90000 });
  await page.locator('.loading-screen-button').click();
  await page.waitForFunction(() => window.__roomPreview.getState().introComplete && window.__roomPreview.getState().controlsEnabled, null, { timeout: 30000 });
  await page.waitForFunction(expected => window.__roomPreview.getAvatarState().loadStatus === expected, blockedAvatar ? 'failed' : 'ready', { timeout: 60000 });
  if (!blockedAvatar) await page.waitForFunction(() => !window.__roomPreview.getAvatarState().waving, null, { timeout: 15000 });
  log.initial = await getState(page);
  return { page, context, log };
}
async function getState(page) { return page.evaluate(() => ({ room: window.__roomPreview.getState(), avatar: window.__roomPreview.getAvatarState() })); }
async function closePanel(page) {
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !window.__roomPreview.getState().modal && window.__roomPreview.getState().controlsEnabled);
}
async function screenshot(page, name) { await page.screenshot({ path: path.join(outputDir, `web-${name}.png`) }); }
async function actualAvatarPixel(page, action) {
  return page.evaluate(async action => {
    const T = await import('/node_modules/three/build/three.module.js');
    const d = window.__roomPreview;
    d.scene.updateMatrixWorld(true); d.camera.updateMatrixWorld(true);
    const roomMeshes = []; d.room.traverse(node => { if (node.isMesh) roomMeshes.push(node); });
    const bounds = new T.Box3().setFromObject(d.avatar.root);
    const projected = [];
    for (let i = 0; i < 8; i++) projected.push(new T.Vector3(i & 1 ? bounds.max.x : bounds.min.x, i & 2 ? bounds.max.y : bounds.min.y, i & 4 ? bounds.max.z : bounds.min.z).project(d.camera));
    const minX = Math.max(0, Math.floor((Math.min(...projected.map(v => v.x)) + 1) * innerWidth / 2));
    const maxX = Math.min(innerWidth - 1, Math.ceil((Math.max(...projected.map(v => v.x)) + 1) * innerWidth / 2));
    const minY = Math.max(0, Math.floor((1 - Math.max(...projected.map(v => v.y))) * innerHeight / 2));
    const maxY = Math.min(innerHeight - 1, Math.ceil((1 - Math.min(...projected.map(v => v.y))) * innerHeight / 2));
    const ray = new T.Raycaster(); const v = new T.Vector2(); const found = [];
    for (let y = minY; y <= maxY; y += 2) for (let x = minX; x <= maxX; x += 2) {
      if (document.elementFromPoint(x, y)?.id !== 'experience-canvas') continue;
      v.set(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2); ray.setFromCamera(v, d.camera);
      const hit = ray.intersectObjects(d.avatar.pickTargets, false)[0];
      if (!hit || d.avatar.resolvePick(hit.object) !== action) continue;
      const obstacle = ray.intersectObjects(roomMeshes, false)[0];
      if (obstacle && obstacle.distance + .025 < hit.distance) continue;
      found.push({ x, y, node: hit.object.name, distance: hit.distance });
    }
    if (!found.length) return { error: `No unobstructed ${action} pixel`, bounds: { minX, maxX, minY, maxY } };
    // Pick a point surrounded by matching pixels, avoiding proxy edges and
    // giving touch tests a stable interior target after a small breathing move.
    const set = new Set(found.map(p => `${p.x},${p.y}`));
    for (const p of found) p.score = [-6,-4,-2,0,2,4,6].reduce((score, dx) => score + [-6,-4,-2,0,2,4,6].filter(dy => set.has(`${p.x+dx},${p.y+dy}`)).length, 0);
    found.sort((a, b) => b.score - a.score);
    return { ...found[0], candidateCount: found.length, bounds: { minX, maxX, minY, maxY } };
  }, action);
}
async function poseSamples(page, milliseconds) {
  return page.evaluate(milliseconds => new Promise(resolve => {
    const root = window.__roomPreview.avatar.root;
    const eye = root.getObjectByName('EyeL'); const body = root.getObjectByName('AvatarBody'); const arm = root.getObjectByName('AvatarArmL'); const head = root.getObjectByName('AvatarHead');
    const samples = []; const start = performance.now();
    function sample() {
      samples.push({ time: performance.now() - start, eyeY: eye.scale.y, bodyY: body.position.y, armZ: arm.rotation.z, headYaw: head.rotation.y });
      if (performance.now() - start < milliseconds) requestAnimationFrame(sample); else resolve(samples);
    }
    sample();
  }), milliseconds);
}
function range(samples, key) { return Math.max(...samples.map(s => s[key])) - Math.min(...samples.map(s => s[key])); }

try {
  const desktop = await scenario('desktop', { viewport: { width: 1440, height: 960 }, deviceScaleFactor: 1 });
  const page = desktop.page;
  await check('V8 room and genuine GLB scene are ready', async () => {
    const state = await getState(page);
    assert(state.room.lightingRevision === 8 && state.room.baked && !state.room.failed && state.room.errors.length === 0, 'Wrong or failed room scene');
    assert(state.avatar.loaded && state.avatar.meshCount > 5 && state.avatar.triangles > 1000 && state.avatar.pickTargetCount >= 5, 'Character GLB geometry or interactive parts missing');
    const visible = await page.evaluate(() => window.__roomPreview.avatar.root.visible);
    assert(visible, 'Avatar root is hidden');
    await screenshot(page, 'desktop-night'); return state;
  });
  await check('Greet button changes arm pose and returns to idle', async () => {
    const before = await getState(page);
    await page.locator('.avatar-card [data-avatar-action="greet"]').click();
    await page.waitForFunction(count => window.__roomPreview.getAvatarState().greetingCount > count && window.__roomPreview.getAvatarState().waving, before.avatar.greetingCount);
    const poses = await poseSamples(page, 2200);
    await page.waitForFunction(() => !window.__roomPreview.getAvatarState().waving);
    assert(range(poses, 'armZ') > 1, 'Waving state did not actually change the arm pose');
    assert(Math.abs(poses.at(-1).armZ) < .3, 'Arm did not settle near its rest pose');
    return { greetingCount: (await getState(page)).avatar.greetingCount, armRotationRange: range(poses, 'armZ'), endArmZ: poses.at(-1).armZ };
  });
  await check('Idle character breathes and blinks using actual mesh transforms', async () => {
    const poses = await poseSamples(page, 5200);
    assert(range(poses, 'eyeY') > .45, 'No visible blink in a full blink period');
    assert(range(poses, 'bodyY') > .005, 'Body idle pose did not change');
    return { samples: poses.length, eyeScaleRange: range(poses, 'eyeY'), bodyYRange: range(poses, 'bodyY') };
  });
  await check('Real body pointer pick greets without opening a panel', async () => {
    const pixel = await actualAvatarPixel(page, 'about'); assert(!pixel.error, JSON.stringify(pixel));
    const before = await getState(page);
    await page.mouse.move(pixel.x, pixel.y); await page.waitForTimeout(350);
    const hover = await getState(page);
    assert(hover.avatar.hovered && hover.avatar.pointerActive, 'Body hover did not reach controller');
    await page.mouse.click(pixel.x, pixel.y);
    await page.waitForFunction(time => window.__roomPreview.getState().lastInteraction?.time > time && window.__roomPreview.getState().lastInteraction?.id === 'avatar.creator', before.room.lastInteraction?.time || 0);
    const after = await getState(page);
    assert(after.room.modal === null && after.avatar.lastAction === 'about' && after.avatar.greetingCount > before.avatar.greetingCount, 'Body click did not greet correctly');
    return { pixel, avatar: after.avatar, interaction: after.room.lastInteraction };
  });
  await page.waitForFunction(() => !window.__roomPreview.getAvatarState().waving);
  await check('Pointer movement turns the real head', async () => {
    await page.mouse.move(100, 200); await page.waitForTimeout(550);
    const a = await poseSamples(page, 80);
    await page.mouse.move(1200, 350); await page.waitForTimeout(550);
    const b = await poseSamples(page, 80);
    const delta = Math.abs(a.at(-1).headYaw - b.at(-1).headYaw);
    assert(delta > .015, 'Head yaw failed to respond to pointer movement');
    return { leftYaw: a.at(-1).headYaw, rightYaw: b.at(-1).headYaw, delta };
  });
  await check('Real terminal pointer pick opens the work panel', async () => {
    const pixel = await actualAvatarPixel(page, 'work'); assert(!pixel.error, JSON.stringify(pixel));
    await page.mouse.click(pixel.x, pixel.y);
    await page.waitForFunction(() => window.__roomPreview.getState().modal === 'work');
    const state = await getState(page);
    assert(state.avatar.lastAction === 'work' && !state.room.controlsEnabled, 'Terminal did not open work and suspend room controls');
    assert((await page.locator('#modal-content').textContent()).includes('待补充'), 'Unexpected personal content');
    await screenshot(page, 'work-panel'); await closePanel(page); return { pixel, state };
  });
  await check('Visible card about/work panels preserve navigation and keyboard close', async () => {
    for (const kind of ['about', 'work']) {
      await page.locator(`.avatar-card [data-modal="${kind}"]`).click();
      await page.waitForFunction(kind => window.__roomPreview.getState().modal === kind, kind);
      assert(await page.locator('.avatar-card').evaluate(element => element.inert), 'Background card is not inert with panel open');
      await closePanel(page);
    }
    return { panels: ['about', 'work'] };
  });
  await check('Existing contact scene portal still opens and deliberate backdrop click closes', async () => {
    const pixel = await page.evaluate(async () => {
      const T = await import('/node_modules/three/build/three.module.js'); const d = window.__roomPreview;
      const portal = d.portals.get('contact');
      const point = portal.getWorldPosition(new T.Vector3()).project(d.camera);
      return { x: (point.x + 1) * innerWidth / 2, y: (1 - point.y) * innerHeight / 2 };
    });
    await page.mouse.click(pixel.x, pixel.y); await page.waitForFunction(() => window.__roomPreview.getState().modal === 'contact');
    await page.waitForTimeout(600); await page.mouse.click(20, 400);
    await page.waitForFunction(() => !window.__roomPreview.getState().modal && window.__roomPreview.getState().controlsEnabled);
    return { pixel };
  });
  await check('Day/night theme reaches character materials and room together', async () => {
    const before = await page.evaluate(() => { const d = window.__roomPreview; const lights = []; d.avatar.root.traverse(n => { if (n.isLight) lights.push({ name: n.type, intensity: n.intensity }); }); return { lights, room: d.getState(), avatar: d.getAvatarState() }; });
    await page.locator('.theme-toggle-button').click(); await page.waitForTimeout(1600);
    const after = await page.evaluate(() => { const d = window.__roomPreview; const lights = []; d.avatar.root.traverse(n => { if (n.isLight) lights.push({ name: n.type, intensity: n.intensity }); }); return { lights, room: d.getState(), avatar: d.getAvatarState() }; });
    assert(after.room.day && after.avatar.theme === 'day', 'Theme states diverged');
    assert(after.lights.some((light, i) => Math.abs(light.intensity - before.lights[i].intensity) > .02), 'Character light values did not change');
    await screenshot(page, 'desktop-day');
    await page.locator('.theme-toggle-button').click(); await page.waitForTimeout(1600);
    assert((await getState(page)).avatar.theme === 'night', 'Avatar did not return to night'); return { before, after };
  });
  await check('Drag starting on the character orbits without accidental selection', async () => {
    const pixel = await actualAvatarPixel(page, 'about'); assert(!pixel.error, JSON.stringify(pixel));
    const before = await getState(page);
    await page.mouse.move(pixel.x, pixel.y); await page.mouse.down(); await page.mouse.move(pixel.x + 110, pixel.y - 20, { steps: 12 }); await page.mouse.up(); await page.waitForTimeout(600);
    const after = await getState(page);
    assert(after.room.modal === null && after.avatar.greetingCount === before.avatar.greetingCount, 'Dragging triggered a character click');
    assert(Math.hypot(...after.room.camera.map((n, i) => n - before.room.camera[i])) > .1, 'Dragging did not move camera');
    await page.locator('[data-action="reset"]').click(); await page.waitForFunction(() => window.__roomPreview.getState().controlsEnabled); await page.waitForTimeout(200);
    return { beforeCamera: before.room.camera, afterCamera: after.room.camera };
  });
  await check('Close-up button focuses actual model and reset restores room', async () => {
    const button = page.locator('.avatar-card [data-avatar-action="focus"]');
    assert(await button.count() === 1, 'Close-up button missing');
    const before = await getState(page); await button.click();
    await page.waitForFunction(() => window.__roomPreview.getState().controlsEnabled); await page.waitForTimeout(250);
    const after = await getState(page);
    assert(Math.hypot(...after.room.camera.map((n, i) => n - before.room.camera[i])) > 1, 'Close-up did not move camera');
    await screenshot(page, 'character-closeup');
    await button.click(); await page.waitForFunction(() => window.__roomPreview.getState().controlsEnabled && !window.__roomPreview.getAvatarState().focused);
    const restored = await getState(page);
    assert(Math.hypot(...restored.room.camera.map((n, i) => n - before.room.camera[i])) < .01, 'Return-to-room did not restore the home camera');
    return { beforeCamera: before.room.camera, afterCamera: after.room.camera, restoredCamera: restored.room.camera };
  });
  desktop.log.final = await getState(page);
  await desktop.context.close();

  const mobile = await scenario('mobile', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  await check('Mobile card and controls fit with real character in V8 room', async () => {
    const layout = await mobile.page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height }; };
      return { overflow: document.documentElement.scrollWidth > innerWidth, card: rect('.avatar-card'), controls: rect('.scene-controls'), width: innerWidth, height: innerHeight };
    });
    assert(!layout.overflow && layout.card.x >= 0 && layout.card.right <= layout.width && layout.card.bottom <= layout.height && layout.controls.right <= layout.width, 'Mobile UI does not fit viewport');
    await screenshot(mobile.page, 'mobile'); return layout;
  });
  await check('Mobile body tap greets and terminal tap opens work', async () => {
    const body = await actualAvatarPixel(mobile.page, 'about'); assert(!body.error, JSON.stringify(body));
    const before = await getState(mobile.page);
    await mobile.page.touchscreen.tap(body.x, body.y);
    await mobile.page.waitForFunction(count => window.__roomPreview.getAvatarState().greetingCount > count, before.avatar.greetingCount);
    assert((await getState(mobile.page)).room.modal === null, 'Mobile body tap opened an unexpected panel');
    await mobile.page.waitForFunction(() => !window.__roomPreview.getAvatarState().waving);
    const terminal = await actualAvatarPixel(mobile.page, 'work'); assert(!terminal.error, JSON.stringify(terminal));
    await mobile.page.touchscreen.tap(terminal.x, terminal.y);
    await mobile.page.waitForFunction(() => window.__roomPreview.getState().modal === 'work');
    await mobile.page.waitForTimeout(800);
    const opened = await mobile.page.evaluate(() => ({ state: window.__roomPreview.getState(), hidden: document.querySelector('.modal').hidden }));
    assert(opened.state.modal === 'work' && !opened.hidden, `Touch-opened panel did not stay open: ${JSON.stringify(opened)}`);
    await mobile.page.locator('.modal-exit-button').tap(); await mobile.page.waitForFunction(() => !window.__roomPreview.getState().modal); return { body, terminal };
  });
  await check('Mobile close-up gives a readable character and working touch targets', async () => {
    await mobile.page.locator('.avatar-card [data-avatar-action="focus"]').tap();
    await mobile.page.waitForFunction(() => window.__roomPreview.getState().controlsEnabled && window.__roomPreview.getAvatarState().focused);
    await screenshot(mobile.page, 'mobile-closeup');
    const terminal = await actualAvatarPixel(mobile.page, 'work'); assert(!terminal.error, JSON.stringify(terminal));
    await mobile.page.touchscreen.tap(terminal.x, terminal.y); await mobile.page.waitForTimeout(800);
    assert((await getState(mobile.page)).room.modal === 'work', 'Focused terminal touch failed to leave work panel open');
    await mobile.page.locator('.modal-exit-button').tap(); await mobile.page.waitForFunction(() => !window.__roomPreview.getState().modal);
    return { terminal };
  });
  mobile.log.final = await getState(mobile.page); await mobile.context.close();

  const reduced = await scenario('reducedMotion', { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  await check('Reduced motion keeps poses still while clicks and themes work', async () => {
    const before = await getState(reduced.page);
    assert(before.avatar.reducedMotion && !before.avatar.waving, 'Reduced-motion preference ignored');
    await reduced.page.locator('.avatar-card [data-avatar-action="greet"]').click();
    const poses = await poseSamples(reduced.page, 1200);
    assert(range(poses, 'armZ') < .0001 && range(poses, 'bodyY') < .0001 && range(poses, 'eyeY') < .0001, 'Reduced-motion avatar still animates');
    await reduced.page.locator('.theme-toggle-button').click();
    assert((await getState(reduced.page)).avatar.theme === 'day', 'Reduced-motion theme failed');
    await reduced.page.locator('.avatar-card [data-modal="work"]').click();
    await reduced.page.waitForFunction(() => window.__roomPreview.getState().modal === 'work'); await closePanel(reduced.page);
    await screenshot(reduced.page, 'reduced-motion'); return { armRange: range(poses, 'armZ'), bodyRange: range(poses, 'bodyY'), eyeRange: range(poses, 'eyeY') };
  });
  reduced.log.final = await getState(reduced.page); await reduced.context.close();

  const failure = await scenario('avatarFailure', { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 }, true);
  await check('Forced avatar GLB failure leaves room and navigation usable', async () => {
    const state = await getState(failure.page);
    assert(state.avatar.loadStatus === 'failed' && state.avatar.error && !state.room.failed && state.room.controlsEnabled, 'Avatar failure blocks the room');
    assert(await failure.page.locator('.avatar-card [data-avatar-action="greet"]').isDisabled(), 'Unavailable avatar greet stays enabled');
    assert((await failure.page.locator('#avatar-status').textContent()).includes('作品仍可浏览'), 'Avatar failure lacks readable fallback');
    await failure.page.locator('.avatar-card [data-modal="work"]').click(); await failure.page.waitForFunction(() => window.__roomPreview.getState().modal === 'work'); await closePanel(failure.page);
    await screenshot(failure.page, 'avatar-unavailable'); return state;
  });
  failure.log.final = await getState(failure.page); await failure.context.close();
  await check('No uncaught JavaScript errors or unexpected failed network requests', async () => {
    const issues = Object.entries(report.scenarios).flatMap(([name, log]) => [
      ...log.pageErrors.map(error => ({ name, type: 'pageerror', error })),
      ...log.badResponses.map(error => ({ name, type: 'HTTP error', ...error })),
      ...log.failedRequests.filter(error => !error.expected).map(error => ({ name, type: 'requestfailed', ...error })),
      ...log.consoleErrors.filter(error => !(name === 'avatarFailure' && error.includes('net::ERR_FAILED'))).map(error => ({ name, type: 'consoleerror', error })),
    ]);
    assert(issues.length === 0, JSON.stringify(issues)); return { expectedAbort: report.scenarios.avatarFailure.failedRequests };
  });
} catch (error) {
  report.fatalError = String(error); console.error(error);
} finally {
  report.passed = !report.fatalError && report.checks.every(check => check.passed);
  await fs.writeFile(path.join(outputDir, 'web-verification.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, failures: report.checks.filter(check => !check.passed), fatalError: report.fatalError }));
  if (!report.passed) process.exitCode = 1;
}
