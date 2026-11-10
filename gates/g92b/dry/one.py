import glob, sys
from opentsense.power import leaklib as L
kit, cell, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
texts, cells, jobs = L.build(kit, sorted(glob.glob("gates/g92b/dry/lib/" + ("sg13g2*.lib" if kit == "ihp" else "asap7*"))))
j = [j for j in jobs if j[0] == cell and j[1][0] == k][0]
print(j[2]); out = L.ngspice("x", j[2], L.KITS[kit]["osdi"])
print("\n".join(l for l in out.splitlines() if not l.startswith(" ") or "rror" in l)[:4000])
