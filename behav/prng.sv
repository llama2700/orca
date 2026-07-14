`default_nettype none

// 32-bit xorshift (marsaglia 13/17/5)
module prng (
  input  logic clk, rst_n,
  input  logic next,
  input  logic seed_we,
  input  logic [31:0] seed_val,
  output logic [31:0] prng_val
);

  localparam logic [31:0] RESET_SEED = 32'hECEBCAFE;

  logic [31:0] state, x1, x2, x3;

  assign x1 = state ^ (state << 13);
  assign x2 = x1 ^ (x1 >> 17);
  assign x3 = x2 ^ (x2 << 5);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)        state <= RESET_SEED;
    else if (seed_we)  state <= (seed_val == 32'h0) ? RESET_SEED : seed_val;
    else if (next)     state <= x3;
  end

  assign prng_val = state;

endmodule
