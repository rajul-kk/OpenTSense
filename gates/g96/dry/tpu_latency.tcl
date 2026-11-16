# Decision 10 evidence (G96 TPU): clock insertion delay at the flops and input-path checks, as the SDC stands
# (no set_clock_latency). env as load_routed.tcl.
source /work/gates/g96/dry/load_routed.tcl
set_propagated_clock [get_clocks core_clock]
report_clock_min_period
puts "== insertion delay (clock arrival at register clock pins)"
report_clock_skew -setup
report_clock_skew -hold
report_clock_latency -clock core_clock
puts "== input paths"
report_checks -path_delay min -from [all_inputs -no_clocks] -format end -group_path_count 5
report_checks -path_delay max -from [all_inputs -no_clocks] -format end -group_path_count 5
report_worst_slack -min
report_worst_slack -max
