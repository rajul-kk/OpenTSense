# G92: routed IHP SG13G2 ibex (G53) with one Liberty file. env: RES, LIB, VCD, VCD_SCOPE
read_db $::env(RES)/6_final.odb
read_liberty $::env(LIB)
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
read_vcd -scope $::env(VCD_SCOPE) $::env(VCD)
report_activity_annotation
report_power -digits 8
report_power -instances [get_cells *] -digits 8
