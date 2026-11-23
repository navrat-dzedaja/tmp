import re
s=open('code/page.html').read()
s=s.replace('/*LEAFLETCSS*/',open('dl/leaflet_inline.css').read())
s=s.replace('/*PLANNERHTML*/',open('code/planner_html.html').read()).replace('/*SAMOTYHTML*/',open('code/samoty_html.html').read())
strip=lambda t:re.sub(r"\n(if|  if)\(typeof module!=='undefined'\).*","",t)
pj=open('code/planner.js').read().replace('/*LAEA*/',strip(open('code/laea.js').read())).replace('/*CORE*/',strip(open('code/route_core.js').read()))
assert 'module.exports' not in pj
s=s+'\n<script>\n'+pj+'\n</script>\n<script>\n'+open('code/samoty.js').read()+'\n</script>\n'
open('site/index.html','w').write(s)
open('site/_test.html','w').write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}img{max-width:100%}</style></head><body>'+s+'</body></html>')
print(len(s))
