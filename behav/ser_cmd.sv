`default_nettype none

// Frame: 24 bits MSB-first {rw(1), addr(7), data(16)}. rw=1 write, rw=0 read.
// - ser_shift rising edge: shifts ser_data into the command register and
//   shifts one response bit out (ser_out shows the MSB *before* the pulse).
// - ser_exec rising edge: rw=1 -> csr_we pulse; rw=0 -> loads response
//   register from csr_rdata (csr_addr holds the exec'd address afterwards).
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

  // 2-flop synchronizers + rising-edge detectors
  logic [2:0] shift_sync, exec_sync;
  logic [1:0] data_sync;
  logic       shift_edge, exec_edge;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      shift_sync <= '0;
      exec_sync  <= '0;
      data_sync  <= '0;
    end else begin
      shift_sync <= {shift_sync[1:0], ser_shift};
      exec_sync  <= {exec_sync[1:0], ser_exec};
      data_sync  <= {data_sync[0], ser_data};
    end
  end

  assign shift_edge = shift_sync[1] & ~shift_sync[2];
  assign exec_edge  = exec_sync[1] & ~exec_sync[2];

  logic [23:0] cmd;
  logic [15:0] resp;
  logic [6:0]  addr_q;
  logic        we_q;

  // For reads, csr_addr must present the new address on the exec cycle so
  // csr_rdata is the addressed register. Bypass the address register then.
  logic [6:0]  csr_addr_eff;
  logic [15:0] csr_rdata_at_exec;
  assign csr_addr_eff      = exec_edge ? cmd[22:16] : addr_q;
  assign csr_rdata_at_exec = csr_rdata;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cmd    <= '0;
      resp   <= '0;
      addr_q <= '0;
      we_q   <= 1'b0;
    end else begin
      we_q <= 1'b0;
      if (shift_edge) begin
        cmd  <= {cmd[22:0], data_sync[1]};
        resp <= {resp[14:0], 1'b0};
      end else if (exec_edge) begin
        addr_q <= cmd[22:16];
        if (cmd[23]) we_q <= 1'b1;   // write: csr_we pulse next cycle
        else         resp <= csr_rdata_at_exec;
      end
    end
  end

  assign csr_addr  = csr_addr_eff;
  assign csr_we    = we_q;
  assign csr_wdata = cmd[15:0];
  assign ser_out   = resp[15];

endmodule
