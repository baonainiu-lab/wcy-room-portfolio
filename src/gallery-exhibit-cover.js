import * as THREE from 'three';
import { galleryExhibits } from './gallery-catalog.js';

export const FIRST_GALLERY_WORK = Object.freeze({
  title: '糖壳暴食兽',
  category: '3D 玩法原型',
  poster: '/media/works/sugar-shell-glutton/poster.webp',
});

// V5's frame, paper and relief are one baked mesh. Project onto the existing
// paper/relief surfaces, leaving its positions, indices and atlas UV untouched.
// These bounds are the actual paper dimensions in the art mesh's local basis.
const PAPER = Object.freeze({ width: .896, height: 1.442, front: .093 });
const UI_FONT = '"Microsoft YaHei", "微软雅黑", "PingFang SC", "Hiragino Sans GB", "Segoe UI", Arial, sans-serif';
const TITLE_FONT = `"Atelier Forge Display", ${UI_FONT}`;

function drawCover(canvas, image, exhibit) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  const inset = 66;
  ctx.fillStyle = '#ede8dc';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#6f7269';
  ctx.font = `500 23px ${UI_FONT}`;
  ctx.fillText(exhibit.eyebrow, inset, 96);
  ctx.strokeStyle = '#b6ad98';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(inset, 130); ctx.lineTo(width - inset, 130); ctx.stroke();

  ctx.fillStyle = '#253c3a';
  ctx.font = `700 112px ${TITLE_FONT}`;
  const titles = { 1: ['糖壳', '暴食兽'], 2: ['夜班', '便利店'], 3: ['三维', '制作研究'], 4: ['龙卷风', '特效'], 5: ['AI 产品', '实践'] };
  const lines = titles[exhibit.index];
  ctx.fillText(lines[0], inset - 3, 299);
  ctx.fillText(lines[1], inset - 3, 446);
  ctx.font = `500 26px ${UI_FONT}`;
  ctx.fillStyle = '#777869';
  ctx.fillText({1:'3D 玩法原型',2:'第一人称经营原型',3:'相机 / 客厅 / 跑车',4:'Maya 动态特效',5:'AI 软件与产品工作流'}[exhibit.index], inset, 507);

  // Show the complete recorded frame. A portrait crop would lose the player's
  // view and is deliberately avoided in this narrow, pre-existing art mount.
  const imageWidth = width - inset * 2;
  const imageHeight = imageWidth * image.naturalHeight / image.naturalWidth;
  const imageTop = 603;
  ctx.drawImage(image, inset, imageTop, imageWidth, imageHeight);
  ctx.fillStyle = '#8a8b7d';
  ctx.font = `400 20px ${UI_FONT}`;
  ctx.fillText(exhibit.index < 3 ? '实际运行画面' : exhibit.index === 3 ? '实际模型渲染' : exhibit.index === 4 ? '特效演示' : '软件与工作流', inset, imageTop + imageHeight + 45);
  ctx.strokeStyle = '#b6ad98';
  ctx.beginPath(); ctx.moveTo(inset, height - 250); ctx.lineTo(width - inset, height - 250); ctx.stroke();
  ctx.fillStyle = '#253c3a';
  ctx.font = `400 23px ${UI_FONT}`;
  ctx.fillText('点击观看完整作品', inset, height - 172);
  ctx.fillStyle = '#9f7e46';
  ctx.font = `400 26px ${UI_FONT}`;
  ctx.textAlign = 'right';
  ctx.fillText('↗', width - inset, height - 172);
}

/** Install before createDualLighting so the cloned material joins its bake mix. */
function createCover({ model, renderer, exhibit }) {
  const number = String(exhibit.index).padStart(2, '0');
  const framed = [1, 3].includes(exhibit.index);
  const assetId = `gallery.work.${number}${framed ? '.art' : ''}`;
  const centerX = [-4.8, -2.7, -.6, 1.5, 3.6][exhibit.index - 1];
  const projection = framed ? { x: 0, y: 0, ...PAPER } : { x: centerX, y: 1.88, width: 1.28, height: 2.54, front: -2.34 };
  let art;
  model.traverse(node => { if (node.userData.asset_id === assetId) art = node; });
  if (!art) throw new Error(`Gallery exhibit ${number} is missing.`);
  const canvas = document.createElement('canvas');
  canvas.width = 896; canvas.height = 1442;
  const texture = new THREE.CanvasTexture(canvas);
  texture.name = `${exhibit.title} · gallery exhibit ${number}`;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);
  // CanvasTexture's default flipY matches the local bottom-to-top projection.
  const readyUniform = { value: 0 };
  const bindings = [];
  let disposed = false, status = 'loading';

  art.traverse(mesh => {
    if (!mesh.isMesh) return;
    // Existing background board only; glass, ornaments and frames retain their geometry.
    if (!framed && !mesh.name.replaceAll('.', '').includes(`gallerywork${number}__baked`)) return;
    const original = mesh.material;
    if (Array.isArray(original) || !original.isMeshBasicMaterial || !/^GALLERY_LIGHTMAP_\d+$/.test(original.name)) {
      throw new Error('The first gallery cover requires the retained baked art material.');
    }
    const material = original.clone();
    // Keep the atlas slot name: dual lighting must patch this private material
    // as well as the shared original used by the rest of the gallery.
    material.userData = { ...material.userData, exhibit: exhibit.slug };
    const previousCompile = material.onBeforeCompile;
    const previousKey = material.customProgramCacheKey.bind(material);
    const baseKey = previousKey();
    material.onBeforeCompile = (shader, currentRenderer) => {
      previousCompile.call(material, shader, currentRenderer);
      shader.uniforms.uExhibitCover = { value: texture };
      shader.uniforms.uExhibitReady = readyUniform;
      shader.vertexShader = `varying vec3 vExhibitPosition;\n${shader.vertexShader}`
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvExhibitPosition = position;');
      shader.fragmentShader = `uniform sampler2D uExhibitCover;\nuniform float uExhibitReady;\nvarying vec3 vExhibitPosition;\n${shader.fragmentShader}`
        .replace('#include <map_fragment>', `#include <map_fragment>
          vec2 exhibitUv = (vExhibitPosition.xy - vec2(${projection.x}, ${projection.y})) / vec2(${projection.width}, ${projection.height}) + 0.5;
          if (uExhibitReady > 0.5 && vExhibitPosition.z >= ${projection.front}
              && all(greaterThanEqual(exhibitUv, vec2(0.0)))
              && all(lessThanEqual(exhibitUv, vec2(1.0)))) {
            // The shared lighting uniform is installed by createDualLighting.
            // Frame pixels keep the exact bake; the printed artwork remains
            // readable at night without retaining the old relief's colours.
            diffuseColor.rgb = texture2D(uExhibitCover, exhibitUv).rgb * mix(0.58, 1.0, uLightingMix);
          }
        `);
    };
    material.customProgramCacheKey = () => `${baseKey}|exhibit-cover-v2-${number}`;
    mesh.material = material;
    bindings.push({ mesh, original, material });
  });
  if (!bindings.length) throw new Error(`作品展架 ${number} 未找到可印刷的原模型表面。`);

  const image = new Image();
  const ready = new Promise(resolve => {
    image.onload = async () => {
      // Canvas text does not repaint when a web font arrives. Wait before the
      // one-time cover upload so headings cannot silently retain fallback faces.
      await document.fonts?.load('700 112px "Atelier Forge Display"', exhibit.title).catch(() => {});
      if (disposed) { resolve(false); return; }
      drawCover(canvas, image, exhibit);
      texture.needsUpdate = true;
      renderer.initTexture(texture);
      readyUniform.value = 1;
      status = 'ready';
      resolve(true);
    };
    image.onerror = () => { if (!disposed) status = 'unavailable'; resolve(false); };
    image.src = exhibit.cover;
  });

  return {
    ready,
    getState: () => ({ status, assetId, title: exhibit.title,
      poster: exhibit.cover, materialCount: bindings.length,
      projection: framed ? 'existing-local-paper' : 'existing-backboard', originalGeometryAndUv: true }),
    dispose() {
      if (disposed) return;
      disposed = true; status = 'disposed';
      for (const { mesh, original, material } of bindings) {
        if (mesh.material === material) mesh.material = original;
        material.dispose();
      }
      texture.dispose();
    },
  };
}

/** Update printed surfaces on the authored meshes; no extra model geometry. */
export function createGalleryExhibitCover({ model, renderer }) {
  const covers = galleryExhibits.map(exhibit => createCover({ model, renderer, exhibit }));
  return {
    ready: Promise.all(covers.map(cover => cover.ready)).then(results => {
      if (results.some(result => !result)) throw new Error('作品展架封面加载失败，请重试。');
      return true;
    }),
    getState: () => ({ ...covers[0].getState(), exhibits: covers.map(cover => cover.getState()) }),
    dispose: () => covers.forEach(cover => cover.dispose()),
  };
}
