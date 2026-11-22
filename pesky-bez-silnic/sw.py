import ctypes, numpy as np, os
_l=ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)),'libsweep.so'))
P=ctypes.c_void_p; I64=ctypes.c_int64; I32=ctypes.c_int32
_l.sweep.argtypes=[P,I64,I64,P,I64,P]
_l.first_idx.argtypes=[P,I64,I32,P]
_l.argmax_label.argtypes=[P,P,I64,I32,P,P]
_l.trace.argtypes=[P,P,I64,I64,I64,P,I64]; _l.trace.restype=I64
def ptr(a): return a.ctypes.data_as(P)
def sweep(lab,src,dist=None):
    assert lab.dtype==np.int32 and lab.flags.c_contiguous
    H,W=lab.shape
    if dist is None: dist=np.empty((H,W),np.uint32)
    s=np.ascontiguousarray(src,np.int64)
    _l.sweep(ptr(lab),H,W,ptr(s),len(s),ptr(dist)); return dist
def first_idx(lab,nlab):
    f=np.empty(nlab+1,np.int64); _l.first_idx(ptr(lab),lab.size,nlab,ptr(f)); return f
def argmax_label(lab,dist,nlab):
    b=np.empty(nlab+1,np.int64); d=np.empty(nlab+1,np.uint32); _l.argmax_label(ptr(lab),ptr(dist),lab.size,nlab,ptr(b),ptr(d)); return b,d
def trace(lab,dist,start,maxn=2_000_000):
    H,W=lab.shape; o=np.empty(maxn,np.int64); n=_l.trace(ptr(lab),ptr(dist),H,W,int(start),ptr(o),maxn); return o[:n]
