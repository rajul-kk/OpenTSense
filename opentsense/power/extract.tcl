# Run inside the ORFS image via `make ... RUN_SCRIPT=<this> run` after a finished flow.
# Writes inst_loc.csv (die box, then instance centres in um) and prints OpenSTA power (total and per instance).
# env: OUT_DIR (where inst_loc.csv goes), VCD (optional activity file), VCD_SCOPE (default tb/dut)
source $::env(SCRIPTS_DIR)/load.tcl
load_design 6_final.odb 6_final.sdc
if {[info exists ::env(VCD)] && $::env(VCD) ne ""} {
  set scope [expr {[info exists ::env(VCD_SCOPE)] ? $::env(VCD_SCOPE) : "tb/dut"}]
  read_vcd -scope $scope $::env(VCD)
  report_activity_annotation
}
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set die [$block getDieArea]
set f [open $::env(OUT_DIR)/inst_loc.csv w]
puts $f "die,[expr {[$die xMin]/double($dbu)}],[expr {[$die yMin]/double($dbu)}],[expr {[$die xMax]/double($dbu)}],[expr {[$die yMax]/double($dbu)}]"
foreach inst [$block getInsts] {
  set bb [$inst getBBox]
  puts $f "[$inst getName],[expr {([$bb xMin]+[$bb xMax])/2.0/$dbu}],[expr {([$bb yMin]+[$bb yMax])/2.0/$dbu}]"
}
close $f
report_power
report_power -instances [get_cells *] -digits 8
