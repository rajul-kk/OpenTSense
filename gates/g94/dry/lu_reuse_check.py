"""G94 dry: HotSpot's LU-reuse patch (opentsense:g94b) gives the same transient output as opentsense:g94a.

Runs HotSpot transients and writes the result arrays plus wall time; run once in each image and compare with
`compare`. Cases: a small stack (16 x 12 grid, a point source switched on, then off) and the 3d stack's step case
of seed 1 (the gated run uses seed 0) for a few slots at level 0.

Usage (repo root):  python gates/g94/dry/lu_reuse_check.py run <out.npz> [n_3d_slots]
                    python gates/g94/dry/lu_reuse_check.py compare <a.npz> <b.npz>
"""
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g94"), "tests"]
import cases  # noqa: E402
import solve  # noqa: E402
from opentsense.stack import model  # noqa: E402
from opentsense.thermal.run import HOTSPOT_EXE as HOTSPOT  # noqa: E402


def small_case():
    from test_solvers import point, small
    s = small()
    on = point(s, 3, 3, 0.5)
    P = {d: np.concatenate([np.repeat(v[None], 6, 0), np.zeros((6,) + v.shape)]) for d, v in on.items()}
    return s, P


def run(out, n3d="3"):
    res, wall = {}, {}
    s, P = small_case()
    t0 = time.time()
    for d, v in solve.rise("hs", s, P, 0.005, 2).items():
        res[f"small_{d}"] = v
    wall["small"] = time.time() - t0
    stack = model.load(os.path.join("configs", "stacks", cases.STACKS["3d"][0]))
    t0 = time.time()
    for d, v in solve.rise("hs", stack, cases.step("3d", 1, int(n3d)), 0.005, 0).items():
        res[f"3d_{d}"] = v
    wall["3d"] = time.time() - t0
    exe = hashlib.sha256(open(shutil.which(HOTSPOT), "rb").read()).hexdigest()
    np.savez(out, hotspot_sha256=np.array(exe), **res)
    print(json.dumps({"hotspot_sha256": exe, "wall_s": wall,
                      "sha256": {k: hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()[:16]
                                 for k, v in res.items()}}))


def compare(a, b):
    """Exit 1 unless every array is identical; refuse two files from the same HotSpot binary. A file written before
    the binary hash was recorded (lu_check_v1/) reads as "unrecorded" and is never refused."""
    A, B = np.load(a), np.load(b)
    ha, hb = (str(X["hotspot_sha256"]) if "hotspot_sha256" in X.files else "unrecorded" for X in (A, B))
    if ha == hb != "unrecorded":
        sys.exit(f"both files come from the same HotSpot binary {ha}")
    keys = sorted(k for k in A.files if k != "hotspot_sha256")
    assert keys == sorted(k for k in B.files if k != "hotspot_sha256")
    bad = 0
    for k in keys:
        same = np.array_equal(A[k], B[k], equal_nan=False)
        bad += not same
        if A[k].shape != B[k].shape:
            print(k, "shape differs", A[k].shape, B[k].shape)
            continue
        print(k, A[k].shape, "identical" if same else f"max diff {np.nanmax(np.abs(A[k] - B[k])):.3e}")
    print("binaries", ha[:16], hb[:16])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    {"run": run, "compare": compare}[sys.argv[1]](*sys.argv[2:])
