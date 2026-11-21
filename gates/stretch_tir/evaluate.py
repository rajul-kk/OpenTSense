"""Goal 14: slack and worst IR drop per case (run.sh's output) against the 25 C library reference.

Controls, printed as PASS/FAIL lines: lib25 reproduces G97's recorded k3 worst VDD drop and VSS rise (FULL source,
gates/g97/record/result.json) to 1 uV; wire_x2_control's VDD drop is 1.8x to 2.2x lib25's (PDNSim reads the scaled
layer resistances; a static grid's drop is linear in R at fixed currents). Writes <run>/result.json.

    python gates/stretch_tir/evaluate.py <run dir>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from opentsense.power.pdnsim import voltages  # noqa: E402

VDD = 0.7
G97 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "g97", "record", "result.json")


def case(d):
    log = open(os.path.join(d, "sta_ir.log")).read()
    slack = dict(re.findall(r"^(SETUP|HOLD):\s*\n\s*worst slack\s+(?:max|min)?\s*([-0-9.]+)", log, re.M))
    tns = re.search(r"^tns\s+(?:max\s+)?([-0-9.]+)", log, re.M)
    supplies = [float(v) for v in re.findall(r"Supply voltage\s*:\s*(\S+) V", log)]
    if sorted(supplies) != [0.0, VDD]:
        raise ValueError(f"{d}: PDNSim's supply voltages {supplies}, expected VSS 0 and VDD {VDD}")
    vdd = voltages(os.path.join(d, "v_VDD.csv"), min)
    vss = voltages(os.path.join(d, "v_VSS.csv"), max)
    return {"setup_wns_ps": float(slack["SETUP"]), "hold_wns_ps": float(slack["HOLD"]),
            "tns_ps": float(tns.group(1)) if tns else None,
            "worst_vdd_drop_mV": 1e3 * (VDD - min(vdd.values())), "worst_vss_rise_mV": 1e3 * max(vss.values())}


def g97_k3():
    return json.load(open(G97))["windows"]["k3"]["FULL"]


def main(run):
    cases = [l.split() for l in open(os.path.join(run, "cases.txt"))]
    res = {n: {"T_C": float(T), "cell_f": float(c), "wire_f": float(w), **case(os.path.join(run, n))}
           for n, T, c, w in cases}
    ref = res["lib25"]
    for r in res.values():
        r["d_setup_wns_ps"] = r["setup_wns_ps"] - ref["setup_wns_ps"]
        r["vdd_drop_ratio"] = r["worst_vdd_drop_mV"] / ref["worst_vdd_drop_mV"]
    x2 = res["wire_x2_control"]["vdd_drop_ratio"]
    controls = {"wire_x2_ratio_in_1.8_2.2": 1.8 <= x2 <= 2.2}
    try:
        g = g97_k3()
        controls["lib25_reproduces_g97"] = (abs(g["worst_vdd_drop_mV"] - ref["worst_vdd_drop_mV"]) < 1e-3 and
                                            abs(g["worst_vss_rise_mV"] - ref["worst_vss_rise_mV"]) < 1e-3)
    except KeyError as e:
        controls["lib25_reproduces_g97"] = False
        controls["lib25_reproduces_g97_error"] = f"not checked: G97 record layout ({e!r})"
    out = {"cases": res, "controls": controls}
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    for n, r in res.items():
        print(f"{n:16s} T={r['T_C']:6.2f}C cell={r['cell_f']:.4f} wire={r['wire_f']:.4f} setup WNS "
              f"{r['setup_wns_ps']:8.2f} ps (d {r['d_setup_wns_ps']:+.2f}) hold {r['hold_wns_ps']:7.2f} ps "
              f"VDD drop {r['worst_vdd_drop_mV']:.3f} mV (x{r['vdd_drop_ratio']:.3f}) "
              f"VSS rise {r['worst_vss_rise_mV']:.3f} mV")
    for k, v in controls.items():
        print("CONTROL", k, v)


if __name__ == "__main__":
    main(sys.argv[1])
