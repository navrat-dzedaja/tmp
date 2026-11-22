// Routing core: cost surface + A* on a 100 m grid (8 neighbours, no corner cutting).
// R: CLC class index (bits 0-5) | bridge (bit 6) | building in cell (bit 7)
// G: road bits 0 motorway/trunk, 1 primary, 2 secondary, 3 tertiary, 4 minor, 5 track, 6 path, 7 rail
// B: distance to nearest building in 10 m units (255 = 2550 m or more)
function buildCost(R,G,B,N,P){
  const cost=new Float32Array(N), road=new Uint8Array(N);
  const lc=P.lc, water=P.water, rp=P.roadPen;
  const bR=P.bR, bS=P.bS;
  for(let i=0;i<N;i++){
    const r=R[i], g=G[i], k=r&63;
    let c=lc[k];
    if(water[k] && (r&64)) c=P.bridgeCost;
    if(r&128) c+=P.bldCell;
    if(bR>0){const d=B[i]*10; if(d<bR){const t=1-d/bR; c+=bS*t*t;}}
    if(g){
      if(g&32) c=c*P.trackMul+P.trackAdd;
      if(g&64) c=c*P.pathMul+P.pathAdd;
      let pen=0;
      if(g&1){pen+=rp[0];} if(g&2){pen+=rp[1];} if(g&4){pen+=rp[2];} if(g&8){pen+=rp[3];}
      if(g&16){pen+=rp[4];} if(g&128){pen+=rp[7];}
      if(pen>0){c+=pen; road[i]=1;}
    }
    cost[i]=c;
  }
  return {cost,road};
}
function astar(cost,road,w,h,s,t,progress){
  const N=w*h, SQ2=Math.SQRT2;
  let minC=Infinity; for(let i=0;i<N;i++){const c=cost[i]; if(c<minC&&c>0)minC=c;}
  if(!isFinite(minC)) minC=0.01;
  const g=new Float32Array(N); g.fill(Infinity);
  const prev=new Int32Array(N); prev.fill(-1);
  const closed=new Uint8Array(N);
  let cap=1<<16, hk=new Float64Array(cap), hv=new Int32Array(cap), hn=0;
  const tx=t%w, ty=(t/w)|0;
  const H=i=>{const dx=Math.abs(i%w-tx), dy=Math.abs(((i/w)|0)-ty); const mn=dx<dy?dx:dy, mx=dx<dy?dy:dx; return minC*((mx-mn)+SQ2*mn);};
  function push(k,v){ if(hn===cap){cap*=2;const a=new Float64Array(cap);a.set(hk);hk=a;const b=new Int32Array(cap);b.set(hv);hv=b;}
    let i=hn++; while(i>0){const p=(i-1)>>1; if(hk[p]<=k)break; hk[i]=hk[p]; hv[i]=hv[p]; i=p;} hk[i]=k; hv[i]=v; }
  function pop(){ const v=hv[0]; const k=hk[--hn], x=hv[hn]; let i=0;
    while(true){let l=2*i+1; if(l>=hn)break; let r=l+1; if(r<hn&&hk[r]<hk[l])l=r; if(hk[l]>=k)break; hk[i]=hk[l]; hv[i]=hv[l]; i=l;}
    hk[i]=k; hv[i]=x; return v; }
  if(!isFinite(cost[s])||!isFinite(cost[t])) return null;
  g[s]=0; push(H(s),s);
  const DX=[1,-1,0,0,1,1,-1,-1], DY=[0,0,1,-1,1,-1,1,-1];
  let n=0, found=false;
  while(hn>0){
    const i=pop(); if(closed[i])continue; closed[i]=1;
    if(i===t){found=true;break;}
    if(progress && (++n & 0x3ffff)===0) progress(n);
    const x=i%w, y=(i/w)|0, ci=cost[i], gi=g[i];
    for(let d=0;d<8;d++){
      const nx=x+DX[d], ny=y+DY[d];
      if(nx<0||ny<0||nx>=w||ny>=h) continue;
      const j=ny*w+nx; if(closed[j]) continue;
      const cj=cost[j]; if(cj===Infinity) continue;
      let step;
      if(d<4) step=(ci+cj)*0.5;
      else{
        const o1=y*w+nx, o2=ny*w+x;
        if(cost[o1]===Infinity||cost[o2]===Infinity) continue;
        if(road[o1]&&road[o2]) continue;
        step=SQ2*(ci+cj)*0.5;
      }
      const ng=gi+step;
      if(ng<g[j]){g[j]=ng; prev[j]=i; push(ng+H(j),j);}
    }
  }
  if(!found) return null;
  const path=[]; for(let i=t;i!==-1;i=prev[i]) path.push(i);
  path.reverse();
  return {path, total:g[t], expanded:n};
}
function routeStats(path,R,G,B,w,P,ends){
  const st={m:0,midM:0,lc:{},cross:[0,0,0,0,0,0,0,0],water:0,bldMin:Infinity,near300:0,near1000:0,bldCells:0,trackM:0,pathM:0};
  let prevBits=0, prevWater=false;
  for(let k=0;k<path.length;k++){
    const i=path[k];
    let len=0;
    if(k>0){const a=path[k-1]; const dx=Math.abs(a%w-i%w), dy=Math.abs(((a/w)|0)-((i/w)|0)); len=(dx&&dy)?141.42:100;}
    st.m+=len;
    const r=R[i], g=G[i], cls=r&63, grp=P.group[cls];
    st.lc[grp]=(st.lc[grp]||0)+len;
    for(const b of [0,1,2,3,4,7]) if((g&(1<<b)) && !(prevBits&(1<<b))) st.cross[b]++;
    prevBits=g;
    const isW=P.water[cls] && !(r&64);
    if(isW && !prevWater) st.water++;
    prevWater=isW;
    let inEnd=false;
    if(ends){const x=i%w,y=(i/w)|0; for(const e of ends.pts){const dx=x-e%w, dy=y-((e/w)|0); if(dx*dx+dy*dy<=ends.rad*ends.rad){inEnd=true;break;}}}
    if(!inEnd){ st.midM+=len; const d=B[i]*10; if(d<st.bldMin) st.bldMin=d;
      if(d<300) st.near300+=len; if(d<1000) st.near1000+=len; if(r&128) st.bldCells++; }
    if(g&32) st.trackM+=len; if(g&64) st.pathM+=len;
  }
  return st;
}
function roadProx(cost,G,w,h,Rm,S){
  if(!(Rm>0&&S>0)) return;
  const N=w*h, d=new Float32Array(N), INF=1e9;
  for(let i=0;i<N;i++) d[i]=(G[i]&7)?0:INF;
  for(let y=0;y<h;y++) for(let x=0;x<w;x++){const i=y*w+x; let v=d[i]; if(v===0)continue;
    if(x>0&&d[i-1]+100<v)v=d[i-1]+100; if(y>0){const u=i-w; if(d[u]+100<v)v=d[u]+100; if(x>0&&d[u-1]+141<v)v=d[u-1]+141; if(x<w-1&&d[u+1]+141<v)v=d[u+1]+141;} d[i]=v;}
  for(let y=h-1;y>=0;y--) for(let x=w-1;x>=0;x--){const i=y*w+x; let v=d[i]; if(v===0)continue;
    if(x<w-1&&d[i+1]+100<v)v=d[i+1]+100; if(y<h-1){const u=i+w; if(d[u]+100<v)v=d[u]+100; if(x<w-1&&d[u+1]+141<v)v=d[u+1]+141; if(x>0&&d[u-1]+141<v)v=d[u-1]+141;} d[i]=v;}
  for(let i=0;i<N;i++){const v=d[i]; if(v<Rm && cost[i]!==Infinity && v>0){const t=1-v/Rm; cost[i]+=S*t*t;}}
}
function escapeZone(cost,R,w,h,pts,rad,val){
  for(const i of pts){ const x0=i%w, y0=(i/w)|0;
    for(let y=Math.max(0,y0-rad);y<=Math.min(h-1,y0+rad);y++) for(let x=Math.max(0,x0-rad);x<=Math.min(w-1,x0+rad);x++){
      const dx=x-x0, dy=y-y0; if(dx*dx+dy*dy>rad*rad) continue;
      const j=y*w+x; if(cost[j]===Infinity && (R[j]&63)) cost[j]=val; } }
}
function snap(cost,w,h,i,maxR){
  if(isFinite(cost[i])) return i;
  const x0=i%w, y0=(i/w)|0;
  for(let r=1;r<=maxR;r++){ let best=-1,bd=1e18;
    for(let dy=-r;dy<=r;dy++) for(let dx=-r;dx<=r;dx++){ if(Math.max(Math.abs(dx),Math.abs(dy))!==r) continue;
      const x=x0+dx,y=y0+dy; if(x<0||y<0||x>=w||y>=h) continue; const j=y*w+x;
      if(isFinite(cost[j])){const dd=dx*dx+dy*dy; if(dd<bd){bd=dd;best=j;}}}
    if(best>=0) return best; }
  return -1;
}
if(typeof module!=='undefined') module.exports={buildCost,astar,routeStats,roadProx,snap,escapeZone};
