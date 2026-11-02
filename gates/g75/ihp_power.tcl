# G75: routed IHP SG13G2 ibex, as G53. env: RES, VCD ("none" = default activity), VCD_SCOPE
read_db $::env(RES)/6_final.odb
read_liberty /OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
if {$::env(VCD) ne "none"} { read_vcd -scope $::env(VCD_SCOPE) $::env(VCD); report_activity_annotation }
report_power -digits 8
report_power -instances [get_cells *] -digits 8
