"""G94 dry: where in time the peak-rise change between refinement levels sits (goals.md, G94, 17 Nov: the change
stays 2-3 K at every level while t63's change halves).

The 3d stack's step case of seed 1 (power switched on at t = 0 and held), as convergence.py, for 3D-ICE and PACT.
Per level against the previous one, per die: the time of the largest change, and the largest change inside and after
the first 1, 5 and 25 ms. If the floor is the backward-Euler error just after the step, it sits in the first
milliseconds and the change after them falls with the level.

Usage (opentsense:g94b, repo root): python gates/g94/dry/locate_change.py <n_slots> <levels> <out.json>
"""
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases  # noqa: E402
import solve  # noqa: E402
from opentsense.stack import model  # noqa: E402

SLOT = 0.005
WINDOWS_S = (0.001, 0.005, 0.025)


def change_profile(fine, coarse, lv, dt_coarse):
    """Largest |change| of the coarse level's row-end peaks, overall and split at each window."""
    ch = np.abs(solve.on_grid(fine, lv, lv - 1) - coarse)
    t = dt_coarse * (np.arange(len(ch)) + 1)
    out = {"max_K": float(ch.max()), "t_of_max_s": float(t[int(ch.argmax())])}
    for w in WINDOWS_S:
        out[f"max_K_t<={w * 1e3:g}ms"] = float(ch[t <= w + 1e-12].max(initial=0))
        out[f"max_K_t>{w * 1e3:g}ms"] = float(ch[t > w + 1e-12].max(initial=0))
    return out


def main(n_slots, levels, out):
    n_slots, levels = int(n_slots), int(levels)
    stack = model.load(os.path.join("configs", "stacks", cases.STACKS["3d"][0]))
    P = cases.step("3d", 1, n_slots)
    res = {"slot_s": SLOT, "n_slots": n_slots, "levels": levels, "solvers": {}}
    for solver in ("ice", "pact"):
        prev, rows = None, []
        for lv in range(levels):
            pk = {d: np.array(s["peak"]) for d, s in solve.series(solve.rise(solver, stack, P, SLOT, lv)).items()}
            if prev is not None:
                row = {"level": lv, "dies": {d: change_profile(pk[d], prev[d], lv, SLOT / 2 ** (lv - 1)) for d in pk}}
                rows.append(row)
                print(solver, json.dumps(row), flush=True)
            prev = pk
        res["solvers"][solver] = rows
        with open(out + ".tmp", "w") as f:
            json.dump(res, f, indent=1)
        os.replace(out + ".tmp", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
