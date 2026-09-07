`default_nettype none

// Correctness sweep: for v = 0..15 drive pi = v, wait SETTLE_WAIT cycles,
// compare po against target, accumulate per-bit correct count (max 32).
// Speed sweep (only if correct == 32 and !speed_sweep_disable): binary-search
// the minimum settle-sensor tap t_min (64 taps) at which all 16 vectors capture
// cleanly (settle_mismatch never asserts); speed = 63 - t_min. Otherwise speed = 0.
// fitness = {correct[5:0], speed[5:0]} — lexicographic by construction.
module eval_engine (
  input  logic clk, rst_n,
  input  logic eval_start,
  input  logic speed_sweep_disable,
  // Target truth table, packed: target[v] = target_flat[2v+1 -: 2] for v in 0..15
  input  logic [31:0] target_flat,
  // Settle sensor interface
  output logic [5:0] settle_tap,
  input  logic       settle_mismatch,
  // Fabric interface
  output logic [3:0] pi,
  input  logic [1:0] po,
  // Results
  output logic eval_done,
  output logic [11:0] fitness // {correct[5:0], speed[5:0]}
);

  localparam int SETTLE_WAIT = 4;

  typedef enum logic [2:0] {
    E_IDLE, E_SETTLE, E_CAPTURE, E_CHECK, S_SETTLE, S_CAPTURE, S_NEXT, E_DONE
  } state_e;

  state_e     state;
  logic [3:0] vec;
  logic [2:0] wait_cnt;
  logic [5:0] correct;
  logic [5:0] lo, hi;
  logic       fail;

  logic [5:0] mid, new_lo, new_hi;
  assign mid    = ({1'b0, lo} + {1'b0, hi}) >> 1;  // 7-bit sum: 6-bit + overflows
  assign new_lo = fail ? mid + 1 : lo;   // failed pass: t_min above mid
  assign new_hi = fail ? hi : mid;       // clean pass: t_min at or below mid

  logic [1:0] tgt;
  assign tgt = target_flat[2 * vec +: 2];

  assign pi         = vec;
  assign settle_tap = (state == S_SETTLE || state == S_CAPTURE || state == S_NEXT) ? mid : 6'd0;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state     <= E_IDLE;
      vec       <= '0;
      wait_cnt  <= '0;
      correct   <= '0;
      lo        <= '0;
      hi        <= '0;
      fail      <= 1'b0;
      eval_done <= 1'b0;
      fitness   <= '0;
    end else begin
      eval_done <= 1'b0;
      case (state)
        E_IDLE: if (eval_start) begin
          vec      <= '0;
          correct  <= '0;
          wait_cnt <= SETTLE_WAIT - 1;
          state    <= E_SETTLE;
        end

        // ---- correctness sweep ----
        E_SETTLE: begin
          if (wait_cnt == 0) state <= E_CAPTURE;
          else               wait_cnt <= wait_cnt - 1;
        end
        E_CAPTURE: begin
          correct <= correct + {5'b0, po[0] == tgt[0]} + {5'b0, po[1] == tgt[1]};
          if (vec == 4'd15) state <= E_CHECK;
          else begin
            vec      <= vec + 1;
            wait_cnt <= SETTLE_WAIT - 1;
            state    <= E_SETTLE;
          end
        end
        E_CHECK: begin
          if (correct == 6'd32 && !speed_sweep_disable) begin
            lo       <= 6'd0;
            hi       <= 6'd63;
            vec      <= '0;
            fail     <= 1'b0;
            wait_cnt <= SETTLE_WAIT - 1;
            state    <= S_SETTLE;
          end else begin
            fitness <= {correct, 6'd0};
            state   <= E_DONE;
          end
        end

        // ---- speed sweep: binary search min clean tap ----
        S_SETTLE: begin
          if (wait_cnt == 0) state <= S_CAPTURE;
          else               wait_cnt <= wait_cnt - 1;
        end
        S_CAPTURE: begin
          fail <= fail | settle_mismatch;
          if (vec == 4'd15) state <= S_NEXT;
          else begin
            vec      <= vec + 1;
            wait_cnt <= SETTLE_WAIT - 1;
            state    <= S_SETTLE;
          end
        end
        S_NEXT: begin
          lo       <= new_lo;
          hi       <= new_hi;
          fail     <= 1'b0;
          vec      <= '0;
          wait_cnt <= SETTLE_WAIT - 1;
          if (new_lo == new_hi) begin
            // interval collapsed: t_min = new_lo
            fitness <= {6'd32, 6'd63 - new_lo};
            state   <= E_DONE;
          end else begin
            state <= S_SETTLE;
          end
        end

        E_DONE: begin
          eval_done <= 1'b1;
          state     <= E_IDLE;
        end

        default: state <= E_IDLE;
      endcase
    end
  end

endmodule
