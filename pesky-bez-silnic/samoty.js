(function(){
function init(){
const PBS=window.PBS, PLAN=window.PLAN, map=PBS.map, fmt=PBS.fmt, $=id=>document.getElementById(id);
const km=m=>m>=1000?(m/1000).toLocaleString('cs-CZ',{maximumFractionDigits:1})+' km':fmt(m)+' m';
const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let D=null, loading=null, sel=null, shown=40;
const F={iso:1000,water:'any',type:'p',n:'3',forest:0,bld:40,major:0,town:40,road:'any',sort:'iso'};
try{Object.assign(F,JSON.parse(localStorage.getItem('pbs-samoty')||'{}'));}catch(e){}
const saveF=()=>{try{localStorage.setItem('pbs-samoty',JSON.stringify(F))}catch(e){}};
const layer=L.layerGroup(), hi=L.layerGroup();
const COL={pond:'#2e9d5b',water:'#2f6fb5',dry:'#8a8f8b'};
const FLOWN={stream:'potok',river:'řeka',canal:'kanál'};
const hasFlow=r=>r.flow&&r.flow[0]<=200, hasStand=r=>r.stand&&r.stand[0]<=300;
const kind=r=>r.pond===2?'pond':(hasFlow(r)||hasStand(r))?'water':'dry';
const wdist=r=>Math.min(r.flow?r.flow[0]:9e9,r.stand?r.stand[0]:9e9);
const wname=(k,n)=>{const K=k[0].toUpperCase()+k.slice(1); if(!n) return K; const l=n.toLowerCase(); return /potok|řeka|rybník|jezero|nádrž|kanál|struha|strouha|tůň|rameno/.test(l)?n:K+' '+n;};
const title=r=>r.cast&&r.cast!==r.obec?`${r.cast} (${r.obec})`:r.obec;

function load(){
  if(!loading) loading=fetch('samoty.json').then(r=>{if(!r.ok)throw 0;return r.json();}).then(j=>{D=j;render();}).catch(()=>{$('s-count').textContent='Data samot se nepodařilo načíst.';});
  return loading;
}
function pass(r){
  if(r.iso<F.iso) return false;
  if(F.type==='p'&&r.t==='e') return false;
  if(r.n>+F.n) return false;
  if(F.forest&&(!r.lc||r.lc[0]<F.forest)) return false;
  if(F.bld<40&&(r.bld==null||r.bld>F.bld)) return false;
  if(F.major&&(r.major==null||r.major<F.major)) return false;
  if(F.town<40&&r.town[1]>F.town*1000) return false;
  if(F.road==='road'&&!(r.road!=null&&r.road<=300)) return false;
  if(F.road==='noroad'&&!(r.road!=null&&r.road>1000)) return false;
  switch(F.water){
    case 'either': return hasFlow(r)||hasStand(r);
    case 'flow': return hasFlow(r);
    case 'stand': return hasStand(r);
    case 'pond': return r.pond>0;
    case 'spring': return r.spring!=null&&r.spring<=300;
  }
  return true;
}
function chips(r){
  const c=[`<span class="tag">${km(r.iso)} od domů</span>`];
  if(r.flow&&r.flow[0]<=300) c.push(`<span class="tag w">${FLOWN[r.flow[2]]||'potok'} ${fmt(r.flow[0])} m</span>`);
  if(r.stand&&r.stand[0]<=300) c.push(`<span class="tag w">rybník ${fmt(r.stand[0])} m</span>`);
  if(r.pond===2) c.push('<span class="tag p">místo pro rybník</span>');
  if(r.lc&&r.lc[0]>=50) c.push(`<span class="tag">les ${r.lc[0]} %</span>`);
  return c.join(' ');
}
let list=[];
function render(){
  if(!D) return;
  list=D.filter(pass);
  const s=F.sort;
  list.sort(s==='water'?(a,b)=>wdist(a)-wdist(b):s==='forest'?(a,b)=>((b.lc?b.lc[0]:0)-(a.lc?a.lc[0]:0))||b.iso-a.iso:s==='town'?(a,b)=>a.town[1]-b.town[1]:(a,b)=>b.iso-a.iso);
  const n=list.length;
  $('s-count').textContent=n===0?'Filtrům neodpovídá žádná samota':`${fmt(n)} ${n===1?'samota':n<5?'samoty':'samot'}`;
  $('s-list').innerHTML=list.slice(0,shown).map((r,i)=>`<li><button type="button" data-i="${i}" aria-current="${sel===r}">
    <i class="sw" style="background:${COL[kind(r)]}"></i>
    <span class="nm"><b>${esc(title(r))}</b><span>${esc(r.adr)}</span><span class="tags">${chips(r)}</span></span>
    <span class="fig">${km(r.iso)}<span>odstup</span></span></button></li>`).join('');
  $('s-more').hidden=n<=shown;
  layer.clearLayers();
  for(const r of list){
    const m=L.circleMarker(PLAN.ll6(r.x,r.y),{radius:Math.min(9,3.5+(r.iso-500)/450),color:'#ffffff',weight:1.2,fillColor:COL[kind(r)],fillOpacity:.95,bubblingMouseEvents:false});
    m.bindTooltip(`${esc(title(r))} · ${km(r.iso)} od domů`,{direction:'top'});
    m.on('click',()=>select(r,false));
    m.addTo(layer);
  }
  saveF();
}
function select(r,fly){
  sel=r; hi.clearLayers();
  L.circleMarker(PLAN.ll6(r.x,r.y),{radius:13,color:'#d3212b',weight:3,fill:false,interactive:false}).addTo(hi);
  const lc=r.lc||[0,0,0,0];
  const pondTxt=r.pond===2?`Ano, vypadá to slibně: spád potoka ${String(r.grad).replace('.',',')} %, dům ${String(r.above).replace('.',',')} m nad potokem.`
    :r.pond===1?`Možná: potok do 300 m, spád ${String(r.grad).replace('.',',')} %, dům ${String(r.above).replace('.',',')} m nad potokem.`
    :(r.grad!=null?`Spíš ne: spád ${String(r.grad).replace('.',',')} %, dům ${String(r.above).replace('.',',')} m nad potokem.`:'Nevychází, potok je daleko nebo chybí výšková data.');
  const water=[
    r.flow?`<li><b>${esc(wname(FLOWN[r.flow[2]]||'potok',r.flow[1]))}:</b> ${km(r.flow[0])}${r.flow[3]?' (občasný)':''}</li>`:'',
    r.stand?`<li><b>${esc(wname('rybník',r.stand[2]))}:</b> ${km(r.stand[0])}, plocha ${r.stand[1]>=10000?(r.stand[1]/10000).toLocaleString('cs-CZ',{maximumFractionDigits:1})+' ha':fmt(r.stand[1])+' m²'}</li>`:'',
    r.spring!=null&&r.spring<=1000?`<li><b>Pramen:</b> ${km(r.spring)}</li>`:'',
    `<li><b>Nový rybník:</b> ${pondTxt}</li>`].join('');
  const kn=`https://nahlizenidokn.cuzk.gov.cz/MapaIdentifikace.aspx?l=KN&x=${Math.round(r.sy)}&y=${Math.round(r.sx)}`;
  const mp=`https://mapy.com/cs/letecka?x=${r.lon}&y=${r.lat}&z=17`;
  $('s-detail').innerHTML=`<h3><span class="blaze" aria-hidden="true"></span>${esc(title(r))}</h3>
    <p class="hint" style="margin:0">${esc(r.adr)} · ${r.n===1?'1 dům':r.n+' domy'}${r.t==='e'?' · rekreační':r.t==='pe'?' · bydlení i rekreace':''}</p>
    <div class="rgrid">
      <div class="stat"><b>${km(r.iso)}</b><span>k nejbližšímu cizímu domu</span></div>
      <div class="stat"><b>${r.z!=null?fmt(r.z)+' m':'–'}</b><span>nadmořská výška</span></div>
      <div class="stat"><b>${km(r.vil[1])}</b><span>do vesnice ${esc(r.vil[0])}</span></div>
      <div class="stat"><b>${km(r.town[1])}</b><span>do obce ${esc(r.town[0])} (300+ adres)</span></div>
    </div>
    <ul class="facts">${water}</ul>
    <ul class="facts">
      <li><b>Okolí do 500 m:</b> les ${lc[0]} %, louky ${lc[1]} %, pole ${lc[2]} %${lc[3]?`, voda ${lc[3]} %`:''}</li>
      <li><b>Budov bez adresy do 1 km:</b> ${r.bld!=null?fmt(r.bld):'–'}</li>
      <li><b>Příjezd:</b> silnice ${r.road!=null?(r.road>=6000?'dál než 6 km':km(r.road)):'–'}, lesní nebo polní cesta ${r.track!=null?(r.track>=6000?'dál než 6 km':km(r.track)):'–'}</li>
      <li><b>Silnice I. a II. třídy:</b> ${r.major!=null?(r.major>=6000?'dál než 6 km':km(r.major)):'–'}</li>
    </ul>
    <div class="row">
      <a class="link" href="${mp}" target="_blank" rel="noopener">Letecká mapa (Mapy.com)</a>
      <a class="link" href="${kn}" target="_blank" rel="noopener">Katastr nemovitostí</a>
      <button type="button" class="link" id="sd-route">Naplánovat cestu sem</button>
    </div>
    <p class="hint">GPS: <span class="sel">${r.lat.toFixed(5)}, ${r.lon.toFixed(5)}</span></p>`;
  $('s-detail').hidden=false;
  $('sd-route').onclick=()=>PLAN.setDest(r.x,r.y,title(r));
  for(const b of $('s-list').querySelectorAll('button[data-i]')) b.setAttribute('aria-current',String(list[+b.dataset.i]===r));
  if(fly) map.flyTo(PLAN.ll6(r.x,r.y),Math.max(map.getZoom(),5.5),{duration:.8});
  $('s-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
}
function outs(){
  $('so-iso').textContent=km(F.iso); $('so-forest').textContent=F.forest?F.forest+' %':'nerozhoduje';
  $('so-bld').textContent=F.bld>=40?'nerozhoduje':fmt(F.bld); $('so-major').textContent=F.major?km(F.major):'nerozhoduje';
  $('so-town').textContent=F.town>=40?'nerozhoduje':F.town+' km';
}
function bindUI(){
  const ids={iso:'sf-iso',water:'sf-water',type:'sf-type',n:'sf-n',forest:'sf-forest',bld:'sf-bld',major:'sf-major',town:'sf-town',road:'sf-road',sort:'s-sort'};
  for(const [k,id] of Object.entries(ids)){
    const el=$(id); el.value=F[k];
    el.addEventListener(el.type==='range'?'input':'change',()=>{F[k]=el.type==='range'?+el.value:el.value; outs(); shown=40; render();});
  }
  outs();
  $('s-list').onclick=e=>{const b=e.target.closest('button[data-i]'); if(b) select(list[+b.dataset.i],true);};
  $('s-more').onclick=()=>{shown+=40; render();};
  $('s-legend').innerHTML=`<div><i style="background:${COL.pond};border-radius:50%"></i>Voda a místo pro rybník</div><div><i style="background:${COL.water};border-radius:50%"></i>Potok nebo rybník poblíž</div><div><i style="background:${COL.dry};border-radius:50%"></i>Bez vody poblíž</div><div><i style="background:transparent;border:2px solid #d3212b;border-radius:50%"></i>Vybraná samota</div>`;
}
bindUI();
PLAN.regMode('samoty',{
  lede:'Najděte samotu, kde je nejbližší soused aspoň kilometr daleko a kolem teče potok nebo stojí rybník. Data pokrývají všech 3 miliony adres v Česku.',
  eyebrow:'Česko · adresy RÚIAN',
  enter(){PLAN.base(true); layer.addTo(map); hi.addTo(map); load();
    if(!sel) map.flyToBounds(L.latLngBounds(PLAN.ll6(19600,29850),PLAN.ll6(24800,26550)),{duration:.8});},
  leave(){PLAN.base(false); map.removeLayer(layer); map.removeLayer(hi);}
});
}
if(window.PLAN_READY) init(); else window.addEventListener('plan-ready',init,{once:true});
})();
