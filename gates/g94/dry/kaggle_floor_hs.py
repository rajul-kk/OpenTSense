"""G94 dry: HotSpot's after-5 ms floor units (floor_after.py) on a Kaggle CPU session, as this machine has no free
4 GB slot (18 Nov 2026; 3D-ICE and PACT ran here, floor_after/). Builds the solvers as gates/g93/kaggle_build.py
does (opentsense:g94b's steps), proves parity first and stops if it misses, then runs one floor_after.py process
per stack at the given level, all three at once (HotSpot uses one core and at most about 4 GB each).

Parity (A18), each against this machine's opentsense:g94b output:
- HotSpot transient: lu_reuse_check.py's cases (small stack at level 2; 3d seed 1, 4 slots, level 0) against
  lu_check/g94b.npz;
- HotSpot at the floor units' step: the small stack at level 5 (384 steps of 5 ms / 32, one LU reused throughout)
  against kaggle_parity/small_hs_L5.npz, made here by `ref`;
- 3D-ICE through solve.py: the 3d stack at level 4 against floor_after/3d_ice_L4.npz.
Each passes when every temperature array agrees within PARITY_K, far below the 0.2 K floor these units measure, and
every t63 (s) within PARITY_REL of its reference. The 3d stack's HotSpot at level 5 is not checked (this machine has
no slot for it, the reason for this session).

Parity and the stack processes all run with one BLAS thread (three stacks share four cores). The script exits 1 if
parity misses or any stack ends with a nonzero code, so the Kaggle session shows the failure. At LIMIT_S the stacks
still running are killed by process group (L69); a stack holds one unit per session, so a killed stack returns
nothing. The floor rows are computed on this machine from the collected units.

Usage (Kaggle, from the repo root): python gates/g94/dry/kaggle_floor_hs.py <working_dir> <level>
       (this machine, opentsense:g94b): python gates/g94/dry/kaggle_floor_hs.py ref <out.npz>
Output: <working_dir>/floor/<stack>/<stack>_hs_L<level>.npz, parity/, parity.json, <stack>.log.
"""
import json
import os
import signal
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "g93"))
from kaggle_build import T0, build, sh  # noqa: E402

LIMIT_S = 11.5 * 3600
PARITY_K = 0.01
PARITY_REL = 1e-3       # t63_* arrays (s), relative
STACKS = ("3d", "3d_bottom", "25d_regions")
REF = "gates/g94/dry"


def agree(ref, got):
    """(ok, {array: max abs difference}) over the arrays the reference holds, binary hashes aside."""
    A, B = np.load(ref), np.load(got)
    diff = {}
    for k in A.files:
        if k == "hotspot_sha256":
            continue
        if k not in B.files or A[k].shape != B[k].shape:
            diff[k] = None
            continue
        a, b = A[k].astype(float), B[k].astype(float)
        d = np.abs(a - b) / (np.abs(a) if k.startswith("t63_") else 1.0)
        diff[k] = float(d.max()) if d.size else 0.0
    ok = all(v is not None and v <= (PARITY_REL if k.startswith("t63_") else PARITY_K) for k, v in diff.items())
    return ok, diff


def small_l5(out):
    """The small stack's point source (lu_reuse_check.small_case) at level 5 in HotSpot, saved to out."""
    sys.path[:0] = [".", "gates/g94", REF, "tests"]
    import lu_reuse_check
    import solve
    s, P = lu_reuse_check.small_case()
    np.savez(out, **{f"small_{d}": v for d, v in solve.rise("hs", s, P, 0.005, 5).items()})


def parity(w):
    p = f"{w}/parity"
    os.makedirs(p, exist_ok=True)
    sh(f"python {REF}/lu_reuse_check.py run {p}/hs.npz 4", w, "parity.log", check=False)
    sh(f"python {REF}/kaggle_floor_hs.py ref {p}/small_hs_L5.npz", w, "parity.log", check=False)
    sh(f"python {REF}/floor_after.py {p} 3d ice 4", w, "parity.log", check=False)
    res = {}
    for name, ref, got in (("hotspot", f"{REF}/lu_check/g94b.npz", f"{p}/hs.npz"),
                           ("hotspot_small_L5", f"{REF}/kaggle_parity/small_hs_L5.npz", f"{p}/small_hs_L5.npz"),
                           ("ice_3d_L4", f"{REF}/floor_after/3d_ice_L4.npz", f"{p}/3d_ice_L4.npz")):
        res[name] = agree(ref, got) if os.path.exists(got) else (False, "missing")
    ok = all(v[0] for v in res.values())
    json.dump({"parity_ok": ok, "tol_K": PARITY_K, "checks": res}, open(f"{w}/parity.json", "w"), indent=1)
    print(json.dumps({"parity_ok": ok, "checks": res}), flush=True)
    return ok


def main(w, level):
    if int(level) not in (4, 5):
        sys.exit("level must be 4 or 5")
    os.makedirs(w, exist_ok=True)
    build(os.getcwd(), w)
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if not parity(w):
        sys.exit("parity failed: stopping before the HotSpot units")
    procs = {}
    for st in STACKS:
        out = f"{w}/floor/{st}"
        os.makedirs(out, exist_ok=True)
        procs[st] = subprocess.Popen([sys.executable, f"{REF}/floor_after.py", out, st, "hs", str(level)],
                                     stdout=open(f"{w}/{st}.log", "w"), stderr=subprocess.STDOUT,
                                     start_new_session=True)
    while any(p.poll() is None for p in procs.values()):
        if time.time() - T0 > LIMIT_S:
            for st, p in procs.items():
                if p.poll() is None:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    print(f"{st}: killed at the session limit", flush=True)
            break
        time.sleep(30)
    for st, p in procs.items():
        p.wait()
        print(f"{st}: rc {p.returncode}, units {sorted(os.listdir(f'{w}/floor/{st}'))}", flush=True)
    print("total", round(time.time() - T0), "s", flush=True)
    if any(p.returncode for p in procs.values()):
        sys.exit(1)


if __name__ == "__main__":
    small_l5(sys.argv[2]) if sys.argv[1] == "ref" else main(*sys.argv[1:3])
