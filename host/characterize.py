#!/usr/bin/env python3
"""CHARACTERIZE demo: per-die settle-tap profiling.

For each genome (current chip genome by default, or a file of genomes), let the
eval engine's speed sweep measure t_min on this die and log it. Comparing logs
from two physical dies shows process variation (the Thompson experiment).

Usage:
  characterize.py --port /dev/ttyACM0 [--genomes FILE] [--out die_A.csv]
  (FILE: one hex genome per line)
"""

import argparse
import csv
import sys
import time

from tt_orca import (Orca, TTBoardTransport, CTRL, CTRL_SOFT_RUN, STATUS,
                     SETTLE_TAP, BEST_FIT, LAST_FIT)


def measure(orca, genome):
    """Load a genome and let the speed sweep measure t_min for it: set the
    target to the genome's own truth table (correct == 32 by construction,
    so the sweep always runs), soft-run briefly, read back SETTLE_TAP."""
    orca.pause()
    orca.write_genome(genome)
    # target := genome's own truth table, so the speed sweep always runs.
    # The chip can't compute its own truth table; the host does it with the
    # golden model if available, else assumes the target is already loaded.
    try:
        sys.path.insert(0, "..")
        from model.cgp_ref import CGPFabric
        m = CGPFabric()
        packed = 0
        for v in range(16):
            po0, po1, _ = m.sim(genome, 0, 0, v)
            packed |= ((po1 << 1) | po0) << (2 * v)
        orca.load_target(packed)
    except ImportError:
        pass
    orca.write(CTRL, CTRL_SOFT_RUN)   # speed sweep enabled
    time.sleep(0.05)                  # a few thousand generations
    orca.pause()
    return orca.read(SETTLE_TAP)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--genomes", help="file with one hex genome per line")
    ap.add_argument("--out", default="characterize.csv")
    a = ap.parse_args()

    orca = Orca(TTBoardTransport(a.port))
    orca.check_id()

    if a.genomes:
        genomes = [int(l, 16) for l in open(a.genomes) if l.strip()]
    else:
        genomes = [orca.read_genome()]

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["genome_hex", "t_min"])
        for g in genomes:
            t = measure(orca, g)
            w.writerow([f"{g:033x}", t])
            print(f"genome {g:#x} -> t_min {t}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
