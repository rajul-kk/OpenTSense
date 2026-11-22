"""Goal 15 (ungated sensitivity before G93 registers, 3D-ICE only): leakage rising with temperature in the gated
stacks.

Each stack's nominal power is taken as its power at stacks.LEAK_T_REF_K (85 C), of which a share is leakage on
stacks.LEAK_CURVE (our ASAP7 LVT SPICE curve, G92e); k(T) and leakage settle in one loop (thermal.run.solve_kT with
`leak`). share 0 is the stacks as gated today. Per stack and share: common.summary, the total power at the fixed point
and its ratio to nominal, written to <out>/<stack>_<cell>um_leak<share>.json (skipped when that file exists with the
same key, common.key). A loop that runs away (thermal.run.Runaway) is recorded as such, with the solve it was
detected at; any other failure (the tool, or no settling in MAX_IT solves) stops the script, so it is not cached.

Usage (in the image, repo root): python gates/g93/sens/leak.py <out_dir> <cell_um> <stack>[,<stack>...]
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

SHARES = (0.0, 0.1, 0.25, 0.4)
MAX_IT = 40


def main(out_dir, cell_um, names):
    os.makedirs(out_dir, exist_ok=True)
    k = common.key(__file__, cell_um)
    for name in names.split(","):
        st, P = stacks.build(name, float(cell_um))
        nominal = float(sum(np.sum(p) for p in P.values()))
        for s in SHARES:
            path = os.path.join(out_dir, f"{name}_{float(cell_um):.0f}um_leak{s:g}.json")
            if common.done(path, k):
                print("skip", path)
                continue
            dyn, leak = stacks.leakage(P, s)
            rec = {"key": k, "stack": name, "share": s, "cell_um": float(cell_um), "nominal_W": nominal}
            t0 = time.time()
            try:
                with tempfile.TemporaryDirectory() as wd:
                    T, it = run.solve_kT(run.run_3dice, st, dyn, wd, max_it=MAX_IT, leak=leak)
            except run.Runaway as e:
                rec.update(settled=False, runaway=str(e), wall_s=round(time.time() - t0, 1))
                common.write(path, rec)
                continue
            L = leak(T)
            total = float(sum(np.sum(dyn[d]) + np.sum(L[d]) for d in dyn))
            rec.update(settled=True, total_W=total, power_ratio=total / nominal, wall_s=round(time.time() - t0, 1),
                       iterations=it, dies=common.summary(st, T, P))
            common.write(path, rec)


if __name__ == "__main__":
    main(*sys.argv[1:])
