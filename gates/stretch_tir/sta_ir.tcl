# Goal 14 (stretch, ungated): setup/hold slack and static IR drop of the routed ASAP7 Ibex at a die temperature.
# env as gates/g96/dry/load_routed.tcl (RES, CORNER, VTS), plus
#   CELL_F  cell-delay factor (derate_probe.py's ratio at the temperature; 1 = the library's 25 C)
#   WIRE_F  metal resistance factor rho(T) / rho(25 C), applied to the SPEF wire delay (net derate) and to every
#           tech layer's resistance before PDNSim
#   VCD, VCD_SCOPE  activity for the IR run ("none": no IR run); OUT  output directory
# PDNSim part as gates/g97/ir.tcl (frozen, so not sourced: it loads the design itself), FULL source model only.
source /work/gates/g96/dry/load_routed.tcl
set_propagated_clock [all_clocks]
set cf $::env(CELL_F)
set wf $::env(WIRE_F)
# cell delays and the flops' setup/hold check times, both by the measured gate-delay factor (a stated approximation
# for the check times, which were not characterised)
if {$cf != 1.0} {
  foreach t {-cell_delay -cell_check} { set_timing_derate $t -early $cf; set_timing_derate $t -late $cf }
}
if {$wf != 1.0} { set_timing_derate -net_delay -early $wf; set_timing_derate -net_delay -late $wf }
puts "SETUP:"
report_worst_slack -max -digits 3
puts "HOLD:"
report_worst_slack -min -digits 3
report_tns -digits 3
report_checks -path_delay max -format end -group_path_count 3 -digits 3
if {$::env(VCD) eq "none"} { exit }
set n 0
foreach layer [[ord::get_db_tech] getLayers] {
  set r [$layer getResistance]
  if {$r > 0} { $layer setResistance [expr {$r * $wf}]; incr n }
}
puts "SCALED_LAYERS $n by $wf"
read_vcd -scope $::env(VCD_SCOPE) $::env(VCD)
report_power -digits 8
foreach net {VDD VSS} {
  check_power_grid -net $net -error_file $::env(OUT)/check_$net.rpt
  analyze_power_grid -net $net -source_type FULL -voltage_file $::env(OUT)/v_${net}.csv -error_file $::env(OUT)/err_${net}.rpt
}
