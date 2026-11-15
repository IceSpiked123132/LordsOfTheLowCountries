# Builds the map shapes and writes them into the game template.
import json, sys, re, shapely
from shapely.geometry import shape, box, Point, MultiPoint, LineString, Polygon
from shapely.ops import unary_union
G, TPL, OUT = sys.argv[1:4]
def load(f): return json.load(open(f"{G}/{f}.geojson"))['features']
P = lambda c: shapely.transform(c, lambda a: a * [150, -220] + [(-4.1*150+20), 53.4*220])
BIG = box(-300, -400, 800, 1000)
GEO = box(1.5, 48.5, 9.6, 55.5)
adm1 = load('adm1')
land = unary_union([shape(f['geometry']).buffer(0).intersection(GEO) for f in load('ne_10m_land') if shape(f['geometry']).intersects(GEO)])
lakes = [shape(f['geometry']) for f in load('ne_10m_lakes') if f['properties'].get('name') in ('IJsselmeer','Lauwerszee')]
flevo = [shape(f['geometry']) for f in adm1 if f['properties'].get('name')=='Flevoland' and f['properties'].get('admin')=='Netherlands']
water = unary_union(lakes + flevo)
land = P(land.difference(water)).intersection(BIG)
nl = unary_union([shape(f['geometry']).buffer(0).intersection(GEO) for f in load('ne_10m_admin_0_countries') if f['properties']['ADMIN']=='Netherlands'])
be = unary_union([shape(f['geometry']).buffer(0) for f in adm1 if f['properties'].get('admin')=='Belgium'
                  and f['properties']['name'] in ('Antwerp','Limburg','Brussels','Flemish Brabant','Walloon Brabant')])
play = P(unary_union([nl, be]).difference(water)).buffer(0.8).buffer(-0.8).intersection(land.buffer(0.3))
rivers = P(unary_union([shape(f['geometry']).intersection(GEO) for f in load('ne_10m_rivers_lake_centerlines')
    if f['properties'].get('name') in ('IJssel','Nederrijn','Lek','Rhine','Waal','Schelde','Maas') and shape(f['geometry']).intersects(GEO)])).intersection(BIG)
src = open(TPL).read()
seeds = {m[0]: (float(m[1]), float(m[2])) for m in re.findall(r'(\w+):\s*\{ name: "[^"]+",\s*owner: "\w+",\s*x: (\d+),\s*y: (\d+)', src)}
ids = list(seeds); assert len(ids) == 20, len(ids)
vor = shapely.voronoi_polygons(MultiPoint([seeds[i] for i in ids]), extend_to=BIG.buffer(300))
cells = {}
for poly in vor.geoms:
    for i in ids:
        if poly.contains(Point(seeds[i])): cells[i] = poly.intersection(play).buffer(0)
def path(g, closed=True, tol=0.4):
    g = g.simplify(tol); out = []
    def walk(p):
        if p.geom_type == 'Polygon':
            if p.area < 2: return
            for r in [p.exterior, *[i for i in p.interiors if Polygon(i).area > 4]]:
                out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in r.coords[:-1]) + "Z")
        elif p.geom_type == 'LineString':
            out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in p.coords))
        elif hasattr(p, 'geoms'):
            for q in p.geoms: walk(q)
    walk(g); return "".join(out)
borders = []
for a in range(len(ids)):
    for b in range(a+1, len(ids)):
        A, Bc = ids[a], ids[b]
        line = cells[A].boundary.intersection(cells[Bc].buffer(0.6))
        L = 0 if line.is_empty else line.length
        if L < 15: continue
        near = line.intersection(rivers.buffer(7)).length
        cross = LineString([seeds[A], seeds[Bc]]).intersects(rivers)
        river = (near / L > 0.4) or (cross and near / L > 0.15)
        borders.append((A, Bc, river)); print(A, Bc, round(L), 'RIVER' if river else '')
x0, y0, x1, y1 = play.bounds
vb = f"{x0-8:.0f} {y0-8:.0f} {x1-x0+16:.0f} {y1-y0+16:.0f}"
print("viewBox", vb, "borders", len(borders))
rows = ",\n".join('  ["%s","%s"%s]' % (a, b, ', true' if r else '') for a, b, r in borders)
subs = {"__VIEWBOX__": vb, "__BORDERS__": rows,
        "__TERRITORIES__": json.dumps({i: path(cells[i]) for i in ids}),
        "__MAP_SHAPES__": json.dumps({"land": path(land, tol=0.6), "rivers": path(rivers, tol=0.5)})}
for k, v in subs.items():
    assert src.count(k) == 1, k; src = src.replace(k, v)
open(OUT, 'w').write(src)
