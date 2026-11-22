#!/bin/bash
# usage: dl_clc.sh i j  -> tile column i (x), row j (y)
i=$1; j=$2
X0=$((2500000 + i*409600)); Y0=$((1300000 + j*409600))
X1=$((X0+409600)); Y1=$((Y0+409600))
out=dl/clc/t_${i}_${j}.png
[ -s "$out" ] && exit 0
for a in 1 2 3 4 5; do
  curl -s --max-time 120 -o "$out.tmp" "https://image.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_LAEA/MapServer/export?bbox=$X0,$Y0,$X1,$Y1&bboxSR=3035&imageSR=3035&size=4096,4096&dpi=96&format=png32&transparent=false&layers=show:1&f=image"
  if file "$out.tmp" | grep -q "PNG image data, 4096 x 4096"; then mv "$out.tmp" "$out"; exit 0; fi
  sleep $((a*5))
done
echo "FAILED $i $j"
