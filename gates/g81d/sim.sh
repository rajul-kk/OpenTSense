#!/bin/bash
# G81d: run one looped test on G51's Chipyard simulator (GemminiRocketConfig + act_mon), fast preload as G51 note 3.
# Usage (inside WSL): sim.sh <elf> <log> <max-cycles>
source ~/miniforge3/etc/profile.d/conda.sh; cd ~/g51/chipyard && source env.sh >/dev/null 2>&1; cd sims/verilator
s=$(date +%s)
./simulator-chipyard.harness-GemminiRocketConfig +permissive +max-cycles=$3 +loadmem=$1 +permissive-off $1 > $2 2>&1; rc=$?
echo "RUN_DONE rc=$rc wall=$(( $(date +%s) - s ))s" >> $2
