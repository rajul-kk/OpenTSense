#!/bin/bash
# G81d main run (inside WSL): build K = 100/4/3, simulate mlp1 and conv together, then matmul; copy logs to runs/main.
G=/mnt/d/Work/FYP-search/fyp/opentsense/gates/g81d; O=~/g81d/main; C=30000000
bash $G/build.sh 100 4 3 g81d/main > $O.build.log 2>&1 || { echo BUILD_FAILED; exit 1; }
bash $G/sim.sh $O/mlps/g81d_mlp1-baremetal $O/mlp1.log $C &
bash $G/sim.sh $O/bm/g81d_conv-baremetal $O/conv.log $C &
wait
bash $G/sim.sh $O/bm/g81d_mm-baremetal $O/mm.log $C
mkdir -p $G/runs/main && cp $O/*.log $O/sha256.txt $O.build.log $G/runs/main/ && echo ALL_DONE
