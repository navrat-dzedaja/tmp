import sys; sys.path.insert(0,'code')
import pyarrow.parquet as pq, pyarrow as pa, numpy as np, time, pickle
from concurrent.futures import ThreadPoolExecutor
from httpfile import HTTPRangeFile
LON0,LON1,LAT0,LAT1=11.9,19.0,48.4,51.2
urls=[l.strip() for l in open('code/water_urls.txt')]
def meta(u):
    f=HTTPRangeFile(u); pf=pq.ParquetFile(f); md=pf.metadata
    names=[md.schema.column(i).path for i in range(md.num_columns)]
    ix={n:names.index(n) for n in ('bbox.xmin','bbox.xmax','bbox.ymin','bbox.ymax')}
    sel=[]
    for r in range(md.num_row_groups):
        rg=md.row_group(r); s={n:rg.column(i).statistics for n,i in ix.items()}
        if s['bbox.xmax'].max>LON0 and s['bbox.xmin'].min<LON1 and s['bbox.ymax'].max>LAT0 and s['bbox.ymin'].min<LAT1: sel.append(r)
    return u,f.size,sel
t=time.time()
with ThreadPoolExecutor(4) as ex: M=list(ex.map(meta,urls))
jobs=[(u,s,sel) for u,s,sel in M if sel]
print('files',len(jobs),'rowgroups',sum(len(s) for _,_,s in jobs),round(time.time()-t),flush=True)
def work(j):
    u,sz,sel=j; pf=pq.ParquetFile(HTTPRangeFile(u,size=sz),pre_buffer=True); out=[]
    for i in range(0,len(sel),10):
        tb=pf.read_row_groups(sel[i:i+10],columns=['names.primary','subtype','class','is_intermittent','geometry','bbox'])
        b=tb.column('bbox').combine_chunks()
        m=(b.field('xmax').to_numpy()>LON0)&(b.field('xmin').to_numpy()<LON1)&(b.field('ymax').to_numpy()>LAT0)&(b.field('ymin').to_numpy()<LAT1)
        tb=tb.filter(pa.array(m))
        out.append(tb.drop_columns(['bbox']))
    return pa.concat_tables(out) if out else None
with ThreadPoolExecutor(3) as ex: parts=[p for p in ex.map(work,jobs) if p is not None]
tb=pa.concat_tables(parts)
pq.write_table(tb,'dl/water_cz.parquet')
print('rows',tb.num_rows,round(time.time()-t))
import collections
print(collections.Counter(zip(tb.column('subtype').to_pylist(),tb.column('class').to_pylist())).most_common(25))
