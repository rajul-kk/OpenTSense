"""G92d dry run: a settled reference for G53's two flip-flop states (IHP dfrbp_1, Q = 0 and Q = 1), independent of leaklib.
G53's own deck (leak.py: capture edge at 2 ns, D constant, RESET_B high) run as one plain transient to 100 us, with the
mean supply current over the last 5% before 150 ns, 1, 10 and 100 us. G92c showed leak.py's 150 ns value is not settled.
Usage: ref_dfrbp.py"""
import re
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leak as LK

ENDS = (150, 1000, 10000, 100000)                    # ns


def run(job):
    name, t = job
    src, dut = LK.IHP[name]
    # leak.py's clock repeats every 100 ns (a second capture edge at 102 ns, same D); stop it after the first pulse here
    assert " 100n)" in src
    src = src.replace(" 100n)", " 1)")
    ms = "\n".join(f"meas tran i{e} avg i(vdd) from={e * 0.95}n to={e}n" for e in ENDS)
    deck = (f"* {name} {t}C\n.lib cornerMOSlv.lib mos_tt\n.include {LK.SPICE}/ihp/sg13g2_stdcell.spice\nVDD VDD 0 {LK.IV}\nVSS VSS 0 0\n"
            f"{src}\n{dut}\n.control\noption temp={t}\nsave vdd#branch\ntran 20p {ENDS[-1]}n\n{ms}\n.endc\n.end\n")
    out = LK.ngspice(f"{name}_{t}", deck, ("psp103", "psp103_nqs", "r3_cmc", "mosvar"))
    v = {int(e): abs(float(x)) * LK.IV * 1e12 for e, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}
    return name, t, {e: round(x, 3) for e, x in sorted(v.items())}, (round(v[100000] / v[10000] - 1, 5) if len(v) == 4 else out[-300:])


with ThreadPoolExecutor(4) as ex:
    for r in ex.map(run, [(n, t) for n in ("dfrbp_1_Q0", "dfrbp_1_Q1") for t in LK.IHP_T]):
        print(*r, flush=True)
