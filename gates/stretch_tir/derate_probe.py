"""Goal 14 (stretch, ungated): gate delay against temperature on ASAP7's TT transistor models, for a timing derating.

ASAP7's Liberty has one temperature per corner (TT 25 C, SS 100 C at 0.63 V, FF 0 C), so timing at a stack's
temperature needs a derating. This measures it: a chain of five stages, each loaded by three more copies (fan-out 4),
for INVx1 and NAND2x1 (other input high), RVT cells from the image's cells_R.sp, at VDD 0.7 V, TT models
(asap7_tt_osdi.lib), at each temperature in TEMPS_C. The delay is the mean of the rise and fall 50%-50% delays of the
fourth stage (X3, n3 to n4; the three stages before it set its input slew). The ratio d(T) / d(25 C) is the
derating; the 25 C delay is printed so it can be checked against the Liberty table at the same slew and load.

Usage (in the image): python gates/stretch_tir/derate_probe.py <out.json>
"""
import json
import re
import sys

sys.path.insert(0, ".")
from opentsense.power.leaklib import ngspice  # noqa: E402  (loads the BSIM-CMG OSDI model; one thread per run)

TEMPS_C = (0, 25, 50, 75, 100, 125)
VDD = 0.7
CELLS = {"INVx1": ("INVx1_ASAP7_75t_R", "{i} VDD 0 {o}"), "NAND2x1": ("NAND2x1_ASAP7_75t_R", "{i} VDD VDD 0 {o}")}


def deck(cell, pins, temp):
    lines = ["* derate probe", ".include /opt/spice/asap7/asap7_tt_osdi.lib", ".include /opt/spice/asap7/cells_R.sp",
             f"VDD VDD 0 {VDD}", f"VIN n0 0 PULSE(0 {VDD} 100p 20p 20p 480p 1n)"]
    for s in range(5):
        lines.append(f"X{s} " + pins.format(i=f"n{s}", o=f"n{s + 1}") + f" {cell}")
        for k in range(3):
            lines.append(f"XL{s}_{k} " + pins.format(i=f"n{s + 1}", o=f"d{s}_{k}") + f" {cell}")
    half = VDD / 2
    lines += [".control", f"option temp={temp}", "tran 1p 2n",
              # every stage inverts: the first input edge makes n3 fall and n4 rise, the second the reverse
              f"meas tran tr trig v(n3) val={half} fall=1 targ v(n4) val={half} rise=1",
              f"meas tran tf trig v(n3) val={half} rise=1 targ v(n4) val={half} fall=1",
              ".endc", ".end"]
    return "\n".join(lines) + "\n"


def run(cell, pins, temp):
    out = ngspice("probe", deck(cell, pins, temp), ("bsimcmg",))
    v = {k: float(x) for k, x in re.findall(r"^(tr|tf)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    if set(v) != {"tr", "tf"}:
        raise RuntimeError(f"{cell} at {temp} C: no measurement\n{out[-1500:]}")
    return v


def main(out):
    res = {}
    for name, (cell, pins) in CELLS.items():
        rows = {t: run(cell, pins, t) for t in TEMPS_C}
        d25 = (rows[25]["tr"] + rows[25]["tf"]) / 2
        res[name] = {str(t): {"rise_ps": r["tr"] * 1e12, "fall_ps": r["tf"] * 1e12,
                              "ratio": (r["tr"] + r["tf"]) / 2 / d25} for t, r in rows.items()}
    json.dump({"vdd": VDD, "corner": "TT", "cells": res}, open(out, "w"), indent=1)
    for name, rows in res.items():
        print(name, " ".join(f"{t}C:{r['ratio']:.3f}" for t, r in rows.items()),
              f"(25 C rise {rows['25']['rise_ps']:.2f} ps, fall {rows['25']['fall_ps']:.2f} ps)")


if __name__ == "__main__":
    main(sys.argv[1])
