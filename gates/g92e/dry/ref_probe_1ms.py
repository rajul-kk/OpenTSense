"""G92e dry run (not scored): G92d's dfrbp_1 reference deck (gates/g92d/ref_dfrbp.py, Amendment 2 settings: Gear, 1 ns
maximum step) run to 1 ms instead of 100 us, mean supply current over the last 5% before each end. Question: is the
10-100 us drift (G92d, ref_probe.log: unchanged by reltol or step) slow settling that is flat by 1 ms?
Usage: ref_probe_1ms.py   env: J, TEMPS, NAMES (default dfrbp_1_Q0,dfrbp_1_Q1)"""
import os
import re
from concurrent.futures import ThreadPoolExecutor

from opentsense.power import leak as LK

ENDS = (1000, 10000, 30000, 100000, 300000, 1000000)        # ns


def run(job):
    name, t = job
    src, dut = LK.IHP[name]
    src = src.replace(" 100n)", " 1)")
    ms = "\n".join(f"meas tran i{e} avg i(vdd) from={e * 0.95}n to={e}n" for e in ENDS)
    deck = (f"* {name} {t}C\n.lib cornerMOSlv.lib mos_tt\n.include {LK.SPICE}/ihp/sg13g2_stdcell.spice\nVDD VDD 0 {LK.IV}\nVSS VSS 0 0\n"
            f"{src}\n{dut}\n.options method=gear\n.control\noption temp={t}\nsave vdd#branch\ntran 20p {ENDS[-1]}n 0 1n\n{ms}\n.endc\n.end\n")
    out = LK.ngspice(f"{name}_{t}", deck, ("psp103", "psp103_nqs", "r3_cmc", "mosvar"))
    return name, t, {int(e): abs(float(x)) * LK.IV * 1e12 for e, x in re.findall(r"^i(\d+)\s*=\s*(\S+)", out, re.M)}


if __name__ == "__main__":
    temps = [int(x) for x in os.environ.get("TEMPS", "25,50,75,100").split(",")]
    with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
        for name, t, v in ex.map(run, [(n, t) for n in os.environ.get("NAMES", "dfrbp_1_Q0,dfrbp_1_Q1").split(",") for t in temps]):
            ok = len(v) == len(ENDS)
            print(name, t, {k: round(x, 2) for k, x in v.items()},
                  "flat100u-1m", round(abs(v[1000000] / v[100000] - 1), 5) if ok else "FAILED",
                  "flat300u-1m", round(abs(v[1000000] / v[300000] - 1), 5) if ok else "", flush=True)
