#!/bin/bash
# G81d: generate the looped Gemmini tests and build them for the G51 Chipyard simulator (run inside WSL).
# Usage: build.sh <K_mm> <K_conv> <K_mlp1> <out dir under ~> [--stack]   e.g. build.sh 100 4 3 g81d/main
# --stack (G81d2): stamps on the stack, so data addresses equal G51's binaries
source ~/miniforge3/etc/profile.d/conda.sh; cd ~/g51/chipyard && source env.sh >/dev/null 2>&1
set -euo pipefail   # after env.sh, which uses unset variables
T=~/g51/chipyard/generators/gemmini/software/gemmini-rocc-tests
G=/mnt/d/Work/FYP-search/fyp/opentsense/gates/g81d
O=~/$4; mkdir -p $O/src $O/bm $O/mlps
V="abs_top_srcdir=$T src_dir=$O/src"
mk() {
  python3 $G/make_src.py $T $O/src $1 $2 $3 "$@"
  rm -f $O/bm/g81d_*-baremetal $O/mlps/g81d_*-baremetal
  make -s -C $O/bm    -f $T/bareMetalC/Makefile $V g81d_mm-baremetal
  make -s -C $O/bm    -f $T/bareMetalC/Makefile $V g81d_conv-baremetal
  make -s -C $O/mlps  -f $T/mlps/Makefile       $V g81d_mlp1-baremetal
}
if [ "${5:-}" = --stack ]; then
  # G81d2: pass 1 measures how far the added code moves the data; pass 2 pads .text so the shift is one page
  mk $1 $2 $3 --stack
  P=$(python3 $G/layout.py $O)
  mk $1 $2 $3 --stack --pad $P
  echo "pad $P"; python3 $G/layout.py $O --check
else
  mk $1 $2 $3
fi
sha256sum $O/bm/g81d_mm-baremetal $O/bm/g81d_conv-baremetal $O/mlps/g81d_mlp1-baremetal $O/src/*.c | tee $O/sha256.txt
