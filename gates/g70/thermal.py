"""G70 smoke run, thermal half (inside the OpenTSense image): ORFS power -> tile map -> 3D-ICE and PACT.
Usage: python gates/g70/thermal.py <run_dir>   (run_dir holds orfs/inst_loc.csv and orfs/power.txt)"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from opentsense import manifest
from opentsense.power import maps
from opentsense.stack import model
from opentsense.thermal import run

RUN = sys.argv[1]
ORFS = os.path.join(RUN, "orfs")
t0 = time.time()
stack = model.load(os.path.join(os.path.dirname(__file__), "..", "..", "configs", "stacks", "single_die.yaml"))
box, pos = maps.read_locations(os.path.join(ORFS, "inst_loc.csv"))
inst, total = maps.read_power(os.path.join(ORFS, "power.txt"))
stack.size_um = (box[2] - box[0], box[3] - box[1])
P, missing = maps.tile_map(inst, box, pos, stack.grid)
# rows without a location are hierarchical modules (sums of their placed children), so the map must still hold the
# whole design's power; report_power prints 3 significant figures
assert abs(P.sum() - total) <= 0.005 * total, f"map power {P.sum()} vs design total {total}"
power = {"die0": P}
T_ice = run.run_3dice(stack, power, os.path.join(RUN, "ice"))["die0"]
T_pact = run.run_pact(stack, power, os.path.join(RUN, "pact"))["die0"]
np.savez(os.path.join(RUN, "maps.npz"), power=P, T_ice=T_ice, T_pact=T_pact)
res = dict(
    design="sky130hd/gcd", activity="default", die_um=stack.size_um, grid=stack.grid,
    n_instances=len(inst), n_hierarchical_skipped=missing, total_power_W=total, map_power_W=float(P.sum()),
    peak_rise_ice_K=float(T_ice.max() - stack.ambient_K), peak_rise_pact_K=float(T_pact.max() - stack.ambient_K),
    thermal_s=round(time.time() - t0, 1),
)
json.dump(res, open(os.path.join(RUN, "result.json"), "w"), indent=2)
manifest.write(os.path.join(RUN, "manifest.json"), extra={"orfs_version": open(os.path.join(ORFS, "openroad_version.txt")).read().strip()})
print(json.dumps(res, indent=2))
