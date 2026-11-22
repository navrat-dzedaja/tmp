const fs=require('fs'); const C=require('./route_core.js'); const LAEA=require('./laea.js');
function npy(f){const b=fs.readFileSync(f);const hl=b.readUInt16LE(8);const hdr=b.slice(10,10+hl).toString();const sh=hdr.match(/\((\d+), (\d+)\)/);return {a:new Uint8Array(b.buffer,b.byteOffset+10+hl),h:+sh[1],w:+sh[2]};}
const R0=npy('../dl/plan_R.npy'),G0=npy('../dl/plan_G.npy'),B0=npy('../dl/plan_B.npy');
const PX0=18*1024,PY0=25*1024,X0=2500000,YTOP=5805600;
const fl=(lo,la)=>{const [E,N]=LAEA.fwd(lo,la);return [(E-X0)/100,(YTOP-N)/100];};
const CODES=[111,112,121,122,123,124,131,132,133,141,142,211,212,213,221,222,223,231,241,242,243,244,311,312,313,321,322,323,324,331,332,333,334,335,411,412,421,422,423,511,512,521,522,523];
const GROUPS=[[311,312,313],[322,323,324],[321,333],[231],[211,212,213,241,242,243,244],[221,222,223],[411,412,421,422,423],[331,332,334,335],[511,512,521,522,523],[111,112,121,122,123,124,131,132,133,141,142]];
const prof=process.argv[2]||'hidden';
const LAND={hidden:[1,2,2,5,5,5,5,2,12,Infinity],balanced:[1,2,2,2,5,5,5,2,40,Infinity],short:[2,2,2,2,2,2,5,2,40,3]}[prof];
const ROADV=[[0,15,60,Infinity],[0,8,30,Infinity],[0,6,20,Infinity],[0,4,12,Infinity],[0,3,10,Infinity],[0,6,20,Infinity]];
const RSEL={hidden:[2,2,1,1,1,1],balanced:[2,1,1,1,0,1],short:[2,0,0,0,0,0]}[prof];
const lc=new Float32Array(64).fill(Infinity),water=new Uint8Array(64),group=new Uint8Array(64).fill(255);
GROUPS.forEach((g,gi)=>g.forEach(c=>{const k=CODES.indexOf(c)+1;lc[k]=LAND[gi];group[k]=gi;if(gi===8)water[k]=1;}));
const roadPen=new Float32Array(8);[0,1,2,3,4,7].forEach((b,i)=>roadPen[b]=ROADV[i][RSEL[i]]);
const P={lc,water,group,roadPen,bridgeCost:3,
  bldCell:{hidden:Infinity,balanced:15,short:0}[prof],bR:{hidden:1500,balanced:700,short:0}[prof],bS:{hidden:8,balanced:5,short:0}[prof],
  trackMul:{hidden:1,balanced:.6,short:.6}[prof],trackAdd:0,pathMul:{hidden:1,balanced:.6,short:.6}[prof],pathAdd:{hidden:2,balanced:0,short:0}[prof],rR:{hidden:400,balanced:200,short:0}[prof],rS:4};
const [fx,fy]=fl(18.2625,49.8209),[tx,ty]=fl(14.4378,50.0755);
const dist=Math.hypot(fx-tx,fy-ty), m=Math.max(150,0.25*dist);
const x0=Math.max(PX0,Math.floor(Math.min(fx,tx)-m)), x1=Math.min(PX0+8192,Math.ceil(Math.max(fx,tx)+m));
const y0=Math.max(PY0,Math.floor(Math.min(fy,ty)-m)), y1=Math.min(PY0+6144,Math.ceil(Math.max(fy,ty)+m));
const w=x1-x0,h=y1-y0,N=w*h; const R=new Uint8Array(N),G=new Uint8Array(N),B=new Uint8Array(N);
for(let y=y0;y<y1;y++){const so=(y-PY0)*8192+(x0-PX0);R.set(R0.a.subarray(so,so+w),(y-y0)*w);G.set(G0.a.subarray(so,so+w),(y-y0)*w);B.set(B0.a.subarray(so,so+w),(y-y0)*w);}
let t=performance.now();
const {cost,road}=C.buildCost(R,G,B,N,P); C.roadProx(cost,G,w,h,P.rR,P.rS);
C.escapeZone(cost,R,w,h,[(Math.floor(fy)-y0)*w+(Math.floor(fx)-x0),(Math.floor(ty)-y0)*w+(Math.floor(tx)-x0)],80,60);
const s=C.snap(cost,w,h,(Math.floor(fy)-y0)*w+(Math.floor(fx)-x0),100), e=C.snap(cost,w,h,(Math.floor(ty)-y0)*w+(Math.floor(tx)-x0),100);
console.log('window',w,h,(N/1e6).toFixed(1)+'M cells','cost',(performance.now()-t|0)+'ms','snap',s,e);
t=performance.now(); const res=C.astar(cost,road,w,h,s,e);
console.log('astar',(performance.now()-t|0)+'ms','expanded',res&&res.expanded);
if(!res){console.log('NO PATH');process.exit();}
const st=C.routeStats(res.path,R,G,B,w,P);
console.log(JSON.stringify({km:(st.m/1000).toFixed(1),air:(dist/10).toFixed(1),bldMin:st.bldMin,near300:(100*st.near300/st.m).toFixed(1),cross:st.cross,water:st.water,lc:Object.fromEntries(Object.entries(st.lc).map(([k,v])=>[k,(100*v/st.m).toFixed(1)])),track:(st.trackM/1000).toFixed(1),path:(st.pathM/1000).toFixed(1)}));
fs.writeFileSync('../dl/test_path_'+prof+'.json',JSON.stringify({x0,y0,w,path:Array.from(res.path)}));
