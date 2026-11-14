# G96: SDF of a routed design (env as load_routed.tcl, plus OUT = sdf path). Timing is checked by reg2reg.tcl.
source [file dirname [info script]]/load_routed.tcl
write_sdf -divider / -digits 4 $::env(OUT)
