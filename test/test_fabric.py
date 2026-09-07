"""Fabric standalone vs golden model — 1,000 random
genomes x all 16 vectors (no faults). Toplevel: fabric."""

import random

import cocotb
from cocotb.triggers import Timer

from model.cgp_ref import CGPFabric

N_GENOMES = 1000


@cocotb.test()
async def test_fabric_vs_model(dut):
    random.seed(0xFAB)
    model = CGPFabric()

    dut.stuck_en.value = 0
    dut.stuck_val.value = 0

    for _ in range(N_GENOMES):
        genome = random.getrandbits(132)
        dut.genome.value = genome
        for v in range(16):
            dut.pi.value = v
            await Timer(1, unit="ns")
            po0, po1, cells = model.sim(genome, 0, 0, v)
            got_po = dut.po.value.to_unsigned()
            got_dbg = dut.cell_out_dbg.value.to_unsigned()
            assert got_po == (po1 << 1) | po0, \
                f"po mismatch: genome={genome:#x} pi={v} rtl={got_po:02b} model={po1}{po0}"
            assert got_dbg == cells, \
                f"cell_out_dbg mismatch: genome={genome:#x} pi={v} rtl={got_dbg:#06x} model={cells:#06x}"
