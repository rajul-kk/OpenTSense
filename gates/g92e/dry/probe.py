"""G92e dry run (not scored): the staged continuation on chosen states, printing the 25 C trace per stage.
Variants via env:
  CONT_OPTS  extra .options on continuation decks (e.g. "reltol=1e-6")
  TAIL       if set (fraction, e.g. 0.1): a stage's current is the time-weighted mean of i(vdd) over the last TAIL of the
             stage, instead of its last point (the .ic seeds still come from the last point)
  FLAT, FLOOR_A, STAGES as G92d's probe; TEMPS (comma) limits temperatures; J workers
Usage: probe.py <kit> <cell> [when-substring;when-substring...]"""
import os
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from opentsense.power import leaklib as L

kit, cell = sys.argv[1], sys.argv[2]
whens = sys.argv[3].split(";") if len(sys.argv) > 3 else None
if "FLAT" in os.environ: L.FLAT = float(os.environ["FLAT"])
if "FLOOR_A" in os.environ: L.FLOOR_A = float(os.environ["FLOOR_A"])
if "CONT_OPTS" in os.environ: L.CONT_OPTS = os.environ["CONT_OPTS"]
if "STAGES" in os.environ: L.STAGES = tuple(float(x) for x in os.environ["STAGES"].split(","))
if "TEMPS" in os.environ: L.TEMPS = tuple(int(x) for x in os.environ["TEMPS"].split(","))
TAIL = float(os.environ.get("TAIL", "0"))
_last = L.raw_last


def raw_tail(b):
    d = _last(b)
    if not TAIL:
        return d
    i = b.index(b"Binary:\n")
    head = b[:i].decode(errors="replace").splitlines()
    nv = int(next(l for l in head if l.startswith("No. Variables:")).split(":")[1])
    npt = int(next(l for l in head if l.startswith("No. Points:")).split(":")[1])
    k = next(j for j, l in enumerate(head) if l.startswith("Variables:"))
    nm = [head[k + 1 + j].split()[1] for j in range(nv)]
    ic = next((nm.index(x) for x in ("i(vdd)", "vdd#branch") if x in nm), None)
    if ic is None or npt < 3:
        return d
    rows = struct.unpack(f"<{nv * npt}d", b[i + 8: i + 8 + npt * nv * 8])
    t = [abs(rows[j * nv]) for j in range(npt)]
    y = [rows[j * nv + ic] for j in range(npt)]
    t0 = t[-1] - TAIL * (t[-1] - t[0])
    num = den = 0.0
    for j in range(1, npt):
        a, c = max(t[j - 1], t0), t[j]
        if c <= a:
            continue
        num += 0.5 * (y[j - 1] + y[j]) * (c - a)
        den += c - a
    if den > 0:
        d[nm[ic]] = num / den
    return d


L.raw_last = raw_tail
libs = sorted(__import__("glob").glob(f"gates/g92c/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
pick = [j for j in jobs if j[0] == cell and (whens is None or any(w in (cells[cell]["states"][j[1][0]]["when"] or "") for w in whens))]
t0 = time.time()
f = lambda d, n=2: {t: round(x, n) for t, x in (d or {}).items()}
print("variant", dict(CONT_OPTS=L.CONT_OPTS, TAIL=TAIL, FLAT=L.FLAT, FLOOR_A=L.FLOOR_A, STAGES=L.STAGES, TEMPS=L.TEMPS), flush=True)
with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
    for c, key, r in ex.map(L.solve, pick):
        st = cells[c]["states"][key[0]]
        print(c, st["when"], "ok" if r["ok"] else "FAIL", "settled", f(r.get("spice_pW")), "t", r.get("settle_t"), flush=True)
        for T, tr in (r.get("settle_trace") or {}).items():
            print("   trace", T, [(f"{e:g}", round(x, 2) if x else x) for e, x in tr], flush=True)
print("wall", round(time.time() - t0, 1), "s,", len(pick), "plans", flush=True)
