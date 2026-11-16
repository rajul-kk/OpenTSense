# G97: static IR drop of one window on a routed ORFS ASAP7 layout (registration.md), in the ORFS image.
# env as gates/g96/dry/load_routed.tcl (RES, CORNER, VTS), plus VCD ("none" = default activity), VCD_SCOPE,
# OUT (output directory), SOURCES (source models, e.g. "FULL BUMPS"), HELP (1: print the tool's help first).
source /work/gates/g96/dry/load_routed.tcl
if {[info exists ::env(HELP)] && $::env(HELP)} {
  foreach c {analyze_power_grid check_power_grid set_pdnsim_net_voltage} { puts "HELP $c:"; help $c }
}
if {$::env(VCD) ne "none"} {
  read_vcd -scope $::env(VCD_SCOPE) $::env(VCD)
  report_activity_annotation
}
report_power -digits 8
foreach net {VDD VSS} {
  puts "CHECK $net:"
  check_power_grid -net $net -error_file $::env(OUT)/check_$net.rpt
  foreach src $::env(SOURCES) {
    puts "ANALYZE $net $src:"
    analyze_power_grid -net $net -source_type $src -voltage_file $::env(OUT)/v_${net}_$src.csv \
      -error_file $::env(OUT)/err_${net}_$src.rpt
  }
}
