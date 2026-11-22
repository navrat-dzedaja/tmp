#include <stdint.h>
#include <stdlib.h>
#include <string.h>
/* Multi-source Dijkstra on a raster (Dial's bucket queue).
   Moves: orthogonal cost 5, diagonal cost 7 (only when both orthogonal
   neighbours are passable: no corner cutting across barriers).
   lab[p] != 0 means passable. dist = 0xFFFFFFFF where unreached. */
typedef struct { int64_t *a; int64_t n, cap; } vec;
static void push(vec* v, int64_t x){
  if(v->n==v->cap){ v->cap = v->cap ? v->cap*2 : 4096; v->a = realloc(v->a, v->cap*sizeof(int64_t)); }
  v->a[v->n++] = x;
}
#define NB 8
#define INF 0xFFFFFFFFu
void sweep(const int32_t* lab, int64_t H, int64_t W, const int64_t* src, int64_t nsrc, uint32_t* dist){
  int64_t N=H*W;
  for(int64_t i=0;i<N;i++) dist[i]=INF;
  vec b[NB]; memset(b,0,sizeof(b));
  int64_t pending=0;
  for(int64_t k=0;k<nsrc;k++){ if(src[k]<0||lab[src[k]]==0) continue; dist[src[k]]=0; push(&b[0],src[k]); pending++; }
  uint32_t d=0;
  while(pending>0){
    vec* cur=&b[d%NB];
    for(int64_t t=0;t<cur->n;t++){
      int64_t p=cur->a[t]; pending--;
      if(dist[p]!=d) continue;
      int64_t y=p/W, x=p-y*W;
      int up = y>0 && lab[p-W];
      int dn = y<H-1 && lab[p+W];
      int lf = x>0 && lab[p-1];
      int rt = x<W-1 && lab[p+1];
      uint32_t d5=d+5, d7=d+7;
      #define RELAX(q,nd) if(nd<dist[q]){ dist[q]=nd; push(&b[(nd)%NB],q); pending++; }
      if(up){ RELAX(p-W,d5) }
      if(dn){ RELAX(p+W,d5) }
      if(lf){ RELAX(p-1,d5) }
      if(rt){ RELAX(p+1,d5) }
      if(up&&lf&&lab[p-W-1]){ RELAX(p-W-1,d7) }
      if(up&&rt&&lab[p-W+1]){ RELAX(p-W+1,d7) }
      if(dn&&lf&&lab[p+W-1]){ RELAX(p+W-1,d7) }
      if(dn&&rt&&lab[p+W+1]){ RELAX(p+W+1,d7) }
    }
    cur->n=0; d++;
  }
  for(int i=0;i<NB;i++) free(b[i].a);
}
/* first pixel index of each label (labels 1..nlab), -1 if absent */
void first_idx(const int32_t* lab, int64_t N, int32_t nlab, int64_t* first){
  for(int32_t i=0;i<=nlab;i++) first[i]=-1;
  for(int64_t p=0;p<N;p++){ int32_t L=lab[p]; if(L>0 && L<=nlab && first[L]<0) first[L]=p; }
}
/* farthest reached pixel per label */
void argmax_label(const int32_t* lab, const uint32_t* dist, int64_t N, int32_t nlab, int64_t* best, uint32_t* bestd){
  for(int32_t i=0;i<=nlab;i++){ best[i]=-1; bestd[i]=0; }
  for(int64_t p=0;p<N;p++){ int32_t L=lab[p]; if(L>0 && L<=nlab && dist[p]!=INF && (best[L]<0 || dist[p]>bestd[L])){ best[L]=p; bestd[L]=dist[p]; } }
}
/* walk downhill from start to a source; returns number of points written */
int64_t trace(const int32_t* lab, const uint32_t* dist, int64_t H, int64_t W, int64_t start, int64_t* out, int64_t maxn){
  int64_t p=start, n=0;
  if(dist[p]==INF) return 0;
  while(n<maxn){
    out[n++]=p;
    if(dist[p]==0) break;
    int64_t y=p/W, x=p-y*W; int64_t nxt=-1; uint32_t dp=dist[p];
    int up = y>0 && lab[p-W], dn = y<H-1 && lab[p+W], lf = x>0 && lab[p-1], rt = x<W-1 && lab[p+1];
    /* prefer diagonal steps for smoother lines */
    if(nxt<0 && up&&lf&&lab[p-W-1] && dist[p-W-1]+7==dp) nxt=p-W-1;
    if(nxt<0 && up&&rt&&lab[p-W+1] && dist[p-W+1]+7==dp) nxt=p-W+1;
    if(nxt<0 && dn&&lf&&lab[p+W-1] && dist[p+W-1]+7==dp) nxt=p+W-1;
    if(nxt<0 && dn&&rt&&lab[p+W+1] && dist[p+W+1]+7==dp) nxt=p+W+1;
    if(nxt<0 && up && dist[p-W]+5==dp) nxt=p-W;
    if(nxt<0 && dn && dist[p+W]+5==dp) nxt=p+W;
    if(nxt<0 && lf && dist[p-1]+5==dp) nxt=p-1;
    if(nxt<0 && rt && dist[p+1]+5==dp) nxt=p+1;
    if(nxt<0) break;
    p=nxt;
  }
  return n;
}
