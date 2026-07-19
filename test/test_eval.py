"""Eval engine fitness vs golden model, with the settle sensor's t_min forced
to known values — checks the lexicographic {correct, speed} packing and the
binary search. Toplevel: eval_harness."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, with_timeout

from model.cgp_ref import CGPFabric

EVAL_TIMEOUT_NS = 200_000


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    dut.eval_start.value = 0
    dut.speed_sweep_disable.value = 0
    dut.genome.value = 0
    dut.target_flat.value = 0
    dut.stuck_en.value = 0
    dut.stuck_val.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


def flat(target):
    return sum((target[v] & 3) << (2 * v) for v in range(16))


async def run_eval(dut):
    dut.eval_start.value = 1
    await ClockCycles(dut.clk, 1)
    dut.eval_start.value = 0
    await with_timeout(RisingEdge(dut.eval_done), EVAL_TIMEOUT_NS, "ns")
    await ClockCycles(dut.clk, 1)
    return dut.fitness.value.to_unsigned()


def own_truth_table(model, genome, stuck_en=0, stuck_val=0):
    """Target equal to the genome's actual behavior => correct == 32."""
    t = []
    for v in range(16):
        po0, po1, _ = model.sim(genome, stuck_en, stuck_val, v)
        t.append((po1 << 1) | po0)
    return t


@cocotb.test()
async def test_correctness_only(dut):
    """Random genome + random target: correct < 32 almost surely => speed = 0,
    fitness matches the model exactly."""
    await start(dut)
    random.seed(0xE7A1)
    model = CGPFabric()

    for _ in range(20):
        genome = random.getrandbits(132)
        target = [random.getrandbits(2) for _ in range(16)]
        dut.genome.value = genome
        dut.target_flat.value = flat(target)
        got = await run_eval(dut)
        want = model.evaluate(genome, 0, 0, target, speed_val=0)
        assert got == want, f"fitness {got:#x} != model {want:#x} (genome={genome:#x})"


@cocotb.test()
async def test_speed_sweep_forced_tmin(dut):
    """correct == 32 by construction; force behav_tmin=K => speed = 63-K."""
    await start(dut)
    random.seed(0xE7A2)
    model = CGPFabric()

    for k in (0, 1, 7, 15, 31, 62, 63):
        genome = random.getrandbits(132)
        target = own_truth_table(model, genome)
        dut.genome.value = genome
        dut.target_flat.value = flat(target)
        dut.u_sensor.behav_tmin.value = k
        got = await run_eval(dut)
        assert got == (32 << 6) | (63 - k), \
            f"tmin={k}: fitness {got:#x}, expected speed {63-k}"


@cocotb.test()
async def test_speed_sweep_disable(dut):
    """speed_sweep_disable forces speed=0 even for perfect genomes."""
    await start(dut)
    random.seed(0xE7A3)
    model = CGPFabric()

    genome = random.getrandbits(132)
    target = own_truth_table(model, genome)
    dut.genome.value = genome
    dut.target_flat.value = flat(target)
    dut.u_sensor.behav_tmin.value = 5
    dut.speed_sweep_disable.value = 1
    assert await run_eval(dut) == 32 << 6
    # and re-enabling brings speed back
    dut.speed_sweep_disable.value = 0
    assert await run_eval(dut) == (32 << 6) | (63 - 5)


@cocotb.test()
async def test_lexicographic_dominance(dut):
    """A fully-correct slow genome must always outrank an almost-correct fast
    one: fitness(32, 0) > fitness(31, 31)."""
    await start(dut)
    random.seed(0xE7A4)
    model = CGPFabric()

    genome = random.getrandbits(132)
    target = own_truth_table(model, genome)

    # perfect but slowest die
    dut.genome.value = genome
    dut.target_flat.value = flat(target)
    dut.u_sensor.behav_tmin.value = 63
    fit_correct_slow = await run_eval(dut)

    # break one output bit of the target => correct = 31, fastest die
    broken = list(target)
    broken[3] ^= 1
    dut.target_flat.value = flat(broken)
    dut.u_sensor.behav_tmin.value = 0
    fit_wrong_fast = await run_eval(dut)

    assert fit_correct_slow == (32 << 6) | 0
    assert fit_wrong_fast == (31 << 6) | 0  # speed suppressed when correct < 32
    assert fit_correct_slow > fit_wrong_fast


@cocotb.test()
async def test_eval_with_faults(dut):
    """Faults corrupt the phenotype the eval engine scores."""
    await start(dut)
    random.seed(0xE7A5)
    model = CGPFabric()

    genome = random.getrandbits(132)
    target = own_truth_table(model, genome)
    stuck_en, stuck_val = 0x4420, 0x0000  # the demo fault pattern
    dut.genome.value = genome
    dut.target_flat.value = flat(target)
    dut.stuck_en.value = stuck_en
    dut.stuck_val.value = stuck_val
    got = await run_eval(dut)
    want = model.evaluate(genome, stuck_en, stuck_val, target, speed_val=0)
    if want >> 6 == 32:  # faults happened not to matter: speed sweep runs
        want |= 63 - dut.u_sensor.behav_tmin.value.to_unsigned()
    assert got == want
