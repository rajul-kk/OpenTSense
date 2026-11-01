`timescale 1ps/1ps
// G36 testbench: routed ASAP7 tpu netlist, stimulus from hex (130-bit {w_valid, w_data, a_valid, a_data}), result rows logged.
module tb;
  reg clk = 0, rst = 1; always #100 clk = ~clk;          // 200 ps clock (SDC)
  reg [129:0] stim [0:2399]; reg w_valid = 0, a_valid = 0; reg [63:0] w_data = 0, a_data = 0;
  wire c_valid; wire [255:0] c_data;
  tpu dut (.clk(clk), .rst(rst), .w_valid(w_valid), .w_data(w_data), .a_valid(a_valid), .a_data(a_data), .c_valid(c_valid), .c_data(c_data));
  integer cyc = 0, fo, ws, wl; reg [1023:0] hex, vcd, outf;
  initial begin
    if (!$value$plusargs("hex=%s", hex)) hex = "stim.hex"; if (!$value$plusargs("vcd=%s", vcd)) vcd = "w.vcd"; if (!$value$plusargs("out=%s", outf)) outf = "c.txt";
    if (!$value$plusargs("win_start=%d", ws)) ws = 600; if (!$value$plusargs("win_len=%d", wl)) wl = 1000;
    $readmemh(hex, stim); fo = $fopen(outf, "w");
    repeat (5) @(posedge clk); #1 rst = 0;
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
