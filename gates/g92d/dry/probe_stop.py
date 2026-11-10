"""G92d dry run: what cures the LVT AOI311xp33 solver stop at 125 C (G92c)? Runs the state's deck as written and with
candidate retry options, and prints the leakage and whether ngspice stopped.
Usage: probe_stop.py <kit> <cell> <when-substring>"""
import sys, glob, re
from opentsense.power import leaklib as L
kit, cell, w = sys.argv[1:4]
libs = sorted(glob.glob(f"gates/g92c/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
job = next(j for j in jobs if j[0] == cell and w in str(cells[cell]["states"][j[1][0]]["when"]))
d = job[2]
VAR = {"as is": d,
       "gear": d.replace(".control", ".options method=gear\n.control"),
       "step 1p": d.replace("tran 20p", "tran 1p"),
       "no nodeset": re.sub(r"^\.nodeset[^\n]*\n", "", d, flags=re.M),
       "gear+gmin": d.replace(".control", ".options method=gear gmin=1e-15\n.control")}
for k, dk in VAR.items():
    out = L.ngspice(f"stop_{abs(hash(k))}", dk, L.KITS[kit]["osdi"])
    pw, v, want, ok = L._parse(out, job[3], L.KITS[kit]["vdd"])
    print(f"{k:12s} ok={ok} abort={bool(L.ABORT.search(out))}", {t: round(x, 2) for t, x in sorted(pw.items())},
          {q: {t: round(x, 4) for t, x in sorted(a.items())} for q, a in v.items()}, flush=True)
    if not ok:
        print("   ", " | ".join(l for l in out.splitlines() if re.search(r"abort|timestep|fail|converge|singular|Warning", l, re.I))[:400])
