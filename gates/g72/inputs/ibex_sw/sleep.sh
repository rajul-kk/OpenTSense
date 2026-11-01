#!/bin/bash
# G28e prep: sleep-state (WFI) kernel -> VCD window -> OpenROAD power at 25 C
E="$(cd "$(dirname "$0")" && pwd)"; cd $E/build
riscv64-unknown-elf-gcc -march=rv32imc -mabi=ilp32 -O1 -ffreestanding -nostdlib -DKERNEL=4 -T $E/sw/link.ld $E/sw/crt0.S $E/sw/kernels.c -lgcc -o k4.elf 2>/dev/null
riscv64-unknown-elf-objcopy -O binary k4.elf k4.bin
python3 -c "
b=open('k4.bin','rb').read(); b+=b'\0'*(-len(b)%4); f=open('k4.hex','w'); f.write('@20\n')
[f.write('%08x\n'%int.from_bytes(b[i:i+4],'little')) for i in range(0,len(b),4)]"
vvp -n sim.vvp +hex=k4.hex +win_start=1500 +win_len=1000 +vcd=w4.vcd +max=2600 +trace | grep -E "RESULT|TRACE cyc=(1500|2000|2500)"
