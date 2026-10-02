const $ = selector => document.querySelector(selector);
const diagnostics = { status: 'loading', selected: null, depth: true, phrase: '创作空间', fonts: [], errors: [] };
const publish = () => { $('#font-review-diagnostics').textContent = JSON.stringify(diagnostics); };
let candidates = [], selected = null;
const fontReady = new Map();
const element = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text) node.textContent = text; return node; };

function select(candidate, animate = true) {
  selected = candidate;
  document.documentElement.style.setProperty('--preview-family', `"${candidate.family}"`);
  document.documentElement.style.setProperty('--preview-weight', candidate.weight);
  $('.selected-index').textContent = `${candidate.letter} / 04`;
  $('.candidate-kind').textContent = candidate.kind;
  $('.selected-name').textContent = candidate.name;
  $('.selected-tag').textContent = candidate.tag;
  $('.selected-description').textContent = candidate.description;
  for (const button of document.querySelectorAll('[data-select]')) button.setAttribute('aria-pressed', String(button.dataset.select === candidate.id));
  for (const card of document.querySelectorAll('.candidate-card')) card.classList.toggle('is-selected', card.dataset.id === candidate.id);
  const ready = fontReady.get(candidate.id);
  $('.type-proof').textContent = ready === true ? '真实字体 · 已载入' : ready === false ? '载入失败 · 请刷新重试' : '字体载入中';
  $('.type-proof').dataset.loadStatus = ready === true ? 'loaded' : ready === false ? 'error' : 'pending';
  if (animate) { $('.type-stage').classList.remove('switching'); requestAnimationFrame(() => { $('.type-stage').classList.add('switching'); }); }
  diagnostics.selected = candidate.id; publish();
}

try {
  const response = await fetch('./candidates.json');
  if (!response.ok) throw new Error(`字体信息读取失败 (${response.status})`);
  candidates = await response.json();
  $('.font-picks').replaceChildren();
  for (const candidate of candidates) {
    const button = element('button', 'font-pick'); button.type = 'button'; button.dataset.select = candidate.id;
    button.append(element('span', '', candidate.letter), document.createTextNode(candidate.shortName));
    button.addEventListener('click', () => select(candidate)); $('.font-picks').append(button);
    const card = element('article', 'candidate-card'); card.dataset.id = candidate.id;
    card.style.setProperty('--candidate-family', `"${candidate.family}"`); card.style.setProperty('--candidate-weight', candidate.weight);
    const top = element('div', 'card-top'); top.append(element('span', 'card-letter', candidate.letter), element('span', '', candidate.kind));
    const sample = element('p', 'card-sample display-text', '创作空间');
    const cardButton = element('button', 'card-button'); cardButton.type = 'button'; cardButton.dataset.select = candidate.id;
    cardButton.setAttribute('aria-label', `放大查看${candidate.name}`); cardButton.append(element('span', '', '放大查看'), element('span', '', '↗'));
    cardButton.addEventListener('click', () => { select(candidate); if (matchMedia('(max-width:760px)').matches) $('.controls').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth', block: 'start' }); });
    card.append(top, sample, element('p', 'card-name', candidate.name), element('p', 'card-tag', candidate.tag), cardButton);
    $('.candidate-grid').append(card);
    const credit = element('li'), name = element('span', '', candidate.name); name.append(element('span', 'credit-author', candidate.author));
    const links = element('span', 'credit-links');
    for (const [label, href] of [['来源 ↗', candidate.source], ['OFL 许可 ↗', candidate.licenseUrl]]) {
      const link = element('a', '', label); link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer'; links.append(link);
    }
    credit.append(name, links); $('#font-credits').append(credit);
  }
  select(candidates[0], false);
  await Promise.all(candidates.map(async candidate => {
    try {
      const loaded = await document.fonts.load(`${candidate.weight} 96px "${candidate.family}"`, '创作空间');
      const ready = loaded.length > 0 && loaded.every(face => face.status === 'loaded');
      if (!ready) throw new Error(`${candidate.name} 字体文件未成功载入`);
      fontReady.set(candidate.id, true);
      const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
      ctx.font = `${candidate.weight} 96px "${candidate.family}"`;
      diagnostics.fonts.push({ id: candidate.id, family: candidate.family, loaded: true, fontUrl: candidate.fontUrl, sampleWidth: ctx.measureText('创作空间').width, bytes: candidate.fontBytes, requiredOutlinesUnchanged: candidate.requiredOutlinesUnchanged });
    } catch (error) { fontReady.set(candidate.id, false); diagnostics.errors.push(String(error)); }
    if (selected.id === candidate.id) select(candidate, false); publish();
  }));
  diagnostics.status = diagnostics.errors.length ? 'error' : 'ready'; publish();
} catch (error) { diagnostics.status = 'error'; diagnostics.errors.push(String(error)); $('.loading-note')?.replaceChildren(document.createTextNode('字体读取失败，请刷新重试')); publish(); }

$('.depth-toggle').addEventListener('click', event => {
  diagnostics.depth = !diagnostics.depth;
  document.body.classList.toggle('has-depth', diagnostics.depth);
  event.currentTarget.setAttribute('aria-pressed', String(diagnostics.depth)); publish();
});
$('#sample-phrase').addEventListener('change', event => {
  diagnostics.phrase = event.currentTarget.value;
  for (const sample of document.querySelectorAll('.card-sample')) sample.textContent = diagnostics.phrase;
  publish();
});
