"""Goal 14 cases: Ibex's die temperature in the two-die 3D stack, and the cell and wire factors at it.

Temperatures: G93a's 3D-ICE steady fields of the bottom die (Ibex, under the TPU) in gates/g93a/runs/main/3d_fields.npz,
rise over a 300 K ambient, worst seed for the peak and the mean. Factors at temperature T (deg C):
  cell: derate_probe.py's delay ratio d(T) / d(25 C), linear between its temperatures, the larger of INVx1 and NAND2x1;
  wire: rho(T) / rho(25 C) = 1 + ALPHA_CU (T - 25), ALPHA_CU the bulk copper value, an upper bound for narrow lines
        (whose larger residual resistivity lowers the relative coefficient).
The library's own corner is 25 C, so "lib25" (both factors 1) is the reference and must reproduce G97's numbers.

    python gates/stretch_tir/cases.py <derate.json>  -> prints one line per case: name T_C cell_f wire_f
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FIELDS = os.path.join(ROOT, "gates", "g93a", "runs", "main", "3d_fields.npz")
AMBIENT_C = 300.0 - 273.15
ALPHA_CU = 0.0039          # 1/K, bulk copper near room temperature


def die_temps(fields=FIELDS, die="bot", solver="ice"):
    z = np.load(fields)
    maps = [z[k] for k in z.files if k.endswith(f"_{die}_{solver}")]
    return {"peak": AMBIENT_C + max(float(m.max()) for m in maps), "mean": AMBIENT_C + max(float(m.mean()) for m in maps)}


def cell_factor(derate, T):
    out = 0.0
    for rows in derate["cells"].values():
        ts = sorted(float(t) for t in rows)
        rs = [rows[k]["ratio"] for k in sorted(rows, key=float)]
        if not ts[0] <= T <= ts[-1]:
            raise ValueError(f"{T} C outside the probe's {ts[0]}-{ts[-1]} C")
        out = max(out, float(np.interp(T, ts, rs)))
    return out


def cases(derate):
    rows = [("lib25", 25.0, 1.0, 1.0), ("wire_x2_control", 25.0, 1.0, 2.0)]
    for name, T in die_temps().items():
        rows.append((f"stack_{name}", T, cell_factor(derate, T), 1 + ALPHA_CU * (T - 25.0)))
    T, c, w = next(r[1:] for r in rows if r[0] == "stack_peak")   # each factor alone at the peak, to attribute it
    rows += [("peak_cell_only", T, c, 1.0), ("peak_wire_only", T, 1.0, w)]
    return rows


if __name__ == "__main__":
    for r in cases(json.load(open(sys.argv[1]))):
        print(r[0], f"{r[1]:.2f}", f"{r[2]:.5f}", f"{r[3]:.5f}")
