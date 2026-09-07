#!/usr/bin/env python3
"""Delay-line structural check: verify the settle sensor's buffer
chain survived synthesis/hardening untouched.

Counts instances of the delay cell in a netlist and fails if fewer than
expected. Run against the post-synthesis netlist the TT flow produces.

Usage: delayline_check.py NETLIST.v [--cell sky130_fd_sc_hd__dlygate4sd3] [--expect 64]
"""

import argparse
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--cell", default="sky130_fd_sc_hd__dlygate4sd3")
    ap.add_argument("--expect", type=int, default=64)  # 64 taps x 1 cell
    args = ap.parse_args()

    text = Path(args.netlist).read_text()
    n = len(re.findall(rf"\b{re.escape(args.cell)}(?:_\d+)?\s", text))
    print(f"{args.cell}: {n} instances (expected >= {args.expect})")
    if n < args.expect:
        sys.exit(f"FAIL: delay chain incomplete ({n} < {args.expect}) — "
                 "check keep/dont_touch attributes")
    print("PASS")


if __name__ == "__main__":
    main()
