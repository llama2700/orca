`default_nettype none

module settle_sensor (
  input  logic clk, rst_n,
  input  logic [4:0] tap_sel,
  input  logic [3:0] pi_main,
  input  logic [1:0] po_main,
  input  logic [1:0] target_val,
  input  logic eval_start,
  output logic [3:0] pi_shadow,
  output logic mismatch,
  output logic probe
);

    // TODO

endmodule
