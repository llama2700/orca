class Xorshift32:
    def __init__(self, seed: int = 0xECEBCAFE):
        if seed == 0:
            seed = 0xECEBCAFE
        self.state = seed & 0xFFFFFFFF

    # marsaglia 13/17/5 xorshift
    def next(self) -> int:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x
        return self.state
