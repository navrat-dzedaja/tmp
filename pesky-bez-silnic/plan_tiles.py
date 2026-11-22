import json, base64, io, glob, numpy as np, os
from PIL import Image
from scipy import ndimage
W=8192; H=6144; TX0=18; TY0=25
# --- CLC window crop at 100 m (tiles i 4..6, j 3..4)
d=json.load(open('dl/legend.json'))
codes=[]; cols=[]
for L in d['layers']:
    if L['layerId']==1:
        for e in L['legend']:
            im=Image.open(io.BytesIO(base64.b64decode(e['imageData']))).convert('RGB'); w,h=im.size
            r,g,b=im.getpixel((w//2,h//2)); codes.append(int(e['label'].split(':')[0])); cols.append((r<<16)|(g<<8)|b)
CODES=sorted(c for c in codes if c!=999)          # index 1..44
idx_of={c:i+1 for i,c in enumerate(CODES)}; idx_of[999]=0
order=np.argsort(cols); keys=np.array(cols)[order]; vals=np.array([idx_of[c] for c in np.array(codes)[order]],np.uint8)
mos=np.zeros((2*4096,3*4096),np.uint8)
for a,i in enumerate(range(4,7)):
    for b,j in enumerate((4,3)):     # top row = j 4
        im=np.asarray(Image.open(f'dl/clc/t_{i}_{j}.png').convert('RGB')).astype(np.uint32)
        p=(im[...,0]<<16)|(im[...,1]<<8)|im[...,2]
        k=np.clip(np.searchsorted(keys,p),0,len(keys)-1); c=vals[k]; c[keys[k]!=p]=0
        mos[b*4096:(b+1)*4096, a*4096:(a+1)*4096]=c
lc=mos[1024:1024+H, 2048:2048+W].copy(); del mos
print('clc', np.bincount(lc.ravel(),minlength=45)[:5])
# --- buildings
cnt=np.zeros((H,W),np.uint32)
for f in glob.glob('dl/bld/*.npy'): cnt+=np.load(f)
bp=cnt>0
print('building cells', int(bp.sum()), 'buildings', int(cnt.sum()))
dist=ndimage.distance_transform_edt(~bp)*100.0
B=np.minimum(255,np.round(dist/10)).astype(np.uint8); del dist
# --- roads
G=np.zeros((H,W),np.uint8); BR=np.zeros((H,W),bool)
for f in glob.glob('dl/wroads/*.npz'):
    L=np.load(f)['L']
    for b in range(8): G|=(L[b]>0).astype(np.uint8)<<b
    BR|=L[8]>0
R=lc|(BR.astype(np.uint8)<<6)|(bp.astype(np.uint8)<<7)
os.makedirs('site/p',exist_ok=True); tot=0
for ty in range(H//1024):
    for tx in range(W//1024):
        sl=(slice(ty*1024,(ty+1)*1024),slice(tx*1024,(tx+1)*1024))
        im=np.dstack([R[sl],G[sl],B[sl]])
        fn=f'site/p/{TX0+tx}_{TY0+ty}.png'
        Image.fromarray(im,'RGB').save(fn,optimize=True); tot+=os.path.getsize(fn)
print('tiles MB', tot/1e6)
json.dump({'codes':CODES,'tx0':TX0,'ty0':TY0,'nx':W//1024,'ny':H//1024},open('dl/plan_meta.json','w'))
np.save('dl/plan_R.npy',R); np.save('dl/plan_G.npy',G); np.save('dl/plan_B.npy',B)
