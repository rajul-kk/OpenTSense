"""Temperature sensors simulated as circuits in ngspice (goal 18), with the models in the image (power.leak).

    ring(kit, corner, vdd, temps_C, stages=RING_STAGES, load_F=RING_LOAD_F) -> {T_C: period (s)} or {"failed": ...}
    dvbe(corner, temps_C, ratio=DVBE_RATIO, i_A=DVBE_I_A)                    -> {T_C: dVBE (V)} or {"failed": ...}

ring: a ring oscillator of `stages` minimum inverters (ASAP7 INVx1 RVT at 0.7 V nominal; IHP sg13g2_inv_1 at 1.2 V),
each node loaded by load_F (ASSUMED wiring), started from alternating node levels (uic); the period is the mean
of cycles 7-10, and must agree with cycles 4-7 to RING_SETTLED (a harmonic mode or a start-up still settling
fails). Its frequency falls with temperature and depends on supply and process corner: a ring-oscillator sensor
reads temperature through that curve.
dvbe: the IHP SG13G2 npn13g2 pair of a PTAT sensor, two transistors biased by ideal currents i_A and ratio x i_A;
dVBE = (kT/q) ln(ratio) for an ideal device, so its deviation from that line is the circuit's own error. The bias
circuit (and so its supply sensitivity) is not modelled.
"""
import re

from ..power.leak import ABORT, SPICE, _failed, ngspice

RING_STAGES = 11
RING_LOAD_F = 1e-15
RING_SETTLED = 0.002        # periods over rises 4-7 and 7-10 must agree to 0.2%
DVBE_RATIO, DVBE_I_A = 8, 1e-6
NOMINAL_V = {"asap7": 0.7, "ihp": 1.2}
_IHP_OSDI = ("psp103", "psp103_nqs", "r3_cmc", "mosvar")
_HBT_CORNER = {"tt": "hbt_typ", "ss": "hbt_wcs", "ff": "hbt_bcs"}


def _ring_deck(kit, corner, vdd, temps_C, stages, load_F):
    nodes = [f"n{i}" for i in range(stages)]
    if kit == "asap7":
        head = [f".include {SPICE}/asap7/asap7_{corner}_osdi.lib", f".include {SPICE}/asap7/cells_R.sp"]
        inv = [f"X{i} {nodes[i]} VDD 0 {nodes[(i + 1) % stages]} INVx1_ASAP7_75t_R" for i in range(stages)]
        t_stop, t_step = "4n", "0.5p"
    else:
        head = [f".lib cornerMOSlv.lib mos_{corner}", f".include {SPICE}/ihp/sg13g2_stdcell.spice"]
        inv = [f"X{i} {nodes[(i + 1) % stages]} {nodes[i]} VDD 0 sg13g2_inv_1" for i in range(stages)]
        t_stop, t_step = "16n", "2p"
    caps = [f"C{i} {n} 0 {load_F}" for i, n in enumerate(nodes)]
    ctl = []
    for t in temps_C:
        ctl += [f"option temp={t}", f"tran {t_step} {t_stop} uic",
                f"meas tran a{t} trig v(n0) val={vdd / 2} rise=4 targ v(n0) val={vdd / 2} rise=7",
                f"meas tran b{t} trig v(n0) val={vdd / 2} rise=7 targ v(n0) val={vdd / 2} rise=10"]
    return "\n".join([f"* ring {kit} {corner} {vdd}"] + head + [f"VDD VDD 0 {vdd}"] + inv + caps +
                     # alternating start, one inconsistent stage: a single edge runs round the ring
                     [".ic " + " ".join(f"v({n})={vdd if i % 2 else 0}" for i, n in enumerate(nodes)), ".control"]
                     + ctl + [".endc", ".end"]) + "\n"


def ring(kit, corner, vdd, temps_C, stages=RING_STAGES, load_F=RING_LOAD_F):
    out = ngspice(f"ring_{kit}", _ring_deck(kit, corner, vdd, temps_C, stages, load_F),
                  ("bsimcmg",) if kit == "asap7" else _IHP_OSDI)
    if ABORT.search(out):
        return _failed("aborted", out)
    a, b = ({int(t): float(x) / 3 for t, x in re.findall(rf"^{k}(-?\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)} for k in "ab")
    if len(a) != len(temps_C) or len(b) != len(temps_C):
        return _failed("missing", out)
    if any(abs(a[t] - b[t]) > RING_SETTLED * b[t] for t in b):
        return _failed("unsettled", out)        # period still changing: a harmonic mode or start-up, not a measurement
    return b


def _dvbe_deck(corner, temps_C, ratio, i_A):
    ctl = []
    for t in temps_C:
        ctl += [f"option temp={t}", "op", "print v(e1) v(e2)"]
    return "\n".join([f"* dvbe {corner}", f".lib cornerHBT.lib {_HBT_CORNER[corner]}",
                      # diode-connected npn13g2 pair (collector and base tied to ground, emitter pulled down): VBE = -V(e)
                      f"I1 e1 0 {i_A}", f"I2 e2 0 {ratio * i_A}",
                      "X1 0 0 e1 0 npn13G2 Nx=1", "X2 0 0 e2 0 npn13G2 Nx=1",
                      ".control"] + ctl + [".endc", ".end"]) + "\n"


def dvbe(corner, temps_C, ratio=DVBE_RATIO, i_A=DVBE_I_A):
    out = ngspice("dvbe", _dvbe_deck(corner, temps_C, ratio, i_A), ())      # VBIC is built into ngspice
    if ABORT.search(out):
        return _failed("aborted", out)
    e1 = [float(x) for x in re.findall(r"^v\(e1\)\s*=\s*([-+0-9.eE]+)", out, re.M)]
    e2 = [float(x) for x in re.findall(r"^v\(e2\)\s*=\s*([-+0-9.eE]+)", out, re.M)]
    if len(e1) != len(temps_C) or len(e2) != len(temps_C):
        return _failed("missing", out)
    return {int(t): a - b for t, a, b in zip(temps_C, e1, e2)}      # VBE2 - VBE1, VBE = -V(e)
