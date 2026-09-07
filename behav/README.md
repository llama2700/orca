# behav/ — behavioral reference RTL

Complete, simulation-verified behavioral implementations of every module.
The cocotb suites run against this tree by default.

## Contracts (the tests assume these)

- **LUT index**: `lut[{a, b}]` — input A is the index MSB.
- **PRNG**: xorshift32 13/17/5; state advances one step per `next` cycle;
  `seed_we` with value 0 loads 0xECEBCAFE. DECIDE's anneal draw reuses the
  state left by the final MUTATE draw (no extra tick).
- **Genome CSR window**: words 0..10 = `genome[12w +: 12]`; word 11 (0x1B)
  reads 0 / write ignored. Reads allowed anytime; writes only in IDLE
  (violation sets sticky `err_busy`).
- **STATUS (0x02)**: `[2:0]` fsm_state, `[3]` solved, `[4]` err_busy.
- **CTRL (0x01)**: `[0]` soft_run, `[1]` soft_reset_counters (write-1 pulse,
  reads 0), `[2]` pause_after_accept, `[3]` W1C err_busy, `[4]` speed_sweep_disable.
- **ES FSM encoding**: IDLE=0, MUTATE=1, EVAL_WAIT=2, DECIDE=3, ACCEPT=4,
  REVERT=5, GEN_TICK=6 (3-bit `state`, exported in STATUS).
- **Eval**: SETTLE_WAIT=4 cycles per vector; fitness `{correct[5:0], speed[5:0]}`;
  speed sweep binary-searches min clean tap `t_min`, `speed = 63 - t_min`;
  skipped (speed=0) unless correct==32 and !speed_sweep_disable.
- **Settle sensor**: capture is clean iff `tap_sel >= behav_tmin`;
  `behav_tmin` resets to parameter `BEHAV_TMIN` (0) and is poked
  hierarchically by the eval tests to fake a die speed.
- **Fault demo (ui[2] rising edge)** is self-contained (no host needed): ORs
  0x4420 into STUCK_EN (kills cells 5, 10, 14 stuck at 0 — columns 1-3 only),
  re-baselines fitness/counters (same effect as CTRL.soft_reset_counters —
  without this the stale perfect best_fitness rejects every candidate and the
  solved LED lies forever), and arms TEMP=0x6000. Strapping anneal_en (ui[1])
  high is the only other requirement. Host clears faults via CSR. **Never
  kill a column-0 cell**: the default target needs all four column-0 pair
  functions (xor01+xor23 for parity, and10+and32 for the AND-OR), so any dead
  column-0 cell makes it unsolvable. Model-measured: 3-cell faults heal in
  ~15k-41k generations with annealing, never without; a 1-cell fault heals
  without annealing (~1.3k-12k).
- **pause_after_accept**: latches after an accepted generation; cleared by
  deasserting run.
- **soft_reset_counters clears best/last fitness too**: without it HEAL
  deadlocks — after fault injection the stale best_fitness (32<<6) rejects
  every imperfect candidate and the genome freezes. The demo recipe is:
  inject fault, pulse CTRL bit1, evolution re-baselines and heals.
- **SETTLE_TAP (0x1C)**: updated only when a speed sweep actually ran;
  resets to 63.
