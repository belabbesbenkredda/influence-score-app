"""Stage 7 — Report and hand-check.

Item-first: individual items are ranked, because the framework defines influence
as a property of content. Outlets follow as a rollup.

Influence is published as PSI points = I x 1000. Since R is already a share of
US adults, a point is the expected influence per thousand American adults — an
absolute quantity, so scores stay comparable between editions and between
countries instead of being rescaled to whoever leads this week.

Visual direction follows BB's reference: an index of record — light ground,
numbered leaderboard, a component breakdown under every rank, chips carrying
type, language and provenance. Typography is Instrument Sans for the interface,
Newsreader for headlines, JetBrains Mono for every number, all bundled so the
page works with no network.
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
POINT_SCALE = 1000          # I x 1000 = influence per thousand US adults
LEADERBOARD_N = 25

CSS = """
:root{
 --ground:#F4F6F7;--surface:#FFFFFF;--sunken:#EDF0F2;--ink:#0F1417;--ink-2:#3B464C;--muted:#6B767C;
 --rule:#E1E6E9;--rule-2:#CFD6DA;--bar:#1A2228;--bar-track:#E7EBEE;
 --logos:#2F6FB5;--ethos:#1F8A6D;--pathos:#C4622D;--accent:#1A2228;--focus:#2F6FB5;
 --chip:#F0F3F5;--chip-ink:#4A555B;--warnbg:#FBF3E6;--warn:#8A6512;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ground:#0E1113;--surface:#161A1D;--sunken:#1C2124;--ink:#EAEEF0;--ink-2:#C3CBD0;--muted:#8B959B;
 --rule:#252B2F;--rule-2:#333A3F;--bar:#E4EAED;--bar-track:#262C31;
 --logos:#5490D2;--ethos:#36A886;--pathos:#D07C50;--accent:#E4EAED;--focus:#6BA6E8;
 --chip:#20262A;--chip-ink:#A9B3B8;--warnbg:#2A2317;--warn:#D7AC55;}}
:root[data-theme="dark"]{
 --ground:#0E1113;--surface:#161A1D;--sunken:#1C2124;--ink:#EAEEF0;--ink-2:#C3CBD0;--muted:#8B959B;
 --rule:#252B2F;--rule-2:#333A3F;--bar:#E4EAED;--bar-track:#262C31;
 --logos:#5490D2;--ethos:#36A886;--pathos:#D07C50;--accent:#E4EAED;--focus:#6BA6E8;
 --chip:#20262A;--chip-ink:#A9B3B8;--warnbg:#2A2317;--warn:#D7AC55;}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);
 font-family:"Instrument Sans",-apple-system,"Segoe UI",sans-serif;font-size:15px;line-height:1.5}
h1,h2,h3{margin:0;letter-spacing:-.018em;text-wrap:balance}
.num,.pts,td.n,th.n,.chip.mono,.kpi b,.compval{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.headline{font-family:Newsreader,Georgia,serif}
a{color:inherit}
.wrap{max-width:1120px;margin:0 auto;padding:0 22px}
/* top bar */
.topbar{background:var(--surface);border-bottom:1px solid var(--rule);position:sticky;top:0;z-index:20}
.topbar .wrap{display:flex;align-items:center;gap:12px;height:56px;flex-wrap:nowrap;overflow:hidden}
.brand{font-weight:600;font-size:.95rem;white-space:nowrap}
.brand span{color:var(--muted);font-weight:400}
.chip{display:inline-flex;align-items:center;gap:.3rem;background:var(--chip);color:var(--chip-ink);
 border-radius:999px;padding:3px 10px;font-size:.72rem;white-space:nowrap;border:1px solid transparent}
.chip.mono{font-size:.7rem}
.chip.warn{background:var(--warnbg);color:var(--warn)}
.spacer{flex:1}
button.ghost{background:var(--surface);border:1px solid var(--rule-2);color:var(--ink-2);border-radius:999px;
 padding:4px 12px;font:inherit;font-size:.75rem;cursor:pointer}
button.ghost:hover{border-color:var(--ink-2)}
/* header */
header .wrap{padding:34px 22px 8px}
h1{font-size:2.15rem;font-weight:600}
.lede{color:var(--muted);max-width:62ch;margin:10px 0 0;font-size:.98rem}
.kpis{display:grid;grid-template-columns:1.5fr repeat(4,1fr);gap:0;margin:22px 0 0;
 background:var(--surface);border:1px solid var(--rule);border-radius:12px;overflow:hidden}
.kpi{padding:14px 16px;border-right:1px solid var(--rule);min-width:0}
.kpi:last-child{border-right:0}
.kpi .lab{font-size:.63rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:500}
.kpi b{display:block;font-size:1.9rem;font-weight:500;line-height:1.15;margin:.15rem 0 .1rem}
.kpi .sub{font-size:.76rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kpi.lead b{font-size:2.3rem}
/* cards */
.card{background:var(--surface);border:1px solid var(--rule);border-radius:12px;margin:22px 0;overflow:hidden}
.card>h2{font-size:1rem;font-weight:600;padding:16px 20px 0}
.card>.sub{color:var(--muted);font-size:.85rem;padding:4px 20px 0;margin:0;max-width:78ch}
.card>.body{padding:8px 20px 18px}
/* leaderboard */
.lb{border-top:1px solid var(--rule);padding:16px 0 14px}
.lb:first-child{border-top:0}
.lbhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.rk{font-size:.8rem;color:var(--muted);min-width:1.9rem;font-family:"JetBrains Mono",monospace}
.lbtitle{flex:1 1 320px;min-width:0}
.lbtitle .h{font-family:Newsreader,Georgia,serif;font-size:1.06rem;line-height:1.3;font-weight:500}
.lbtitle .h a{text-decoration:none}
.lbtitle .h a:hover{text-decoration:underline}
.lbmeta{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;align-items:center}
.pts{font-size:1.45rem;font-weight:500;text-align:right;margin-left:auto}
.track{height:7px;background:var(--bar-track);border-radius:4px;margin:9px 0 0;overflow:hidden}
.track i{display:block;height:100%;background:var(--bar);border-radius:4px}
.comps{display:grid;grid-template-columns:repeat(3,1fr) minmax(120px,.8fr);gap:16px;margin-top:12px}
.comp .lab{font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:500}
.compval{font-size:.85rem;margin:1px 0 4px}
.comp .track{height:5px;margin:0}
.lep{display:flex;height:5px;gap:2px}
.lep i{display:block;height:100%;border-radius:2px;min-width:2px}
.lep .l{background:var(--logos)}.lep .e{background:var(--ethos)}.lep .p{background:var(--pathos)}
/* tables */
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:500;
 cursor:pointer;white-space:nowrap;background:var(--surface);position:sticky;top:56px}
th.sorted{color:var(--ink)}
td.n,th.n{text-align:right}
tbody tr:hover td{background:var(--sunken)}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:12px 20px 4px}
.controls input,.controls select{font:inherit;font-size:.82rem;padding:6px 9px;border:1px solid var(--rule-2);
 border-radius:8px;background:var(--surface);color:var(--ink);max-width:100%;min-width:0}
.controls .lab{font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:500}
/* topics */
.trow{display:grid;grid-template-columns:minmax(150px,1fr) 1fr 1fr;gap:14px;align-items:center;
 padding:7px 0;border-bottom:1px solid var(--rule)}
.trow:last-child{border-bottom:0}
.tname{font-size:.88rem}
.tname span{display:block;font-size:.65rem;color:var(--muted);font-family:"JetBrains Mono",monospace}
.tbar{display:flex;align-items:center;gap:8px}
.tbar .track{flex:1;margin:0;height:6px}
.tbar .track i.cov{background:var(--muted)}
.tbar b{font-family:"JetBrains Mono",monospace;font-size:.75rem;font-weight:500;min-width:3.2ch;text-align:right}
/* assumptions */
.arow{display:grid;grid-template-columns:minmax(200px,auto) 4.5rem 1fr;gap:12px;padding:8px 0;
 border-bottom:1px solid var(--rule);font-size:.85rem;align-items:baseline}
.arow:last-child{border-bottom:0}
.arow code{font-family:"JetBrains Mono",monospace;font-size:.75rem;color:var(--pathos)}
.arow b{font-family:"JetBrains Mono",monospace;font-weight:500}
.arow span{color:var(--muted)}
.note{background:var(--warnbg);color:var(--warn);border-radius:10px;padding:11px 14px;font-size:.85rem;margin:0 20px 16px}
/* expandable rows */
.lb{cursor:pointer;position:relative;transition:background .12s}
.lb:hover{background:var(--sunken)}
.lb .caret{position:absolute;right:0;top:18px;color:var(--muted);font-size:.7rem;transition:transform .15s}
.lb[aria-expanded="true"] .caret{transform:rotate(90deg)}
.lb[aria-expanded="true"]{background:var(--sunken)}
.detail{display:none;padding:14px 0 4px;border-top:1px dashed var(--rule-2);margin-top:12px}
.lb[aria-expanded="true"] .detail,tr.open+tr.det .detail{display:block}
.det>td{background:var(--sunken)}
.dgrid{display:grid;grid-template-columns:1.4fr 1fr;gap:18px}
.dsec h4{font-size:.6rem;letter-spacing:.11em;text-transform:uppercase;color:var(--muted);margin:0 0 6px;font-weight:500}
.quote{font-family:Newsreader,Georgia,serif;font-size:.95rem;line-height:1.5;color:var(--ink-2);margin:0}
.tsplit{display:flex;flex-direction:column;gap:5px}
.tsplit div{display:grid;grid-template-columns:minmax(90px,auto) 1fr 2.6rem;gap:8px;align-items:center;font-size:.78rem}
.tsplit .track{height:5px;margin:0}
.tsplit b{font-family:"JetBrains Mono",monospace;font-weight:500;text-align:right;font-size:.72rem}
.calc{font-family:"JetBrains Mono",monospace;font-size:.72rem;color:var(--muted);line-height:1.7}
.calc b{color:var(--ink);font-weight:500}
.prov{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.prov a{font-size:.72rem}
/* hover explainers */
.hint{position:relative;border-bottom:1px dotted var(--rule-2);cursor:help}
.hint>.tip{position:absolute;left:0;bottom:calc(100% + 8px);width:250px;background:var(--ink);color:var(--ground);
 padding:9px 11px;border-radius:8px;font-family:"Instrument Sans",sans-serif;font-size:.74rem;line-height:1.45;
 opacity:0;visibility:hidden;transition:opacity .12s;z-index:30;pointer-events:none;box-shadow:0 6px 24px rgba(0,0,0,.18)}
.hint:hover>.tip,.hint:focus-visible>.tip{opacity:1;visibility:visible}
.hint>.tip em{font-style:normal;font-family:"JetBrains Mono",monospace;display:block;margin-top:5px;opacity:.75}
/* distribution strip */
.strip{width:100%;height:110px;display:block}
.strip circle{fill:var(--bar);fill-opacity:.32;transition:fill-opacity .1s}
.strip circle:hover{fill-opacity:1}
.strip circle.hi{fill:var(--pathos);fill-opacity:1}
.strip .ax{stroke:var(--rule-2);stroke-width:1}
.strip text{fill:var(--muted);font-family:"JetBrains Mono",monospace;font-size:9px}
footer{border-top:1px solid var(--rule);background:var(--surface);margin-top:30px}
footer .wrap{padding:22px 22px 40px;color:var(--muted);font-size:.86rem}
footer h2{font-size:.95rem;color:var(--ink);margin-bottom:8px}
footer ol{padding-left:1.1rem;margin:0}footer li{margin-bottom:6px}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
@media(max-width:860px){.kpis{grid-template-columns:1fr 1fr}.kpi{border-bottom:1px solid var(--rule)}
 .comps{grid-template-columns:1fr 1fr;gap:10px}}
@media(max-width:600px){
 body{font-size:14px}h1{font-size:1.5rem}.wrap{padding:0 14px}
 .topbar .wrap{gap:8px}.brand{font-size:.85rem}.topbar .chip{display:none}
 .kpi b{font-size:1.5rem}.kpi.lead b{font-size:1.7rem}
 .card>h2,.card>.sub,.controls{padding-left:14px;padding-right:14px}.card>.body{padding:8px 14px 14px}
 .pts{font-size:1.2rem}.lbtitle .h{font-size:1rem}
 .trow{grid-template-columns:1fr;gap:4px}
 .arow{grid-template-columns:1fr;gap:2px}
 th{top:52px}
 #items thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
 #items,#items tbody,#items tr,#items td{display:block;width:auto}
 #items tr{border:1px solid var(--rule);border-radius:10px;margin:0 0 8px;padding:9px 11px}
 #items td{border:0;padding:0}
 #items td:nth-child(1){display:inline-block;width:2.2rem;color:var(--muted)}
 #items td:nth-child(2){display:inline-block;width:calc(100% - 2.5rem);vertical-align:top}
 #items td:nth-child(n+3){display:inline-block;margin:.3rem .7rem 0 0;font-size:.76rem}
 #items td:nth-child(3){margin-left:2.2rem}
 #items td:nth-child(3)::before{content:"R "}#items td:nth-child(4)::before{content:"S "}
 #items td:nth-child(5)::before{content:"D "}#items td:nth-child(6)::before{content:"pts "}
 #items td:nth-child(n+3)::before{color:var(--muted);font-size:.64rem}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = """
(function(){
 var root=document.documentElement,btn=document.getElementById('theme');
 function cur(){return root.getAttribute('data-theme')||'system'}
 function label(){var c=cur();btn.textContent=c==='system'?'Theme':(c==='dark'?'Dark':'Light')}
 try{var saved=localStorage.getItem('psi-theme');if(saved&&saved!=='system')root.setAttribute('data-theme',saved)}catch(e){}
 label();
 btn.addEventListener('click',function(){
   var order=['system','light','dark'],next=order[(order.indexOf(cur())+1)%3];
   if(next==='system')root.removeAttribute('data-theme');else root.setAttribute('data-theme',next);
   try{localStorage.setItem('psi-theme',next)}catch(e){}
   label();});
 var t=document.getElementById('items');if(!t)return;
 var ths=t.querySelectorAll('th');
 ths.forEach(function(th,i){th.addEventListener('click',function(){
   var tb=t.tBodies[0],rows=[].slice.call(tb.rows),num=th.classList.contains('n'),asc=th.dataset.asc==='1';
   rows.sort(function(a,b){
     var x=a.cells[i].dataset.v!==undefined?a.cells[i].dataset.v:a.cells[i].textContent;
     var y=b.cells[i].dataset.v!==undefined?b.cells[i].dataset.v:b.cells[i].textContent;
     if(num){x=x===''?-Infinity:parseFloat(x);y=y===''?-Infinity:parseFloat(y);return asc?x-y:y-x}
     return asc?x.localeCompare(y):y.localeCompare(x)});
   rows.forEach(function(r){tb.appendChild(r)});
   ths.forEach(function(o){o.classList.remove('sorted')});th.classList.add('sorted');th.dataset.asc=asc?'0':'1';})});
 // expand a leaderboard entry
 document.querySelectorAll('.lb').forEach(function(el){
   function toggle(){var o=el.getAttribute('aria-expanded')==='true';el.setAttribute('aria-expanded',String(!o))}
   el.addEventListener('click',function(ev){if(!ev.target.closest('a'))toggle()});
   el.addEventListener('keydown',function(ev){
     if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle()}});
 });
 // expand a table row
 t.tBodies[0].addEventListener('click',function(ev){
   var tr=ev.target.closest('tr');if(!tr||tr.classList.contains('det')||ev.target.closest('a'))return;
   var det=tr.nextElementSibling;
   if(det&&det.classList.contains('det')){tr.classList.toggle('open');det.style.display=tr.classList.contains('open')?'':'none'}
 });
 // distribution strip: highlight the hovered mark's row
 var strip=document.getElementById('strip');
 if(strip){var lbl=document.getElementById('striplabel');
  strip.addEventListener('mouseover',function(ev){
    var c=ev.target.closest('circle');if(!c)return;
    lbl.textContent=c.dataset.t+' — '+c.dataset.p+' points';});
  strip.addEventListener('mouseleave',function(){lbl.textContent='Hover a mark to identify it.'});}
 var q=document.getElementById('q'),ty=document.getElementById('ty'),tp=document.getElementById('tp'),sh=document.getElementById('shown');
 function f(){var n=(q.value||'').toLowerCase(),a=ty.value,b=tp.value,k=0;
  [].forEach.call(t.tBodies[0].rows,function(r){
    if(r.classList.contains('det')){r.style.display=r.previousElementSibling.classList.contains('open')&&r.previousElementSibling.style.display!=='none'?'':'none';return}
    var ok=(!n||r.dataset.s.indexOf(n)>=0)&&(!a||r.dataset.type===a)&&(!b||r.dataset.topics.indexOf(b)>=0);
    r.style.display=ok?'':'none';if(ok)k++});
  sh.textContent=k}
 [q,ty,tp].forEach(function(e){e.addEventListener('input',f);e.addEventListener('change',f)});f();
})();
"""


def esc(v):
    return html.escape("" if v is None else str(v))


def font_css() -> str:
    faces = FONT_DIR / "faces.css"
    if not faces.exists():
        return "/* fonts not bundled; system stacks in use */"
    css = faces.read_text(encoding="utf-8")
    for path in FONT_DIR.glob("*.woff2"):
        css = css.replace("url(FONT:%s)" % path.name,
                          "url(data:font/woff2;base64,%s)" % base64.b64encode(path.read_bytes()).decode("ascii"))
    return css


def f(v, n=3):
    return "—" if v is None else ("%.*f" % (n, v))


def pts(i):
    return None if i is None else i * POINT_SCALE


def run() -> None:
    """Assemble the interactive report: shell + stylesheet + app, with the corpus inlined."""
    import json
    from psi.tools import payload as payload_mod

    data = payload_mod.build()
    assets = db.ROOT / "psi" / "assets"
    shell = (assets / "report_app.html").read_text(encoding="utf-8")
    css = (assets / "report_app.css").read_text(encoding="utf-8")
    app = (assets / "report_app.js").read_text(encoding="utf-8")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")

    page = ("""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSI Influence Engine v0.5 — United States</title>
<style>%s
%s</style></head><body>
%s
<script>window.__PSI__=%s;</script>
<script>%s</script>
</body></html>""" % (font_css(), css, shell, blob, app))

    db.OUT.mkdir(parents=True, exist_ok=True)
    (db.OUT / "report.html").write_text(page, encoding="utf-8")
    (db.ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(db.OUT / "report.html", db.ROOT / "docs" / "index.html")

    # hand-check sample, computed at the default assumptions
    import csv as _csv
    labels = {}
    with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            labels[r["topic"]] = r["label"]
    with db.db() as con:
        rows = db.rows(con, """SELECT s.*, i.title, i.url, i.content_basis, o.name AS outlet, o.type
                               FROM item_scores s JOIN items i USING(item_id) JOIN outlets o USING(outlet_id)
                               WHERE s.country=? AND s.i IS NOT NULL ORDER BY s.i DESC""", (db.COUNTRY,))
        just = {r["item_id"]: r["justification"] for r in
                db.rows(con, "SELECT item_id, justification FROM scores2 WHERE prompt_version='score_v2'")}
        tp = {}
        for r in db.rows(con, "SELECT item_id, topic, share FROM item_topics WHERE prompt_version='score_v2'"):
            tp.setdefault(r["item_id"], []).append((r["topic"], r["share"]))
    rng = random.Random(HANDCHECK_SEED)
    sample = rng.sample(rows, min(HANDCHECK_N, len(rows)))
    lines = ["# Hand-check sample — %d ranked items" % len(sample), "",
             "Generated %s, seed %d. Rubric score_v2, default assumptions." % (data["generated"], HANDCHECK_SEED), "",
             "Ethos is the speaker's standing with their own audience, not their fairness.", ""]
    for k, x in enumerate(sample, 1):
        tl = sorted(tp.get(x["item_id"], []), key=lambda kv: -kv[1])
        lines += ["## %d. %s" % (k, x["title"]), "",
                  "- Outlet: %s (%s%s)" % (x["outlet"], x["type"],
                                           ", summary only" if x["content_basis"] == "summary_only" else ""),
                  "- Link: %s" % x["url"],
                  "- Topics: %s" % ", ".join("%s %.0f%%" % (labels.get(t, t), 100 * v) for t, v in tl),
                  "- R %s  S %s  D %s  points %.3f" % (f(x["r"], 5), f(x["s"], 3), f(x["d"], 2), x["i"] * 1000),
                  "- Justification: %s" % just.get(x["item_id"], ""), "- BB verdict:", ""]
    (db.OUT / "handcheck_sample.md").write_text("\n".join(lines), encoding="utf-8")
    print("  wrote out/report.html (%d KB, %d items inlined), docs/index.html, out/handcheck_sample.md"
          % (len(page) // 1024, len(data["items"])))


if __name__ == "__main__":
    run()
