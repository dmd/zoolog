/* ============================================================
   Zoolog PWA
   Client-side journal reader + full-text search. No backend.
   ============================================================ */
'use strict';

/* ---------- Category config ---------- */
const CATS = {
  A:    { tag: 'A',     label: 'A',       color: 'var(--cat-A)' },
  D:    { tag: 'D',     label: 'D',       color: 'var(--cat-D)' },
  J:    { tag: 'J',     label: 'Uncle J', color: 'var(--cat-J)' },
  AHNS: { tag: 'AHNS',  label: 'AHNS',    color: 'var(--cat-AHNS)' },
  G:    { tag: 'G',     label: 'Grandpa', color: 'var(--cat-G)' },
};
// Filter chips: value -> predicate over category code.
const FILTERS = [
  { key: 'all', label: 'All',     match: () => true },
  { key: 'US',  label: 'Us',      match: c => c === 'A' || c === 'D' },
  { key: 'A',   label: 'A',       match: c => c === 'A' },
  { key: 'D',   label: 'D',       match: c => c === 'D' },
  { key: 'J',   label: 'Uncle J', match: c => c === 'J' },
  { key: 'AHNS',label: 'AHNS',    match: c => c === 'AHNS' },
  { key: 'G',   label: 'Grandpa', match: c => c === 'G' },
];

/* ---------- State ---------- */
let ALL = [];              // all entries, ascending by date
let display = [];          // current filtered list, in display order
let ascList = [];          // current filtered list, ascending by date (reader nav)
let ascPos = new Map();    // entry.i -> index within ascList
let renderedCount = 0;
let lastMonthRendered = null;

const state = {
  filter: localStorage.getItem('zl.filter') || 'all',
  query: '',
};
let queryParsed = { terms: [], phrases: [] };
let highlightRe = null;

/* ---------- Search index (lazy) ---------- */
let index = null;          // Map: token -> int[] (entry indices, ascending)
let indexBuilding = false;

const TOKEN_RE = /[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu;

function tokenize(text) {
  const out = [];
  let m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(text)) !== null) out.push(m[0].toLowerCase());
  return out;
}

function buildIndex() {
  if (index || indexBuilding) return;
  indexBuilding = true;
  const idx = new Map();
  for (const e of ALL) {
    const seen = new Set(tokenize(e.b));
    for (const tok of seen) {
      let arr = idx.get(tok);
      if (!arr) { arr = []; idx.set(tok, arr); }
      arr.push(e.i);
    }
  }
  index = idx;
  indexBuilding = false;
}

/* ---------- Query parsing & search ---------- */
function parseQuery(q) {
  const phrases = [];
  const terms = [];
  // Pull out "quoted phrases" first.
  const re = /"([^"]+)"/g;
  let m;
  let rest = q;
  while ((m = re.exec(q)) !== null) {
    const p = m[1].trim().toLowerCase();
    if (p) phrases.push(p);
  }
  rest = q.replace(/"[^"]*"/g, ' ');
  for (const t of tokenize(rest)) terms.push(t);
  return { terms, phrases };
}

function postingsForPrefix(prefix) {
  // Union of postings for every indexed token starting with `prefix`.
  const exact = index.get(prefix);
  const set = new Set(exact || []);
  // Also include longer tokens with this prefix (search-as-you-type).
  for (const [tok, arr] of index) {
    if (tok.length > prefix.length && tok.startsWith(prefix)) {
      for (const id of arr) set.add(id);
    }
  }
  return set;
}

function runSearch() {
  // Returns a Set of entry indices, or null for "no query".
  const { terms, phrases } = queryParsed;
  if (!terms.length && !phrases.length) return null;
  if (!index) buildIndex();

  let candidate = null; // Set of ids
  for (const term of terms) {
    const docs = postingsForPrefix(term);
    if (candidate === null) candidate = docs;
    else candidate = intersect(candidate, docs);
    if (candidate.size === 0) return candidate;
  }

  if (phrases.length) {
    const ids = candidate === null ? ALL.map(e => e.i) : [...candidate];
    const result = new Set();
    for (const id of ids) {
      const body = ALL[id].b.toLowerCase();
      if (phrases.every(p => body.includes(p))) result.add(id);
    }
    return result;
  }
  return candidate;
}

function intersect(a, b) {
  const [small, big] = a.size <= b.size ? [a, b] : [b, a];
  const out = new Set();
  for (const x of small) if (big.has(x)) out.add(x);
  return out;
}

/* ---------- Highlight ---------- */
function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function buildHighlightRe() {
  const { terms, phrases } = queryParsed;
  const parts = [];
  for (const p of phrases) parts.push(escapeRe(p));
  for (const t of terms) parts.push(escapeRe(t) + "[\\p{L}\\p{N}'’]*"); // prefix
  if (!parts.length) { highlightRe = null; return; }
  // Longest first so phrases win over their constituent words.
  parts.sort((a, b) => b.length - a.length);
  highlightRe = new RegExp('(' + parts.join('|') + ')', 'giu');
}

function highlightInto(el) {
  if (!highlightRe) return;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let n;
  while ((n = walker.nextNode())) nodes.push(n);
  for (const node of nodes) {
    const text = node.nodeValue;
    highlightRe.lastIndex = 0;
    if (!highlightRe.test(text)) continue;
    highlightRe.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0, m;
    while ((m = highlightRe.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const mark = document.createElement('mark');
      mark.textContent = m[0];
      frag.appendChild(mark);
      last = m.index + m[0].length;
      if (m.index === highlightRe.lastIndex) highlightRe.lastIndex++; // guard empty
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }
}

/* ---------- Date helpers ---------- */
function parseDate(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}
const fmtCard = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
const fmtFull = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
const fmtMonth = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });
function monthKey(s) { return s.slice(0, 7); }

/* ---------- Markdown-ish renderer ---------- */
function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function inlineMd(s) {
  s = escapeHtml(s);
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  return s;
}
// The source text is hard-wrapped at ~74 chars. A line is a *soft wrap*
// (continuation of the same sentence) when it is "full"; a noticeably short
// line is an intentional break — a list item, a line of dialogue, or the end
// of a paragraph. We rejoin soft wraps with spaces and keep intentional breaks.
const WRAP = 64;

function dewrap(lines) {
  const out = [];
  let cur = '';
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].replace(/\s+$/, '');
    cur += (cur ? ' ' : '') + line.trim();
    const full = line.length >= WRAP;
    if (i === lines.length - 1 || !full) {
      out.push(cur);
      cur = '';
    }
  }
  return out.filter(s => s.length);
}

function renderBody(text) {
  const blocks = text.replace(/\r/g, '').split(/\n{2,}/);
  const html = [];
  for (const block of blocks) {
    if (!block.trim()) continue;
    const lines = block.split('\n');
    if (lines.every(l => /^\s*[-*]\s+/.test(l))) {
      html.push('<ul>' + lines.map(l =>
        '<li>' + inlineMd(l.replace(/^\s*[-*]\s+/, '').trim()) + '</li>').join('') + '</ul>');
    } else if (/^#{1,6}\s+/.test(lines[0])) {
      html.push('<h3>' + inlineMd(lines[0].replace(/^#{1,6}\s+/, '').trim()) + '</h3>');
    } else {
      html.push('<p>' + dewrap(lines).map(inlineMd).join('<br>') + '</p>');
    }
  }
  return html.join('');
}
function excerpt(text, n = 180) {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > n ? flat.slice(0, n).trimEnd() + '…' : flat;
}

/* ---------- List computation ---------- */
function recompute() {
  const f = FILTERS.find(x => x.key === state.filter) || FILTERS[0];
  const searchSet = runSearch();
  let list = ALL.filter(e => f.match(e.c) && (searchSet === null || searchSet.has(e.i)));
  // ascending list for reader navigation
  ascList = list;
  ascPos = new Map();
  ascList.forEach((e, i) => ascPos.set(e.i, i));
  // Feed always shows newest first; ascList stays ascending for reader nav.
  display = [...list].reverse();
}

/* ---------- Feed rendering ---------- */
const feedList = document.getElementById('feed-list');
const feedStatus = document.getElementById('feed-status');
const feedEmpty = document.getElementById('feed-empty');
const sentinel = document.getElementById('feed-sentinel');
const BATCH = 30;

function cardEl(e) {
  const cat = CATS[e.c] || { tag: e.c, color: 'var(--ink-faint)' };
  const btn = document.createElement('button');
  btn.className = 'card';
  btn.dataset.id = e.i;
  const meta = document.createElement('div');
  meta.className = 'card__meta';
  const date = document.createElement('span');
  date.className = 'card__date';
  date.textContent = fmtCard.format(parseDate(e.d));
  const tag = document.createElement('span');
  tag.className = 'tag';
  tag.style.setProperty('--tag', cat.color);
  tag.textContent = cat.tag;
  meta.append(date, tag);
  const ex = document.createElement('p');
  ex.className = 'card__excerpt';
  ex.textContent = excerpt(e.b);
  if (highlightRe) highlightInto(ex);
  btn.append(meta, ex);
  return btn;
}

function monthHeadEl(label) {
  const h = document.createElement('div');
  h.className = 'month-head';
  h.textContent = label;
  return h;
}

function appendBatch() {
  const frag = document.createDocumentFragment();
  const end = Math.min(renderedCount + BATCH, display.length);
  for (let i = renderedCount; i < end; i++) {
    const e = display[i];
    const mk = monthKey(e.d);
    if (mk !== lastMonthRendered) {
      lastMonthRendered = mk;
      frag.appendChild(monthHeadEl(fmtMonth.format(parseDate(e.d))));
    }
    frag.appendChild(cardEl(e));
  }
  feedList.appendChild(frag);
  renderedCount = end;
  if (renderedCount >= display.length) io.unobserve(sentinel);
  else io.observe(sentinel);
}

function renderFeed() {
  recompute();
  feedList.innerHTML = '';
  renderedCount = 0;
  lastMonthRendered = null;
  io.unobserve(sentinel);

  const n = display.length;
  if (state.query) {
    feedStatus.textContent = n
      ? `${n.toLocaleString()} ${n === 1 ? 'entry' : 'entries'} matching “${state.query.trim()}”`
      : '';
  } else {
    feedStatus.textContent = `${n.toLocaleString()} entries`;
  }
  feedEmpty.hidden = n > 0;
  if (n === 0 && state.query) {
    document.getElementById('feed-empty-text').textContent =
      `Nothing matches “${state.query.trim()}”.`;
  }
  appendBatch();
}

const io = new IntersectionObserver(entries => {
  for (const en of entries) if (en.isIntersecting) appendBatch();
}, { rootMargin: '600px 0px' });

/* ---------- Reader ---------- */
const reader = document.getElementById('reader');
const readerScroll = document.getElementById('reader-scroll');
let currentId = null;

function openReader(id) {
  const e = ALL[id];
  if (!e) return;
  currentId = id;
  const cat = CATS[e.c] || { label: e.c, tag: e.c, color: 'var(--ink-faint)' };

  const barTitle = document.getElementById('reader-bar-title');
  barTitle.textContent = fmtCard.format(parseDate(e.d));
  barTitle.classList.remove('show'); // revealed on scroll past the heading
  const eyebrow = document.getElementById('reader-eyebrow');
  eyebrow.innerHTML = '';
  const dot = document.createElement('span');
  dot.className = 'tag';
  dot.style.setProperty('--tag', cat.color);
  dot.textContent = cat.tag;
  eyebrow.appendChild(dot);

  document.getElementById('reader-date').textContent = fmtFull.format(parseDate(e.d));
  const body = document.getElementById('reader-body');
  body.innerHTML = renderBody(e.b);
  if (highlightRe) highlightInto(body);

  // Position + neighbors within the current ascending list.
  const pos = ascPos.has(id) ? ascPos.get(id) : -1;
  const posEl = document.getElementById('reader-pos');
  posEl.textContent = pos >= 0 ? `${pos + 1} / ${ascList.length}` : '';

  const prevEntry = pos > 0 ? ascList[pos - 1] : null;            // earlier (older)
  const nextEntry = pos >= 0 && pos < ascList.length - 1 ? ascList[pos + 1] : null; // later (newer)
  wireNav('reader-prev', 'reader-prev-date', prevEntry);
  wireNav('reader-next', 'reader-next-date', nextEntry);

  reader.hidden = false;
  document.body.style.overflow = 'hidden';
  readerScroll.scrollTop = 0;
}

function wireNav(btnId, dateId, entry) {
  const btn = document.getElementById(btnId);
  const dt = document.getElementById(dateId);
  if (entry) {
    btn.disabled = false;
    dt.textContent = fmtCard.format(parseDate(entry.d));
    btn.dataset.target = entry.i;
  } else {
    btn.disabled = true;
    dt.textContent = '—';
    delete btn.dataset.target;
  }
}

function navTo(btnId) {
  const t = document.getElementById(btnId).dataset.target;
  if (t !== undefined) goToEntry(Number(t));
}

// Opening the reader from the feed pushes ONE history entry. Hopping between
// entries with Earlier/Later *replaces* that single entry instead of stacking,
// so the back button (and the OS back gesture) always returns to the feed in
// one step no matter how many entries you paged through.
function goToEntry(id) {
  if (!ALL[id]) return;
  const url = '#/e/' + id;
  if (currentId === null) history.pushState({ id }, '', url);
  else history.replaceState({ id }, '', url);
  openReader(id);
}

function closeReader() {
  reader.hidden = true;
  document.body.style.overflow = '';
  currentId = null;
}

/* ---------- Routing ---------- */
// Back/forward (button, gesture) land here; programmatic nav uses goToEntry.
window.addEventListener('popstate', () => {
  const m = location.hash.match(/^#\/e\/(\d+)$/);
  if (m && ALL[Number(m[1])]) openReader(Number(m[1]));
  else closeReader();
});

function initRoute() {
  const m = location.hash.match(/^#\/e\/(\d+)$/);
  if (m && ALL[Number(m[1])]) {
    // Synthesize a feed state underneath a deep-linked entry so back works.
    history.replaceState(null, '', '#/');
    goToEntry(Number(m[1]));
  } else if (location.hash) {
    history.replaceState(null, '', '#/');
  }
}

/* ---------- Chips ---------- */
function buildChips() {
  const wrap = document.getElementById('chips');
  for (const f of FILTERS) {
    const b = document.createElement('button');
    b.className = 'chip';
    b.dataset.key = f.key;
    b.setAttribute('aria-pressed', String(f.key === state.filter));
    const catColor = ({ A: 'var(--cat-A)', D: 'var(--cat-D)', J: 'var(--cat-J)',
      AHNS: 'var(--cat-AHNS)', G: 'var(--cat-G)' })[f.key];
    if (catColor) {
      const dot = document.createElement('span');
      dot.className = 'chip__dot';
      dot.style.setProperty('--dot', catColor);
      b.appendChild(dot);
    }
    b.appendChild(document.createTextNode(f.label));
    b.addEventListener('click', () => {
      if (state.filter === f.key) return;
      state.filter = f.key;
      localStorage.setItem('zl.filter', f.key);
      wrap.querySelectorAll('.chip').forEach(c =>
        c.setAttribute('aria-pressed', String(c.dataset.key === f.key)));
      renderFeed();
      document.getElementById('feed').scrollIntoView();
    });
    wrap.appendChild(b);
  }
}

/* ---------- Search input ---------- */
function setupSearch() {
  const input = document.getElementById('search-input');
  const clear = document.getElementById('search-clear');
  let timer = null;
  function apply() {
    state.query = input.value;
    queryParsed = parseQuery(state.query);
    buildHighlightRe();
    clear.hidden = !input.value;
    renderFeed();
  }
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(apply, 140);
  });
  input.addEventListener('search', apply);
  clear.addEventListener('click', () => {
    input.value = '';
    apply();
    input.focus();
  });
}

/* ---------- Wiring ---------- */
function wireGlobal() {
  feedList.addEventListener('click', ev => {
    const card = ev.target.closest('.card');
    if (card) goToEntry(Number(card.dataset.id));
  });
  document.getElementById('reader-back').addEventListener('click', () => history.back());
  document.getElementById('reader-prev').addEventListener('click', () => navTo('reader-prev'));
  document.getElementById('reader-next').addEventListener('click', () => navTo('reader-next'));

  // Reveal the date in the reader bar only after the big heading scrolls away.
  const barTitle = document.getElementById('reader-bar-title');
  readerScroll.addEventListener('scroll', () => {
    barTitle.classList.toggle('show', readerScroll.scrollTop > 56);
  }, { passive: true });

  // Keyboard (desktop / external keyboards)
  document.addEventListener('keydown', ev => {
    if (reader.hidden) return;
    if (ev.key === 'Escape') history.back();
    else if (ev.key === 'ArrowLeft') navTo('reader-prev');
    else if (ev.key === 'ArrowRight') navTo('reader-next');
  });

  // Swipe navigation inside the reader.
  let sx = 0, sy = 0, tracking = false;
  readerScroll.addEventListener('touchstart', e => {
    if (e.touches.length !== 1) { tracking = false; return; }
    sx = e.touches[0].clientX; sy = e.touches[0].clientY; tracking = true;
  }, { passive: true });
  readerScroll.addEventListener('touchend', e => {
    if (!tracking) return;
    tracking = false;
    const dx = e.changedTouches[0].clientX - sx;
    const dy = e.changedTouches[0].clientY - sy;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.8) {
      if (dx < 0) navTo('reader-next');   // swipe left -> later
      else navTo('reader-prev');          // swipe right -> earlier
    }
  }, { passive: true });
}

/* ---------- Boot ---------- */
async function boot() {
  buildChips();
  setupSearch();
  wireGlobal();

  try {
    const res = await fetch('data/posts.json', { cache: 'force-cache' });
    ALL = await res.json();
  } catch (err) {
    feedStatus.textContent = 'Could not load the journal data.';
    document.getElementById('splash').classList.add('hide');
    return;
  }

  renderFeed();
  initRoute(); // honor deep links

  const splash = document.getElementById('splash');
  splash.classList.add('hide');
  setTimeout(() => splash.remove(), 450);

  // Warm the search index during idle time so the first search is instant.
  const idle = window.requestIdleCallback || (cb => setTimeout(cb, 200));
  idle(buildIndex);

  if ('serviceWorker' in navigator && !/[?&]nosw/.test(location.search)) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
