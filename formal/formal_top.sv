`default_nettype none

// Formal harness: es_controller + genome_store + prng with the
// eval engine abstracted. The genome shadow register exists only here.
module formal_top (
  input logic clk, rst_n,
  input logic run, anneal_en,
  input logic [15:0] temperature,
  input logic eval_done,
  input logic [11:0] fitness
);

  logic next_prng, mut_valid, log_clear, log_replay, eval_start;
  logic [7:0]   mut_addr;
  logic [31:0]  prng_val;
  logic [131:0] genome;
  logic [23:0]  generation;
  logic [15:0]  accepts;
  logic [11:0]  best_fitness, last_fitness;
  logic         solved;
  logic [2:0]   state;

  prng u_prng (.clk(clk), .rst_n(rst_n), .next(next_prng),
               .seed_we(1'b0), .seed_val(32'h0), .prng_val(prng_val));

  genome_store u_genome (
    .clk(clk), .rst_n(rst_n),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .csr_we(1'b0), .csr_waddr(4'd0), .csr_wdata(12'd0),
    .csr_raddr(4'd0), .csr_rdata(), .csr_allowed(1'b0),
    .genome(genome));

  es_controller u_es (
    .clk(clk), .rst_n(rst_n), .run(run), .anneal_en(anneal_en),
    .temperature(temperature), .ctr_clear(1'b0), .pause_after_accept(1'b0),
    .next_prng(next_prng), .prng_val(prng_val),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .eval_start(eval_start), .eval_done(eval_done), .fitness(fitness),
    .generation(generation), .accepts(accepts),
    .best_fitness(best_fitness), .last_fitness(last_fitness),
    .solved(solved), .state(state), .accept_pulse());

`ifdef FORMAL
  reg f_past_valid = 1'b0;
  always_ff @(posedge clk) f_past_valid <= 1'b1;
  always_comb begin
    if (!f_past_valid) assume (!rst_n);
    else               assume (rst_n);
  end

  // fairness: eval answers within 8 cycles (abstract eval engine)
  logic [3:0] eval_pending;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)            eval_pending <= 0;
    else if (eval_start)   eval_pending <= 1;
    else if (eval_done)    eval_pending <= 0;
    else if (eval_pending != 0 && eval_pending < 15) eval_pending <= eval_pending + 1;
  end
  always_comb begin
    assume (!(eval_pending > 8) || eval_done);          // bounded response
    assume (!eval_done || eval_pending != 0 || eval_start); // no spurious done
  end

  // ---- P1: with annealing off, best_fitness is monotone non-decreasing ----
  // anneal_en is quasi-static (pin/CSR): assume it doesn't toggle mid-run,
  // otherwise a DECIDE-time annealed accept can legitimately lower
  // best_fitness just as the guard re-arms. fitness is constrained to what
  // the eval engine can produce (correct <= 32).
  logic [11:0] best_prev;
  logic        past_valid, anneal_q;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin past_valid <= 0; best_prev <= 0; anneal_q <= 1'b1; end
    else begin past_valid <= 1; best_prev <= best_fitness; anneal_q <= anneal_en; end
  end
  always_comb begin
    assume (fitness[11:6] <= 6'd32);
    if (past_valid) assume (anneal_en == anneal_q);
    if (past_valid && !anneal_en) assert (best_fitness >= best_prev);
  end

  // ---- P2: REVERT restores the exact pre-mutation genome ----
  logic [131:0] genome_shadow;
  logic         shadow_valid;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin shadow_valid <= 0; genome_shadow <= '0; end
    else if (mut_valid) begin genome_shadow <= genome; shadow_valid <= 1; end
    else if (log_replay && shadow_valid) shadow_valid <= 0;
  end
  logic replay_q;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) replay_q <= 0;
    else replay_q <= log_replay && shadow_valid;
  end
  always_comb if (replay_q) assert (genome == genome_shadow);

  // ---- P3: no deadlock — EVAL_WAIT always exits (given fairness above);
  //      MUTATE exits (assume PRNG eventually yields < 132) ----
  logic [4:0] mutate_cnt;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)               mutate_cnt <= 0;
    else if (state == 3'd1)   mutate_cnt <= mutate_cnt + 1;
    else                      mutate_cnt <= 0;
  end
  always_comb assume (!(mutate_cnt > 16) || prng_val[7:0] < 132);
  always_comb assert (mutate_cnt < 30);

  logic [4:0] wait_cnt;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)             wait_cnt <= 0;
    else if (state == 3'd2) wait_cnt <= wait_cnt + 1;
    else                    wait_cnt <= 0;
  end
  always_comb assert (wait_cnt < 16);
`endif

endmodule
