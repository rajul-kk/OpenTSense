import re, glob
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leaklib as L
libs = sorted(glob.glob("gates/g92b/runs/main/asap7/lib/ship/*"))
_, cells, jobs = L.build("asap7", libs)
pick = []
for cell in ("DFFHQNx1_ASAP7_75t_R", "SDFHx1_ASAP7_75t_R", "DHLx1_ASAP7_75t_R", "ICGx1_ASAP7_75t_R", "DFFASRHQNx1_ASAP7_75t_R"):
    js = [j for j in jobs if j[0] == cell and not j[3]["forced"]][:2]
    pick += js
def run(j):
    d = j[2]; body = d[:d.find(".control")]
    ms = "\n".join(f"meas tran i{t} avg i(vdd) from={t*0.95}n to={t}n" for t in (150, 1000, 10000, 100000))
    out = L.ngspice("s", body + f".control\noption temp=25\nsave vdd#branch\ntran 20p 100000n\n{ms}\n.endc\n.end\n", ("bsimcmg",))
    v = {int(t): abs(float(x)) * 0.7e12 for t, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}
    return j[0], cells[j[0]]["states"][j[1][0]]["when"], {t: round(x, 2) for t, x in v.items()}, round(v[150] / v[100000] - 1, 4) if len(v) == 4 else None
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(run, pick): print(r, flush=True)
