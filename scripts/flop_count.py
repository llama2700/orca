#!/usr/bin/env python3
"""Flop-count gate: synthesize the RTL with yosys and fail if the
design uses more than the budgeted number of DFFs.

Usage: flop_count.py [--rtl-dir DIR] [--budget N] [--top MODULE]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

RTL_FILES = [
    "orca_pkg.sv", "fabric_cell.sv", "fabric.sv", "prng.sv", "genome_store.sv",
    "ser_cmd.sv", "settle_sensor.sv", "eval_engine.sv", "es_controller.sv",
    "tt_um_orca.sv",
]


def count_flops(rtl_dir: Path, top: str) -> dict:
    files = " ".join(str(rtl_dir / f) for f in RTL_FILES if (rtl_dir / f).exists())
    script = (
        f"read_verilog -sv {files}; "
        f"hierarchy -top {top}; proc; opt; memory; opt; techmap; opt; stat"
    )
    out = subprocess.run(["yosys", "-p", script], capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stdout[-3000:], out.stderr[-2000:], file=sys.stderr)
        sys.exit("yosys failed")

    # sum all $_DFF*/$_SDFF* single-bit cells in the whole-design stat
    stat = out.stdout[out.stdout.rfind("=== design hierarchy ==="):]
    flops = 0
    for m in re.finditer(r"(\d+)\s+\$_S?DFF[A-Z0-9]*_[A-Z0-9]+_", stat):
        flops += int(m.group(1))
    return flops, stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl-dir", default="src")
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--top", default="tt_um_orca")
    args = ap.parse_args()

    flops, stat = count_flops(Path(args.rtl_dir), args.top)
    print(stat)
    print(f"== DFF count: {flops} (budget {args.budget}) ==")
    if flops > args.budget:
        sys.exit(f"FAIL: {flops} flops > budget {args.budget}")
    print("PASS")


if __name__ == "__main__":
    main()
