"""G93 gated run, one unit = (stack, solver): the stack at the registered 500 um cells with leakage at a 10% share of
each cell's nominal power at the 85 C reference, k(T) and leakage settled by thermal.run.solve_kT (registration.md).

Writes <out>/<stack>_<solver>.json (common.summary per die or S3 region, iterations, total power, wall time, `inputs`
and `image`) and <stack>_<solver>.npz (each die's settled temperature map, K) for evaluate.py's RMS. A loop that runs
away or does not settle in MAX_IT solves is recorded (settled false, with the reason); one that reaches its time
budget is recorded as settled null (evaluate.py counts it as missing); a tool failure stops the unit with no
output. total_W is the power at the settled maps (they moved less than the loop's 0.01 K at the last solve).
A finished unit whose JSON (and, if settled, maps) exists with the same inputs and image is skipped (A17); any other
existing unit (other inputs or image, out of time, or maps missing) is kept as <stack>_<solver>_v<n> before the new
run writes (A14).

`inputs` = floor.py's hash of the solver code, converters, patches and floorplans, plus this file: the parity units
of the same session (floor.py, S2 on the gated mesh) carry the first part, so a gated unit is tied to a build whose
parity was checked.

Usage (in the image or on Kaggle, repo root): python gates/g93/run.py <out_dir> <stack> <solver> [<budget_s>]
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "dry"), os.path.join(HERE, "sens")]
import common  # noqa: E402
import floor  # noqa: E402
from common import stacks  # noqa: E402
from opentsense.manifest import write_json  # noqa: E402
from opentsense.thermal import run  # noqa: E402

CELL_UM = floor.CELL_UM
LEAK_SHARE = 0.10
MAX_IT = 40
NOT_SETTLED = "k(T) and leakage loop did not settle"   # solve_kT's message (thermal/run.py is hashed into inputs,
# so it cannot gain its own exception class without changing the parity reference)


def inputs():
    return floor.inputs() + "+" + hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:8]


class OutOfTime(Exception):
    pass


def timed(runner, deadline, solves):
    """The runner, refusing to start a solve after `deadline` and giving each one only the time left; counts solves."""
    def f(stack, power, workdir):
        left = deadline - time.time()
        if left <= 0:
            raise OutOfTime
        solves.append(time.time())
        print(f"solve {len(solves)}", flush=True)
        try:
            return runner(stack, power, workdir, timeout=int(left))
        except subprocess.TimeoutExpired:
            raise OutOfTime
    return f


def main(out_dir, name, solver, budget_s=7200):
    os.makedirs(out_dir, exist_ok=True)
    tag = {"inputs": inputs(), "image": os.environ.get("OTS_IMAGE", "unknown")}
    path = os.path.join(out_dir, f"{name}_{solver}.json")
    if os.path.exists(path):
        old = json.load(open(path))
        maps_ok = not old.get("settled") or os.path.exists(path[:-5] + ".npz")
        if old.get("settled") is not None and maps_ok and all(old.get(k) == v for k, v in tag.items()):
            print("skip", path)
            return
    if os.path.exists(path):
        v = 0
        while os.path.exists(f"{path[:-5]}_v{v}.json"):
            v += 1
        for ext in (".json", ".npz"):
            if os.path.exists(path[:-5] + ext):
                os.replace(path[:-5] + ext, f"{path[:-5]}_v{v}{ext}")
    st, P = stacks.build(name, CELL_UM)
    dyn, leak = stacks.leakage(P, LEAK_SHARE)
    nominal = float(sum(np.sum(p) for p in P.values()))
    rec = {**tag, "stack": name, "solver": solver, "cell_um": CELL_UM, "leak_share": LEAK_SHARE, "grid": list(st.grid),
           "nominal_W": nominal}
    t0, solves = time.time(), []
    try:
        with tempfile.TemporaryDirectory() as wd:
            T, it = run.solve_kT(timed(floor.RUN[solver], t0 + float(budget_s), solves), st, dyn, wd,
                                 max_it=MAX_IT, leak=leak)
    except OutOfTime:
        rec.update(settled=None, why=f"out of time ({float(budget_s):.0f} s) in solve {len(solves)}",
                   wall_s=round(time.time() - t0, 1))
        write_json(rec, path)
        print(f"{name} {solver} out of time", flush=True)
        return
    except RuntimeError as e:
        if not (isinstance(e, run.Runaway) or str(e).startswith(NOT_SETTLED)):
            raise
        rec.update(settled=False, why=str(e), iterations=len(solves), wall_s=round(time.time() - t0, 1))
        write_json(rec, path)
        print(f"{name} {solver} not settled", flush=True)
        return
    L = leak(T)
    total = float(sum(np.sum(dyn[d]) + np.sum(L[d]) for d in dyn))
    np.savez_compressed(os.path.join(out_dir, f"{name}_{solver}.npz"), **{d: np.asarray(T[d]) for d in T})
    rec.update(settled=True, iterations=it, total_W=total, power_ratio=total / nominal,
               wall_s=round(time.time() - t0, 1), dies=common.summary(st, T, P))
    write_json(rec, path)
    print(f"{name} {solver} {rec['wall_s']} s, {it} solves", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
