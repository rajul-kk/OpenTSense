"""G93 size probe (before registration): can each solver run each stack, and at what RAM and wall time?
Uniform power at each die's nominal total; prints nodes, peak RSS of the solver process tree and wall time, and no
temperatures (registration comes before any comparison on these stacks). One solver per process.
Usage (inside the image, repo root): python gates/g93/dry/size_probe.py <stack> <cell_um> <ice|pact|hs> <workdir>
"""
import json
import resource
import sys
import time

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "gates/g93")
import stacks  # noqa: E402
from opentsense.thermal.run import run_3dice, run_hotspot, run_pact  # noqa: E402

name, cell, solver, work = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
st, P = stacks.build(name, cell)
nx, ny = st.grid
U = {d: np.full((ny, nx), float(v.sum()) / (nx * ny)) for d, v in P.items()}
run = {"ice": run_3dice, "pact": run_pact, "hs": run_hotspot}[solver]
t0 = time.time()
try:
    run(st, U, work)
    ok, err = True, ""
except Exception as e:  # report and go on: the probe's job is to find what does not run
    ok, err = False, str(e)[-300:]
rss = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
print(json.dumps(dict(stack=name, cell_um=cell, solver=solver, grid=[nx, ny], sublayers=sum(1 for _ in st.sublayers()),
                      nodes=nx * ny * sum(1 for _ in st.sublayers()), ok=ok, wall_s=round(time.time() - t0, 1),
                      peak_rss_GB=round(rss / 2 ** 20, 2), error=err)), flush=True)
