`default_nettype none

// Unit-test harness: eval_engine + fabric + settle_sensor.
// cocotb drives genome/target directly and pokes u_sensor.forced_tmin to fake
// a die speed. the fabric hangs off pi_shadow like in the top so the shadow
// launch path is exercised too.
module eval_harness (
  input  logic clk, rst_n,
  input  logic eval_start,
  input  logic speed_sweep_disable,
  input  logic [31:0]  target_flat,
  input  logic [131:0] genome,
  input  logic [15:0]  stuck_en, stuck_val,
  output logic eval_done,
  output logic [11:0] fitness
);

  logic [3:0]  pi, pi_shadow;
  logic [1:0]  po;
  logic [15:0] cell_out_dbg;
  logic [5:0]  settle_tap;
  logic        settle_mismatch, probe;

  fabric u_fabric (
    .pi(pi_shadow), .genome(genome),
    .stuck_en(stuck_en), .stuck_val(stuck_val),
    .po(po), .cell_out_dbg(cell_out_dbg)
  );

  settle_sensor u_sensor (
    .clk(clk), .rst_n(rst_n),
    .tap_sel(settle_tap),
    .pi_main(pi), .po_main(po),
    .target_val(target_flat[2 * pi +: 2]),
    .eval_start(eval_start),
    .pi_shadow(pi_shadow),
    .mismatch(settle_mismatch), .probe(probe)
  );

  eval_engine u_eval (
    .clk(clk), .rst_n(rst_n),
    .eval_start(eval_start), .speed_sweep_disable(speed_sweep_disable),
    .target_flat(target_flat),
    .settle_tap(settle_tap), .settle_mismatch(settle_mismatch),
    .pi(pi), .po(po),
    .eval_done(eval_done), .fitness(fitness)
  );

  wire _unused = &{probe, cell_out_dbg, 1'b0};

endmodule
