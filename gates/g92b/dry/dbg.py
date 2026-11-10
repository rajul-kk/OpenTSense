import re, sys
from opentsense.power import leaklib as L
kit, cell, k, temp = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
libs = ["gates/g92b/dry/lib/sg13g2_stdcell_typ_1p20V_25C.lib"] if kit == "ihp" else sorted(__import__("glob").glob("gates/g92b/dry/lib/asap7*"))
_, cells, jobs = L.build(kit, libs)
j = [j for j in jobs if j[0] == cell and j[1][0] == k][0]
d = j[2]; print(d[:d.find(".control")])
q = sys.argv[5]
ms = "\n".join(f"meas tran q{t} find v(n_{q}) at={t}n\nmeas tran i{t} find i(vdd) at={t}n" for t in (1, 2.5, 4, 6, 7.5, 20, 100, 149))
d = d[:d.find(".control")] + f".control\noption temp={temp}\ntran 20p {sys.argv[6]}n\n{ms}\n.endc\n.end\n"
out = L.ngspice("d", d, L.KITS[kit]["osdi"])
print("\n".join(l for l in out.splitlines() if re.match(r"^[qi][\d.]+\s", l) or "rror" in l))
