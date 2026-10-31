"""G71 development check, run before the gate: how many sublayers until 3D-ICE and PACT stop moving?

Uses synthetic maps (not the G71 test maps): a 1 W/mm^2-class 1 mm block plus single-cell point sources on each
die, over 0.05 W/mm^2 background. Runs the two-die 3D stack at increasing mesh levels.
Usage (inside the image): python gates/g71/dev_mesh.py <out dir> [level ...]
"""
import json
import os
import sys
import time

import numpy as np
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from opentsense.stack import model  # noqa: E402
from opentsense.thermal.run import run_3dice, run_pact  # noqa: E402

CFG = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "stacks", "g71_3d.yaml")
LEVELS = {  # NCU, NTIM, NSI50, NBOND, NSI100
    "L0": (1, 1, 1, 1, 1),
    "L1": (5, 2, 4, 2, 4),
    "Lm": (10, 3, 6, 3, 8),
    "L2": (20, 5, 8, 4, 16),
    "L3": (40, 10, 16, 8, 32),
}


def load(level):
    txt = open(CFG).read()
    for k, v in zip(("NCU", "NTIM", "NSI50", "NBOND", "NSI100"), LEVELS[level]):
        txt = txt.replace(k, str(v))
    d = yaml.safe_load(txt)
    return model.Stack(d["name"], tuple(d["size_um"]), tuple(d["grid"]), float(d["ambient_K"]), float(d["heat_sink"]["htc"]),
                       {m: model.Material(float(v["k"]), float(v["cv"])) for m, v in d["materials"].items()},
                       [model.Layer(**l) for l in d["layers"]]).validate()


def maps():
    b = 0.05e-6 * 50 * 50
    top = np.full((60, 60), b); top[20:40, 20:40] += 6.0 / 400; top[50, 10] += 0.05
    bot = np.full((60, 60), b); bot[25:45, 15:35] += 1.5 / 400; bot[8, 48] += 0.05
    return {"top": top, "bot": bot}


def main(out, levels=None):
    P, res = maps(), {}
    for lv in levels or LEVELS:
        s = load(lv)
        t0 = time.time(); a = run_3dice(s, P, os.path.join(out, lv, "ice")); t1 = time.time()
        b = run_pact(s, P, os.path.join(out, lv, "pact")); t2 = time.time()
        r = {"ice_s": t1 - t0, "pact_s": t2 - t1}
        for d in P:
            A, B = a[d] - s.ambient_K, b[d] - s.ambient_K
            pt = (50, 10) if d == "top" else (8, 48)
            r[d] = dict(ice_peak=A.max(), pact_peak=B.max(), ice_point=A[pt], pact_point=B[pt], rms=np.sqrt(((A - B) ** 2).mean()), mean=A.mean())
        res[lv] = json.loads(json.dumps(r, default=float))
        print(lv, json.dumps(res[lv], indent=None, default=lambda v: round(v, 4)), flush=True)
    json.dump(res, open(os.path.join(out, "dev_mesh_" + "_".join(res) + ".json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
