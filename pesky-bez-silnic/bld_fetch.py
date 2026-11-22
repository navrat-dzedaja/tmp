import sys; sys.path.insert(0,'code')
import pyarrow.parquet as pq, pickle, time, numpy as np, os
from concurrent.futures import ThreadPoolExecutor
from httpfile import HTTPRangeFile
from pyproj import Transformer
X0W=4343200; YTW=3245600; W=8192; H=6144; RES=100
LON0,LON1,LAT0,LAT1=10.29,22.24,46.23,52.32
tr=Transformer.from_crs(4326,3035,always_xy=True)
meta=pickle.load(open('dl/bld_meta.pkl','rb'))
jobs=[]
for u,sz,rgs in meta:
    sel=[r for r,nr,x0,x1,y0,y1,cs,tb in rgs if x1>LON0 and x0<LON1 and y1>LAT0 and y0<LAT1]
    if sel: jobs.append((u,sz,sel))
os.makedirs('dl/bld',exist_ok=True)
def work(job):
    u,sz,sel=job; out=f"dl/bld/{u.split('/')[-1][:10]}.npy"
    if os.path.exists(out): return out,0
    f=HTTPRangeFile(u,size=sz); pf=pq.ParquetFile(f,pre_buffer=True)
    cnt=np.zeros((H,W),np.uint16); n=0
    for i in range(0,len(sel),20):
        tb=pf.read_row_groups(sel[i:i+20],columns=['bbox'])
        b=tb.column('bbox').combine_chunks()
        x0=b.field('xmin').to_numpy(); x1=b.field('xmax').to_numpy(); y0=b.field('ymin').to_numpy(); y1=b.field('ymax').to_numpy()
        lo=(x0+x1)/2; la=(y0+y1)/2
        m=(lo>LON0)&(lo<LON1)&(la>LAT0)&(la<LAT1)
        X,Y=tr.transform(lo[m],la[m])
        c=((np.asarray(X)-X0W)//RES).astype(np.int64); r=((YTW-np.asarray(Y))//RES).astype(np.int64)
        k=(c>=0)&(c<W)&(r>=0)&(r<H)
        np.add.at(cnt,(r[k],c[k]),1); n+=int(k.sum())
    np.save(out,cnt); return out,n
t=time.time(); tot=0
with ThreadPoolExecutor(3) as ex:
    for out,n in ex.map(work,jobs):
        tot+=n; print(out,n,round(time.time()-t),flush=True)
print('DONE',tot)
