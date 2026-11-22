const LAEA=(()=>{const a=6378137,e2=0.0066943800229,e=Math.sqrt(e2),D2R=Math.PI/180,phi0=52*D2R,lam0=10*D2R,FE=4321000,FN=3210000;
const q=p=>{const s=Math.sin(p);return(1-e2)*(s/(1-e2*s*s)-(1/(2*e))*Math.log((1-e*s)/(1+e*s)));};
const qP=q(Math.PI/2),q0=q(phi0),b0=Math.asin(q0/qP),Rq=a*Math.sqrt(qP/2),D=a*(Math.cos(phi0)/Math.sqrt(1-e2*Math.sin(phi0)**2))/(Rq*Math.cos(b0));
const sb0=Math.sin(b0),cb0=Math.cos(b0);
return{fwd(lon,lat){const p=lat*D2R,l=lon*D2R-lam0,b=Math.asin(q(p)/qP),B=Rq*Math.sqrt(2/(1+sb0*Math.sin(b)+cb0*Math.cos(b)*Math.cos(l)));
  return[FE+B*D*Math.cos(b)*Math.sin(l),FN+(B/D)*(cb0*Math.sin(b)-sb0*Math.cos(b)*Math.cos(l))];},
 inv(E,N){const x=E-FE,y=N-FN,r=Math.hypot(x/D,D*y);if(r<1e-9)return[10,52];const C=2*Math.asin(r/(2*Rq));
  const bp=Math.asin(Math.cos(C)*sb0+(D*y*Math.sin(C)*cb0)/r);
  const l=lam0+Math.atan2(x*Math.sin(C),D*r*cb0*Math.cos(C)-D*D*y*sb0*Math.sin(C));
  const p=bp+(e2/3+31*e2*e2/180+517*e2**3/5040)*Math.sin(2*bp)+(23*e2*e2/360+251*e2**3/3780)*Math.sin(4*bp)+(761*e2**3/45360)*Math.sin(6*bp);
  return[l/D2R,p/D2R];}};})();
if(typeof module!=='undefined')module.exports=LAEA;
