import sys; sys.path.insert(0,'code')
import pyarrow.parquet as pq, pandas as pd, numpy as np, shapely, time, os
from shapely.ops import substring
from concurrent.futures import ThreadPoolExecutor
from httpfile import HTTPRangeFile
from pyproj import Transformer
from rasterio.features import rasterize
from affine import Affine
X0W=4343200; YTW=3245600; W=8192; H=6144; RES=100
LON0,LON1,LAT0,LAT1=10.29,22.24,46.23,52.32
tf=Affine(RES,0,X0W,0,-RES,YTW)
tr=Transformer.from_crs(4326,3035,always_xy=True)
def proj(c):
    x,y=tr.transform(c[:,0],c[:,1]); return np.column_stack([x,y])
BIT={'motorway':0,'trunk':0,'primary':1,'secondary':2,'tertiary':3,
     'unclassified':4,'residential':4,'living_street':4,'service':4,'pedestrian':4,
     'track':5,'path':6,'footway':6,'cycleway':6,'bridleway':6,'steps':6}
RAIL={'standard_gauge','narrow_gauge'}
df=pd.read_pickle('dl/ovt_meta.pkl')
k=['file_name','row_group_id']
p=df.pivot_table(index=k,columns='path_in_schema',values='stats_min',aggfunc='first')
q=df.pivot_table(index=k,columns='path_in_schema',values='stats_max',aggfunc='first')
m=(q['bbox, xmax'].astype(float)>LON0)&(p['bbox, xmin'].astype(float)<LON1)&(q['bbox, ymax'].astype(float)>LAT0)&(p['bbox, ymin'].astype(float)<LAT1)
jobs={}
for f,r in m[m].index: jobs.setdefault(f,[]).append(int(r))
os.makedirs('dl/wroads',exist_ok=True)
def work(item):
    u,sel=item; out=f"dl/wroads/{u.split('/')[-1][:10]}.npz"
    if os.path.exists(out): return out,0
    L=np.zeros((9,H,W),np.uint8)   # 0-7 bits, 8 = bridges
    pf=pq.ParquetFile(HTTPRangeFile(u),pre_buffer=True)
    n=0
    for i in range(0,len(sel),8):
        tb=pf.read_row_groups(sel[i:i+8],columns=['subtype','class','road_flags','rail_flags','geometry','bbox'])
        b=tb.column('bbox').combine_chunks()
        lo0=b.field('xmin').to_numpy(); lo1=b.field('xmax').to_numpy(); la0=b.field('ymin').to_numpy(); la1=b.field('ymax').to_numpy()
        keep=np.nonzero((lo1>LON0)&(lo0<LON1)&(la1>LAT0)&(la0<LAT1))[0]
        if len(keep)==0: continue
        tb=tb.take(keep)
        sub=tb.column('subtype').to_pylist(); cls=tb.column('class').to_pylist()
        rf=tb.column('road_flags').to_pylist(); lf=tb.column('rail_flags').to_pylist()
        geo=shapely.from_wkb(tb.column('geometry').combine_chunks().to_numpy(zero_copy_only=False))
        groups=[[] for _ in range(9)]
        for j in range(len(sub)):
            g=geo[j]
            if g is None: continue
            if sub[j]=='rail':
                if cls[j] not in RAIL: continue
                bit=7; flags=lf[j]
            elif sub[j]=='road':
                bit=BIT.get(cls[j])
                if bit is None: continue
                flags=rf[j]
            else: continue
            cut=[]; brg=[]; full=False
            for fl in (flags or []):
                vals=set(fl['values'] or [])
                if 'is_tunnel' in vals or 'is_bridge' in vals or (bit==7 and vals & {'is_abandoned','is_disused'}):
                    if fl['between'] is None:
                        full=True
                        if 'is_bridge' in vals and bit!=7: brg.append((0.0,1.0))
                        break
                    cut.append(tuple(fl['between']))
                    if 'is_bridge' in vals and bit!=7: brg.append(tuple(fl['between']))
            for a,c in brg:
                s=g if (a,c)==(0.0,1.0) else substring(g,a,c,normalized=True)
                if not s.is_empty: groups[8].append(s)
            if full: continue
            if cut:
                cut.sort(); pos=0.0
                for a,c in cut:
                    if a>pos+1e-6:
                        s=substring(g,pos,a,normalized=True)
                        if not s.is_empty: groups[bit].append(s)
                    pos=max(pos,c)
                if pos<1-1e-6:
                    s=substring(g,pos,1.0,normalized=True)
                    if not s.is_empty: groups[bit].append(s)
            else: groups[bit].append(g)
        for gi,gl in enumerate(groups):
            if gl:
                pg=shapely.transform(np.array(gl,dtype=object),proj)
                rasterize(((x,1) for x in pg), out=L[gi], transform=tf, all_touched=True)
                n+=len(gl)
    np.savez_compressed(out,L=L); return out,n
t=time.time()
with ThreadPoolExecutor(2) as ex:
    for out,n in ex.map(work,list(jobs.items())):
        print(out,n,round(time.time()-t),flush=True)
print('DONE')
