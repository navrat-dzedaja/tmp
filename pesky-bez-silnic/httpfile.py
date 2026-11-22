import urllib.request, io, time
class HTTPRangeFile(io.RawIOBase):
    def __init__(self,url,size=None,tail=1<<20):
        self.url=url; self.pos=0
        if size is None:
            r=self._req('HEAD'); size=int(r.headers['Content-Length'])
        self.size=size; self.cache={}
        # prefetch tail (footer)
        t0=max(0,size-tail); self.tail_start=t0; self.tail=self._get(t0,size-1)
    def _req(self,method,hdr=None):
        for a in range(8):
            try:
                rq=urllib.request.Request(self.url,method=method,headers=hdr or {})
                return urllib.request.urlopen(rq,timeout=120)
            except Exception as e:
                if a==7: raise
                time.sleep(1+a*2)
    def _get(self,a,b):
        for k in range(8):
            try:
                return self._req('GET',{'Range':f'bytes={a}-{b}'}).read()
            except Exception:
                if k==7: raise
                time.sleep(1+k*2)
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self,off,whence=0):
        self.pos = off if whence==0 else self.pos+off if whence==1 else self.size+off
        return self.pos
    def read(self,n=-1):
        if n<0: n=self.size-self.pos
        a=self.pos; b=min(self.size,a+n)
        if a>=self.tail_start: d=self.tail[a-self.tail_start:b-self.tail_start]
        else: d=self._get(a,b-1)
        self.pos=b; return d
    def readinto(self,buf):
        d=self.read(len(buf)); buf[:len(d)]=d; return len(d)
