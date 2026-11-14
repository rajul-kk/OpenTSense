`timescale 1ps/1ps
// G36 testbench: routed ASAP7 tpu netlist, stimulus from hex (130-bit {w_valid, w_data, a_valid, a_data}), result rows logged.
module tb;
  // +half_ps=<half clock period, default 100> +in_ps=<default 0: when the stimulus reaches the core after the ideal
  // edge; give the SDC's clock latency + input delay for a netlist with delays (G96)>
  reg clk = 0, rst = 1; integer half_ps, in_ps;
  initial begin                               // settings first, then the clock
    if (!$value$plusargs("half_ps=%d", half_ps)) half_ps = 100;   // 200 ps clock (SDC)
    if (!$value$plusargs("in_ps=%d", in_ps)) in_ps = 0;
    if (half_ps <= 0 || in_ps < 0 || in_ps >= 2 * half_ps) $fatal(1, "need half_ps > 0 and 0 <= in_ps < 2*half_ps");
    forever #(half_ps) clk = ~clk;
  end
  reg [129:0] stim [0:2399]; reg w_valid = 0, a_valid = 0; reg [63:0] w_data = 0, a_data = 0;
  wire c_valid; wire [255:0] c_data;
  // the stimulus reaches the core in_ps after the edge (a delayed copy, used only when in_ps > 0)
  wire [129:0] st = {w_valid, w_data, a_valid, a_data}; reg [129:0] st_d;
  always @(st) if (in_ps > 0) st_d <= #(in_ps) st;
  wire [129:0] to_core = in_ps > 0 ? st_d : st;
  tpu dut (.clk(clk), .rst(rst), .w_valid(to_core[129]), .w_data(to_core[128:65]), .a_valid(to_core[64]), .a_data(to_core[63:0]), .c_valid(c_valid), .c_data(c_data));
  integer cyc = 0, fo, ws, wl; reg [1023:0] hex, vcd, outf;
  initial begin
    if (!$value$plusargs("hex=%s", hex)) hex = "stim.hex"; if (!$value$plusargs("vcd=%s", vcd)) vcd = "w.vcd"; if (!$value$plusargs("out=%s", outf)) outf = "c.txt";
    if (!$value$plusargs("win_start=%d", ws)) ws = 600; if (!$value$plusargs("win_len=%d", wl)) wl = 1000;
    $readmemh(hex, stim); fo = $fopen(outf, "w");
    repeat (5) @(posedge clk); if (in_ps > 0) #(in_ps); else #1; rst = 0;
  end
  always @(posedge clk) begin
    if (!rst) begin
      {w_valid, w_data, a_valid, a_data} <= stim[cyc]; cyc <= cyc + 1;
      if (c_valid) $fdisplay(fo, "%h", c_data);
      if (cyc == ws) begin $dumpfile(vcd); $dumpvars(0, tb.dut); end
      if (cyc == ws + wl) $dumpoff;
      if (cyc == 2399) begin $fclose(fo); $display("DONE cycles=%0d", cyc); $finish; end
    end
  end
endmodule
