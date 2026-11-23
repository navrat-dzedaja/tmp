import numpy as np, pickle
from scipy import ndimage
from scipy.spatial import cKDTree
d=pickle.load(open('dl/ruian/adr.pkl','rb'))
Y,X=d['Y'],d['X']; N=len(Y)
# 50 m grid, link points closer than ~150 m
C=50.0; y0,x0=Y.min()-500,X.min()-500
gi=((Y-y0)//C).astype(np.int64); gj=((X-x0)//C).astype(np.int64)
H,W=gj.max()+20, gi.max()+20
grid=np.zeros((H,W),bool); grid[gj,gi]=True
st=ndimage.generate_binary_structure(2,1)
dil=ndimage.binary_dilation(grid,structure=np.ones((3,3),bool),iterations=1)   # ~75 m each side
lab,nl=ndimage.label(dil,structure=np.ones((3,3)))
L=lab[gj,gi]
size=np.bincount(L,minlength=nl+1)
print('clusters',nl,'singletons',int((size==1).sum()))
pickle.dump({'L':L,'size':size},open('dl/ruian/clusters.pkl','wb'))
pts=np.column_stack([Y,X]); tree=cKDTree(pts)
small=np.nonzero((size[L]<=6))[0]
K=9
dd,ii=tree.query(pts[small],k=K,distance_upper_bound=6000)
iso=np.full(len(small),6000.0)
for k in range(1,K):
    other=(ii[:,k]<N)
    lk=np.where(other,L[np.minimum(ii[:,k],N-1)],-1)
    m=other&(lk!=L[small])&(iso==6000.0)
    iso[m]=dd[m,k]
# cluster isolation = min over members
ciso=np.full(nl+1,6000.0)
np.minimum.at(ciso,L[small],iso)
cand=np.nonzero((size<=6)&(ciso>=400)&(size>0))[0]; cand=cand[cand>0]
print('candidate clusters (iso>=400m, <=6 addresses):',len(cand))
for t in (500,800,1000,1500,2000):
    print(t, int((ciso[cand]>=t).sum()))
np.save('dl/ruian/ciso.npy',ciso)
