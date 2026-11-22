import numpy as np, os, json, itertools, gc
from PIL import Image
OUT='site'
T=1024
def dmin_nonzero(a):
    b=np.where(a==0,np.uint16(999),a.astype(np.uint16))
    m=np.minimum(np.minimum(b[0::2,0::2],b[0::2,1::2]),np.minimum(b[1::2,0::2],b[1::2,1::2]))
    m[m==999]=0; return m.astype(np.uint8)
def dmode(a):
    q=[a[0::2,0::2],a[0::2,1::2],a[1::2,0::2],a[1::2,1::2]]
    best=None; bk=None
    for i in range(4):
        cnt=sum((q[i]==q[j]).astype(np.uint16) for j in range(4))
        pri=np.where(q[i]==0,np.uint16(0),np.uint16(511)-q[i].astype(np.uint16))  # prefer nonzero & low rank on ties
        key=cnt*np.uint16(1024)+pri
        if best is None: best=q[i].copy(); bk=key
        else:
            m=key>bk; best[m]=q[i][m]; bk=np.maximum(bk,key)
    return best
def dor(a): return a[0::2,0::2]|a[0::2,1::2]|a[1::2,0::2]|a[1::2,1::2]
# base category (display)
C=np.load('dl/C200.npy'); cn=np.load('dl/CNTR200.npy')
remap=np.array([0,0,1,2,3,4,5,6,7,8],np.uint8)
D=remap[C]; D[(C==0)&(cn>0)]=9
del C,cn; gc.collect()
base=dmode(D); del D; gc.collect()
rb=np.zeros_like(base)
for bit,k in ((4,'big'),(5,'sec'),(6,'tert'),(7,'rail')):
    r=dor(np.load(f'dl/road_{k}200.npy')); rb|=(r>0).astype(np.uint8)<<bit; del r
base|=rb; del rb; gc.collect()
ranks=[dmin_nonzero(np.load(f'dl/rank_{v}.npy')) for v in ('v1','v2','v3')]
gc.collect()
levels={4:(ranks,base)}
for z in (3,2,1,0):
    rk,bs=levels[z+1]
    nb=dmode(bs&15)|(dor(bs)&0xF0)
    levels[z]=([dmode(r) for r in rk],nb)
stats={}
for z,(rk,bs) in levels.items():
    h,w=bs.shape; nt=0; sz=0
    os.makedirs(f'{OUT}/t/{z}',exist_ok=True); os.makedirs(f'{OUT}/b/{z}',exist_ok=True)
    for ty in range((h+T-1)//T):
        for tx in range((w+T-1)//T):
            sl=(slice(ty*T,(ty+1)*T),slice(tx*T,(tx+1)*T))
            b=bs[sl]
            if not (b&15).any() and not any(r[sl].any() for r in rk): continue
            pb=np.zeros((T,T),np.uint8); pb[:b.shape[0],:b.shape[1]]=b
            pr=np.zeros((T,T,3),np.uint8)
            for i in range(3): pr[:b.shape[0],:b.shape[1],i]=rk[i][sl]
            Image.fromarray(pb,'L').save(f'{OUT}/b/{z}/{tx}_{ty}.png',optimize=True)
            Image.fromarray(pr,'RGB').save(f'{OUT}/t/{z}/{tx}_{ty}.png',optimize=True)
            nt+=1; sz+=os.path.getsize(f'{OUT}/b/{z}/{tx}_{ty}.png')+os.path.getsize(f'{OUT}/t/{z}/{tx}_{ty}.png')
    stats[z]={'shape':[h,w],'tiles':nt,'MB':round(sz/1e6,1)}
    print(z,stats[z],flush=True)
json.dump(stats,open('dl/tile_stats.json','w'))
