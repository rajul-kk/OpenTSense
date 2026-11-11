#!/bin/bash
# G92e dry check of the leak.py abort fix: rerun both kits, compare with G92d's leak_ref.json (expect exact, no failures).
cd /d/Work/FYP-search/fyp/opentsense || exit 1
D() { MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work "$@"; }
{
for k in ihp asap7; do
  D opentsense:g75spice python opentsense/power/leak.py $k gates/g92e/dry/leak_check_$k.json || echo "leak.py $k exit $?"
done
python - <<'EOF'
import json
for k in ("ihp", "asap7"):
    a = json.load(open(f"gates/g92e/dry/leak_check_{k}.json")); b = json.load(open(f"gates/g92d/runs/main/{k}/leak_ref.json"))
    fails = [n for n, v in a.items() if "failed" in v]
    d = max(abs(a[n][t] / b[n][t] - 1) for n in b if "failed" not in b[n] and n in a and "failed" not in a[n] for t in b[n])
    print(k, len(a), "cases, failed:", fails, "max rel diff vs G92d:", d, "same keys:", set(a) == set(b))
EOF
echo EXIT=$?
} > gates/g92e/dry/leak_check.log 2>&1
