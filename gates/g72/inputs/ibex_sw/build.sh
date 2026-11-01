#!/bin/bash
# G30: build kernels (rv32imc) and the gate-level simulation of the routed sky130hd ibex_core.
set -e
E=$(cd "$(dirname "$0")" && pwd); S=$E/..
PDK=$S/dl_pdk/sky130A/libs.ref/sky130_fd_sc_hd; NET=$S/orfs/batch/sky130hd-ibex/results/sky130hd/ibex/base/6_final.v
mkdir -p $E/build; cd $E/build
for k in 0 1 2 3; do
  riscv64-unknown-elf-gcc -march=rv32imc -mabi=ilp32 -O1 -ffreestanding -nostdlib -DKERNEL=$k -T $E/sw/link.ld $E/sw/crt0.S $E/sw/kernels.c -lgcc -o k$k.elf
  riscv64-unknown-elf-objcopy -O binary k$k.elf k$k.bin
  python3 - k$k.bin k$k.hex <<'P'
import sys
b = open(sys.argv[1], "rb").read(); b += b"\0" * (-len(b) % 4)
with open(sys.argv[2], "w") as f:
    f.write("@20\n")                                  # .text starts at byte 0x80 = word 0x20
    for i in range(0, len(b), 4): f.write("%08x\n" % int.from_bytes(b[i:i + 4], "little"))
P
done
ls -la *.hex
# gate-level compile (functional cell models, zero delay)
sed 's/\r$//' $NET > netlist.v
sed -E 's/^(\s*`endif)\s+[A-Za-z_0-9]+.*$/\1/' $PDK/verilog/sky130_fd_sc_hd.v > cells.v      # icarus rejects text after `endif
sed -E 's/^(\s*`endif)\s+[A-Za-z_0-9]+.*$/\1/' $PDK/verilog/primitives.v > prims.v
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY=#0 -o sim.vvp -s tb prims.v cells.v netlist.v $E/tb/tb.v 2>&1 | grep -v -i "warning" | head -20
ls -la sim.vvp
