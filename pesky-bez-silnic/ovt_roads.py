import duckdb, time, pandas as pd
df=pd.read_pickle('dl/ovt_meta.pkl')
k=['file_name','row_group_id']
p=df.pivot_table(index=k,columns='path_in_schema',values='stats_min',aggfunc='first')
q=df.pivot_table(index=k,columns='path_in_schema',values='stats_max',aggfunc='first')
m=(q['bbox, xmax'].astype(float)>-25)&(p['bbox, xmin'].astype(float)<45)&(q['bbox, ymax'].astype(float)>34)&(p['bbox, ymin'].astype(float)<72)
files=sorted(set(i[0] for i in m[m].index))
print(len(files),'files', flush=True)
con=duckdb.connect()
con.execute('LOAD httpfs;')
con.execute("SET http_proxy='127.0.0.1:36463'")
con.execute("SET ca_cert_file='/root/.ccr/ca-bundle.crt'")
con.execute("SET threads=6"); con.execute("SET memory_limit='3GB'"); con.execute("SET preserve_insertion_order=false")
con.execute("SET http_retries=8")
t=time.time()
for n,u in enumerate(files):
    out=f'dl/roads/r_{n:03d}.parquet'
    import os
    if os.path.exists(out): continue
    con.execute(f"""COPY (
      SELECT subtype, class, road_flags, rail_flags, geometry
      FROM read_parquet('{u}')
      WHERE bbox.xmax > -25 AND bbox.xmin < 45 AND bbox.ymax > 34 AND bbox.ymin < 72
        AND ((subtype='road' AND class IN ('motorway','trunk','primary','secondary','tertiary'))
          OR (subtype='rail' AND class IN ('standard_gauge','narrow_gauge')))
    ) TO '{out}.tmp' (FORMAT parquet)""")
    os.rename(out+'.tmp', out)
    print(n, round(time.time()-t), flush=True)
print('DONE', flush=True)
