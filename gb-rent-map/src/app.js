(function () {
  "use strict";

  var MONTHS = RENT.months;
  var CAT_ORDER = ["all", "bed1", "bed2", "bed3", "bed4"];
  var CAT_LABELS = RENT.categories;
  var METRIC_LABELS = {
    price: "Průměrné nájemné",
    index: "Index nájmů",
    yoy: "Meziroční změna",
    mom: "Měsíční změna"
  };
  var CZ_MONTHS_FULL = ["leden", "únor", "březen", "duben", "květen", "červen", "červenec", "srpen", "září", "říjen", "listopad", "prosinec"];
  var CZ_MONTHS_SHORT = ["Led", "Úno", "Bře", "Dub", "Kvě", "Čvn", "Čvc", "Srp", "Zář", "Říj", "Lis", "Pro"];

  function parseYM(ym) {
    var parts = ym.split("-");
    return { y: +parts[0], m: +parts[1] };
  }
  function monthShort(ym) {
    var d = parseYM(ym);
    return CZ_MONTHS_SHORT[d.m - 1] + " " + d.y;
  }
  function monthFull(ym) {
    var d = parseYM(ym);
    return CZ_MONTHS_FULL[d.m - 1] + " " + d.y;
  }

  var state = {
    level: "local",
    category: "all",
    metric: "price",
    monthIndex: MONTHS.length - 1,
    selectedCode: null,
    playing: false
  };

  // ---------- colour scales (read live from CSS custom properties so light/dark stay in sync) ----------
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function hexToRgb(hex) {
    hex = hex.replace("#", "");
    if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    var n = parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgbToHex(rgb) {
    return "#" + rgb.map(function (v) {
      return Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0");
    }).join("");
  }
  function lerp3(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  }
  function multiStop(stops, t) {
    t = Math.max(0, Math.min(1, t));
    var n = stops.length - 1;
    var seg = Math.min(n - 1, Math.floor(t * n));
    var localT = t * n - seg;
    return rgbToHex(lerp3(hexToRgb(stops[seg]), hexToRgb(stops[seg + 1]), localT));
  }

  function getSeqStops() {
    return ["--seq-0", "--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5"].map(cssVar);
  }
  function getDivStops() {
    return [cssVar("--div-lo"), cssVar("--div-mid"), cssVar("--div-hi")];
  }
  function seqColor(value, min, max) {
    var t = max > min ? (value - min) / (max - min) : 0.5;
    return multiStop(getSeqStops(), t);
  }
  function divColor(value, absMax) {
    if (!(absMax > 0)) return cssVar("--div-mid");
    var t = Math.max(-1, Math.min(1, value / absMax));
    var stops = getDivStops();
    if (t < 0) return multiStop([stops[0], stops[1]], t + 1);
    return multiStop([stops[1], stops[2]], t);
  }
  function isDiverging(metric) {
    return metric === "mom" || metric === "yoy";
  }

  // ---------- data access ----------
  function getRecord(level, code) {
    return RENT.levels[level][code];
  }
  function getValue(level, code, cat, metric, mIdx) {
    var rec = getRecord(level, code);
    if (!rec) return null;
    var s = rec.series[cat];
    if (!s) return null;
    if (metric === "price") return s.price[mIdx];
    if (metric === "index") return s.index[mIdx];
    if (metric === "mom") {
      if (mIdx < 1) return null;
      var a = s.index[mIdx], b = s.index[mIdx - 1];
      if (a == null || b == null || b === 0) return null;
      return (a / b - 1) * 100;
    }
    if (metric === "yoy") {
      if (mIdx < 12) return null;
      var c = s.index[mIdx], d = s.index[mIdx - 12];
      if (c == null || d == null || d === 0) return null;
      return (c / d - 1) * 100;
    }
    return null;
  }
  function formatValue(metric, value) {
    if (value == null || isNaN(value)) return "–";
    if (metric === "price") return "£" + Math.round(value).toLocaleString("en-GB");
    if (metric === "index") return value.toFixed(1);
    var sign = value >= 0 ? "+" : "";
    return sign + value.toFixed(1) + "%";
  }
  function regionLabel(level, code, rec) {
    if (level === "local") return rec && rec.region ? rec.region : "";
    if (level === "region") {
      if (code.indexOf("E12") === 0) return "Anglie";
      if (code.indexOf("W92") === 0) return "Wales";
      if (code.indexOf("S92") === 0) return "Skotsko";
    }
    return "";
  }

  // ---------- Leaflet setup ----------
  var map = L.map("map", {
    zoomControl: true,
    attributionControl: false,
    minZoom: 4,
    maxZoom: 11,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
    worldCopyJump: false
  }).setView([54.5, -3.2], 5.3);

  var currentGeoLayer = null;
  var layersByCode = {};

  var NODATA_COLOR = "#c9c3b6";
  function nodataColor() { return cssVar("--nodata"); }
  function outlineColor() { return cssVar("--map-outline"); }
  function accentColor() { return cssVar("--accent"); }
  function accent2Color() { return cssVar("--accent-2"); }

  var domainCache = { min: 0, max: 0, absMax: 0 };

  function computeDomain() {
    var codes = Object.keys(RENT.levels[state.level]);
    var min = Infinity, max = -Infinity, absMax = 0;
    for (var i = 0; i < codes.length; i++) {
      var v = getValue(state.level, codes[i], state.category, state.metric, state.monthIndex);
      if (v == null) continue;
      if (v < min) min = v;
      if (v > max) max = v;
      if (Math.abs(v) > absMax) absMax = Math.abs(v);
    }
    if (!isFinite(min)) { min = 0; max = 1; }
    domainCache = { min: min, max: max, absMax: absMax || 1 };
  }

  function colorForValue(value) {
    if (value == null) return nodataColor();
    if (isDiverging(state.metric)) return divColor(value, domainCache.absMax);
    return seqColor(value, domainCache.min, domainCache.max);
  }

  function baseStyle(code, value) {
    var selected = code === state.selectedCode;
    return {
      fillColor: colorForValue(value),
      fillOpacity: value == null ? 0.55 : 0.88,
      color: selected ? accentColor() : outlineColor(),
      weight: selected ? 2.6 : 0.9,
      opacity: 1
    };
  }

  function tooltipHtml(code, rec, value) {
    var name = rec ? rec.name : code;
    return '<div class="tt-name">' + name + '</div><div class="tt-val">' +
      formatValue(state.metric, value) + " · " + CAT_LABELS[state.category] + "</div>";
  }

  function styleAndBindFeature(feature, layer) {
    var code = feature.properties.code;
    layersByCode[code] = layer;
    var rec = getRecord(state.level, code);
    var value = getValue(state.level, code, state.category, state.metric, state.monthIndex);
    layer.setStyle(baseStyle(code, value));
    layer.bindTooltip(tooltipHtml(code, rec, value), { sticky: true, className: "rt-tooltip", direction: "top" });

    layer.on("mouseover", function () {
      if (code !== state.selectedCode) {
        layer.setStyle({ color: accent2Color(), weight: 2.2 });
      }
      layer.bringToFront();
    });
    layer.on("mouseout", function () {
      var v = getValue(state.level, code, state.category, state.metric, state.monthIndex);
      layer.setStyle(baseStyle(code, v));
    });
    layer.on("click", function () {
      selectArea(code);
    });
  }

  function buildLevel(level) {
    if (currentGeoLayer) {
      map.removeLayer(currentGeoLayer);
    }
    layersByCode = {};
    computeDomain();
    currentGeoLayer = L.geoJSON(GEO[level], {
      style: function (feature) {
        var code = feature.properties.code;
        var value = getValue(level, code, state.category, state.metric, state.monthIndex);
        return baseStyle(code, value);
      },
      onEachFeature: styleAndBindFeature
    }).addTo(map);
    map.fitBounds(currentGeoLayer.getBounds(), { padding: [24, 24] });
    buildSearchList();
    updateLegend();
  }

  function redrawStyles() {
    computeDomain();
    if (!currentGeoLayer) return;
    currentGeoLayer.eachLayer(function (layer) {
      var code = layer.feature.properties.code;
      var rec = getRecord(state.level, code);
      var value = getValue(state.level, code, state.category, state.metric, state.monthIndex);
      layer.setStyle(baseStyle(code, value));
      layer.setTooltipContent(tooltipHtml(code, rec, value));
    });
    updateLegend();
    if (state.selectedCode) renderPanel(state.selectedCode);
  }

  // ---------- legend ----------
  function updateLegend() {
    document.getElementById("legendTitle").textContent = METRIC_LABELS[state.metric];
    document.getElementById("legendSub").textContent = CAT_LABELS[state.category] + " · " + monthFull(MONTHS[state.monthIndex]);
    var bar = document.getElementById("legendBar");
    if (isDiverging(state.metric)) {
      var stops = getDivStops();
      bar.style.background = "linear-gradient(90deg," + stops[0] + "," + stops[1] + "," + stops[2] + ")";
      document.getElementById("legendMin").textContent = formatValue(state.metric, -domainCache.absMax);
      document.getElementById("legendMax").textContent = formatValue(state.metric, domainCache.absMax);
    } else {
      var s = getSeqStops();
      bar.style.background = "linear-gradient(90deg," + s.join(",") + ")";
      document.getElementById("legendMin").textContent = formatValue(state.metric, domainCache.min);
      document.getElementById("legendMax").textContent = formatValue(state.metric, domainCache.max);
    }
  }

  // ---------- detail panel ----------
  var panel = document.getElementById("panel");
  function selectArea(code) {
    state.selectedCode = code;
    var layer = layersByCode[code];
    if (layer) {
      try { map.fitBounds(layer.getBounds(), { maxZoom: 9, padding: [60, 60] }); } catch (e) {}
    }
    redrawStyles();
    renderPanel(code);
    panel.classList.remove("hidden");
  }

  function buildSparkline(values, currentIdx) {
    var w = 252, h = 64, padX = 4, padY = 8;
    var pts = [];
    for (var i = 0; i < values.length; i++) {
      if (values[i] != null) pts.push([i, values[i]]);
    }
    if (pts.length < 2) return '<div style="font-size:11px;color:var(--ink-faint);padding:6px 2px;">Nedostatek dat pro graf</div>';
    var minV = Math.min.apply(null, pts.map(function (p) { return p[1]; }));
    var maxV = Math.max.apply(null, pts.map(function (p) { return p[1]; }));
    if (minV === maxV) { minV -= 1; maxV += 1; }
    var n = values.length - 1;
    function x(i) { return padX + (i / n) * (w - padX * 2); }
    function y(v) { return h - padY - ((v - minV) / (maxV - minV)) * (h - padY * 2); }
    var d = "";
    pts.forEach(function (p, i) {
      d += (i === 0 ? "M" : "L") + x(p[0]).toFixed(1) + "," + y(p[1]).toFixed(1) + " ";
    });
    var area = d + "L" + x(pts[pts.length - 1][0]).toFixed(1) + "," + (h - padY) + " L" + x(pts[0][0]).toFixed(1) + "," + (h - padY) + " Z";
    var curPt = null;
    for (var j = pts.length - 1; j >= 0; j--) {
      if (pts[j][0] <= currentIdx) { curPt = pts[j]; break; }
    }
    if (!curPt) curPt = pts[pts.length - 1];
    var dot = '<circle cx="' + x(curPt[0]).toFixed(1) + '" cy="' + y(curPt[1]).toFixed(1) + '" r="3.4" fill="var(--accent)" stroke="var(--surface)" stroke-width="1.5"/>';
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" height="64" preserveAspectRatio="none" role="img" aria-label="Vývoj indexu nájmů v čase">' +
      '<path d="' + area + '" fill="var(--accent-2)" fill-opacity="0.14" stroke="none"/>' +
      '<path d="' + d + '" fill="none" stroke="var(--accent-2)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' +
      dot + "</svg>";
  }

  function renderPanel(code) {
    var rec = getRecord(state.level, code);
    var body = document.getElementById("panelBody");
    if (!rec) {
      document.getElementById("panelName").textContent = code;
      document.getElementById("panelRegion").textContent = "";
      body.innerHTML = '<div class="panel-empty">Pro tuto oblast (<b>' + code + "</b>) nejsou v datové sadě dostupné hodnoty.</div>";
      return;
    }
    document.getElementById("panelName").textContent = rec.name;
    document.getElementById("panelRegion").textContent = regionLabel(state.level, code, rec);

    var mIdx = state.monthIndex, cat = state.category;
    var heroVal = getValue(state.level, code, cat, state.metric, mIdx);
    var price = getValue(state.level, code, cat, "price", mIdx);
    var index = getValue(state.level, code, cat, "index", mIdx);
    var mom = getValue(state.level, code, cat, "mom", mIdx);
    var yoy = getValue(state.level, code, cat, "yoy", mIdx);

    function trendClass(v) { return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : ""; }

    var html = "";
    html += '<div class="hero-stat"><div class="label">' + METRIC_LABELS[state.metric] + " · " + CAT_LABELS[cat] + "</div>";
    html += '<div class="value tnum">' + formatValue(state.metric, heroVal) + "</div></div>";

    html += '<div class="stat-grid">';
    html += '<div class="stat-tile"><div class="label">Nájemné</div><div class="value tnum">' + formatValue("price", price) + "</div></div>";
    html += '<div class="stat-tile"><div class="label">Index</div><div class="value tnum">' + formatValue("index", index) + "</div></div>";
    html += '<div class="stat-tile"><div class="label">Meziročně</div><div class="value tnum ' + trendClass(yoy) + '">' + formatValue("yoy", yoy) + "</div></div>";
    html += '<div class="stat-tile"><div class="label">Měsíčně</div><div class="value tnum ' + trendClass(mom) + '">' + formatValue("mom", mom) + "</div></div>";
    html += "</div>";

    html += '<div class="spark-head"><h3>Index nájmů, ' + CAT_LABELS[cat] + '</h3><span>2015–2026</span></div>';
    html += '<div class="sparkline-wrap">' + buildSparkline(rec.series[cat].index, mIdx) + "</div>";

    body.innerHTML = html;
  }

  document.getElementById("panelClose").addEventListener("click", function () {
    state.selectedCode = null;
    panel.classList.add("hidden");
    redrawStyles();
  });

  // ---------- controls ----------
  var levelSeg = document.getElementById("levelSeg");
  levelSeg.addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-level]");
    if (!btn) return;
    levelSeg.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
    btn.classList.add("active");
    state.level = btn.dataset.level;
    state.selectedCode = null;
    panel.classList.add("hidden");
    buildLevel(state.level);
  });

  var catSel = document.getElementById("catSel");
  CAT_ORDER.forEach(function (c) {
    var opt = document.createElement("option");
    opt.value = c;
    opt.textContent = CAT_LABELS[c];
    catSel.appendChild(opt);
  });
  catSel.value = state.category;
  catSel.addEventListener("change", function () {
    state.category = catSel.value;
    redrawStyles();
  });

  var metricSel = document.getElementById("metricSel");
  metricSel.value = state.metric;
  metricSel.addEventListener("change", function () {
    state.metric = metricSel.value;
    redrawStyles();
  });

  var monthRange = document.getElementById("monthRange");
  var monthLabel = document.getElementById("monthLabel");
  monthRange.min = 0;
  monthRange.max = MONTHS.length - 1;
  monthRange.value = state.monthIndex;
  function updateMonthLabel() { monthLabel.textContent = monthShort(MONTHS[state.monthIndex]); }
  monthRange.addEventListener("input", function () {
    stopPlaying();
    state.monthIndex = +monthRange.value;
    updateMonthLabel();
    redrawStyles();
  });
  updateMonthLabel();

  var playBtn = document.getElementById("playBtn");
  var playTimer = null;
  function stopPlaying() {
    state.playing = false;
    playBtn.textContent = "▶";
    playBtn.setAttribute("aria-label", "Přehrát vývoj v čase");
    if (playTimer) { clearInterval(playTimer); playTimer = null; }
  }
  function startPlaying() {
    state.playing = true;
    playBtn.textContent = "⏸";
    playBtn.setAttribute("aria-label", "Pozastavit přehrávání");
    playTimer = setInterval(function () {
      state.monthIndex = state.monthIndex >= MONTHS.length - 1 ? 0 : state.monthIndex + 1;
      monthRange.value = state.monthIndex;
      updateMonthLabel();
      redrawStyles();
    }, 320);
  }
  playBtn.addEventListener("click", function () {
    if (state.playing) stopPlaying(); else startPlaying();
  });

  // ---------- search ----------
  var searchInput = document.getElementById("searchInput");
  var areaList = document.getElementById("areaList");
  var nameToCode = {};
  function buildSearchList() {
    areaList.innerHTML = "";
    nameToCode = {};
    var codes = Object.keys(RENT.levels[state.level]);
    codes.sort(function (a, b) {
      return RENT.levels[state.level][a].name.localeCompare(RENT.levels[state.level][b].name);
    });
    codes.forEach(function (code) {
      var name = RENT.levels[state.level][code].name;
      nameToCode[name.toLowerCase()] = code;
      var opt = document.createElement("option");
      opt.value = name;
      areaList.appendChild(opt);
    });
  }
  function trySearch() {
    var q = searchInput.value.trim().toLowerCase();
    if (!q) return;
    if (nameToCode[q]) { selectArea(nameToCode[q]); return; }
    var match = Object.keys(nameToCode).find(function (n) { return n.indexOf(q) === 0; });
    if (!match) match = Object.keys(nameToCode).find(function (n) { return n.indexOf(q) !== -1; });
    if (match) selectArea(nameToCode[match]);
  }
  searchInput.addEventListener("change", trySearch);
  searchInput.addEventListener("keydown", function (e) { if (e.key === "Enter") trySearch(); });

  // ---------- about popover ----------
  var aboutBtn = document.getElementById("aboutBtn");
  var aboutPop = document.getElementById("aboutPop");
  aboutBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    var open = aboutPop.classList.toggle("open");
    aboutBtn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", function (e) {
    if (!aboutPop.contains(e.target) && e.target !== aboutBtn) {
      aboutPop.classList.remove("open");
      aboutBtn.setAttribute("aria-expanded", "false");
    }
  });

  // ---------- theme change -> re-tint without changing data ----------
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      redrawStyles();
    });
  }

  // ---------- period label ----------
  document.getElementById("periodLabel").textContent = monthFull(MONTHS[0]) + " – " + monthFull(MONTHS[MONTHS.length - 1]);

  // ---------- init ----------
  buildLevel(state.level);
})();
