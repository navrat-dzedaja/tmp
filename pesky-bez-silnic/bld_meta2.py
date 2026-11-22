import sys; sys.path.insert(0,'code')
import pyarrow.parquet as pq, pickle, time
from concurrent.futures import ThreadPoolExecutor
from httpfile import HTTPRangeFile
urls=[l.strip() for l in open('code/bld_urls.txt')]
def meta(u):
    f=HTTPRangeFile(u); md=pq.ParquetFile(f).metadata
    names=[md.schema.column(i).path for i in range(md.num_columns)]
    idx={n:names.index(n) for n in ('bbox.xmin','bbox.xmax','bbox.ymin','bbox.ymax')}
    rgs=[]
    for r in range(md.num_row_groups):
        rg=md.row_group(r)
        st={n:rg.column(i).statistics for n,i in idx.items()}
        cs={n:rg.column(i).total_compressed_size for n,i in idx.items()}
        rgs.append((r,rg.num_rows,st['bbox.xmin'].min,st['bbox.xmax'].max,st['bbox.ymin'].min,st['bbox.ymax'].max,sum(cs.values()),rg.total_byte_size))
    return u,f.size,rgs
t=time.time(); out=[]
with ThreadPoolExecutor(4) as ex:
    for i,r in enumerate(ex.map(meta,urls)):
        out.append(r)
        if i%64==0: print(i,round(time.time()-t),flush=True)
pickle.dump(out,open('dl/bld_meta.pkl','wb'))
n=0;rows=0;by=0;files=set()
for u,sz,rgs in out:
    for r,nr,x0,x1,y0,y1,cs,tb in rgs:
        if x1>10.29 and x0<22.24 and y1>46.23 and y0<52.32: n+=1; rows+=nr; by+=cs; files.add(u)
print('rowgroups',n,'rows',rows/1e6,'M bbox GB',by/1e9,'files',len(files))
