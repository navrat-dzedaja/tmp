import duckdb, time
con=duckdb.connect()
con.execute('LOAD httpfs;')
con.execute("SET http_proxy='127.0.0.1:36463'")
con.execute("SET ca_cert_file='/root/.ccr/ca-bundle.crt'")
urls=[l.strip() for l in open('code/seg_urls.txt')]
t=time.time()
lst="[" + ",".join("'"+u+"'" for u in urls) + "]"
con.execute("SET threads=16")
df=con.execute(f"""
select file_name, row_group_id, row_group_num_rows, path_in_schema, stats_min, stats_max, total_compressed_size
from parquet_metadata({lst})
where path_in_schema in ('bbox, xmin','bbox, xmax','bbox, ymin','bbox, ymax','geometry','class','subtype')
""").fetchdf()
print(time.time()-t, len(df))
df.to_pickle('dl/ovt_meta.pkl')
print(df.head(10).to_string())
