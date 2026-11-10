#!/bin/bash
# Edge time / shunt variants on the ASAP7 cells whose capture transient stops. Prints ok/fail counts per variant.
cd "$(dirname "$0")/../../.."
C=${C:-DHLx1_ASAP7_75t_R,DLLx3_ASAP7_75t_R,ICGx8DC_ASAP7_75t_R,ICGx2p67DC_ASAP7_75t_R,SDFHx4_ASAP7_75t_R,SDFLx4_ASAP7_75t_R,NOR5xp2_ASAP7_75t_R,OAI31xp67_ASAP7_75t_R}
for v in ${V:-"0.05 1e-15" "0.2 1e-15" "0.05 1e-14" "0.2 1e-14"}; do
  MSYS_NO_PATHCONV=1 docker run --rm -m 6g -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work -e J=8 opentsense:g75spice \
    python gates/g92c/dry/probe.py asap7 $C $v > gates/g92c/dry/variant_${v// /_}.log 2>&1
  echo "EDGE/cshunt $v: ok $(grep -c ' ok ' gates/g92c/dry/variant_${v// /_}.log) FAIL $(grep -c ' FAIL ' gates/g92c/dry/variant_${v// /_}.log) $(grep '^wall' gates/g92c/dry/variant_${v// /_}.log) failing: $(grep ' FAIL ' gates/g92c/dry/variant_${v// /_}.log | cut -d' ' -f1 | sort | uniq -c | tr '\n' ' ')"
done
