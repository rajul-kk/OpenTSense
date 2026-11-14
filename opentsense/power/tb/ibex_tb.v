`timescale 1ns/1ps
// G30 testbench: routed ibex_core gate-level netlist + 32 KB single-cycle memory (instr and data ports).
// Plusargs: +hex=<file> +win_start=<cycle> +win_len=<cycles> +vcd=<file> +max=<cycles>
//           +half_ps=<half clock period, default 450> +in_ps=<default 0: when the memory's outputs reach the core after
//           the ideal edge; give the SDC's clock latency + input delay for a netlist with delays (G96)>
// Core outputs are sampled on the ideal edge: they change only after clock latency + clock-to-output, so that edge
// sees the previous cycle's settled value (STA checks they settle in time).
module tb;
  reg clk = 0, rst_n = 0;
  integer half_ps, in_ps;
  initial begin                               // settings first, then the clock
    if (!$value$plusargs("half_ps=%d", half_ps)) half_ps = 450;   // 900 ps clock (ASAP7 SDC)
    if (!$value$plusargs("in_ps=%d", in_ps)) in_ps = 0;
    if (half_ps <= 0 || in_ps < 0 || in_ps >= 2 * half_ps) $fatal(1, "need half_ps > 0 and 0 <= in_ps < 2*half_ps");
    forever #(half_ps / 1000.0) clk = ~clk;
  end
  reg [31:0] mem [0:8191];
  wire instr_req, data_req, data_we; wire [31:0] instr_addr, data_addr, data_wdata; wire [3:0] data_be;
  reg instr_gnt, instr_rvalid, data_gnt, data_rvalid; reg [31:0] instr_rdata, data_rdata;
  // the memory's registered outputs reach the core in_ps after the edge (a delayed copy, used only when in_ps > 0)
  wire [65:0] mem_out = {instr_rvalid, data_rvalid, instr_rdata, data_rdata}; reg [65:0] mem_out_d;
  always @(mem_out) if (in_ps > 0) mem_out_d <= #(in_ps / 1000.0) mem_out;
  wire [65:0] to_core = in_ps > 0 ? mem_out_d : mem_out;
  ibex_core dut (
    .clk_i(clk), .rst_ni(rst_n), .test_en_i(1'b0), .hart_id_i(32'd0), .boot_addr_i(32'd0),
    .instr_req_o(instr_req), .instr_gnt_i(instr_gnt), .instr_rvalid_i(to_core[65]), .instr_addr_o(instr_addr), .instr_rdata_i(to_core[63:32]), .instr_err_i(1'b0),
    .data_req_o(data_req), .data_gnt_i(data_gnt), .data_rvalid_i(to_core[64]), .data_we_o(data_we), .data_be_o(data_be),
    .data_addr_o(data_addr), .data_wdata_o(data_wdata), .data_rdata_i(to_core[31:0]), .data_err_i(1'b0),
    .irq_software_i(1'b0), .irq_timer_i(1'b0), .irq_external_i(1'b0), .irq_fast_i(15'd0), .irq_nm_i(1'b0),
    .debug_req_i(1'b0), .fetch_enable_i(1'b1), .alert_minor_o(), .alert_major_o(), .core_sleep_o());
  // memory: grant immediately, data valid next cycle
  always @(*) begin instr_gnt = instr_req; data_gnt = data_req; end
  integer i; reg [31:0] w;
  reg trace = 0; initial trace = $test$plusargs("trace");
  reg done = 0; reg [31:0] checksum = 0; integer cyc = 0, ws = 0, wl = 0, mx = 0, done_cyc = -1; reg [1023:0] hex, vcd;
  always @(posedge clk) begin
    instr_rvalid <= instr_req; data_rvalid <= data_req;
    if (instr_req) instr_rdata <= mem[instr_addr[14:2]];
    if (data_req) begin
      if (data_we) begin
        w = mem[data_addr[14:2]];
        if (data_be[0]) w[7:0] = data_wdata[7:0];   if (data_be[1]) w[15:8] = data_wdata[15:8];
        if (data_be[2]) w[23:16] = data_wdata[23:16]; if (data_be[3]) w[31:24] = data_wdata[31:24];
        mem[data_addr[14:2]] <= w; data_rdata <= 32'hx;
        if (data_addr == 32'h8004 && data_wdata == 1) done <= 1;
        if (data_addr == 32'h8000) checksum <= data_wdata;
      end else data_rdata <= mem[data_addr[14:2]];
    end
  end
  always @(posedge clk) begin
    cyc <= cyc + 1;
    if (done && done_cyc < 0) done_cyc = cyc;
    if (trace && cyc % 500 == 0) $display("TRACE cyc=%0d instr_addr=%08x req=%b data_req=%b", cyc, instr_addr, instr_req, data_req);
    if (done && done_cyc >= 0 && cyc > done_cyc + 5 && ws > cyc) begin
      $display("RESULT checksum=%08x done=%0d done_cycle=%0d cycles=%0d", checksum, done, done_cyc, cyc); $finish;
    end
    if (cyc == ws) begin $dumpfile(vcd); $dumpvars(0, tb.dut); end
    if (cyc == ws + wl) $dumpoff;
    if (cyc >= mx) begin
      $display("RESULT checksum=%08x done=%0d done_cycle=%0d cycles=%0d", checksum, done, done_cyc, cyc); $finish;
    end
  end
  initial begin
    for (i = 0; i < 8192; i = i + 1) mem[i] = 32'h0000006f;   // jal x0,0 everywhere else
    if (!$value$plusargs("hex=%s", hex)) hex = "prog.hex";
    if (!$value$plusargs("vcd=%s", vcd)) vcd = "win.vcd";
    if (!$value$plusargs("win_start=%d", ws)) ws = 400;
    if (!$value$plusargs("win_len=%d", wl)) wl = 1000;
    if (!$value$plusargs("max=%d", mx)) mx = ws + wl + 10;
    $readmemh(hex, mem);
    instr_rvalid = 0; data_rvalid = 0; instr_rdata = 0; data_rdata = 0;
    repeat (5) @(posedge clk); if (in_ps > 0) #(in_ps / 1000.0); rst_n = 1;
  end
endmodule
