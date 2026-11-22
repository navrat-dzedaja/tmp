import json, numpy as np, shapely, pyogrio
from pyproj import Transformer
X0=2500000; YTOP=1300000+11*409600
trf=Transformer.from_crs(4326,3035,always_xy=True)
meta,tab=pyogrio.raw.read_arrow('dl/ctx/ne_10m_populated_places_simple.shp',columns=['name','scalerank','pop_max'])
geom=shapely.from_wkb(tab.column(tab.column_names[-1]).to_numpy(zero_copy_only=False))
names=tab.column('name').to_pylist(); sr=np.array(tab.column('scalerank').to_pylist())
lon=np.array([g.x for g in geom]); lat=np.array([g.y for g in geom])
ok=(lon>-30)&(lon<50)&(lat>33)&(lat<72)&(sr<=9)
x,y=trf.transform(lon[ok],lat[ok]); px=(np.array(x)-X0)/400; py=(YTOP-np.array(y))/400
nm=[n for n,o in zip(names,ok) if o]
CZ=dict(Prague='Praha',Vienna='Vídeň',Warsaw='Varšava',Rome='Řím',Athens='Atény',Munich='Mnichov',Copenhagen='Kodaň',Brussels='Brusel',Bucharest='Bukurešť',Belgrade='Bělehrad',Lisbon='Lisabon',Paris='Paříž',London='Londýn',Milan='Milán',Naples='Neapol',Venice='Benátky',Florence='Florencie',Budapest='Budapešť',Zurich='Curych',Geneva='Ženeva',Thessaloniki='Soluň',Krakow='Krakov',Wroclaw='Vratislav',Dresden='Drážďany',Nuremberg='Norimberk',Hamburg='Hamburk',Helsinki='Helsinky',Sofia='Sofie',Zagreb='Záhřeb',Ljubljana='Lublaň',Chisinau='Kišiněv',Valencia='Valencie',Berlin='Berlín',Linz='Linec',Graz='Štýrský Hradec',Salzburg='Salcburk',Nicosia='Nikósie',Gothenburg='Göteborg',Pristina='Priština',Lviv='Lvov',Gdansk='Gdaňsk',Poznan='Poznaň',Luxembourg='Lucemburk',Passau='Pasov',Regensburg='Řezno',Innsbruck='Innsbruck',Plzen='Plzeň')
def nearest(pt):
    d=(px-pt[0])**2+(py-pt[1])**2; k=int(np.argmin(d)); n=nm[k]; return CZ.get(n,n)
PAL=10
out={'variants':{}}
for v in ('v1','v2','v3'):
    d=json.load(open(f'dl/res_{v}.json'))
    comps=d['comps']; boxes=[]
    for c in comps:
        t=np.array(c['trail']).reshape(-1,2)
        mid=t[len(t)//2] if len(t) else [(c['bbox'][0]+c['bbox'][2])/2,(c['bbox'][1]+c['bbox'][3])/2]
        c['near']=nearest(mid)
        # greedy colouring: avoid colours of comps whose (padded) bbox overlaps
        b=c['bbox']; pad=6
        used={o['col'] for o,ob in zip(comps,boxes) if not (ob[2]+pad<b[0] or b[2]+pad<ob[0] or ob[3]+pad<b[1] or b[3]+pad<ob[1])}
        cnt={k:0 for k in range(PAL)}
        for o in comps[:len(boxes)]: cnt[o['col']]+=1
        free=[k for k in range(PAL) if k not in used] or list(range(PAL))
        c['col']=min(free,key=lambda k:(cnt[k],k))
        boxes.append(b)
    out['variants'][v]=d
out['borders']=json.load(open('dl/borders.json'))
out['cities']=json.load(open('dl/cities.json'))
out['grid']={'w':12288,'h':11264,'tile':1024,'maxNative':4,'res_m':400}
json.dump(out,open('site/data.json','w'),ensure_ascii=False,separators=(',',':'))
import os; print(os.path.getsize('site/data.json')//1000,'KB')
for v in ('v1','v2','v3'):
    print(v,[(c['r'],c['near'],c['col']) for c in out['variants'][v]['comps'][:10]])
