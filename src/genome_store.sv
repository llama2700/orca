`default_nettype none

module genome_store (
  input  logic clk, rst_n,
  // mutation port (from es_controller/mutator)
  input  logic        mut_valid,
  input  logic [7:0]  mut_addr,    // flip genome[mut_addr]; caller guarantees < 132
  input  logic        log_clear,   // on ACCEPT
  input  logic        log_replay,  // on REVERT: re-flips logged addr (single cycle)
  // CSR port (word access, 12 x 12-bit words or agent's choice of packing)
  input  logic        csr_we, input logic [3:0] csr_waddr, input logic [11:0] csr_wdata,
  input  logic [3:0]  csr_raddr, output logic [11:0] csr_rdata,
  input  logic        csr_allowed, // = (es_state == IDLE)
  output logic [131:0] genome
);

    // TODO

endmodule
