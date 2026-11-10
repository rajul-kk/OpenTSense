"""Probe: capture deck, then a long transient whose step may grow (tmax), measured at several decades. 25 C only."""
import re, sys, time, glob
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leaklib as L
kit, method, tmax = sys.argv[1], sys.argv[2], sys.argv[3]
libs = sorted(glob.glob(f"gates/g92b/runs/main/{kit}/lib/ship/*"))
want = sys.argv[4].split(",")
_, cells, jobs = L.build(kit, libs)
pick = []
for cell in want:
    pick += [j for j in jobs if j[0] == cell and not j[3]["forced"]][:2]
ends = (150, 1e3, 1e4, 1e5, 1e6, 1e7)
def run(j):
    d = j[2]; body = d[:d.find(".control")]
    ms = "\n".join(f"meas tran i{int(t)} avg i(vdd) from={t*0.95}n to={t}n" for t in ends)
    ms += "\n" + "\n".join(f"meas tran v_{q}_x avg v(n_{q}) from={ends[-1]*0.95}n to={ends[-1]}n" for q in j[3]["expect"])
    opt = f".options method={method}\n" if method != "trap" else ""
    t0 = time.time()
    out = L.ngspice("s", body + f"{opt}.control\noption temp=25\nsave all\ntran 20p {int(ends[-1])}n 0 {tmax}n\n{ms}\n.endc\n.end\n", L.KITS[kit]["osdi"])
    v = {int(t): round(abs(float(x)) * L.KITS[kit]["vdd"] * 1e12, 2) for t, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}
    q = {k: (round(float(x), 3), j[3]["expect"][k]) for k, x in [(m.group(1).upper(), m.group(2)) for m in re.finditer(r"^v_(\w+?)_x\s*=\s*(\S+)", out, re.M)]}
    pts = re.search(r"No\. of Data Rows\s*:\s*(\d+)", out)
    return j[0], cells[j[0]]["states"][j[1][0]]["when"], v, q, round(time.time() - t0, 1), pts and pts.group(1), (out[-400:] if len(v) < len(ends) else "")
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(run, pick): print(r, flush=True)
