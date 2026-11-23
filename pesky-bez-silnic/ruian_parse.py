import glob, csv, numpy as np, pickle
rows=[]
for f in sorted(glob.glob('dl/ruian/adr/CSV/*.csv')):
    with open(f,encoding='cp1250',newline='') as fh:
        r=csv.reader(fh,delimiter=';'); next(r)
        for x in r:
            if not x[16] or not x[17]: continue
            rows.append((int(x[0]),x[2],x[8],x[10],x[11],x[12],float(x[16]),float(x[17])))
print(len(rows))
adm=np.array([r[0] for r in rows],np.int64)
Y=np.array([r[6] for r in rows]); X=np.array([r[7] for r in rows])
typ=np.array([1 if r[4]=='č.p.' else 2 for r in rows],np.uint8)
obec=[r[1] for r in rows]; cast=[r[2] for r in rows]; ulice=[r[3] for r in rows]; cd=[r[5] for r in rows]
pickle.dump({'adm':adm,'Y':Y,'X':X,'typ':typ,'obec':obec,'cast':cast,'ulice':ulice,'cd':cd},open('dl/ruian/adr.pkl','wb'))
print('cp',int((typ==1).sum()),'cev',int((typ==2).sum()))
