(function(){
function init(){
const PBS=window.PBS, map=PBS.map, fmt=PBS.fmt, $=id=>document.getElementById(id);
/*LAEA*/
/*CORE*/
const X0=2500000, YTOP=5805600, T=1024;
const PT={tx0:18,ty0:25,nx:8,ny:6};
const PX0=PT.tx0*T, PY0=PT.ty0*T, PX1=(PT.tx0+PT.nx)*T, PY1=(PT.ty0+PT.ny)*T;
const ll6=(x,y)=>L.latLng(-y/64,x/64);
const px6=ll=>{const p=map.project(ll,6);return [p.x,p.y];};
const fromLonLat=(lon,lat)=>{const [E,N]=LAEA.fwd(lon,lat);return [(E-X0)/100,(YTOP-N)/100];};
const toLonLat=(x,y)=>LAEA.inv(X0+x*100,YTOP-y*100);
const inPlan=(x,y)=>x>=PX0&&y>=PY0&&x<PX1&&y<PY1;
const planBounds=L.latLngBounds(ll6(PX0,PY1),ll6(PX1,PY0));
const f1=n=>n.toLocaleString('cs-CZ',{maximumFractionDigits:1});

const CODES=[111,112,121,122,123,124,131,132,133,141,142,211,212,213,221,222,223,231,241,242,243,244,311,312,313,321,322,323,324,331,332,333,334,335,411,412,421,422,423,511,512,521,522,523];
const GROUPS=[
 {id:'forest',name:'Les',codes:[311,312,313]},
 {id:'shrub',name:'Křoviny a vřesoviště',codes:[322,323,324]},
 {id:'grass',name:'Přirozené trávníky',codes:[321,333]},
 {id:'meadow',name:'Louky a pastviny',codes:[231]},
 {id:'field',name:'Pole',codes:[211,212,213,241,242,243,244]},
 {id:'orchard',name:'Sady a vinice',codes:[221,222,223]},
 {id:'wet',name:'Mokřady a rašeliniště',codes:[411,412,421,422,423]},
 {id:'rock',name:'Skály a písky',codes:[331,332,334,335]},
 {id:'water',name:'Řeky a jezera',codes:[511,512,521,522,523],water:true},
 {id:'urban',name:'Zástavba, průmysl, doly',codes:[111,112,121,122,123,124,131,132,133,141,142]},
];
const LV={land:[['pref','preferovat',1],['neut','neutrální',2],['avoid','vyhnout se',5],['ban','zakázat',Infinity]],
  water:[['ford','přebrodit',12],['avoid','vyhnout se',40],['ban','jen po mostech',Infinity]],
  urban:[['neut','neutrální',3],['avoid','vyhnout se',30],['ban','zakázat',Infinity]]};
const ROADS=[
 {bit:0,name:'Dálnice a rychlostní',v:[0,15,60,Infinity]},
 {bit:1,name:'Silnice I. třídy',v:[0,8,30,Infinity]},
 {bit:2,name:'Silnice II. třídy',v:[0,6,20,Infinity]},
 {bit:3,name:'Silnice III. třídy',v:[0,4,12,Infinity]},
 {bit:4,name:'Místní a obslužné',v:[0,3,10,Infinity]},
 {bit:7,name:'Železnice',v:[0,6,20,Infinity]}];
const RLV=['nevadí','přejít opatrně','vyhnout se','zakázat'];
const TLV=[['use','využívat',0.6,0],['neut','neutrální',1,0],['avoid','vyhýbat se',1,2]];
const PROFILES={
 hidden:{desc:'Drží se lesa a obchází budovy i silnice. Trasa bývá delší, ale vede místy, kde potkáte nejméně lidí.',
   bR:1500,bS:8,bCell:'inf',rR:400,track:'neut',path:'avoid',roads:[2,2,1,1,1,1],
   land:{forest:'pref',shrub:'neut',grass:'neut',meadow:'avoid',field:'avoid',orchard:'avoid',wet:'avoid',rock:'neut',water:'ford',urban:'ban'}},
 balanced:{desc:'Preferuje les a lesní cesty. Budovám se vyhýbá s menším odstupem a silnice přechází bez velkých oklik.',
   bR:700,bS:5,bCell:'15',rR:200,track:'use',path:'use',roads:[2,1,1,1,0,1],
   land:{forest:'pref',shrub:'neut',grass:'neut',meadow:'neut',field:'avoid',orchard:'avoid',wet:'avoid',rock:'neut',water:'avoid',urban:'ban'}},
 short:{desc:'Co nejkratší pěší trasa. Využívá cesty a na budovy ani silnice nehledí, jen se nepouští po dálnici.',
   bR:0,bS:0,bCell:'0',rR:0,track:'use',path:'use',roads:[2,0,0,0,0,0],
   land:{forest:'neut',shrub:'neut',grass:'neut',meadow:'neut',field:'neut',orchard:'neut',wet:'avoid',rock:'neut',water:'avoid',urban:'neut'}}};
const PLACES=[
 ['Česko',[['Praha',50.0755,14.4378],['Ostrava',49.8209,18.2625],['Brno',49.1951,16.6068],['Plzeň',49.7384,13.3736],['Olomouc',49.5938,17.2509],['Liberec',50.7663,15.0543],['České Budějovice',48.9745,14.4743],['Hradec Králové',50.2092,15.8328],['Ústí nad Labem',50.6607,14.0323],['Pardubice',50.0343,15.7812],['Zlín',49.2265,17.6707],['Jihlava',49.3961,15.5912],['Karlovy Vary',50.2302,12.8711],['Opava',49.9387,17.9026],['Frýdek-Místek',49.6853,18.3484],['Vsetín',49.3387,17.9962],['Šumperk',49.9653,16.9706],['Jeseník',50.2294,17.2046],['Trutnov',50.561,15.9127],['Děčín',50.7822,14.2148],['Cheb',50.0796,12.3739],['Domažlice',49.4405,12.9298],['Prachatice',49.0129,13.9975],['Český Krumlov',48.8127,14.3175],['Tábor',49.4144,14.6578],['Znojmo',48.8555,16.0488]]],
 ['Za hranicemi',[['Vídeň',48.2082,16.3738],['Linec',48.3069,14.2858],['Bratislava',48.1486,17.1077],['Žilina',49.2231,18.7394],['Krakov',50.0647,19.945],['Katovice',50.2649,19.0238],['Vratislav',51.1079,17.0385],['Drážďany',51.0504,13.7373],['Řezno',49.0134,12.1016],['Pasov',48.5665,13.4312],['Mnichov',48.1351,11.582],['Norimberk',49.4521,11.0767],['Salcburk',47.8095,13.055]]]];
const PL={};
for(const [,arr] of PLACES) for(const [n,la,lo] of arr){const [x,y]=fromLonLat(lo,la); if(inPlan(x,y)) PL[n]=[x,y,la,lo];}

const S={active:false,from:null,to:null,fromName:'Ostrava',toName:'Praha',pick:null,view:'land',prof:'hidden',route:null};
function applyProfile(k){
  const p=PROFILES[k]; S.prof=k;
  Object.assign(S,{bR:p.bR,bS:p.bS,bCell:p.bCell,rR:p.rR,track:p.track,path:p.path,roads:p.roads.slice(),land:{...p.land}});
}
applyProfile('hidden');
try{const s=JSON.parse(localStorage.getItem('pbs-plan')||'null'); if(s&&s.land){Object.assign(S,{prof:s.prof,bR:s.bR,bS:s.bS,bCell:s.bCell,rR:s.rR,track:s.track,path:s.path,roads:s.roads,land:s.land});}}catch(e){}
const savePlan=()=>{try{localStorage.setItem('pbs-plan',JSON.stringify({prof:S.prof,bR:S.bR,bS:S.bS,bCell:S.bCell,rR:S.rR,track:S.track,path:S.path,roads:S.roads,land:S.land}))}catch(e){}};
S.from=PL['Ostrava']?PL['Ostrava'].slice(0,2):null; S.to=PL['Praha']?PL['Praha'].slice(0,2):null;

function params(){
  const lc=new Float32Array(64).fill(Infinity), water=new Uint8Array(64), group=new Uint8Array(64).fill(255);
  GROUPS.forEach((g,gi)=>{
    const lv=g.water?LV.water:g.id==='urban'?LV.urban:LV.land;
    const val=(lv.find(l=>l[0]===S.land[g.id])||lv[1])[2];
    for(const c of g.codes){const k=CODES.indexOf(c)+1; lc[k]=val; group[k]=gi; if(g.water) water[k]=1;}
  });
  const roadPen=new Float32Array(8);
  ROADS.forEach((r,i)=>{roadPen[r.bit]=r.v[S.roads[i]];});
  const tr=TLV.find(t=>t[0]===S.track), pa=TLV.find(t=>t[0]===S.path);
  return {lc,water,group,roadPen,bridgeCost:3,bldCell:S.bCell==='inf'?Infinity:+S.bCell,bR:S.bR,bS:S.bS,
    trackMul:tr[2],trackAdd:tr[3],pathMul:pa[2],pathAdd:pa[3],rR:S.rR,rS:4};
}

// ---------- UI build
function fillSelect(sel,cur){
  let h='<option value="">— vyberte —</option>';
  for(const [grp,arr] of PLACES){h+=`<optgroup label="${grp}">`+arr.filter(([n])=>PL[n]).map(([n])=>`<option value="${n}">${n}</option>`).join('')+'</optgroup>';}
  h+='<option value="__custom">Vlastní bod</option>';
  sel.innerHTML=h; sel.value=cur;
}
function nameOfPt(x,y){const [lo,la]=toLonLat(x,y);return `${la.toFixed(4)}, ${lo.toFixed(4)}`;}
function syncPts(){
  fillSelect($('p-from'),PL[S.fromName]?S.fromName:(S.from?'__custom':''));
  fillSelect($('p-to'),PL[S.toName]?S.toName:(S.to?'__custom':''));
  drawPins();
  const hint=[];
  if(S.from&&!PL[S.fromName]) hint.push('Start: '+nameOfPt(...S.from));
  if(S.to&&!PL[S.toName]) hint.push('Cíl: '+nameOfPt(...S.to));
  $('p-hint').textContent=hint.join(' · ');
}
function filtersUI(){
  $('f-bR').value=S.bR; $('f-bS').value=S.bS; $('f-bCell').value=S.bCell; $('f-rR').value=S.rR;
  $('o-bR').textContent=S.bR?fmt(S.bR)+' m':'vypnuto'; $('o-bS').textContent=S.bS; $('o-rR').textContent=S.rR?fmt(S.rR)+' m':'vypnuto';
  $('f-land').innerHTML=GROUPS.map(g=>{const lv=g.water?LV.water:g.id==='urban'?LV.urban:LV.land;
    return `<div class="frow"><label for="fl-${g.id}"><i class="sq" style="background:${PAL().g[g.id]}"></i>${g.name}</label><select id="fl-${g.id}" data-g="${g.id}">${lv.map(l=>`<option value="${l[0]}"${S.land[g.id]===l[0]?' selected':''}>${l[1]}</option>`).join('')}</select></div>`;}).join('');
  $('f-roads').innerHTML=ROADS.map((r,i)=>`<div class="frow"><label for="fr-${i}">${r.name}</label><select id="fr-${i}" data-r="${i}">${RLV.map((t,j)=>`<option value="${j}"${S.roads[i]===j?' selected':''}>${t}</option>`).join('')}</select></div>`).join('')
   +`<div class="frow"><label for="ft-track">Lesní a polní cesty</label><select id="ft-track">${TLV.map(t=>`<option value="${t[0]}"${S.track===t[0]?' selected':''}>${t[1]}</option>`).join('')}</select></div>`
   +`<div class="frow"><label for="ft-path">Pěšiny a turistické stezky</label><select id="ft-path">${TLV.map(t=>`<option value="${t[0]}"${S.path===t[0]?' selected':''}>${t[1]}</option>`).join('')}</select></div>`;
  for(const k of ['hidden','balanced','short']) $('pr-'+k).setAttribute('aria-pressed',String(S.prof===k));
  $('prof-desc').textContent=S.prof==='custom'?'Vlastní nastavení filtrů.':PROFILES[S.prof].desc;
}
function changed(){S.prof='custom';filtersUI();savePlan();if(S.view==='cost')planLayer.redraw();}

// ---------- palette
const PALS={
 light:{g:{forest:'#4f8a4f',shrub:'#8fb36a',grass:'#b9cf86',meadow:'#dde2a6',field:'#f3ecd6',orchard:'#e8cfa6',wet:'#79aeb0',rock:'#cbc4b7',water:'#8fb9d6',urban:'#c6beb6'},
   nodata:'#e8e7e2',bld:'#8c3a2b',road:['#c0392b','#e0702c','#d99a2b','#8f8576','#a69d90','','','#2b2b2b'],track:'#6d5536',path:'#6a4f86',
   ramp:['#2f8f5b','#a8c94d','#f2d24b','#e0703a','#7a1f5c'],ban:'#2a2a2a'},
 dark:{g:{forest:'#2f5a33',shrub:'#4d6b3c',grass:'#5f6f45',meadow:'#6a6c48',field:'#3a3528',orchard:'#4a3d2c',wet:'#2f5a5c',rock:'#575249',water:'#2a4a60',urban:'#4a4541'},
   nodata:'#1b1d20',bld:'#e08a70',road:['#ff6b5a','#f0954f','#e9c46a','#a59e92','#7d776d','','','#d0d0d0'],track:'#b89a6a',path:'#a98fd0',
   ramp:['#2f8f5b','#93b445','#d9bb3f','#d0632f','#9a3d7a'],ban:'#050505'}};
const PAL=()=>PBS.isDark()?PALS.dark:PALS.light;
const H=PBS.hex, PK=PBS.pack, MX=PBS.mix;
let LUT;
function buildLUT(){
  const p=PAL(), lc=new Uint32Array(64).fill(PK(H(p.nodata)));
  GROUPS.forEach(g=>{for(const c of g.codes) lc[CODES.indexOf(c)+1]=PK(H(g.id&&p.g[g.id]));});
  const lcRGB=[]; for(let k=0;k<64;k++){const v=lc[k];lcRGB[k]=[v&255,(v>>8)&255,(v>>16)&255];}
  const trackLc=new Uint32Array(64), pathLc=new Uint32Array(64);
  for(let k=0;k<64;k++){trackLc[k]=PK(MX(lcRGB[k],H(p.track),.45)); pathLc[k]=PK(MX(lcRGB[k],H(p.path),.4));}
  const ramp=new Uint32Array(256), st=p.ramp.map(H);
  for(let i=0;i<256;i++){const t=i/255*(st.length-1), a=Math.min(st.length-2,Math.floor(t)); ramp[i]=PK(MX(st[a],st[a+1],t-a));}
  LUT={lc,trackLc,pathLc,bld:PK(H(p.bld)),road:p.road.map(c=>c?PK(H(c)):0),ramp,ban:PK(H(p.ban))};
}
buildLUT();

// ---------- planner tiles (100 m)
const imgCache=new Map();
function loadTile(tx,ty){const k=`${tx}_${ty}`; if(!imgCache.has(k)) imgCache.set(k,PBS.loadImg(`p/${k}.png`)); return imgCache.get(k);}
const scr=document.createElement('canvas'); scr.width=scr.height=T; const sx=scr.getContext('2d',{willReadFrequently:true});
function rgbOf(img){sx.clearRect(0,0,T,T); sx.drawImage(img,0,0); const d=sx.getImageData(0,0,T,T).data, N=T*T;
  const R=new Uint8Array(N),G=new Uint8Array(N),B=new Uint8Array(N); for(let i=0,p=0;i<N;i++,p+=4){R[i]=d[p];G[i]=d[p+1];B[i]=d[p+2];} return {R,G,B};}
function paintPlan(c,img){
  const ctx=c.getContext('2d'), out=ctx.createImageData(T,T), o=new Uint32Array(out.data.buffer), N=T*T;
  if(!img){ctx.putImageData(out,0,0);return;}
  const {R,G,B}=rgbOf(img);
  if(S.view==='cost'){
    const P=params(); const {cost}=buildCost(R,G,B,N,P); roadProx(cost,G,T,T,P.rR,P.rS);
    const L60=Math.log(60);
    for(let i=0;i<N;i++){const v=cost[i]; if(v===Infinity){o[i]=LUT.ban;continue;} if(!(R[i]&63)){o[i]=0;continue;}
      const t=Math.max(0,Math.min(1,Math.log(Math.max(v,1))/L60)); o[i]=LUT.ramp[(t*255)|0];}
  } else {
    const rd=LUT.road;
    for(let i=0;i<N;i++){const r=R[i], g=G[i], k=r&63; if(!k){o[i]=0;continue;}
      let col=(g&32)?LUT.trackLc[k]:(g&64)?LUT.pathLc[k]:LUT.lc[k];
      if(r&128) col=LUT.bld;
      if(g&31||g&128){ if(g&1)col=rd[0]; else if(g&2)col=rd[1]; else if(g&4)col=rd[2]; else if(g&128)col=rd[7]; else if(g&8)col=rd[3]; else if(g&16)col=rd[4]; }
      o[i]=col;}
  }
  ctx.putImageData(out,0,0);
}
const PlanTiles=L.GridLayer.extend({createTile(co,done){const c=document.createElement('canvas');c.width=c.height=T;
  loadTile(co.x,co.y).then(img=>{try{paintPlan(c,img);}catch(e){} done(null,c);}); return c;}});
const planLayer=new PlanTiles({tileSize:T,minNativeZoom:6,maxNativeZoom:6,minZoom:4,maxZoom:7,bounds:planBounds,noWrap:true,keepBuffer:0,updateWhenZooming:false,zIndex:5});
const frame=L.rectangle(planBounds,{color:'#6d746f',weight:1.2,dashArray:'6 4',fill:false,interactive:false});
const routeLayer=L.layerGroup(), pinLayer=L.layerGroup();

// ---------- pins
function pin(label,cls){return L.divIcon({className:'',html:`<span class="ppin ${cls}">${label}</span>`,iconSize:null,iconAnchor:[0,0]});}
function drawPins(){
  pinLayer.clearLayers();
  if(S.from) L.marker(ll6(...S.from),{icon:pin('Start','s'),interactive:false}).addTo(pinLayer);
  if(S.to) L.marker(ll6(...S.to),{icon:pin('Cíl','e'),interactive:false}).addTo(pinLayer);
}

// ---------- routing
let worker=null;
function getWorker(){
  if(worker) return worker;
  const src=[buildCost,astar,routeStats,roadProx,snap,escapeZone].map(f=>f.toString()).join('\n')+`
onmessage=e=>{const {R,G,B,w,h,s,t,P}=e.data; const N=w*h;
 const {cost,road}=buildCost(R,G,B,N,P); roadProx(cost,G,w,h,P.rR,P.rS);
 escapeZone(cost,R,w,h,[s,t],80,60);
 const s2=snap(cost,w,h,s,100), t2=snap(cost,w,h,t,100);
 if(s2<0||t2<0){postMessage({err:s2<0?'start':'cil'});return;}
 const res=astar(cost,road,w,h,s2,t2,n=>postMessage({progress:n}));
 if(!res){postMessage({err:'nopath'});return;}
 const st=routeStats(res.path,R,G,B,w,P,{pts:[s,t],rad:80});
 postMessage({path:Int32Array.from(res.path),st,s2,t2,total:res.total,expanded:res.expanded});};`;
  worker=new Worker(URL.createObjectURL(new Blob([src],{type:'text/javascript'})));
  return worker;
}
let busy=false;
async function run(){
  if(busy) return;
  if(!S.from||!S.to){$('p-status').textContent='Vyberte start i cíl.';return;}
  busy=true; $('p-go').disabled=true; $('p-status').textContent='Načítám data oblasti…';
  const [fx,fy]=S.from,[tx,ty]=S.to, dist=Math.hypot(fx-tx,fy-ty), m=Math.max(150,0.25*dist);
  const x0=Math.max(PX0,Math.floor(Math.min(fx,tx)-m)), x1=Math.min(PX1,Math.ceil(Math.max(fx,tx)+m));
  const y0=Math.max(PY0,Math.floor(Math.min(fy,ty)-m)), y1=Math.min(PY1,Math.ceil(Math.max(fy,ty)+m));
  const w=x1-x0, h=y1-y0, N=w*h;
  const R=new Uint8Array(N),G=new Uint8Array(N),B=new Uint8Array(N);
  try{
    for(let ty0=Math.floor(y0/T);ty0<=Math.floor((y1-1)/T);ty0++) for(let tx0=Math.floor(x0/T);tx0<=Math.floor((x1-1)/T);tx0++){
      const img=await loadTile(tx0,ty0); if(!img) continue;
      const d=rgbOf(img), ox=tx0*T, oy=ty0*T;
      const ax=Math.max(x0,ox), bx=Math.min(x1,ox+T), ay=Math.max(y0,oy), by=Math.min(y1,oy+T);
      for(let y=ay;y<by;y++){const so=(y-oy)*T+(ax-ox), dO=(y-y0)*w+(ax-x0), n=bx-ax;
        R.set(d.R.subarray(so,so+n),dO); G.set(d.G.subarray(so,so+n),dO); B.set(d.B.subarray(so,so+n),dO);}
    }
  }catch(e){$('p-status').textContent='Data oblasti se nepodařilo načíst.';busy=false;$('p-go').disabled=false;return;}
  $('p-status').textContent=`Hledám trasu v ${f1(N/1e6)} mil. buněk…`;
  const s=(Math.floor(fy)-y0)*w+(Math.floor(fx)-x0), t=(Math.floor(ty)-y0)*w+(Math.floor(tx)-x0);
  const P=params(); const t0=performance.now();
  const wk=getWorker();
  const Rc=R.slice(), Gc=G.slice(), Bc=B.slice();
  wk.onmessage=e=>{
    const d=e.data;
    if(d.progress){$('p-status').textContent=`Hledám trasu… prošlo ${f1(d.progress/1e6)} mil. buněk`;return;}
    busy=false; $('p-go').disabled=false;
    if(d.err){
      $('p-status').textContent=d.err==='nopath'?'Trasu se s těmito filtry nepodařilo najít. Povolte přechod některé překážky (např. dálnice nebo vody).'
        :`${d.err==='start'?'Start':'Cíl'} leží v zakázané oblasti a do 10 km není průchozí místo. Zmírněte filtry.`;
      return;
    }
    $('p-status').textContent=`Hotovo za ${f1((performance.now()-t0)/1000)} s.`;
    showRoute(d,{x0,y0,w,R:Rc,G:Gc,B:Bc},dist);
  };
  wk.onerror=()=>{busy=false;$('p-go').disabled=false;$('p-status').textContent='Výpočet selhal, zkuste menší vzdálenost.';};
  wk.postMessage({R,G,B,w,h,s,t,P},[R.buffer,G.buffer,B.buffer]);
}
function days(km){const n=Math.max(1,Math.round(km/25));return n===1?'1 den':n<5?n+' dny':n+' dní';}
function showRoute(d,W,airCells){
  routeLayer.clearLayers();
  const pts=[]; for(const i of d.path){pts.push([W.x0+(i%W.w)+0.5, W.y0+Math.floor(i/W.w)+0.5]);}
  const ll=pts.map(p=>ll6(p[0],p[1]));
  PBS.blazeLine(ll,routeLayer,{w:4});
  const sp=pts[0], ep=pts[pts.length-1];
  const conn=(a,b)=>L.polyline([ll6(...a),ll6(...b)],{color:'#6d746f',weight:2,dashArray:'4 4',interactive:false}).addTo(routeLayer);
  if(Math.hypot(sp[0]-S.from[0],sp[1]-S.from[1])>1.5) conn(S.from,sp);
  if(Math.hypot(ep[0]-S.to[0],ep[1]-S.to[1])>1.5) conn(S.to,ep);
  map.flyToBounds(L.latLngBounds(ll).pad(.15),{duration:.8});
  const st=d.st, km=st.m/1000, title=`${PL[S.fromName]?S.fromName:'Start'} → ${PL[S.toName]?S.toName:'Cíl'}`;
  $('r-title').textContent=title;
  $('r-grid').innerHTML=[
    [fmt(km)+' km',`délka trasy (vzdušně ${fmt(airCells/10)} km)`],
    ['~'+fmt(km/3.5)+' h',`chůze při 3,5 km/h, asi ${days(km)} po 25 km`],
    [st.midM>0?fmt(st.bldMin)+' m':'–','nejmenší odstup od budov (mimo 8 km u startu a cíle)'],
    [st.midM>0?fmt(100*st.near300/st.midM)+' %':'–','této části vede do 300 m od budov']
  ].map(([a,b])=>`<div class="stat"><b>${a}</b><span>${b}</span></div>`).join('');
  const p=PAL(), parts=GROUPS.map((g,gi)=>[g,st.lc[gi]||0]).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
  $('r-bars').innerHTML=`<div class="bar">${parts.map(([g,v])=>`<i style="background:${p.g[g.id]};flex:${v}" title="${g.name} ${fmt(100*v/st.m)} %"></i>`).join('')}</div>`
    +`<div class="barl">${parts.slice(0,5).map(([g,v])=>`<span><i style="background:${p.g[g.id]}"></i>${g.name} ${fmt(100*v/st.m)} %</span>`).join('')}</div>`;
  const cr=ROADS.map(r=>[r.name,st.cross[r.bit]]).filter(([,n])=>n>0).map(([n,c])=>`${n.replace('Silnice ','')} ${c}×`);
  $('r-text').innerHTML=`<b>Přechody:</b> ${cr.length?cr.join(', '):'žádná silnice ani železnice'}${st.water?`, voda ${st.water}×`:''}. `
    +`Po lesních a polních cestách ${f1(st.trackM/1000)} km, po pěšinách ${f1(st.pathM/1000)} km.`;
  // GPX
  const mpts=pts.map(([x,y])=>L.point(X0+x*100,YTOP-y*100));
  const simp=L.LineUtil.simplify(mpts,25);
  const trk=simp.map(q=>{const [lo,la]=LAEA.inv(q.x,q.y);return `<trkpt lat="${la.toFixed(6)}" lon="${lo.toFixed(6)}"/>`;}).join('\n');
  const wp=(n,[x,y])=>{const [lo,la]=toLonLat(x,y);return `<wpt lat="${la.toFixed(6)}" lon="${lo.toFixed(6)}"><name>${n}</name></wpt>`;};
  $('r-gpx').value=`<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Pesky bez silnic" xmlns="http://www.topografix.com/GPX/1/1">\n${wp('Start',S.from)}\n${wp('Cil',S.to)}\n<trk><name>${title}</name><trkseg>\n${trk}\n</trkseg></trk>\n</gpx>`;
  $('p-result').hidden=false;
  S.route=d;
}

// ---------- legend
function legend(){
  const p=PAL(); const sw=(c,t)=>`<div><i style="background:${c}"></i>${t}</div>`;
  if(S.view==='cost'){
    $('p-legend').innerHTML=`<div class="ramp">${p.ramp.map(c=>`<i style="background:${c}"></i>`).join('')}</div><div class="rampl"><span>snadné, skryté</span><span>náročné, na očích</span></div><div class="legend" style="margin-top:8px">${sw(p.ban,'zakázané')}</div><p class="hint">Barvy se mění podle filtrů. Zobrazí se po přiblížení na Česko.</p>`;
  } else {
    $('p-legend').innerHTML=`<div class="legend">${GROUPS.map(g=>sw(p.g[g.id],g.name)).join('')}${sw(p.bld,'Budova')}${sw(p.road[0],'Dálnice')}${sw(p.road[1],'Silnice I. třídy')}${sw(p.road[2],'Silnice II. třídy')}${sw(p.road[3],'III. třída, místní')}${sw(p.road[7],'Železnice')}${sw(p.track,'Lesní cesta')}</div><p class="hint">Podklad v rozlišení 100 m se zobrazí po přiblížení na Česko.</p>`;
  }
}

// ---------- mode switching & events
const LEDE={areas:[document.querySelector('.lede').textContent,document.querySelector('.eyebrow').lastChild.textContent],
  plan:['Naplánujte pěší trasu, která se drží co nejdál od lidí. Vyberte start a cíl, nastavte, čemu se vyhnout, a plánovač najde cestu přes lesy a mimo budovy i silnice.','Česko a okolí · mřížka 100 m']};
function setActive(on){
  S.active=on; const ld=LEDE[on?'plan':'areas']; document.querySelector('.lede').textContent=ld[0]; document.querySelector('.eyebrow').lastChild.textContent=ld[1]; $('mode-plan').hidden=!on; $('mode-areas').hidden=on;
  $('tab-areas').setAttribute('aria-selected',String(!on)); $('tab-plan').setAttribute('aria-selected',String(on));
  if(on){ PBS.hideAreas(true); planLayer.addTo(map); frame.addTo(map); routeLayer.addTo(map); pinLayer.addTo(map);
    if(!S.route) map.flyToBounds(L.latLngBounds(ll6(PL['Praha'][0]-300,PL['Ostrava'][1]+700),ll6(PL['Ostrava'][0]+300,PL['Praha'][1]-700)),{duration:.8}); }
  else { PBS.hideAreas(false); map.removeLayer(planLayer); map.removeLayer(frame); map.removeLayer(routeLayer); map.removeLayer(pinLayer); }
  try{localStorage.setItem('pbs-tab',on?'plan':'areas')}catch(e){}
}
$('tab-areas').onclick=()=>setActive(false);
$('tab-plan').onclick=()=>setActive(true);
for(const k of ['hidden','balanced','short']) $('pr-'+k).onclick=()=>{applyProfile(k);filtersUI();savePlan();if(S.view==='cost')planLayer.redraw();};
$('f-bR').oninput=e=>{S.bR=+e.target.value;changed();};
$('f-bS').oninput=e=>{S.bS=+e.target.value;changed();};
$('f-rR').oninput=e=>{S.rR=+e.target.value;changed();};
$('f-bCell').onchange=e=>{S.bCell=e.target.value;changed();};
$('f-land').onchange=e=>{const g=e.target.dataset.g; if(g){S.land[g]=e.target.value;changed();}};
$('f-roads').onchange=e=>{const t=e.target; if(t.dataset.r!==undefined) S.roads[+t.dataset.r]=+t.value; else if(t.id==='ft-track') S.track=t.value; else if(t.id==='ft-path') S.path=t.value; changed();};
function setPlace(which,name){ if(!PL[name]) return; S[which]=PL[name].slice(0,2); S[which+'Name']=name; syncPts(); }
$('p-from').onchange=e=>{if(e.target.value==='__custom'){startPick('from');return;} setPlace('from',e.target.value);};
$('p-to').onchange=e=>{if(e.target.value==='__custom'){startPick('to');return;} setPlace('to',e.target.value);};
function startPick(w){S.pick=S.pick===w?null:w; $('pick-from').setAttribute('aria-pressed',String(S.pick==='from')); $('pick-to').setAttribute('aria-pressed',String(S.pick==='to'));
  map.getContainer().style.cursor=S.pick?'crosshair':''; if(S.pick) $('p-status').textContent=`Klikněte do mapy, kam umístit ${S.pick==='from'?'start':'cíl'}.`;}
$('pick-from').onclick=()=>startPick('from');
$('pick-to').onclick=()=>startPick('to');
$('p-swap').onclick=()=>{[S.from,S.to]=[S.to,S.from];[S.fromName,S.toName]=[S.toName,S.fromName];syncPts();};
function coordSet(which){
  const m=$('p-coord').value.replace(/[^\d.,\s-]/g,' ').trim().split(/[\s,;]+/).filter(Boolean).map(Number);
  if(m.length<2||m.some(isNaN)){$('p-status').textContent='Zadejte souřadnice ve tvaru 49.82, 18.26 (šířka, délka).';return;}
  let [la,lo]=m; if(la<lo&&lo>40){[la,lo]=[lo,la];}
  const [x,y]=fromLonLat(lo,la);
  if(!inPlan(x,y)){$('p-status').textContent='Bod leží mimo oblast plánovače (Česko a okolí).';return;}
  S[which]=[x,y]; S[which+'Name']='__custom'; syncPts(); map.panTo(ll6(x,y));
}
$('p-coord-from').onclick=()=>coordSet('from');
$('p-coord-to').onclick=()=>coordSet('to');
$('p-go').onclick=run;
$('pv-land').onclick=()=>{S.view='land';$('pv-land').setAttribute('aria-pressed','true');$('pv-cost').setAttribute('aria-pressed','false');legend();planLayer.redraw();};
$('pv-cost').onclick=()=>{S.view='cost';$('pv-land').setAttribute('aria-pressed','false');$('pv-cost').setAttribute('aria-pressed','true');legend();planLayer.redraw();};
$('r-copy').onclick=()=>{const ta=$('r-gpx'); const done=()=>{$('r-copy').textContent='Zkopírováno';setTimeout(()=>$('r-copy').textContent='Kopírovat',1500);};
  try{navigator.clipboard.writeText(ta.value).then(done,()=>{ta.focus();ta.select();});}catch(e){ta.focus();ta.select();}};

// readout & click hooks (called from the main map script)
const p1=document.createElement('canvas');p1.width=p1.height=1;const pc=p1.getContext('2d',{willReadFrequently:true});
const GNAME=new Array(64).fill('Mimo data'); GROUPS.forEach(g=>{for(const c of g.codes) GNAME[CODES.indexOf(c)+1]=g.name;});
const RNAMES=[[1,'dálnice'],[2,'silnice I. tř.'],[4,'silnice II. tř.'],[8,'silnice III. tř.'],[16,'místní silnice'],[32,'lesní/polní cesta'],[64,'pěšina'],[128,'železnice']];
let rdTok=0;
async function readout(e,ro){
  const [x,y]=px6(e.latlng); if(!inPlan(x,y)||map.getZoom()<4){ro.hidden=true;return;}
  const tok=++rdTok; const img=await loadTile(Math.floor(x/T),Math.floor(y/T)); if(tok!==rdTok) return;
  if(!img){ro.hidden=true;return;}
  pc.clearRect(0,0,1,1); pc.drawImage(img,Math.floor(x)%T,Math.floor(y)%T,1,1,0,0,1,1); const [r,g,b]=pc.getImageData(0,0,1,1).data;
  const P=params(); const one=buildCost(Uint8Array.of(r),Uint8Array.of(g),Uint8Array.of(b),1,P).cost[0];
  const rds=RNAMES.filter(([bit])=>g&bit).map(([,n])=>n);
  ro.innerHTML=`<b>${GNAME[r&63]}</b>${r&64?' · most':''}<br><span class="k">Nejbližší budova:</span> ${r&128?'v této buňce':(b>=255?'víc než 2,5 km':'asi '+fmt(b*10)+' m')}`
    +(rds.length?`<br><span class="k">V buňce:</span> ${rds.join(', ')}`:'')
    +`<br><span class="k">Náročnost podle filtrů:</span> ${one===Infinity?'zakázáno':f1(one)}`;
  ro.hidden=false;
}
function click(e){
  if(!S.pick) return;
  const [x,y]=px6(e.latlng);
  if(!inPlan(x,y)){$('p-status').textContent='Bod leží mimo oblast plánovače (Česko a okolí).';return;}
  S[S.pick]=[x,y]; S[S.pick+'Name']='__custom'; const w=S.pick; startPick(w); $('p-status').textContent=''; syncPts();
}
window.PLAN={get active(){return S.active;},readout,click,retheme(){buildLUT();legend();filtersUI();if(S.active)planLayer.redraw();}};

syncPts(); filtersUI(); legend();
let tab='areas'; try{tab=localStorage.getItem('pbs-tab')||'areas';}catch(e){}
if(location.hash==='#planovac') tab='plan';
setActive(tab==='plan');
}
if(window.PBS) init(); else window.addEventListener('pbs-ready',init,{once:true});
})();
