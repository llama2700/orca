`default_nettype none

import orca_pkg::*;

module fabric_cell #(
  parameter integer FAULT_EN = 1 
)(
  input  logic [FABRIC_ROWS-1:0]        in,
  input  logic [LUT_BITS-1:0]           lut,
  input  logic [SEL_W-1:0]              sel_a,
  input  logic [SEL_W-1:0]              sel_b,
  input  logic                          stuck_en,
  input  logic                          stuck_val,
  output logic                          out
);

  logic o_int;
  assign o_int = lut[{in[sel_a], in[sel_b]}];

  generate
    if (FAULT_EN) begin
      assign out = (stuck_en) ? stuck_val : o_int;
    end else begin
      assign out = o_int;
    end
  endgenerate

endmodule
