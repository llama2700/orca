#!/usr/bin/env python3
"""Live fitness-vs-generation plot: polls BEST_FIT/LAST_FIT/GEN
over the serial interface and animates convergence.

Usage: live_plot.py --port /dev/ttyACM0 [--interval 0.2]
"""

import argparse

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from tt_orca import Orca, TTBoardTransport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--interval", type=float, default=0.2, help="poll period, s")
    a = ap.parse_args()

    orca = Orca(TTBoardTransport(a.port))
    orca.check_id()

    gens, best, last, accepts = [], [], [], []

    fig, (ax_fit, ax_acc) = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
    (ln_best,) = ax_fit.plot([], [], label="best fitness", drawstyle="steps-post")
    (ln_last,) = ax_fit.plot([], [], label="last fitness", alpha=0.4, lw=0.8)
    (ln_acc,)  = ax_acc.plot([], [], label="accepts")
    ax_fit.axhline(32 << 6, ls="--", lw=0.8, label="solved (correct=32)")
    ax_fit.set_ylabel("fitness {correct,speed}")
    ax_fit.legend(loc="lower right")
    ax_acc.set_xlabel("generation")
    ax_acc.set_ylabel("accepts")
    fig.suptitle("ORCA evolution")

    def tick(_frame):
        s = orca.poll()
        gens.append(s["generation"])
        best.append(s["best_fitness"])
        last.append(s["last_fitness"])
        accepts.append(s["accepts"])
        ln_best.set_data(gens, best)
        ln_last.set_data(gens, last)
        ln_acc.set_data(gens, accepts)
        for ax in (ax_fit, ax_acc):
            ax.relim()
            ax.autoscale_view()
        return ln_best, ln_last, ln_acc

    _anim = FuncAnimation(fig, tick, interval=a.interval * 1000, cache_frame_data=False)
    plt.show()


if __name__ == "__main__":
    main()
