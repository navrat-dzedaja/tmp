import pyarrow.parquet as pq, numpy as np, shapely, glob, sys, time
from shapely.ops import substring
from pyproj import Transformer
from rasterio.features import rasterize
from affine import Affine
RES=200; X0=2500000; YTOP=1300000+11*409600
H,W=11*2048,12*2048
tf=Affine(RES,0,X0,0,-RES,YTOP)
tr=Transformer.from_crs(4326,3035,always_xy=True)
def proj(c):
    x,y=tr.transform(c[:,0],c[:,1]); return np.column_stack([x,y])
out={k:np.zeros((H,W),np.uint8) for k in ('big','sec','tert','rail')}
stats={k:0 for k in ('big','sec','tert','rail','drop_full','partial')}
SKIP={'is_tunnel','is_bridge'}
RAILDEAD={'is_abandoned','is_disused'}
files=sorted(glob.glob('dl/roads/r_*.parquet'))
t=time.time()
for f in files:
    tb=pq.read_table(f)
    sub=tb.column('subtype').to_pylist(); cls=tb.column('class').to_pylist()
    rf=tb.column('road_flags').to_pylist(); lf=tb.column('rail_flags').to_pylist()
    geo=shapely.from_wkb(tb.column('geometry').combine_chunks().to_numpy(zero_copy_only=False))
    groups={'big':[], 'sec':[], 'tert':[], 'rail':[]}
    for k in range(len(sub)):
        g=geo[k]
        if g is None: continue
        if sub[k]=='rail': grp='rail'; flags=lf[k]
        else: grp={'tertiary':'tert','secondary':'sec'}.get(cls[k],'big'); flags=rf[k]
        if flags:
            cut=[]; full=False
            for fl in flags:
                vals=set(fl['values'] or [])
                if (vals & SKIP) or (grp=='rail' and vals & RAILDEAD):
                    if fl['between'] is None: full=True; break
                    cut.append(tuple(fl['between']))
            if full: stats['drop_full']+=1; continue
            if cut:
                cut.sort(); keep=[]; pos=0.0
                for a,b in cut:
                    if a>pos: keep.append((pos,a))
                    pos=max(pos,b)
                if pos<1: keep.append((pos,1.0))
                stats['partial']+=1
                for a,b in keep:
                    if b-a>1e-6:
                        s=substring(g,a,b,normalized=True)
                        if not s.is_empty: groups[grp].append(s)
                continue
        groups[grp].append(g)
    for grp,gl in groups.items():
        if not gl: continue
        pg=shapely.transform(np.array(gl,dtype=object),proj)
        stats[grp]+=len(pg)
        rasterize(((g,1) for g in pg), out=out[grp], transform=tf, all_touched=True)
    print(f, round(time.time()-t), stats, flush=True)
for k,a in out.items(): np.save(f'dl/road_{k}200.npy',a)
print('DONE',stats)
