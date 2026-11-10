"""G92d: the settled reference for G53's two flip-flop states (IHP dfrbp_1, Q = 0 and Q = 1), independent of leaklib.
G53's own deck (leak.py: capture edge at 2 ns, D constant, RESET_B high), with the clock's 100 ns repeat removed, run as one
plain transient to 100 us. Writes the mean supply current over the last 5% before 150 ns, 1, 10 and 100 us, and the flatness
|I(100 us) / I(10 us) - 1|. G92c showed leak.py's 150 ns value is not settled (G92c README).
Usage: ref_dfrbp.py <out.json>"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from opentsense.power import leak as LK

ENDS = (150, 1000, 10000, 100000)                    # ns
# Amendment 2: with no maximum step ngspice caps the step at the 20 ps print step (5 million steps to 100 us, 10 h or
# more for the 8 runs). The step may now grow to 1 ns once the edge has passed; Gear, because the trapezoidal rule rings
# at large steps (G92c). The deck, the windows and the flatness bar are unchanged.
TMAX = "1n"


def run(job):
    name, t = job
    src, dut = LK.IHP[name]
    # leak.py's clock repeats every 100 ns (a second capture edge at 102 ns, same D); stop it after the first pulse here
    assert " 100n)" in src
    src = src.replace(" 100n)", " 1)")
    ms = "\n".join(f"meas tran i{e} avg i(vdd) from={e * 0.95}n to={e}n" for e in ENDS)
    deck = (f"* {name} {t}C\n.lib cornerMOSlv.lib mos_tt\n.include {LK.SPICE}/ihp/sg13g2_stdcell.spice\nVDD VDD 0 {LK.IV}\nVSS VSS 0 0\n"
            f"{src}\n{dut}\n.options method=gear\n.control\noption temp={t}\nsave vdd#branch\ntran 20p {ENDS[-1]}n 0 {TMAX}\n{ms}\n.endc\n.end\n")
    out = LK.ngspice(f"{name}_{t}", deck, ("psp103", "psp103_nqs", "r3_cmc", "mosvar"))
    v = {int(e): abs(float(x)) * LK.IV * 1e12 for e, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}
    if len(v) != len(ENDS):
        return name, t, dict(failed=out[-400:])
    return name, t, dict(pW={str(e): v[e] for e in ENDS}, flat=abs(v[100000] / v[10000] - 1))


if __name__ == "__main__":
    res = {}
    with ThreadPoolExecutor(int(os.environ.get("REF_J", "4"))) as ex:      # REF_J: workers (memory), not a result setting
        for name, t, r in ex.map(run, [(n, t) for n in ("dfrbp_1_Q0", "dfrbp_1_Q1") for t in LK.IHP_T]):
            res.setdefault(name, {})[str(t)] = r
            print(name, t, r, flush=True)
    json.dump(res, open(sys.argv[1], "w"), indent=1)
