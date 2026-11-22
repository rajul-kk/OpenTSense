"""Goal 19 (ungated sensitivity, 3D-ICE only): a liquid cold plate whose coolant warms from inlet to outlet, in
place of the gated stacks' uniform cooler coefficient.

The plate (model.ColdPlate, all ASSUMED: a copper microchannel plate, 1 mm fins, 100 um channels and walls, water
at h = 1.5e4 W/(m2 K), laminar in 100 um channels, Nu about 4.5) sits on the lid; its coolant enters at ambient.
Flows FLOWS_ML_MIN: an AIO pump's 1 L/min and a weak 0.25 L/min, and None, the gated stack's uniform coefficient
(the baseline: a floorplan tilts the field by itself, so the coolant's share is the tilt minus the baseline's). Per
stack and flow: common.summary and the tilt of each powered die along x and y (mean rise in the last third minus the
first third of the die's silicon), written to <out>/<stack>_<cell>um_q<flow or uniform>.json (skipped when that
file exists with the same key, common.key).

Usage (in the image, repo root): python gates/g93/sens/coldplate.py <out_dir> <cell_um> <stack>[,<stack>...]
"""
import dataclasses
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from common import stacks  # noqa: E402
from opentsense.stack import model  # noqa: E402
from opentsense.thermal import run  # noqa: E402

FLOWS_ML_MIN = (1000.0, 250.0, None)
PLATE = dict(height_um=1000.0, channel_um=100.0, wall_um=100.0, wall_material="copper", h_top=1.5e4, h_bottom=1.5e4)


def tilt(st, T, P):
    """Per die and powered rectangle: mean rise of the last third minus the first third, along x and along y (K)."""
    out = {}
    for l in st.dies:
        rects = stacks.powered(st, l, P)
        for rect in rects:
            j0, j1, i0, i1 = st.cells(rect)
            r = np.asarray(T[l.name])[i0:i1, j0:j1]
            nx, ny = max(1, r.shape[1] // 3), max(1, r.shape[0] // 3)
            label = l.name if len(rects) == 1 else f"{l.name}@{rect[0]:.0f},{rect[1]:.0f}"
            out[label] = {"x_K": float(r[:, -nx:].mean() - r[:, :nx].mean()),
                          "y_K": float(r[-ny:, :].mean() - r[:ny, :].mean())}
    return out


def main(out_dir, cell_um, names):
    os.makedirs(out_dir, exist_ok=True)
    k = common.key(__file__, cell_um)
    for name in names.split(","):
        st0, P = stacks.build(name, float(cell_um))
        for q in FLOWS_ML_MIN:
            tag = "uniform" if q is None else f"q{q:g}"
            path = os.path.join(out_dir, f"{name}_{float(cell_um):.0f}um_{tag}.json")
            if common.done(path, k):
                print("skip", path)
                continue
            st = st0 if q is None else dataclasses.replace(st0, coldplate=model.ColdPlate(flow_ml_min=q, **PLATE)).validate()
            t0 = time.time()
            with tempfile.TemporaryDirectory() as wd:
                T, it = run.solve_kT(run.run_3dice, st, P, wd)
            total = float(sum(np.sum(p) for p in P.values()))
            rise = None if q is None else total / (st.coldplate.coolant_cv * q * 1e-6 / 60)
            common.write(path, {"key": k, "stack": name, "flow_ml_min": q, "plate": None if q is None else PLATE,
                                "cell_um": float(cell_um), "total_W": total, "coolant_rise_K": rise,
                                "wall_s": round(time.time() - t0, 1), "kT_iterations": it,
                                "dies": common.summary(st, T, P), "tilt": tilt(st, T, P)})


if __name__ == "__main__":
    main(*sys.argv[1:])
