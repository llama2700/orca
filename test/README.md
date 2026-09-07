# ORCA test suites

cocotb 2.0 + Icarus, The suites run against the RTL in `src/`.

```sh
pip install -r requirements.txt   # or use the repo .venv

make -B                           # full chip: test_reset, test_serial, test_evolution_e2e
make -B UNIT=fabric               # 1000 random genomes vs model (fabric standalone)
make -B UNIT=fault                # stuck-at injection vs model
make -B UNIT=eval                 # eval engine, settle sensor harness (forced t_min sweep)
make -B UNIT=es                   # ES controller lockstep vs the golden model
```

The evolution end-to-end test seeds the PRNG over the serial BFM and checks the
chip bit exact against the Python golden model in `model/` (genome, fitness,
accepts at the same generation). `test_heal_demo` injects a 1-cell fault and
asserts recovery; `test_fault_demo_button` checks the self-contained HEAL trigger 
(mask + re-baseline + TEMP arm).

GLS: 

```sh
make -B GATES=yes
```

