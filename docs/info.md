## How it works

ORCA is a self-optimizing, self-healing evolvable logic engine. It contains:

1. **A CGP-style reconfigurable fabric** — a 4×4 grid of cells(4-bit LUT) with 2 
   4:1 input muxes.
   Column 0 reads the 4 primary inputs and column *c* reads only column *c−1*
   Two outputs are selected from the last column, circuit is defined by a 132-bit genome

2. **An on-chip (1+1) evolution strategy.** Each generation, a xorshift32 PRNG
   picks one genome bit to flip. An eval engine scores the resulting circuit
   against a 16-row × 2-output target truth table (fitness = correct outputs,
   circuit *speed* using razor sensor). Better or equal mutants are kept. 
   Worse ones are reverted. Simulated annealing accepts some worse mutants with
   decaying probability.

3. **A settle-time sensor.** clk runs down a 64 cell delay line, a tap mux
   picks one delayed edge off it and that edge launches the fabric inputs late,
   while capture stays on the main clock. The eval engine binary searches how
   far that window can shrink before the outputs break, and the surviving tap
   is the speed half of fitness. With `CTRL.speed_sweep_disable` set, fitness
   is correctness only and the sensor is never used.

At reset the target is parity + AND-OR, so the chip evolves with no host
attached. LEDs on `uo_out[7:4]` count as fitness converges and `uo_out[3]`
lights when solved. The serial bit-bang interface (24-bit command frames on
`ui_in[4:6]`, output on `uio[3]`) exposes CSRs for Target truth table (desired function),
genome read/write, PRNG seed, fault injection, annealing temperature, fitness
counters, and the settle-tap measurement.

**Demos:** EVOLVE (converge on any loaded truth table), HEAL (inject
faults and evolution will route around the dead cells) and CHARACTERIZE
(load a genome, run one sweep, read the min stable tap back from SETTLE_TAP,
compare across dies). The delay line spans about one 25 MHz period on a
typical die, so run CHARACTERIZE at 25 to 33 MHz. Slower and the window never
gets short enough to fail, faster and the deep taps wrap past the next edge.

## How to test

Smoke test with no host: strap `ui_in[0]` (run) high, clock at 25 MHz, and
watch `uo_out[7:4]` climb within a second; `uo_out[3]` = solved,
`uo_out[0]` = generation heartbeat, `uo_out[1]` = evolving.

Host-free HEAL demo: additionally strap `ui_in[1]` (anneal) high; once solved,
pulse `ui_in[2]` — solved drops and the fitness LEDs dip, then recover over a
few seconds as evolution routes around the three dead cells.

With the demo board host tools (`host/` in the repo):

```
tt_orca.py --port /dev/ttyACM0 id            # read 0x08CA ("ORCA")
tt_orca.py ... seed 0xDEADBEEF               # reseed PRNG
tt_orca.py ... run                           # start evolution
tt_orca.py ... poll                          # generation / fitness / accepts
live_plot.py --port /dev/ttyACM0             # live fitness plot
tt_orca.py ... inject-fault 0x4420 0x0000    # HEAL demo (kills 3 cells)
characterize.py --port /dev/ttyACM0          # CHARACTERIZE, settle tap per genome
```

The full cocotb suite (`test/`) runs with
`make -B` and unit suites with `make -B UNIT=fabric|fault|eval|es`; the
evolution end-to-end test is bit-exact against the Python golden model in
`model/`.

## External hardware

None required. Optional: scope on `uio[4]` (accept pulse trigger) or `uio[5]`
(settle-sensor tap strobe); LEDs/PMOD on `uo_out`.

## Pinout

| Pin | Dir | Function |
|---|---|---|
| ui[0] | in | run (evolution enable) |
| ui[1] | in | anneal_en |
| ui[2] | in | fault_demo (rising edge kills 3 cells) |
| ui[3] | in | reserved |
| ui[4] | in | ser_data |
| ui[5] | in | ser_shift |
| ui[6] | in | ser_exec |
| ui[7] | in | reserved |
| uo[0] | out | heartbeat (generation counter bit) |
| uo[1] | out | evolving |
| uo[2] | out | accept pulse |
| uo[3] | out | solved |
| uo[7:4] | out | best_fitness[11:8] |
| uio[3] | out | ser_out (serial response) |
| uio[4] | out | scope trigger (= accept pulse) |
| uio[5] | out | settle-sensor tap strobe |
| uio[7] | out | fabric PO0 live |
