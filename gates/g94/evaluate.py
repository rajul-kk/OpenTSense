"""Score G94 (registration.md) from run.py's units. Every solver pair (student, 16 Nov); bar (c) after the first 5 ms
(student, 17 Nov; the first 5 ms reported).

Floor of a solver on a quantity = its change between its level and one level finer (`solve.py`'s rule, run.py's
series_finer), over the same times as the quantity; a pair's floor is the larger of its two solvers'. Series are at
row resolution (slot / 2^level); (c) compares each pair on its common row grid (the coarser level's rows), (b) uses
each series at its own resolution. Settings and tolerances: the run's manifests (settings.json as run).
- (a) step end: each solver's last step row equals its own steady solve within a_K, every stack.
- (b) time to 63% of the step's final peak rise, per die: |t_a - t_b| <= max(3 x floor, tol_b_rel x mean(t_a, t_b)).
- (c) peak rise against time for t > 5 ms, per die and case: max |p_a - p_b| <= max(3 x floor, tol_c_K).
Validity (INCONCLUSIVE otherwise): every unit of every solver present, every manifest in the run directory (one per
machine) holds the same settings, and every unit ran at its solver's level in them.

Usage (repo root): python gates/g94/evaluate.py <run dir>
"""
import glob
import itertools
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import solve  # noqa: E402
from run import SEED, units  # noqa: E402
from run import settings as run_settings  # noqa: E402
from solve import on_grid, t63  # noqa: E402

AFTER_S = 0.005


def finite(u):
    series = [v for k in ("series", "series_finer") for d in u[k].values() for v in d.values()]
    return all(np.isfinite(v).all() for v in series) and np.isfinite(u.get("steady_end_diff_K", 0.0))


def load(run):
    """(settings, {(stack, case): {solver: unit}}) or (None, reason)."""
    ms = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(run, "manifest*.json")))]
    S = run_settings()
    if not ms or any(m["settings"] != S or m.get("seed") != SEED for m in ms):
        return None, f"{len(ms)} manifests; none, or settings or seed differ from settings.json and seed {SEED}"
    R = {}
    for name, case in units():
        for s in solve.SOLVERS:
            p = os.path.join(run, f"{name}_{case}_{s}.json")
            if not os.path.exists(p):
                return None, f"missing {p}"
            u = json.load(open(p))
            if u["level"] != S["level"][s]:
                return None, f"{p} ran at level {u['level']}"
            if not finite(u):
                return None, f"{p} holds a non-finite value"
            R.setdefault((name, case), {})[s] = u
    return S, R


def main(run):
    S, R = load(run)
    if S is None:
        out = {"verdict": "INCONCLUSIVE", "valid": False, "reason": R}
        json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
        print(json.dumps(out))
        return
    slot, out = S["slot_s"], {"a": {}, "b": {}, "c": {}, "first_5ms": {}, "rms_K": {}, "floor_K": {}, "wall_s": {}}
    for (name, case), U in R.items():
        lv = {s: U[s]["level"] for s in U}
        out["wall_s"].update({f"{name} {case} {s}": U[s]["wall_s"] for s in U})
        for d in U[next(iter(U))]["series"]:
            raw = {s: U[s]["series"][d]["peak"] for s in U}
            fine = {s: U[s]["series_finer"][d]["peak"] for s in U}
            for a, b in itertools.combinations(U, 2):
                key = f"{name} {case} {d} {a}-{b}"
                g = min(lv[a], lv[b])                       # the pair's common row grid
                pa, pb = on_grid(raw[a], lv[a], g), on_grid(raw[b], lv[b], g)
                late = slot / 2 ** g * (np.arange(len(pa)) + 1) > AFTER_S + 1e-12
                fa = float(np.abs(pa - on_grid(fine[a], lv[a] + 1, g))[late].max())
                fb = float(np.abs(pb - on_grid(fine[b], lv[b] + 1, g))[late].max())
                diff = np.abs(pa - pb)
                bar = max(3 * max(fa, fb), S["tol_c_K"])
                out["c"][key] = {"max_diff_K": float(diff[late].max()), "bar_K": bar, "ok": diff[late].max() <= bar}
                out["first_5ms"][key] = float(diff[~late].max())
                out["rms_K"][key] = float(np.sqrt(np.mean(diff[late] ** 2)))
                out["floor_K"][f"{name} {case} {d} {a}"] = fa
                out["floor_K"][f"{name} {case} {d} {b}"] = fb
                if case == "step":
                    dt = {s: slot / 2 ** lv[s] for s in (a, b)}
                    ta, tb = t63(raw[a], dt[a]), t63(raw[b], dt[b])
                    fa = abs(ta - t63(fine[a], dt[a] / 2))
                    fb = abs(tb - t63(fine[b], dt[b] / 2))
                    bar = max(3 * max(fa, fb), S["tol_b_rel"] * (ta + tb) / 2)
                    out["b"][key] = {"t63_s": [ta, tb], "bar_s": bar, "ok": abs(ta - tb) <= bar}
        if case == "step":
            for s in U:
                e = U[s]["steady_end_diff_K"]
                out["a"][f"{name} {s}"] = {"diff_K": e, "ok": e <= S["a_K"]}
    passed = {k: all(v["ok"] for v in out[k].values()) for k in ("a", "b", "c")}
    out.update(verdict="PASS" if all(passed.values()) else "FAIL", valid=True, passed=passed)
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1, default=bool)
    print(out["verdict"], passed, {k: sum(not v["ok"] for v in out[k].values()) for k in ("a", "b", "c")})


if __name__ == "__main__":
    main(sys.argv[1])
