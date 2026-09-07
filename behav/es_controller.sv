`default_nettype none

// (1+1) ES:
//   MUTATE  — tick PRNG once per cycle until prng_val[7:0] < 132; that value
//             is the mutation address (single mut_valid pulse).
//   DECIDE  — accept iff fitness >= best_fitness, or anneal draw passes using
//             the PRNG state left from the final MUTATE draw (no extra tick).
module es_controller (
  input  logic clk, rst_n,
  input  logic run,
  input  logic anneal_en,
  input  logic [15:0] temperature,
  input  logic ctr_clear,           // extra: CTRL.soft_reset_counters
  input  logic pause_after_accept,  // extra: CTRL.pause_after_accept
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
  input  logic [11:0] fitness,
  // CSR/Status
  output logic [23:0] generation,
  output logic [15:0] accepts,
  output logic [11:0] best_fitness,
  output logic [11:0] last_fitness,
  output logic solved,
  output logic [2:0] state,
  output logic accept_pulse         // extra: 1-cycle pulse on accept
);

  typedef enum logic [2:0] {
    S_IDLE = 3'd0, S_MUTATE = 3'd1, S_EVAL_WAIT = 3'd2, S_DECIDE = 3'd3,
    S_ACCEPT = 3'd4, S_REVERT = 3'd5, S_GEN_TICK = 3'd6
  } state_e;

  state_e st;
  logic drawn;         // at least one PRNG tick since entering MUTATE
  logic eval_started;
  logic accepted;      // this generation ended in an accept
  logic paused;        // pause_after_accept latch; cleared when run drops

  logic candidate_ok;
  assign candidate_ok = drawn && (prng_val[7:0] < 8'd132);

  logic accept_c;
  assign accept_c = (last_fitness >= best_fitness) ||
                    (anneal_en && (prng_val[15:0] < temperature));

  // combinational strobes
  assign next_prng    = (st == S_MUTATE) && !candidate_ok;
  assign mut_valid    = (st == S_MUTATE) && candidate_ok;
  assign mut_addr     = prng_val[7:0];
  assign log_clear    = (st == S_ACCEPT);
  assign log_replay   = (st == S_REVERT);
  assign eval_start   = (st == S_EVAL_WAIT) && !eval_started;
  assign accept_pulse = (st == S_ACCEPT);
  assign solved       = (best_fitness[11:6] == 6'd32);
  assign state        = st;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      st           <= S_IDLE;
      drawn        <= 1'b0;
      eval_started <= 1'b0;
      accepted     <= 1'b0;
      paused       <= 1'b0;
      generation   <= '0;
      accepts      <= '0;
      best_fitness <= '0;
      last_fitness <= '0;
    end else begin
      if (!run) paused <= 1'b0;
      if (ctr_clear) begin
        // clears fitness state too so HEAL can re-baseline after fault
        // injection (stale best_fitness would otherwise block all accepts)
        generation   <= '0;
        accepts      <= '0;
        best_fitness <= '0;
        last_fitness <= '0;
      end

      case (st)
        S_IDLE: begin
          if (run && !paused) begin
            drawn <= 1'b0;
            st    <= S_MUTATE;
          end
        end

        S_MUTATE: begin
          drawn <= 1'b1;
          if (candidate_ok) begin
            eval_started <= 1'b0;
            st           <= S_EVAL_WAIT;
          end
        end

        S_EVAL_WAIT: begin
          eval_started <= 1'b1;
          if (eval_done) begin
            last_fitness <= fitness;
            st           <= S_DECIDE;
          end
        end

        S_DECIDE: begin
          if (accept_c) st <= S_ACCEPT;
          else          st <= S_REVERT;
        end

        S_ACCEPT: begin
          if (!ctr_clear) best_fitness <= last_fitness;
          if (!ctr_clear) accepts <= accepts + 1;
          accepted <= 1'b1;
          st       <= S_GEN_TICK;
        end

        S_REVERT: begin
          accepted <= 1'b0;
          st       <= S_GEN_TICK;
        end

        S_GEN_TICK: begin
          if (!ctr_clear) generation <= generation + 1;
          if (accepted && pause_after_accept) paused <= 1'b1;
          drawn <= 1'b0;
          if (run && !(accepted && pause_after_accept)) st <= S_MUTATE;
          else                                          st <= S_IDLE;
        end

        default: st <= S_IDLE;
      endcase
    end
  end

endmodule
