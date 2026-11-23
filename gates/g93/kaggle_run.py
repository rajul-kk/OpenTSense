"""G93 gated units on a Kaggle CPU session (registration.md, "Where it runs"). Builds the solvers (kaggle_build.py),
runs the parity units first (dry/floor.py, S2 on the gated mesh, every solver, against dry/floor_image/ by
floor_summary's rule) and stops if they miss; then run.py for each unit given, in order. A unit starts only with
time for its expected solves left; its budget is enough for run.MAX_IT solves or the session's time left, whichever
is less, and run.py stops it between solves at the budget (recorded as out of time); a kill of the unit's process
group 900 s later is a backstop only.

Usage (Kaggle, started by kaggle_kernel.py from the repo root): python gates/g93/kaggle_run.py <working_dir>
<stack:solver>[,...]
Output: <working_dir>/runs/<stack>_<solver>.{json,npz}, parity/, parity.json, units.log.
"""
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kaggle_build import T0, build, sh  # noqa: E402

LIMIT_S = 11.5 * 3600      # Kaggle stops a session at 12 h; leave time to save the output
# one solve on Kaggle, s (dry/floor_kaggle/floor_summary.json x1 walls; S3 dry/size_probe_kaggle_beol.jsonl)
SOLVE_S = {"s1": {"ice": 41, "hs": 166, "pact": 67}, "s2": {"ice": 8, "hs": 36, "pact": 24},
           "s4": {"ice": 44, "hs": 180, "pact": 72}, "s3": {"ice": 740, "hs": 4483, "pact": 817}}
# solves 3D-ICE needed for 10% leakage (sens/leak_runs: S1 9, S2 4, S4 4; S3 not measured, taken as 4)
EXPECT = {"s1": 9, "s2": 4, "s4": 4, "s3": 4}
MAX_IT, SLACK = 40, 1.5    # run.MAX_IT; budget = SLACK x MAX_IT solves


def unit(cmd, backstop_s, w):
    """Run one unit in its own process group, so a backstop kill also stops the solver it started (whose memory
    would otherwise stay held while the next unit runs). Returns its last output line; the output goes to units.log."""
    with open(f"{w}/units.log", "a") as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            p.wait(timeout=backstop_s)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return f"{cmd[3:5]} killed by the backstop after {backstop_s} s"
    return f"{cmd[3:5]} rc {p.returncode}: " + open(f"{w}/units.log").read().strip().splitlines()[-1]


def main(w, units):
    todo = [tuple(u.split(":")) for u in units.split(",")]
    bad = [u for u in todo if len(u) != 2 or u[1] not in SOLVE_S.get(u[0], {})]
    if bad:
        sys.exit(f"unknown units {bad}; stacks and solvers are {SOLVE_S}")
    os.makedirs(w, exist_ok=True)
    build(os.getcwd(), w)
    for s in ("ice", "hs", "pact"):
        sh(f"python gates/g93/dry/floor.py {w}/parity 1 s2 {s} 1800", w, "units.log", check=False)
    r = sh(f"python gates/g93/dry/floor_summary.py {w}/parity {w}/parity.json gates/g93/dry/floor_image", w,
           check=False)
    if '"parity_ok": true' not in r.stdout:
        print("parity failed: stopping before the gated units", r.stdout[-1500:], flush=True)
        return
    for name, solver in todo:
        left = LIMIT_S - (time.time() - T0)
        one = SOLVE_S[name][solver]
        if left < EXPECT[name] * one:
            print(f"no time for {name}:{solver} ({left:.0f} s left)", flush=True)
            continue
        budget = int(min(left - 120, SLACK * MAX_IT * one))
        print(unit([sys.executable, "gates/g93/run.py", f"{w}/runs", name, solver, str(budget)], budget + 900, w),
              flush=True)
    print("total", round(time.time() - T0), "s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
