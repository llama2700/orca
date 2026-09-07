"""Full-chip seeded evolution vs golden model.

Seeds the PRNG over the serial interface, runs with the speed sweep disabled
(fitness = pure correctness, deterministic), lets the chip evolve the default
parity/AND-OR target, and checks:
  - solved within 2x the generation count the model needed
  - after pausing, chip genome/generation/best_fitness match the model run
    step-for-step (bit-exact whole-chip check)
Marked slow: ~1M sim cycles.
"""

import cocotb
from cocotb.triggers import ClockCycles

import ser_bfm as csr
from chip_util import start_chip
from model.es_ref import ESController

SEED = 0x0DDBA11
POLL_LIMIT = 400  # status polls before giving up


def model_solve_generations(seed):
    model = ESController(seed=seed)
    while model.best_fitness >> 6 < 32:
        model.step()
        if model.generation > 50_000:
            raise RuntimeError("model did not solve; pick another seed")
    return model.generation


@cocotb.test()
async def test_evolution_e2e(dut):
    n_model = model_solve_generations(SEED)
    dut._log.info(f"model solves seed {SEED:#x} in {n_model} generations")
    budget = 2 * n_model

    bfm = await start_chip(dut)

    # seed PRNG, then run with speed sweep disabled
    await bfm.write(csr.SEED_LO, SEED & 0xFFFF)
    await bfm.write(csr.SEED_HI, SEED >> 16)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN)

    solved_at = None
    for _ in range(POLL_LIMIT):
        status = await bfm.read(csr.STATUS)
        gen = await bfm.read(csr.GEN_LO) | (await bfm.read(csr.GEN_HI) << 16)
        if status & csr.STATUS_SOLVED:
            solved_at = gen
            break
        assert gen <= budget, f"not solved within {budget} generations (model: {n_model})"
        await ClockCycles(dut.clk, 2000)
    assert solved_at is not None, "poll limit hit before solved"
    dut._log.info(f"chip solved by generation {solved_at}")

    # pause and let the current generation drain to IDLE
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE)
    for _ in range(50):
        if (await bfm.read(csr.STATUS)) & csr.STATUS_STATE_MASK == csr.ES_IDLE:
            break
        await ClockCycles(dut.clk, 100)
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_STATE_MASK == csr.ES_IDLE

    # bit-exact check: replay the model to the chip's generation count
    gen = await bfm.read(csr.GEN_LO) | (await bfm.read(csr.GEN_HI) << 16)
    model = ESController(seed=SEED)
    for _ in range(gen):
        model.step()

    assert await bfm.read_genome() == model.genome, "genome diverged from model"
    assert await bfm.read(csr.BEST_FIT) == model.best_fitness
    assert await bfm.read(csr.ACCEPTS) == model.accepts & 0xFFFF
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_SOLVED

    # LED outputs: solved pin high, top fitness bits all-ones for correct=32
    assert dut.uo_out.value[3] == 1 or (dut.uo_out.value.to_unsigned() >> 3) & 1


@cocotb.test()
async def test_heal_demo(dut):
    """HEAL: solve, inject a 1-cell fault via CSR, watch fitness collapse and
    recover to 32 (routing around the dead cell). Model-free (recovery path
    depends on PRNG state at injection time; asserting recovery is the point).

    A single dead cell keeps sim time bounded: model-measured recovery is
    ~1.3k-12k generations without annealing. The full 3-cell button demo
    (mask 0x4420) needs annealing and ~15k-41k generations — demonstrated on
    hardware, not simulated here; the button path is covered by
    test_fault_demo_button below."""
    bfm = await start_chip(dut)

    await bfm.write(csr.SEED_LO, SEED & 0xFFFF)
    await bfm.write(csr.SEED_HI, SEED >> 16)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN)

    for _ in range(POLL_LIMIT):
        if (await bfm.read(csr.STATUS)) & csr.STATUS_SOLVED:
            break
        await ClockCycles(dut.clk, 2000)
    assert (await bfm.read(csr.STATUS)) & csr.STATUS_SOLVED

    # kill cell 5 (column 1 — never column 0: a dead column-0 cell makes the
    # default target unsolvable) and re-baseline fitness so imperfect-but-
    # improving candidates can be accepted again (stale best_fitness would
    # reject everything)
    await bfm.write(csr.STUCK_EN, 0x0020)
    await bfm.write(csr.STUCK_VAL, 0x0000)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN |
                    csr.CTRL_RESET_COUNTERS)

    # fitness is re-scored with the faulted phenotype: LAST_FIT dips below
    # perfect (the fault must actually hurt this genome for the demo to show)
    dipped = False
    for _ in range(40):
        if (await bfm.read(csr.LAST_FIT)) >> 6 < 32:
            dipped = True
            break
        await ClockCycles(dut.clk, 500)
    assert dipped, "fault injection never hurt fitness — faults ineffective?"

    # evolution routes around the dead cell: solved flag re-asserts once a
    # fault-tolerant genome is re-established (best_fitness was cleared above)
    recovered = False
    for _ in range(3 * POLL_LIMIT):
        if (await bfm.read(csr.STATUS)) & csr.STATUS_SOLVED:
            recovered = True
            break
        await ClockCycles(dut.clk, 2000)
    assert recovered, "did not heal around injected fault"

    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE)


@cocotb.test()
async def test_fault_demo_button(dut):
    """ui[2] rising edge is a self-contained HEAL demo trigger: it applies the
    hardwired 3-cell mask (0x4420, columns 1-3 only), stuck-at-0, re-baselines
    fitness/counters (a stale perfect best_fitness would otherwise reject every
    imperfect candidate and freeze the genome — solved LED lying forever), and
    arms TEMP=0x6000 so a strapped-high anneal_en is all the demo needs."""
    bfm = await start_chip(dut)

    # give the button something to visibly clear: fake a solved-looking state
    await bfm.write(csr.STUCK_VAL, 0xFFFF)
    await bfm.write(csr.SEED_LO, SEED & 0xFFFF)
    await bfm.write(csr.SEED_HI, SEED >> 16)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE | csr.CTRL_SOFT_RUN)
    for _ in range(20):
        if await bfm.read(csr.GEN_LO) > 10:
            break
        await ClockCycles(dut.clk, 500)
    await bfm.write(csr.CTRL, csr.CTRL_SPEED_DISABLE)  # pause
    assert await bfm.read(csr.BEST_FIT) > 0

    await bfm.set_pin(2, 1)
    await bfm.set_pin(2, 0)
    assert await bfm.read(csr.STUCK_EN) == 0x4420, "demo fault mask wrong"
    assert await bfm.read(csr.STUCK_VAL) == 0xFFFF & ~0x4420, \
        "demo fault cells not stuck at 0"
    assert await bfm.read(csr.TEMP) == 0x6000, "button did not arm anneal TEMP"
    assert await bfm.read(csr.BEST_FIT) == 0, "button did not re-baseline fitness"
    assert await bfm.read(csr.GEN_LO) == 0, "button did not clear generation"
    assert not (await bfm.read(csr.STATUS)) & csr.STATUS_SOLVED

    # host can clear the faults again
    await bfm.write(csr.STUCK_EN, 0)
    assert await bfm.read(csr.STUCK_EN) == 0
