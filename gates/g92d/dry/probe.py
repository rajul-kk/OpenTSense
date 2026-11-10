"""G92d dry run: solve every plan of chosen cells with the staged continuation; print the 150 ns value, the settled value,
the stage at which each temperature went flat, and the seeded-DC cross-check.
Usage: probe.py <kit> <cells,comma>     (env J: workers, default 4)"""
import sys, glob, time, os
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leaklib as L
kit, want = sys.argv[1], sys.argv[2].split(",")
if "FLAT" in os.environ: L.FLAT = float(os.environ["FLAT"])
if "FLOOR_A" in os.environ: L.FLOOR_A = float(os.environ["FLOOR_A"])
if "CONT_OPTS" in os.environ: L.CONT_OPTS = os.environ["CONT_OPTS"]
if "STAGES" in os.environ: L.STAGES = tuple(float(x) for x in os.environ["STAGES"].split(","))
libs = sorted(glob.glob(f"gates/g92c/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
pick = [j for j in jobs if j[0] in want]
t0 = time.time()
f = lambda d, n=1: {t: round(x, n) for t, x in (d or {}).items()}
with ThreadPoolExecutor(int(os.environ.get("J", "4"))) as ex:
    for cell, key, r in ex.map(L.solve, pick):
        st = cells[cell]["states"][key[0]]
        if "tran_pW" in r:
            flips = [t for t, okl in r["dc_levels_ok"].items() if not okl]
            print(cell, st["when"], "ok" if r["ok"] else "FAIL", "tran", f(r["tran_pW"]), "settled", f(r["spice_pW"]),
                  "t", {t: f"{x:g}" for t, x in r["settle_t"].items()}, "flat", f(r["settle_flat"], 5), "dc", f(r["dc_agree"], 4),
                  "dcflip", flips, "" if r["ok"] else r.get("tail", "")[-200:].replace("\n", " | "), flush=True)
            if os.environ.get("TRACE"):
                print("   trace25", [(f"{e:g}", round(c, 2) if c else c) for e, c in r["settle_trace"].get(25, [])], flush=True)
        else:
            print(cell, st["when"], "ok" if r["ok"] else "FAIL", "comb", f(r["spice_pW"]), "retried" if r.get("retried") else "", flush=True)
print("wall", round(time.time() - t0, 1), "s,", len(pick), "plans")
