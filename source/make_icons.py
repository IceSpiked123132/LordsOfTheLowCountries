# Draws the app icons (icon-192.png, icon-512.png): a red castle on parchment.
# Usage: python3 source/make_icons.py .
import sys
from PIL import Image, ImageDraw

def icon(n, out):
    S = 1024
    im = Image.new("RGB", (S, S), "#3b2a1a")
    d = ImageDraw.Draw(im)
    d.ellipse([132, 132, 892, 892], fill="#efe3c4")
    red, ink, base = "#b23a3a", "#3b2a1a", 700
    d.rectangle([330, 470, 694, base], fill=red)
    for x0 in (270, 600):
        d.rectangle([x0, 360, x0 + 154, base], fill=red)
        for i in range(3):
            d.rectangle([x0 + i * 58, 315, x0 + i * 58 + 38, 365], fill=red)
    for x in range(424, 600, 60):
        d.rectangle([x, 430, x + 36, 475], fill=red)
    d.rectangle([462, 560, 562, base], fill=ink)
    d.ellipse([462, 510, 562, 610], fill=ink)
    d.line([512, 260, 512, 430], fill=ink, width=14)
    d.polygon([(518, 262), (610, 292), (518, 322)], fill="#c9a227")
    d.rectangle([250, base, 774, base + 22], fill=ink)
    im.resize((n, n), Image.LANCZOS).save(f"{out}/icon-{n}.png")

folder = sys.argv[1] if len(sys.argv) > 1 else "."
icon(180, folder)
icon(192, folder)
icon(512, folder)
