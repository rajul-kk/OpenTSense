"""G92e dry run (not scored): G92d's IHP dfrbp_1 reference (gates/g92d/ref_dfrbp.py) under solver variants, with more
averaging windows, to see whether its 10-100 us wobble (up to 1.1% in G92d) is solver noise.
env: TMAX (default 1n), OPTS (extra .options, e.g. "reltol=1e-6"), STATES (comma), TEMPS (comma), J
Usage: ref_probe.py"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "gates/g92d")
from opentsense.power import leak as LK

ENDS = (1000, 3000, 10000, 30000, 100000)
TMAX = os.environ.get("TMAX", "1n")
OPTS = os.environ.get("OPTS", "")


def run(job):
    name, t = job
    src, dut = LK.IHP[name]
    src = src.replace(" 100n)", " 1)")
    ms = "\n".join(f"meas tran i{e} avg i(vdd) from={e * 0.95}n to={e}n" for e in ENDS)
    deck = (f"* {name} {t}C\n.lib cornerMOSlv.lib mos_tt\n.include {LK.SPICE}/ihp/sg13g2_stdcell.spice\nVDD VDD 0 {LK.IV}\nVSS VSS 0 0\n"
            f"{src}\n{dut}\n.options method=gear {OPTS}\n.control\noption temp={t}\nsave vdd#branch\ntran 20p {ENDS[-1]}n 0 {TMAX}\n{ms}\n.endc\n.end\n")
    out = LK.ngspice(f"{name}_{t}", deck, ("psp103", "psp103_nqs", "r3_cmc", "mosvar"))
    v = {int(e): abs(float(x)) * LK.IV * 1e12 for e, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}
    return name, t, v


if __name__ == "__main__":
    states = os.environ.get("STATES", "dfrbp_1_Q0,dfrbp_1_Q1").split(",")
    temps = [int(x) for x in os.environ.get("TEMPS", "25,50,75").split(",")]
    print("variant", dict(TMAX=TMAX, OPTS=OPTS), flush=True)
    with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
        for name, t, v in ex.map(run, [(n, t) for n in states for t in temps]):
            ok = len(v) == len(ENDS)
            print(name, t, {k: round(x, 2) for k, x in v.items()},
                  "flat10-100", round(abs(v[100000] / v[10000] - 1), 5) if ok else "FAILED",
                  "spread3-100", round((max(v[e] for e in ENDS[1:]) - min(v[e] for e in ENDS[1:])) / v[100000], 5) if ok else "", flush=True)
