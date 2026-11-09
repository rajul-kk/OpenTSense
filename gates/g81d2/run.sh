#!/bin/bash
# G81d2 main run (inside WSL): G81d's run with the layout-preserving build (--stack, page-shift padding, layout check).
G=/mnt/d/Work/FYP-search/fyp/opentsense/gates/g81d; H=/mnt/d/Work/FYP-search/fyp/opentsense/gates/g81d2; O=~/g81d/main2; C=30000000
rm -rf $O; bash $G/build.sh 100 4 3 g81d/main2 --stack > $O.build.log 2>&1 || { echo BUILD_FAILED; exit 1; }
grep -q LAYOUT_OK $O.build.log || { echo LAYOUT_MISMATCH; exit 1; }
bash $G/sim.sh $O/mlps/g81d_mlp1-baremetal $O/mlp1.log $C &
bash $G/sim.sh $O/bm/g81d_conv-baremetal $O/conv.log $C &
wait
bash $G/sim.sh $O/bm/g81d_mm-baremetal $O/mm.log $C
mkdir -p $H/runs/main && cp $O/*.log $O/sha256.txt $O.build.log $H/runs/main/ && cp -r $O/src $H/runs/main/ && echo ALL_DONE
