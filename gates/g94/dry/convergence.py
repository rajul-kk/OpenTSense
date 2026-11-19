"""G94 dry: refinement convergence of each solver against itself (draft.md, "Time-step convergence first").

Step case of seed 1 (the gated run uses seed 0) on every stack, refined by `solve.py`'s rule (level L: 2^L rows per
slot, one step per row, for all three solvers). No cross-solver difference is computed or printed. Per level, against
the previous level: the largest change of the peak rise at the previous level's row ends (absolute and relative),
the change of t63 (each at its own row resolution, as bar (b) uses it), and the wall time.

Usage (opentsense:g94a, repo root): python gates/g94/dry/convergence.py <slot_s> <n_slots> <levels> <out.json>
"""
import json
import os
import sys
import time

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases  # noqa: E402
import solve  # noqa: E402
from opentsense.stack import model  # noqa: E402


def main(slot, n_slots, levels, out):
    slot, n_slots, levels = float(slot), int(n_slots), int(levels)
    for lv in range(levels):
        solve.check_level(slot, lv)
    res = {"slot_s": slot, "n_slots": n_slots, "levels": levels, "stacks": {}}
    if os.path.exists(out):
        old = json.load(open(out))
        if {k: old.get(k) for k in ("slot_s", "n_slots", "levels")} != {k: res[k] for k in ("slot_s", "n_slots", "levels")}:
            raise SystemExit(f"{out} was made with other arguments; use a new file")
        res = old
    for name, (cfg, _) in cases.STACKS.items():
        if name in res["stacks"]:
            continue
        stack = model.load(os.path.join("configs", "stacks", cfg))
        P = cases.step(name, 1, n_slots)
        res["stacks"][name] = {}
        for solver in solve.SOLVERS:
            prev, rows = None, []
            for lv in range(levels):
                t0 = time.time()
                pk = {d: np.array(s["peak"]) for d, s in solve.series(solve.rise(solver, stack, P, slot, lv)).items()}
                tc = {d: solve.t63(v, slot / 2 ** lv) for d, v in pk.items()}
                row = {"level": lv, "wall_s": time.time() - t0, "t63_s": tc,
                       "final_peak_rise_K": {d: float(v[-1]) for d, v in pk.items()}}
                if prev is not None:
                    ch = {d: np.abs(solve.on_grid(pk[d], lv, lv - 1) - prev[0][d]) for d in pk}
                    row["max_change_K"] = max(float(c.max()) for c in ch.values())
                    row["max_change_rel"] = max(float((ch[d] / np.maximum(prev[0][d], 1e-12)).max()) for d in pk)
                    row["t63_change_rel"] = max(abs(tc[d] - prev[1][d]) / prev[1][d] for d in pk)
                rows.append(row)
                prev = (pk, tc)
                print(name, solver, {k: v for k, v in row.items() if k != "final_peak_rise_K"}, flush=True)
            res["stacks"][name][solver] = rows
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
