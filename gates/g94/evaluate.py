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
machine) holds the same settings, and every unit ran at its solver's level in them, holds every die of its stack at
the case's row count at both levels, and only finite values (`problem`; Amendment 1).

Usage (repo root): python gates/g94/evaluate.py <run dir>
"""
import glob
import itertools
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases
import solve
from run import SEED, units
from run import settings as run_settings
from solve import on_grid, t63

AFTER_S = 0.005


def read(path):
    with open(path) as f:
        return json.load(f)


def write(out, run):
    with open(os.path.join(run, "result.json"), "w") as f:
        json.dump(out, f, indent=1, default=bool)


def problem(u, dies, n_slots, case):
    """Why a unit is not what the registration ran (its stack's dies, n_slots * 2^level rows at its level and twice
    that one level finer, finite values), or None."""
    for key, lv in (("series", u["level"]), ("series_finer", u["level"] + 1)):
        if set(u[key]) != dies:
            return f"{key} dies {sorted(u[key])}, expected {sorted(dies)}"
        for d, q in u[key].items():
            if set(q) != {"peak", "mean"} or any(len(v) != n_slots * 2 ** lv for v in q.values()):
                return f"{key} {d}: rows {[len(v) for v in q.values()]}, expected {n_slots * 2 ** lv}"
            for v in q.values():
                a = np.asarray(v)               # a list of plain numbers: 1-D, int or float (None makes it object)
                if a.ndim != 1 or a.dtype.kind not in "if" or not np.isfinite(a).all():
                    return f"{key} {d} holds a non-finite or non-numeric value"
    scalars = ["wall_s"] + (["steady_end_diff_K"] if case == "step" else [])
    number = (int, float)
    if not all(isinstance(u.get(k), number) and not isinstance(u.get(k), bool) and np.isfinite(u[k]) for k in scalars):
        return f"missing or non-finite {scalars}"
    return None


def load(run):
    """(settings, {(stack, case): {solver: unit}}) or (None, reason)."""
    ms = [read(p) for p in sorted(glob.glob(os.path.join(run, "manifest*.json")))]
    S = run_settings()
    if not ms or any(m["settings"] != S or m.get("seed") != SEED for m in ms):
        return None, f"{len(ms)} manifests; none, or settings or seed differ from settings.json and seed {SEED}"
    R = {}
    for name, case in units():
        dies = set(cases.STACKS[name][1])
        n_slots = cases.n_slots(case, S, SEED)
        for s in solve.SOLVERS:
            p = os.path.join(run, f"{name}_{case}_{s}.json")
            if not os.path.exists(p):
                return None, f"missing {p}"
            u = read(p)
            if u["level"] != S["level"][s]:
                return None, f"{p} ran at level {u['level']}"
            why = problem(u, dies, n_slots, case)
            if why:
                return None, f"{p}: {why}"
            R.setdefault((name, case), {})[s] = u
    return S, R


def trajectories(S, A, B):
    """Bar (c) for one pair on one die: A, B = (level, peak series, peak series one level finer). Returns the bar
    entry, the first-5 ms and RMS differences, and each solver's floor."""
    g = min(A[0], B[0])                                     # the pair's common row grid
    pa, pb = on_grid(A[1], A[0], g), on_grid(B[1], B[0], g)
    late = S["slot_s"] / 2 ** g * (np.arange(len(pa)) + 1) > AFTER_S + 1e-12
    fa = float(np.abs(pa - on_grid(A[2], A[0] + 1, g))[late].max())
    fb = float(np.abs(pb - on_grid(B[2], B[0] + 1, g))[late].max())
    diff = np.abs(pa - pb)
    bar = max(3 * max(fa, fb), S["tol_c_K"])
    c = {"max_diff_K": float(diff[late].max()), "bar_K": bar, "ok": diff[late].max() <= bar}
    return c, float(diff[~late].max()), float(np.sqrt(np.mean(diff[late] ** 2))), fa, fb


def time_constants(S, A, B):
    """Bar (b) for one pair on one die (step case), A and B as in `trajectories`."""
    t, floor = [], []
    for lv, raw, fine in (A, B):
        dt = S["slot_s"] / 2 ** lv
        t.append(t63(raw, dt))
        floor.append(abs(t[-1] - t63(fine, dt / 2)))
    bar = max(3 * max(floor), S["tol_b_rel"] * (t[0] + t[1]) / 2)
    return {"t63_s": t, "bar_s": bar, "ok": abs(t[0] - t[1]) <= bar}


def main(run):
    S, R = load(run)
    if S is None:
        out = {"verdict": "INCONCLUSIVE", "valid": False, "reason": R}
        write(out, run)
        print(json.dumps(out))
        return
    # level_solve_s: run.py's wall_s, the transient at the unit's level plus its reduction to series (PACT: with the
    # steady run that captures its matrix); not level + 1, the steady check or the writes, so not a unit's wall time
    out = {"a": {}, "b": {}, "c": {}, "first_5ms": {}, "rms_K": {}, "floor_K": {}, "level_solve_s": {}}
    for (name, case), U in R.items():
        out["level_solve_s"].update({f"{name} {case} {s}": U[s]["wall_s"] for s in U})
        for d in U[next(iter(U))]["series"]:
            q = {s: (U[s]["level"], U[s]["series"][d]["peak"], U[s]["series_finer"][d]["peak"]) for s in U}
            for a, b in itertools.combinations(U, 2):
                key = f"{name} {case} {d} {a}-{b}"
                out["c"][key], out["first_5ms"][key], out["rms_K"][key], fa, fb = trajectories(S, q[a], q[b])
                out["floor_K"][f"{name} {case} {d} {a}"] = fa
                out["floor_K"][f"{name} {case} {d} {b}"] = fb
                if case == "step":
                    out["b"][key] = time_constants(S, q[a], q[b])
        if case == "step":
            for s in U:
                e = U[s]["steady_end_diff_K"]
                out["a"][f"{name} {s}"] = {"diff_K": e, "ok": e <= S["a_K"]}
    passed = {k: all(v["ok"] for v in out[k].values()) for k in ("a", "b", "c")}
    out.update(verdict="PASS" if all(passed.values()) else "FAIL", valid=True, passed=passed)
    write(out, run)
    print(out["verdict"], passed, {k: sum(not v["ok"] for v in out[k].values()) for k in ("a", "b", "c")})


if __name__ == "__main__":
    main(sys.argv[1])
