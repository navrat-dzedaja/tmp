import json, base64, io, numpy as np, os, sys, itertools
from PIL import Image
d=json.load(open('dl/legend.json'))
codes=[]; cols=[]
for L in d['layers']:
    if L['layerId']==1:
        for e in L['legend']:
            im=Image.open(io.BytesIO(base64.b64decode(e['imageData']))).convert('RGB'); w,h=im.size
            r,g,b=im.getpixel((w//2,h//2)); codes.append(int(e['label'].split(':')[0])); cols.append((r<<16)|(g<<8)|b)
order=np.argsort(cols); keys=np.array(cols)[order]; vals=np.array(codes)[order]
def cat(c):
    if c==999: return 0
    if c==523: return 1
    if c in (511,512,521,522): return 2
    if c in (311,312,313): return 3
    if c in (321,322,323,324,333,334): return 4
    if c in (331,332,335): return 5
    if c in (411,412,421,423): return 6
    if c==231: return 7
    if 200<=c<300: return 8
    return 9
NC=10
catv=np.array([cat(c) for c in vals],dtype=np.uint8)
strict=np.zeros(NC,np.uint8); strict[[3,4,5,6]]=1
main=strict.copy(); main[7]=1
# LUT for mode of 4 categories (tie -> first-seen order irrelevant; prefer higher count then lower cat)
mode=np.zeros(NC**4,np.uint8)
for t in itertools.product(range(NC),repeat=4):
    cnt=np.bincount(t,minlength=NC); mode[((t[0]*NC+t[1])*NC+t[2])*NC+t[3]]=cnt.argmax()
B=2048
i,j=int(sys.argv[1]),int(sys.argv[2])
out=f'dl/c200b/{i}_{j}.npz'
if os.path.exists(out): sys.exit()
a=np.asarray(Image.open(f'dl/clc/t_{i}_{j}.png').convert('RGB')).astype(np.uint32)
p=(a[...,0]<<16)|(a[...,1]<<8)|a[...,2]
idx=np.clip(np.searchsorted(keys,p),0,len(keys)-1)
bad=keys[idx]!=p
c=catv[idx]; c[bad]=0
q=[c[0::2,0::2],c[0::2,1::2],c[1::2,0::2],c[1::2,1::2]]
S=strict[q[0]]+strict[q[1]]+strict[q[2]]+strict[q[3]]
M=main[q[0]]+main[q[1]]+main[q[2]]+main[q[3]]
k=((q[0].astype(np.int32)*NC+q[1])*NC+q[2])*NC+q[3]
C=mode[k]
np.savez(out,S=S,M=M,C=C)
