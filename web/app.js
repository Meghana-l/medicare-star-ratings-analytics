(function () {
  "use strict";

  var D = null;                 // loaded data
  var state = { cid: null };
  var charts = {};
  var mById = {};

  // ---------- helpers
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(v) {
    if (v == null) return "—";
    return Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);
  }
  function stars(n) {
    if (n == null) return '<span class="note">n/a</span>';
    return '<span class="stars">' + "★".repeat(n) + '<span class="off">' + "★".repeat(5 - n) + "</span></span>";
  }
  function overallText(v) { return v == null ? "—" : v.toFixed(1) + " ★"; }
  function card(label, value, hint) {
    return '<div class="card"><div class="label">' + esc(label) + '</div><div class="value">' + value +
      '</div><div class="hint">' + esc(hint || "") + "</div></div>";
  }
  function drawChart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id), cfg);
  }
  function currentRows() { return D.scores[state.cid] || []; }
  function currentContract() {
    return D.contracts.find(function (c) { return c.id === state.cid; });
  }
  function latestYear() { return String(D.meta.year); }

  // ---------- tabs
  function showTab(name) {
    document.querySelectorAll(".tab").forEach(function (t) { t.classList.toggle("active", t.dataset.tab === name); });
    document.querySelectorAll(".panel").forEach(function (p) { p.classList.toggle("active", p.id === name); });
    $("plan-picker").hidden = !(name === "scorecard" || name === "gaps" || name === "dist");
    if (name === "dist") renderDist();
    if (name === "overview") renderOverview();
  }

  // ---------- overview
  function renderOverview() {
    var m = D.meta;
    var rate = m.match_rate == null ? "n/a" : m.match_rate.toFixed(1) + "%";
    $("overview-cards").innerHTML =
      card("Plans (contracts)", D.contracts.length.toLocaleString(), "Rating year " + m.year) +
      card("Measures", D.measures.length, "HEDIS, CAHPS, HOS, Admin, Part D") +
      card("Measure stars matching CMS", rate,
        (m.compared - m.mismatches).toLocaleString() + " of " + m.compared.toLocaleString() + " rebuilt from raw scores") +
      card("Cut points", cutLabel(), "Source of the thresholds");

    var buckets = {}, order = [];
    for (var s = 1; s <= 5; s += 0.5) { buckets[s] = 0; order.push(s); }
    D.contracts.forEach(function (c) { if (c.cms_overall != null && buckets[c.cms_overall] !== undefined) buckets[c.cms_overall]++; });
    drawChart("chart-overall", {
      type: "bar",
      data: { labels: order.map(function (s) { return s.toFixed(1) + " ★"; }),
        datasets: [{ label: "Plans", data: order.map(function (s) { return buckets[s]; }), backgroundColor: "#2f7fc1" }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
    var ok = m.compared - m.mismatches;
    drawChart("chart-match", {
      type: "doughnut",
      data: { labels: ["Match CMS", "Differ from CMS"], datasets: [{ data: [ok, m.mismatches], backgroundColor: ["#1c7c54", "#b83232"], borderWidth: 0 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
    });
  }
  function cutLabel() {
    var s = D.meta.cutpoint_source || "";
    return s.indexOf("CMS") === 0 ? "Official" : s.indexOf("estimated") === 0 ? "Estimated" : "Synthetic";
  }

  // ---------- scorecard
  function renderScorecard() {
    var c = currentContract(), rows = currentRows();
    var compared = 0, matched = 0;
    rows.forEach(function (r) { if (r[2] != null && r[3] != null) { compared++; if (r[2] === r[3]) matched++; } });
    $("score-cards").innerHTML =
      card("CMS overall rating", overallText(c.cms_overall), c.name || c.id) +
      card("Rebuilt overall", overallText(c.calc_overall), "Weighted average " + (c.wavg == null ? "—" : c.wavg.toFixed(2)) + " (before CMS adjustments)") +
      card("Measures rated", c.n_rated, "of " + rows.length + " measures") +
      card("Match with CMS", compared ? matched + " / " + compared : "—", "Measure stars rebuilt vs published");

    var html = "<tr><th>Measure</th><th>Source</th><th class='num'>Weight</th><th class='num'>Score</th>" +
      "<th>Rebuilt star</th><th>CMS star</th><th>Match</th></tr>";
    rows.forEach(function (r) {
      var m = mById[r[0]] || {};
      var ok = r[2] == null || r[3] == null ? "—" : (r[2] === r[3] ? '<span class="ok">✓</span>' : '<span class="no">✗</span>');
      html += "<tr><td>" + esc(m.name || r[0]) + '</td><td><span class="tag">' + esc(m.source || "") + "</span></td>" +
        '<td class="num">' + esc(m.weight) + '</td><td class="num">' + fmt(r[1]) + "</td><td>" + stars(r[3]) +
        "</td><td>" + stars(r[2]) + "</td><td>" + ok + "</td></tr>";
    });
    $("score-table").innerHTML = html;
  }

  // ---------- gaps
  function renderGaps() {
    var mode = $("gap-sort").value;
    var rows = currentRows().filter(function (r) { return r[3] != null && r[3] < 5 && r[5] != null; });
    rows.sort(function (a, b) {
      var wa = (mById[a[0]] || {}).weight || 0, wb = (mById[b[0]] || {}).weight || 0;
      if (mode === "weight") return wb - wa || a[6] - b[6];
      return a[6] - b[6] || wb - wa;
    });
    var html = "<tr><th>Measure</th><th>Source</th><th class='num'>Weight</th><th class='num'>Score</th><th>Stars now</th>" +
      "<th class='num'>Next cut point</th><th class='num'>Gap</th><th>Gap as % of band</th></tr>";
    rows.forEach(function (r) {
      var m = mById[r[0]] || {};
      var pct = Math.min(100, Math.round((r[6] || 0) * 100));
      var dir = m.higher_is_better === 0 ? " (lower is better)" : "";
      html += "<tr><td>" + esc(m.name || r[0]) + '<span class="note">' + esc(dir) + '</span></td><td><span class="tag">' + esc(m.source || "") +
        '</span></td><td class="num">' + esc(m.weight) + '</td><td class="num">' + fmt(r[1]) + "</td><td>" + stars(r[3]) +
        '</td><td class="num">' + fmt(r[4]) + '</td><td class="num">' + fmt(r[5]) + '</td><td><div class="bar"><i style="width:' + pct +
        '%"></i></div>' + pct + "%</td></tr>";
    });
    if (!rows.length) html += "<tr><td colspan='8'>No measures below 5 stars with a computable gap.</td></tr>";
    $("gap-table").innerHTML = html;
  }

  // ---------- distributions & trends
  var linePlugin = {
    id: "vlines",
    afterDatasetsDraw: function (chart, args, opts) {
      if (!opts || !opts.lines) return;
      var x = chart.scales.x, area = chart.chartArea, ctx = chart.ctx;
      opts.lines.forEach(function (l) {
        var px = x.getPixelForValue(l.index);
        ctx.save();
        ctx.strokeStyle = l.color; ctx.lineWidth = l.width || 1.5; ctx.setLineDash(l.dash || []);
        ctx.beginPath(); ctx.moveTo(px, area.top); ctx.lineTo(px, area.bottom); ctx.stroke();
        if (l.label) { ctx.fillStyle = l.color; ctx.font = "11px sans-serif"; ctx.fillText(l.label, px + 3, area.top + (l.ly || 10)); }
        ctx.restore();
      });
    }
  };

  function renderDist() {
    var mid = $("measure-pick").value;
    var m = mById[mid];
    var vals = [], mine = null;
    Object.keys(D.scores).forEach(function (cid) {
      D.scores[cid].forEach(function (r) {
        if (r[0] === mid && r[1] != null) { vals.push(r[1]); if (cid === state.cid) mine = r[1]; }
      });
    });
    var yr = latestYear(), cuts = (D.cutpoints[mid] || {})[yr];
    if (!vals.length) { return; }
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var all = vals.slice();
    if (cuts) cuts.forEach(function (c) { if (c != null && Math.abs(c) < 1e9) all.push(c); });
    min = Math.min.apply(null, all); max = Math.max.apply(null, all);
    var bins = 20, w = (max - min) / bins || 1, counts = new Array(bins).fill(0), labels = [];
    vals.forEach(function (v) { counts[Math.min(bins - 1, Math.floor((v - min) / w))]++; });
    for (var i = 0; i < bins; i++) labels.push(fmt(min + w * (i + 0.5)));
    function idx(v) { return (v - min) / w - 0.5; }

    var lines = [];
    if (cuts) cuts.forEach(function (c, k) {
      if (c != null && Math.abs(c) < 1e9) lines.push({ index: idx(c), color: "#5b6577", dash: [4, 3], label: (k + 2) + "★" });
    });
    if (mine != null) lines.push({ index: idx(mine), color: "#b83232", width: 2.5, label: "this plan", ly: 24 });

    drawChart("chart-dist", {
      type: "bar", plugins: [linePlugin],
      data: { labels: labels, datasets: [{ label: "Plans", data: counts, backgroundColor: "#9ec3e6", categoryPercentage: 1, barPercentage: 0.95 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, vlines: { lines: lines } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
    $("dist-note").textContent = (m.higher_is_better === 0 ? "Lower is better. " : "Higher is better. ") +
      "Dashed lines are the " + yr + " cut points. " + (m.higher_is_better === 0 ? "Scores left of a line earn at least that star." : "Scores right of a line earn at least that star.") + (mine != null ? " Red line: the selected plan." : "");

    var years = Object.keys(D.cutpoints[mid] || {}).sort();
    var names = ["2★ cut", "3★ cut", "4★ cut", "5★ cut"], colors = ["#b83232", "#b7791f", "#2f7fc1", "#1c7c54"];
    drawChart("chart-trend", {
      type: "line",
      data: { labels: years, datasets: names.map(function (n, k) {
        return { label: n, data: years.map(function (y) { var v = D.cutpoints[mid][y][k]; return Math.abs(v) > 1e9 ? null : v; }),
          borderColor: colors[k], backgroundColor: colors[k], tension: 0.2 };
      }) },
      options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
    });
    $("trend-note").textContent = years.length < 2
      ? "Only one rating year of cut points is loaded. Add earlier years in data/reference to see the trend."
      : (m.higher_is_better === 0 ? "Falling cut points on a lower-is-better measure mean plans need a lower score for the same star."
        : "Rising cut points on a higher-is-better measure mean plans need a higher score for the same star.");
  }

  // ---------- specs
  function renderSpecs() {
    var f = $("spec-filter").value;
    var html = "";
    D.measures.filter(function (m) { return !f || m.source === f; }).forEach(function (m) {
      function row(label, v) { return v ? "<dt>" + label + "</dt><dd>" + esc(v) + "</dd>" : ""; }
      html += '<div class="spec"><h3>' + esc(m.name) + '</h3><span class="tag">' + esc(m.source || "") + '</span> <span class="note">' +
        esc(m.measure_id) + " · Part " + esc(m.part) + " · weight " + esc(m.weight) + " · " +
        (m.higher_is_better === 0 ? "lower is better" : "higher is better") + "</span><dl>" +
        row("Meaning", m.definition) + row("Numerator", m.numerator) + row("Denominator", m.denominator) + row("Exclusions", m.exclusions) + "</dl></div>";
    });
    $("spec-list").innerHTML = html || "<p class='note'>No measures for this source.</p>";
  }

  // ---------- checks
  function renderChecks() {
    $("check-list").innerHTML = D.checks.map(function (c) {
      return '<div class="check"><span class="pill ' + esc(c.status) + '">' + esc(c.status.toUpperCase()) + "</span><div><b>" + esc(c.name) +
        "</b><span>" + esc(c.detail) + (c.count != null ? " (count: " + Number(c.count).toLocaleString() + ")" : "") + "</span></div></div>";
    }).join("");
  }

  // ---------- init
  function init(data) {
    D = data;
    D.measures.forEach(function (m) { mById[m.measure_id] = m; });
    $("demo-banner").hidden = D.meta.source !== "demo";
    $("est-banner").hidden = (D.meta.cutpoint_source || "").indexOf("estimated") !== 0;
    $("meta-line").textContent = "Rating year " + D.meta.year + " · data source: " + D.meta.source + " · cut points: " +
      D.meta.cutpoint_source + " · built " + D.meta.generated;

    var sel = $("contract");
    sel.innerHTML = D.contracts.map(function (c) {
      return '<option value="' + esc(c.id) + '">' + esc(c.id) + (c.name ? " · " + esc(c.name) : "") + "</option>";
    }).join("");
    state.cid = D.contracts.length ? D.contracts[0].id : null;
    sel.addEventListener("change", function () { state.cid = sel.value; renderScorecard(); renderGaps(); renderDist(); });

    $("measure-pick").innerHTML = D.measures.map(function (m) {
      return '<option value="' + esc(m.measure_id) + '">' + esc(m.name) + "</option>";
    }).join("");
    $("measure-pick").addEventListener("change", renderDist);

    var sources = {};
    D.measures.forEach(function (m) { if (m.source) sources[m.source] = 1; });
    Object.keys(sources).forEach(function (s) { $("spec-filter").insertAdjacentHTML("beforeend", '<option value="' + esc(s) + '">' + esc(s) + "</option>"); });
    $("spec-filter").addEventListener("change", renderSpecs);
    $("gap-sort").addEventListener("change", renderGaps);

    document.querySelectorAll(".tab").forEach(function (t) { t.addEventListener("click", function () { showTab(t.dataset.tab); }); });

    renderOverview(); renderScorecard(); renderGaps(); renderSpecs(); renderChecks();
  }

  fetch("data/data.json").then(function (r) { return r.json(); }).then(init).catch(function (e) {
    document.querySelector("main").innerHTML = '<div class="box"><h2>Could not load data</h2><p class="note">Run <code>python -m pipeline.build --demo</code> and serve the <code>web/</code> folder (for example <code>python -m http.server</code>). ' + esc(e) + "</p></div>";
  });
})();
