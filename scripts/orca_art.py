#!/usr/bin/env python3
"""Generate src/orca_art.gds: a full-die orca on met4 (layer 71, dt 20).

The orca is a proper macro in the flow (MACROS in src/config.json): the LEF
(src/orca_art.lef) is a 2x2 um block parked in the cell-free margin at die
coordinate (1,1), and the GDS content is offset so the art lands where we
want it. ROUTING_OBSTRUCTIONS keeps the signal router off the art.

Source is scripts/orca.png, tilted clockwise so the face sits up and left
and the fluke trails down and right, then rasterised onto a 0.5 um grid (the
same pixel size tt uses for its own logo) at 655 x 439 px, which puts the art
at 327.5 x 219.5 um.

The tilt is 18 degrees, not 45. Tilting a long body inside a wide tile costs
width: at 18 the rotated bounding box aspect matches the drawable window, so
both the width and the height are used up at once and the picture is as big
as it can get. Steeper than that and it goes height limited and shrinks fast
(45 degrees gives up a third of the metal). Rotating the raster rather than
the polygons keeps every shape axis aligned, so the sloped edges come out as
a 0.5 um staircase and the rules still hold by construction.

DRC-safe by construction. Every shape sits on the 0.5 um pixel grid, so the
narrowest metal is 0.5 um (met4 min width 0.30) and the narrowest gap is
0.5 um (min space 0.40 for shapes wider than 3 um). Coordinates are whole
multiples of 500 nm, well inside the 5 nm manufacturing grid.

The 17 met4 power straps cannot move, so the art is cut around them with
0.6 um clearance. That splits the orca into islands, but the straps are met4
too, so the seams read as hairlines.

Usage:
  orca_art.py                  write src/orca_art.gds + print the obstructions
  orca_art.py --check          run the met4 rule checks over the result
  orca_art.py --preview P.png  render what the tile will look like
  orca_art.py --write-config   also splice the obstructions into config.json
  orca_art.py --verify-straps runs/run5/final/def/tt_um_orca.def
"""

import argparse
import json
import os
import re
import sys
from collections import deque

import gdstk
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC_PNG = os.path.join(HERE, "orca.png")
OUT_GDS = os.path.join(REPO, "src", "orca_art.gds")

LAYER, DATATYPE = 71, 20      # met4.drawing
PRB_LAYER, PRB_DATATYPE = 235, 4  # prBoundary.boundary

PIXEL = 0.5                   # um, art raster pitch
ROTATE = -18                  # degrees, pil turns anticlockwise so this is cw
ART_W, ART_H = 655, 439       # px, preserves the 1.493 aspect once rotated
ART_X0, ART_Y0 = 3.5, 3.0     # um, lower-left of the art on the die
INSTANCE = (1.0, 1.0)         # macro instance location (the lef bbox lives here)
LEF_SIZE = 2.0                # um, dummy lef block

DIE_W, DIE_H = 334.88, 225.76

# met4 power straps: 1.6 um wide, spanning y 2.48..223.28, pairs 3.3 um apart
# on a 38.87 um pitch (FP_PDN_VPITCH). verified against the routed def, see
# --verify-straps
STRAP_W = 1.6
STRAP_X = [19.08, 22.38, 57.95, 61.25, 96.82, 100.12, 135.69, 138.99,
           174.56, 177.86, 213.43, 216.73, 252.30, 255.60, 291.17, 294.47,
           330.04]
STRAP_CLEAR = 0.6             # um of bare silicon between art and strap

MIN_ISLAND = 1.0              # um2, drop specks below this (min area is 0.24)
OBS_BAND = 2.0                # um, row height of the routing obstructions
OBS_MARGIN = 0.5              # um, grow obstructions sideways past the ink

# met4 rules, um
RULE_WIDTH, RULE_SPACE, RULE_AREA = 0.30, 0.40, 0.24


def ink_raster():
    """Source png as a boolean array: cropped, rotated, then resampled."""
    im = Image.open(SRC_PNG)
    flat = Image.new("RGB", im.size, (255, 255, 255))
    flat.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
    a = np.array(flat.convert("L"))
    ys, xs = np.where(a < 128)
    crop = Image.fromarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    if ROTATE:
        crop = crop.rotate(ROTATE, expand=True, fillcolor=255,
                           resample=Image.BICUBIC)
        m = np.array(crop) < 128
        ys, xs = np.where(m)
        crop = crop.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return np.array(crop.resize((ART_W, ART_H), Image.LANCZOS)) < 128


def strap_blocked_columns():
    """Pixel columns that fall within clearance of a power strap."""
    keep_out = STRAP_W / 2 + STRAP_CLEAR
    cx = ART_X0 + (np.arange(ART_W) + 0.5) * PIXEL
    blocked = np.zeros(ART_W, bool)
    for s in STRAP_X:
        blocked |= (cx > s - keep_out - PIXEL / 2) & (cx < s + keep_out + PIXEL / 2)
    return blocked


def fill_pinches(p):
    """Fill diagonal-only touches, which would meet at a zero-width corner.

    Each 2x2 window with metal on one diagonal and nothing on the other gets
    one of the empty cells filled, which turns the corner into a real join.
    Fill an empty cell, never one of the two that are already set, or the
    pass is a no-op and the loop spins forever on a 45 degree edge.
    """
    p = p.copy()
    for _ in range(64):
        a, b = p[:-1, :-1], p[:-1, 1:]
        c, d = p[1:, :-1], p[1:, 1:]
        d1 = a & d & ~b & ~c    # metal top-left + bottom-right, fill top-right
        d2 = b & c & ~a & ~d    # metal top-right + bottom-left, fill bottom-right
        if not (d1.any() or d2.any()):
            return p
        p[:-1, 1:] |= d1
        p[1:, 1:] |= d2
    raise RuntimeError("pinch fill did not converge")


def islands(p):
    """Label 4-connected regions, returns (count, list of pixel counts)."""
    seen = np.zeros(p.shape, bool)
    sizes = []
    for y in range(p.shape[0]):
        for x in range(p.shape[1]):
            if p[y, x] and not seen[y, x]:
                seen[y, x] = True
                q = deque([(y, x)])
                cells = []
                while q:
                    cy, cx = q.popleft()
                    cells.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if (0 <= ny < p.shape[0] and 0 <= nx < p.shape[1]
                                and p[ny, nx] and not seen[ny, nx]):
                            seen[ny, nx] = True
                            q.append((ny, nx))
                sizes.append(cells)
    return sizes


def build_mask():
    """The final met4 pixel mask, bottom row first for gds coordinates."""
    ink = ink_raster()
    art = ink.copy()
    art[:, strap_blocked_columns()] = False
    art = fill_pinches(art)
    for cells in islands(art):
        if len(cells) * PIXEL * PIXEL < MIN_ISLAND:
            for cy, cx in cells:
                art[cy, cx] = False
    return ink, art[::-1]


def row_runs(mask):
    """Horizontal runs of set pixels, as (row, col_start, col_end_exclusive)."""
    for r in range(mask.shape[0]):
        row = mask[r]
        c = 0
        while c < len(row):
            if row[c]:
                c0 = c
                while c < len(row) and row[c]:
                    c += 1
                yield r, c0, c
            else:
                c += 1


def art_polygons(mask):
    """Union the pixel runs into merged polygons, in gds (macro) coordinates."""
    ox = ART_X0 - INSTANCE[0]
    oy = ART_Y0 - INSTANCE[1]
    rects = [
        gdstk.rectangle((ox + c0 * PIXEL, oy + r * PIXEL),
                        (ox + c1 * PIXEL, oy + (r + 1) * PIXEL))
        for r, c0, c1 in row_runs(mask)
    ]
    return gdstk.offset(rects, 0, use_union=True, layer=LAYER, datatype=DATATYPE)


def obstructions(ink):
    """met4 blockages tracing the orca, as config.json strings.

    Built from the ink before the straps are cut out, so the router stays off
    the whole silhouette. Banded into OBS_BAND rows to keep the list short.
    """
    band = max(1, int(round(OBS_BAND / PIXEL)))
    flipped = ink[::-1]
    out = []
    for r0 in range(0, ART_H, band):
        rows = flipped[r0:r0 + band]
        merged = rows.any(axis=0)[None, :]
        y0 = ART_Y0 + r0 * PIXEL
        y1 = ART_Y0 + min(r0 + band, ART_H) * PIXEL
        for _, c0, c1 in row_runs(merged):
            x0 = max(0.0, ART_X0 + c0 * PIXEL - OBS_MARGIN)
            x1 = min(DIE_W, ART_X0 + c1 * PIXEL + OBS_MARGIN)
            out.append(f"met4 {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f}")
    return out


def write_config(obs):
    """Replace the ROUTING_OBSTRUCTIONS array in src/config.json in place.

    Edited as text, not via json round-trip: config.json carries repeated
    "//" comment keys that a load/dump would collapse.
    """
    path = os.path.join(REPO, "src", "config.json")
    s = open(path).read()
    body = ",\n".join(f'    "{o}"' for o in obs)
    new, n = re.subn(r'"ROUTING_OBSTRUCTIONS": \[.*?\n  \]',
                     '"ROUTING_OBSTRUCTIONS": [\n' + body + "\n  ]", s,
                     count=1, flags=re.S)
    if n != 1:
        sys.exit("could not find ROUTING_OBSTRUCTIONS in src/config.json")
    open(path, "w").write(new)
    json.load(open(path))
    print(f"updated {path}: {len(obs)} obstructions")


def write_gds(polys):
    cell = gdstk.Cell("orca_art")
    for p in polys:
        cell.add(p)
    # magic extracts the macro bbox from the pr boundary, so it matches the
    # lef block, not the art. the art deliberately lives outside it
    cell.add(gdstk.rectangle((0, 0), (LEF_SIZE, LEF_SIZE),
                             layer=PRB_LAYER, datatype=PRB_DATATYPE))
    lib = gdstk.Library("orca_art")
    lib.add(cell)
    lib.write_gds(OUT_GDS, max_points=4000)
    return cell


def check(polys):
    """Verify the met4 rules with klayout, plus placement and grid."""
    import klayout.db as kdb

    ly = kdb.Layout()
    ly.dbu = 0.001
    top = ly.create_cell("check")
    lyr = ly.layer(LAYER, DATATYPE)
    for p in polys:
        pts = [kdb.Point(round(x * 1000), round(y * 1000)) for x, y in p.points]
        top.shapes(lyr).insert(kdb.Polygon(pts))

    art = kdb.Region(top.begin_shapes_rec(lyr)).merged()
    art.move(round(INSTANCE[0] * 1000), round(INSTANCE[1] * 1000))

    straps = kdb.Region()
    for s in STRAP_X:
        straps.insert(kdb.Box(round((s - STRAP_W / 2) * 1000), 2480,
                              round((s + STRAP_W / 2) * 1000), 223280))

    fails = []
    n = art.width_check(round(RULE_WIDTH * 1000)).count()
    fails.append((f"met4 min width {RULE_WIDTH} um", n))
    n = art.space_check(round(RULE_SPACE * 1000)).count()
    fails.append((f"met4 min space {RULE_SPACE} um", n))
    n = art.separation_check(straps, round(RULE_SPACE * 1000)).count()
    fails.append((f"clearance to power straps {RULE_SPACE} um", n))
    n = art.and_(straps).count()
    fails.append(("overlap with power straps", n))
    n = art.with_area(0, round(RULE_AREA * 1e6), False).count()
    fails.append((f"met4 min area {RULE_AREA} um2", n))

    # everything must sit on the 5 nm grid
    off = 0
    for poly in art.each():
        for pt in poly.each_point_hull():
            if pt.x % 5 or pt.y % 5:
                off += 1
    fails.append(("off-grid vertices (5 nm)", off))

    # inside the die, and clear of the top-edge met4 pins
    bb = art.bbox()
    outside = 0 if (bb.left >= 0 and bb.bottom >= 0
                    and bb.right <= DIE_W * 1000
                    and bb.top <= DIE_H * 1000) else 1
    fails.append(("shapes outside the die", outside))
    pins = kdb.Region(kdb.Box(30320, 224260, 147240, 225760))
    fails.append(("overlap with the top-edge pins", art.and_(pins).count()))

    # the obstructions in config.json must cover every bit of art, or the
    # router is free to drop a met4 wire straight through it
    cfg = json.load(open(os.path.join(REPO, "src", "config.json")))
    blocked = kdb.Region()
    for o in cfg.get("ROUTING_OBSTRUCTIONS", []):
        _, x0, y0, x1, y1 = o.split()
        blocked.insert(kdb.Box(round(float(x0) * 1000), round(float(y0) * 1000),
                               round(float(x1) * 1000), round(float(y1) * 1000)))
    uncovered = (art - blocked.merged()).area()
    fails.append(("art left uncovered by ROUTING_OBSTRUCTIONS", uncovered))

    width = 78
    print("\nmet4 rule checks")
    ok = True
    for name, count in fails:
        state = "pass" if count == 0 else f"FAIL ({count})"
        print(f"  {name:.<{width - 12}} {state}")
        ok &= count == 0
    print(f"  art bbox {bb.left/1000:.3f},{bb.bottom/1000:.3f} .. "
          f"{bb.right/1000:.3f},{bb.top/1000:.3f} um")
    return ok


def preview(path, ink, mask):
    """Render the tile so the art can be seen without a hardening run."""
    scale = 4  # px per um
    w, h = int(DIE_W * scale), int(DIE_H * scale)
    img = Image.new("RGB", (w, h), (14, 16, 22))
    px = img.load()

    def box(x0, y0, x1, y1, col):
        for X in range(max(0, int(x0 * scale)), min(w, int(x1 * scale))):
            for Y in range(max(0, int(y0 * scale)), min(h, int(y1 * scale))):
                px[X, h - 1 - Y] = col

    for s in STRAP_X:
        box(s - STRAP_W / 2, 2.48, s + STRAP_W / 2, 223.28, (86, 96, 122))
    up = mask[::-1]
    for r, c0, c1 in row_runs(up):
        box(ART_X0 + c0 * PIXEL, ART_Y0 + (ART_H - 1 - r) * PIXEL,
            ART_X0 + c1 * PIXEL, ART_Y0 + (ART_H - r) * PIXEL, (222, 232, 245))
    img.save(path)
    print(f"wrote {path}  ({w} x {h} px, {scale} px/um)")


def verify_straps(def_path):
    txt = open(def_path).read()
    sn = txt[txt.index("SPECIALNETS"):txt.index("END SPECIALNETS")]
    pat = re.compile(r"met4\s+(\d+)[^(]*\(\s*(-?\d+)\s+(-?\d+)\s*\)")
    hits = pat.findall(sn)
    xs = sorted({int(h[1]) / 1000 for h in hits})
    widths = sorted({int(h[0]) / 1000 for h in hits})
    same = xs == sorted(STRAP_X) and widths == [STRAP_W]
    print(f"{def_path}: {len(hits)} met4 straps, widths {widths}")
    print(f"  matches the hard-coded table: {same}")
    if not same:
        print(f"  def has: {xs}")
        print(f"  script has: {sorted(STRAP_X)}")
    return same


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run the met4 rule checks")
    ap.add_argument("--write-config", action="store_true",
                    help="splice the obstructions into src/config.json")
    ap.add_argument("--preview", metavar="PNG", help="render the tile to a png")
    ap.add_argument("--verify-straps", metavar="DEF", help="check straps against a def")
    args = ap.parse_args()

    if args.verify_straps:
        sys.exit(0 if verify_straps(args.verify_straps) else 1)

    ink, mask = build_mask()
    polys = art_polygons(mask)
    write_gds(polys)

    area = mask.sum() * PIXEL * PIXEL
    kept = 100 * mask.sum() / ink.sum()
    print(f"wrote {OUT_GDS}: {len(polys)} polygons on ({LAYER},{DATATYPE})")
    print(f"  art {ART_W*PIXEL:.1f} x {ART_H*PIXEL:.1f} um at "
          f"({ART_X0}, {ART_Y0}) .. ({ART_X0+ART_W*PIXEL}, {ART_Y0+ART_H*PIXEL})")
    print(f"  {area:.0f} um2 of met4, {100*area/(DIE_W*DIE_H):.1f}% of the die, "
          f"{kept:.0f}% of the ink survives the straps")

    obs = obstructions(ink)
    print(f"\nROUTING_OBSTRUCTIONS for src/config.json ({len(obs)} rects):")
    print("  " + ",\n  ".join(f'"{o}"' for o in obs))

    if args.write_config:
        write_config(obs)
    if args.preview:
        preview(args.preview, ink, mask)
    if args.check and not check(polys):
        sys.exit("rule checks failed")


if __name__ == "__main__":
    main()
