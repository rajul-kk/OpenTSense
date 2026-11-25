// Same falling-edge and row-end convention as G81b regions.py, on four testbench signals.
localparam integer TL_INTERVAL = 1000;
integer tl_fd;
integer tl_i;
integer tl_toggles [0:3];
reg tl_primed = 0;
reg [3:0] tl_previous = 0;
wire [3:0] tl_signals = {core_sleep, data_we, data_req, instr_req};
initial begin
  tl_fd = $fopen("rtl_activity.csv", "w");
  if (!tl_fd) $fatal(1, "could not open rtl_activity.csv");
  $fdisplay(tl_fd, "cycle,instr_req,data_req,data_we,core_sleep");
  for (integer j = 0; j < 4; j = j + 1) tl_toggles[j] = 0;
end
always @(negedge clk) if (rst_n) begin
  if (cyc > 0 && cyc % TL_INTERVAL == 0) begin
    $fdisplay(tl_fd, "%0d,%0d,%0d,%0d,%0d", cyc,
              tl_toggles[0], tl_toggles[1], tl_toggles[2], tl_toggles[3]);
    for (tl_i = 0; tl_i < 4; tl_i = tl_i + 1) tl_toggles[tl_i] = 0;
  end
  if (tl_primed) begin
    for (tl_i = 0; tl_i < 4; tl_i = tl_i + 1)
      tl_toggles[tl_i] = tl_toggles[tl_i] + int'(tl_signals[tl_i] != tl_previous[tl_i]);
  end
  tl_previous = tl_signals;
  tl_primed = 1;
end
final $fclose(tl_fd);
