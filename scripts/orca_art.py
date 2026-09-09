#!/usr/bin/env python3
"""Generate src/orca_art.gds: a pixel-art orca on met4 (layer 71, dt 20).

The orca is a proper macro in the flow (MACROS in src/config.json): the LEF
(src/orca_art.lef) is a 2x2 um block parked in the cell-free margin at die
coordinate (1,1), and the GDS content is offset so the art lands at
ART_ABS when the instance is placed at INSTANCE. The art region is covered
by a ROUTING_OBSTRUCTIONS met4 blockage, so the router never touches it.

DRC-safe by construction: 2.0 um pixels on a 2.5 um pitch => 0.5 um
separation between unconnected shapes (met4 min space is 0.3 um), adjacent
pixels unioned into larger polygons. Placement is a met4-free strip of the
routed die (x~297..327, y~99..225 with 1.5 um clearance, measured on the
routed GDS).
"""

import gdstk

# diving orca, fluke up — 18 x 12 px, top row first (rotated CW below ->
# breaching pose, head up, 12 wide x 18 tall)
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

PIXEL = 2.0   # um
PITCH = 2.5   # um
LAYER, DATATYPE = 71, 20  # met4 drawing
ART_ABS = (297.2, 170.0)  # lower-left of the art on the die
INSTANCE = (1.0, 1.0)     # macro instance location (LEF bbox lives here)


def rotate_cw(bitmap):
    r, c = len(bitmap), len(bitmap[0])
    return ["".join(bitmap[r - 1 - rr][cc] for rr in range(r)) for cc in range(c)]


def main():
    bmp = rotate_cw(BITMAP)
    assert len({len(row) for row in bmp}) == 1, "bitmap rows must all be the same width"
    origin = (ART_ABS[0] - INSTANCE[0], ART_ABS[1] - INSTANCE[1])

    rows = bmp[::-1]  # bottom row first for gds coords
    squares = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch != "#":
                continue
            x0 = origin[0] + c * PITCH
            y0 = origin[1] + r * PITCH
            squares.append(gdstk.rectangle((x0, y0), (x0 + PIXEL, y0 + PIXEL)))

    merged = gdstk.offset(squares, 0, use_union=True, layer=LAYER, datatype=DATATYPE)
    cell = gdstk.Cell("orca_art")
    for p in merged:
        cell.add(p)

    # PR boundary (sky130 areaid 235/4) matching the 2x2 LEF bbox at the
    # origin — magic's macro bbox extraction requires it
    cell.add(gdstk.rectangle((0, 0), (2.0, 2.0), layer=235, datatype=4))

    lib = gdstk.Library("orca_art")
    lib.add(cell)
    out = "src/orca_art.gds"
    lib.write_gds(out)

    bb = cell.bounding_box()
    w = bb[1][0] - bb[0][0]
    h = bb[1][1] - bb[0][1]
    print(f"wrote {out}: {len(merged)} polygons on ({LAYER},{DATATYPE})")
    print(f"on-die bbox {bb[0][0]+INSTANCE[0]:.1f},{bb[0][1]+INSTANCE[1]:.1f} .. "
          f"{bb[1][0]+INSTANCE[0]:.1f},{bb[1][1]+INSTANCE[1]:.1f}  ({w:.1f} x {h:.1f} um)")


if __name__ == "__main__":
    main()
