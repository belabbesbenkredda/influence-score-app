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
 --logos:#6BA6E8;--ethos:#4FC2A0;--pathos:#E8996A;--accent:#E4EAED;--focus:#6BA6E8;
 --chip:#20262A;--chip-ink:#A9B3B8;--warnbg:#2A2317;--warn:#D7AC55;}}
:root[data-theme="dark"]{
 --ground:#0E1113;--surface:#161A1D;--sunken:#1C2124;--ink:#EAEEF0;--ink-2:#C3CBD0;--muted:#8B959B;
 --rule:#252B2F;--rule-2:#333A3F;--bar:#E4EAED;--bar-track:#262C31;
 --logos:#6BA6E8;--ethos:#4FC2A0;--pathos:#E8996A;--accent:#E4EAED;--focus:#6BA6E8;
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
.lep{display:flex;height:5px;border-radius:3px;overflow:hidden;background:var(--bar-track)}
.lep i{display:block;height:100%}
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
 var q=document.getElementById('q'),ty=document.getElementById('ty'),tp=document.getElementById('tp'),sh=document.getElementById('shown');
 function f(){var n=(q.value||'').toLowerCase(),a=ty.value,b=tp.value,k=0;
  [].forEach.call(t.tBodies[0].rows,function(r){
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
    with db.db() as con:
        items = db.rows(con, """
            SELECT s.*, i.title, i.url, i.published_at, i.word_count, i.fetch_method, i.content_basis,
                   o.name AS outlet, o.type, o.language, o.content_access
            FROM item_scores s JOIN items i USING(item_id) JOIN outlets o USING(outlet_id)
            WHERE s.country=? ORDER BY (s.i IS NULL), s.i DESC""", (db.COUNTRY,))
        sc = {r["item_id"]: r for r in db.rows(con, "SELECT * FROM scores2 WHERE prompt_version='score_v2'")}
        for r in db.rows(con, "SELECT * FROM scores"):
            sc.setdefault(r["item_id"], dict(r))
        tops = {}
        for r in db.rows(con, "SELECT item_id, topic, share FROM item_topics WHERE prompt_version='score_v2'"):
            tops.setdefault(r["item_id"], []).append((r["topic"], r["share"]))
        outlets = db.rows(con, """SELECT os.*, o.name, o.type, o.language, o.content_access, r.reach_raw,
                                         r.reach_unit, r.flag AS reach_flag
                                  FROM outlet_scores os JOIN outlets o USING(outlet_id) LEFT JOIN reach r USING(outlet_id)
                                  WHERE os.country=? ORDER BY (os.i IS NULL), os.i DESC""", (db.COUNTRY,))
        mip = db.rows(con, "SELECT topic, mip_share FROM mip WHERE country=? ORDER BY mip_share DESC", (db.COUNTRY,))
        meta = {k: db.get_meta(con, k) for k in ("mip_survey_date", "signals_run")}
        spend = (con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores2").fetchone()[0]
                 + con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores").fetchone()[0])
        n_out = con.execute("SELECT COUNT(*) FROM outlets WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        n_reach = con.execute("SELECT COUNT(*) FROM reach WHERE country=? AND reach_raw IS NOT NULL", (db.COUNTRY,)).fetchone()[0]
        pub = con.execute("SELECT MIN(published_at),MAX(published_at) FROM items WHERE published_at IS NOT NULL").fetchone()

    labels = {}
    with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            labels[r["topic"]] = r["label"]

    ranked = [x for x in items if x["i"] is not None]
    lead = ranked[0] if ranked else None
    pv = sorted(pts(x["i"]) for x in ranked)
    median = pv[len(pv) // 2] if pv else None
    p25 = pv[len(pv) // 4] if pv else None
    p75 = pv[3 * len(pv) // 4] if pv else None
    maxpts = pts(lead["i"]) if lead else 1
    types = sorted({x["type"] for x in items if x["type"]})
    n_summary = sum(1 for x in items if x["content_basis"] == "summary_only")
    sig = meta.get("signals_run") or {}
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    days = ""
    if pub[0] and pub[1]:
        days = "%s – %s" % (pub[0][:10], pub[1][:10])

    mass = Counter()
    for lst in tops.values():
        for t, share in lst:
            mass[t] += share
    total_mass = sum(mass.values()) or 1

    def chips(x):
        out = ['<span class="chip">%s</span>' % esc(x["outlet"]),
               '<span class="chip mono">%s</span>' % esc(x["type"])]
        if x["language"] and x["language"] != "en":
            out.append('<span class="chip mono">%s</span>' % esc(x["language"].upper()))
        if x["content_basis"] == "summary_only":
            out.append('<span class="chip warn">summary only</span>')
        return "".join(out)

    # ---- leaderboard
    lb = []
    for x in ranked[:LEADERBOARD_N]:
        s = sc.get(x["item_id"], {})
        lep = [s.get("logos") or 0, s.get("ethos") or 0, s.get("pathos") or 0]
        tot = sum(lep) or 1
        p = pts(x["i"])
        lb.append(
            '<div class="lb"><div class="lbhead"><div class="rk">%02d</div>'
            '<div class="lbtitle"><div class="h"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            '<div class="lbmeta">%s</div></div><div class="pts">%.2f</div></div>'
            '<div class="track"><i style="width:%.1f%%"></i></div>'
            '<div class="comps">'
            '<div class="comp"><div class="lab">Reach</div><div class="compval">%s</div>'
            '<div class="track"><i style="width:%.1f%%"></i></div></div>'
            '<div class="comp"><div class="lab">Salience</div><div class="compval">%s</div>'
            '<div class="track"><i style="width:%.1f%%"></i></div></div>'
            '<div class="comp"><div class="lab">Discursiveness</div><div class="compval">%s</div>'
            '<div class="track"><i style="width:%.1f%%"></i></div></div>'
            '<div class="comp"><div class="lab">L &middot; E &middot; P</div>'
            '<div class="compval">%s &middot; %s &middot; %s</div>'
            '<div class="lep"><i class="l" style="width:%.1f%%"></i><i class="e" style="width:%.1f%%"></i>'
            '<i class="p" style="width:%.1f%%"></i></div></div>'
            '</div></div>'
            % (x["rank"], esc(x["url"]), esc((x["title"] or "(untitled)")[:130]), chips(x), p,
               100 * p / maxpts,
               f(x["r"], 5), 100 * min(1.0, (x["r"] or 0) / max(0.0001, max(y["r"] or 0 for y in ranked))),
               f(x["s"], 3), 100 * min(1.0, (x["s"] or 0) / 0.30),
               f(x["d"], 2), 100 * (x["d"] or 0),
               lep[0], lep[1], lep[2],
               100 * lep[0] / tot, 100 * lep[1] / tot, 100 * lep[2] / tot))

    # ---- full table
    trs = []
    for x in items:
        s = sc.get(x["item_id"], {})
        tl = sorted(tops.get(x["item_id"], []), key=lambda kv: -kv[1])
        tstr = ", ".join("%s %.0f%%" % (t, 100 * v) for t, v in tl[:3]) or (s.get("topic") or "")
        p = pts(x["i"])
        trs.append(
            '<tr data-s="%s" data-type="%s" data-topics="%s">'
            '<td class="n" data-v="%s">%s</td>'
            '<td><span class="headline">%s</span><div class="lbmeta">%s</div>'
            '<div class="lab" style="font-size:.66rem;color:var(--muted);margin-top:3px">%s</div></td>'
            '<td class="n" data-v="%s">%s</td><td class="n" data-v="%s">%s</td>'
            '<td class="n" data-v="%s">%s</td><td class="n" data-v="%s"><b>%s</b></td></tr>'
            % (esc(((x["outlet"] or "") + " " + (x["title"] or "")).lower()), esc(x["type"]),
               esc(" ".join(t for t, _ in tl)),
               x["rank"] or "", x["rank"] or "—",
               esc((x["title"] or "(untitled)")[:110]), chips(x), esc(tstr),
               x["r"] if x["r"] is not None else "", f(x["r"], 5),
               x["s"] if x["s"] is not None else "", f(x["s"], 3),
               x["d"] if x["d"] is not None else "", f(x["d"], 2),
               p if p is not None else "", ("%.2f" % p) if p is not None else "—"))

    trows = []
    for m in mip:
        cov = mass[m["topic"]] / total_mass
        top = max(max(x["mip_share"] for x in mip), max((mass[k] / total_mass for k in mass), default=0.01))
        trows.append('<div class="trow"><div class="tname">%s<span>%s</span></div>'
                     '<div class="tbar"><div class="track"><i style="width:%.1f%%"></i></div><b>%.0f%%</b></div>'
                     '<div class="tbar"><div class="track"><i class="cov" style="width:%.1f%%"></i></div><b>%.0f%%</b></div></div>'
                     % (esc(labels.get(m["topic"], m["topic"])), esc(m["topic"]),
                        100 * m["mip_share"] / top, 100 * m["mip_share"],
                        100 * cov / top, 100 * cov))

    orows = []
    for o in outlets[:60]:
        orows.append('<tr><td class="n">%s</td><td>%s<div class="lbmeta"><span class="chip mono">%s</span>%s</div></td>'
                     '<td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n"><b>%s</b></td>'
                     '<td class="n">%s</td></tr>'
                     % (o["rank"] or "—", esc(o["name"]), esc(o["type"]),
                        '<span class="chip warn">paywalled</span>' if o["content_access"] == "paywalled" else "",
                        f(o["r"], 5), f(o["s"], 3), f(o["d"], 2),
                        ("%.2f" % pts(o["i"])) if o["i"] is not None else "—", o["n_scored"]))

    arows = "".join('<div class="arow"><code>%s</code><b>%s</b><span>%s</span></div>'
                    % (esc(k), esc(v[0]), esc(v[1])) for k, v in audience.ASSUMPTIONS.items())

    sigline = ("No per-item signal provider is configured, so every item from an outlet currently carries that "
               "outlet's average reach — the ranking within an outlet is decided by salience and discursiveness "
               "alone. Setting <code>PSI_YOUTUBE_API_KEY</code> or an analytics endpoint turns this on."
               if not sig.get("providers") else
               "%d of %d items carry a measured per-item signal from %s." %
               (sig.get("measured", 0), sig.get("items", 0), ", ".join(sig.get("providers", []))))

    page = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSI Influence Engine v0.4 — United States</title>
<style>%s
%s</style></head><body>
<div class="topbar"><div class="wrap">
 <div class="brand">Public Sphere Index <span>/ Influence</span></div>
 <span class="chip">United States</span><span class="chip mono">I = R &times; S &times; D</span>
 <div class="spacer"></div><span class="chip mono">%s</span>
 <button class="ghost" id="theme" type="button">Theme</button>
</div></div>

<header><div class="wrap">
<h1>Influence rankings — United States</h1>
<p class="lede">The individual items shaping opinion formation, ranked by reach &times; salience &times; discursiveness.
Scores are PSI points: influence per thousand US adults, an absolute figure rather than a curve fitted to this week's leader.</p>
<div class="kpis">
 <div class="kpi lead"><div class="lab">Leading item</div><b>%s</b><div class="sub">%s</div></div>
 <div class="kpi"><div class="lab">Items ranked</div><b>%d</b><div class="sub">of %d sampled</div></div>
 <div class="kpi"><div class="lab">Outlets</div><b>%d</b><div class="sub">%d with sourced reach</div></div>
 <div class="kpi"><div class="lab">Median influence</div><b>%s</b><div class="sub">PSI points &middot; quartiles %s–%s</div></div>
 <div class="kpi"><div class="lab">Sample window</div><b>%s</b><div class="sub">%s</div></div>
</div></div></header>

<main class="wrap">
<div class="card"><h2>Index leaderboard</h2>
<p class="sub">Top %d items by influence, with the component scores behind each rank. Bars scale to the leader; the L &middot; E &middot; P strip shows the mix of argument, authority and emotion, not their level. The distribution is steeply skewed — the median item scores under a hundredth of the leader — because one broadcast segment reaches millions where one article reaches tens of thousands.</p>
<div class="body">%s</div></div>

<div class="card"><h2>Every item</h2>
<p class="sub">All %d sampled items. Click a column to sort.</p>
<div class="controls">
 <span class="lab">Search</span><input id="q" type="search" placeholder="outlet or headline">
 <span class="lab">Type</span><select id="ty"><option value="">all</option>%s</select>
 <span class="lab">Topic</span><select id="tp"><option value="">all</option>%s</select>
 <span class="lab"><b id="shown">0</b> shown</span></div>
<div class="scroll"><table id="items"><thead><tr>
<th class="n">#</th><th>Item</th><th class="n">R</th><th class="n">S</th><th class="n">D</th><th class="n">Points</th>
</tr></thead><tbody>%s</tbody></table></div></div>

<div class="card"><h2>Topic salience against coverage</h2>
<p class="sub">Left: the share of Americans naming each topic as the most important problem (Gallup, %s). Right: the share of the corpus devoted to it, counted proportionally — an item about a budget fight counts partly to government and partly to the economy.</p>
<div class="body">%s</div></div>

<div class="card"><h2>Outlets, as a rollup</h2>
<p class="sub">The influence of one representative item, not a period total — sampling is capped per outlet, so a total would rank outlets by how many of their items we could fetch. An outlet dominating the item list above is a finding, not a fault.</p>
<div class="scroll"><table><thead><tr><th class="n">#</th><th>Outlet</th><th class="n">R</th><th class="n">S</th>
<th class="n">D</th><th class="n">Points</th><th class="n">n</th></tr></thead><tbody>%s</tbody></table></div></div>

<div class="card"><h2>What is assumed inside R</h2>
<p class="sub">Each medium reports a different currency — viewers, visits, listeners, subscribers. Converting them into one quantity, people reaching a single item, needs the constants below. None is measured; each is a stated assumption, collected in <code>psi/audience.py</code> so it can be replaced one at a time.</p>
<div class="note">%s</div>
<div class="body">%s
<div class="arow" style="border-top:1px solid var(--rule)"><code>US_ADULTS</code><b>%s</b><span>%s</span></div>
</div></div>
</main>

<footer><div class="wrap"><h2>Method</h2><ol>
<li><b>R</b> — the outlet's sourced third-party audience figure, converted to people reaching one item, divided by US adults. Absolute: no normalisation against a category leader, no platform weights.</li>
<li><b>S</b> — Gallup's Most Important Problem (%s), applied proportionally across every topic an item addresses.</li>
<li><b>D</b> — Logos, Ethos and Pathos, each 0–10, rubric <span class="num">score_v2</span>. Ethos is the speaker's standing with their own audience, never their fairness: the instrument is descriptive and must register a demagogue and a statesman alike.</li>
<li><b>Points</b> — I &times; 1,000, the expected influence per thousand American adults.</li>
<li>%d outlets, %d with a sourced audience figure, each carrying a source URL, a verbatim quote and a date.</li>
<li>%d items published %s. %d are headline-and-summary only, from outlets that block article fetching: their topics are meaningful, their discursiveness is not comparable with full text.</li>
<li>Known gaps: the corpus is concentrated in a few days rather than spread over a month, and skewed towards outlets permitting automated fetching. Untranscribed audio is still missing.</li>
<li>Nothing is estimated silently. Unsourced reach stays null, and every modelling constant is printed above. Scoring spend to date: $%.2f.</li>
</ol></div></footer>
<script>%s</script></body></html>""" % (
        font_css(), CSS, generated,
        ("%.2f" % pts(lead["i"])) if lead else "—",
        esc(("%s · %s" % (lead["outlet"], lead["title"]))[:80]) if lead else "no ranked items",
        len(ranked), len(items), n_out, n_reach,
        ("%.3f" % median) if median is not None else "—",
        ("%.3f" % p25) if p25 is not None else "—", ("%.2f" % p75) if p75 is not None else "—",
        "%d d" % 14, esc(days),
        LEADERBOARD_N, "".join(lb), len(items),
        "".join('<option value="%s">%s</option>' % (esc(t), esc(t)) for t in types),
        "".join('<option value="%s">%s</option>' % (esc(t), esc(labels.get(t, t))) for t in sorted(mass, key=lambda k: -mass[k])),
        "".join(trs), esc(meta.get("mip_survey_date")), "".join(trows), "".join(orows),
        sigline, arows, "%s" % f"{audience.US_ADULTS:,}", esc(audience.US_ADULTS_SOURCE),
        esc(meta.get("mip_survey_date")), n_out, n_reach, len(items), esc(days), n_summary, spend, JS)

    db.OUT.mkdir(parents=True, exist_ok=True)
    (db.OUT / "report.html").write_text(page, encoding="utf-8")
    (db.ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(db.OUT / "report.html", db.ROOT / "docs" / "index.html")

    rng = random.Random(HANDCHECK_SEED)
    sample = rng.sample(ranked, min(HANDCHECK_N, len(ranked)))
    lines = ["# Hand-check sample — %d ranked items" % len(sample), "",
             "Generated %s, seed %d. Rubric score_v2." % (generated, HANDCHECK_SEED), "",
             "Ethos is the speaker's standing with their own audience, not their fairness.", ""]
    for k, x in enumerate(sample, 1):
        s = sc.get(x["item_id"], {})
        tl = sorted(tops.get(x["item_id"], []), key=lambda kv: -kv[1])
        lines += ["## %d. %s" % (k, x["title"]), "",
                  "- Outlet: %s (%s%s)" % (x["outlet"], x["type"],
                                           ", summary only" if x["content_basis"] == "summary_only" else ""),
                  "- Link: %s" % x["url"],
                  "- Topics: %s" % ", ".join("%s %.0f%%" % (t, 100 * v) for t, v in tl),
                  "- L/E/P: %s / %s / %s" % (s.get("logos"), s.get("ethos"), s.get("pathos")),
                  "- R %s  S %s  D %s  points %.2f" % (f(x["r"], 5), f(x["s"], 3), f(x["d"], 2), pts(x["i"])),
                  "- Justification: %s" % s.get("justification"), "- BB verdict:", ""]
    (db.OUT / "handcheck_sample.md").write_text("\n".join(lines), encoding="utf-8")
    print("  wrote out/report.html (%d KB), docs/index.html, out/handcheck_sample.md" % (len(page) // 1024))


if __name__ == "__main__":
    run()
