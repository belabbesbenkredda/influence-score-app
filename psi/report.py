"""Stage 7 — Report and hand-check sample.

Writes out/report.html (single self-contained page, inline CSS/JS), copies it
to docs/index.html, and writes out/handcheck_sample.md (20 scored items for
phone review).
"""
from __future__ import annotations

import html
import json
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone

from psi import db

OXBLOOD = "#6B1F2B"
PAPER = "#F7F3EC"
INK = "#1C1A17"
HANDCHECK_N = 20
HANDCHECK_SEED = 20260903  # fixed so reruns produce the same 20 items


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def f3(v) -> str:
    return "—" if v is None else f"{v:.3f}"


def f1(v) -> str:
    return "—" if v is None else f"{v:.1f}"


def fnum(v) -> str:
    return "—" if v is None else f"{v:,.0f}"


CSS = f"""
:root {{ --ox: {OXBLOOD}; --paper: {PAPER}; --ink: {INK}; --rule: #D9D2C5; --muted: #6E675C; --band: #EFE9DE; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: var(--paper); color: var(--ink); font-family: Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.45; }}
body {{ padding: 0 0 4rem; }}
h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif; font-weight: 600; letter-spacing: -0.01em; margin: 0; }}
h1 {{ font-size: 2.4rem; line-height: 1.1; }}
h2 {{ font-size: 1.5rem; margin: 0 0 .75rem; border-bottom: 2px solid var(--ox); padding-bottom: .3rem; }}
h3 {{ font-size: 1.1rem; }}
.mono, td.num, th.num, .kpi b, .bar text, .flag {{ font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }}
header {{ border-top: 8px solid var(--ox); padding: 1.5rem 1.25rem 1rem; max-width: 1180px; margin: 0 auto; }}
header .kicker {{ color: var(--ox); text-transform: uppercase; letter-spacing: .12em; font-size: .8rem; font-family: 'IBM Plex Mono', monospace; }}
header p {{ max-width: 70ch; color: var(--muted); margin: .5rem 0 0; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 0 1.25rem; }}
section {{ margin: 2.25rem 0; }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; margin: 1.25rem 0 0; }}
.kpi {{ border: 1px solid var(--rule); background: #fff; padding: .6rem .8rem; }}
.kpi b {{ display: block; font-size: 1.5rem; color: var(--ox); font-weight: 500; }}
.kpi span {{ font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; border: 1px solid var(--rule); font-size: .92rem; }}
th, td {{ padding: .4rem .55rem; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; }}
th {{ background: var(--band); font-family: 'IBM Plex Mono', monospace; font-weight: 500; font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; cursor: pointer; white-space: nowrap; position: sticky; top: 0; }}
th.sorted::after {{ content: ' ▾'; color: var(--ox); }}
td.num, th.num {{ text-align: right; }}
tr:hover td {{ background: #FBF9F4; }}
.scroll {{ overflow-x: auto; }}
.conf-high {{ color: #2F6B3A; }} .conf-medium {{ color: #9A6A12; }} .conf-low {{ color: var(--muted); }}
.flag {{ font-size: .72rem; color: var(--muted); }}
.bar {{ width: 100%; height: auto; background: #fff; border: 1px solid var(--rule); }}
.bar rect.i {{ fill: var(--ox); }}
.bar text {{ font-size: 11px; fill: var(--ink); }}
.bar text.val {{ fill: var(--muted); }}
.topics {{ display: grid; grid-template-columns: 1fr; gap: .25rem; }}
.topic-row {{ display: grid; grid-template-columns: minmax(180px, 1.2fr) 3fr 3fr; gap: .5rem; align-items: center; font-size: .9rem; border-bottom: 1px solid var(--rule); padding: .3rem 0; }}
.topic-row .lab {{ font-size: .72rem; color: var(--muted); font-family: 'IBM Plex Mono', monospace; }}
.tbar {{ display: flex; align-items: center; gap: .4rem; }}
.tbar i {{ display: block; height: 12px; background: var(--ox); }}
.tbar i.cov {{ background: #8A8175; }}
.tbar span {{ font-family: 'IBM Plex Mono', monospace; font-size: .78rem; color: var(--muted); min-width: 3.5ch; }}
details {{ border: 1px solid var(--rule); background: #fff; margin: .4rem 0; }}
summary {{ cursor: pointer; padding: .55rem .8rem; font-family: 'Fraunces', Georgia, serif; font-weight: 600; display: flex; gap: 1rem; flex-wrap: wrap; align-items: baseline; }}
summary .meta {{ font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: .78rem; color: var(--muted); }}
.item {{ padding: .6rem .8rem .7rem; border-top: 1px solid var(--rule); }}
.item a {{ color: var(--ox); text-decoration: none; }}
.item a:hover {{ text-decoration: underline; }}
.item .just {{ color: var(--muted); font-size: .9rem; margin: .2rem 0 0; }}
.item .scores {{ font-family: 'IBM Plex Mono', monospace; font-size: .8rem; margin-top: .15rem; }}
.item .scores b {{ color: var(--ox); font-weight: 500; }}
.controls {{ display: flex; gap: .75rem; flex-wrap: wrap; margin: 0 0 .6rem; font-size: .85rem; }}
.controls label {{ font-family: 'IBM Plex Mono', monospace; }}
.controls input, .controls select {{ font: inherit; padding: .2rem .4rem; border: 1px solid var(--rule); background: #fff; }}
footer {{ max-width: 1180px; margin: 3rem auto 0; padding: 1.25rem; border-top: 2px solid var(--ox); font-size: .88rem; color: var(--muted); }}
footer ol {{ padding-left: 1.2rem; }}
footer a {{ color: var(--ox); }}
.legend span {{ display: inline-block; margin-right: 1rem; }}
@media (max-width: 720px) {{ h1 {{ font-size: 1.7rem; }} .topic-row {{ grid-template-columns: 1fr; }} th, td {{ padding: .3rem .4rem; }} }}
"""

JS = """
(function(){
  // sortable ranked table
  var table = document.getElementById('ranked');
  if (table) {
    var ths = table.querySelectorAll('th');
    ths.forEach(function(th, idx){
      th.addEventListener('click', function(){
        var tbody = table.tBodies[0];
        var rows = Array.prototype.slice.call(tbody.rows);
        var numeric = th.classList.contains('num');
        var asc = th.dataset.asc === '1';
        rows.sort(function(a, b){
          var x = a.cells[idx].dataset.v !== undefined ? a.cells[idx].dataset.v : a.cells[idx].textContent;
          var y = b.cells[idx].dataset.v !== undefined ? b.cells[idx].dataset.v : b.cells[idx].textContent;
          if (numeric) { x = x === '' ? -Infinity : parseFloat(x); y = y === '' ? -Infinity : parseFloat(y); return asc ? x - y : y - x; }
          return asc ? x.localeCompare(y) : y.localeCompare(x);
        });
        rows.forEach(function(r){ tbody.appendChild(r); });
        ths.forEach(function(t){ t.classList.remove('sorted'); });
        th.classList.add('sorted');
        th.dataset.asc = asc ? '0' : '1';
      });
    });
  }
  // filters
  var q = document.getElementById('q'), typeSel = document.getElementById('typeSel');
  function applyFilter(){
    var needle = (q.value || '').toLowerCase(), t = typeSel.value;
    document.querySelectorAll('#ranked tbody tr, #drill details').forEach(function(el){
      var name = (el.dataset.name || '').toLowerCase(), ty = el.dataset.type || '';
      var show = (!needle || name.indexOf(needle) >= 0) && (!t || ty === t);
      el.style.display = show ? '' : 'none';
    });
  }
  if (q && typeSel) { q.addEventListener('input', applyFilter); typeSel.addEventListener('change', applyFilter); }
  // jump from table row to drill-down
  document.querySelectorAll('#ranked tbody tr').forEach(function(tr){
    tr.addEventListener('click', function(){
      var d = document.getElementById('o-' + tr.dataset.id);
      if (d) { d.open = true; d.scrollIntoView({behavior: 'smooth', block: 'start'}); }
    });
  });
})();
"""


def bar_chart(rows: list[dict]) -> str:
    rows = [r for r in rows if r["i"] is not None][:40]
    if not rows:
        return "<p>No ranked outlets yet.</p>"
    h = 22
    w = 1100
    label_w = 260
    top = 10
    height = top + h * len(rows) + 10
    maxv = max(r["i"] for r in rows) or 1
    parts = [f'<svg class="bar" viewBox="0 0 {w} {height}" role="img" aria-label="Influence score by outlet, top {len(rows)}">']
    for k, r in enumerate(rows):
        y = top + k * h
        bw = (w - label_w - 90) * (r["i"] / maxv)
        parts.append(f'<text x="{label_w - 8}" y="{y + 15}" text-anchor="end">{esc(r["name"])[:40]}</text>')
        parts.append(f'<rect class="i" x="{label_w}" y="{y + 4}" width="{bw:.1f}" height="{h - 8}"><title>{esc(r["name"])}: I = {r["i"]:.4f}</title></rect>')
        parts.append(f'<text class="val" x="{label_w + bw + 6:.1f}" y="{y + 15}">{r["i"]:.4f}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def topic_panel(mip: list[dict], coverage: Counter, n_scored: int) -> str:
    out = ['<div class="topics">', '<div class="topic-row"><div class="lab">TOPIC</div><div class="lab">MIP SHARE (Gallup)</div><div class="lab">COVERAGE SHARE (scored items)</div></div>']
    maxv = max([m["mip_share"] for m in mip] + [coverage[m["topic"]] / n_scored if n_scored else 0 for m in mip] + [0.01])
    for m in mip:
        cov = coverage[m["topic"]] / n_scored if n_scored else 0
        out.append('<div class="topic-row">'
                   f'<div>{esc(m["label"])}<br><span class="lab">{esc(m["topic"])}</span></div>'
                   f'<div class="tbar"><i style="width:{100 * m["mip_share"] / maxv:.1f}%"></i><span>{100 * m["mip_share"]:.0f}%</span></div>'
                   f'<div class="tbar"><i class="cov" style="width:{100 * cov / maxv:.1f}%"></i><span>{100 * cov:.0f}%</span></div>'
                   '</div>')
    out.append("</div>")
    return "\n".join(out)


def run() -> None:
    with db.db() as con:
        ranked = db.rows(con, """SELECT os.*, o.name, o.type, o.url, r.reach_raw, r.reach_unit, r.reach_source, r.reach_source_url, r.reach_date, r.flag AS reach_flag
                                 FROM outlet_scores os JOIN outlets o USING(outlet_id) LEFT JOIN reach r USING(outlet_id)
                                 WHERE os.country=? ORDER BY (os.i IS NULL), os.i DESC, os.d DESC""", (db.COUNTRY,))
        items = db.rows(con, """SELECT i.item_id, i.outlet_id, i.title, i.url, i.published_at, i.word_count, i.fetch_method,
                                       s.topic, s.logos, s.ethos, s.pathos, s.d, s.justification, s.model, s.prompt_version
                                FROM items i LEFT JOIN scores s USING(item_id) WHERE i.country=? ORDER BY i.outlet_id, i.published_at DESC""", (db.COUNTRY,))
        mip = db.rows(con, "SELECT topic, mip_share, gallup_categories, survey_date FROM mip WHERE country=? ORDER BY mip_share DESC", (db.COUNTRY,))
        weights = db.rows(con, "SELECT * FROM type_weights WHERE country=? ORDER BY weight DESC", (db.COUNTRY,))
        meta = {k: db.get_meta(con, k) for k in ("mip_survey_date", "mip_provenance", "sample_run", "score_run")}
        n_outlets = con.execute("SELECT COUNT(*) FROM outlets WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        n_sourced = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND reach_raw IS NOT NULL", (db.COUNTRY,)).fetchone()[0]
        n_unsourced = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND flag='unsourced'", (db.COUNTRY,)).fetchone()[0]
        n_self = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND flag LIKE 'self_reported%'", (db.COUNTRY,)).fetchone()[0]
        n_unver = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND flag LIKE '%unverified%'", (db.COUNTRY,)).fetchone()[0]
        spend = con.execute("SELECT COALESCE(SUM(cost_usd),0), COUNT(*) FROM scores").fetchone()
        pub_range = con.execute("SELECT MIN(published_at), MAX(published_at) FROM items WHERE country=? AND published_at IS NOT NULL", (db.COUNTRY,)).fetchone()

    import csv
    labels = {}
    with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels[r["topic"]] = r["label"]
    for m in mip:
        m["label"] = labels.get(m["topic"], m["topic"])
    mip_share = {m["topic"]: m["mip_share"] for m in mip}

    scored = [it for it in items if it["d"] is not None]
    coverage = Counter(it["topic"] for it in scored)
    by_outlet = defaultdict(list)
    for it in items:
        by_outlet[it["outlet_id"]].append(it)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_ranked = sum(1 for r in ranked if r["i"] is not None)
    types = sorted({r["type"] for r in ranked})

    # ---- ranked table
    trs = []
    for r in ranked:
        flag = r["reach_flag"] or "unsourced"
        trs.append(
            f'<tr data-id="{esc(r["outlet_id"])}" data-name="{esc(r["name"])}" data-type="{esc(r["type"])}">'
            f'<td class="num" data-v="{r["rank"] if r["rank"] is not None else ""}">{r["rank"] if r["rank"] is not None else "—"}</td>'
            f'<td>{esc(r["name"])}<br><span class="flag">{esc(flag)}{" · " + esc(r["flags"]) if r["flags"] else ""}</span></td>'
            f'<td>{esc(r["type"])}</td>'
            f'<td class="num" data-v="{r["r"] if r["r"] is not None else ""}">{f3(r["r"])}</td>'
            f'<td class="num" data-v="{r["s"] if r["s"] is not None else ""}">{f3(r["s"])}</td>'
            f'<td class="num" data-v="{r["d"] if r["d"] is not None else ""}">{f3(r["d"])}</td>'
            f'<td class="num" data-v="{r["i"] if r["i"] is not None else ""}"><b>{f3(r["i"])}</b></td>'
            f'<td class="num" data-v="{r["n_scored"]}">{r["n_scored"]}</td>'
            f'<td class="conf-{esc(r["confidence"])}">{esc(r["confidence"])}</td>'
            "</tr>")

    # ---- drill-down
    drill = []
    for r in ranked:
        its = by_outlet.get(r["outlet_id"], [])
        reach_line = (f'reach {fnum(r["reach_raw"])} {esc(r["reach_unit"] or "")} — <a href="{esc(r["reach_source_url"])}">{esc(r["reach_source"])}</a> ({esc(r["reach_date"] or "n.d.")})'
                      if r["reach_raw"] is not None else "reach: unsourced")
        item_html = []
        for it in its:
            if it["d"] is None:
                item_html.append(f'<div class="item"><a href="{esc(it["url"])}">{esc(it["title"])}</a> <span class="flag">{esc(it["fetch_method"])} · {it["word_count"]} words · not scored</span></div>')
                continue
            item_html.append(
                f'<div class="item"><a href="{esc(it["url"])}">{esc(it["title"])}</a> '
                f'<span class="flag">{esc((it["published_at"] or "")[:10])} · {esc(it["fetch_method"])} · {it["word_count"]} w</span>'
                f'<div class="scores">topic <b>{esc(it["topic"])}</b> (S {mip_share.get(it["topic"], 0):.2f}) · L <b>{it["logos"]}</b> E <b>{it["ethos"]}</b> P <b>{it["pathos"]}</b> · D <b>{it["d"]}</b>/30</div>'
                f'<p class="just">{esc(it["justification"])}</p></div>')
        drill.append(
            f'<details id="o-{esc(r["outlet_id"])}" data-name="{esc(r["name"])}" data-type="{esc(r["type"])}">'
            f'<summary>{"#" + str(r["rank"]) + " " if r["rank"] else ""}{esc(r["name"])} '
            f'<span class="meta">{esc(r["type"])} · R {f3(r["r"])} · S {f3(r["s"])} · D {f3(r["d"])} · I {f3(r["i"])} · {r["n_scored"]} scored · {esc(r["confidence"])}</span></summary>'
            f'<div class="item flag">{reach_line} · <a href="{esc(r["url"])}">{esc(r["url"])}</a></div>'
            + "".join(item_html) + "</details>")

    weights_txt = ", ".join(f'{w["type"]} {w["weight"]:.2f}' + (f' ({w["flag"]})' if w["flag"] not in (None, "ok") else "") for w in weights if w["weight"] is not None)
    type_opts = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in types)
    score_meta = meta.get("score_run") or {}

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSI Influence Engine v0.2 — United States</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
<header>
  <div class="kicker">Public Sphere Index · Influence Engine v0.2 · United States</div>
  <h1>The opinion-forming core of the American public sphere</h1>
  <p>Outlets ranked by the Influence Formula <span class="mono">I = R × S × D</span>: third-party reach, Gallup "Most Important Problem" salience of what they cover, and LLM-scored discursiveness (Logos + Ethos + Pathos). Generated {generated}.</p>
  <div class="kpis">
    <div class="kpi"><b>{n_outlets}</b><span>outlets</span></div>
    <div class="kpi"><b>{n_sourced}</b><span>sourced reach</span></div>
    <div class="kpi"><b>{len(items)}</b><span>items sampled</span></div>
    <div class="kpi"><b>{len(scored)}</b><span>items scored</span></div>
    <div class="kpi"><b>{n_ranked}</b><span>outlets ranked</span></div>
    <div class="kpi"><b>${spend[0]:.2f}</b><span>scoring spend</span></div>
  </div>
</header>
<main>
<section id="table">
  <h2>Ranked outlets</h2>
  <div class="controls"><label>Filter <input id="q" type="search" placeholder="outlet name"></label>
    <label>Type <select id="typeSel"><option value="">all</option>{type_opts}</select></label>
    <span class="flag">Click a column to sort; click a row to open its items.</span></div>
  <div class="scroll"><table id="ranked"><thead><tr>
    <th class="num">Rank</th><th>Outlet</th><th>Type</th><th class="num">R</th><th class="num">S</th><th class="num">D</th><th class="num">I</th><th class="num">n</th><th>Confidence</th>
  </tr></thead><tbody>{"".join(trs)}</tbody></table></div>
</section>
<section id="chart">
  <h2>Influence score, top {min(40, n_ranked)}</h2>
  {bar_chart(ranked)}
</section>
<section id="topics">
  <h2>Topic salience vs. coverage</h2>
  <p class="flag">Left bars: share of Americans naming the topic as the most important problem (Gallup, {esc(meta.get("mip_survey_date"))}). Right bars: share of scored items assigned to the topic ({len(scored)} items). Percentages can exceed 100 in total because Gallup allows multiple mentions.</p>
  {topic_panel(mip, coverage, len(scored))}
</section>
<section id="drill">
  <h2>Per-outlet drill-down</h2>
  <p class="flag">Every sampled item with its topic, Logos / Ethos / Pathos and the model's justification. Reach source linked under each outlet.</p>
  {"".join(drill)}
</section>
</main>
<footer>
  <h3>Methodology in eight lines</h3>
  <ol>
    <li>Outlet universe: {n_outlets} US national, English-language (plus Univision/Telemundo) opinion-forming outlets, editable in <span class="mono">data/outlets_seed.csv</span>.</li>
    <li>R (reach): one third-party audience figure per outlet with URL and verbatim quote, fact-checked by a second pass; normalised within type then across types with Pew platform weights ({esc(weights_txt)}).</li>
    <li>S (salience): Gallup Most Important Problem, {esc(meta.get("mip_survey_date"))} column, collapsed into {len(mip)} topics; an item's S is its topic's share.</li>
    <li>Content sample: up to 8 items per outlet from the last 14 days via RSS full text, page fetch, outlet transcript pages, or GDELT; minimum 300 words.</li>
    <li>D (discursiveness): each item scored once by <span class="mono">{esc(score_meta.get("model", "claude-sonnet-5"))}</span> with rubric <span class="mono">{esc(score_meta.get("prompt_version", "score_v1"))}</span> for topic, Logos, Ethos, Pathos (0–10 each); D = sum / 30.</li>
    <li>Outlet score: I = R × S × D with S and D averaged over the outlet's scored items; outlets without sourced reach are listed but unranked.</li>
    <li>Confidence: high = 6+ scored items and sourced reach; medium = 3–5 items; low otherwise.</li>
    <li>Nothing is estimated by hand: missing figures are null and flagged, never guessed.</li>
  </ol>
  <p><b>Data dates.</b> Gallup MIP: {esc(meta.get("mip_survey_date"))} ({esc(meta.get("mip_provenance"))}). Items published {esc((pub_range[0] or "")[:10])} to {esc((pub_range[1] or "")[:10])}. Sampled {esc((meta.get("sample_run") or {}).get("at", "")[:16])}. Scored {esc(score_meta.get("at", "")[:16])}.</p>
  <p class="legend"><b>Provenance flags.</b> <span><b>ok</b> third-party figure, verified</span> <span><b>self_reported</b> publisher-stated</span> <span><b>unverified</b> source page could not be re-fetched ({n_unver})</span> <span><b>unsourced</b> no figure found, R = null ({n_unsourced})</span> <span><b>self_reported</b> count: {n_self}</span></p>
  <p>Public Sphere Index — <a href="https://publicspheres.org">publicspheres.org</a>. Code and data: this repository (<span class="mono">python run.py all</span> reproduces everything).</p>
</footer>
<script>{JS}</script>
</body></html>
"""
    db.OUT.mkdir(parents=True, exist_ok=True)
    (db.OUT / "report.html").write_text(page, encoding="utf-8")
    (db.ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(db.OUT / "report.html", db.ROOT / "docs" / "index.html")

    # ---- hand-check sample
    rng = random.Random(HANDCHECK_SEED)
    names = {r["outlet_id"]: r["name"] for r in ranked}
    pool = [it for it in scored]
    sample = rng.sample(pool, min(HANDCHECK_N, len(pool)))
    lines = [f"# Hand-check sample — {len(sample)} scored items", "",
             f"Generated {generated}. Random seed {HANDCHECK_SEED} (same items on rerun).",
             "Model: " + esc(score_meta.get("model", "")) + ", rubric " + esc(score_meta.get("prompt_version", "")) + ".", "",
             "For each item: does the topic fit? Are L/E/P defensible? Write a verdict.", ""]
    for k, it in enumerate(sample, 1):
        lines += [f"## {k}. {it['title']}", "",
                  f"- Outlet: {names.get(it['outlet_id'], it['outlet_id'])}",
                  f"- Link: {it['url']}",
                  f"- Topic: `{it['topic']}` (S = {mip_share.get(it['topic'], 0):.2f})",
                  f"- L/E/P: {it['logos']} / {it['ethos']} / {it['pathos']}  → D = {it['d']}/30",
                  f"- Justification: {it['justification']}",
                  "- BB verdict:", ""]
    (db.OUT / "handcheck_sample.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote out/report.html ({len(page)//1024} KB), docs/index.html, out/handcheck_sample.md ({len(sample)} items)")


if __name__ == "__main__":
    run()
