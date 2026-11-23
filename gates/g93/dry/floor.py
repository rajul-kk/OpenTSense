"""G93 noise floor (before registration; draft "Bars by the noise-floor rule"): how far each solver's own answer moves
when every cell of the gated 500 um mesh is split in four, on S1, S2 and S4 (S3 refined is about 1.5 M nodes).

The refined stack is the 500 um stack with its grid doubled (`refine`): the same layers, lid, die positions and
regions (all on the 500 um grid, so on the finer one too), and each cell's power split evenly over its four
children. Building at 250 um instead would move S2's DRAM banks and the lid margins (both are rounded to whole
cells), so the change would mix layout with mesh error.

One linear solve per unit: each die's nominal power (the gated power at the 85 C leakage reference) with every
temperature-dependent material at 85 C (thermal.run.stack_at), not the 4 to 9 solves of the k(T) and leakage loop
(sens/leak_runs); the floor is relative to the peak rise and the gate applies it to its own loop-settled rises.

A unit is (stack, factor, solver): common.summary per die written to <out>/<stack>_x<factor>_<solver>.json with
`inputs` (hash of the code and floorplans that set the result) and `image` apart, skipped when that file exists with
the same inputs and image. Prints only the wall time; floor_summary.py reports each solver against itself only.

Usage (in the image or on Kaggle, repo root): python gates/g93/dry/floor.py <out_dir> <factor 1|2> <stack> <solver>
[<timeout_s>]
"""
import dataclasses
import hashlib
import json
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sens"))
import common  # noqa: E402
from common import stacks  # noqa: E402
from opentsense.manifest import write_json  # noqa: E402
from opentsense.thermal import run  # noqa: E402

CELL_UM = 500.0
RUN = {"ice": run.run_3dice, "hs": run.run_hotspot, "pact": run.run_pact}
CODE = common.INPUTS + ["gates/g93/dry/floor.py", "opentsense/stack/to_hotspot.py", "opentsense/stack/to_pact.py",
                        "docker/versions.env"]


def inputs():
    """Hash of the code, patches and floorplans that set a unit's result (not the image or machine)."""
    h = hashlib.sha256()
    flp, pat = os.path.join(common.ROOT, "configs", "floorplans"), os.path.join(common.ROOT, "docker", "patches")
    for p in ([os.path.join(common.ROOT, f) for f in CODE] + sorted(os.path.join(flp, f) for f in os.listdir(flp))
              + sorted(os.path.join(pat, f) for f in os.listdir(pat))):
        h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


def refine(st, P, f):
    """The same stack on a grid f times finer in x and y, each cell's power spread evenly over its f^2 children."""
    if f == 1:
        return st, P
    fine = dataclasses.replace(st, grid=(st.grid[0] * f, st.grid[1] * f)).validate()
    return fine, {d: np.kron(p, np.ones((f, f))) / f ** 2 for d, p in P.items()}


def main(out_dir, factor, name, solver, timeout_s=7200):
    os.makedirs(out_dir, exist_ok=True)
    f = int(factor)
    tag = {"inputs": inputs(), "image": os.environ.get("OTS_IMAGE", "unknown")}
    path = os.path.join(out_dir, f"{name}_x{f}_{solver}.json")
    if os.path.exists(path) and all(json.load(open(path)).get(k) == v for k, v in tag.items()):
        print("skip", path)
        return
    st, P = refine(*stacks.build(name, CELL_UM), f)
    at = run.stack_at(st, {l.name: stacks.LEAK_T_REF_K for l in st.layers})
    t0 = time.time()
    with tempfile.TemporaryDirectory() as wd:
        T = RUN[solver](at, P, wd, timeout=int(float(timeout_s)))
    rec = {**tag, "stack": name, "factor": f, "solver": solver, "grid": list(st.grid),
           "nodes": st.grid[0] * st.grid[1] * sum(1 for _ in st.sublayers()),
           "wall_s": round(time.time() - t0, 1), "dies": common.summary(st, T, P)}
    write_json(rec, path)
    print(f"{name} x{f} {solver} {rec['wall_s']} s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
