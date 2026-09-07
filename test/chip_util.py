"""Shared startup for full-chip tests (tb.v toplevel)."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from ser_bfm import SerBFM

CLK_PERIOD_NS = 40  # 25 MHz


async def start_chip(dut):
    """Clock + reset; returns a SerBFM. Chip comes up idle (run=0)."""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    return SerBFM(dut)


def default_target():
    """Reset-default target truth table as a list of 16 2-bit entries."""
    from model.es_ref import ESController
    return ESController().target


def target_words(target):
    """(TARGET0, TARGET1) CSR words for a 16-entry target list."""
    t0 = sum(((target[v] >> 0) & 1) << v for v in range(16))
    t1 = sum(((target[v] >> 1) & 1) << v for v in range(16))
    return t0, t1
