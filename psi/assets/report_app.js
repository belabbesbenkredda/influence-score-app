(function(){
"use strict";
var D = window.__PSI__;
var A = Object.assign({}, D.defaults);           // live assumptions
var state = {q:"", type:"", topic:"", limit:25, open:null, baseRank:null};
var $ = function(id){return document.getElementById(id)};
var esc = function(s){var d=document.createElement("div");d.textContent=s==null?"":s;return d.innerHTML};
var fmt = function(v,n){return v==null?"—":v.toFixed(n)};
var num = function(v){return v==null?"—":Math.round(v).toLocaleString("en-US")};

// ---- the audience model, mirroring psi/audience.py ------------------------------------
var TV = {avg_total_day_viewers:1, avg_total_viewers_flagship_newscast:1};
function peoplePerItem(o){
  var unit=o[5], raw=o[4];
  if(raw==null||!unit) return null;
  if(TV[unit]) return raw*A.TV_SEGMENT_SHARE;
  if(unit==="weekly_listeners") return raw/A.RADIO_EPISODES_PER_WEEK;
  if(unit==="youtube_subscribers") return raw*A.PODCAST_EPISODE_VIEW_RATE*(1+A.PODCAST_AUDIO_MULTIPLE);
  if(unit==="subscribers") return raw*A.NEWSLETTER_OPEN_RATE;
  if(unit==="monthly_visits_semrush") return raw/A.DIGITAL_ITEMS_PER_MONTH;
  if(unit.indexOf("monthly_downloads")===0) return raw;
  return null;
}
function basis(o){
  var unit=o[5];
  if(TV[unit]) return "programme average viewers × TV_SEGMENT_SHARE";
  if(unit==="weekly_listeners") return "weekly cume ÷ RADIO_EPISODES_PER_WEEK (cume overlap not modelled)";
  if(unit==="youtube_subscribers") return "subscribers × episode view rate × (1 + audio multiple)";
  if(unit==="subscribers") return "subscribers × NEWSLETTER_OPEN_RATE";
  if(unit==="monthly_visits_semrush") return "monthly visits ÷ DIGITAL_ITEMS_PER_MONTH — a visit is not a read";
  return "no conversion rule for this unit";
}

// ---- recompute ------------------------------------------------------------------------
var rows=[], ranked=[], pcts={};
function recompute(){
  CORPUS=null;
  var people={}, r={};
  D.outlets.forEach(function(o,k){ var p=peoplePerItem(o); people[k]=p; r[k]= p==null?null:p/D.usAdults; });
  rows = D.items.map(function(it,idx){
    var s=0, tk=Object.keys(it[7]);
    tk.forEach(function(t){ s += it[7][t]*(D.mip[t]||0) });
    var lep=(it[4]||0)+(it[5]||0)+(it[6]||0);
    var d=lep/30, R=r[it[0]];
    return {idx:idx, o:it[0], title:it[1], url:it[2], date:it[3],
            l:it[4], e:it[5], p:it[6], topics:it[7], summary:it[8], words:it[9],
            method:it[10], just:it[11],
            R:R, S:s, D:d, I:(R==null?null:R*s*d), people:people[it[0]]};
  });
  ranked = rows.filter(function(x){return x.I!=null}).sort(function(a,b){return b.I-a.I});
  ranked.forEach(function(x,i){x.rank=i+1});
  // percentiles for placement
  ["R","S","D","I"].forEach(function(k){
    var v=ranked.map(function(x){return x[k]}).sort(function(a,b){return a-b});
    pcts[k]=v;
  });
}
function pct(k,v){
  var arr=pcts[k]; if(!arr||!arr.length||v==null) return 0;
  var lo=0,hi=arr.length;
  while(lo<hi){var m=(lo+hi)>>1; if(arr[m]<v)lo=m+1; else hi=m}
  return lo/arr.length;
}
var pts=function(i){return i==null?null:i*1000};

// ---- rendering ------------------------------------------------------------------------
function mk(frac,cls){
  frac=Math.max(0,Math.min(1,frac||0));
  return '<div class="mk'+(cls?" "+cls:"")+'"><i style="width:'+(frac*100).toFixed(1)+'%"></i></div>';
}
function chips(x){
  var o=D.outlets[x.o];
  var h='<span class="chip">'+esc(o[0])+'</span><span class="chip mono">'+esc(o[1])+'</span>';
  if(o[2]&&o[2]!=="en") h+='<span class="chip mono">'+esc(o[2].toUpperCase())+'</span>';
  if(x.summary) h+='<span class="chip warn">summary only</span>';
  return h;
}
function renderKPIs(){
  var lead=ranked[0], med=ranked.length?pts(pcts.I[Math.floor(pcts.I.length/2)]):null;

  $("kpis").innerHTML=
   '<div class="kpi lead"><div class="lab">Leading item</div><b>'+
     (lead?pts(lead.I).toFixed(2):"—")+'</b><div class="sub">'+(lead?esc(D.outlets[lead.o][0]+" · "+lead.title):"")+'</div></div>'+
   '<div class="kpi"><div class="lab">Items ranked</div><b>'+ranked.length+'</b><div class="sub">of '+rows.length+' scored</div></div>'+
   '<div class="kpi"><div class="lab">Outlets</div><b>'+D.outlets.length+'</b><div class="sub">'+
     D.outlets.filter(function(o){return o[4]!=null}).length+' with sourced reach</div></div>'+
   '<div class="kpi"><div class="lab">Median influence</div><b>'+(med==null?"—":med.toFixed(3))+
     '</b><div class="sub">PSI points</div></div>'+
   '<div class="kpi"><div class="lab">Sample window</div><b>14 d</b><div class="sub">'+esc(D.window[0]+" – "+D.window[1])+'</div></div>';
}
var pts=function(i){return i==null?null:i*1000};

// ---- rendering ------------------------------------------------------------------------
function mk(frac,cls){
  frac=Math.max(0,Math.min(1,frac||0));
  return '<div class="mk'+(cls?" "+cls:"")+'"><i style="width:'+(frac*100).toFixed(1)+'%"></i></div>';
}
function chips(x){
  var o=D.outlets[x.o];
  var h='<span class="chip">'+esc(o[0])+'</span><span class="chip mono">'+esc(o[1])+'</span>';
  if(o[2]&&o[2]!=="en") h+='<span class="chip mono">'+esc(o[2].toUpperCase())+'</span>';
  if(x.summary) h+='<span class="chip warn">summary only</span>';
  return h;
}
function renderKPIs(){
  var lead=ranked[0], med=ranked.length?pts(pcts.I[Math.floor(pcts.I.length/2)]):null;

  $("kpis").innerHTML=
   '<div class="kpi lead"><div class="lab">Leading item</div><b>'+
     (lead?pts(lead.I).toFixed(2):"—")+'</b><div class="sub">'+(lead?esc(D.outlets[lead.o][0]+" · "+lead.title):"")+'</div></div>'+
   '<div class="kpi"><div class="lab">Items ranked</div><b>'+ranked.length+'</b><div class="sub">of '+rows.length+' scored</div></div>'+
   '<div class="kpi"><div class="lab">Outlets</div><b>'+D.outlets.length+'</b><div class="sub">'+
     D.outlets.filter(function(o){return o[4]!=null}).length+' with sourced reach</div></div>'+
   '<div class="kpi"><div class="lab">Median influence</div><b>'+(med==null?"—":med.toFixed(3))+
     '</b><div class="sub">PSI points</div></div>'+
   '<div class="kpi"><div class="lab">Sample window</div><b>14 d</b><div class="sub">'+esc(D.window[0]+" – "+D.window[1])+'</div></div>';
}
function movement(){
  if(!state.baseRank) return null;
  var changed=0, sum=0, best=null, worst=null, top=0;
  ranked.forEach(function(x){
    var b=state.baseRank[x.idx]; if(b==null) return;
    var d=b-x.rank;                       // positive = climbed
    if(d!==0){ changed++; sum+=Math.abs(d) }
    if(x.rank<=25 && d!==0) top++;
    if(!best||d>best.d) best={x:x,d:d};
    if(!worst||d<worst.d) worst={x:x,d:d};
  });
  return {changed:changed, mean:changed?sum/changed:0, best:best, worst:worst, top:top, n:ranked.length};
}
function renderStrip(){
  var el=$("strip"); if(!ranked.length){el.innerHTML="";return}
  var W=1000,H=108,PL=8,PR=8,PB=22, vals=ranked.map(function(x){return pts(x.I)});
  var lo=Math.max(Math.min.apply(null,vals),1e-5), hi=Math.max.apply(null,vals);
  var lgl=Math.log10(lo), lgh=Math.log10(hi), span=(lgh-lgl)||1, pw=W-PL-PR, out=[];
  out.push('<line class="ax" x1="'+PL+'" y1="'+(H-PB)+'" x2="'+(W-PR)+'" y2="'+(H-PB)+'"/>');
  for(var e=Math.floor(lgl); e<=Math.ceil(lgh); e++){
    var tv=Math.pow(10,e); if(tv<lo||tv>hi*1.01) continue;
    var tx=PL+pw*(e-lgl)/span;
    out.push('<line class="ax" x1="'+tx.toFixed(1)+'" y1="'+(H-PB)+'" x2="'+tx.toFixed(1)+'" y2="'+(H-PB+4)+'"/>'+
             '<text x="'+tx.toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle">'+(tv>=0.01?tv:tv.toFixed(3))+'</text>');
  }
  ranked.forEach(function(x,k){
    var cx=PL+pw*(Math.log10(Math.max(pts(x.I),lo))-lgl)/span, cy=10+((k*37)%47)*(H-PB-20)/47;
    out.push('<circle cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="3" data-i="'+x.idx+'"><title>'+
      esc(D.outlets[x.o][0]+" · "+x.title)+' — '+pts(x.I).toFixed(3)+' points</title></circle>');
  });
  el.innerHTML=out.join("");
  $("stripsub").textContent="All "+ranked.length+" ranked items on a logarithmic influence scale, "+
    lo.toFixed(3)+" to "+hi.toFixed(2)+" points. The long left tail is print and digital: one article reaches tens of "+
    "thousands where one broadcast segment reaches millions. Hover a mark to identify it.";
}
function filtered(){
  var q=state.q.toLowerCase();
  return ranked.filter(function(x){
    if(state.type && D.outlets[x.o][1]!==state.type) return false;
    if(state.topic && !(state.topic in x.topics)) return false;
    if(q && (D.outlets[x.o][0]+" "+x.title).toLowerCase().indexOf(q)<0) return false;
    return true;
  });
}
var CORPUS=null;
function corpusNorm(){
  if(CORPUS) return CORPUS;
  var n=ranked.length||1, l=0,e=0,p=0;
  ranked.forEach(function(x){l+=x.l||0;e+=x.e||0;p+=x.p||0});
  CORPUS={l:l/n,e:e/n,p:p/n};
  return CORPUS;
}
function triangle(x){
  // Aristotle's triad as a shape: each axis runs from the centre to a vertex, scaled 0-10.
  // The item is filled; the corpus average is the dashed outline behind it, so the point of the
  // picture is the difference in shape, not the size.
  var W=210,H=180,cx=W/2,cy=H/2+6,R=64;
  var ang=[-Math.PI/2, Math.PI/6, 5*Math.PI/6];       // L top, E lower-right, P lower-left
  function pt(i,v){ return [cx+Math.cos(ang[i])*R*(v/10), cy+Math.sin(ang[i])*R*(v/10)] }
  function poly(vals){ return vals.map(function(v,i){var q=pt(i,v);return q[0].toFixed(1)+","+q[1].toFixed(1)}).join(" ") }
  var norm=corpusNorm();
  var g=[];
  // axes and rings
  [0.5,1].forEach(function(f){
    g.push('<polygon points="'+poly([10*f,10*f,10*f])+'" fill="none" stroke="var(--rule-2)" stroke-width="1" opacity="'+(f===1?0.9:0.5)+'"/>');
  });
  ang.forEach(function(a,i){
    var q=pt(i,10);
    g.push('<line x1="'+cx+'" y1="'+cy+'" x2="'+q[0].toFixed(1)+'" y2="'+q[1].toFixed(1)+
           '" stroke="var(--rule-2)" stroke-width="1" opacity="0.5"/>');
  });
  g.push('<polygon points="'+poly([norm.l,norm.e,norm.p])+'" fill="none" stroke="var(--mark)" stroke-width="1.5" stroke-dasharray="3 3"/>');
  g.push('<polygon points="'+poly([x.l,x.e,x.p])+'" fill="var(--mark)" fill-opacity="0.16" stroke="var(--ink)" stroke-width="2" stroke-linejoin="round"/>');
  var names=[["Logos","logos",x.l],["Ethos","ethos",x.e],["Pathos","pathos",x.p]];
  names.forEach(function(nm,i){
    var q=pt(i,10), lx=cx+(q[0]-cx)*1.30, ly=cy+(q[1]-cy)*1.30;
    g.push('<circle cx="'+q[0].toFixed(1)+'" cy="'+q[1].toFixed(1)+'" r="3.5" fill="var(--'+nm[1]+')"/>');
    g.push('<text x="'+lx.toFixed(1)+'" y="'+(ly+ (i===0?-4:11)).toFixed(1)+'" text-anchor="middle" class="tl">'+nm[0]+'</text>');
    g.push('<text x="'+lx.toFixed(1)+'" y="'+(ly+ (i===0?-16:23)).toFixed(1)+'" text-anchor="middle" class="tv">'+nm[2]+'</text>');
  });
  return '<svg class="tri" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Logos '+x.l+', Ethos '+x.e+
         ', Pathos '+x.p+' against the corpus average">'+g.join("")+'</svg>';
}
function histogram(x){
  // where this item falls in the real shape of the distribution, not just its percentile
  var vals=pcts.I, W=260,H=54,B=26;
  if(!vals.length) return "";
  var lo=Math.log10(Math.max(vals[0],1e-6)), hi=Math.log10(vals[vals.length-1]);
  var span=(hi-lo)||1, bins=new Array(B).fill(0);
  vals.forEach(function(v){ var b=Math.min(B-1,Math.floor((Math.log10(Math.max(v,1e-6))-lo)/span*B)); bins[b]++ });
  var mx=Math.max.apply(null,bins)||1, bw=W/B, g=[];
  var mine=Math.min(B-1,Math.floor((Math.log10(Math.max(x.I,1e-6))-lo)/span*B));
  bins.forEach(function(c,i){
    var h=(c/mx)*(H-14);
    g.push('<rect x="'+(i*bw+0.6).toFixed(1)+'" y="'+(H-12-h).toFixed(1)+'" width="'+(bw-1.2).toFixed(1)+
           '" height="'+h.toFixed(1)+'" rx="1.5" fill="'+(i===mine?"var(--ink)":"var(--track)")+'"/>');
  });
  g.push('<line x1="0" y1="'+(H-11)+'" x2="'+W+'" y2="'+(H-11)+'" stroke="var(--rule-2)" stroke-width="1"/>');
  g.push('<text x="0" y="'+H+'" class="tl">least</text><text x="'+W+'" y="'+H+'" text-anchor="end" class="tl">most influential</text>');
  return '<svg class="hist" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Distribution of influence with this item marked">'+g.join("")+'</svg>';
}
function detail(x){
  var o=D.outlets[x.o];
  var tk=Object.keys(x.topics).sort(function(a,b){return x.topics[b]-x.topics[a]});
  var top=x.topics[tk[0]]||1;
  var split=tk.map(function(t){
    return '<div><span>'+esc(D.labels[t]||t)+'</span>'+mk(x.topics[t]/top)+'<b>'+Math.round(x.topics[t]*100)+'%</b></div>';
  }).join("");
  function prow(label,key,val,fmtd){
    var p=pct(key,val);
    return '<div class="row"><span>'+label+'</span><div class="spine"><u style="left:'+(p*100).toFixed(1)+'%"></u>'+
      '</div><span>'+fmtd+' · '+(p*100).toFixed(0)+'th</span></div>';
  }
  var norm=corpusNorm();
  var lead=[["logos",x.l-norm.l,"argument"],["ethos",x.e-norm.e,"authority"],["pathos",x.p-norm.p,"emotion"]]
    .sort(function(a,b){return b[1]-a[1]})[0];
  var shape = lead[1]>0.4
    ? "Leans on <b>"+lead[2]+"</b>, "+lead[1].toFixed(1)+" points above the corpus average."
    : "No axis stands out — a flat rhetorical profile close to the corpus average.";
  var calc = (x.people!=null? '<b>'+num(x.people)+'</b> people reach one item<br>÷ '+num(D.usAdults)+
      ' US adults = R <b>'+fmt(x.R,5)+'</b><br>':'')+
    'R '+fmt(x.R,5)+' × S '+fmt(x.S,3)+' × D '+fmt(x.D,2)+'<br>= <b>'+pts(x.I).toFixed(3)+' points</b>';
  var src = o[8] ? '<a href="'+esc(o[8])+'" target="_blank" rel="noopener">'+esc(o[7])+'</a>' : esc(o[7]||"unsourced");
  return '<div class="detail"><div class="dgrid3">'+
    '<div class="dsec fig"><h4>Rhetorical fingerprint</h4>'+triangle(x)+
      '<p class="figcap">'+shape+' Dashed outline is the average of all '+ranked.length+' ranked items.</p>'+
      '<h4>Influence, against the field</h4>'+histogram(x)+'</div>'+
    '<div class="dsec"><h4>Why it scored this way</h4><p class="quote">'+esc(x.just||"not scored")+'</p>'+
    '<h4>Where it sits</h4><div class="pct">'+
      prow("Reach","R",x.R,fmt(x.R,5))+prow("Salience","S",x.S,fmt(x.S,3))+
      prow("Discursive","D",x.D,fmt(x.D,2))+'</div>'+
    '<h4>Topic split</h4><div class="tsplit">'+split+'</div></div>'+
    '<div class="dsec"><h4>How reach was built</h4><div class="calc">'+calc+'</div>'+
    '<h4>Assumption in play</h4><div class="calc">'+esc(basis(o))+'</div>'+
    '<h4>Provenance</h4><div class="calc">'+src+' · '+esc(o[5]||"")+(o[9]?" · "+esc(o[9]):"")+'</div>'+
    '<div class="prov"><span class="chip mono">'+esc(x.method)+'</span><span class="chip mono">'+x.words+
    ' words</span><span class="chip mono">'+esc(o[10])+'</span>'+
    '<a class="chip" href="'+esc(x.url)+'" target="_blank" rel="noopener">open item →</a></div></div></div></div>';
}
function renderBoard(){
  var list=filtered(), lim=state.limit||list.length, show=list.slice(0,lim);
  var maxp=ranked.length?pts(ranked[0].I):1;
  $("shown").textContent=show.length; $("total").textContent=list.length;
  $("board").innerHTML = show.map(function(x){
    var lep=(x.l||0)+(x.e||0)+(x.p||0)||1;
    return '<div class="lb'+(state.open===x.idx?" open":"")+'" data-i="'+x.idx+'" tabindex="0" role="button" aria-expanded="'+
      (state.open===x.idx)+'">'+
      '<div class="lbhead"><div class="rk">'+String(x.rank).padStart(2,"0")+'</div>'+
      '<div class="lbtitle"><div class="h"><a href="'+esc(x.url)+'" target="_blank" rel="noopener">'+esc(x.title)+'</a></div>'+
      '<div class="lbmeta">'+chips(x)+'</div></div>'+
      '<div class="pts">'+pts(x.I).toFixed(2)+'</div></div>'+
      mk(pts(x.I)/maxp,"lead")+
      '<div class="comps">'+
      '<div class="comp"><div class="lab">Reach</div><div class="compval">'+fmt(x.R,5)+'</div>'+mk(pct("R",x.R))+'</div>'+
      '<div class="comp"><div class="lab">Salience</div><div class="compval">'+fmt(x.S,3)+'</div>'+mk(pct("S",x.S))+'</div>'+
      '<div class="comp"><div class="lab">Discursiveness</div><div class="compval">'+fmt(x.D,2)+'</div>'+mk(pct("D",x.D))+'</div>'+
      '<div class="comp"><div class="lab">L · E · P</div><div class="compval">'+x.l+' · '+x.e+' · '+x.p+'</div>'+
      '<div class="lep"><i class="l" style="width:'+(100*x.l/lep).toFixed(1)+'%"></i>'+
      '<i class="e" style="width:'+(100*x.e/lep).toFixed(1)+'%"></i>'+
      '<i class="p" style="width:'+(100*x.p/lep).toFixed(1)+'%"></i></div></div></div>'+
      (state.open===x.idx?detail(x):"")+'</div>';
  }).join("") || '<p class="sub">Nothing matches those filters.</p>';
}
function renderGaps(){
  var mass={}, tot=0;
  var pool = (state.type||state.topic||state.q)?filtered():ranked;
  pool.forEach(function(x){ Object.keys(x.topics).forEach(function(t){ mass[t]=(mass[t]||0)+x.topics[t]; tot+=x.topics[t] }) });
  var topics=Object.keys(D.mip);
  var max=0;
  topics.forEach(function(t){ max=Math.max(max, D.mip[t], (mass[t]||0)/(tot||1)) });
  var rowsx=topics.map(function(t){
    return {t:t, care:D.mip[t], cov:(mass[t]||0)/(tot||1)};
  }).sort(function(a,b){return (b.care-b.cov)-(a.care-a.cov)});
  $("gaps").innerHTML=rowsx.map(function(r){
    var a=r.care/max, b=r.cov/max, lo=Math.min(a,b), hi=Math.max(a,b);
    var g=r.care-r.cov;
    return '<div class="gap"><div class="gname">'+esc(D.labels[r.t]||r.t)+'<span>'+esc(r.t)+'</span></div>'+
      '<div class="dumb"><div class="link" style="left:'+(lo*100).toFixed(1)+'%;width:'+((hi-lo)*100).toFixed(1)+'%"></div>'+
      '<u class="hollow" style="left:'+(b*100).toFixed(1)+'%"></u><u class="solid" style="left:'+(a*100).toFixed(1)+'%"></u></div>'+
      '<div class="gval"><b>'+(g>0?"+":"")+(g*100).toFixed(0)+'</b> pts '+(g>0?"under":"over")+'covered</div></div>';
  }).join("");
  var worst=rowsx[0], best=rowsx[rowsx.length-1];
  $("foot-gaps").innerHTML="Largest deficit this window: <b>"+esc(D.labels[worst.t]||worst.t)+"</b> ("+
    (worst.care*100).toFixed(0)+"% of public concern, "+(worst.cov*100).toFixed(0)+"% of coverage). Largest surplus: <b>"+
    esc(D.labels[best.t]||best.t)+"</b> ("+(best.care*100).toFixed(0)+"% concern, "+(best.cov*100).toFixed(0)+"% coverage).";
}
function renderOutlets(){
  var by={};
  ranked.forEach(function(x){ (by[x.o]=by[x.o]||[]).push(x) });
  var list=Object.keys(by).map(function(k){
    var arr=by[k], m=function(f){return arr.reduce(function(a,x){return a+x[f]},0)/arr.length};
    return {o:+k, R:arr[0].R, S:m("S"), D:m("D"), I:m("I"), n:arr.length};
  }).sort(function(a,b){return b.I-a.I});
  $("outlets").tBodies[0].innerHTML=list.map(function(r,i){
    var o=D.outlets[r.o];
    return '<tr><td class="n">'+(i+1)+'</td><td>'+esc(o[0])+' <span class="chip mono">'+esc(o[1])+'</span>'+
      (o[3]==="paywalled"?' <span class="chip warn">paywalled</span>':'')+'</td>'+
      '<td class="n">'+fmt(r.R,5)+'</td><td class="n">'+fmt(r.S,3)+'</td><td class="n">'+fmt(r.D,2)+'</td>'+
      '<td class="n"><b>'+pts(r.I).toFixed(2)+'</b></td><td class="n">'+r.n+'</td></tr>';
  }).join("");
}
function renderAll(){ renderKPIs(); renderStrip(); renderBoard(); renderGaps(); renderOutlets(); }

// ---- controls -------------------------------------------------------------------------
function init(){
  $("stamp").textContent=D.generated;
  var types={}, topics={};
  D.outlets.forEach(function(o){types[o[1]]=1});
  D.items.forEach(function(it){Object.keys(it[7]).forEach(function(t){topics[t]=(topics[t]||0)+it[7][t]})});
  $("ty").innerHTML+='<option value="'+Object.keys(types).sort().join('"></option><option value="')+'"></option>';
  $("ty").innerHTML='<option value="">all media</option>'+Object.keys(types).sort().map(function(t){
    return '<option value="'+esc(t)+'">'+esc(t)+'</option>'}).join("");
  $("tp").innerHTML='<option value="">all topics</option>'+Object.keys(topics).sort(function(a,b){return topics[b]-topics[a]})
    .map(function(t){return '<option value="'+esc(t)+'">'+esc(D.labels[t]||t)+'</option>'}).join("");
  recompute();
  $("foot-assume").textContent = Object.keys(D.defaults).map(function(k){
    return k.toLowerCase().replace(/_/g," ")+" "+D.defaults[k] }).join(", ")+".";
  renderAll();

  $("q").addEventListener("input",function(e){state.q=e.target.value; renderBoard(); renderGaps()});
  $("ty").addEventListener("change",function(e){state.type=e.target.value; renderBoard(); renderGaps()});
  $("tp").addEventListener("change",function(e){state.topic=e.target.value; renderBoard(); renderGaps()});
  $("lim").addEventListener("change",function(e){state.limit=+e.target.value; renderBoard()});
  $("board").addEventListener("click",function(ev){
    if(ev.target.closest("a")) return;
    var el=ev.target.closest(".lb"); if(!el) return;
    var i=+el.dataset.i; state.open = state.open===i?null:i; renderBoard();
  });
  $("board").addEventListener("keydown",function(ev){
    if(ev.key!=="Enter"&&ev.key!==" ") return;
    var el=ev.target.closest(".lb"); if(!el) return;
    ev.preventDefault(); var i=+el.dataset.i; state.open= state.open===i?null:i; renderBoard();
  });
  var lbl=$("striplabel");
  $("strip").addEventListener("mouseover",function(ev){
    var c=ev.target.closest("circle"); if(!c) return;
    var x=rows[+c.dataset.i];
    lbl.textContent=D.outlets[x.o][0]+" · "+x.title+" — "+pts(x.I).toFixed(3)+" points";
  });
  $("strip").addEventListener("click",function(ev){
    var c=ev.target.closest("circle"); if(!c) return;
    state.open=+c.dataset.i; state.limit=0; $("lim").value="0"; renderBoard();
    var el=document.querySelector('.lb[data-i="'+c.dataset.i+'"]');
    if(el) el.scrollIntoView({block:"center"});
  });
  var root=document.documentElement, btn=$("theme");
  function cur(){return root.getAttribute("data-theme")||"system"}
  function label(){var c=cur(); btn.textContent=c==="system"?"Theme":(c==="dark"?"Dark":"Light")}
  try{var sv=localStorage.getItem("psi-theme"); if(sv&&sv!=="system")root.setAttribute("data-theme",sv)}catch(e){}
  label();
  btn.addEventListener("click",function(){
    var order=["system","light","dark"], next=order[(order.indexOf(cur())+1)%3];
    if(next==="system") root.removeAttribute("data-theme"); else root.setAttribute("data-theme",next);
    try{localStorage.setItem("psi-theme",next)}catch(e){}
    label();
  });
}
init();
})();
