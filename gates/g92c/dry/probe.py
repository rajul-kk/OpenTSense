"""Probe G92c generator on chosen cells: solve every plan of each, print tran (150 ns) vs settled (DC) leakage and checks.
Usage: probe.py <kit> <cells,comma> [EDGE] [cshunt]"""
import sys, glob, time
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leaklib as L
kit, want = sys.argv[1], sys.argv[2].split(",")
if len(sys.argv) > 3: L.EDGE = float(sys.argv[3])
if len(sys.argv) > 4: L.KITS[kit]["models"] = L.KITS[kit]["models"].replace("cshunt=1e-14", f"cshunt={sys.argv[4]}")
libs = sorted(glob.glob(f"gates/g92b/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
pick = [j for j in jobs if j[0] in want]
t0 = time.time()
with ThreadPoolExecutor(int(__import__("os").environ.get("J", "6"))) as ex:
    for cell, key, r in ex.map(L.solve, pick):
        st = cells[cell]["states"][key[0]]
        f = lambda d: {t: round(x, 1) for t, x in (d or {}).items()}
        print(cell, st["when"], key, "ok" if r["ok"] else "FAIL", "tran", f(r.get("tran_pW")), "cont", f(r.get("cont_pW")), "dc" if "tran_pW" in r else "", f(r["spice_pW"]),
              "" if r["ok"] else r.get("tail", "")[-250:].replace("\n", " | "), flush=True)
print("wall", round(time.time() - t0, 1), "s,", len(pick), "plans")
