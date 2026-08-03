`default_nettype none

import orca_pkg::*;

module fabric #(
  parameter integer FAULT_EN = 1
)(
  input  logic [PI_WIDTH-1:0]    pi,
  input  logic [GENOME_SIZE-1:0] genome,
  input  logic [NUM_CELLS-1:0]   stuck_en,
  input  logic [NUM_CELLS-1:0]   stuck_val,
  output logic [PO_WIDTH-1:0]    po,
  output logic [NUM_CELLS-1:0]   cell_out_dbg
);

  logic [FABRIC_ROWS-1:0] net [FABRIC_COLS+1];
  assign net[0] = pi;

  generate
    for (genvar c = 0; c < FABRIC_COLS; c++) begin : col_gen
      for (genvar r = 0; r < FABRIC_ROWS; r++) begin : row_gen
        localparam integer I = c * FABRIC_ROWS + r;
        localparam integer G = I * GENE_W;

        fabric_cell #(
          .FAULT_EN(FAULT_EN)
        ) u_cell (
          .in       (net[c]),
          .lut      (genome[G +: LUT_BITS]),
          .sel_a    (genome[G + LUT_BITS +: SEL_W]),
          .sel_b    (genome[G + LUT_BITS + SEL_W +: SEL_W]),
          .stuck_en (stuck_en[I]),
          .stuck_val(stuck_val[I]),
          .out      (net[c+1][r])
        );

        assign cell_out_dbg[I] = net[c+1][r];
      end
    end

    for (genvar k = 0; k < PO_WIDTH; k++) begin : po_gen
      assign po[k] = net[FABRIC_COLS][genome[ (NUM_CELLS * GENE_W) + (k * SEL_W) +: SEL_W]];
    end
  endgenerate

endmodule
