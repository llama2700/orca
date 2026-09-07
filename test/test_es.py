"""ES controller vs the reference model, bit-exact.

The eval engine is mocked from Python: on each eval_start we hand the DUT the
fitness the golden model computed for the same generation. Genome, accept/
revert decisions, and every counter must then track the model exactly —
including genome restoration after every REVERT. Toplevel: es_harness."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, with_timeout

from model.es_ref import ESController

N_GENERATIONS = 300
GEN_TIMEOUT_NS = 100_000


async def start(dut, seed):
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    dut.run.value = 0
    dut.anneal_en.value = 0
    dut.temperature.value = 0
    dut.seed_we.value = 0
    dut.seed_val.value = 0
    dut.eval_done.value = 0
    dut.fitness_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    dut.seed_we.value = 1
    dut.seed_val.value = seed
    await ClockCycles(dut.clk, 1)
    dut.seed_we.value = 0
    await ClockCycles(dut.clk, 1)


async def lockstep(dut, model, generations, respond):
    """Run N generations; `respond(model_step_result)` returns the fitness fed
    to the DUT. Checks DUT state against the model after every generation."""
    for gen in range(generations):
        await with_timeout(RisingEdge(dut.eval_start), GEN_TIMEOUT_NS, "ns")

        accept, mut_addr, new_fitness = model.step()

        # DUT genome now carries the model's candidate mutation
        got = dut.genome.value.to_unsigned()
        want = model.genome if accept else model.genome ^ (1 << mut_addr)
        assert got == want, f"gen {gen}: mutated genome mismatch (addr {mut_addr})"

        await ClockCycles(dut.clk, 3)
        dut.fitness_in.value = respond(new_fitness)
        dut.eval_done.value = 1
        await ClockCycles(dut.clk, 1)
        dut.eval_done.value = 0

        # DECIDE -> ACCEPT/REVERT -> GEN_TICK
        await ClockCycles(dut.clk, 4)
        assert dut.genome.value.to_unsigned() == model.genome, \
            f"gen {gen}: genome diverged after {'accept' if accept else 'revert'}"
        assert dut.generation.value.to_unsigned() == model.generation
        assert dut.accepts.value.to_unsigned() == model.accepts
        assert dut.best_fitness.value.to_unsigned() == model.best_fitness
        assert dut.last_fitness.value.to_unsigned() == new_fitness
        assert dut.solved.value == (model.best_fitness >> 6 == 32)


async def drain_to_idle(dut):
    """Drop run and keep answering in-flight evals until the FSM parks —
    the FSM only exits via GEN_TICK, so a started generation must complete."""
    dut.run.value = 0
    for _ in range(50):
        if dut.state.value.to_unsigned() == 0:
            return
        if int(dut.eval_start.value):
            await ClockCycles(dut.clk, 2)
            dut.fitness_in.value = 0
            dut.eval_done.value = 1
            await ClockCycles(dut.clk, 1)
            dut.eval_done.value = 0
        await ClockCycles(dut.clk, 2)
    raise AssertionError("did not return to IDLE")


@cocotb.test()
async def test_es_lockstep(dut):
    """Plain (1+1) ES, no annealing."""
    seed = 0x12345678
    await start(dut, seed)
    model = ESController(seed=seed)

    dut.run.value = 1
    await lockstep(dut, model, N_GENERATIONS, respond=lambda f: f)
    await drain_to_idle(dut)


@cocotb.test()
async def test_es_lockstep_anneal(dut):
    """Annealing path: temperature draws must match the model bit-exactly."""
    seed = 0xCAFE0001
    temp = 0x4000
    await start(dut, seed)
    model = ESController(seed=seed)
    model.anneal_en = True
    model.temperature = temp

    dut.anneal_en.value = 1
    dut.temperature.value = temp
    dut.run.value = 1
    # NB: temperature decay lives in the top level's CSR block, not the ES
    # controller, and 300 generations stay below the first decay at gen 256
    # only if we stop earlier — keep to 200 so the constant-temp model matches.
    await lockstep(dut, model, 200, respond=lambda f: f)
    await drain_to_idle(dut)


@cocotb.test()
async def test_es_monotone_best_fitness(dut):
    """With anneal off, best_fitness never decreases."""
    seed = 0x0BADF00D
    await start(dut, seed)
    model = ESController(seed=seed)

    best_seen = 0
    dut.run.value = 1
    for _ in range(5):
        await lockstep(dut, model, 40, respond=lambda f: f)
        best = dut.best_fitness.value.to_unsigned()
        assert best >= best_seen
        best_seen = best
    await drain_to_idle(dut)
