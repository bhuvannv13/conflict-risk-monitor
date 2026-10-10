"use strict";
const MODEL_NAMES = { persistence: "Persistence baseline", logistic_regression: "Logistic regression", gradient_boosting: "Gradient boosting" };
const SERIES = [
  { key: "state_based", label: "State-based", color: "var(--s1)" },
  { key: "non_state", label: "Non-state", color: "var(--s2)" },
  { key: "one_sided", label: "One-sided (against civilians)", color: "var(--s3)" },
];
const BAND_ORDER = ["High", "Elevated", "Moderate", "Low"];
const ALIASES = {
  USA: ["us", "america", "united states of america"], GBR: ["uk", "britain", "england"],
  COD: ["drc", "congo kinshasa", "democratic republic of the congo", "zaire"], COG: ["congo brazzaville", "republic of the congo"],
  CIV: ["ivory coast"], MMR: ["burma"], RUS: ["russian federation"], PRK: ["dprk"], CZE: ["czech republic"],
  SWZ: ["swaziland"], TUR: ["turkiye"], ISR: ["palestine", "gaza", "west bank"], TLS: ["east timor"], MKD: ["macedonia"],
};
const fmt = new Intl.NumberFormat("en");
const pct = p => (p == null ? "–" : p < 0.001 ? "<0.1%" : (p * 100).toFixed(1) + "%");
const esc = s => LocalChat.escapeHtml(s);
let DATA = null;

const el = (tag, attrs = {}, html = "") => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (html) node.innerHTML = html;
  return node;
};
const monthLabel = m => { const [y, mo] = m.split("-"); return new Date(+y, +mo - 1, 1).toLocaleString("en", { month: "short", year: "numeric" }); };

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map(m => m * p).find(m => m >= v);
}

/* Line chart with crosshair + tooltip, direct labels at the line ends. */
function lineChart(container, months, series) {
  const W = 860, H = 300, m = { t: 12, r: 150, b: 28, l: 56 };
  const max = niceMax(Math.max(...series.flatMap(s => s.values)));
  const x = i => m.l + (i / (months.length - 1)) * (W - m.l - m.r);
  const y = v => H - m.b - (v / max) * (H - m.t - m.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Monthly deaths from organised violence by type" });
  for (let k = 0; k <= 4; k++) {
    const v = (max / 4) * k;
    svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: k ? "var(--grid)" : "var(--axis)", "stroke-width": 1 }));
    svg.appendChild(el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" }, fmt.format(Math.round(v))));
  }
  months.forEach((mo, i) => {
    if (mo.endsWith("-01") && (+mo.slice(0, 4)) % 2 === 0) svg.appendChild(el("text", { x: x(i), y: H - 8, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)" }, mo.slice(0, 4)));
  });
  const ends = [];
  series.forEach(s => {
    const d = s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    svg.appendChild(el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round" }));
    ends.push({ s, y: y(s.values[s.values.length - 1]) });
  });
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
  ends.forEach(e => svg.appendChild(el("text", { x: W - m.r + 8, y: e.y + 4, "font-size": 12, fill: "var(--ink-2)" }, esc(e.s.label.split(" (")[0]))));

  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
  svg.appendChild(cross);
  const dots = series.map(s => { const c = el("circle", { r: 4, fill: s.color, stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }); svg.appendChild(c); return c; });
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" });
  svg.appendChild(hit);
  container.innerHTML = "";
  container.appendChild(svg);
  const tip = document.createElement("div"); tip.className = "tooltip"; tip.hidden = true; container.appendChild(tip);
  const move = evt => {
    const box = svg.getBoundingClientRect();
    const px = ((evt.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(months.length - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (months.length - 1))));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    dots.forEach((d, k) => { d.setAttribute("cx", x(i)); d.setAttribute("cy", y(series[k].values[i])); d.setAttribute("visibility", "visible"); });
    tip.innerHTML = `<strong>${monthLabel(months[i])}</strong><br>` + series.map(s => `${esc(s.label)}: ${fmt.format(s.values[i])}`).join("<br>");
    tip.hidden = false;
    const left = (x(i) / W) * box.width;
    tip.style.left = Math.min(left + 12, box.width - tip.offsetWidth) + "px";
    tip.style.top = "8px";
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerleave", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dots.forEach(d => d.setAttribute("visibility", "hidden")); });
}

/* Single-series bar chart with per-bar tooltip. */
function barChart(container, months, values, label) {
  const W = 620, H = 240, m = { t: 12, r: 12, b: 28, l: 52 };
  const max = niceMax(Math.max(1, ...values));
  const step = (W - m.l - m.r) / values.length, bw = Math.max(2, step - 2);
  const y = v => H - m.b - (v / max) * (H - m.t - m.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": label });
  for (let k = 0; k <= 4; k++) {
    const v = (max / 4) * k;
    svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: k ? "var(--grid)" : "var(--axis)" }));
    svg.appendChild(el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" }, fmt.format(Math.round(v))));
  }
  const tip = document.createElement("div"); tip.className = "tooltip"; tip.hidden = true;
  values.forEach((v, i) => {
    const bx = m.l + i * step + 1, top = y(v), h = H - m.b - top;
    if (h > 0) {
      const r = Math.min(4, bw / 2, h);
      svg.appendChild(el("path", { d: `M${bx},${H - m.b}V${top + r}Q${bx},${top} ${bx + r},${top}H${bx + bw - r}Q${bx + bw},${top} ${bx + bw},${top + r}V${H - m.b}Z`, fill: "var(--s1)" }));
    }
    if (i % 6 === 0) svg.appendChild(el("text", { x: bx + bw / 2, y: H - 8, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)" }, monthLabel(months[i])));
    const hit = el("rect", { x: m.l + i * step, y: m.t, width: step, height: H - m.t - m.b, fill: "transparent" });
    hit.addEventListener("pointerenter", () => {
      tip.innerHTML = `<strong>${monthLabel(months[i])}</strong><br>${fmt.format(v)} deaths`;
      tip.hidden = false;
      const box = svg.getBoundingClientRect();
      tip.style.left = Math.min(((m.l + i * step) / W) * box.width + 10, box.width - 140) + "px";
      tip.style.top = "4px";
    });
    hit.addEventListener("pointerleave", () => { tip.hidden = true; });
    svg.appendChild(hit);
  });
  container.innerHTML = "";
  container.appendChild(svg);
  container.appendChild(tip);
}

function sparkline(values) {
  const max = Math.max(1, ...values), W = 120, H = 26;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * (W - 4) + 2).toFixed(1)},${(H - 3 - (v / max) * (H - 6)).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="var(--s1)" stroke-width="1.5"/></svg>`;
}

function renderKpis() {
  const c = DATA.countries;
  const count = b => c.filter(x => x.band === b).length;
  const deaths = c.reduce((s, x) => s + x.deaths_12m.state_based + x.deaths_12m.non_state + x.deaths_12m.one_sided, 0);
  document.getElementById("kpis").innerHTML = [
    [count("High"), "countries at high risk (50%+)"],
    [count("Elevated"), "countries at elevated risk (20–50%)"],
    [fmt.format(deaths), "deaths from organised violence, last 12 months"],
    [monthLabel(DATA.data_through), "latest month of event data"],
  ].map(([v, l]) => `<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join("");
}

function renderGlobal() {
  const g = DATA.global;
  lineChart(document.getElementById("global-chart"), g.months, SERIES.map(s => ({ ...s, values: g[s.key] })));
  document.getElementById("global-legend").innerHTML = SERIES.map(s => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("");
}

function renderTable() {
  const q = LocalChat.normalise(document.getElementById("search").value);
  const region = document.getElementById("region").value, band = document.getElementById("band").value;
  const rows = DATA.countries.filter(c => (!q || LocalChat.normalise(c.name).includes(q)) && (!region || c.region === region) && (!band || c.band === band));
  document.querySelector("#risk-table tbody").innerHTML = rows.map(c => `
    <tr tabindex="0" data-iso="${c.iso3}">
      <td>${esc(c.name)}</td><td>${esc(c.region)}</td>
      <td><span class="band band-${c.band}">${c.band}</span></td>
      <td class="num">${pct(c.probability)}</td>
      <td class="num">${fmt.format(c.deaths_12m.state_based)}</td>
      <td>${sparkline(c.trend_state_based)}</td>
    </tr>`).join("") || `<tr><td colspan="6">No countries match these filters.</td></tr>`;
}

function showCountry(iso, scroll = true) {
  const c = DATA.countries.find(x => x.iso3 === iso);
  if (!c) return;
  const box = document.getElementById("detail");
  box.hidden = false;
  const rank = DATA.countries.indexOf(c) + 1;
  box.innerHTML = `
    <button class="close-detail" type="button">Close</button>
    <div class="card-head"><h2>${esc(c.name)}</h2><p class="muted">${esc(c.region)} · ranked ${rank} of ${DATA.countries.length}</p></div>
    <div class="detail-grid">
      <div><p class="muted">State-based battle-related deaths per month</p><div class="chart" id="country-chart"></div></div>
      <ul class="facts">
        <li><span>Risk level</span><span class="band band-${c.band}">${c.band}</span></li>
        <li><span>Probability, next 3 months</span><span>${pct(c.probability)}</span></li>
        <li><span>State-based deaths, 12 months</span><span>${fmt.format(c.deaths_12m.state_based)}</span></li>
        <li><span>Non-state deaths, 12 months</span><span>${fmt.format(c.deaths_12m.non_state)}</span></li>
        <li><span>One-sided deaths, 12 months</span><span>${fmt.format(c.deaths_12m.one_sided)}</span></li>
        <li><span>Recorded events, 12 months</span><span>${fmt.format(c.events_12m)}</span></li>
        <li><span>Months since last fatal event</span><span>${c.months_since_fatal >= 240 ? "20+ years" : c.months_since_fatal}</span></li>
        <li><span>GDP per person (constant US$)</span><span>${c.gdp_per_capita ? fmt.format(c.gdp_per_capita) : "n/a"}</span></li>
        <li><span>Infant mortality per 1,000 births</span><span>${c.infant_mortality ?? "n/a"}</span></li>
      </ul>
    </div>`;
  barChart(box.querySelector("#country-chart"), DATA.trend_months, c.trend_state_based, `Monthly state-based deaths in ${c.name}`);
  box.querySelector(".close-detail").addEventListener("click", () => { box.hidden = true; });
  if (scroll) box.scrollIntoView({ behavior: "smooth", block: "start" });
}

function metricCell(m) { return m && m.roc_auc != null ? `${m.roc_auc.toFixed(3)} / ${m.average_precision.toFixed(3)} / ${m.brier.toFixed(3)}` : "–"; }

function renderModel() {
  const mm = DATA.model, p = mm.periods;
  document.getElementById("target-text").textContent = DATA.target.description + ".";
  document.getElementById("model-card").innerHTML = `
    <p><strong>Question the model answers:</strong> ${esc(DATA.target.description)}. 25 deaths is the threshold UCDP uses to count an active armed conflict.</p>
    <p><strong>Inputs (all known at the end of each month):</strong> recent state-based, non-state and one-sided deaths (1, 3, 12 and 36-month windows), number of events, months since the last fatal event, population, GDP per person and infant mortality from the previous year.</p>
    <p><strong>Evaluation:</strong> trained on ${p.train[0]} to ${p.train[1]}, model chosen on ${p.validation[0]} to ${p.validation[1]}, then scored once on ${p.test[0]} to ${p.test[1]}, a period it never saw. Chosen model: <strong>${MODEL_NAMES[mm.chosen]}</strong>.</p>
    <div class="table-wrap"><table class="metrics"><thead><tr><th scope="col">Model</th><th scope="col">Validation: ROC AUC / avg. precision / Brier</th><th scope="col">Test: ROC AUC / avg. precision / Brier</th></tr></thead><tbody>
      ${Object.entries(mm.metrics).map(([k, v]) => `<tr><td>${MODEL_NAMES[k] || k}${k === mm.chosen ? " (chosen)" : ""}</td><td>${metricCell(v.validation)}</td><td>${metricCell(v.test)}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="muted">Higher ROC AUC and average precision are better; lower Brier score is better. The persistence baseline simply assumes recent violence continues, which is hard to beat. The model's main value is ranking countries consistently and putting a number on how likely continuation or onset is.</p>
    <p><strong>Limitations:</strong> most risk comes from countries that are already in conflict, so new outbreaks in previously calm countries are hard to foresee. The newest months use UCDP's preliminary candidate data, which can be revised. Events are counted in the month they started.</p>`;
}

function renderSources() {
  const s = DATA.sources;
  document.getElementById("sources").innerHTML = `
    <ul>
      <li><a href="https://ucdp.uu.se/downloads/">UCDP Georeferenced Event Dataset</a> version ${esc(s.ged?.version || "")} (final data), plus UCDP Candidate Events ${esc(s.candidate?.version || "")} for the most recent months. Licensed CC BY 4.0. Cite Sundberg &amp; Melander (2013), Introducing the UCDP Georeferenced Event Dataset, <em>Journal of Peace Research</em> 50(4), and the current UCDP annual article listed on the downloads page.</li>
      <li><a href="https://data.worldbank.org/">World Bank World Development Indicators</a> (population, GDP per person, infant mortality). Licensed CC BY 4.0.</li>
    </ul>
    <p class="muted">UCDP codes each event from multiple published reports and records a best estimate of deaths, so this page uses researchers' counts rather than headlines or commentary. Page generated ${esc(DATA.generated_at)}.</p>`;
}

/* ---- Chat assistant ---- */
function findCountry(text) {
  const t = " " + LocalChat.normalise(text).replace(/[^a-z0-9 ]/g, " ") + " ";
  let best = null;
  for (const c of DATA.countries) {
    const names = [c.name, c.iso3, ...(ALIASES[c.iso3] || [])].map(n => LocalChat.normalise(n));
    for (const n of names) {
      if ((n.length > 3 || n === LocalChat.normalise(c.iso3)) && t.includes(" " + n + " ") && (!best || n.length > best.len)) best = { c, len: n.length };
    }
  }
  return best && best.c;
}

function countryAnswer(c) {
  const d = c.deaths_12m;
  const trend = c.trend_state_based, recent = trend.slice(-6).reduce((a, b) => a + b, 0), before = trend.slice(-12, -6).reduce((a, b) => a + b, 0);
  const direction = recent > before * 1.25 ? "rising" : recent < before * 0.75 ? "falling" : "roughly steady";
  return `<p><strong>${esc(c.name)}</strong>: <strong>${c.band}</strong> risk, ${pct(c.probability)} chance of 25+ state-based battle deaths in the next 3 months.</p>
    <ul><li>Last 12 months: ${fmt.format(d.state_based)} state-based, ${fmt.format(d.non_state)} non-state and ${fmt.format(d.one_sided)} one-sided deaths.</li>
    <li>State-based deaths over the last 6 months are ${direction} compared with the 6 months before.</li>
    <li>Months since the last fatal event: ${c.months_since_fatal >= 240 ? "more than 20 years" : c.months_since_fatal}.</li></ul>
    <p>This is a statistical estimate, not a forecast of war. <a href="#detail" data-iso="${c.iso3}">Open the chart</a>.</p>`;
}

function listAnswer(list, title) {
  return `<p>${title}</p><ol>${list.map(c => `<li>${esc(c.name)}: ${c.band}, ${pct(c.probability)}</li>`).join("")}</ol>`;
}

const FAQ = [
  { id: "method", text: "how does the model work method machine learning features inputs algorithm predict prediction trained", html: () => `<p>Each month, for every country, the model looks at recent deaths from organised violence (UCDP), how long since the last fatal event, and last year's population, GDP per person and infant mortality (World Bank). It then estimates the chance of 25+ state-based battle deaths in the next 3 months. Chosen model: ${MODEL_NAMES[DATA.model.chosen]}.</p>` },
  { id: "accuracy", text: "how accurate good reliable accuracy auc precision brier evaluation test performance metrics trust", html: () => { const t = DATA.model.metrics[DATA.model.chosen].test, b = DATA.model.metrics.persistence.test; return `<p>On ${DATA.model.periods.test[0]} to ${DATA.model.periods.test[1]}, a period the model never saw, it scored ROC AUC ${t.roc_auc}, average precision ${t.average_precision} and Brier ${t.brier}. The simple "recent violence continues" baseline scored ROC AUC ${b.roc_auc} and average precision ${b.average_precision}. Full table is in the model section.</p>`; } },
  { id: "sources", text: "data sources where come from news official trusted ucdp world bank uppsala licence license cite citation", html: () => `<p>Conflict data comes from the Uppsala Conflict Data Program (UCDP), which codes events from published reports and records researchers' best estimates of deaths. Development indicators come from the World Bank. Both are open data under CC BY 4.0. No opinion pieces or social media are used.</p>` },
  { id: "war", text: "will there be war world war predict war next war start invasion is war coming", html: () => `<p>No model can tell you whether a war will start. This page estimates the chance of continued or new armed-conflict violence (25+ battle deaths in 3 months) from past patterns. Treat it as a ranking of where violence is most likely, not a prediction of specific events.</p>` },
  { id: "types", text: "state based non state one sided difference types violence meaning definition", html: () => `<p><strong>State-based</strong>: fighting where at least one side is a government. <strong>Non-state</strong>: fighting between organised armed groups, neither a government. <strong>One-sided</strong>: deliberate killing of civilians by a government or armed group. These are UCDP's definitions.</p>` },
  { id: "update", text: "when updated update refresh latest how often fresh new data", html: () => `<p>A scheduled GitHub Actions job refreshes the data and retrains the model monthly. Current event data runs to ${monthLabel(DATA.data_through)}; this page was generated ${esc(DATA.generated_at)}.</p>` },
  { id: "bands", text: "risk levels bands high elevated moderate low mean thresholds", html: () => `<p>High: 50% or more. Elevated: 20–50%. Moderate: 5–20%. Low: under 5%.</p>` },
  { id: "code", text: "source code github built who made author pipeline tests", html: () => `<p>The pipeline is Python (pandas, scikit-learn) with tests and GitHub Actions; the site is plain HTML and JavaScript on GitHub Pages. Code: <a href="https://github.com/bhuvannv13/conflict-risk-monitor">github.com/bhuvannv13/conflict-risk-monitor</a>. Built by <a href="https://bhuvannv13.github.io/">Bhuvann Vinodh Ram</a>.</p>` },
];

function setupChat() {
  const index = new LocalChat.Index(FAQ);
  const regions = [...new Set(DATA.countries.map(c => c.region))];
  const avatar = `<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="20" fill="#2a78d6"/><circle cx="20" cy="20" r="11" fill="none" stroke="#fff" stroke-width="2"/><path d="M20 9v22M9 20h22" stroke="#fff" stroke-width="1.5"/><circle cx="20" cy="20" r="3" fill="#fff"/></svg>`;
  const chat = LocalChat.createChat({
    title: "Ask the monitor", subtitle: "Answers from this page's data · runs in your browser",
    launcherLabel: "Ask the monitor", avatar,
    greeting: `<p>Hi! Ask me about any country (for example "Sudan" or "risk in India"), the riskiest countries or regions, or how the model works.</p>`,
    suggestions: ["Top 10 highest risk", "Risk in Africa", "How accurate is it?", "Where does the data come from?", "Will there be a war?"],
    answer: async text => {
      const t = LocalChat.normalise(text);
      const c = findCountry(text);
      if (c) return { html: countryAnswer(c), suggestions: ["Top 10 highest risk", `Risk in ${c.region}`, "How does the model work?"] };
      const region = regions.find(r => t.includes(LocalChat.normalise(r)));
      const top = /\b(top|highest|most|riskiest|worst|list|which countries)\b/.test(t);
      if (region) return { html: listAnswer(DATA.countries.filter(x => x.region === region).slice(0, 8), `Highest estimated risk in ${region}:`) };
      if (top) { const n = Math.min(20, +(t.match(/\d+/) || [10])[0]); return { html: listAnswer(DATA.countries.slice(0, n), `Top ${n} countries by estimated risk:`) }; }
      if (/\b(rising|increase|increasing|growing|escalat)/.test(t)) {
        const rising = DATA.countries.map(x => ({ x, r: x.trend_state_based.slice(-6).reduce((a, b) => a + b, 0) - x.trend_state_based.slice(-12, -6).reduce((a, b) => a + b, 0) })).sort((a, b) => b.r - a.r).slice(0, 8).filter(o => o.r > 0);
        return { html: `<p>Largest increases in state-based deaths (last 6 months vs the 6 before):</p><ol>${rising.map(o => `<li>${esc(o.x.name)}: +${fmt.format(o.r)}</li>`).join("")}</ol>` };
      }
      const hits = index.search(text, 1);
      if (hits.length && hits[0].score > 0.08) return { html: hits[0].doc.html() };
      return { html: `<p>I can answer from this page's data only. Try a country name, a region (${regions.join(", ")}), "top 10", "rising", or ask how the model works.</p>` };
    },
  });
  document.addEventListener("click", e => {
    const a = e.target.closest("a[data-iso]");
    if (a) { e.preventDefault(); showCountry(a.dataset.iso); }
  });
  return chat;
}

async function main() {
  const response = await fetch("data/forecast.json", { cache: "no-cache" });
  DATA = await response.json();
  renderKpis(); renderGlobal(); renderModel(); renderSources();
  const regionSel = document.getElementById("region");
  [...new Set(DATA.countries.map(c => c.region))].sort().forEach(r => regionSel.add(new Option(r, r)));
  const bandSel = document.getElementById("band");
  BAND_ORDER.forEach(b => bandSel.add(new Option(b, b)));
  ["search", "region", "band"].forEach(id => document.getElementById(id).addEventListener("input", renderTable));
  renderTable();
  const tbody = document.querySelector("#risk-table tbody");
  tbody.addEventListener("click", e => { const tr = e.target.closest("tr[data-iso]"); if (tr) showCountry(tr.dataset.iso); });
  tbody.addEventListener("keydown", e => { const tr = e.target.closest("tr[data-iso]"); if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showCountry(tr.dataset.iso); } });
  setupChat();
}
main().catch(err => {
  document.querySelector("main").insertAdjacentHTML("afterbegin", `<p class="note">Could not load the data file. ${esc(err.message)}</p>`);
});
