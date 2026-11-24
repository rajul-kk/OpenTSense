"""G94 gated run, HotSpot units on Kaggle CPU sessions (this machine has no free 4 GB slot; 3D-ICE and PACT run here
with run.py). Builds the solvers as gates/g93/kaggle_build.py does (opentsense:g94b's steps), proves parity first
with dry/kaggle_floor_hs.py's checks (HotSpot transient at levels 0, 2 and 5 and 3D-ICE at level 4, all against this
machine's g94b outputs) and stops if it misses, then runs one run.py process per unit of its session, all at once,
with one BLAS thread each. The manifest is written once before the units start.

Two sessions (about 7.5 h and 4.5 h of HotSpot, estimated from the floor sessions' 1.7 to 2 s a row):
- step:  the step case of the three stacks;
- rest:  the pulse case of the three stacks and the programs case of the two with a CPU die.
At LIMIT_S the units still running are killed by process group; a killed unit leaves no file (run.py writes each
unit whole), so the run stays INCONCLUSIVE until it is rerun. Exits 1 if parity misses or any unit fails.

Usage (Kaggle, repo root): python gates/g94/kaggle_gate_hs.py <working_dir> <session>
Output: <working_dir>/run/ (manifest.json and the units), parity/, parity.json, <stack>_<case>.log.
"""
import os
import signal
import subprocess
import sys
import time

sys.path[:0] = [".", os.path.join("gates", "g94"), os.path.join("gates", "g94", "dry")]
from kaggle_floor_hs import T0, build, parity  # noqa: E402
import run  # noqa: E402

LIMIT_S = 11.5 * 3600
SESSIONS = {"step": [u for u in run.units() if u[1] == "step"],
            "rest": [u for u in run.units() if u[1] != "step"]}


def main(w, session):
    todo = SESSIONS[session]
    build(os.getcwd(), w)
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if not parity(w):
        sys.exit("parity failed: stopping before the HotSpot units")
    out = os.path.join(w, "run")
    run.start(out)
    procs = {f"{n}_{c}": subprocess.Popen([sys.executable, "gates/g94/run.py", out, "hs", f"{n}:{c}"],
                                          stdout=open(f"{w}/{n}_{c}.log", "w"), stderr=subprocess.STDOUT,
                                          start_new_session=True) for n, c in todo}
    while any(p.poll() is None for p in procs.values()):
        if time.time() - T0 > LIMIT_S:
            for k, p in procs.items():
                if p.poll() is None:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    print(f"{k}: killed at the session limit", flush=True)
            break
        time.sleep(30)
    for k, p in procs.items():
        p.wait()
        print(f"{k}: rc {p.returncode}", flush=True)
    print("total", round(time.time() - T0), "s", sorted(os.listdir(out)), flush=True)
    if any(p.returncode for p in procs.values()):
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
