`default_nettype none

// razor-style settle-time sensor 
// clk runs down a 64 cell delay chain, a 64:1 mux picks one position off it
// and that delayed edge clocks a shadow copy of pi. during a speed sweep the
// fabric is fed from the shadow register, so it only gets T_clk - delay(t)
// to settle before the main clock captures po. tap t reads chain position
// 63 - t (64 - t cells of delay), so the delay shrinks as t grows and the
// clean region is t >= t_min, which is what the eval engine's search wants.
//
// mismatch pipeline, E0 = the edge where the eval engine changes vec:
//   E0+d   shadow launches the new vector (E1+d when d < clk-to-q, tap 63)
//   E1     cap = po != target, masked while shadow != pi (launch not in yet)
//   E2 E3  two sync stages
//   E4     mismatch = cap(E1) | cap(E2), the eval engine samples it at E5
// the cap(E2) term covers the late launch case. every capture after that
// has had a full period on a stable input and is clean regardless.
module settle_sensor #(
  parameter logic [5:0] FORCED_TMIN = 6'd0
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

  localparam int TAPS = 64;

  // ---- delay line ----
  // chain[0] is clk, chain[i] is i cells of delay. keep on every cell and
  // the nets are dont_touch in config.json, or the flow eats the whole thing
  logic [TAPS:0] chain;
`ifdef SYNTHESIS
  assign chain[0] = clk;
  generate
    for (genvar i = 0; i < TAPS; i++) begin : g_dly
      (* keep *) sky130_fd_sc_hd__dlygate4sd3_1 u_dly (.A(chain[i]), .X(chain[i+1]));
    end
  endgenerate
`else
  // zero delay sim, one assign rather than 65 chained ones (icarus crawls)
  assign chain = {(TAPS + 1){clk}};
`endif

  // tap t -> chain[64 - t], tap 63 still has one cell between clk and the
  // launch edge so the shadow register isn't racing clk-to-q of pi_main.
  // the mux only sees chain[64:1]. indexing chain[] directly left chain[0],
  // which is clk, as an unreachable leg of the mux and sta then timed the
  // shadow register off it
  logic [TAPS-1:0] taps;
  logic late_launch;
  assign taps        = chain[TAPS:1];
  assign late_launch = taps[6'd63 - tap_sel];

  // ---- shadow launch, the only flops on late_launch ----
  logic [3:0] shadow_q;
  always_ff @(posedge late_launch or negedge rst_n) begin
    if (!rst_n) shadow_q <= '0;
    else        shadow_q <= pi_main;
  end

  // the eval engine only drives a nonzero tap inside a speed sweep and every
  // sweep opens at tap 31, so "seen a nonzero tap since eval_start" tracks
  // the sweep. the combinational term is there so the very first vector is
  // already launched from the shadow register and not from pi_main
  logic sweep_q, sweeping;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)          sweep_q <= 1'b0;
    else if (eval_start) sweep_q <= 1'b0;
    else if (tap_sel != 6'd0) sweep_q <= 1'b1;
  end
  assign sweeping  = sweep_q | (tap_sel != 6'd0);
  assign pi_shadow = sweeping ? shadow_q : pi_main;

  // ---- capture, main clock ----
  // shadow_q == pi_main is quasi static (pi_main holds for 5 cycles) and only
  // says whether the launch has happened yet, so a stale po is not counted
  logic launched, cap, sync1, sync2;
  assign launched = (shadow_q == pi_main);

`ifndef SYNTHESIS
  // sim only, fakes a die speed. test_eval pokes u_sensor.forced_tmin
  logic [5:0] forced_tmin;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) forced_tmin <= FORCED_TMIN;
  end
  wire forced_fail = (tap_sel < forced_tmin);
`else
  wire forced_fail = 1'b0;
`endif

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cap      <= 1'b0;
      sync1    <= 1'b0;
      sync2    <= 1'b0;
      mismatch <= 1'b0;
    end else begin
      cap      <= launched & (po_main != target_val);
      sync1    <= cap;
      sync2    <= sync1;
      mismatch <= sync1 | sync2 | forced_fail;
    end
  end

  // tap strobe probe -> uio[5], registered to keep clk out of the data path.
  // raw delayed edge is not exported
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) probe <= 1'b0;
    else        probe <= (tap_sel != 6'd0);
  end

endmodule
