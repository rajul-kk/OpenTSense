"""Score G94 (registration.md) from run.py's output. Every solver pair, at all times (student, 16 Nov).

Floor of a solver on a quantity = its change between its level and one level finer (`solve.py`'s rule, run.py's
series_finer); a pair's floor is the larger of its two solvers'. Series are at row resolution (slot / 2^level); (c)
compares each pair on its common row grid (the coarser level's rows), (b) uses each series at its own resolution.
Settings and tolerances: the run's manifest (settings.json as run).
- (a) step end: each solver's last step row equals its own steady solve within a_K, every stack.
- (b) time to 63% of the step's final peak rise, per die: |t_a - t_b| <= max(3 x floor, tol_b_rel x mean(t_a, t_b)).
- (c) peak rise against time, per die and case: max_t |p_a - p_b| <= max(3 x floor, tol_c_K).

Usage (repo root): python gates/g94/evaluate.py <run dir>
"""
import itertools
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases  # noqa: E402
from solve import on_grid, t63  # noqa: E402


def main(run):
    S = json.load(open(os.path.join(run, "manifest.json")))["settings"]
    slot, out = S["slot_s"], {"a": {}, "b": {}, "c": {}}
    for name in cases.STACKS:
        for case in cases.names(name):
            R = json.load(open(os.path.join(run, f"{name}_{case}.json")))["solvers"]
            SOLVERS = list(R)
            dies = R[SOLVERS[0]]["series"]
            lv = {s: R[s]["level"] for s in SOLVERS}
            for d in dies:
                raw = {s: R[s]["series"][d]["peak"] for s in SOLVERS}
                fine = {s: R[s]["series_finer"][d]["peak"] for s in SOLVERS}
                for a, b in itertools.combinations(SOLVERS, 2):
                    key = f"{name} {case} {d} {a}-{b}"
                    g = min(lv[a], lv[b])                       # the pair's common row grid
                    pa, pb = on_grid(raw[a], lv[a], g), on_grid(raw[b], lv[b], g)
                    fa = float(np.abs(pa - on_grid(fine[a], lv[a] + 1, g)).max())
                    fb = float(np.abs(pb - on_grid(fine[b], lv[b] + 1, g)).max())
                    diff = float(np.abs(pa - pb).max())
                    bar = max(3 * max(fa, fb), S["tol_c_K"])
                    out["c"][key] = {"max_diff_K": diff, "bar_K": bar, "ok": diff <= bar}
                    if case == "step":
                        dt = {s: slot / 2 ** lv[s] for s in (a, b)}
                        ta, tb = t63(raw[a], dt[a]), t63(raw[b], dt[b])
                        fa = abs(ta - t63(fine[a], dt[a] / 2))
                        fb = abs(tb - t63(fine[b], dt[b] / 2))
                        bar = max(3 * max(fa, fb), S["tol_b_rel"] * (ta + tb) / 2)
                        out["b"][key] = {"t63_s": [ta, tb], "bar_s": bar, "ok": abs(ta - tb) <= bar}
            if case == "step":
                for s in SOLVERS:
                    e = R[s]["steady_end_diff_K"]
                    out["a"][f"{name} {s}"] = {"diff_K": e, "ok": e <= S["a_K"]}
    passed = {k: all(v["ok"] for v in out[k].values()) for k in ("a", "b", "c")}
    out["verdict"] = "PASS" if all(passed.values()) else "FAIL"
    out["passed"] = passed
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    print(out["verdict"], passed, {k: sum(not v["ok"] for v in out[k].values()) for k in ("a", "b", "c")})


if __name__ == "__main__":
    main(sys.argv[1])
