/* ViSTR-Bench Dashboard SPA — vanilla JS, no external deps. */
"use strict";

const S = {
  config: null,          // {tasks, dims, task_dim, reference}
  runs: [],              // /api/runs
  overview: {},          // run_id -> stats
  selected: new Set(),   // leaderboard run selection
  browser: { run: "", task: "", status: "all", q: "", activeId: null },
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const api = (url) => fetch(url).then((r) => {
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
});

/* ---------------- tabs ---------------- */
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === name));
  document.querySelectorAll(".tabpage").forEach((x) => x.classList.toggle("active", x.id === "tab-" + name));
  if (name === "browser" && !S.browserInited) initBrowser();
  if (name === "taxonomy" && !S.taxonomy) initTaxonomy();
}
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => switchTab(b.dataset.tab))
);

/* ---------------- leaderboard ---------------- */
const COLORS = { ours: "#4fc3f7", ref: "#ffd54f", chance: "#9e9e9e", human: "#81c784" };
const RUN_PALETTE = ["#4fc3f7", "#ce93d8", "#a5d6a7", "#ffab91", "#90caf9", "#fff59d"];

function runColor(i) { return RUN_PALETTE[i % RUN_PALETTE.length]; }

function svgBars(container, groups, opts = {}) {
  /* groups: [{label, bars: [{name, value, color}]}] grouped bar chart */
  const W = opts.w || 460, H = opts.h || 250, padL = 34, padB = 46, padT = 14;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  const plotW = W - padL - 8, plotH = H - padT - padB;
  const maxV = 100;
  const gw = plotW / groups.length;
  groups.forEach((g, gi) => {
    const bw = Math.min(26, (gw * 0.8) / g.bars.length);
    const gx0 = padL + gi * gw + (gw - bw * g.bars.length) / 2;
    g.bars.forEach((b, bi) => {
      const h = (plotH * (b.value || 0)) / maxV;
      const r = document.createElementNS(ns, "rect");
      r.setAttribute("x", gx0 + bi * bw); r.setAttribute("y", padT + plotH - h);
      r.setAttribute("width", bw - 2); r.setAttribute("height", h);
      r.setAttribute("fill", b.color);
      svg.appendChild(r);
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", gx0 + bi * bw + (bw - 2) / 2);
      t.setAttribute("y", padT + plotH - h - 3);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "bar-value");
      t.textContent = (b.value ?? 0).toFixed(1);
      svg.appendChild(t);
    });
    const lt = document.createElementNS(ns, "text");
    lt.setAttribute("x", padL + gi * gw + gw / 2);
    lt.setAttribute("y", H - padB + 14);
    lt.setAttribute("text-anchor", "middle");
    lt.setAttribute("class", "bar-label");
    lt.textContent = g.label;
    svg.appendChild(lt);
    if (g.label2) {
      const lt2 = document.createElementNS(ns, "text");
      lt2.setAttribute("x", padL + gi * gw + gw / 2);
      lt2.setAttribute("y", H - padB + 26);
      lt2.setAttribute("text-anchor", "middle");
      lt2.setAttribute("class", "bar-label");
      lt2.textContent = g.label2;
      svg.appendChild(lt2);
    }
  });
  for (const yv of [0, 25, 50, 75, 100]) {
    const y = padT + plotH - (plotH * yv) / maxV;
    const l = document.createElementNS(ns, "line");
    l.setAttribute("x1", padL); l.setAttribute("x2", W - 8);
    l.setAttribute("y1", y); l.setAttribute("y2", y);
    l.setAttribute("class", yv === 0 ? "axis-line" : "ref-line");
    svg.appendChild(l);
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", padL - 5); t.setAttribute("y", y + 3);
    t.setAttribute("text-anchor", "end"); t.setAttribute("class", "bar-label");
    t.textContent = yv;
    svg.appendChild(t);
  }
  if (opts.refLine !== undefined) {
    const y = padT + plotH - (plotH * opts.refLine) / maxV;
    const l = document.createElementNS(ns, "line");
    l.setAttribute("x1", padL); l.setAttribute("x2", W - 8);
    l.setAttribute("y1", y); l.setAttribute("y2", y);
    l.setAttribute("class", "ref-line");
    svg.appendChild(l);
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", W - 10); t.setAttribute("y", y - 4);
    t.setAttribute("text-anchor", "end"); t.setAttribute("class", "bar-label");
    t.textContent = `chance(freq) ${opts.refLine}`;
    svg.appendChild(t);
  }
  container.replaceChildren(svg);
  if (opts.legend) {
    const lg = el("div", "legend");
    lg.style.cssText = "display:flex;gap:14px;flex-wrap:wrap;margin-top:6px;font-size:11px;color:var(--text-dim)";
    opts.legend.forEach(([name, color]) => {
      const item = el("span");
      item.innerHTML = `<span style="display:inline-block;width:10px;height:10px;background:${color};border-radius:2px;margin-right:4px"></span>${name}`;
      lg.appendChild(item);
    });
    container.appendChild(lg);
  }
}

function heatColor(v) {
  /* RdYlGn-ish, 30..100 */
  const t = Math.max(0, Math.min(1, (v - 30) / 70));
  const hue = t * 120; // red -> green
  return `hsl(${hue}, 65%, 55%)`;
}

async function refreshLeaderboard() {
  const ids = [...S.selected];
  if (ids.length) {
    const data = await api("/api/overview?" + ids.map((i) => "run=" + encodeURIComponent(i)).join("&"));
    Object.assign(S.overview, data);
  }
  renderOverall(); renderDims(); renderBias(); renderHeatmap();
}

function selRuns() { return [...S.selected].filter((i) => S.overview[i]); }

function renderOverall() {
  const runs = selRuns();
  const groups = runs.map((rid, i) => ({
    label: (S.overview[rid].model || rid).slice(0, 14), label2: "",
    bars: [{ value: S.overview[rid].overall, color: runColor(i) }],
  }));
  groups.push({ label: "GPT-5.4", label2: "thinking", bars: [{ value: 62.0, color: COLORS.ref }] });
  groups.push({ label: "Chance", label2: "(Freq)", bars: [{ value: 57.9, color: COLORS.chance }] });
  groups.push({ label: "Human", label2: "", bars: [{ value: 91.0, color: COLORS.human }] });
  groups.forEach((g) => (g.bars[0].name = g.label));
  svgBars($("#chart-overall"), groups, { refLine: 57.9 });
}

function renderDims() {
  const runs = selRuns();
  const ref = S.config.reference["GPT-5.4-thinking"];
  const groups = S.config.dims.map((d) => {
    const bars = runs.map((rid, i) => ({
      value: S.overview[rid].per_dim[d]?.acc ?? 0, color: runColor(i),
    }));
    // reference per-dim: mean of its task accs in this dimension
    const tIdx = S.config.tasks.map((t, ti) => [t, ti]).filter(([t]) => S.config.task_dim[t] === d).map(([, ti]) => ti);
    const refV = tIdx.reduce((a, ti) => a + ref.tasks[ti], 0) / tIdx.length;
    bars.push({ value: refV, color: COLORS.ref });
    return { label: d.replace(" ", "\n"), label2: "", bars };
  });
  svgBars($("#chart-dims"), groups, {
    legend: [...runs.map((rid, i) => [(S.overview[rid].model || rid), runColor(i)]), ["GPT-5.4-thinking", COLORS.ref]],
  });
}

function renderBias() {
  const box = $("#chart-bias");
  box.replaceChildren();
  const cards = el("div", "bias-cards");
  for (const rid of selRuns()) {
    const o = S.overview[rid];
    const frac = o.bias.frac;
    const c = el("div", "bias-card");
    c.appendChild(el("div", "name", o.model || rid));
    const v = el("div", "val " + (frac > 20 ? "bad" : "ok"), frac.toFixed(0) + "%");
    c.appendChild(v);
    c.appendChild(el("div", "sub", `${o.bias.n_bias}/${o.bias.n_tasks} 个任务 >90% 预测为同一选项（n=${o.n}）`));
    cards.appendChild(c);
  }
  if (!selRuns().length) cards.appendChild(el("div", null, "选择至少一个 run"));
  box.appendChild(cards);
}

function renderHeatmap() {
  const box = $("#chart-heatmap");
  box.replaceChildren();
  const runs = selRuns();
  const table = el("table", "heatmap");
  const dims = S.config.dims;
  // dimension group header
  const dh = el("tr", "dimhead");
  dh.appendChild(el("th", "rowname", ""));
  let spans = [];
  for (const d of dims) spans.push([d, S.config.tasks.filter((t) => S.config.task_dim[t] === d).length]);
  for (const [d, n] of spans) {
    const th = el("th", null, d);
    th.colSpan = n;
    dh.appendChild(th);
  }
  table.appendChild(dh);
  // task header
  const th = el("tr");
  th.appendChild(el("th", "rowname", "model \\ task"));
  for (const t of S.config.tasks) th.appendChild(el("th", null, t));
  table.appendChild(th);
  // run rows
  const addRow = (name, getter, isRef) => {
    const tr = el("tr");
    tr.appendChild(el("td", "rowname", name));
    S.config.tasks.forEach((t, ti) => {
      const v = getter(t, ti);
      const td = el("td", "cell");
      if (v === null || v === undefined || Number.isNaN(v)) {
        td.classList.add("na"); td.textContent = "–";
      } else {
        td.style.background = heatColor(v);
        td.textContent = v.toFixed(0);
        if (v < 45 || v > 90) td.style.color = "#f0f0f0";
      }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  };
  for (const rid of runs) {
    const o = S.overview[rid];
    addRow(o.model || rid, (t) => (o.per_task[t] ? o.per_task[t].acc : null));
  }
  for (const name of ["GPT-5.4-thinking", "Chance (Frequency)", "Human"]) {
    addRow(name, (t, ti) => S.config.reference[name].tasks[ti], true);
  }
  box.appendChild(table);
}

/* ---------------- taxonomy ---------------- */
const DIM_COLORS = {
  "Motion Perception": "#4fc3f7", "Spatial Relations": "#ffd54f",
  "Outcome Prediction": "#ef9a9a", "Physical Dynamics": "#81c784",
};
const ANS_PALETTE = ["#4fc3f7", "#ffd54f", "#ce93d8", "#81c784", "#ffab91", "#90caf9", "#f48fb1", "#a5d6a7"];

async function initTaxonomy() {
  S.taxonomy = await api("/api/taxonomy");
  const T = S.taxonomy;
  // overview strip
  const ov = $("#tax-overview");
  ov.replaceChildren();
  const mk = (v, l) => {
    const d = el("div");
    d.appendChild(el("div", "big", v));
    d.appendChild(el("div", "lbl", l));
    return d;
  };
  ov.appendChild(mk(T.total, "public 题（全集 1,340）"));
  ov.appendChild(mk(Object.keys(T.dims).length, "维度"));
  ov.appendChild(mk(T.tasks.length, "子任务"));
  const bar = el("div", "tax-dimbar");
  for (const [d, info] of Object.entries(T.dims)) {
    const seg = el("div");
    seg.style.width = (100 * info.n / T.total) + "%";
    seg.style.background = DIM_COLORS[d];
    seg.title = `${d}: ${info.n} (${(100 * info.n / T.total).toFixed(1)}%)`;
    bar.appendChild(seg);
  }
  ov.appendChild(bar);
  // per-dimension sections
  const root = $("#tax-dims");
  root.replaceChildren();
  for (const [d, info] of Object.entries(T.dims)) {
    const sec = el("div", "tax-dim");
    const head = el("div", "tax-dim-head");
    head.style.borderLeftColor = DIM_COLORS[d];
    const h2 = el("h2", null, d);
    h2.style.color = DIM_COLORS[d];
    head.appendChild(h2);
    head.appendChild(el("span", "cnt", `${info.n} 题 · ${(100 * info.n / T.total).toFixed(1)}%`));
    sec.appendChild(head);
    const grid = el("div", "tax-grid");
    for (const t of T.tasks.filter((x) => x.dimension === d)) {
      grid.appendChild(taxCard(t));
    }
    sec.appendChild(grid);
    root.appendChild(sec);
  }
}

function taxCard(t) {
  const card = el("div", "tax-card");
  card.title = t.template;
  const img = el("img");
  img.src = t.poster;
  img.loading = "lazy";
  img.onerror = () => { img.style.display = "none"; };
  card.appendChild(img);
  const body = el("div", "body");
  body.appendChild(el("div", "name", t.task));
  const srcs = Object.entries(t.sources).sort((a, b) => b[1] - a[1]).map(([s, n]) => `${s}:${n}`).join(" · ");
  body.appendChild(el("div", "sub", `${t.n} 题 · ${t.n_templates} 个模板 · ${srcs}`));
  // answer distribution bar
  const answers = Object.entries(t.answers).sort((a, b) => b[1] - a[1]);
  const barEl = el("div", "ansbar");
  const lg = el("div", "anslg");
  answers.forEach(([a, n], i) => {
    const c = ANS_PALETTE[i % ANS_PALETTE.length];
    const seg = el("div");
    seg.style.width = (100 * n / t.n) + "%";
    seg.style.background = c;
    barEl.appendChild(seg);
    const item = el("span");
    item.innerHTML = `<i style="background:${c}"></i>${a} ${n}`;
    lg.appendChild(item);
  });
  body.appendChild(barEl);
  body.appendChild(lg);
  card.appendChild(body);
  card.addEventListener("click", () => openCaseInBrowser(t.task));
  return card;
}

/* 点击 taxonomy 卡片 → 跳到 Sample Browser 并随机开一道该任务的题 */
async function openCaseInBrowser(task) {
  S.browser.run = "__benchmark__";
  S.browser.task = task;
  S.browser.status = "all";
  S.browser.q = "";
  if (S.browserInited) {
    $("#f-run").value = S.browser.run;
    $("#f-task").value = task;
    $("#f-status").value = "all";
    $("#f-q").value = "";
  }
  switchTab("browser");
  await refreshList();
  const data = await api(`/api/samples?run=__benchmark__&task=${encodeURIComponent(task)}&status=all&q=`);
  if (data.samples.length) {
    const pick = data.samples[Math.floor(Math.random() * data.samples.length)];
    S.browser.activeId = pick.id;
    showDetail(pick.id);
  }
}

/* 当前过滤范围内随机换一题 */
async function pickAnother() {
  const b = S.browser;
  const data = await api(`/api/samples?run=${encodeURIComponent(b.run)}&task=${encodeURIComponent(b.task)}&status=${b.status}&q=${encodeURIComponent(b.q)}`);
  if (!data.samples.length) return;
  const pick = data.samples[Math.floor(Math.random() * data.samples.length)];
  b.activeId = pick.id;
  showDetail(pick.id);
  refreshList();
}


async function initBrowser() {
  const sel = $("#f-run");
  sel.replaceChildren();
  for (const r of S.runs) {
    const o = el("option", null, `${r.model}  (${r.n})`);
    o.value = r.id;
    sel.appendChild(o);
  }
  // respect pre-set filters (e.g. from taxonomy card click); default to first run
  S.browser.run = S.browser.run || S.runs[0]?.id || "";
  sel.value = S.browser.run;
  const tsel = $("#f-task");
  for (const t of S.config.tasks) tsel.appendChild(el("option", null, t));
  tsel.value = S.browser.task || "";
  sel.addEventListener("change", () => { S.browser.run = sel.value; refreshList(); });
  tsel.addEventListener("change", () => { S.browser.task = tsel.value; refreshList(); });
  $("#f-status").addEventListener("change", (e) => { S.browser.status = e.target.value; refreshList(); });
  $("#d-another").addEventListener("click", pickAnother);
  let timer;
  $("#f-q").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { S.browser.q = e.target.value; refreshList(); }, 250);
  });
  S.browserInited = true;
  refreshList();
}

async function refreshList() {
  const b = S.browser;
  const url = `/api/samples?run=${encodeURIComponent(b.run)}&task=${encodeURIComponent(b.task)}&status=${b.status}&q=${encodeURIComponent(b.q)}`;
  const data = await api(url);
  $("#list-meta").textContent = `${data.total} samples`;
  const ul = $("#sample-list");
  ul.replaceChildren();
  for (const s of data.samples.slice(0, 500)) {
    const li = el("li");
    const dot = el("span", "dot " + (s.correct === true ? "ok" : s.correct === false ? "bad" : "na"));
    li.appendChild(dot);
    li.appendChild(el("span", "lid", s.id));
    li.appendChild(el("span", "ltask", s.task));
    if (s.id === b.activeId) li.classList.add("active");
    li.addEventListener("click", () => { b.activeId = s.id; showDetail(s.id); refreshListActive(ul, li); });
    ul.appendChild(li);
  }
}

function refreshListActive(ul, activeLi) {
  ul.querySelectorAll("li").forEach((x) => x.classList.remove("active"));
  activeLi.classList.add("active");
}

async function showDetail(id) {
  const s = await api(`/api/sample?run=${encodeURIComponent(S.browser.run)}&id=${encodeURIComponent(id)}`);
  $("#detail-empty").hidden = true;
  $("#detail-body").hidden = false;
  $("#d-id").textContent = s.id;
  $("#d-task").textContent = s.task;
  $("#d-dim").textContent = s.dimension || "";
  const v = $("#d-verdict");
  if (s.correct === true) { v.textContent = "MATCH"; v.className = "verdict ok"; }
  else if (s.correct === false) { v.textContent = "MISMATCH"; v.className = "verdict bad"; }
  else { v.textContent = "GROUND TRUTH"; v.className = "verdict na"; }
  const vid = $("#d-video");
  if (s.video_url) { vid.src = s.video_url; vid.hidden = false; $("#d-novideo").hidden = true; }
  else { vid.removeAttribute("src"); vid.load(); vid.hidden = true; $("#d-novideo").hidden = false; }
  $("#d-question").textContent = s.question || "";
  const opts = $("#d-options");
  opts.replaceChildren();
  (s.options || []).forEach((o, i) => {
    const isGt = o === s.gt, isPred = s.pred && o === s.pred;
    const d = el("div", "opt" + (isGt && isPred ? " both" : isGt ? " gt" : isPred ? " pred" : ""));
    d.appendChild(el("b", null, `[${String.fromCharCode(65 + i)}]`));
    d.appendChild(el("span", null, o));
    d.appendChild(el("span", "mark", isGt && isPred ? "GT ✓ Pred" : isGt ? "GT" : isPred ? "Pred" : ""));
    opts.appendChild(d);
  });
  $("#d-gt").innerHTML = `GT: <b>${s.gt ?? "?"}</b>`;
  $("#d-pred").innerHTML = s.pred ? `Pred: <b>${s.pred}</b>` : "Pred: —";
  const cot = $("#d-cot-box");
  if (s.manual_cot) { cot.hidden = false; $("#d-cot").textContent = s.manual_cot; } else cot.hidden = true;
  const eb = $("#d-evidence-box");
  if (s.evidence) { eb.hidden = false; $("#d-evidence").textContent = s.evidence; } else eb.hidden = true;
  const rb = $("#d-reasoning-box");
  if (s.reasoning) { rb.hidden = false; $("#d-reasoning").textContent = s.reasoning; } else rb.hidden = true;
}

/* ---------------- boot ---------------- */
(async function boot() {
  S.config = await api("/api/config");
  S.runs = await api("/api/runs");
  const predRuns = S.runs.filter((r) => !r.is_benchmark);
  predRuns.forEach((r) => S.selected.add(r.id));
  // run checkboxes
  const box = $("#run-checkboxes");
  for (const r of predRuns) {
    const lb = el("label");
    const cb = el("input");
    cb.type = "checkbox"; cb.checked = true; cb.value = r.id;
    cb.addEventListener("change", () => {
      cb.checked ? S.selected.add(r.id) : S.selected.delete(r.id);
      refreshLeaderboard();
    });
    lb.appendChild(cb);
    lb.appendChild(el("span", null, `${r.model} (${r.n})`));
    box.appendChild(lb);
  }
  $("#header-meta").textContent =
    `${S.runs.length} run(s) · ${predRuns.length} prediction run(s) · benchmark ${S.runs.find((r) => r.is_benchmark)?.n ?? 0} samples`;
  await refreshLeaderboard();
})().catch((e) => {
  $("#header-meta").textContent = "load failed: " + e.message;
  console.error(e);
});
