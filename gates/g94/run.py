"""G94 gated run: every case on every stack in all three solvers (registration.md; seed 0, the dry runs used seed 1).

Settings (slot, case lengths, refinement level per solver, tolerance terms) come from `settings.json`, fixed in the
registration from the dry runs. One unit = (stack, case, solver): the peak and mean rise per die at every row end at
the solver's level and at one level finer (`solve.py`; the floor is their difference, taken in `evaluate.py` per bar
quantity), the field at the last row, and for the step case the solver's own steady solve (bar (a)). Units are
independent, so they can run on different machines (HotSpot on Kaggle, `kaggle_gate_hs.py`); each machine's output
directory holds a manifest of the settings it ran with, and `evaluate.py` refuses a run whose manifests differ.
PACT's wall time includes the steady PACT run that captures its matrix.

Usage (opentsense:g94b, repo root): python gates/g94/run.py <out dir> [solver,...] [stack:case,...]
(defaults: every solver, every unit)
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


def units():
    """Every (stack, case) of the gate."""
    return [(name, case) for name in cases.STACKS for case in cases.names(name)]


def start(out, name="manifest.json"):
    """The settings, after writing (or checking against) this output directory's manifest."""
    S = settings()
    os.makedirs(out, exist_ok=True)
    m = os.path.join(out, name)
    if not os.path.exists(m):
        manifest.write(m, {"gate": "G94", "settings": S, "seed": SEED})
    j = json.load(open(m))
    if (j["settings"], j.get("seed")) != (S, SEED):
        raise SystemExit("settings.json or the seed differs from this run's manifest; resume only with what it started with")
    return S


def unit(out, S, name, case, solver):
    path = os.path.join(out, f"{name}_{case}_{solver}.json")
    if os.path.exists(path):
        return
    stack = model.load(os.path.join("configs", "stacks", cases.STACKS[name][0]))
    P = cases.builders(name, SEED, S)[case]()
    lv = S["level"][solver]
    t0 = time.time()
    T = solve.rise(solver, stack, P, S["slot_s"], lv)
    r = {"level": lv, "series": solve.series(T), "wall_s": time.time() - t0,
         "series_finer": solve.series(solve.rise(solver, stack, P, S["slot_s"], lv + 1))}
    if case == "step":
        with tempfile.TemporaryDirectory() as wd:
            st = solve.SOLVERS[solver](stack, {d: v[0] for d, v in P.items()}, wd)
        r["steady_end_diff_K"] = max(float(np.abs(T[d][-1] - (st[d] - stack.ambient_K)).max()) for d in T)
    np.savez_compressed(os.path.join(out, f"{name}_{case}_{solver}_last.npz"), **{d: v[-1] for d, v in T.items()})
    manifest.write_json(r, path)
    print(name, case, solver, f"{r['wall_s']:.1f} s", flush=True)


def main(out, solvers=None, todo=None):
    S = start(out)
    solvers = solvers.split(",") if solvers else list(solve.SOLVERS)
    todo = [tuple(u.split(":")) for u in todo.split(",")] if todo else units()
    if not set(solvers) <= set(solve.SOLVERS) or not set(todo) <= set(units()):
        raise SystemExit(f"unknown solver or unit: {solvers} {todo}")
    for name, case in todo:
        for solver in solvers:
            unit(out, S, name, case, solver)


if __name__ == "__main__":
    main(*sys.argv[1:4])
