"""G70 criterion (d): two clean rebuilds give the same power report and temperatures within 0.01 K.
Usage: python gates/g70/compare.py <run_dir_a> <run_dir_b>"""
import json
import os
import re
import sys

import numpy as np

a, b = sys.argv[1:3]


def power_lines(run):
    # the power tables only: drop log lines that carry timestamps, paths or run times
    txt = open(os.path.join(run, "orfs", "power.txt"), errors="replace").read().splitlines()
    return [l for l in txt if re.match(r"^\s*(Group|Sequential|Combinational|Clock|Macro|Pad|Total|[-+]?\d)", l)]


same_power = power_lines(a) == power_lines(b)
A, B = np.load(os.path.join(a, "maps.npz")), np.load(os.path.join(b, "maps.npz"))
d_ice = float(np.abs(A["T_ice"] - B["T_ice"]).max())
d_pact = float(np.abs(A["T_pact"] - B["T_pact"]).max())
res = dict(power_report_identical=same_power, n_power_lines=len(power_lines(a)), max_dT_ice_K=d_ice, max_dT_pact_K=d_pact,
           d_pass=same_power and d_ice <= 0.01 and d_pact <= 0.01)
print(json.dumps(res, indent=2))
