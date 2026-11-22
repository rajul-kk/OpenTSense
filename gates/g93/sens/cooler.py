"""Ungated sensitivity (3D-ICE only): how much the cooler's resistance moves the gated stacks' temperatures.

The cooler is a stated resistance r_sink spread over the lid top (stacks.PACKAGE, ASSUMED). Each stack is solved at
its PACKAGE r_sink times each factor in FACTORS (steady, nominal power, silicon k(T) by thermal.run.solve_kT, the
gated stacks as stacks.build makes them, BEOL included). Per die: common.summary, written to
<out>/<stack>_<cell>um_x<factor>.json (skipped when that file exists with the same key, common.key).
A uniform cooler only: a cold plate's inlet-to-outlet gradient or a non-uniform coefficient is not modelled here.

Usage (in the image, repo root): python gates/g93/sens/cooler.py <out_dir> <cell_um> <stack>[,<stack>...]
"""
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from common import stacks  # noqa: E402
from opentsense.thermal import run  # noqa: E402

FACTORS = (0.5, 1.0, 2.0)


def main(out_dir, cell_um, names):
    os.makedirs(out_dir, exist_ok=True)
    k = common.key(__file__, cell_um)
    for name in names.split(","):
        for f in FACTORS:
            path = os.path.join(out_dir, f"{name}_{float(cell_um):.0f}um_x{f:g}.json")
            if common.done(path, k):
                print("skip", path)
                continue
            r = stacks.PACKAGE[name]["r_sink"] * f
            st, P = stacks.build(name, float(cell_um), r_sink=r)
            t0 = time.time()
            with tempfile.TemporaryDirectory() as wd:
                T, it = run.solve_kT(run.run_3dice, st, P, wd)
            common.write(path, {"key": k, "stack": name, "r_sink_K_per_W": r, "factor": f, "cell_um": float(cell_um),
                                "total_W": float(sum(np.sum(p) for p in P.values())), "wall_s": round(time.time() - t0, 1),
                                "kT_iterations": it, "dies": common.summary(st, T, P)})


if __name__ == "__main__":
    main(*sys.argv[1:])
