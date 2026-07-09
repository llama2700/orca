import pytest
from model.prng_ref import Xorshift32
from model.cgp_ref import CGPFabric
from model.es_ref import ESController

def test_xorshift32():
    # Hand-computed cases for xorshift
    prng = Xorshift32(0x12345678)
    
    # 0x12345678
    # x ^= x << 13: 12345678 ^ 8acf0000 = 98fb5678
    # x ^= x >> 17: 98fb5678 ^ 00004c7d = 98fb1a05
    # x ^= x << 5:  98fb1a05 ^ 1f6340a0 = 87985aa5
    
    val1 = prng.next()
    assert val1 == 0x87985aa5
    assert prng.state == val1
    
    val2 = prng.next()
    assert val2 != val1

    # 0-seed falls back to the reset seed
    prng0 = Xorshift32(0)
    assert prng0.state == 0xECEBCAFE

def test_cgp_fabric():
    fabric = CGPFabric()
    # Simple genome: all cells pass through in_a (sel_a=0)
    # in_a for col0 is pi[0] if sel_a=0.
    # lut for pass through in_a: if in_a is 0 -> 0, if 1 -> 1.
    # lut idx = {in_a, in_b} (A is MSB). for in_a=0, idx=0,1 -> out=0. for in_a=1, idx=2,3 -> out=1.
    # lut = 1100 in binary = 0xC.
    genome = 0
    # Set all LUTs to 0xC
    for i in range(16):
        genome |= (0xC << (8 * i))
    
    # PO selects: let's select cell 12 (col3, row0) for PO0, cell 13 for PO1
    # cell 12 is index 0 in col3. so po0_sel = 0.
    # cell 13 is index 1 in col3. so po1_sel = 1.
    genome |= (0 << 128)
    genome |= (1 << 130)

    # Every cell passes in_a with sel_a=0, so both POs chain back to pi[0].
    # Against an all-zero target each PO is correct on the 8 vectors with
    # pi[0]==0: correct = 16 exactly (speed field 0 — model default).
    target = [0]*16
    fitness = fabric.evaluate(genome, 0, 0, target)
    assert fitness == 16 << 6

def test_es_controller():
    es = ESController(seed=42)
    # run a few steps
    for _ in range(100):
        es.step()

    assert es.generation == 100
    assert es.best_fitness > 0

    # known-good seed solves the default target at a pinned generation
    # (regression anchor for the whole model stack; seed 42 never solves)
    es = ESController(seed=0x0DDBA11)
    while (es.best_fitness >> 6) < 32:
        es.step()
        assert es.generation <= 4841, "model diverged: seed 0xDDBA11 must solve at gen 4841"
    assert es.generation == 4841
