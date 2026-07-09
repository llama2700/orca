def get_bits(genome, s, w):
    # get w bits from a 'genome' starting at index s (0-indexed, LSB=0)
    return (genome >> s) & ((1 << w) - 1)

class CGPFabric:
    def __init__(self):
        pass

    def decode(self, genome):
        # configure 4x4 netlist of cells from the genome
        # each cell is a dict with keys 'lut', 'sel_a', 'sel_b'
        cells = []
        for i in range(16):
            base = 8 * i
            lut = get_bits(genome, base, 4)
            sel_a = get_bits(genome, base + 4, 2)
            sel_b = get_bits(genome, base + 6, 2)
            cells.append({'lut': lut, 'sel_a': sel_a, 'sel_b': sel_b})

        # extra 4b: select cells in the last col for the final output
        po0_sel = get_bits(genome, 128, 2)
        po1_sel = get_bits(genome, 130, 2)
        return {'cells': cells, 'po_sel': [po0_sel, po1_sel]}

    def sim(self, genome, stuck_en, stuck_val, pi_val, netlist=None):
        """Simulate one input vector. Returns (po0, po1, cells16) where cells16
        packs every cell's output bit at index 4*col + row (== cell_out_dbg).
        Pass a pre-decoded netlist when sweeping vectors (16x fewer decodes)."""
        if netlist is None:
            netlist = self.decode(genome)
        cells = netlist['cells']
        po_sel = netlist['po_sel']

        col_outputs = [[0] * 4 for _ in range(4)]
        for col in range(4):
            for row in range(4):
                cell_idx = col * 4 + row
                cell = cells[cell_idx]

                if col == 0:
                    in_a = (pi_val >> cell['sel_a']) & 1
                    in_b = (pi_val >> cell['sel_b']) & 1
                else:
                    in_a = col_outputs[col-1][cell['sel_a']]
                    in_b = col_outputs[col-1][cell['sel_b']]

                # LUT execution: index is {in_a, in_b} (A is MSB)
                lut_idx = (in_a << 1) | in_b
                lut_out = (cell['lut'] >> lut_idx) & 1

                # Fault injection overrides phenotype
                if (stuck_en >> cell_idx) & 1:
                    lut_out = (stuck_val >> cell_idx) & 1

                col_outputs[col][row] = lut_out

        cells16 = 0
        for col in range(4):
            for row in range(4):
                cells16 |= col_outputs[col][row] << (col * 4 + row)
        return col_outputs[3][po_sel[0]], col_outputs[3][po_sel[1]], cells16

    def evaluate(self, genome, stuck_en, stuck_val, target, speed_val=0):
        """
        eval engine model draft 
        target: list of 16 integers (0-3) representing the expected PO[1:0] for PI=0..15
        return 'fitness': integer representing {correct[5:0], speed[5:0]}
        """
        correct = 0
        netlist = self.decode(genome)

        for pi_val in range(16):
            po0, po1, _ = self.sim(genome, stuck_en, stuck_val, pi_val, netlist)

            po0_target = target[pi_val] & 1
            po1_target = (target[pi_val] >> 1) & 1
            
            if po0 == po0_target:
                correct += 1
            if po1 == po1_target:
                correct += 1

        # speed only applies if correct == 32
        if correct != 32:
            speed = 0
        else:
            speed = speed_val
        fitness = (correct << 6) | speed
        return fitness
