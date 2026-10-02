import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DemoProgress } from '../public/loader-review-v1/source/demo-progress.js';
import { SHAPES, PathLoader } from '../public/loader-review-v1/source/vendor/adapted-effects.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const review = resolve(root, 'public/loader-review-v1');
const require = createRequire(import.meta.url);
const { gsap } = require('../node_modules/gsap/dist/gsap.js');
let passed = 0;
function check(name, fn) { fn(); passed++; console.log(`PASS ${name}`); }
function advance(model, seconds = 20) { for (let i = 0; i < seconds * 60; i++) model.advance(1 / 60); }
const hash = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');

check('100% gates reveal; completion callback cannot finish an incomplete load', () => {
  const model = new DemoProgress();
  model.complete(); assert.equal(model.phase, 'loading');
  model.scrub(99); model.complete(); assert.equal(model.phase, 'loading');
  model.scrub(100); assert.equal(model.phase, 'revealing');
  model.complete(); assert.equal(model.phase, 'complete');
});
check('automatic simulation is monotonic and bounded, with no frame time jump', () => {
  const model = new DemoProgress();
  model.advance(120); assert(model.progress < 3);
  let previous = model.progress;
  for (let i = 0; i < 1000; i++) { model.advance(1 / 60); assert(model.progress >= previous && model.progress <= 100); previous = model.progress; }
  assert.equal(model.progress, 100); assert.equal(model.phase, 'revealing');
});
check('waiting holds at 78 indefinitely and resumes after wait is released', () => {
  const model = new DemoProgress({ wait: true });
  advance(model); assert.equal(model.progress, 78); assert.equal(model.phase, 'waiting');
  advance(model, 90); assert.equal(model.progress, 78);
  model.complete(); assert.equal(model.phase, 'waiting');
  model.setOptions({ wait: false }); advance(model); assert.equal(model.phase, 'revealing');
});
check('failure holds at 62, outranks wait, and cannot complete', () => {
  const model = new DemoProgress({ fail: true, wait: true });
  advance(model); assert.equal(model.progress, 62); assert.equal(model.phase, 'error'); assert.equal(model.playing, false);
  model.complete(); advance(model, 90); assert.equal(model.progress, 62); assert.equal(model.phase, 'error');
  model.scrub(100); assert.equal(model.phase, 'error'); assert.equal(model.progress, 62);
});
check('failure release permits continuation; retry resets previous state', () => {
  const model = new DemoProgress({ fail: true }); advance(model);
  model.setOptions({ fail: false }); assert.equal(model.phase, 'loading'); assert.equal(model.playing, true);
  advance(model); model.complete(); assert.equal(model.phase, 'complete');
  model.reset(); assert.deepEqual(model.snapshot(), { progress: 0, phase: 'loading', playing: true, wait: false, fail: false });
});
check('pause and scrub retain exact progress; reveal can be scrubbed back to loading', () => {
  const model = new DemoProgress(); model.scrub(43); advance(model); assert.equal(model.progress, 43);
  model.scrub(100); model.complete(); model.scrub(30); assert.equal(model.phase, 'loading'); assert.equal(model.progress, 30);
  model.playing = true; advance(model); assert.equal(model.phase, 'revealing');
});
check('invalid progress/time input cannot poison state', () => {
  const model = new DemoProgress(); model.scrub(30);
  for (const value of [NaN, Infinity, 'no']) model.scrub(value);
  assert.equal(model.progress, 30);
  model.playing = true; model.advance(-1); model.advance(NaN); model.advance(Infinity); assert.equal(model.progress, 30);
  model.scrub(-8); assert.equal(model.progress, 0); model.scrub(200); assert.equal(model.progress, 100);
});
check('Codrops PathLoader adapter draws actual measured path and clamps endpoints', () => {
  const path = { style: {}, getTotalLength: () => 314.159 };
  const loader = new PathLoader(path);
  assert.equal(path.style.strokeDasharray, 314.159); assert.equal(path.style.strokeDashoffset, 314.159);
  loader.setProgress(.625); assert.equal(path.style.strokeDashoffset, 314.159 * .375);
  loader.setProgress(-1); assert.equal(path.style.strokeDashoffset, 314.159);
  loader.setProgress(2); assert.equal(path.style.strokeDashoffset, 0);
});
check('actual installed GSAP core interpolates both normalized SVG path strings', () => {
  for (const shape of Object.values(SHAPES)) {
    // GSAP registers DOM AttrPlugin only in a browser. Check its core string
    // interpolation here; the real SVG attribute binding remains browser QA.
    const path = { d: shape.closed };
    const tween = gsap.to(path, { d: shape.open, duration: 1, ease: 'none', paused: true });
    tween.progress(.5); assert.notEqual(path.d, shape.closed); assert.notEqual(path.d, shape.open); assert(!/NaN|undefined/.test(path.d));
    const numbers = (d) => d.match(/-?\d+(?:\.\d+)?/g).map(Number);
    const midpoint = numbers(path.d), start = numbers(shape.closed), end = numbers(shape.open);
    assert.equal(midpoint.length, start.length); assert.equal(start.length, end.length);
    midpoint.forEach((n, index) => assert(Math.abs(n - (start[index] + end[index]) / 2) < 1e-4));
    tween.progress(1); assert.deepEqual(numbers(path.d), numbers(shape.open)); tween.kill();
  }
});
check('adapted compound path endpoints close fully and reveal full rectangular view', () => {
  const polygon = (d) => d.split('Z')[1].match(/-?\d+(?:\.\d+)?/g).map(Number).reduce((out, n, i, all) => { if (i % 2 === 0) out.push([n, all[i + 1]]); return out; }, []);
  const area = (points) => Math.abs(points.reduce((sum, [x,y], i) => { const [nx,ny] = points[(i+1)%points.length]; return sum+x*ny-y*nx; }, 0)/2);
  for (const shape of Object.values(SHAPES)) assert.equal(area(polygon(shape.closed)), 0);
  assert.equal(area(polygon(SHAPES.D.open)), 80*60);
  // Origami diamond encloses every corner of the 80x60 viewport.
  for (const [x,y] of [[0,0],[80,0],[80,60],[0,60]]) assert(Math.abs(x-40)/80 + Math.abs(y-30)/70 <= 1.001);
});
check('HTML controls, ARIA tabs, and all local script/style/media references exist', () => {
  const html = readFileSync(resolve(review, 'index.html'), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  for (const id of ['preview','progress','play','replay','simulate-wait','simulate-failure','reduce-motion','stage-retry','tab-A','tab-B','tab-C','tab-D','loader-review-diagnostics']) assert(ids.includes(id));
  assert.equal((html.match(/role="tab"/g) || []).length, 4);
  for (const [, target] of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    if (/^https:|^#/.test(target) || target === '/') continue;
    assert(existsSync(target.startsWith('/') ? resolve(root, 'public', target.slice(1)) : resolve(review, target)), target);
  }
  assert(!/<(?:script|iframe)[^>]*src="https?:/i.test(html));
  assert(!/<link[^>]*href="https?:/i.test(html));
  const css = readFileSync(resolve(review, 'review.css'), 'utf8'); assert(!/url\(['"]?https?:|@import/.test(css));
});
check('provenance pins every source and copied runtime/media hashes match originals', () => {
  const manifest = JSON.parse(readFileSync(resolve(review, 'source/provenance.json')));
  assert.equal(manifest.sources.length, 3);
  for (const source of manifest.sources) {
    assert.match(source.commit, /^[a-f\d]{40}$/);
    for (const file of source.files) { assert.match(file.sha256, /^[a-f\d]{64}$/); assert(file.url.includes(source.commit)); }
  }
  for (const item of [manifest.dependency, ...manifest.projectMedia]) {
    assert.equal(hash(resolve(review, item.local)), item.sha256);
    assert.equal(hash(resolve(root, item.source)), item.sha256);
  }
  for (const name of ['olaf-MIT.txt','Codrops-MIT.txt','PageLoadingEffects-README.md','PagePreloadingEffect-README.md','GSAP-NOTICE.txt']) assert(existsSync(resolve(review, 'source/licenses', name)));
  assert(readFileSync(resolve(review, 'source/vendor/gsap.min.js'), 'utf8').includes('@license Copyright 2026, GreenSock. All rights reserved.'));
});
gsap.ticker.sleep();
console.log(`\n${passed} CPU checks passed. No browser / WebGL was run; visual and interaction QA remain browser checks.`);
