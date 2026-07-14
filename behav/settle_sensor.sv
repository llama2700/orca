`default_nettype none

// capture is clean iff tap_sel >= behav_tmin.
// behav_tmin resets to BEHAV_TMIN (0 = "infinitely fast fabric" => speed 63)
// and is pokeable hierarchically to fake a die speed.
module settle_sensor #(
  parameter logic [5:0] BEHAV_TMIN = 6'd0
)(
  input  logic clk, rst_n,
  input  logic [5:0] tap_sel,
  input  logic [3:0] pi_main,
  input  logic [1:0] po_main,
  input  logic [1:0] target_val,
  input  logic eval_start,
  output logic [3:0] pi_shadow,
  output logic mismatch,
  output logic probe
);

  logic [5:0] behav_tmin;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) behav_tmin <= BEHAV_TMIN;
  end

  // shadow PI launch
  assign pi_shadow = pi_main;

  // registered mismatch flag
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) mismatch <= 1'b0;
    else        mismatch <= (tap_sel < behav_tmin);
  end

  // tap strobe probe -> uio[5]; registered to keep clk out of the data path
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) probe <= 1'b0;
    else        probe <= (tap_sel != 6'd0);
  end

endmodule
