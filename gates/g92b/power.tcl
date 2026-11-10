# G92b: routed ibex (IHP G53 or ASAP7 G34) with a list of Liberty files. env: RES, LIBS (space separated), VCD, VCD_SCOPE
read_db $::env(RES)/6_final.odb
foreach f $::env(LIBS) { read_liberty $f }
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
read_vcd -scope $::env(VCD_SCOPE) $::env(VCD)
report_activity_annotation
report_power -digits 8
report_power -instances [get_cells *] -digits 8
