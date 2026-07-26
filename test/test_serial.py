"""Serial BFM, every CSR RW, genome window lock while
evolving (err_busy sticky + W1C)."""

import random

import cocotb
from cocotb.triggers import ClockCycles

import ser_bfm as csr
from chip_util import start_chip


@cocotb.test()
async def test_csr_rw(dut):
    bfm = await start_chip(dut)
    random.seed(2)

    # simple RW regs
    for reg in (csr.TEMP, csr.STUCK_EN, csr.STUCK_VAL, csr.TARGET0, csr.TARGET1):
        for _ in range(3):
            v = random.getrandbits(16)
            await bfm.write(reg, v)
            assert await bfm.read(reg) == v, f"RW mismatch at reg 0x{reg:02x}"
        await bfm.write(reg, 0)
    # restore target default is not required for this suite

    # CTRL: bit1 (soft_reset_counters) is a pulse and reads 0
    await bfm.write(csr.CTRL, csr.CTRL_PAUSE_ACCEPT | csr.CTRL_SPEED_DISABLE |
                    csr.CTRL_RESET_COUNTERS)
    assert await bfm.read(csr.CTRL) == csr.CTRL_PAUSE_ACCEPT | csr.CTRL_SPEED_DISABLE
    await bfm.write(csr.CTRL, 0)

    # SEED_LO reads back; SEED_HI write-only (reads 0)
    await bfm.write(csr.SEED_LO, 0xBEEF)
    assert await bfm.read(csr.SEED_LO) == 0xBEEF
    await bfm.write(csr.SEED_HI, 0xDEAD)
    assert await bfm.read(csr.SEED_HI) == 0

    # unmapped address reads 0
    assert await bfm.read(0x0F) == 0


@cocotb.test()
async def test_genome_window(dut):
    bfm = await start_chip(dut)
    random.seed(3)

    for _ in range(5):
        g = random.getrandbits(132)
        await bfm.write_genome(g)
        assert await bfm.read_genome() == g, "genome window readback mismatch"

    # word 11 (0x1B) is padding: reads 0, write ignored
    await bfm.write(csr.GENOME_BASE + 11, 0xFFF)
    assert await bfm.read(csr.GENOME_BASE + 11) == 0


@cocotb.test()
async def test_genome_lock_while_evolving(dut):
    bfm = await start_chip(dut)

    await bfm.write_genome(0)
    # speed sweep off so generations are quick; soft-run the ES
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN)
    await ClockCycles(dut.clk, 20)
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_STATE_MASK != csr.ES_IDLE \
        or (await bfm.read(csr.GEN_LO)) > 0, "ES did not start"

    # genome writes while evolving must be dropped and set sticky err_busy
    before = await bfm.read(csr.GEN_LO)
    await bfm.write(csr.GENOME_BASE + 0, 0xFFF)
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_ERR_BUSY, "err_busy not set"

    # W1C clears it (keep running while clearing)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN |
                    csr.CTRL_ERR_BUSY_W1C)
    assert not (await bfm.read(csr.STATUS)) & csr.STATUS_ERR_BUSY, "W1C failed"

    # generations advanced in the background the whole time
    assert await bfm.read(csr.GEN_LO) > before

    # stop; counters reset via CTRL bit1
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE)
    await ClockCycles(dut.clk, 200)
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_STATE_MASK == csr.ES_IDLE
    await bfm.write(csr.CTRL, csr.CTRL_RESET_COUNTERS)
    assert await bfm.read(csr.GEN_LO) == 0
    assert await bfm.read(csr.ACCEPTS) == 0
