# G75: routed ASAP7 cva6, as G52 (FF libraries, hierarchical database). env: RES, VCD, VCD_SCOPE
set L /OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM
source /OpenROAD-flow-scripts/flow/platforms/asap7/liberty_suppressions.tcl
foreach vt {RVT LVT SLVT} {
  foreach f [list AO_${vt}_FF_nldm_211120.lib.gz INVBUF_${vt}_FF_nldm_220122.lib.gz OA_${vt}_FF_nldm_211120.lib.gz SIMPLE_${vt}_FF_nldm_211120.lib.gz SEQ_${vt}_FF_nldm_220123.lib] { read_liberty $L/asap7sc7p5t_$f }
}
foreach m {64x256 128x64 64x28 64x25} { read_liberty $L/fakeram7_$m.lib }
read_db -hier $::env(RES)/6_final.odb
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
if {$::env(VCD) ne "none"} { read_vcd -scope $::env(VCD_SCOPE) $::env(VCD); report_activity_annotation }
report_power -digits 8
report_power -instances [get_cells *] -digits 8
