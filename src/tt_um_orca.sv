/*
* Copyright (c) 2026 Abhi Alavilli
* SPDX-License-Identifier: Apache-2.0
*
* ORCA top level.
* STATUS (0x02): [2:0] fsm_state, [3] solved, [4] err_busy (sticky)
* CTRL   (0x01): [0] soft_run, [1] soft_reset_counters (pulse),
*                [2] pause_after_accept, [3] W1C err_busy, [4] speed_sweep_disable
*/

`default_nettype none

module tt_um_orca (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 1=output, 0=input)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // default target: PO0 = parity(pi), PO1 = pi[3]&pi[2] | pi[1]&pi[0]
  localparam logic [31:0] TARGET_RESET = 32'hBEC1_C194;

  // fault demo (ui[2]): kills cells 5, 10, 14 — columns 1-3 only, a dead
  // column-0 cell makes the default target unsolvable. one press does the
  // whole heal recipe: inject, re-baseline counters (stale best_fitness
  // would reject every imperfect candidate), arm anneal temp.
  localparam logic [15:0] FAULT_DEMO_MASK = 16'h4420;
  localparam logic [15:0] FAULT_DEMO_TEMP = 16'h6000;

  // ---- input synchronizers ----
  logic [1:0] run_sync, anneal_sync;
  logic [2:0] fault_sync;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      run_sync    <= '0;
      anneal_sync <= '0;
      fault_sync  <= '0;
    end else begin
      run_sync    <= {run_sync[0], ui_in[0]};
      anneal_sync <= {anneal_sync[0], ui_in[1]};
      fault_sync  <= {fault_sync[1:0], ui_in[2]};
    end
  end
  wire fault_demo_edge = fault_sync[1] & ~fault_sync[2];

  // ---- CSR registers ----
  logic        soft_run, pause_after_accept, speed_sweep_disable;
  logic        err_busy;
  logic [15:0] temperature, stuck_en, stuck_val, seed_lo;
  logic [31:0] target_flat;
  logic [5:0]  settle_tap_last;

  // ---- serial command interface ----
  logic        csr_we;
  logic [6:0]  csr_addr;
  logic [15:0] csr_wdata, csr_rdata;
  logic        ser_out;

  ser_cmd u_ser (
    .clk(clk), .rst_n(rst_n),
    .ser_data(ui_in[4]), .ser_shift(ui_in[5]), .ser_exec(ui_in[6]),
    .ser_out(ser_out),
    .csr_we(csr_we), .csr_addr(csr_addr), .csr_wdata(csr_wdata),
    .csr_rdata(csr_rdata)
  );

  // ---- PRNG ----
  logic        next_prng, seed_we;
  logic [31:0] prng_val;
  assign seed_we = csr_we && (csr_addr == 7'h0A);

  prng u_prng (
    .clk(clk), .rst_n(rst_n),
    .next(next_prng),
    .seed_we(seed_we), .seed_val({csr_wdata, seed_lo}),
    .prng_val(prng_val)
  );

  // ---- genome store ----
  logic        mut_valid, log_clear, log_replay;
  logic [7:0]  mut_addr;
  logic [11:0] gs_rdata;
  logic [131:0] genome;
  logic [2:0]  es_state;

  wire csr_allowed    = (es_state == 3'd0);  // IDLE
  wire genome_csr_sel = (csr_addr >= 7'h10) && (csr_addr <= 7'h1B);

  genome_store u_genome (
    .clk(clk), .rst_n(rst_n),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .csr_we(csr_we && genome_csr_sel), .csr_waddr(csr_addr[3:0]),
    .csr_wdata(csr_wdata[11:0]),
    .csr_raddr(csr_addr[3:0]), .csr_rdata(gs_rdata),
    .csr_allowed(csr_allowed),
    .genome(genome)
  );

  // ---- fabric + eval + settle sensor ----
  logic [3:0]  pi;
  logic [1:0]  po;
  logic [15:0] cell_out_dbg;
  logic [5:0]  settle_tap;
  logic        settle_mismatch, probe;
  logic [3:0]  pi_shadow;
  logic        eval_start, eval_done;
  logic [11:0] fitness;

  // pi_shadow is pi outside a speed sweep and the late-launched copy inside one
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

  // ---- ES controller ----
  logic [23:0] generation;
  logic [15:0] accepts;
  logic [11:0] best_fitness, last_fitness;
  logic        solved, accept_pulse;

  wire run_eff   = run_sync[1] | soft_run;
  wire ctr_clear = (csr_we && (csr_addr == 7'h01) && csr_wdata[1]) | fault_demo_edge;

  es_controller u_es (
    .clk(clk), .rst_n(rst_n),
    .run(run_eff), .anneal_en(anneal_sync[1]),
    .temperature(temperature),
    .ctr_clear(ctr_clear), .pause_after_accept(pause_after_accept),
    .next_prng(next_prng), .prng_val(prng_val),
    .mut_valid(mut_valid), .mut_addr(mut_addr),
    .log_clear(log_clear), .log_replay(log_replay),
    .eval_start(eval_start), .eval_done(eval_done), .fitness(fitness),
    .generation(generation), .accepts(accepts),
    .best_fitness(best_fitness), .last_fitness(last_fitness),
    .solved(solved), .state(es_state),
    .accept_pulse(accept_pulse)
  );

  // generation[8] flips every 256 generations — 1-flop decay detector
  logic prev_gen_b8;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) prev_gen_b8 <= 1'b0;
    else        prev_gen_b8 <= generation[8];
  end

  // ---- CSR writes ----
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      soft_run            <= 1'b0;
      pause_after_accept  <= 1'b0;
      speed_sweep_disable <= 1'b0;
      err_busy            <= 1'b0;
      temperature         <= '0;
      stuck_en            <= '0;
      stuck_val           <= '0;
      seed_lo             <= '0;
      target_flat         <= TARGET_RESET;
      settle_tap_last     <= 6'd63;
    end else begin
      if (csr_we) begin
        case (csr_addr)
          7'h01: begin
            soft_run            <= csr_wdata[0];
            pause_after_accept  <= csr_wdata[2];
            speed_sweep_disable <= csr_wdata[4];
            if (csr_wdata[3]) err_busy <= 1'b0;  // W1C
          end
          7'h08: temperature <= csr_wdata;
          7'h09: seed_lo     <= csr_wdata;
          7'h0B: stuck_en    <= csr_wdata;
          7'h0C: stuck_val   <= csr_wdata;
          7'h0D: for (int v = 0; v < 16; v++) target_flat[2*v]   <= csr_wdata[v];
          7'h0E: for (int v = 0; v < 16; v++) target_flat[2*v+1] <= csr_wdata[v];
          default: ;
        endcase
        // genome window write while evolving: dropped, sets sticky err_busy
        if (genome_csr_sel && !csr_allowed) err_busy <= 1'b1;
      end

      if (fault_demo_edge) begin
        stuck_en    <= stuck_en  | FAULT_DEMO_MASK;
        stuck_val   <= stuck_val & ~FAULT_DEMO_MASK;
        temperature <= FAULT_DEMO_TEMP;
      end

      // annealing temperature decay every 256 generations
      if (anneal_sync[1] && (generation[8] != prev_gen_b8))
        temperature <= temperature - (temperature >> 4);

      // record t_min whenever a speed sweep actually ran
      if (eval_done && (fitness[11:6] == 6'd32) && !speed_sweep_disable)
        settle_tap_last <= 6'd63 - fitness[5:0];
    end
  end

  // ---- CSR read mux ----
  always_comb begin
    if (genome_csr_sel) csr_rdata = {4'b0, gs_rdata};
    else begin
      case (csr_addr)
        7'h00: csr_rdata = 16'h08CA;
        7'h01: csr_rdata = {11'b0, speed_sweep_disable, err_busy, pause_after_accept, 1'b0, soft_run};
        7'h02: csr_rdata = {11'b0, err_busy, solved, es_state};
        7'h03: csr_rdata = {4'b0, best_fitness};
        7'h04: csr_rdata = {4'b0, last_fitness};
        7'h05: csr_rdata = generation[15:0];
        7'h06: csr_rdata = {8'b0, generation[23:16]};
        7'h07: csr_rdata = accepts;
        7'h08: csr_rdata = temperature;
        7'h09: csr_rdata = seed_lo;
        7'h0B: csr_rdata = stuck_en;
        7'h0C: csr_rdata = stuck_val;
        7'h0D: begin csr_rdata = '0; for (int v = 0; v < 16; v++) csr_rdata[v] = target_flat[2*v];   end
        7'h0E: begin csr_rdata = '0; for (int v = 0; v < 16; v++) csr_rdata[v] = target_flat[2*v+1]; end
        7'h1C: csr_rdata = {10'b0, settle_tap_last};
        default: csr_rdata = '0;
      endcase
    end
  end

  // ---- pin map ----
  assign uo_out[0]   = generation[13];            // heartbeat
  assign uo_out[1]   = (es_state != 3'd0);        // evolving
  assign uo_out[2]   = accept_pulse;
  assign uo_out[3]   = solved;
  assign uo_out[7:4] = best_fitness[11:8];

  assign uio_oe  = 8'b1011_1000;
  assign uio_out = {po[0], 1'b0, probe, accept_pulse, ser_out, 3'b000};

  // unused
  wire _unused = &{ena, ui_in[3], ui_in[7], uio_in, cell_out_dbg, 1'b0};

endmodule
