`default_nettype none

module ser_cmd (
  input  logic clk, rst_n,
  input  logic ser_data,
  input  logic ser_shift,
  input  logic ser_exec,
  output logic ser_out,
  // CSR bus
  output logic        csr_we,
  output logic [6:0]  csr_addr,
  output logic [15:0] csr_wdata,
  input  logic [15:0] csr_rdata
);

    // TODO

endmodule
