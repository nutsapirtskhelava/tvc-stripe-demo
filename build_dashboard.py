"""
build_dashboard.py

Exports subject-level IN/Psi + the stats table into dashboard_data.json, and
writes dashboard.html (a static, self-contained page; all chart drawing is
done client-side in vanilla JS/SVG from the embedded JSON -- no server, no
build step needed to view it).

Does NOT replicate the PI's reference analysis -- only borrows its visual
language (eyebrow labels, navy/orange eye coding, pill toggles, clean tables
with dagger footnotes for bound-pinned fits) and applies it to our own TvC
noise-model data (IN, Psi) from plot_tvc_curves.py / tvc_stats.py.

Usage:
    python3 build_dashboard.py
Output:
    dashboard_data.json
    dashboard.html
"""

import json
import pandas as pd

from plot_tvc_curves import load_final_rows, geometric_mean

STATS_CSV = "results/tvc_stats_table.csv"
DATA_OUT = "dashboard_data.json"
HTML_OUT = "dashboard.html"


def export_subjects(final):
    """One record per subject, each holding its two eyes (blue/orange coded)."""
    subjects = []
    for subj_id, rows in final.groupby("Subject"):
        rows = rows.set_index("Eye")
        group = rows["Group"].iloc[0]
        eyes = []
        for physical_eye in ["OD", "OS"]:
            r = rows.loc[physical_eye]
            status = r["EyeStatus"]  # Control / Fellow / Amblyopic
            if status == "Control":
                role = f"Control {physical_eye}"
                color_group = "blue" if physical_eye == "OD" else "orange"
            elif status == "Fellow":
                role = "Fellow eye"
                color_group = "blue"
            else:
                role = "Amblyopic eye"
                color_group = "orange"
            eyes.append({
                "physicalEye": physical_eye,
                "role": role,
                "colorGroup": color_group,
                "IN": round(float(r["IN"]), 4),
                "Psi": round(float(r["Psi"]), 4),
                "atBound": bool(r["Psi"] >= 1.999),
            })
        subjects.append({"subject": int(subj_id), "group": group, "eyes": eyes})
    return subjects


def export_group_means(final):
    roles = {
        "Control OD": final[(final["EyeStatus"] == "Control") & (final["Eye"] == "OD")],
        "Control OS": final[(final["EyeStatus"] == "Control") & (final["Eye"] == "OS")],
        "Fellow eye": final[final["EyeStatus"] == "Fellow"],
        "Amblyopic eye": final[final["EyeStatus"] == "Amblyopic"],
        "All Controls": final[final["EyeStatus"] == "Control"],
        "All Amblyopes": final[final["EyeStatus"].isin(["Fellow", "Amblyopic"])],
    }
    out = {}
    for label, g in roles.items():
        out[label] = {
            "n": len(g),
            "IN": round(geometric_mean(g["IN"].values), 4),
            "Psi": round(geometric_mean(g["Psi"].values), 4),
        }
    return out


# "minimum detectable cohort difference" from the AIM-TvC+ method paper's own
# test-retest repeatability data (Skerswetat et al., Appendix A3) -- an independent,
# data-derived reference for whether an observed group difference is plausibly real
MCD = {"IN": 0.0023, "Psi": 0.1079}


def export_stats(group_means):
    df = pd.read_csv(STATS_CSV)
    records = df.to_dict(orient="records")
    for r in records:
        label_a, label_b = r["comparison"].split(" vs ")
        param = r["parameter"]
        mean_diff = abs(group_means[label_a][param] - group_means[label_b][param])
        r["group_mean_diff"] = round(mean_diff, 4)
        r["exceeds_mcd"] = bool(mean_diff > MCD[param])
    return records


def main():
    final = load_final_rows()
    group_means = export_group_means(final)
    data = {
        "subjects": export_subjects(final),
        "groupMeans": group_means,
        "stats": export_stats(group_means),
        "mcd": MCD,
    }
    with open(DATA_OUT, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {DATA_OUT} ({len(data['subjects'])} subjects, {len(data['stats'])} stats rows)")

    with open(HTML_OUT, "w") as f:
        f.write(HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data)))
    print(f"Wrote {HTML_OUT}")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TvC in Amblyopia &mdash; Internal Noise &amp; Weber Fraction</title>
<style>
  :root {
    --ink: #17191c;
    --muted: #8a8f98;
    --faint: #c7cad0;
    --hairline: #e6e7ea;
    --bg: #ffffff;
    --blue: #1b3a5e;
    --orange: #c1440e;
    --pill-bg: #f3f4f6;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 72px 28px 120px; }
  .eyebrow {
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 18px;
    font-weight: 500;
  }
  h1.title {
    font-size: 56px;
    line-height: 1.05;
    font-weight: 500;
    letter-spacing: -0.01em;
    margin: 0 0 24px;
  }
  p.subtitle {
    font-size: 19px;
    line-height: 1.5;
    color: #555;
    max-width: 720px;
    margin: 0 0 40px;
  }
  .legend {
    display: flex;
    gap: 28px;
    flex-wrap: wrap;
    align-items: center;
    font-size: 14px;
    color: #444;
    margin-bottom: 8px;
  }
  .legend .swatch {
    display: inline-block;
    width: 22px;
    height: 2px;
    margin-right: 8px;
    vertical-align: middle;
    position: relative;
    top: -2px;
  }
  .swatch.blue { background: var(--blue); }
  .swatch.orange { background: var(--orange); }
  hr.rule {
    border: none;
    border-top: 1px solid var(--hairline);
    margin: 48px 0;
  }
  .q-eyebrow {
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 10px;
    font-weight: 500;
  }
  h2.question {
    font-size: 30px;
    font-weight: 500;
    letter-spacing: -0.005em;
    margin: 0 0 14px;
  }
  p.question-sub {
    font-size: 16px;
    color: #555;
    line-height: 1.55;
    max-width: 680px;
    margin: 0 0 28px;
  }
  .pillgroup {
    display: inline-flex;
    background: var(--pill-bg);
    border-radius: 999px;
    padding: 3px;
    gap: 2px;
    margin-right: 20px;
    margin-bottom: 24px;
  }
  .pillgroup button {
    border: none;
    background: transparent;
    font-size: 14px;
    padding: 7px 16px;
    border-radius: 999px;
    cursor: pointer;
    color: #444;
    font-family: inherit;
  }
  .pillgroup button.active {
    background: var(--ink);
    color: #fff;
  }
  .control-label {
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    display: block;
    margin-bottom: 8px;
  }
  .controls-row { margin-bottom: 8px; }

  .subject-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 18px;
    margin: 28px 0 8px;
  }
  .subject-panel {
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 10px 6px;
  }
  .subject-panel:hover { border-color: var(--faint); }
  .subject-panel-head {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    margin-bottom: 2px;
  }
  .subject-panel-head .sid { font-weight: 600; color: var(--ink); }
  .subject-panel-head .grp { color: var(--muted); }

  table.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    margin: 20px 0 8px;
  }
  table.data-table th {
    text-align: left;
    font-size: 11px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 500;
    padding: 10px 14px;
    border-bottom: 1px solid var(--hairline);
    white-space: nowrap;
  }
  table.data-table td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--hairline);
    color: #333;
    white-space: nowrap;
  }
  table.data-table td.num, table.data-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
  table.data-table tr:last-child td { border-bottom: none; }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 7px; }
  .dot.blue { background: var(--blue); }
  .dot.orange { background: var(--orange); }
  .bound-mark { color: var(--orange); cursor: default; }
  .footnote { font-size: 13px; color: var(--muted); line-height: 1.6; margin-top: 14px; max-width: 680px; }

  .sig { font-weight: 600; }
  .sig.yes { color: #0a7a3d; }
  .sig.no { color: var(--muted); font-weight: 400; }

  .group-curve-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    margin: 28px 0 8px;
  }
  @media (max-width: 900px) {
    .group-curve-grid { grid-template-columns: 1fr; }
    h1.title { font-size: 38px; }
  }
  .panel-title { font-size: 13px; color: #444; margin-bottom: 6px; }
  svg text { font-family: inherit; fill: var(--muted); }
  svg .axis-line { stroke: var(--hairline); stroke-width: 1; }

  .matlab-fig-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 20px;
    margin: 24px 0 8px;
  }
  .matlab-fig-grid figure { margin: 0; }
  .matlab-fig-grid img { width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--hairline); }
  .matlab-fig-grid figcaption { font-size: 12px; color: var(--muted); margin-top: 6px; }
</style>
</head>
<body>
<div class="wrap">

  <p class="eyebrow">BEHAVIORAL &middot; ORIENTATION DISCRIMINATION &middot; THRESHOLD VS CONTRAST &middot;
    <a href="index.html" style="color:inherit;">&larr; stripe-ring task demo</a></p>
  <h1 class="title">Internal Noise &amp; Weber Fraction<br>in Amblyopia</h1>
  <p class="subtitle">
    How much does each eye's contrast-discrimination threshold rise with pedestal contrast?
    Fitted internal noise (IN) and Weber fraction (Psi), measured separately for each eye in
    11 child control observers (ages 6&ndash;17) and 6 children with amblyopia (ages 6&ndash;16)
    (subjects 26 and 32 excluded; see footnote).
  </p>
  <div class="legend">
    <span><span class="swatch blue"></span>Control OD &middot; Fellow eye</span>
    <span><span class="swatch orange"></span>Control OS &middot; Amblyopic eye</span>
  </div>

  <hr class="rule">

  <p class="q-eyebrow">QUESTION 1</p>
  <h2 class="question">What does each eye's TvC curve look like?</h2>
  <p class="question-sub">
    AIM-TvC+ dipper function: TvC(c) = &radic;((IN&sup2; + c&sup2;)&middot;(1+Psi)) &minus; c, across a range of
    pedestal contrasts, from each subject's fitted final IN/Psi (not raw trial data &mdash; see repo CLAUDE.md).
  </p>

  <div id="subjectGrid" class="subject-grid"></div>

  <table class="data-table" id="subjectTable"></table>
  <p class="footnote"><span class="bound-mark">&dagger;</span> Psi estimate sits at the model's upper fitting bound (2.0) &mdash; likely an unreliable fit for that eye, included as-is.</p>

  <hr class="rule">

  <p class="q-eyebrow">QUESTION 2</p>
  <h2 class="question">Do IN and Weber fraction differ between the eyes?</h2>
  <p class="question-sub">
    Four comparisons &times; two parameters. Log10-scale Welch/paired t-tests with a Mann-Whitney/Wilcoxon
    cross-check, Holm-corrected within each parameter (2 families of 4 tests).
  </p>

  <div class="controls-row">
    <span class="control-label">PARAMETER</span>
    <div class="pillgroup" id="paramPills">
      <button data-param="IN" class="active">Internal noise (IN)</button>
      <button data-param="Psi">Weber fraction (Psi)</button>
    </div>
  </div>

  <div class="group-curve-grid" id="groupCurveGrid"></div>

  <table class="data-table" id="statsTable"></table>
  <p class="footnote">Effect size = Cohen's d (independent) / dz (paired) on log10 values, with approx. 95% CI (Hedges normal approximation). None of the 8 comparisons reach significance after Holm correction, given the small amblyopic-eye groups (n=6) &mdash; but Psi shows a consistent moderate-to-large effect in the expected direction (amblyopic eye worse) that IN does not. <strong>|&Delta; mean| vs MCD</strong> compares the raw group-mean difference against the "minimum detectable cohort difference" reported in the AIM-TvC+ method paper's own test-retest data (IN: 0.0023, Psi: 0.1079) &mdash; an independent, non-circular check: both Psi comparisons involving the amblyopic eye exceed this reference, while neither IN comparison does.</p>

  <hr class="rule">

  <p class="q-eyebrow">ADDITIONAL FIGURES</p>
  <h2 class="question">From analyze_WF_internal_noise.m</h2>
  <p class="question-sub">
    The lab's existing MATLAB pipeline (group comparisons, mixed models, IN/Psi correlation, convergence
    across charts) on the same data, same exclusions. Full numeric output:
    <a href="results/WF_IN_results.xlsx" style="color:inherit;">results/WF_IN_results.xlsx</a>.
  </p>
  <div class="matlab-fig-grid">
    <figure><img src="results/Fig1_final_by_group_eye.png" alt="Final estimates by group and eye"><figcaption>Final estimates by group &amp; eye</figcaption></figure>
    <figure><img src="results/Fig1b_control_FE_AE.png" alt="Control vs Fellow/Amblyopic eye"><figcaption>Control vs Fellow/Amblyopic eye</figcaption></figure>
    <figure><img src="results/Fig2_IN_vs_WF.png" alt="IN vs Weber fraction correlation"><figcaption>IN vs Weber fraction correlation</figcaption></figure>
    <figure><img src="results/Fig3_convergence_across_charts.png" alt="Convergence across charts"><figcaption>Convergence across charts</figcaption></figure>
    <figure><img src="results/Fig4_interocular_difference.png" alt="Interocular difference"><figcaption>Interocular difference (per-subject)</figcaption></figure>
  </div>

  <hr class="rule">
  <p class="footnote">
    Subjects 26 (did not understand the task) and 32 (no TvC data recorded) excluded throughout.
    Full pipeline, data survey, and source at
    <a href="https://github.com/nutsapirtskhelava/tvc-stripe-demo" style="color:inherit;">github.com/nutsapirtskhelava/tvc-stripe-demo</a>.
  </p>

</div>

<script id="dashboard-data" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
const COLORS = { blue: '#1b3a5e', orange: '#c1440e' };
const CONTRAST_MIN = 0.001, CONTRAST_MAX = 0.9;
const N_POINTS = 60;

// AIM-TvC+ dipper function (Skerswetat et al. method paper, eq. 3):
// TvC(c) = sqrt((IN^2 + c^2) * (1 + Psi)) - c -- dips down before rising, not monotonic
function threshold(c, IN, Psi) { return Math.sqrt((IN * IN + c * c) * (1 + Psi)) - c; }

function logRange(min, max, n) {
  const out = [];
  const lo = Math.log10(min), hi = Math.log10(max);
  for (let i = 0; i < n; i++) out.push(Math.pow(10, lo + (hi - lo) * i / (n - 1)));
  return out;
}
const CONTRASTS = logRange(CONTRAST_MIN, CONTRAST_MAX, N_POINTS);

function svgEl(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

// draws one log-log TvC panel into an existing <svg>, given a list of {IN, Psi, color}
// Picks readable log-scale tick values (powers of 10, falling back to 2x/5x
// multiples when the visible range spans less than one decade) within
// [10^loExp, 10^hiExp].
function niceLogTicks(loExp, hiExp) {
  const ticks = [];
  const eLo = Math.floor(loExp), eHi = Math.ceil(hiExp);
  for (let e = eLo; e <= eHi; e++) {
    const lv = e;
    if (lv >= loExp - 1e-9 && lv <= hiExp + 1e-9) ticks.push(Math.pow(10, e));
  }
  if (ticks.length < 2) {
    const e = Math.round((loExp + hiExp) / 2);
    [1, 2, 5].forEach(mult => {
      const v = mult * Math.pow(10, e);
      const lv = Math.log10(v);
      if (lv >= loExp && lv <= hiExp) ticks.push(v);
    });
  }
  return Array.from(new Set(ticks)).sort((a, b) => a - b);
}

function fmtTick(v) {
  if (v >= 1) return String(v);
  return String(parseFloat(v.toPrecision(2)));
}

function drawPanel(svg, curves, opts) {
  opts = opts || {};
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const m = { left: 38, right: 8, top: 6, bottom: 20 };
  const innerW = W - m.left - m.right, innerH = H - m.top - m.bottom;

  let yMin = Infinity, yMax = -Infinity;
  const series = curves.map(c => {
    const ys = CONTRASTS.map(ct => threshold(ct, c.IN, c.Psi));
    yMin = Math.min(yMin, ...ys);
    yMax = Math.max(yMax, ...ys);
    return { ys, color: c.color };
  });
  const yLo = Math.log10(yMin) - 0.15, yHi = Math.log10(yMax) + 0.15;
  const xLo = Math.log10(CONTRAST_MIN), xHi = Math.log10(CONTRAST_MAX);

  const px = v => m.left + (Math.log10(v) - xLo) / (xHi - xLo) * innerW;
  const py = v => m.top + innerH - (Math.log10(v) - yLo) / (yHi - yLo) * innerH;

  svg.appendChild(svgEl('line', { x1: m.left, y1: m.top + innerH, x2: m.left + innerW, y2: m.top + innerH, class: 'axis-line' }));
  svg.appendChild(svgEl('line', { x1: m.left, y1: m.top, x2: m.left, y2: m.top + innerH, class: 'axis-line' }));

  if (opts.ticks !== false) {
    [0.01, 0.1, 1].forEach(v => {
      if (v < CONTRAST_MIN || v > CONTRAST_MAX) return;
      const t = svgEl('text', { x: px(v), y: H - 4, 'font-size': 9, 'text-anchor': 'middle' });
      t.textContent = v;
      svg.appendChild(t);
    });
  }

  niceLogTicks(yLo, yHi).forEach(v => {
    const y = py(v);
    svg.appendChild(svgEl('line', {
      x1: m.left - 3, y1: y, x2: m.left, y2: y, class: 'axis-line',
    }));
    const t = svgEl('text', {
      x: m.left - 6, y: y, 'font-size': 9, 'text-anchor': 'end', 'dominant-baseline': 'middle',
    });
    t.textContent = fmtTick(v);
    svg.appendChild(t);
  });

  series.forEach(s => {
    const d = CONTRASTS.map((c, i) => `${i === 0 ? 'M' : 'L'}${px(c).toFixed(1)},${py(s.ys[i]).toFixed(1)}`).join(' ');
    svg.appendChild(svgEl('path', { d, fill: 'none', stroke: s.color, 'stroke-width': opts.strokeWidth || 2 }));
  });
}

// ---- Question 1: subject small multiples ----
const grid = document.getElementById('subjectGrid');
DATA.subjects.forEach(s => {
  const panel = document.createElement('div');
  panel.className = 'subject-panel';
  const head = document.createElement('div');
  head.className = 'subject-panel-head';
  head.innerHTML = `<span class="sid">${s.subject}</span><span class="grp">${s.group}</span>`;
  panel.appendChild(head);
  const svg = svgEl('svg', { viewBox: '0 0 190 110', width: '100%', height: '100' });
  panel.appendChild(svg);
  grid.appendChild(panel);
  drawPanel(svg, s.eyes.map(e => ({ IN: e.IN, Psi: e.Psi, color: COLORS[e.colorGroup] })));
});

// subject table
const subjTable = document.getElementById('subjectTable');
subjTable.innerHTML = `<tr><th>Subject</th><th>Group</th><th>Eye</th><th>Role</th><th class="num">IN</th><th class="num">Psi</th></tr>` +
  DATA.subjects.flatMap(s => s.eyes.map(e => `<tr>
    <td>${s.subject}</td><td>${s.group}</td><td>${e.physicalEye}</td>
    <td><span class="dot ${e.colorGroup}"></span>${e.role}</td>
    <td class="num">${e.IN.toFixed(4)}</td>
    <td class="num">${e.Psi.toFixed(4)}${e.atBound ? '<span class="bound-mark"> &dagger;</span>' : ''}</td>
  </tr>`)).join('');

// ---- Question 2: group curves + stats, toggled by parameter ----
// each panel compares exactly 2 curves: first label = blue, second = orange
function renderGroupCurves() {
  const container = document.getElementById('groupCurveGrid');
  container.innerHTML = '';
  const defs = [
    { title: 'Control OD vs OS', labels: ['Control OD', 'Control OS'] },
    { title: 'Amblyopic vs Fellow eye', labels: ['Fellow eye', 'Amblyopic eye'] },
    { title: 'Amblyopes vs Controls (both eyes pooled)', labels: ['All Controls', 'All Amblyopes'] },
  ];
  defs.forEach(def => {
    const wrap = document.createElement('div');
    const label = document.createElement('div');
    label.className = 'panel-title';
    label.textContent = def.title;
    wrap.appendChild(label);
    const svg = svgEl('svg', { viewBox: '0 0 320 180', width: '100%', height: '170' });
    wrap.appendChild(svg);
    container.appendChild(wrap);
    const colors = [COLORS.blue, COLORS.orange];
    const curves = def.labels.map((l, i) => ({
      IN: DATA.groupMeans[l].IN, Psi: DATA.groupMeans[l].Psi, color: colors[i],
    }));
    drawPanel(svg, curves, { strokeWidth: 2.5 });
    const legend = document.createElement('div');
    legend.style.fontSize = '12px';
    legend.style.color = '#555';
    legend.style.marginTop = '4px';
    legend.innerHTML = def.labels.map((l, i) =>
      `<span class="dot ${i === 0 ? 'blue' : 'orange'}"></span>${l} (n=${DATA.groupMeans[l].n})`
    ).join('&nbsp;&nbsp;');
    wrap.appendChild(legend);
  });
}
renderGroupCurves();

function renderStatsTable(param) {
  const rows = DATA.stats.filter(r => r.parameter === param);
  const table = document.getElementById('statsTable');
  table.innerHTML = `<tr><th>Comparison</th><th>Design</th><th class="num">n1</th><th class="num">n2</th>
    <th class="num">t_p (Holm)</th><th class="num">u_p (Holm)</th><th class="num">Effect size</th><th class="num">95% CI</th>
    <th class="num">|&Delta; mean|</th><th class="num">vs MCD</th></tr>` +
    rows.map(r => {
      const sig = r.t_p_holm < 0.05;
      return `<tr>
        <td>${r.comparison}</td><td>${r.design}</td>
        <td class="num">${r.n1}</td><td class="num">${r.n2}</td>
        <td class="num"><span class="sig ${sig ? 'yes' : 'no'}">${r.t_p_holm.toFixed(3)}</span></td>
        <td class="num">${r.u_p_holm.toFixed(3)}</td>
        <td class="num">${r.effect_size.toFixed(2)}</td>
        <td class="num">[${r.ci_low.toFixed(2)}, ${r.ci_high.toFixed(2)}]</td>
        <td class="num">${r.group_mean_diff.toFixed(4)}</td>
        <td class="num"><span class="sig ${r.exceeds_mcd ? 'yes' : 'no'}">${r.exceeds_mcd ? 'exceeds' : 'below'}</span></td>
      </tr>`;
    }).join('');
}
renderStatsTable('IN');

document.getElementById('paramPills').addEventListener('click', e => {
  const btn = e.target.closest('button');
  if (!btn) return;
  document.querySelectorAll('#paramPills button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderStatsTable(btn.dataset.param);
});

</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
