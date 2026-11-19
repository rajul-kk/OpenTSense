"""G94 gated run: every case on every stack in all three solvers (registration.md; seed 0, the dry runs used seed 1).

Settings (slot, case lengths, refinement level per solver, tolerance terms) come from `settings.json`, fixed in the
registration from the convergence dry run. Per stack, case and solver: the peak and mean rise per die at every row
end at the solver's level and at one level finer (`solve.py`; the floor is their difference, taken in `evaluate.py`
per bar quantity), and the field at the last row. For the step case, each solver's own steady solve too (bar (a)).
PACT's wall time includes the steady PACT run that captures its matrix.

Usage (opentsense:g94a, repo root): python gates/g94/run.py <out dir>
"""
import json
import os
import sys
import tempfile
import time

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases  # noqa: E402
import solve  # noqa: E402
from opentsense import manifest  # noqa: E402
from opentsense.stack import model  # noqa: E402

SEED = 0


def settings():
    S = json.load(open(os.path.join("gates", "g94", "settings.json")))
    missing = [k for k, v in S.items() if v is None] + [f"level.{k}" for k, v in S["level"].items() if v is None]
    if missing:
        raise SystemExit(f"settings.json not filled in (fixed in the registration): {missing}")
    for lv in S["level"].values():
        solve.check_level(S["slot_s"], lv + 1)
    tau = json.load(open(os.path.join("gates", "g94", "dry", "time_constants.json")))
    if set(tau) != set(cases.STACKS):
        raise SystemExit(f"time constants missing for {set(cases.STACKS) - set(tau)}")
    need = 10 * max(max(v["tau_s"]) for v in tau.values())
    if S["step_slots"] * S["slot_s"] < need or not 0 < S["pulse_on_slots"] < S["pulse_slots"]:
        raise SystemExit(f"step must cover 10 slowest time constants ({need:.3f} s) and the pulse must switch off")
    return S


def main(out):
    S = settings()
    os.makedirs(out, exist_ok=True)
    m = os.path.join(out, "manifest.json")
    if not os.path.exists(m):
        manifest.write(m, {"gate": "G94", "settings": S, "seed": SEED})
    elif json.load(open(m))["settings"] != S:
        raise SystemExit("settings.json differs from this run's manifest; resume only with the settings it started with")
    for name, (cfg, _) in cases.STACKS.items():
        stack = model.load(os.path.join("configs", "stacks", cfg))
        steady_P = {d: v[0] for d, v in cases.step(name, SEED, 1).items()}
        for case, build in cases.builders(name, SEED, S).items():
            path = os.path.join(out, f"{name}_{case}.json")
            if os.path.exists(path):
                continue
            P = build()
            rec, fields = {"slot_s": S["slot_s"], "solvers": {}}, {}
            for solver in solve.SOLVERS:
                lv = S["level"][solver]
                t0 = time.time()
                T = solve.rise(solver, stack, P, S["slot_s"], lv)
                wall = time.time() - t0
                r = {"level": lv, "series": solve.series(T), "wall_s": wall,
                     "series_finer": solve.series(solve.rise(solver, stack, P, S["slot_s"], lv + 1))}
                if case == "step":
                    with tempfile.TemporaryDirectory() as wd:
                        st = solve.SOLVERS[solver](stack, steady_P, wd)
                    r["steady_end_diff_K"] = max(float(np.abs(T[d][-1] - (st[d] - stack.ambient_K)).max()) for d in T)
                rec["solvers"][solver] = r
                fields.update({f"{solver}_{d}": v[-1] for d, v in T.items()})
                print(name, case, solver, f"{wall:.1f} s", flush=True)
            np.savez_compressed(os.path.join(out, f"{name}_{case}_last.npz"), **fields)
            json.dump(rec, open(path + ".tmp", "w"))
            os.replace(path + ".tmp", path)


if __name__ == "__main__":
    main(sys.argv[1])
