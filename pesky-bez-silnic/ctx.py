import json, numpy as np, shapely, pyogrio
from shapely.geometry import shape, mapping
from rasterio.features import rasterize
from affine import Affine
from pyproj import Transformer
RES=200; X0=2500000; YTOP=1300000+11*409600; H,W=11*2048,12*2048
tf=Affine(RES,0,X0,0,-RES,YTOP)
# country raster
r=json.load(open('dl/ctx/rg.geojson'))
ids=[]; shapes=[]
for f in r['features']:
    g=shape(f['geometry'])
    if not g.intersects(shapely.box(X0,1300000,X0+W*RES,YTOP)): continue
    ids.append(f['properties']['CNTR_ID']); shapes.append((g,len(ids)))
cn=rasterize(shapes,out_shape=(H,W),transform=tf,dtype=np.uint8)
np.save('dl/CNTR200.npy',cn); json.dump(ids,open('dl/cntr_ids.json','w'))
print(len(ids),'countries')
# land borders for display, in z4 pixel units (400 m)
b=json.load(open('dl/ctx/bn.geojson'))
lines=[]
box=shapely.box(X0,1300000,X0+W*RES,YTOP)
for f in b['features']:
    p=f['properties']
    if p['COAS_FLAG']=='T': continue
    g=shape(f['geometry'])
    if not g.intersects(box): continue
    g=g.simplify(800)
    for ls in (g.geoms if g.geom_type=='MultiLineString' else [g]):
        c=np.array(ls.coords)
        px=np.round((c[:,0]-X0)/400,1); py=np.round((YTOP-c[:,1])/400,1)
        lines.append([v for xy in zip(px.tolist(),py.tolist()) for v in xy])
json.dump(lines,open('dl/borders.json','w'),separators=(',',':'))
print(len(lines),'border lines')
# cities
CZ={'Prague':'Praha','Vienna':'Vídeň','Warsaw':'Varšava','Rome':'Řím','Athens':'Atény','Munich':'Mnichov','Copenhagen':'Kodaň','Brussels':'Brusel','Bucharest':'Bukurešť','Belgrade':'Bělehrad','Lisbon':'Lisabon','Paris':'Paříž','London':'Londýn','Milan':'Milán','Naples':'Neapol','Cologne':'Kolín nad Rýnem','Venice':'Benátky','Florence':'Florencie','Kiev':'Kyjev','Bratislava':'Bratislava','Budapest':'Budapešť','Zurich':'Curych','Geneva':'Ženeva','Thessaloniki':'Soluň','Istanbul':'Istanbul','Krakow':'Krakov','Kraków':'Krakov','Wroclaw':'Vratislav','Dresden':'Drážďany','Nuremberg':'Norimberk','Hamburg':'Hamburk','Stockholm':'Stockholm','Helsinki':'Helsinky','Oslo':'Oslo','Riga':'Riga','Vilnius':'Vilnius','Tallinn':'Tallinn','Sofia':'Sofie','Zagreb':'Záhřeb','Ljubljana':'Lublaň','Sarajevo':'Sarajevo','Skopje':'Skopje','Tirana':'Tirana','Podgorica':'Podgorica','Chisinau':'Kišiněv','Minsk':'Minsk','Dublin':'Dublin','Edinburgh':'Edinburgh','Madrid':'Madrid','Barcelona':'Barcelona','Seville':'Sevilla','Valencia':'Valencie','Porto':'Porto','Marseille':'Marseille','Lyon':'Lyon','Amsterdam':'Amsterdam','Berlin':'Berlín','Brno':'Brno','Ostrava':'Ostrava','Linz':'Linec','Graz':'Štýrský Hradec','Salzburg':'Salcburk','Ankara':'Ankara','Izmir':'Izmir','Reykjavík':'Reykjavík','Bern':'Bern','Luxembourg':'Lucemburk','Valletta':'Valletta','Nicosia':'Nikósie','Gothenburg':'Göteborg','Trondheim':'Trondheim','Tromsø':'Tromsø','Bergen':'Bergen','Luleå':'Luleå','Oulu':'Oulu','Rovaniemi':'Rovaniemi','Pristina':'Priština','Cluj-Napoca':'Kluž','Lviv':'Lvov','Gdansk':'Gdaňsk','Poznan':'Poznaň','Frankfurt':'Frankfurt','Stuttgart':'Stuttgart','Ceske Budejovice':'České Budějovice','Passau':'Pasov'}
import pyogrio
t=pyogrio.read_arrow if False else None
from pyogrio import read_info
import pyarrow as pa
meta,tab=pyogrio.raw.read_arrow('dl/ctx/ne_10m_populated_places_simple.shp',columns=['name','pop_max','adm0cap','scalerank','featurecla'])
geom=shapely.from_wkb(tab.column('wkb_geometry' if 'wkb_geometry' in tab.column_names else tab.column_names[-1]).to_numpy(zero_copy_only=False))
names=tab.column('name').to_pylist(); popm=tab.column('pop_max').to_pylist(); cap=tab.column('adm0cap').to_pylist(); sr=tab.column('scalerank').to_pylist()
trf=Transformer.from_crs(4326,3035,always_xy=True)
out=[]
for g,n,pm,c,s in zip(geom,names,popm,cap,sr):
    x,y=trf.transform(g.x,g.y)
    px=(x-X0)/400; py=(YTOP-y)/400
    if not (0<=px<W/2 and 0<=py<H/2): continue
    if not (c==1 or pm>=600000 or n in CZ): continue
    if not (-25<g.x<45 and 34<g.y<72): continue
    tier=1 if (c==1 or pm>=2500000) else 2
    out.append([CZ.get(n,n),round(px,1),round(py,1),tier])
json.dump(out,open('dl/cities.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out),'cities')
