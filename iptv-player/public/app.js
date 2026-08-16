/* ==========================================================================
   Tivi Web — frontend
   Vanilla ES modules, no build step. Virtualised lists keep it fast even
   with playlists of several thousand channels.
   ========================================================================== */

const $ = (id) => document.getElementById(id);

const LS = {
  settings: 'tivi.settings',
  favs: 'tivi.favs',
  last: 'tivi.last',
};

const DEFAULT_SETTINGS = {
  playlists: 'BCU Media | https://bcumedia.su/playlist/hls/ucbaaspl8i.m3u',
  epgs: 'https://epg.bcumedia.pro/epg.xml',
  autoplay: true,
  proxy: true,
};

const PX_PER_MIN = 6;          // guide horizontal scale
const GUIDE_SPAN_H = 30;       // hours rendered in the guide
const HOUR_PX = 60 * PX_PER_MIN;

const state = {
  settings: { ...DEFAULT_SETTINGS },
  channels: [],        // all channels from all playlists
  filtered: [],        // channels currently listed (group + search applied)
  epgByChan: new Map(),// channel index -> programme array
  epgRaw: null,        // { channels, programmes } merged
  group: 'all',
  query: '',
  current: -1,         // index into state.channels
  cursor: 0,           // keyboard cursor into state.filtered
  favs: new Set(),
  guideStart: 0,       // ms, left edge of guide viewport content
  guideOpen: false,
};

// ── utils ─────────────────────────────────────────────────────────────────

const pad = (n) => (n < 10 ? '0' + n : '' + n);
const hhmm = (ms) => { const d = new Date(ms); return pad(d.getHours()) + ':' + pad(d.getMinutes()); };
const dayLabel = (ms) => {
  const d = new Date(ms), t = new Date();
  const same = (a, b) => a.toDateString() === b.toDateString();
  const tom = new Date(t.getTime() + 864e5), yes = new Date(t.getTime() - 864e5);
  if (same(d, t)) return 'Dnes';
  if (same(d, tom)) return 'Zítra';
  if (same(d, yes)) return 'Včera';
  return d.toLocaleDateString('cs-CZ', { weekday: 'short', day: 'numeric', month: 'numeric' });
};
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Normalised key used to match playlist channels to EPG entries by name.
function norm(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/\(.*?\)|\[.*?\]/g, ' ')
    .replace(/\b(uhd|fhd|hd|sd|4k|hevc|h265|h264|raw|backup|plus)\b/g, ' ')
    .replace(/[^a-z0-9]+/g, '');
}

let toastTimer;
function toast(msg, ms = 2600) {
  const t = $('toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), ms);
}

// ── storage ───────────────────────────────────────────────────────────────

function loadSettings() {
  try {
    const raw = localStorage.getItem(LS.settings);
    if (raw) state.settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {}
  try {
    const f = localStorage.getItem(LS.favs);
    if (f) state.favs = new Set(JSON.parse(f));
  } catch {}
}
const saveSettings = () => localStorage.setItem(LS.settings, JSON.stringify(state.settings));
const saveFavs = () => localStorage.setItem(LS.favs, JSON.stringify([...state.favs]));

function parseLines(text) {
  return String(text || '')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const i = l.indexOf('|');
      if (i !== -1 && /^https?:/i.test(l.slice(i + 1).trim())) {
        return { name: l.slice(0, i).trim(), url: l.slice(i + 1).trim() };
      }
      return { name: '', url: l };
    })
    .filter((e) => /^https?:/i.test(e.url));
}

// ── data loading ──────────────────────────────────────────────────────────

async function loadAll({ silent = false } = {}) {
  const pls = parseLines(state.settings.playlists);
  const epgs = parseLines(state.settings.epgs);

  if (!pls.length) {
    renderList();
    setFoot('Žádný playlist — otevři nastavení.');
    return;
  }
  if (!silent) setFoot('Načítám playlist…');

  // playlists first: the UI is usable as soon as they land
  const results = await Promise.allSettled(
    pls.map((p) => fetch('/api/playlist?url=' + encodeURIComponent(p.url)).then(async (r) => {
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
      return { src: p.name || new URL(p.url).hostname, data: j };
    }))
  );

  const chans = [];
  const errs = [];
  for (const r of results) {
    if (r.status === 'fulfilled') {
      for (const c of r.value.data.channels) chans.push({ ...c, id: chans.length, src: r.value.src });
    } else {
      errs.push(r.reason.message || String(r.reason));
    }
  }
  state.channels = chans;
  if (errs.length) toast('Playlist se nepodařilo načíst: ' + errs[0], 5000);

  buildGroups();
  applyFilter();
  setFoot(`${chans.length} kanálů · EPG se načítá…`);

  // restore last channel
  if (state.settings.autoplay && state.current === -1) {
    const last = localStorage.getItem(LS.last);
    if (last) {
      const i = state.channels.findIndex((c) => c.url === last);
      if (i !== -1) play(i, { quiet: true });
    }
  }

  // EPG in the background — big files shouldn't block the channel list
  if (epgs.length) {
    const eres = await Promise.allSettled(
      epgs.map((e) => fetch('/api/epg?url=' + encodeURIComponent(e.url)).then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
        return j;
      }))
    );
    const merged = { channels: {}, programmes: {} };
    let okCount = 0, epgErr = '';
    for (const r of eres) {
      if (r.status !== 'fulfilled') { epgErr = r.reason.message || String(r.reason); continue; }
      okCount++;
      Object.assign(merged.channels, r.value.channels);
      for (const [k, v] of Object.entries(r.value.programmes)) {
        merged.programmes[k] = (merged.programmes[k] || []).concat(v);
      }
    }
    for (const k of Object.keys(merged.programmes)) merged.programmes[k].sort((a, b) => a.s - b.s);
    state.epgRaw = merged;
    indexEpg();
    renderList();
    renderEpgHits(); // a search typed while the guide was still loading
    if (state.current !== -1) updateOsd();
    const progs = Object.values(merged.programmes).reduce((a, b) => a + b.length, 0);
    setFoot(`${state.channels.length} kanálů · ${progs.toLocaleString('cs-CZ')} pořadů`);
    if (!okCount && epgErr) toast('EPG se nepodařilo načíst: ' + epgErr, 5000);
  } else {
    setFoot(`${state.channels.length} kanálů · bez EPG`);
  }
}

/** Map playlist channels onto EPG programme lists (tvg-id first, name second). */
function indexEpg() {
  state.epgByChan = new Map();
  if (!state.epgRaw) return;
  const { channels: ec, programmes } = state.epgRaw;

  const byNorm = new Map();
  for (const [id, meta] of Object.entries(ec)) {
    for (const key of [norm(meta.name), norm(id)]) {
      if (key && !byNorm.has(key)) byNorm.set(key, id);
    }
  }
  // EPG ids that have programmes but no <channel> entry
  for (const id of Object.keys(programmes)) {
    const k = norm(id);
    if (k && !byNorm.has(k)) byNorm.set(k, id);
  }

  for (const c of state.channels) {
    let progs = c.tvgId && programmes[c.tvgId];
    if (!progs) {
      const id = byNorm.get(norm(c.tvgId)) || byNorm.get(norm(c.tvgName)) || byNorm.get(norm(c.name));
      if (id) progs = programmes[id];
    }
    if (progs && progs.length) {
      state.epgByChan.set(c.id, progs);
      if (!c.logo && state.epgRaw.channels[c.tvgId]?.icon) c.logo = state.epgRaw.channels[c.tvgId].icon;
    }
  }
}

/** Currently airing programme + the one after it. */
function nowNext(chanIdx, at = Date.now()) {
  const list = state.epgByChan.get(chanIdx);
  if (!list) return [null, null];
  let lo = 0, hi = list.length - 1, found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (list[mid].s <= at) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  if (found === -1) return [null, list[0] || null];
  const cur = list[found];
  return [at < cur.e ? cur : null, list[found + 1] || null];
}

// ── groups & filtering ────────────────────────────────────────────────────

let groupList = [];
function buildGroups() {
  const counts = new Map();
  for (const c of state.channels) counts.set(c.group, (counts.get(c.group) || 0) + 1);
  groupList = [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'cs'));
  renderGroups();
}

function renderGroups() {
  const favN = state.favs.size;
  const items = [
    ['all', 'Vše', state.channels.length],
    ...(favN ? [['fav', '★ Oblíbené', favN]] : []),
    ...groupList.map(([g, n]) => [g, g, n]),
  ];
  $('groups').innerHTML = items
    .map(([k, label, n]) =>
      `<button class="chip${state.group === k ? ' on' : ''}" data-g="${esc(k)}">${esc(label)}<span class="n">${n}</span></button>`)
    .join('');
}

function applyFilter() {
  const q = state.query.trim().toLowerCase();
  let list = state.channels;
  if (state.group === 'fav') list = list.filter((c) => state.favs.has(c.url));
  else if (state.group !== 'all') list = list.filter((c) => c.group === state.group);
  if (q) {
    list = list.filter((c) =>
      c.name.toLowerCase().includes(q) ||
      (c.tvgName && c.tvgName.toLowerCase().includes(q)) ||
      c.group.toLowerCase().includes(q));
  }
  state.filtered = list;
  state.cursor = Math.min(state.cursor, Math.max(0, list.length - 1));
  renderList();
  scheduleEpgHits();
}

// ── programme search across every channel ─────────────────────────────────

/**
 * Find programmes matching `q` on any channel, from the ones airing right now
 * into the future — the "which station is the match on?" question.
 */
function searchProgrammes(q) {
  q = q.trim().toLowerCase();
  if (q.length < 2) return [];
  const now = Date.now();
  const hits = [];
  for (const c of state.channels) {
    const list = state.epgByChan.get(c.id);
    if (!list) continue;
    for (const p of list) {
      if (p.e < now) continue; // already over
      if (p.t.toLowerCase().includes(q) || (p.d && p.d.toLowerCase().includes(q))) {
        hits.push({ p, c });
      }
    }
  }
  return hits.sort((a, b) => a.p.s - b.p.s);
}

// ── virtualised channel list ──────────────────────────────────────────────

const listEl = $('chanList');
let rowH = 62;
let spacer, viewport, hitsEl, emptyEl;

function initList() {
  // The virtual viewport is absolutely positioned, so anything it renders would
  // overlap what follows. The empty notice lives in normal flow instead.
  listEl.innerHTML =
    '<div class="vspacer" style="position:relative"><div class="vview" style="position:absolute;top:0;left:0;right:0"></div></div>' +
    '<div class="list-empty" id="listEmpty" hidden></div>' +
    '<div class="epg-hits" id="epgHits" hidden></div>';
  spacer = listEl.firstElementChild;
  viewport = spacer.firstElementChild;
  emptyEl = $('listEmpty');
  hitsEl = $('epgHits');
  listEl.addEventListener('scroll', () => renderList(true), { passive: true });
  const measure = () => {
    const v = getComputedStyle(document.documentElement).getPropertyValue('--row-h');
    rowH = parseInt(v) || 62;
  };
  measure();
  window.addEventListener('resize', () => { measure(); renderList(); });
}

function rowHtml(c, i) {
  const [now, next] = nowNext(c.id);
  let epgHtml = '';
  if (now) {
    const pct = Math.max(0, Math.min(100, ((Date.now() - now.s) / (now.e - now.s)) * 100));
    epgHtml =
      `<div class="now"><span class="t">${esc(now.t)}</span></div>` +
      `<div class="prog"><i style="width:${pct.toFixed(1)}%"></i></div>`;
  } else if (next) {
    epgHtml = `<div class="now"><span class="t">Další: ${esc(next.t)} v ${hhmm(next.s)}</span></div>`;
  }
  const fav = state.favs.has(c.url);
  const initials = esc(c.name.replace(/[^A-Za-z0-9]/g, '').slice(0, 3).toUpperCase() || '?');
  const logo = `<span class="fallback">${initials}</span>` + (c.logo
    ? `<img src="${esc(c.logo)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">`
    : '');

  return `<div class="row${state.current === c.id ? ' active' : ''}${state.cursor === i ? ' cursor' : ''}"
     style="position:absolute;top:${i * rowH}px;left:0;right:0" data-i="${i}" title="${esc(c.name)}">
    <span class="num">${esc(c.chno || i + 1)}</span>
    <span class="logo">${logo}</span>
    <span class="info"><span class="cname">${esc(c.name)}</span>${epgHtml}</span>
    <button class="fav${fav ? ' on' : ''}" data-fav="${i}" title="Oblíbené">
      <svg viewBox="0 0 24 24" fill="${fav ? 'currentColor' : 'none'}"><path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/></svg>
    </button>
  </div>`;
}

function renderList(scrollOnly = false) {
  if (!spacer) return;
  const n = state.filtered.length;
  spacer.style.height = n * rowH + 'px';

  if (!n) {
    viewport.innerHTML = '';
    emptyEl.textContent = state.channels.length ? 'Žádný kanál nenalezen' : 'Načítám…';
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;
  const top = listEl.scrollTop;
  const h = listEl.clientHeight || 600;
  const first = Math.max(0, Math.floor(top / rowH) - 6);
  const last = Math.min(n, Math.ceil((top + h) / rowH) + 6);

  if (scrollOnly && viewport.dataset.f == first && viewport.dataset.l == last) return;
  viewport.dataset.f = first;
  viewport.dataset.l = last;

  let html = '';
  for (let i = first; i < last; i++) html += rowHtml(state.filtered[i], i);
  viewport.innerHTML = html;
}

const SIDE_HITS_MAX = 60;
let epgHitsTimer;

function scheduleEpgHits() {
  clearTimeout(epgHitsTimer);
  epgHitsTimer = setTimeout(renderEpgHits, 180);
}

function renderEpgHits() {
  if (!hitsEl) return;
  const q = state.query.trim();
  if (q.length < 2 || !state.epgByChan.size) {
    hitsEl.hidden = true;
    hitsEl.innerHTML = '';
    return;
  }
  const hits = searchProgrammes(q);
  if (!hits.length) {
    hitsEl.hidden = true;
    hitsEl.innerHTML = '';
    return;
  }
  const shown = hits.slice(0, SIDE_HITS_MAX);
  const now = Date.now();

  hitsEl.hidden = false;
  hitsEl.innerHTML =
    `<div class="ehit-head">V programu · <b>${hits.length}</b>` +
    `${hits.length > SIDE_HITS_MAX ? ` (prvních ${SIDE_HITS_MAX})` : ''}</div>` +
    shown.map((h, i) => {
      const live = h.p.s <= now && now < h.p.e;
      return `<div class="ehit${live ? ' live' : ''}" data-h="${i}" title="${esc(h.p.t)}">
        <span class="ehit-when">${live
          ? '<b class="lv">ŽIVĚ</b>'
          : `<b>${esc(dayLabel(h.p.s))}</b><span>${hhmm(h.p.s)}</span>`}</span>
        <span class="ehit-body">
          <span class="ehit-t">${esc(h.p.t)}</span>
          <span class="ehit-c">${esc(h.c.name)}</span>
        </span>
      </div>`;
    }).join('');
  hitsEl._hits = shown;
}

listEl.addEventListener('click', (e) => {
  const hit = e.target.closest('.ehit[data-h]');
  if (hit) {
    const h = hitsEl._hits[+hit.dataset.h];
    if (h) openDetail(h.p, h.c.id);
    return;
  }
  const favBtn = e.target.closest('[data-fav]');
  if (favBtn) {
    e.stopPropagation();
    const c = state.filtered[+favBtn.dataset.fav];
    if (state.favs.has(c.url)) state.favs.delete(c.url); else state.favs.add(c.url);
    saveFavs();
    renderGroups();
    if (state.group === 'fav') applyFilter(); else renderList();
    return;
  }
  const row = e.target.closest('[data-i]');
  if (!row) return;
  const i = +row.dataset.i;
  state.cursor = i;
  play(state.filtered[i].id);
});

$('groups').addEventListener('click', (e) => {
  const chip = e.target.closest('[data-g]');
  if (!chip) return;
  state.group = chip.dataset.g;
  renderGroups();
  listEl.scrollTop = 0;
  applyFilter();
});

$('chanSearch').addEventListener('input', (e) => {
  state.query = e.target.value;
  listEl.scrollTop = 0;
  applyFilter();
});

const setFoot = (txt) => { $('sideFoot').innerHTML = `<span>${esc(txt)}</span>`; };

// ── player ────────────────────────────────────────────────────────────────

const video = $('video');
let hls = null;

function streamUrl(u) {
  return state.settings.proxy ? '/stream?url=' + encodeURIComponent(u) : u;
}

function destroyHls() {
  if (hls) { try { hls.destroy(); } catch {} hls = null; }
}

function showError(msg) {
  $('spinner').hidden = true;
  // Live streams routinely emit fatal errors that hls.js recovers from on its
  // own. If pictures are still coming, there is nothing to tell the user about.
  if (!video.paused && !video.ended && video.readyState >= 3) return;
  $('stageErrorMsg').textContent = msg;
  $('stageError').hidden = false;
}

function play(chanIdx, { quiet = false } = {}) {
  const c = state.channels[chanIdx];
  if (!c) return;
  state.current = chanIdx;
  localStorage.setItem(LS.last, c.url);

  $('stageEmpty').hidden = true;
  $('stageError').hidden = true;
  $('spinner').hidden = false;
  renderList();
  updateOsd(true);

  const src = streamUrl(c.url);
  destroyHls();
  video.pause();
  video.removeAttribute('src');
  video.load();

  const isHls = /\.m3u8?($|\?)/i.test(c.url) || !/\.(mp4|mkv|webm|ts)($|\?)/i.test(c.url);
  const Hls = window.Hls;

  if (isHls && Hls && Hls.isSupported()) {
    hls = new Hls({
      lowLatencyMode: false,
      enableWorker: true,
      backBufferLength: 60,
      maxBufferLength: 24,
      manifestLoadingTimeOut: 20000,
      fragLoadingTimeOut: 30000,
      manifestLoadingMaxRetry: 3,
      levelLoadingMaxRetry: 4,
    });
    hls.loadSource(src);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
    hls.on(Hls.Events.LEVEL_SWITCHED, (_e, d) => {
      const lv = hls.levels[d.level];
      const pill = $('qualityPill');
      if (lv && lv.height) { pill.textContent = lv.height + 'p'; pill.hidden = false; }
      else pill.hidden = true;
    });
    hls.on(Hls.Events.ERROR, (_e, data) => {
      if (!data.fatal) return;
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad();
      else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError();
      else { destroyHls(); showError(`${data.details || data.type}`); }
    });
  } else {
    video.src = src;
    video.play().catch(() => {});
  }

  if (!quiet) flashOsd();
}

video.addEventListener('playing', () => {
  $('spinner').hidden = true;
  $('stageError').hidden = true;
});
// clears a dialog left over from an error the stream already recovered from
video.addEventListener('timeupdate', () => {
  if (!$('stageError').hidden) $('stageError').hidden = true;
});
video.addEventListener('waiting', () => { $('spinner').hidden = false; });
video.addEventListener('error', () => {
  if (!hls) showError('Přehrávání selhalo — zkus jiný kanál nebo vypni proxy v nastavení.');
});
$('retryBtn').addEventListener('click', () => state.current !== -1 && play(state.current));

// ── OSD ───────────────────────────────────────────────────────────────────

let osdTimer;
function flashOsd(ms = 5000) {
  updateOsd(true);
  $('osd').hidden = false;
  clearTimeout(osdTimer);
  osdTimer = setTimeout(() => ($('osd').hidden = true), ms);
}

function updateOsd(force = false) {
  if (state.current === -1) return;
  if (!force && $('osd').hidden) return;
  const c = state.channels[state.current];
  const [now, next] = nowNext(c.id);

  $('osdLogo').src = c.logo || '';
  $('osdLogo').style.display = c.logo ? '' : 'none';
  $('osdNum').textContent = c.chno || '';
  $('osdName').textContent = c.name;
  $('osdBadges').innerHTML = '<span class="pill live">ŽIVĚ</span>';

  if (now) {
    const pct = ((Date.now() - now.s) / (now.e - now.s)) * 100;
    $('osdProg').textContent = now.t;
    $('osdBarFill').style.width = Math.max(0, Math.min(100, pct)) + '%';
    $('osdStart').textContent = hhmm(now.s);
    $('osdEnd').textContent = hhmm(now.e);
    $('osdNext').innerHTML = next ? `Pak: <b>${esc(next.t)}</b> · ${hhmm(next.s)}` : '';
  } else {
    $('osdProg').textContent = state.epgByChan.has(c.id) ? '—' : 'Bez EPG';
    $('osdBarFill').style.width = '0%';
    $('osdStart').textContent = '';
    $('osdEnd').textContent = '';
    $('osdNext').innerHTML = next ? `Další: <b>${esc(next.t)}</b> · ${hhmm(next.s)}` : '';
  }
}

$('stage').addEventListener('mousemove', () => { if (state.current !== -1) flashOsd(3500); });
$('stage').addEventListener('dblclick', toggleFs);

// ── controls ──────────────────────────────────────────────────────────────

function toggleFs() {
  const el = $('stage');
  if (!document.fullscreenElement) el.requestFullscreen?.().catch(() => {});
  else document.exitFullscreen?.();
}
$('btnFs').addEventListener('click', toggleFs);
$('btnPip').addEventListener('click', () => {
  if (document.pictureInPictureElement) document.exitPictureInPicture();
  else video.requestPictureInPicture?.().catch(() => toast('PiP není podporováno'));
});
$('btnMute').addEventListener('click', () => {
  video.muted = !video.muted;
  $('btnMute').classList.toggle('on', video.muted);
});
$('volume').addEventListener('input', (e) => {
  video.volume = e.target.value / 100;
  video.muted = e.target.value === '0';
});
$('sidebarToggle').addEventListener('click', () => $('app').classList.remove('hide-side'));

// ── EPG guide ─────────────────────────────────────────────────────────────

const gridInner = $('gridInner');
const guideGrid = $('guideGrid');
const guideNames = $('guideNames');
const timebarInner = $('timebarInner');
let guideRowH = 56;

function openGuide() {
  if (!state.channels.length) { toast('Nejdřív se musí načíst playlist'); return; }
  state.guideOpen = true;
  $('guide').hidden = false;
  guideRowH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--guide-row-h')) || 56;
  const now = Date.now();
  state.guideStart = now - (now % (30 * 60000)) - 30 * 60000;
  buildDaySelect();
  renderGuide();
  requestAnimationFrame(() => scrollGuideToNow());
}
function closeGuide() {
  state.guideOpen = false;
  $('guide').hidden = true;
  $('searchResults').hidden = true;
  $('progSearch').value = '';
}
$('btnGuide').addEventListener('click', openGuide);
$('guideClose').addEventListener('click', closeGuide);

function buildDaySelect() {
  const sel = $('gDay');
  const base = new Date();
  base.setHours(0, 0, 0, 0);
  let html = '';
  for (let d = -1; d <= 6; d++) {
    const t = base.getTime() + d * 864e5;
    html += `<option value="${t}"${d === 0 ? ' selected' : ''}>${esc(dayLabel(t))}</option>`;
  }
  sel.innerHTML = html;
}
$('gDay').addEventListener('change', (e) => {
  const day = +e.target.value;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  state.guideStart = day === today.getTime()
    ? Date.now() - (Date.now() % 18e5) - 18e5
    : day;
  renderGuide();
  guideGrid.scrollLeft = 0;
});
$('gPrev').addEventListener('click', () => { guideGrid.scrollLeft -= 2 * HOUR_PX; });
$('gNext').addEventListener('click', () => { guideGrid.scrollLeft += 2 * HOUR_PX; });
$('gNow').addEventListener('click', () => {
  const now = Date.now();
  if (now < state.guideStart || now > state.guideStart + GUIDE_SPAN_H * 36e5) {
    state.guideStart = now - (now % 18e5) - 18e5;
    buildDaySelect();
    renderGuide();
  }
  scrollGuideToNow();
});
function scrollGuideToNow() {
  const x = ((Date.now() - state.guideStart) / 60000) * PX_PER_MIN;
  guideGrid.scrollLeft = Math.max(0, x - guideGrid.clientWidth * 0.25);
}

function renderGuide() {
  const chans = state.filtered.length ? state.filtered : state.channels;
  const totalW = GUIDE_SPAN_H * 60 * PX_PER_MIN;

  // time bar
  let tb = '';
  for (let m = 0; m <= GUIDE_SPAN_H * 60; m += 30) {
    const t = state.guideStart + m * 60000;
    const isHour = new Date(t).getMinutes() === 0;
    tb += `<div class="tick${isHour ? ' hour' : ''}" style="left:${m * PX_PER_MIN}px">${hhmm(t)}</div>`;
  }
  timebarInner.style.width = totalW + 'px';
  timebarInner.innerHTML = tb;

  // names column
  guideNames.innerHTML = chans.map((c, i) => {
    const logo = c.logo
      ? `<img src="${esc(c.logo)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">` : '';
    return `<div class="gname${state.current === c.id ? ' active' : ''}" data-ci="${c.id}" title="${esc(c.name)}">
      <span class="logo">${logo}</span>
      <span class="txt"><span class="n">${esc(c.name)}</span><span class="no">${esc(c.chno || i + 1)}</span></span>
    </div>`;
  }).join('');

  gridInner.style.width = totalW + 'px';
  gridInner.style.height = chans.length * guideRowH + 'px';
  $('nowline').style.height = chans.length * guideRowH + 'px';
  renderGuideBlocks();
  positionNowline();
}

/** Only the vertical slice in view gets programme blocks. */
function renderGuideBlocks() {
  const chans = state.filtered.length ? state.filtered : state.channels;
  const top = guideGrid.scrollTop;
  const h = guideGrid.clientHeight || 600;
  const first = Math.max(0, Math.floor(top / guideRowH) - 2);
  const last = Math.min(chans.length, Math.ceil((top + h) / guideRowH) + 2);
  const start = state.guideStart;
  const end = start + GUIDE_SPAN_H * 36e5;
  const now = Date.now();

  let html = '';
  for (let i = first; i < last; i++) {
    const c = chans[i];
    const list = state.epgByChan.get(c.id);
    const y = i * guideRowH;
    if (!list || !list.length) {
      html += `<div class="pblock" style="left:0;top:${y}px;width:${GUIDE_SPAN_H * 60 * PX_PER_MIN}px" data-ci="${c.id}">
        <span class="pt" style="color:var(--txt-3)">Bez EPG</span></div>`;
      continue;
    }
    for (const p of list) {
      if (p.e <= start || p.s >= end) continue;
      const x = ((p.s - start) / 60000) * PX_PER_MIN;
      const w = ((p.e - p.s) / 60000) * PX_PER_MIN;
      const live = p.s <= now && now < p.e;
      const past = p.e <= now;
      html += `<div class="pblock${live ? ' live' : ''}${past ? ' past' : ''}"
        style="left:${Math.max(0, x).toFixed(0)}px;top:${y}px;width:${Math.max(24, w + Math.min(0, x)).toFixed(0)}px"
        data-ci="${c.id}" data-s="${p.s}" title="${esc(p.t)}">
        <span class="pt">${esc(p.t)}</span>
        <span class="ps">${hhmm(p.s)} – ${hhmm(p.e)}</span>
      </div>`;
    }
  }
  gridInner.innerHTML = html;
}

function positionNowline() {
  const x = ((Date.now() - state.guideStart) / 60000) * PX_PER_MIN;
  const line = $('nowline');
  const within = x >= 0 && x <= GUIDE_SPAN_H * 60 * PX_PER_MIN;
  line.hidden = !within;
  if (within) line.style.left = x + 'px';
}

guideGrid.addEventListener('scroll', () => {
  guideNames.scrollTop = guideGrid.scrollTop;
  timebarInner.style.transform = `translateX(${-guideGrid.scrollLeft}px)`;
  renderGuideBlocks();
}, { passive: true });

guideGrid.addEventListener('click', (e) => {
  const b = e.target.closest('.pblock');
  if (!b) return;
  const ci = +b.dataset.ci;
  if (!b.dataset.s) { play(ci); closeGuide(); return; }
  const list = state.epgByChan.get(ci) || [];
  const p = list.find((x) => x.s === +b.dataset.s);
  if (p) openDetail(p, ci);
});
guideNames.addEventListener('click', (e) => {
  const n = e.target.closest('[data-ci]');
  if (n) { play(+n.dataset.ci); closeGuide(); }
});

// ── programme search ──────────────────────────────────────────────────────

let searchTimer;
$('progSearch').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => runProgSearch(e.target.value), 160);
});

const GUIDE_HITS_MAX = 400;

function runProgSearch(q) {
  q = q.trim();
  const box = $('searchResults');
  if (q.length < 2) { box.hidden = true; return; }

  const now = Date.now();
  const all = searchProgrammes(q);
  const hits = all.slice(0, GUIDE_HITS_MAX);

  box.hidden = false;
  if (!hits.length) {
    box.innerHTML = `<div class="sr-head">Nic nenalezeno pro „${esc(q)}“.</div>`;
    return;
  }
  box.innerHTML =
    `<div class="sr-head">${all.length} výsledků` +
    `${all.length > GUIDE_HITS_MAX ? ` (zobrazeno prvních ${GUIDE_HITS_MAX})` : ''}</div>` +
    hits.map(({ p, c }, i) => {
      const live = p.s <= now && now < p.e;
      return `<div class="sr-item" data-h="${i}">
        <span class="sr-when"><b>${esc(dayLabel(p.s))}</b>${hhmm(p.s)} – ${hhmm(p.e)}</span>
        <span><span class="sr-t">${esc(p.t)}${live ? '<span class="sr-badge">ŽIVĚ</span>' : ''}</span>
          ${p.d ? `<span class="sr-d">${esc(p.d)}</span>` : ''}</span>
        <span class="sr-c">${esc(c.name)}</span>
      </div>`;
    }).join('');
  box._hits = hits;
}

$('searchResults').addEventListener('click', (e) => {
  const it = e.target.closest('[data-h]');
  if (!it) return;
  const hit = $('searchResults')._hits[+it.dataset.h];
  if (hit) openDetail(hit.p, hit.c.id);
});

// ── programme detail ──────────────────────────────────────────────────────

let detailChan = -1;
function openDetail(p, chanIdx) {
  detailChan = chanIdx;
  const c = state.channels[chanIdx];
  const now = Date.now();
  const live = p.s <= now && now < p.e;
  const mins = Math.round((p.e - p.s) / 60000);

  $('dWhen').textContent = `${dayLabel(p.s)} · ${hhmm(p.s)} – ${hhmm(p.e)} · ${mins} min${live ? ' · ŽIVĚ' : ''}`;
  $('dTitle').textContent = p.t;
  $('dChan').textContent = [c?.name, p.c].filter(Boolean).join(' · ');
  $('dDesc').textContent = p.d || 'Popis není k dispozici.';
  const wrap = $('dBarWrap');
  wrap.hidden = !live;
  if (live) $('dBar').style.width = (((now - p.s) / (p.e - p.s)) * 100).toFixed(1) + '%';
  $('detailBackdrop').hidden = false;
}
const closeDetail = () => ($('detailBackdrop').hidden = true);
$('detailClose').addEventListener('click', closeDetail);
$('detailBackdrop').addEventListener('click', (e) => { if (e.target.id === 'detailBackdrop') closeDetail(); });
$('dWatch').addEventListener('click', () => { if (detailChan !== -1) { play(detailChan); closeDetail(); closeGuide(); } });

// ── settings ──────────────────────────────────────────────────────────────

function openSettings() {
  $('setPlaylists').value = state.settings.playlists;
  $('setEpgs').value = state.settings.epgs;
  $('setAutoplay').checked = !!state.settings.autoplay;
  $('setProxy').checked = !!state.settings.proxy;
  $('setHint').textContent = '';
  $('setBackdrop').hidden = false;
}
$('btnSettings').addEventListener('click', openSettings);
$('setClose').addEventListener('click', () => ($('setBackdrop').hidden = true));
$('setBackdrop').addEventListener('click', (e) => { if (e.target.id === 'setBackdrop') $('setBackdrop').hidden = true; });
$('setSave').addEventListener('click', async () => {
  state.settings.playlists = $('setPlaylists').value;
  state.settings.epgs = $('setEpgs').value;
  state.settings.autoplay = $('setAutoplay').checked;
  state.settings.proxy = $('setProxy').checked;
  saveSettings();
  $('setHint').textContent = 'Načítám…';
  $('setBackdrop').hidden = true;
  await loadAll();
  toast('Nastavení uloženo');
});
$('setReload').addEventListener('click', async () => {
  $('setHint').textContent = 'Obnovuji…';
  await loadAll();
  $('setHint').textContent = 'Hotovo.';
});

// ── keyboard ──────────────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);

  if (e.key === 'Escape') {
    if (!$('detailBackdrop').hidden) return closeDetail();
    if (!$('setBackdrop').hidden) return ($('setBackdrop').hidden = true);
    if (state.guideOpen) {
      if (!$('searchResults').hidden) { $('progSearch').value = ''; $('searchResults').hidden = true; return; }
      return closeGuide();
    }
    if (typing) { e.target.blur(); return; }
    $('app').classList.toggle('hide-side');
    return;
  }
  if (typing) return;

  switch (e.key) {
    case '/':
      e.preventDefault();
      if (state.guideOpen) $('progSearch').focus(); else $('chanSearch').focus();
      break;
    case 'g': case 'G':
      state.guideOpen ? closeGuide() : openGuide();
      break;
    case 'f': case 'F': toggleFs(); break;
    case 'm': case 'M': $('btnMute').click(); break;
    case 'p': case 'P': $('btnPip').click(); break;
    case 'i': case 'I': flashOsd(6000); break;
    case 'ArrowDown':
      if (state.guideOpen) return;
      e.preventDefault(); moveCursor(1); break;
    case 'ArrowUp':
      if (state.guideOpen) return;
      e.preventDefault(); moveCursor(-1); break;
    case 'PageDown': e.preventDefault(); moveCursor(10); break;
    case 'PageUp': e.preventDefault(); moveCursor(-10); break;
    case 'Enter':
      if (state.guideOpen) return;
      if (state.filtered[state.cursor]) play(state.filtered[state.cursor].id);
      break;
  }
});

function moveCursor(d) {
  const n = state.filtered.length;
  if (!n) return;
  state.cursor = Math.max(0, Math.min(n - 1, state.cursor + d));
  const y = state.cursor * rowH;
  if (y < listEl.scrollTop) listEl.scrollTop = y;
  else if (y + rowH > listEl.scrollTop + listEl.clientHeight) listEl.scrollTop = y + rowH - listEl.clientHeight;
  renderList();
}

// ── periodic refresh ──────────────────────────────────────────────────────

setInterval(() => {
  updateOsd();
  if (!document.hidden) {
    renderList();
    if (state.guideOpen) positionNowline();
  }
}, 30000);

// ── boot ──────────────────────────────────────────────────────────────────

(async function boot() {
  loadSettings();
  initList();
  video.volume = 1;

  if (!window.Hls && window.__hlsFailed) {
    // vendored copy missing — fall back to the CDN build
    await new Promise((res) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js';
      s.onload = s.onerror = res;
      document.head.appendChild(s);
    });
  }
  await loadAll();
})();
