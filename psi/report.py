"""Stage 7 — Report and hand-check.

Item-first: the page ranks individual items, because that is what the framework
says influence is a property of. Outlets appear as a rollup below.

Visual identity is the diagnostic-instrument one — Archivo / Source Serif 4 /
JetBrains Mono on a cool clinical ground — shared with the methodology review
console, so the project reads as one instrument rather than two unrelated pages.
"""
from __future__ import annotations

import base64
import csv
import html
import random
import shutil
from collections import Counter
from datetime import datetime, timezone

from psi import audience, db

HANDCHECK_N = 20
HANDCHECK_SEED = 20260904
FONT_DIR = db.ROOT / "psi" / "assets" / "fonts"

CSS = """
:root{--ground:#EEF1EF;--surface:#FFFFFF;--raise:#F7F9F8;--ink:#131C19;--muted:#5A6763;
 --rule:#CFD8D4;--rule-soft:#E2E8E5;--signal:#0E5C4A;--signal-ink:#FFFFFF;
 --hot:#A5372A;--warm:#8A6512;--cool:#4A5F58;--focus:#0E5C4A}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ground:#0D1512;--surface:#131D19;--raise:#182420;--ink:#E4EBE7;--muted:#93A39D;
 --rule:#2A3833;--rule-soft:#202C28;--signal:#4FBFA0;--signal-ink:#08120F;
 --hot:#E08476;--warm:#D7AC55;--cool:#8AA79C;--focus:#4FBFA0}}
:root[data-theme="dark"]{--ground:#0D1512;--surface:#131D19;--raise:#182420;--ink:#E4EBE7;--muted:#93A39D;
 --rule:#2A3833;--rule-soft:#202C28;--signal:#4FBFA0;--signal-ink:#08120F;
 --hot:#E08476;--warm:#D7AC55;--cool:#8AA79C;--focus:#4FBFA0}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;font-size:17px;line-height:1.55}
h1,h2,h3,.ui{font-family:Archivo,"Helvetica Neue",Arial,sans-serif}
h1,h2,h3{margin:0;text-wrap:balance;letter-spacing:-.015em}
.mono,td.num,th,.tag,.sid,.figs,.meta{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
a{color:var(--signal)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header{border-top:6px solid var(--signal);background:var(--surface);border-bottom:1px solid var(--rule)}
header .wrap{padding:26px 20px 20px}
.eyebrow{font-family:"JetBrains Mono",monospace;font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:var(--signal)}
h1{font-size:2rem;font-weight:700;margin:.35rem 0 .5rem}
.lede{max-width:66ch;color:var(--muted);margin:0}
.counts{display:flex;flex-wrap:wrap;margin-top:18px;border:1px solid var(--rule);background:var(--raise)}
.count{flex:1 1 130px;padding:9px 12px;border-right:1px solid var(--rule)}
.count:last-child{border-right:0}
.count b{display:block;font-family:"JetBrains Mono",monospace;font-size:1.15rem;font-weight:500}
.count span{font-family:Archivo,sans-serif;font-size:.64rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
section{margin:38px 0}
h2{font-size:1.12rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding-bottom:7px;border-bottom:2px solid var(--ink);margin-bottom:4px}
.sub{color:var(--muted);font-size:.92rem;margin:8px 0 16px;max-width:70ch}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--rule);font-size:.88rem}
th,td{padding:6px 8px;border-bottom:1px solid var(--rule-soft);text-align:left;vertical-align:top}
th{background:var(--raise);font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;font-weight:500;
   position:sticky;top:0;cursor:pointer;white-space:nowrap;color:var(--muted)}
th.sorted{color:var(--signal)}
td.num,th.num{text-align:right}
tr:hover td{background:var(--raise)}
.itemtitle{font-family:"Source Serif 4",serif;font-size:.95rem}
.itemtitle a{text-decoration:none}
.itemtitle a:hover{text-decoration:underline}
.meta{font-size:.68rem;color:var(--muted)}
.lep{font-family:"JetBrains Mono",monospace;font-size:.72rem;color:var(--muted)}
.lep b{color:var(--ink);font-weight:500}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 10px;font-size:.85rem;align-items:center}
.controls input,.controls select{font-family:"JetBrains Mono",monospace;font-size:.8rem;padding:5px 7px;
  border:1px solid var(--rule);background:var(--surface);color:var(--ink)}
.controls label{font-family:Archivo,sans-serif;font-size:.66rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.trow{display:grid;grid-template-columns:minmax(150px,1.1fr) 1fr 1fr;gap:.5rem;align-items:center;
  border-bottom:1px solid var(--rule-soft);padding:5px 0;font-size:.88rem}
.trow .lab{font-family:"JetBrains Mono",monospace;font-size:.66rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.bar{display:flex;align-items:center;gap:.4rem}
.bar i{display:block;height:11px;background:var(--signal)}
.bar i.cov{background:var(--cool)}
.bar span{font-family:"JetBrains Mono",monospace;font-size:.72rem;color:var(--muted);min-width:3.6ch}
.assump{border:1px solid var(--rule);background:var(--surface)}
.assump div{display:grid;grid-template-columns:minmax(190px,auto) 5rem 1fr;gap:.6rem;padding:7px 11px;border-bottom:1px solid var(--rule-soft);font-size:.85rem}
.assump div:last-child{border-bottom:0}
.assump code{font-family:"JetBrains Mono",monospace;font-size:.76rem;color:var(--hot)}
.assump b{font-family:"JetBrains Mono",monospace;font-weight:500}
.delta{border:1px solid var(--rule);background:var(--surface);padding:12px 14px}
.delta .n{font-family:"JetBrains Mono",monospace;font-size:1.5rem;color:var(--signal)}
footer{border-top:2px solid var(--signal);background:var(--surface);margin-top:44px}
footer .wrap{padding:22px 20px 34px;font-size:.9rem;color:var(--muted)}
footer h2{border:0;padding:0;margin-bottom:10px;color:var(--ink)}
footer ol{padding-left:1.15rem}footer li{margin-bottom:6px}
.controls label{max-width:100%;display:inline-flex;align-items:center;gap:.4rem;min-width:0}
.controls input,.controls select{max-width:100%;min-width:0;flex:1 1 auto}
@media(max-width:720px){
 body{font-size:16px}h1{font-size:1.45rem}.wrap{padding:0 14px}.count{flex:1 1 45%;border-bottom:1px solid var(--rule)}
 .trow{grid-template-columns:1fr}
 .assump div{grid-template-columns:1fr;gap:.15rem}
 table{font-size:.82rem}th,td{padding:5px 6px}
 .controls{flex-direction:column;align-items:stretch}
 /* the seven-column item table becomes one card per item */
 #items thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
 #items,#items tbody,#items tr,#items td{display:block;width:auto}
 #items{border:0;background:none}
 #items tr{border:1px solid var(--rule-soft);background:var(--surface);margin-bottom:8px;padding:9px 11px}
 #items tr:hover td{background:none}
 #items td{border:0;padding:0;text-align:left}
 #items td:nth-child(1){display:inline-block;width:2.2rem;color:var(--signal);font-size:1rem;vertical-align:top}
 #items td:nth-child(2){display:inline-block;width:calc(100% - 2.6rem);vertical-align:top}
 #items td:nth-child(n+3){display:inline-block;margin:.35rem .8rem 0 0;font-size:.78rem}
 #items td:nth-child(3){margin-left:2.2rem}
 #items td:nth-child(3)::before{content:"R "}
 #items td:nth-child(4)::before{content:"S "}
 #items td:nth-child(5)::before{content:"D "}
 #items td:nth-child(6)::before{content:"I "}
 #items td:nth-child(7)::before{content:"reached "}
 #items td:nth-child(n+3)::before{color:var(--muted);font-size:.66rem;letter-spacing:.05em}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = """
(function(){
 var t=document.getElementById('items');if(!t)return;
 var ths=t.querySelectorAll('th');
 ths.forEach(function(th,i){th.addEventListener('click',function(){
   var tb=t.tBodies[0],rows=[].slice.call(tb.rows),num=th.classList.contains('num'),asc=th.dataset.asc==='1';
   rows.sort(function(a,b){
     var x=a.cells[i].dataset.v!==undefined?a.cells[i].dataset.v:a.cells[i].textContent;
     var y=b.cells[i].dataset.v!==undefined?b.cells[i].dataset.v:b.cells[i].textContent;
     if(num){x=x===''?-Infinity:parseFloat(x);y=y===''?-Infinity:parseFloat(y);return asc?x-y:y-x}
     return asc?x.localeCompare(y):y.localeCompare(x)});
   rows.forEach(function(r){tb.appendChild(r)});
   ths.forEach(function(o){o.classList.remove('sorted')});th.classList.add('sorted');th.dataset.asc=asc?'0':'1';
 })});
 var q=document.getElementById('q'),ty=document.getElementById('ty'),tp=document.getElementById('tp'),cnt=document.getElementById('shown');
 function f(){var n=(q.value||'').toLowerCase(),a=ty.value,b=tp.value,k=0;
  [].forEach.call(t.tBodies[0].rows,function(r){
    var ok=(!n||r.dataset.s.indexOf(n)>=0)&&(!a||r.dataset.type===a)&&(!b||r.dataset.topics.indexOf(b)>=0);
    r.style.display=ok?'':'none';if(ok)k++});
  cnt.textContent=k}
 [q,ty,tp].forEach(function(e){e.addEventListener('input',f);e.addEventListener('change',f)});f();
})();
"""


def esc(v):
    return html.escape("" if v is None else str(v))


def font_css() -> str:
    faces = FONT_DIR / "faces.css"
    if not faces.exists():
        return "/* bundled fonts absent; system stacks in use */"
    css = faces.read_text(encoding="utf-8")
    for path in FONT_DIR.glob("*.woff2"):
        css = css.replace("url(FONT:%s)" % path.name,
                          "url(data:font/woff2;base64,%s)" % base64.b64encode(path.read_bytes()).decode("ascii"))
    return css


def f(v, n=3):
    return "—" if v is None else ("%.*f" % (n, v))


def run() -> None:
    with db.db() as con:
        items = db.rows(con, """
            SELECT s.*, i.title, i.url, i.published_at, i.word_count, i.fetch_method,
                   o.name AS outlet, o.type
            FROM item_scores s JOIN items i USING(item_id) JOIN outlets o USING(outlet_id)
            WHERE s.country=? ORDER BY (s.i IS NULL), s.i DESC""", (db.COUNTRY,))
        sc = {r["item_id"]: r for r in db.rows(con, "SELECT * FROM scores2 WHERE prompt_version='score_v2'")}
        for r in db.rows(con, "SELECT * FROM scores"):
            sc.setdefault(r["item_id"], dict(r))
        tops = {}
        for r in db.rows(con, "SELECT item_id, topic, share FROM item_topics WHERE prompt_version='score_v2'"):
            tops.setdefault(r["item_id"], []).append((r["topic"], r["share"]))
        outlets = db.rows(con, """SELECT os.*, o.name, o.type, r.reach_raw, r.reach_unit, r.flag AS reach_flag,
                                         r.reach_source, r.reach_source_url
                                  FROM outlet_scores os JOIN outlets o USING(outlet_id) LEFT JOIN reach r USING(outlet_id)
                                  WHERE os.country=? ORDER BY (os.i IS NULL), os.i DESC""", (db.COUNTRY,))
        mip = db.rows(con, "SELECT topic, mip_share FROM mip WHERE country=? ORDER BY mip_share DESC", (db.COUNTRY,))
        meta = {k: db.get_meta(con, k) for k in ("mip_survey_date", "sample_run", "score_run", "aggregate_run")}
        spend = con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores2").fetchone()[0] + \
            con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores").fetchone()[0]
        n_out = con.execute("SELECT COUNT(*) FROM outlets WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        n_reach = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND reach_raw IS NOT NULL", (db.COUNTRY,)).fetchone()[0]
        pub = con.execute("SELECT MIN(published_at),MAX(published_at) FROM items WHERE published_at IS NOT NULL").fetchone()

    labels = {}
    with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            labels[r["topic"]] = r["label"]
    mip_share = {m["topic"]: m["mip_share"] for m in mip}

    # proportional coverage mass
    mass = Counter()
    for iid, lst in tops.items():
        for t, share in lst:
            mass[t] += share
    total_mass = sum(mass.values()) or 1

    ranked = [x for x in items if x["i"] is not None]
    types = sorted({x["type"] for x in items if x["type"]})
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = []
    for x in items:
        s = sc.get(x["item_id"], {})
        tl = sorted(tops.get(x["item_id"], []), key=lambda kv: -kv[1])
        tstr = ", ".join("%s %.0f%%" % (t, 100 * v) for t, v in tl[:3]) or (s.get("topic") or "")
        rows_html.append(
            '<tr data-s="%s" data-type="%s" data-topics="%s">'
            '<td class="num" data-v="%s">%s</td>'
            '<td class="itemtitle"><a href="%s" target="_blank" rel="noopener">%s</a>'
            '<div class="meta">%s &middot; %s &middot; %s &middot; %d w</div>'
            '<div class="lep">L <b>%s</b> E <b>%s</b> P <b>%s</b> &middot; %s</div></td>'
            '<td class="num" data-v="%s">%s</td><td class="num" data-v="%s">%s</td>'
            '<td class="num" data-v="%s">%s</td><td class="num" data-v="%s"><b>%s</b></td>'
            '<td class="num" data-v="%s">%s</td></tr>'
            % (esc(((x["outlet"] or "") + " " + (x["title"] or "")).lower()), esc(x["type"]),
               esc(" ".join(t for t, _ in tl)),
               x["rank"] if x["rank"] else "", x["rank"] if x["rank"] else "—",
               esc(x["url"]), esc((x["title"] or "(untitled)")[:110]),
               esc(x["outlet"]), esc(x["type"]), esc((x["published_at"] or "")[:10]), x["word_count"] or 0,
               s.get("logos", "—"), s.get("ethos", "—"), s.get("pathos", "—"), esc(tstr),
               x["r"] if x["r"] is not None else "", f(x["r"], 5),
               x["s"] if x["s"] is not None else "", f(x["s"]),
               x["d"] if x["d"] is not None else "", f(x["d"], 2),
               x["i"] if x["i"] is not None else "", f(x["i"], 7),
               x["r_people"] if x["r_people"] is not None else "",
               ("%,.0f" % x["r_people"]).replace("%,.0f", "") if False else (f"{x['r_people']:,.0f}" if x["r_people"] else "—")))

    orows = []
    for o in outlets:
        orows.append('<tr><td class="num">%s</td><td>%s<div class="meta">%s &middot; %s</div></td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num"><b>%s</b></td><td class="num">%s</td><td>%s</td></tr>'
                     % (o["rank"] or "—", esc(o["name"]), esc(o["type"]), esc(o["reach_flag"] or ""),
                        f(o["r"], 5), f(o["s"]), f(o["d"], 2), f(o["i"], 7), o["n_scored"], esc(o["confidence"])))

    trows = []
    maxv = max([m["mip_share"] for m in mip] + [mass[m["topic"]] / total_mass for m in mip] + [0.01])
    for m in mip:
        cov = mass[m["topic"]] / total_mass
        trows.append('<div class="trow"><div>%s<br><span class="lab">%s</span></div>'
                     '<div class="bar"><i style="width:%.1f%%"></i><span>%.0f%%</span></div>'
                     '<div class="bar"><i class="cov" style="width:%.1f%%"></i><span>%.0f%%</span></div></div>'
                     % (esc(labels.get(m["topic"], m["topic"])), esc(m["topic"]),
                        100 * m["mip_share"] / maxv, 100 * m["mip_share"], 100 * cov / maxv, 100 * cov))

    arows = "".join('<div><span>%s</span><b>%s</b><span class="sub" style="margin:0">%s</span></div>'
                    % (esc(k), esc(v[0]), esc(v[1])) for k, v in audience.ASSUMPTIONS.items())

    topt = "".join('<option value="%s">%s</option>' % (esc(t), esc(labels.get(t, t))) for t in sorted(mass, key=lambda k: -mass[k]))
    tyopt = "".join('<option value="%s">%s</option>' % (esc(t), esc(t)) for t in types)

    page = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSI Influence Engine v0.3 — United States</title>
<style>%s
%s</style></head><body>
<header><div class="wrap">
<div class="eyebrow">Public Sphere Index &middot; Influence Engine v0.3 &middot; United States</div>
<h1>What actually moved American opinion</h1>
<p class="lede">Individual items ranked by <span class="mono">I = R &times; S &times; D</span>. R is the estimated share of US adults reaching that item, S is how much of it addresses what Americans say matters, D is its persuasive force. Outlets appear below as a rollup. Generated %s.</p>
<div class="counts">
<div class="count"><b>%d</b><span>items ranked</span></div>
<div class="count"><b>%d</b><span>outlets</span></div>
<div class="count"><b>%d</b><span>with sourced reach</span></div>
<div class="count"><b>%s</b><span>items published</span></div>
<div class="count"><b>$%.2f</b><span>scoring spend</span></div>
</div></div></header><main class="wrap">

<section><h2>Most influential items</h2>
<p class="sub">The primary object of the index. R is a penetration rate, so the numbers are small and absolute: 0.006 means roughly six in a thousand US adults. Click a column to sort, or filter by outlet type and topic.</p>
<div class="controls">
<label>Search <input id="q" type="search" placeholder="outlet or headline"></label>
<label>Type <select id="ty"><option value="">all</option>%s</select></label>
<label>Topic <select id="tp"><option value="">all</option>%s</select></label>
<span class="meta"><b id="shown">0</b> shown</span></div>
<div class="scroll"><table id="items"><thead><tr>
<th class="num">#</th><th>Item</th><th class="num">R</th><th class="num">S</th><th class="num">D</th>
<th class="num">I</th><th class="num">people</th></tr></thead><tbody>%s</tbody></table></div></section>

<section><h2>Topic salience against coverage</h2>
<p class="sub">Left: share of Americans naming the topic as the most important problem (Gallup, %s). Right: share of the corpus devoted to it, measured proportionally — an item counts fractionally towards every topic it addresses, which is what the single-label rule in v0.2 got wrong.</p>
%s</section>

<section><h2>Outlets, as a rollup</h2>
<p class="sub">The influence of one representative item, not a period total: sampling is capped per outlet, so a total would rank outlets by how many of their items happened to be fetchable. A single outlet dominating the item list above is a finding, not a fault.</p>
<div class="scroll"><table><thead><tr><th class="num">#</th><th>Outlet</th><th class="num">R</th><th class="num">S</th>
<th class="num">D</th><th class="num">I per item</th><th class="num">n</th><th>confidence</th></tr></thead>
<tbody>%s</tbody></table></div></section>

<section><h2>The assumptions inside R</h2>
<p class="sub">Every medium reports a different currency — viewers, visits, listeners, subscribers. Converting them into one quantity (people reaching one item) needs the constants below. None of them is measured; each is a stated assumption, gathered in <span class="mono">psi/audience.py</span> so it can be replaced one at a time. The digital divisor is the weakest.</p>
<div class="assump">%s</div>
<p class="sub" style="margin-top:10px">Denominator: %s US adults — %s.</p></section>
</main>
<footer><div class="wrap"><h2>Method, in eight lines</h2><ol>
<li>Universe: %d national outlets across six media; %d carry a sourced third-party audience figure, each with a URL, a verbatim quote and a date.</li>
<li>R: the outlet's audience figure converted to people reaching one item, divided by US adults. Leader-normalisation and platform weights are gone — R is now absolute.</li>
<li>S: Gallup's Most Important Problem (%s), applied proportionally across every topic an item addresses.</li>
<li>D: Logos + Ethos + Pathos, each 0-10, from rubric <span class="mono">score_v2</span>. Ethos is the speaker's standing with their own audience, never their fairness — the framework must catch both a demagogue and a statesman.</li>
<li>I = R &times; S &times; D per item; outlets are the mean of their items.</li>
<li>Corpus: %s items published %s to %s, fetched from RSS, article pages and published transcripts.</li>
<li>Known gap: the corpus is concentrated in a few days and skewed towards outlets that permit automated fetching. Paywalled papers and untranscribed audio are under-represented.</li>
<li>Nothing is estimated silently: unsourced reach is null, and every modelling constant is named above.</li>
</ol></div></footer>
<script>%s</script></body></html>""" % (
        font_css(), CSS, generated, len(ranked), n_out, n_reach,
        len(items), spend,
        tyopt, topt, "".join(rows_html), esc(meta.get("mip_survey_date")), "".join(trows),
        "".join(orows), arows, f"{audience.US_ADULTS:,}", esc(audience.US_ADULTS_SOURCE),
        n_out, n_reach, esc(meta.get("mip_survey_date")), len(items),
        esc((pub[0] or "")[:10]), esc((pub[1] or "")[:10]), JS)

    db.OUT.mkdir(parents=True, exist_ok=True)
    (db.OUT / "report.html").write_text(page, encoding="utf-8")
    (db.ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(db.OUT / "report.html", db.ROOT / "docs" / "index.html")

    rng = random.Random(HANDCHECK_SEED)
    pool = [x for x in items if x["i"] is not None]
    sample = rng.sample(pool, min(HANDCHECK_N, len(pool)))
    lines = ["# Hand-check sample — %d ranked items" % len(sample), "",
             "Generated %s, seed %d. Rubric score_v2." % (generated, HANDCHECK_SEED), "",
             "Ethos is the speaker's standing with their own audience, not their fairness.", ""]
    for k, x in enumerate(sample, 1):
        s = sc.get(x["item_id"], {})
        tl = sorted(tops.get(x["item_id"], []), key=lambda kv: -kv[1])
        lines += ["## %d. %s" % (k, x["title"]), "",
                  "- Outlet: %s (%s)" % (x["outlet"], x["type"]),
                  "- Link: %s" % x["url"],
                  "- Topics: %s" % ", ".join("%s %.0f%%" % (t, 100 * v) for t, v in tl),
                  "- L/E/P: %s / %s / %s" % (s.get("logos"), s.get("ethos"), s.get("pathos")),
                  "- R %s  S %s  D %s  I %s" % (f(x["r"], 5), f(x["s"]), f(x["d"], 2), f(x["i"], 7)),
                  "- Justification: %s" % s.get("justification"), "- BB verdict:", ""]
    (db.OUT / "handcheck_sample.md").write_text("\n".join(lines), encoding="utf-8")
    print("  wrote out/report.html (%d KB), docs/index.html, out/handcheck_sample.md (%d items)"
          % (len(page) // 1024, len(sample)))


if __name__ == "__main__":
    run()
