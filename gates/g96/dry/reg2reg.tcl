# Setup and hold at a corner with propagated clocks (env as load_routed.tcl).
source [file dirname [info script]]/load_routed.tcl
set_propagated_clock [all_clocks]
puts "REG2REG max:"
report_checks -from [all_registers -clock_pins] -to [all_registers -data_pins] -path_delay max -format end -group_path_count 5 -digits 2
puts "REG2REG min:"
report_checks -from [all_registers -clock_pins] -to [all_registers -data_pins] -path_delay min -format end -group_path_count 5 -digits 2
puts "I/O and all paths:"
report_checks -path_delay max -format end -group_path_count 5 -digits 2
report_tns -digits 2
report_wns -digits 2
