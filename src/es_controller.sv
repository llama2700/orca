`default_nettype none

module es_controller (
  input  logic clk, rst_n,
  input  logic run,
  input  logic anneal_en,
  input  logic [15:0] temperature,
  // PRNG
  output logic next_prng,
  input  logic [31:0] prng_val,
  // Genome store
  output logic mut_valid,
  output logic [7:0] mut_addr,
  output logic log_clear,
  output logic log_replay,
  // Eval engine
  output logic eval_start,
  input  logic eval_done,
  input  logic [10:0] fitness,
  // CSR/Status
  output logic [23:0] generation,
  output logic [15:0] accepts,
  output logic [10:0] best_fitness,
  output logic [10:0] last_fitness,
  output logic solved,
  output logic [2:0] state
);

    // TODO

endmodule
