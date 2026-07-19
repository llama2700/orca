`default_nettype none

// Unit-test harness: es_controller + prng + genome_store, with the eval
// engine mocked from cocotb (drive fitness_in + eval_done in response to
// eval_start).
module es_harness (
  input  logic clk, rst_n,
  input  logic run, anneal_en,
  input  logic [15:0] temperature,
  input  logic seed_we,
  input  logic [31:0] seed_val,
  // mocked eval interface
  output logic eval_start,
  input  logic eval_done,
  input  logic [11:0] fitness_in,
  // observation
  output logic [131:0] genome,
  output logic [23:0] generation,
  output logic [15:0] accepts,
  output logic [11:0] best_fitness, last_fitness,
  output logic solved,
  output logic [2:0] state
);

  logic        next_prng, mut_valid, log_clear, log_replay;
  logic [7:0]  mut_addr;
  logic [31:0] prng_val;

  prng u_prng (
    .clk(clk), .rst_n(rst_n),
    .next(next_prng),
    .seed_we(seed_we), .seed_val(seed_val),
    .prng_val(prng_val)
  );

  genome_store u_genome (
    .clk(clk), .rst_n(rst_n),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .csr_we(1'b0), .csr_waddr(4'd0), .csr_wdata(12'd0),
    .csr_raddr(4'd0), .csr_rdata(),
    .csr_allowed(1'b0),
    .genome(genome)
  );

  es_controller u_es (
    .clk(clk), .rst_n(rst_n),
    .run(run), .anneal_en(anneal_en),
    .temperature(temperature),
    .ctr_clear(1'b0), .pause_after_accept(1'b0),
    .next_prng(next_prng), .prng_val(prng_val),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .eval_start(eval_start), .eval_done(eval_done), .fitness(fitness_in),
    .generation(generation), .accepts(accepts),
    .best_fitness(best_fitness), .last_fitness(last_fitness),
    .solved(solved), .state(state),
    .accept_pulse()
  );

endmodule
