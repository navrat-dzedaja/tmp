/*
 * Tivi Web — TiviMate-style web IPTV player backend.
 *
 * Responsibilities:
 *  - serve the static frontend
 *  - fetch + parse m3u playlists  -> JSON  (/api/playlist)
 *  - fetch + parse XMLTV EPG      -> JSON  (/api/epg), gzip-aware
 *  - proxy HLS manifests/segments so the browser is never blocked by CORS (/stream)
 *
 * Everything is cached in memory so the UI stays snappy.
 */

const express = require('express');
const compression = require('compression');
const zlib = require('zlib');
const path = require('path');
const { Readable } = require('stream');

const PORT = process.env.PORT || 8098;
const UA = process.env.UPSTREAM_UA || 'VLC/3.0.20 LibVLC/3.0.20';

const PLAYLIST_TTL = 5 * 60 * 1000; // 5 min
const EPG_TTL = 30 * 60 * 1000; // 30 min
// EPG window we ship to the client: from 12h back to 48h ahead.
const EPG_PAST_MS = 12 * 3600 * 1000;
const EPG_FUTURE_MS = 48 * 3600 * 1000;

const app = express();
app.use(compression());
app.use(express.static(path.join(__dirname, 'public'), { maxAge: '1h', index: 'index.html' }));
app.use('/vendor', express.static(path.join(__dirname, 'node_modules/hls.js/dist'), { maxAge: '7d' }));

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

const cache = new Map(); // key -> { at, ttl, data }

function cacheGet(key) {
  const e = cache.get(key);
  if (e && Date.now() - e.at < e.ttl) return e.data;
  if (e) cache.delete(key);
  return null;
}

function cachePut(key, data, ttl) {
  cache.set(key, { at: Date.now(), ttl, data });
}

function isHttpUrl(u) {
  try {
    const p = new URL(u);
    return p.protocol === 'http:' || p.protocol === 'https:';
  } catch {
    return false;
  }
}

async function fetchBuffer(url, extraHeaders = {}) {
  const res = await fetch(url, {
    headers: { 'User-Agent': UA, ...extraHeaders },
    redirect: 'follow',
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`upstream ${res.status} for ${url}`);
  let buf = Buffer.from(await res.arrayBuffer());
  // transparently gunzip .xml.gz / mislabelled gzip payloads
  if (buf.length > 2 && buf[0] === 0x1f && buf[1] === 0x8b) {
    buf = zlib.gunzipSync(buf);
  }
  return { buf, finalUrl: res.url || url, contentType: res.headers.get('content-type') || '' };
}

const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&#39;': "'" };
function decodeEntities(s) {
  if (!s || s.indexOf('&') === -1) return s;
  return s
    .replace(/&(amp|lt|gt|quot|apos|#39);/g, (m) => ENTITIES[m])
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 16)));
}

// ---------------------------------------------------------------------------
// m3u parsing
// ---------------------------------------------------------------------------

function parseM3U(text) {
  const channels = [];
  const lines = text.split(/\r?\n/);
  let meta = null;
  let extgrp = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;

    if (line.startsWith('#EXTINF')) {
      meta = { name: '', attrs: {} };
      const comma = line.lastIndexOf(',');
      meta.name = comma !== -1 ? line.slice(comma + 1).trim() : '';
      const attrRe = /([A-Za-z0-9_-]+)="([^"]*)"/g;
      let m;
      while ((m = attrRe.exec(line))) meta.attrs[m[1].toLowerCase()] = m[2];
      // some playlists put the name only in tvg-name
      if (!meta.name && meta.attrs['tvg-name']) meta.name = meta.attrs['tvg-name'];
    } else if (line.startsWith('#EXTGRP:')) {
      extgrp = line.slice(8).trim();
    } else if (line.startsWith('#')) {
      continue;
    } else if (meta) {
      const a = meta.attrs;
      channels.push({
        id: channels.length,
        name: meta.name || line,
        url: line,
        tvgId: a['tvg-id'] || '',
        tvgName: a['tvg-name'] || meta.name,
        logo: a['tvg-logo'] || a['logo'] || '',
        group: a['group-title'] || extgrp || 'Uncategorized',
        chno: a['tvg-chno'] || a['ch-number'] || '',
      });
      meta = null;
    }
  }
  return channels;
}

app.get('/api/playlist', async (req, res) => {
  const url = req.query.url;
  if (!isHttpUrl(url)) return res.status(400).json({ error: 'invalid or missing url' });
  const key = 'pl:' + url;
  const hit = cacheGet(key);
  if (hit) return res.json(hit);
  try {
    const { buf } = await fetchBuffer(url);
    const channels = parseM3U(buf.toString('utf8'));
    const data = { fetchedAt: Date.now(), count: channels.length, channels };
    cachePut(key, data, PLAYLIST_TTL);
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
});

// ---------------------------------------------------------------------------
// XMLTV parsing
// ---------------------------------------------------------------------------

// "20260816143000 +0200" -> epoch ms
function parseXmltvTime(s) {
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?(?:\s*([+-])(\d{2})(\d{2}))?/.exec(s);
  if (!m) return NaN;
  let t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
  if (m[7]) {
    const off = (+m[8] * 60 + +m[9]) * 60000;
    t += m[7] === '+' ? -off : off;
  }
  return t;
}

function tagText(block, tag) {
  const m = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`).exec(block);
  return m ? decodeEntities(m[1].replace(/<[^>]+>/g, '').trim()) : '';
}

function parseXmltv(xml) {
  const now = Date.now();
  const minStop = now - EPG_PAST_MS;
  const maxStart = now + EPG_FUTURE_MS;

  const channels = {}; // id -> { name, icon }
  const chRe = /<channel\s+id="([^"]*)"[^>]*>([\s\S]*?)<\/channel>/g;
  let m;
  while ((m = chRe.exec(xml))) {
    const id = decodeEntities(m[1]);
    const body = m[2];
    const icon = /<icon[^>]*src="([^"]*)"/.exec(body);
    channels[id] = {
      name: tagText(body, 'display-name') || id,
      icon: icon ? decodeEntities(icon[1]) : '',
    };
  }

  const programmes = {}; // channelId -> [{s,e,t,d,c}]
  const progRe = /<programme\s+([^>]*)>([\s\S]*?)<\/programme>/g;
  while ((m = progRe.exec(xml))) {
    const attrs = m[1];
    const start = /start="([^"]*)"/.exec(attrs);
    const stop = /stop="([^"]*)"/.exec(attrs);
    const ch = /channel="([^"]*)"/.exec(attrs);
    if (!start || !ch) continue;
    const s = parseXmltvTime(start[1]);
    const e = stop ? parseXmltvTime(stop[1]) : s + 3600000;
    if (isNaN(s) || e < minStop || s > maxStart) continue;
    const cid = decodeEntities(ch[1]);
    const body = m[2];
    (programmes[cid] ||= []).push({
      s,
      e,
      t: tagText(body, 'title') || 'No title',
      d: tagText(body, 'desc'),
      c: tagText(body, 'category'),
    });
  }
  for (const cid of Object.keys(programmes)) programmes[cid].sort((a, b) => a.s - b.s);

  return { channels, programmes };
}

app.get('/api/epg', async (req, res) => {
  const url = req.query.url;
  if (!isHttpUrl(url)) return res.status(400).json({ error: 'invalid or missing url' });
  const key = 'epg:' + url;
  const hit = cacheGet(key);
  if (hit) return res.json(hit);
  try {
    const { buf } = await fetchBuffer(url);
    const parsed = parseXmltv(buf.toString('utf8'));
    const data = { fetchedAt: Date.now(), ...parsed };
    cachePut(key, data, EPG_TTL);
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
});

// ---------------------------------------------------------------------------
// stream proxy (CORS + manifest URL rewriting)
// ---------------------------------------------------------------------------

function proxied(absUrl) {
  return '/stream?url=' + encodeURIComponent(absUrl);
}

function rewriteManifest(text, baseUrl) {
  return text
    .split('\n')
    .map((line) => {
      const l = line.trim();
      if (!l) return line;
      if (l.startsWith('#')) {
        // rewrite URI="..." attributes (keys, maps, alt media, iframe playlists)
        return line.replace(/URI="([^"]+)"/g, (_, u) => {
          try {
            return `URI="${proxied(new URL(u, baseUrl).href)}"`;
          } catch {
            return `URI="${u}"`;
          }
        });
      }
      try {
        return proxied(new URL(l, baseUrl).href);
      } catch {
        return line;
      }
    })
    .join('\n');
}

app.get('/stream', async (req, res) => {
  const url = req.query.url;
  if (!isHttpUrl(url)) return res.status(400).send('invalid url');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const headers = { 'User-Agent': UA };
  if (req.headers.range) headers.Range = req.headers.range;

  let upstream;
  try {
    upstream = await fetch(url, { headers, redirect: 'follow', signal: AbortSignal.timeout(30000) });
  } catch (e) {
    return res.status(502).send('upstream fetch failed: ' + String(e.message || e));
  }
  if (!upstream.ok && upstream.status !== 206) {
    return res.status(upstream.status).send('upstream error ' + upstream.status);
  }

  const finalUrl = upstream.url || url;
  const ct = (upstream.headers.get('content-type') || '').toLowerCase();
  const looksLikeManifest =
    ct.includes('mpegurl') || ct.includes('m3u') || /\.m3u8?($|\?)/i.test(new URL(finalUrl).pathname);

  if (looksLikeManifest) {
    try {
      const text = Buffer.from(await upstream.arrayBuffer()).toString('utf8');
      if (text.startsWith('#EXTM3U')) {
        res.setHeader('Content-Type', 'application/vnd.apple.mpegurl');
        res.setHeader('Cache-Control', 'no-store');
        return res.send(rewriteManifest(text, finalUrl));
      }
      // not actually a manifest — pass through as-is
      res.setHeader('Content-Type', ct || 'application/octet-stream');
      return res.send(Buffer.from(text, 'utf8'));
    } catch (e) {
      return res.status(502).send('manifest read failed');
    }
  }

  // binary passthrough (segments, keys, direct streams)
  res.status(upstream.status);
  for (const h of ['content-type', 'content-length', 'content-range', 'accept-ranges']) {
    const v = upstream.headers.get(h);
    if (v) res.setHeader(h, v);
  }
  res.setHeader('Cache-Control', 'no-store');

  // Readable.fromWeb() locks upstream.body, so tearing down on client
  // disconnect has to go through the Node stream — cancelling the web stream
  // directly throws ERR_INVALID_STATE and would take the process down.
  const body = Readable.fromWeb(upstream.body);
  body.on('error', () => res.destroy());
  res.on('close', () => body.destroy());
  body.pipe(res);
});

app.get('/api/health', (_req, res) => res.json({ ok: true, uptime: process.uptime() }));

// A single misbehaving stream must never take the whole player down.
process.on('uncaughtException', (e) => console.error('[uncaught]', e && e.message));
process.on('unhandledRejection', (e) => console.error('[unhandled]', e && e.message));

app.listen(PORT, () => {
  console.log(`Tivi Web listening on http://0.0.0.0:${PORT}`);
});
