import numpy as np, json, sys, time, gc, shapely
sys.path.insert(0,'code'); import sw
from scipy import ndimage
from pyproj import Transformer
RES=200; X0=2500000; YTOP=1300000+11*409600; H,W=11*2048,12*2048
t0=time.time()
def log(*a): print(round(time.time()-t0), *a, flush=True)
ids=json.load(open('dl/cntr_ids.json'))
trf=Transformer.from_crs(4326,3035,always_xy=True)
def ll2rc(lon,lat):
    x,y=trf.transform(lon,lat); return int((YTOP-y)/RES), int((x-X0)/RES)
SEED=ll2rc(13.50,48.98)      # Šumava: Modrava / Březník
TARGETS={'athens':ll2rc(23.73,37.98),'nordkapp':ll2rc(25.78,71.17),'lisbon':ll2rc(-9.14,38.72)}
def to_px(idx):
    idx=np.asarray(idx); r=idx//W; c=idx%W
    return np.column_stack([(c+0.5)/2.0,(r+0.5)/2.0])   # z4 pixel units (400 m)
def simplify(pts,tol):
    if len(pts)<3: return pts
    return np.array(shapely.LineString(pts).simplify(tol).coords)
def flat(a): return [round(float(v),1) for v in np.asarray(a).ravel()]
def nearest_in(lab, rc, R=40):
    r,c=rc; r0=max(0,r-R); c0=max(0,c-R); win=lab[r0:r+R+1, c0:c+R+1]
    yy,xx=np.nonzero(win)
    if len(yy)==0: return None
    k=np.argmin((yy+r0-r)**2+(xx+c0-c)**2)
    return int((yy[k]+r0)*W + xx[k]+c0)

variant=sys.argv[1]
ROADS={'v1':('big',),'v2':('big','sec'),'v3':('big','sec','tert','rail')}[variant]
mask=np.load('dl/S200.npy' if variant=='v3' else 'dl/M200.npy')>=2
for k in ROADS: mask&=np.load(f'dl/road_{k}200.npy')==0
gc.collect(); log('mask', mask.sum())
lab=np.empty((H,W),np.int32)
n=ndimage.label(mask, structure=[[0,1,0],[1,1,1],[0,1,0]], output=lab)
del mask; gc.collect(); log('labels', n)
area=np.bincount(lab.ravel(), minlength=n+1); area[0]=0
cn=np.load('dl/CNTR200.npy')
big=np.nonzero(area>=250)[0]                      # components >= 10 km2
cin={}                                             # per-country pixel counts for big comps
for ci in range(1,len(ids)+1):
    m=cn==ci
    if not m.any(): continue
    bc=np.bincount(lab[m], minlength=n+1)[big]
    if bc.sum()>0: cin[ci]=bc
    del m
del cn; gc.collect(); log('country counts')
order=np.argsort(-area[big], kind='stable'); bigs=big[order]
feat=list(bigs[:150])
fs=set(feat)
for ci,bc in cin.items():
    # largest components "belonging" to the country: >=30 % inside or >=100 km2 inside
    pos={int(l):i for i,l in enumerate(big)}
    own=[(int(area[big[i]]),int(big[i])) for i in np.nonzero((bc>=2500)|(bc>=0.3*area[big]))[0] if bc[i]>0]
    own.sort(reverse=True)
    for a,l in own[:3]:
        if l not in fs: feat.append(l); fs.add(l)
feat=sorted(feat, key=lambda l:-area[l])[:200]
top=np.array(feat,np.int64)
EDGES=[0.04*(5e5)**(i/54) for i in range(55)]
rank_of=np.zeros(n+1,np.uint8)
akm=area*0.04
binv=np.clip((np.log(np.maximum(akm,0.04)/0.04)/np.log(5e5)*54).astype(np.int64),0,53)
rank_of[:]=(201+binv).astype(np.uint8); rank_of[0]=0
rank_of[top]=np.arange(1,len(top)+1,dtype=np.uint8)
K=len(top)
bigpos={int(l):i for i,l in enumerate(big)}
def composition(l):
    i=bigpos.get(int(l))
    if i is None: return []
    tot=sum(int(bc[i]) for bc in cin.values())
    lst=sorted(((int(bc[i]),ids[ci-1]) for ci,bc in cin.items() if bc[i]>0), reverse=True)
    return [[c,round(100*v/tot,1)] for v,c in lst[:5] if v/tot>=0.005]

# --- Šumava routes on the full label image
dist=np.empty((H,W),np.uint32)
routes={}
s=nearest_in(lab,SEED)
if s is not None:
    Ls=int(lab.flat[s])
    sw.sweep(lab,[s],dist)
    yy,xx=np.nonzero(lab==Ls)
    ii=yy.astype(np.int64)*W+xx
    dd=dist.flat[ii]
    k=int(np.argmax(dd)); e=int(ii[k])
    p=sw.trace(lab,dist,e)
    routes['farthest']={'km':round(float(dd[k])*0.04,1),'trail':flat(simplify(to_px(p),0.6)),'end':flat(to_px([e]))}
    for nm,(ar,ac) in TARGETS.items():
        k=int(np.argmin((yy-ar)**2+(xx-ac)**2)); e=int(ii[k])
        p=sw.trace(lab,dist,e)
        routes[nm]={'km':round(float(dist.flat[e])*0.04,1),'gap_km':round(float(np.hypot(yy[k]-ar,xx[k]-ac))*0.2,1),
                    'trail':flat(simplify(to_px(p),0.6)),'end':flat(to_px([e]))}
    routes['seed']={'rank':int(rank_of[Ls]),'km2':round(float(area[Ls])*0.04,1),'pt':flat(to_px([s])),'cntr':composition(Ls)}
    del yy,xx,ii,dd
log('routes', {k:v.get('km') for k,v in routes.items()})

rank=rank_of[lab]; del lab; gc.collect()
np.save(f'dl/rank_{variant}.npy',rank); log('rank saved')
size_hist={'gt1000':int((area>=25000).sum()),'gt100':int((area>=2500).sum()),'gt10':int((area>=250).sum()),'all':int(n),
           'km2_total':round(float(area.sum())*0.04)}
objs=ndimage.find_objects(rank, max_label=K)
labt=rank.astype(np.int32); labt[labt>K]=0
del rank; gc.collect()
first=sw.first_idx(labt,K)
sw.sweep(labt, first[1:][first[1:]>=0], dist); A,_=sw.argmax_label(labt,dist,K); log('sweep1')
sw.sweep(labt, A[1:][A[1:]>=0], dist); B,dB=sw.argmax_label(labt,dist,K); log('sweep2')
comps=[]
for r in range(1,len(top)+1):
    sl=objs[r-1]
    cntr=composition(top[r-1])
    path=sw.trace(labt,dist,B[r])
    sp=simplify(to_px(path), 0.6 if r<=60 else 1.2)
    comps.append({'r':r,'km2':round(float(area[top[r-1]])*0.04,1),'trail_km':round(float(dB[r])*0.04,1),
        'bbox':[sl[1].start/2, sl[0].start/2, sl[1].stop/2, sl[0].stop/2],'cntr':cntr,'trail':flat(sp)})
log('trails')
json.dump({'variant':variant,'n_components':int(n),'sizes':size_hist,'edges':[round(e,3) for e in EDGES],'comps':comps,'routes':routes},
          open(f'dl/res_{variant}.json','w'),separators=(',',':'))
log('done', comps[0]['km2'], comps[0]['trail_km'], comps[0]['cntr'])
