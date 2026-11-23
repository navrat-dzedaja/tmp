import numpy as np, pickle, json, glob, math, shapely, pyarrow.parquet as pq
from scipy.spatial import cKDTree
from pyproj import Transformer
import rasterio
d=pickle.load(open('dl/ruian/adr.pkl','rb')); c=pickle.load(open('dl/ruian/clusters.pkl','rb'))
ciso=np.load('dl/ruian/ciso.npy')
Y,X=d['Y'],d['X']; L=c['L']; size=c['size']; typ=d['typ']
t_ll=Transformer.from_crs(5514,4326,always_xy=True); t_la=Transformer.from_crs(4326,3035,always_xy=True)
lon,lat=t_ll.transform(-Y,-X); E,N=t_la.transform(lon,lat); E=np.asarray(E); N=np.asarray(N); lon=np.asarray(lon); lat=np.asarray(lat)
cand=np.nonzero((size<=6)&(ciso>=500))[0]; cand=cand[cand>0]
order=np.argsort(L,kind='stable'); Ls=L[order]; starts=np.searchsorted(Ls,cand); ends=np.searchsorted(Ls,cand,side='right')
print('candidates',len(cand))
# towns / villages: clusters with many addresses
tree_town=cKDTree(np.column_stack([E,N])[size[L]>=300]); town_idx=np.nonzero(size[L]>=300)[0]
tree_vil=cKDTree(np.column_stack([E,N])[size[L]>=15]); vil_idx=np.nonzero(size[L]>=15)[0]
# grids (LAEA 100 m window)
X0W=4343200; YTW=3245600
R=np.load('dl/plan_R.npy'); G=np.load('dl/plan_G.npy')
bcnt=np.zeros(R.shape,np.uint32)
for f in glob.glob('dl/bld/*.npy'): bcnt+=np.load(f)
CODES=[111,112,121,122,123,124,131,132,133,141,142,211,212,213,221,222,223,231,241,242,243,244,311,312,313,321,322,323,324,331,332,333,334,335,411,412,421,422,423,511,512,521,522,523]
idx={cd:i+1 for i,cd in enumerate(CODES)}
lcg=np.zeros(64,np.uint8)  # 1 forest 2 meadow/grass 3 field 4 water 5 other natural 6 urban
for cd,i in idx.items():
    lcg[i]=1 if cd in (311,312,313,324) else 2 if cd in (231,321,322,333) else 3 if 200<cd<300 else 4 if cd>=500 else 6 if cd<200 else 5
lcmap=lcg[R&63]
# water
wt=pq.read_table('dl/water_cz.parquet')
sub=np.array(wt.column('subtype').to_pylist(),object); cls=np.array(wt.column('class').to_pylist(),object)
nm=wt.column('primary').to_pylist() if 'primary' in wt.column_names else [x['primary'] if x else None for x in wt.column('names').to_pylist()]
inter=np.array([bool(x) for x in wt.column('is_intermittent').to_pylist()])
geo=shapely.from_wkb(wt.column('geometry').combine_chunks().to_numpy(zero_copy_only=False))
proj=lambda g: shapely.transform(g, lambda cc: np.column_stack(t_la.transform(cc[:,0],cc[:,1])))
gt=shapely.get_type_id(geo)  # 0 pt,1 line,3 poly,5 mline,6 mpoly
isline=np.isin(gt,[1,5]); ispoly=np.isin(gt,[3,6]); ispt=gt==0
flow=isline&np.isin(sub,['stream','river','canal'])&(cls!='ditch')&(cls!='drain')
ditch=isline&np.isin(cls,['ditch','drain'])
stand=ispoly&np.isin(sub,['pond','lake','water','reservoir'])&~np.isin(cls,['wastewater','basin','swimming_pool','sewage','water_storage','river'])
spring=ispt&(sub=='spring')
print('flow',flow.sum(),'ditch',ditch.sum(),'stand',stand.sum(),'spring',spring.sum())
def prep(mask):
    ii=np.nonzero(mask)[0]; g=proj(geo[ii]); return ii,g,shapely.STRtree(g)
W={k:prep(m) for k,m in (('flow',flow),('ditch',ditch),('stand',stand),('spring',spring))}
# DEM
dem={}
def dem_tile(la,lo):
    k=(la,lo)
    if k not in dem:
        f=f'dl/dem/Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM.tif'
        try:
            with rasterio.open(f) as ds: dem[k]=(ds.read(1),ds.transform)
        except Exception: dem[k]=None
    return dem[k]
def elev(lo_,la_):
    out=np.full(len(lo_),np.nan)
    for i,(a,b) in enumerate(zip(lo_,la_)):
        t=dem_tile(int(math.floor(b)),int(math.floor(a)))
        if t is None: continue
        arr,tf=t; col,row=~tf*(a,b); r0=int(row-0.5); c0=int(col-0.5); fr=row-0.5-r0; fc=col-0.5-c0
        if 0<=r0<arr.shape[0]-1 and 0<=c0<arr.shape[1]-1:
            z=arr[r0:r0+2,c0:c0+2].astype(float)
            out[i]=z[0,0]*(1-fr)*(1-fc)+z[0,1]*(1-fr)*fc+z[1,0]*fr*(1-fc)+z[1,1]*fr*fc
    return out
t_inv=Transformer.from_crs(3035,4326,always_xy=True)
res=[]
for n,cl in enumerate(cand):
    mem=order[starts[n]:ends[n]]
    e=float(E[mem].mean()); nn=float(N[mem].mean())
    la_,lo_=float(lat[mem].mean()),float(lon[mem].mean())
    pt=shapely.Point(e,nn)
    r=int((YTW-nn)//100); cc=int((e-X0W)//100)
    rec={'lat':round(la_,6),'lon':round(lo_,6),'x':round((e-2500000)/100,1),'y':round((5805600-nn)/100,1),
         'sy':round(float(-Y[mem].mean()),1),'sx':round(float(-X[mem].mean()),1),
         'obec':d['obec'][mem[0]],'cast':d['cast'][mem[0]],
         'adr':'; '.join(sorted({('č.p. ' if typ[m]==1 else 'č.ev. ')+d['cd'][m] for m in mem}))[:80],
         'n':int(len(mem)),'t':('p' if (typ[mem]==1).all() else 'e' if (typ[mem]==2).all() else 'pe'),'iso':int(ciso[cl])}
    dt,it=tree_town.query([e,nn]); rec['town']=[d['obec'][town_idx[it]],int(dt)]
    dv,iv=tree_vil.query([e,nn]); rec['vil']=[d['cast'][vil_idx[iv]],int(dv)]
    # buildings without address: 300-1000 m annulus
    if 10<=r<R.shape[0]-10 and 10<=cc<R.shape[1]-10:
        yy,xx=np.mgrid[-10:11,-10:11]; dd=np.hypot(yy,xx)*100
        win=bcnt[r-10:r+11,cc-10:cc+11]; rec['bld']=int(win[(dd>=300)&(dd<=1000)].sum())
        lw=lcmap[r-5:r+6,cc-5:cc+6][np.hypot(*np.mgrid[-5:6,-5:6])<=5]
        rec['lc']=[int(round(100*(lw==k).mean())) for k in (1,2,3,4)]
        gw=G[max(0,r-60):r+61,max(0,cc-60):cc+61]; oy,ox=r-max(0,r-60),cc-max(0,cc-60)
        def nd(mask):
            yy2,xx2=np.nonzero(mask); 
            return int(np.min(np.hypot(yy2-oy,xx2-ox))*100) if len(yy2) else 6000
        rec['road']=nd((gw&31)>0); rec['major']=nd((gw&7)>0); rec['track']=nd((gw&32)>0)
    # water
    for k,(ii,g,tr) in W.items():
        q,dist=tr.query_nearest(pt,return_distance=True,all_matches=False)
        if len(q)==0: rec[k]=None; continue
        j=ii[q[0]]; dm=float(dist[0])
        if k=='stand': rec[k]=[int(dm),int(shapely.area(g[q[0]])),nm[j] or '']
        elif k=='flow': rec[k]=[int(dm),nm[j] or '',sub[j],int(inter[j])]; rec['_fg']=g[q[0]]
        else: rec[k]=int(dm)
    res.append(rec)
    if n%1000==0: print(n,flush=True)
# DEM: site elevation, stream gradient & height above stream
for rec in res:
    rec['z']=None
for i0 in range(0,len(res),500):
    chunk=res[i0:i0+500]
    z=elev([r['lon'] for r in chunk],[r['lat'] for r in chunk])
    for r,zz in zip(chunk,z): r['z']=None if np.isnan(zz) else round(float(zz),1)
for rec in res:
    g=rec.pop('_fg',None); rec['pond']=0
    if g is None or rec['flow'] is None or rec['flow'][0]>300 or rec['z'] is None: continue
    pt=shapely.Point((rec['x']*100+2500000),(5805600-rec['y']*100))
    s=shapely.ops.nearest_points(g,pt)[0] if hasattr(shapely,'ops') else None
    import shapely.ops as so
    proj_d=g.project(pt); a=max(0,proj_d-200); b=min(g.length,proj_d+200)
    if b-a<120: continue
    ps=[g.interpolate(t) for t in np.linspace(a,b,9)]
    lo_,la_=t_inv.transform([p.x for p in ps],[p.y for p in ps])
    zz=elev(lo_,la_)
    if np.isnan(zz).any(): continue
    grad=abs(zz[-1]-zz[0])/(b-a)*100
    zs=elev(*t_inv.transform([g.interpolate(proj_d).x],[g.interpolate(proj_d).y]))[0]
    rec['grad']=round(float(grad),1); rec['above']=round(float(rec['z']-zs),1)
    ok=0.3<=grad<=5 and rec['above']>=1.5
    rec['pond']=2 if ok and rec['flow'][0]<=150 else 1 if ok else 0
json.dump(res,open('dl/samoty.json','w'),ensure_ascii=False,separators=(',',':'))
import collections
print('done',len(res),'pond',collections.Counter(r['pond'] for r in res))
