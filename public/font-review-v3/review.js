const list = document.querySelector('#candidates');
const stage = document.querySelector('#room-stage');
const selectedName = document.querySelector('#selected-name');
const candidates = await fetch('./candidates.json').then(response => {
  if (!response.ok) throw new Error('字体候选加载失败');
  return response.json();
});

const styles = document.createElement('style');
styles.textContent = candidates.map(font => `@font-face{font-family:"${font.family}";src:url("${font.fontUrl}") format("woff2");font-weight:${font.weight};font-style:${font.style || 'normal'};font-display:swap;}`).join('\n');
document.head.append(styles);

function applyFont(element, font) {
  element.style.setProperty('--sample-font', `"${font.family}"`);
  element.style.setProperty('--sample-weight', font.weight);
  element.style.setProperty('--sample-style', font.style || 'normal');
}
function selectFont(index, scroll = true) {
  const font = candidates[index];
  applyFont(stage, font);
  selectedName.textContent = `${String(index + 1).padStart(2, '0')} / ${font.name}`;
  document.querySelectorAll('.candidate').forEach((card, i) => {
    card.dataset.selected = String(i === index);
    card.querySelector('.select-font').setAttribute('aria-pressed', String(i === index));
  });
  document.querySelectorAll('.stage-font-options button').forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
  if (scroll) document.querySelector('.room-section').scrollIntoView({ behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start' });
}
candidates.forEach((font, index) => {
  const card = document.createElement('article');
  card.className = 'candidate';
  card.dataset.fontId = font.id;
  applyFont(card, font);
  card.innerHTML = `<div class="card-heading"><span class="card-number"></span><h2 class="card-name"></h2></div><p class="card-tag"></p><div class="specimen"><p class="sample-title lettering">创作空间</p><div class="sample-nav lettering"><span>作品</span><span>关于</span><span>联系</span></div><p class="sample-line lettering">在这里，记录创作与想象</p></div><div class="card-footer"><a class="source-link" target="_blank" rel="noreferrer">字体来源 ↗</a><button class="select-font" type="button" aria-pressed="false">放进房间预览 ↗</button></div>`;
  card.querySelector('.card-number').textContent = String(index + 1).padStart(2, '0');
  card.querySelector('.card-name').textContent = font.name;
  card.querySelector('.card-tag').textContent = font.tag;
  card.querySelector('.source-link').href = font.source;
  card.querySelector('.select-font').setAttribute('aria-label', `预览 ${String(index + 1).padStart(2, '0')} ${font.name}`);
  card.querySelector('.select-font').addEventListener('click', () => selectFont(index));
  list.append(card);
  const quickButton = document.createElement('button');
  quickButton.type = 'button';
  quickButton.textContent = `${String(index + 1).padStart(2, '0')} ${font.shortName || font.name}`;
  quickButton.setAttribute('aria-pressed', 'false');
  quickButton.addEventListener('click', () => selectFont(index, false));
  document.querySelector('.stage-font-options').append(quickButton);
});
document.querySelectorAll('[data-depth]').forEach(button => {
  if (button.tagName !== 'BUTTON') return;
  button.addEventListener('click', () => {
    document.documentElement.dataset.depth = button.dataset.depth;
    document.querySelectorAll('button[data-depth]').forEach(control => control.setAttribute('aria-pressed', String(control === button)));
  });
});
selectFont(0, false);
