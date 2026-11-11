#!/bin/bash
# G81b: build Embench-IoT (pinned) and the idle program for the G81b testbench, in opentsense:g81b-cc.
# Usage (in the container, from the repo root): gates/g81b/build_sw.sh <out dir> <scale file: "bench lsf" per line, or "-" for LSF=1> [NPASS]
set -euo pipefail
OUT=$1; SF=$2; NPASS=${3:-1}
E=gates/g81b/ext/embench-iot; SW=gates/g81b/sw
mkdir -p $OUT; cat /compiler_version.txt > $OUT/compiler.txt
CC="riscv64-unknown-elf-gcc -march=rv32imc_zicsr -mabi=ilp32 -O2 -ffunction-sections -fdata-sections --specs=picolibc.specs -nostartfiles -T $SW/link.ld -Wl,--gc-sections"
hex() {  # elf -> hex from address 0
  riscv64-unknown-elf-objcopy -O binary $1 $1.bin
  python3 - $1.bin $2 <<'P'
import sys
b = open(sys.argv[1], "rb").read(); b += b"\0" * (-len(b) % 4)
with open(sys.argv[2], "w") as f:
    f.write("@0\n")
    for i in range(0, len(b), 4): f.write("%08x\n" % int.from_bytes(b[i:i + 4], "little"))
P
}
for d in $E/src/*/; do
  b=$(basename $d); lsf=1
  [ "$SF" != "-" ] && lsf=$(awk -v b=$b '$1==b{print $2}' $SF)
  [ -z "$lsf" ] && { echo "no scale factor for $b"; exit 1; }
  T=$OUT/src/$b; mkdir -p $T; cp $d/*.c $d/*.h $T/ 2>/dev/null || cp $d/*.c $T/
  # LOCAL_SCALE_FACTOR from the scale file (the source's own value is the Embench default, recorded below)
  orig=$(grep -h "define LOCAL_SCALE_FACTOR" $T/*.c | awk '{print $3}' | head -1)
  sed -i "s/^#define LOCAL_SCALE_FACTOR .*/#define LOCAL_SCALE_FACTOR $lsf/" $T/*.c
  # the define must exist and now hold lsf, or the benchmark would silently keep its Embench default
  [ -n "$orig" ] && grep -qh "^#define LOCAL_SCALE_FACTOR $lsf\s*$" $T/*.c || { echo "LOCAL_SCALE_FACTOR not set for $b"; exit 1; }
  $CC -DHAVE_BOARDSUPPORT_H -DGLOBAL_SCALE_FACTOR=1 -DWARMUP_HEAT=0 -I$SW -I$E/support -I$T \
    $SW/crt0.S $SW/board.c $E/support/main.c $E/support/beebsc.c $T/*.c -lm -lc -lgcc -o $OUT/$b.elf
  hex $OUT/$b.elf $OUT/$b.hex
  echo "$b embench_lsf=$orig lsf=$lsf text=$(riscv64-unknown-elf-size $OUT/$b.elf | awk 'NR==2{print $1+$2+$3}')"
done
$CC -DNPASS=$NPASS $SW/crt0.S $SW/idle.c -lgcc -o $OUT/idle.elf
hex $OUT/idle.elf $OUT/idle.hex
echo "idle npass=$NPASS expected=$(python3 $SW/idle_host.py $NPASS)"
