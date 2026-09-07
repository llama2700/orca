"""Random stuck-at patterns vs golden model.
Toplevel: fabric."""

import random

import cocotb
from cocotb.triggers import Timer

from model.cgp_ref import CGPFabric

N_CASES = 300


@cocotb.test()
async def test_fault_injection_vs_model(dut):
    random.seed(0xFA17)
    model = CGPFabric()

    for _ in range(N_CASES):
        genome = random.getrandbits(132)
        stuck_en = random.getrandbits(16)
        stuck_val = random.getrandbits(16)
        dut.genome.value = genome
        dut.stuck_en.value = stuck_en
        dut.stuck_val.value = stuck_val
        for v in range(16):
            dut.pi.value = v
            await Timer(1, unit="ns")
            po0, po1, cells = model.sim(genome, stuck_en, stuck_val, v)
            assert dut.po.value.to_unsigned() == (po1 << 1) | po0, \
                f"po mismatch under fault: genome={genome:#x} en={stuck_en:#x} val={stuck_val:#x} pi={v}"
            assert dut.cell_out_dbg.value.to_unsigned() == cells, \
                f"dbg mismatch under fault: genome={genome:#x} en={stuck_en:#x} val={stuck_val:#x} pi={v}"


@cocotb.test()
async def test_fault_phenotype_only(dut):
    """Killing a cell must not change what a fault-free evaluation would see
    (genome is upstream; faults are output overrides only)."""
    random.seed(0xFA18)
    model = CGPFabric()

    genome = random.getrandbits(132)
    dut.genome.value = genome
    dut.stuck_en.value = 0xFFFF
    dut.stuck_val.value = 0xA5A5
    for v in range(16):
        dut.pi.value = v
        await Timer(1, unit="ns")
        # all cells overridden: dbg shows exactly the stuck values
        assert dut.cell_out_dbg.value.to_unsigned() == 0xA5A5

    # clearing faults restores the genome's own phenotype
    dut.stuck_en.value = 0
    for v in range(16):
        dut.pi.value = v
        await Timer(1, unit="ns")
        po0, po1, _ = model.sim(genome, 0, 0, v)
        assert dut.po.value.to_unsigned() == (po1 << 1) | po0
