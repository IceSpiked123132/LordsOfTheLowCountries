import os
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
# The Afsluitdijk (1932) is cut out too: in 1350 the Zuiderzee was open sea
afsluitdijk = LineString([(5.035, 52.938), (5.17, 53.005), (5.33, 53.072), (5.385, 53.098)]).buffer(0.013)
# Water around 1350 that is land today. Outlines are approximate (lon, lat), drawn from
# historical maps at the scale of the game; small creeks and peat ponds are left out.
HIST_WATER = {
    # Kop van Noord-Holland: Wieringermeer (drained 1930), Amstelmeer/Balgzand (Anna Paulowna,
    # 1846) and the Zijpe (1597). Wieringen becomes an island again; the dunes from Petten to
    # Den Helder stay as a thin strip, broken by the Zijpe inlet.
    "kop": [(4.700, 52.790), (4.745, 52.790), (4.790, 52.808), (4.840, 52.800), (4.900, 52.786),
            (4.960, 52.775), (5.040, 52.772), (5.095, 52.770), (5.130, 52.790), (5.130, 52.910),
            (5.060, 52.905), (5.000, 52.888), (4.930, 52.878), (4.870, 52.880), (4.845, 52.893),
            (4.830, 52.915), (4.790, 52.965), (4.765, 52.940), (4.745, 52.900),
            (4.735, 52.860), (4.715, 52.830), (4.690, 52.800)],
    "zijpe_inlet": [(4.660, 52.800), (4.700, 52.790), (4.715, 52.820), (4.672, 52.830)],
    # The IJ: a wide arm of the Zuiderzee from Amsterdam to Spaarndam, with the Wijkermeer
    # (drained 1873, North Sea Canal 1876)
    "ij": [(5.060, 52.390), (4.990, 52.393), (4.930, 52.388), (4.880, 52.386), (4.830, 52.394), (4.770, 52.405),
           (4.715, 52.410), (4.690, 52.420), (4.665, 52.440), (4.665, 52.468), (4.690, 52.475),
           (4.715, 52.458), (4.740, 52.440), (4.790, 52.425), (4.840, 52.412), (4.890, 52.404),
           (4.940, 52.404), (4.990, 52.410), (5.060, 52.414)],
    # Haarlemmermeer (drained 1852), here at its smaller medieval size
    "haarlemmermeer": [(4.640, 52.355), (4.680, 52.365), (4.720, 52.350), (4.735, 52.322),
                       (4.715, 52.300), (4.680, 52.292), (4.650, 52.305), (4.632, 52.330)],
    # North Holland lakes drained in the 17th century (the smaller Wormer and
    # Leidsemeer are left out: at game scale they looked like map markers)
    "schermer": [(4.775, 52.635), (4.825, 52.640), (4.860, 52.620), (4.860, 52.585), (4.825, 52.565),
                 (4.790, 52.572), (4.770, 52.600)],
    "beemster": [(4.875, 52.585), (4.935, 52.590), (4.975, 52.565), (4.965, 52.530), (4.920, 52.518),
                 (4.880, 52.528), (4.868, 52.555)],
    "purmer": [(4.950, 52.538), (4.990, 52.540), (5.010, 52.520), (4.995, 52.500), (4.960, 52.502)],
    # Friesland: the last part of the Middelzee, now Het Bildt (diked 1505)
    "middelzee": [(5.520, 53.310), (5.590, 53.258), (5.650, 53.245), (5.720, 53.238),
                  (5.770, 53.268), (5.790, 53.330), (5.700, 53.400), (5.520, 53.380)],
    # The Lauwerszee, much bigger before the dikes of the 16th to 20th century
    "lauwerszee": [(6.060, 53.420), (6.050, 53.350), (6.100, 53.300), (6.170, 53.285),
                   (6.250, 53.310), (6.290, 53.360), (6.300, 53.430)],
    # The Dollard, which the sea started eating from 1277 on (here before the 1362 flood)
    "dollard": [(7.040, 53.320), (7.010, 53.265), (7.050, 53.215), (7.120, 53.200),
                (7.200, 53.215), (7.260, 53.250), (7.260, 53.320)],
    # Zeeland: the Sloe kept Walcheren an island until the railway dam of 1871; it runs on
    # through the Veerse Gat (dammed 1961), which the land data shows as closed
    "sloe": [(3.680, 51.630), (3.720, 51.630), (3.732, 51.500), (3.748, 51.470), (3.742, 51.425),
             (3.700, 51.425), (3.708, 51.470), (3.695, 51.500)],
}
def smooth(c, rounds=3):
    # Chaikin corner cutting, so the hand-drawn outlines look like real shores
    for _ in range(rounds):
        c = [q for a, b in zip(c, c[1:] + c[:1]) for q in ((0.75*a[0]+0.25*b[0], 0.75*a[1]+0.25*b[1]),
                                                       (0.25*a[0]+0.75*b[0], 0.25*a[1]+0.75*b[1]))]
    return Polygon(c)
hist = [smooth(c) for c in HIST_WATER.values()]
# Islands in the Zuiderzee that disappeared into the Noordoostpolder (1942)
ISLANDS = [Point(5.598, 52.662).buffer(0.010), Polygon([(5.755, 52.670), (5.775, 52.660), (5.795, 52.615),
           (5.780, 52.612), (5.760, 52.655)])]  # Urk, Schokland
water = unary_union(lakes + flevo + [afsluitdijk] + hist)
land = land.difference(water).union(unary_union(ISLANDS))
assert all(Polygon(c).is_valid for c in HIST_WATER.values())
# Drop leftover bits of the dike floating in the Zuiderzee
from shapely.geometry import MultiPolygon
dike_area = box(5.05, 52.93, 5.36, 53.09)
land = MultiPolygon([g for g in getattr(land, 'geoms', [land])
                     if g.geom_type == 'Polygon' and not dike_area.contains(g.representative_point())])
land = P(land).intersection(BIG)
nl = unary_union([shape(f['geometry']).buffer(0).intersection(GEO) for f in load('ne_10m_admin_0_countries') if f['properties']['ADMIN']=='Netherlands'])
be = unary_union([shape(f['geometry']).buffer(0) for f in adm1 if f['properties'].get('admin')=='Belgium'
                  and f['properties']['name'] in ('Antwerp','Limburg','Brussels','Flemish Brabant','Walloon Brabant')])
play = P(unary_union([nl, be]).difference(water)).buffer(0.8).buffer(-0.8).intersection(land.buffer(0.3))
rivers = P(unary_union([shape(f['geometry']).intersection(GEO) for f in load('ne_10m_rivers_lake_centerlines')
    if f['properties'].get('name') in ('IJssel','Nederrijn','Lek','Rhine','Waal','Schelde','Maas') and shape(f['geometry']).intersects(GEO)])).intersection(BIG)
src = open(TPL).read()
seeds = {m[0]: (float(m[1]), float(m[2])) for m in re.findall(r'(\w+):\s*\{ name: "[^"]+",\s*owner: "\w+",\s*x: (-?\d+),\s*y: (-?\d+)', src)}
ids = list(seeds); assert len(ids) >= 20, len(ids)
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
border_lines = {}
for a in range(len(ids)):
    for b in range(a+1, len(ids)):
        A, Bc = ids[a], ids[b]
        line = cells[A].boundary.intersection(cells[Bc].buffer(0.6))
        L = 0 if line.is_empty else line.length
        if L >= 4: border_lines[f"{A}|{Bc}"] = path(line)
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
        "__BORDER_LINES__": json.dumps(border_lines),
        "__MAP_SHAPES__": json.dumps({"land": path(land, tol=0.6), "rivers": path(rivers, tol=0.5)}),
        "__ICONS__": open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons.js"), encoding="utf-8").read()}
for k, v in subs.items():
    assert src.count(k) >= 1, k; src = src.replace(k, v)
open(OUT, 'w').write(src)
