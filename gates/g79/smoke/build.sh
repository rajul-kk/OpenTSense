#!/bin/bash
set -euo pipefail
cd /smoke
src=source/designs/src/ibex_sv
g81b=/repo/gates/g81b/tb
rtl=()
for file in "$src"/*.sv; do
    [[ "$file" == "$src/ibex_pkg.sv" ]] || rtl+=("$file")
done
verilator --version
verilator --cc --exe --build --timing --trace --trace-underscore -j 2 --top-module tb \
    -I/smoke "-I$src/vendor/lowrisc_ip/prim/rtl" --Mdir /smoke/obj -o simv -Wno-fatal \
    "$src/ibex_pkg.sv" "${rtl[@]}" "$src/syn/rtl/prim_clock_gating.v" \
    "$g81b/ibex_tb_g81b.v" "$g81b/main.cpp"
test -x obj/simv
echo BUILD_COMPLETE
