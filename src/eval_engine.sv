`default_nettype none

module eval_engine (
  input  logic clk, rst_n,
  input  logic eval_start,
  input  logic speed_sweep_disable,
  // Target truth table
  input  logic [1:0] target [15:0],
  // Settle sensor interface
  output logic [4:0] settle_tap,
  input  logic       settle_mismatch,
  // Fabric interface
  output logic [3:0] pi,
  input  logic [1:0] po,
  // Results
  output logic eval_done,
  output logic [10:0] fitness // {correct[5:0], speed[4:0]}
);

    // TODO

endmodule
