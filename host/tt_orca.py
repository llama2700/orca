#!/usr/bin/env python3
"""Host driver for ORCA over the Tiny Tapeout demo board.

Two transports:

  - TTBoardTransport: drives the TT demo board's RP2040 GPIO through the
    MicroPython REPL (tt demo board firmware). Requires `pyserial`.
  - CallbackTransport: adapter for anything that can set/get pins (FPGA
    bridge, FT232H, simulation) — pass set_ui(bit, val) / get_uio3().

CLI:
  tt_orca.py --port /dev/ttyACM0 id
  tt_orca.py ... seed 0xDEADBEEF
  tt_orca.py ... load-target 0xBEC1C194     (32-bit packed target)
  tt_orca.py ... run | pause | poll | read-genome
  tt_orca.py ... inject-fault 0x4420 0x0000
"""

import argparse
import sys
import time

# CSR map
ID, CTRL, STATUS, BEST_FIT, LAST_FIT = 0x00, 0x01, 0x02, 0x03, 0x04
GEN_LO, GEN_HI, ACCEPTS, TEMP = 0x05, 0x06, 0x07, 0x08
SEED_LO, SEED_HI, STUCK_EN, STUCK_VAL = 0x09, 0x0A, 0x0B, 0x0C
TARGET0, TARGET1, GENOME_BASE, SETTLE_TAP = 0x0D, 0x0E, 0x10, 0x1C

CTRL_SOFT_RUN, CTRL_RESET_COUNTERS = 1 << 0, 1 << 1
CTRL_PAUSE_ACCEPT, CTRL_ERR_BUSY_W1C, CTRL_SPEED_DISABLE = 1 << 2, 1 << 3, 1 << 4
ID_VALUE = 0x08CA

# ui_in bit positions
UI_RUN, UI_ANNEAL, UI_FAULT_DEMO = 0, 1, 2
UI_SER_DATA, UI_SER_SHIFT, UI_SER_EXEC = 4, 5, 6
UIO_SER_OUT = 3


class CallbackTransport:
    def __init__(self, set_ui, get_uio3):
        self.set_ui = set_ui       # set_ui(bit_index, value)
        self.get_uio3 = get_uio3   # -> 0/1


class TTBoardTransport:
    """Talks to the TT demo board MicroPython REPL over USB serial.

    Uses the tt-demo-board firmware's `tt` object: input pins are driven with
    tt.input_byte-style accessors. Verify the exact API against the installed
    firmware (https://github.com/TinyTapeout/tt-micropython-firmware) — this
    was written against the 2026 SDK and is exercised on hardware, not in CI.
    """

    def __init__(self, port, baud=115200):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=2)
        self.ui = 0
        self._repl("import tt")

    def _repl(self, cmd):
        self.ser.write((cmd + "\r\n").encode())
        return self.ser.read_until(b">>> ").decode(errors="replace")

    def set_ui(self, bit, value):
        self.ui = (self.ui & ~(1 << bit)) | (value << bit)
        self._repl(f"tt.input_byte = {self.ui}")

    def get_uio3(self):
        out = self._repl("print(tt.bidir_byte)")
        for line in out.splitlines():
            if line.strip().isdigit():
                return (int(line.strip()) >> UIO_SER_OUT) & 1
        raise RuntimeError(f"unexpected REPL response: {out!r}")


class Orca:
    def __init__(self, transport):
        self.t = transport

    # --- serial protocol ---
    def _pulse(self, bit):
        self.t.set_ui(bit, 1)
        self.t.set_ui(bit, 0)

    def _shift_frame(self, rw, addr, data):
        frame = (rw << 23) | ((addr & 0x7F) << 16) | (data & 0xFFFF)
        for i in range(23, -1, -1):
            self.t.set_ui(UI_SER_DATA, (frame >> i) & 1)
            self._pulse(UI_SER_SHIFT)
        self._pulse(UI_SER_EXEC)

    def write(self, addr, data):
        self._shift_frame(1, addr, data)

    def read(self, addr):
        self._shift_frame(0, addr, 0)
        value = 0
        for _ in range(16):
            value = (value << 1) | self.t.get_uio3()
            self._pulse(UI_SER_SHIFT)
        return value

    # --- high-level ops ---
    def check_id(self):
        got = self.read(ID)
        if got != ID_VALUE:
            raise RuntimeError(f"ID readback {got:#06x} != {ID_VALUE:#06x}")
        return got

    def seed(self, value):
        self.write(SEED_LO, value & 0xFFFF)
        self.write(SEED_HI, (value >> 16) & 0xFFFF)

    def load_target(self, packed32):
        t0 = sum(((packed32 >> (2 * v)) & 1) << v for v in range(16))
        t1 = sum(((packed32 >> (2 * v + 1)) & 1) << v for v in range(16))
        self.write(TARGET0, t0)
        self.write(TARGET1, t1)

    def run(self, speed_sweep=True):
        ctrl = CTRL_SOFT_RUN | (0 if speed_sweep else CTRL_SPEED_DISABLE)
        self.write(CTRL, ctrl)

    def pause(self):
        self.write(CTRL, 0)

    def inject_fault(self, stuck_en, stuck_val, rebaseline=True, temp=0x6000):
        """Mirrors the ui[2] button: inject + re-baseline + arm anneal TEMP.
        Multi-cell faults never heal without annealing (anneal_en is the ui[1]
        pin — strap it high for the HEAL demo)."""
        self.write(STUCK_EN, stuck_en)
        self.write(STUCK_VAL, stuck_val)
        if temp is not None:
            self.write(TEMP, temp)
        if rebaseline:  # stale best_fitness would block all accepts
            cur = self.read(CTRL)
            self.write(CTRL, cur | CTRL_RESET_COUNTERS)

    def poll(self):
        return {
            "generation": self.read(GEN_LO) | (self.read(GEN_HI) << 16),
            "best_fitness": self.read(BEST_FIT),
            "last_fitness": self.read(LAST_FIT),
            "accepts": self.read(ACCEPTS),
            "status": self.read(STATUS),
            "settle_tap": self.read(SETTLE_TAP),
        }

    def read_genome(self):
        g = 0
        for w in range(11):
            g |= (self.read(GENOME_BASE + w) & 0xFFF) << (12 * w)
        return g

    def write_genome(self, genome):
        for w in range(11):
            self.write(GENOME_BASE + w, (genome >> (12 * w)) & 0xFFF)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("cmd", choices=["id", "seed", "load-target", "run", "run-fast",
                                    "pause", "poll", "read-genome", "inject-fault"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    orca = Orca(TTBoardTransport(a.port))
    if a.cmd == "id":
        print(f"ID: {orca.check_id():#06x} ('ORCA')")
    elif a.cmd == "seed":
        orca.seed(int(a.args[0], 0))
    elif a.cmd == "load-target":
        orca.load_target(int(a.args[0], 0))
    elif a.cmd == "run":
        orca.run()
    elif a.cmd == "run-fast":
        orca.run(speed_sweep=False)
    elif a.cmd == "pause":
        orca.pause()
    elif a.cmd == "poll":
        for k, v in orca.poll().items():
            print(f"{k}: {v}")
    elif a.cmd == "read-genome":
        print(f"{orca.read_genome():#035x}")
    elif a.cmd == "inject-fault":
        en = int(a.args[0], 0) if a.args else 0x4420
        val = int(a.args[1], 0) if len(a.args) > 1 else 0
        orca.inject_fault(en, val)


if __name__ == "__main__":
    main()
