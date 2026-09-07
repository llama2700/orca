"""Reset values, CSR ID read."""

import cocotb
from cocotb.triggers import ClockCycles

import ser_bfm as csr
from chip_util import start_chip, default_target, target_words


@cocotb.test()
async def test_reset_values(dut):
    bfm = await start_chip(dut)

    # outputs quiet after reset
    assert dut.uo_out.value.to_unsigned() == 0, "uo_out not quiet after reset"
    assert dut.uio_oe.value.to_unsigned() == 0b10111000

    assert await bfm.read(csr.ID) == csr.ID_VALUE

    status = await bfm.read(csr.STATUS)
    assert status & csr.STATUS_STATE_MASK == csr.ES_IDLE
    assert not status & csr.STATUS_SOLVED
    assert not status & csr.STATUS_ERR_BUSY

    for reg in (csr.BEST_FIT, csr.LAST_FIT, csr.GEN_LO, csr.GEN_HI,
                csr.ACCEPTS, csr.TEMP, csr.STUCK_EN, csr.STUCK_VAL, csr.CTRL):
        assert await bfm.read(reg) == 0, f"reg 0x{reg:02x} not 0 after reset"

    # hardwired default target (PO0 = parity, PO1 = AND-OR) matches the model
    t0, t1 = target_words(default_target())
    assert await bfm.read(csr.TARGET0) == t0
    assert await bfm.read(csr.TARGET1) == t1

    # genome resets to 0; SETTLE_TAP to 63
    assert await bfm.read_genome() == 0
    assert await bfm.read(csr.SETTLE_TAP) == 63

    # still idle, nothing evolved on its own
    await ClockCycles(dut.clk, 50)
    assert await bfm.read(csr.GEN_LO) == 0
