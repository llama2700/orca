`default_nettype none

// P4: CSR genome writes are dropped when !csr_allowed and no mutation port
// activity — genome must be stable.
module p4_top (
  input logic clk, rst_n,
  input logic csr_we,
  input logic [3:0] csr_waddr,
  input logic [11:0] csr_wdata,
  input logic csr_allowed
);

  logic [131:0] genome;

  genome_store u_genome (
    .clk(clk), .rst_n(rst_n),
    .mut_valid(1'b0), .mut_addr(8'd0),
    .log_clear(1'b0), .log_replay(1'b0),
    .csr_we(csr_we), .csr_waddr(csr_waddr), .csr_wdata(csr_wdata),
    .csr_raddr(4'd0), .csr_rdata(),
    .csr_allowed(csr_allowed),
    .genome(genome));

`ifdef FORMAL
  logic [131:0] genome_prev;
  logic past_valid;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin past_valid <= 0; genome_prev <= '0; end
    else begin past_valid <= 1; genome_prev <= genome; end
  end
  logic blocked_write_q;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) blocked_write_q <= 0;
    else blocked_write_q <= csr_we && !csr_allowed;
  end
  always_comb if (past_valid && blocked_write_q)
    assert (genome == genome_prev);
`endif

endmodule
