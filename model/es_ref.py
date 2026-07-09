from .prng_ref import Xorshift32
from .cgp_ref import CGPFabric

class ESController:
    def __init__(self, seed: int = 0xECEBCAFE, target=None):
        self.prng = Xorshift32(seed)
        self.fabric = CGPFabric()
        self.genome = 0
        self.generation = 0
        self.accepts = 0
        self.best_fitness = 0
        self.temperature = 0
        self.anneal_en = False
        # fault injection (phenotype only, like the chip's stuck_* CSRs)
        self.stuck_en = 0
        self.stuck_val = 0
        
        # default parity target
        if target is None:
            self.target = [0] * 16
            for pi in range(16):
                # PO0 = parity(pi), PO1 = pi[3] & pi[2] | pi[1] & pi[0]
                po0 = (pi ^ (pi >> 1) ^ (pi >> 2) ^ (pi >> 3)) & 1
                po1 = (((pi >> 3) & (pi >> 2)) | ((pi >> 1) & pi)) & 1
                self.target[pi] = (po1 << 1) | po0
        else:
            self.target = target

    def step(self):
        """Run one generation of mutation and evaluation."""
        # 1. Mutate: draw PRNG until address < 132
        mut_addr = 255
        while mut_addr >= 132:
            self.prng.next()
            mut_addr = self.prng.state & 0xFF
            
        # Flip the bit
        new_genome = self.genome ^ (1 << mut_addr)
        
        # 2. Evaluate
        new_fitness = self.fabric.evaluate(new_genome, self.stuck_en, self.stuck_val, self.target)
        
        # 3. Decide
        # the anneal draw uses the prng state left by the mutation draws
        # (no extra tick)
        accept = False
        if new_fitness >= self.best_fitness:
            accept = True
        elif self.anneal_en and (self.prng.state & 0xFFFF) < self.temperature:
            accept = True
                
        if accept:
            self.genome = new_genome
            self.best_fitness = new_fitness
            self.accepts += 1
            
        self.generation += 1
        
        # Temperature decay
        if self.anneal_en and (self.generation % 256) == 0:
            self.temperature = self.temperature - (self.temperature >> 4)
            
        return accept, mut_addr, new_fitness
