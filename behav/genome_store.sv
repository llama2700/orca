`default_nettype none

// Genome CSR window packing: word w (w = 0..10) = genome[12w +: 12]; word 11
// reads 0 and ignores writes (11 x 12 = 132 exactly).
// Reads are allowed anytime (racy while evolving, but harmless); writes are
// gated by csr_allowed.
module genome_store (
  input  logic clk, rst_n,
  // mutation port (from es_controller/mutator)
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

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      genome    <= '0;
      log_addr  <= '0;
      log_valid <= 1'b0;
    end else begin
      if (mut_valid) begin
        genome[mut_addr] <= ~genome[mut_addr];
        log_addr  <= mut_addr;
        log_valid <= 1'b1;
      end else if (log_replay) begin
        // XOR is its own inverse: restores pre-mutation genome
        if (log_valid) genome[log_addr] <= ~genome[log_addr];
        log_valid <= 1'b0;
      end else if (log_clear) begin
        log_valid <= 1'b0;
      end else if (csr_we && csr_allowed && (csr_waddr < 4'd11)) begin
        genome[12 * csr_waddr +: 12] <= csr_wdata;
      end
    end
  end

  assign csr_rdata = (csr_raddr < 4'd11) ? genome[12 * csr_raddr +: 12] : 12'h0;

endmodule
