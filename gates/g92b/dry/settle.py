import re, sys, importlib.util
spec = importlib.util.spec_from_file_location("g92", "gates/g92/leaklib_g92.py"); G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
from opentsense.power import leaklib as L
txt = open("gates/g92b/runs/main/ihp/lib/ship/sg13g2_stdcell_typ_1p20V_25C.lib").read()
gc, order = G.parse_lib(txt), G.subckt_pins()
_, nc, jobs = L.build("ihp", ["gates/g92b/runs/main/ihp/lib/ship/sg13g2_stdcell_typ_1p20V_25C.lib"])
for cell, when in (("sg13g2_dlhq_1", "!D&GATE&!Q"), ("sg13g2_sdfrbpq_1", "!CLK&!D&RESET_B&!SCD&!SCE&Q")):
    st = next(s for s in gc[cell]["states"] if s["when"] == when)
    d, q, _ = G.deck(cell, gc[cell], order[cell], dict(st))
    k = next(i for i, s in enumerate(nc[cell]["states"]) if s["when"] == when)
    dn = next(j for j in jobs if j[0] == cell and j[1][0] == k)[2]
    for name, deck in (("G92", d), ("G92b", dn)):
        body = deck[:deck.find(".control")]
        ms = "\n".join(f"meas tran i{t} avg i(vdd) from={t*0.95}n to={t}n" for t in (150, 1000, 10000, 100000))
        out = L.ngspice("s", body + f".control\noption temp=25\ntran 1n 100000n\n{ms}\n.endc\n.end\n", L.KITS["ihp"]["osdi"])
        print(cell, when, name, {t: round(abs(float(x)) * 1.2e12, 2) for t, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}, flush=True)
