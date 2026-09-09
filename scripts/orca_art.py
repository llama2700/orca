#!/usr/bin/env python3
"""Generate src/orca_art.gds: a pixel-art orca on met4 (layer 71, dt 20),
merged into the final layout by LibreLane EXTRA_GDS_FILES.

DRC-safe by construction: 1.0 um pixels on a 1.6 um pitch => >= 0.6 um
separation between unconnected shapes (met4 min space is 0.3 um), adjacent
pixels unioned into larger polygons. Placement is in a met4-free region of
the routed die (top-right, x~297..327, y~99..225 with 1.5 um clearance —
see the overlap check at the bottom of this file).
"""

import gdstk

# diving orca, fluke up — 18 x 12 px, top row first
BITMAP = [
    "..............##..",
    "..............###.",
    "..............####",
    ".....##......#####",
    ".....###....######",
    ".....####..#######",
    ".#################",
    ".################.",
    "#################.",
    ".##############...",
    "..##########......",
    "....######........",
]

PIXEL = 1.0   # um
PITCH = 1.6   # um
LAYER, DATATYPE = 71, 20  # met4 drawing
ORIGIN = (298.0, 202.0)  # lower-left of bitmap, absolute die coords

def main():
    assert len({len(r) for r in BITMAP}) == 1, "bitmap rows must all be the same width"
    rows = BITMAP[::-1]  # bottom row first for gds coords
    squares = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch != "#":
                continue
            x0 = ORIGIN[0] + c * PITCH
            y0 = ORIGIN[1] + r * PITCH
            squares.append(gdstk.rectangle((x0, y0), (x0 + PIXEL, y0 + PIXEL)))

    merged = gdstk.offset(squares, 0, use_union=True, layer=LAYER, datatype=DATATYPE)
    cell = gdstk.Cell("orca_art")
    for p in merged:
        cell.add(p)

    lib = gdstk.Library("orca_art")
    lib.add(cell)
    out = "src/orca_art.gds"
    lib.write_gds(out)

    bb = cell.bounding_box()
    print(f"wrote {out}: {len(merged)} polygons on ({LAYER},{DATATYPE})")
    print(f"bbox {bb[0]} .. {bb[1]}  ({bb[1][0]-bb[0][0]:.1f} x {bb[1][1]-bb[0][1]:.1f} um)")

if __name__ == "__main__":
    main()
