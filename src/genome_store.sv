`default_nettype none

// current genome + single-entry mutation log: revert re-flips the logged bit
// (xor is its own inverse), so no shadow copy of the genome is needed.
// csr window: word w = genome[12w +: 12] for w < 11, word 11 is padding.
// reads anytime; writes only while csr_allowed (ES idle).
module genome_store (
  input  logic clk, rst_n,
  // mutation port (from es_controller)
  input  logic        mut_valid,
  input  logic [7:0]  mut_addr,    // flip genome[mut_addr]; caller guarantees < 132
  input  logic        log_clear,   // on ACCEPT
  input  logic        log_replay,  // on REVERT: re-flips logged addr (single cycle)
  // CSR port
  input  logic        csr_we, input logic [3:0] csr_waddr, input logic [11:0] csr_wdata,
  input  logic [3:0]  csr_raddr, output logic [11:0] csr_rdata,
  input  logic        csr_allowed, // = (es_state == IDLE)
  output logic [131:0] genome
);

  logic [7:0] log_addr;
  logic       log_valid;

  logic        flip_en;
  logic [7:0]  flip_addr;
  logic [131:0] flip_mask;
  assign flip_en   = mut_valid | (log_replay & log_valid);
  assign flip_addr = mut_valid ? mut_addr : log_addr;
  always_comb begin
    flip_mask = '0;
    if (flip_en) flip_mask[flip_addr] = 1'b1;
  end

  logic csr_wr;
  assign csr_wr = csr_we && csr_allowed && (csr_waddr < 4'd11) &&
                  !mut_valid && !log_replay && !log_clear;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      genome    <= '0;
      log_addr  <= '0;
      log_valid <= 1'b0;
    end else begin
      genome <= genome ^ flip_mask;
      if (csr_wr) genome[12 * csr_waddr +: 12] <= csr_wdata;
      if (mut_valid) begin
        log_addr  <= mut_addr;
        log_valid <= 1'b1;
      end else if (log_replay || log_clear) begin
        log_valid <= 1'b0;
      end
    end
  end

  assign csr_rdata = (csr_raddr < 4'd11) ? genome[12 * csr_raddr +: 12] : 12'h0;

endmodule
