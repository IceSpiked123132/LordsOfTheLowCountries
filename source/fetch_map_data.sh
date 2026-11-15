#!/bin/sh
# Downloads the Natural Earth map data that build.py needs (about 70 MB).
# Usage: sh source/fetch_map_data.sh map-data
set -e
DIR="${1:-map-data}"
mkdir -p "$DIR"
BASE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_10m_land ne_10m_lakes ne_10m_rivers_lake_centerlines ne_10m_admin_0_countries; do
  curl -sSfL -o "$DIR/$f.geojson" "$BASE/$f.geojson"
done
curl -sSfL -o "$DIR/adm1.geojson" "$BASE/ne_10m_admin_1_states_provinces.geojson"
echo "Map data saved in $DIR"
