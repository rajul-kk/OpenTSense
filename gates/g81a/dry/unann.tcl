# OpenSTA power of a finished ORFS ASAP7 design from its results directory, without the ORFS make wrapper.
# Run in the ORFS image: openroad -no_init -exit vcd_power.tcl
# env: RES (dir with 6_final.{odb,sdc,spef}), CORNER (TT, FF, ...), VTS (e.g. "RVT LVT SLVT"),
#      VCD (activity file, or "none" for default activity), VCD_SCOPE (default tb/dut), LOC (optional inst_loc.csv to write)
# Prints the activity annotation, the design total and every instance's power.
set L /OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM
read_db $::env(RES)/6_final.odb
foreach vt $::env(VTS) {
  foreach f [glob $L/asap7sc7p5t_{AO,INVBUF,OA,SIMPLE}_${vt}_$::env(CORNER)_nldm_2*.lib.gz $L/asap7sc7p5t_SEQ_${vt}_$::env(CORNER)_nldm_2*.lib] { read_liberty $f }
}
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
if {$::env(VCD) ne "none"} {
  read_vcd -scope [expr {[info exists ::env(VCD_SCOPE)] ? $::env(VCD_SCOPE) : "tb/dut"}] $::env(VCD)
  report_activity_annotation -report_unannotated
}
if {[info exists ::env(LOC)]} {
  set block [ord::get_db_block]
  set dbu [$block getDbUnitsPerMicron]
  set die [$block getDieArea]
  set f [open $::env(LOC) w]
  puts $f "die,[expr {[$die xMin]/double($dbu)}],[expr {[$die yMin]/double($dbu)}],[expr {[$die xMax]/double($dbu)}],[expr {[$die yMax]/double($dbu)}]"
  foreach inst [$block getInsts] {
    set bb [$inst getBBox]
    puts $f "[$inst getName],[expr {([$bb xMin]+[$bb xMax])/2.0/$dbu}],[expr {([$bb yMin]+[$bb yMax])/2.0/$dbu}]"
  }
  close $f
}


