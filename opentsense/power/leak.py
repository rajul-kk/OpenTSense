"""Cell leakage against temperature from ngspice and the models in the image, as in G53 (IHP PSP103) and G41 (ASAP7 BSIM-CMG).
Usage: leak.py <ihp|asap7> <out.json>"""
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

SPICE = os.environ.get("SPICE_ROOT", "/opt/spice")
PW = "VDD VSS"
IHP_T, ASAP7_T = (25, 50, 75, 100), (25, 50, 75, 100, 125)
IV, AV = 1.2, 0.7
_clk = f"Vc c 0 PULSE(0 {IV} 2n 50p 50p 1n 100n)\nVr r 0 {IV}\n"
IHP = {"inv_1_A0": ("Va a 0 0", f"X1 y a {PW} sg13g2_inv_1"), "inv_1_A1": (f"Va a 0 {IV}", f"X1 y a {PW} sg13g2_inv_1"),
       "nand2_1_00": ("Va a 0 0\nVb b 0 0", f"X1 y a b {PW} sg13g2_nand2_1"), "nand2_1_11": (f"Va a 0 {IV}\nVb b 0 {IV}", f"X1 y a b {PW} sg13g2_nand2_1"),
       "nor2_1_00": ("Va a 0 0\nVb b 0 0", f"X1 y a b {PW} sg13g2_nor2_1"), "nor2_1_11": (f"Va a 0 {IV}\nVb b 0 {IV}", f"X1 y a b {PW} sg13g2_nor2_1"),
       "dfrbp_1_Q0": (_clk + "Vd d 0 0", f"X1 q qn c d r {PW} sg13g2_dfrbp_1"), "dfrbp_1_Q1": (_clk + f"Vd d 0 {IV}", f"X1 q qn c d r {PW} sg13g2_dfrbp_1")}
ASAP7 = {"INVx1": ("A VDD VSS Y", [("A", 0), ("A", 1)]), "NAND2x1": ("A B VDD VSS Y", [("AB", 0), ("AB", 1)]), "DFFHQNx1": ("CLK D QN VDD VSS", [("D", 0), ("D", 1)])}


# An aborted analysis prints zeros for its measurements, which a count of measurements alone accepts (leaklib found this in
# G92c). Any abort text now fails the case; a transient also fails if it stopped at its first point ("No. of Data Rows : 1",
# LVT AOI311xp33 in G92c). The op analyses (ASAP7) legitimately print one data row, so that clause applies to IHP only.
ABORT = re.compile(r"simulation\(s\) aborted|timestep too small|failed!|no convergence|singular matrix", re.I)
TRAN_STOPPED = re.compile(r"No\. of Data Rows\s*:\s*[01]\s*$", re.M)


def _failed(why, out):
    """A failed case: {'failed': text, 'outcome': why}. `why` is 'aborted' (abort text or a stopped transient) or 'missing'
    (too few measurements); every consumer tests only for the 'failed' key."""
    return {"failed": f"{why}: " + out[-600:], "outcome": why}


def ngspice(name, deck, osdi):
    with tempfile.TemporaryDirectory() as d:
        init = f"setcs sourcepath = ( $sourcepath {SPICE}/ihp/models {SPICE}/asap7 )\n" + "".join(f"osdi '{SPICE}/osdi/{m}.osdi'\n" for m in osdi)
        open(os.path.join(d, ".spiceinit"), "w").write(init)
        open(os.path.join(d, name + ".cir"), "w").write(deck)
        return subprocess.run(["ngspice", "-b", name + ".cir"], cwd=d, capture_output=True, text=True).stdout


def ihp(name):
    src, dut = IHP[name]
    te = (150, 140) if name.startswith("dfr") else (8, 7)        # flip-flop internal nodes settle only through leakage
    ctl = "\n".join(f"option temp={t}\ntran 20p {te[0]}n\nmeas tran il{t} avg i(vdd) from={te[1]}n to={te[0]}n" for t in IHP_T)
    deck = f"* {name}\n.lib cornerMOSlv.lib mos_tt\n.include {SPICE}/ihp/sg13g2_stdcell.spice\nVDD VDD 0 {IV}\nVSS VSS 0 0\n{src}\n{dut}\n.control\n{ctl}\n.endc\n.end\n"
    out = ngspice(name, deck, ("psp103", "psp103_nqs", "r3_cmc", "mosvar"))
    v = {int(t): abs(float(x)) * IV for t, x in re.findall(r"^il(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    if ABORT.search(out) or TRAN_STOPPED.search(out):
        return name, _failed("aborted", out)
    return name, {t: p * 1e12 for t, p in v.items()} if len(v) == len(IHP_T) else _failed("missing", out)


def asap7(cv):
    cell, vt = cv
    pins, states = ASAP7[cell]
    L = [f"* {cell} {vt}", f".include {SPICE}/asap7/asap7_tt_osdi.lib", f".include {SPICE}/asap7/cells_{vt}.sp"]
    for si, (inp, v) in enumerate(states):
        nodes = [f"vdd{si}" if p == "VDD" else "0" if p in ("VSS", "CLK") else f"o{si}" if p in ("Y", "QN") else "hi" if v else "0" for p in pins.split()]
        L += [f"V{si} vdd{si} 0 {AV}", f"X{si} {' '.join(nodes)} {cell}_ASAP7_75t_{vt}"]
    L += [f"Vhi hi 0 {AV}", ".control"] + [f"option temp={t}\nop\nprint i(V0) i(V1)" for t in ASAP7_T] + [".endc", ".end"]
    out = ngspice(f"{cell}_{vt}", "\n".join(L) + "\n", ("bsimcmg",))
    v = [abs(float(x)) * AV for x in re.findall(r"^i\(v[01]\)\s*=\s*([-+0-9.eE]+)", out, re.M)]
    if ABORT.search(out):
        return f"{cell}_{vt}", _failed("aborted", out)
    if len(v) != 2 * len(ASAP7_T):
        return f"{cell}_{vt}", _failed("missing", out)
    return f"{cell}_{vt}", {t: (v[2 * i] + v[2 * i + 1]) / 2 for i, t in enumerate(ASAP7_T)}


if __name__ == "__main__":
    kit, path = sys.argv[1:3]
    fn, jobs = (ihp, list(IHP)) if kit == "ihp" else (asap7, [(c, v) for c in ASAP7 for v in ("R", "L", "SL")])
    with ThreadPoolExecutor(2) as ex:
        res = dict(ex.map(fn, jobs))
    json.dump(res, open(path, "w"), indent=1)
    print(sum("failed" not in v for v in res.values()), "of", len(res), "cases solved")
