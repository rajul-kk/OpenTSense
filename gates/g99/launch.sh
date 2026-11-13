#!/bin/bash
# G99 host side: one design at a time, in a heavy slot sized from the recorded routing peak (registration.md).
# usage: gates/g99/launch.sh <ibex|tpu> <clk_period_ps>   (run from opentsense/; Git Bash on the laptop)
set -u
D=${1:-}; P=${2:-}; B=D:/Work/FYP-search/_build/g99
case $D in ibex) GB=4.5 ;; tpu) GB=7.5 ;; *) echo "design: ibex or tpu"; exit 2 ;; esac
[[ $P =~ ^[1-9][0-9]*$ ]] || { echo "period: integer ps"; exit 2; }
here=$(cd "$(dirname "$0")" && pwd)
cp "$here/run_g99.sh" "$B/run_g99.sh" && cp "$here/../../opentsense/power/extract.tcl" "$B/extract.tcl" || exit 2
id=$(python C:/Users/rajul/.looptools/slots.py acquire "g99-$D" heavy $GB 150) || exit 3
trap 'python C:/Users/rajul/.looptools/slots.py release $id' EXIT
MSYS_NO_PATHCONV=1 docker run --rm --name "g99-$D" --memory ${GB}g -v "$B:/work" openroad/orfs:latest \
  bash /work/run_g99.sh "$D" "$P"
echo "docker rc=$?"; tail -1 "$B/summary.txt"
