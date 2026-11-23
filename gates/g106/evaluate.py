"""Score G106 from <run>/scores.json against registration.md.

Usage (repo root): python gates/g106/evaluate.py <run dir>            (the gated run: chips 21-30)
                   python gates/g106/evaluate.py <run dir> --dry      (any chips; verdict DRY, never a gate verdict)
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opentsense.manifest import write_json  # noqa: E402
from run import G84_SHA, SALT  # noqa: E402

N_BOOT = 10000
DIES = ("top", "bot")
CHIPS = list(range(21, 31))
GATED = "asap7_ring/regulated"
CASES = (GATED, "asap7_ring/core_g97", "asap7_ring/core_scaled", "ihp_ring/regulated", "ihp_dvbe/one_point",
         "ihp_dvbe/two_point")
NEED_A = 8


def main(run, dry=False):
    d = json.load(open(os.path.join(run, "scores.json")))
    runs, chips = d.get("runs", {}), d.get("chips")
    valid = (d.get("case_set_sha256") == G84_SHA and isinstance(chips, list) and bool(chips)
             and (dry or chips == CHIPS) and d.get("salt") == SALT
             and all(f"{c}/{k}" in runs for c in CASES for k in chips)
             and all(runs[f"{c}/{k}"].get("n_boot") == N_BOOT for c in CASES for k in chips))
    if not valid:
        out = {"verdict": "INCONCLUSIVE", "valid": False}
        write_json(out, os.path.join(run, "result.json"))
        print(out["verdict"])
        return

    def below(case, die):
        return sum(runs[f"{case}/{k}"]["vs_average"][die]["rmse_K"]["ci95"][1] < 0 for k in chips)

    def mean(case, est, die, metric="rmse_K"):
        return float(np.mean([runs[f"{case}/{k}"][est][die]["all"][metric]["mean_group_median"] for k in chips]))

    a_counts = {die: below(GATED, die) for die in DIES}
    a = all(n >= NEED_A for n in a_counts.values())
    rep = {c: {"chips_field_below_average": {die: below(c, die) for die in DIES},
               "field_rmse_K": {die: mean(c, "field_model", die) for die in DIES},
               "field_peak_err_K": {die: mean(c, "field_model", die, "peak_err_K") for die in DIES},
               "average_rmse_K": {die: mean(c, "average", die) for die in DIES},
               "corners": [runs[f"{c}/{k}"]["corner"] for k in chips],
               "noise_K_told": float(np.mean([runs[f"{c}/{k}"]["noise_K"] for k in chips]))}
           for c in CASES}
    out = {"verdict": "DRY (counts only, no verdict)" if dry else "PASS" if a else "FAIL", "valid": True, "chips": chips,
           "a": {"ok": a, "need": NEED_A, "chips_field_below_average": a_counts},
           "squeeze_mV": d["squeeze_mV"], "density_scale": d["density_scale"], "reported": rep}
    write_json(out, os.path.join(run, "result.json"))
    print(out["verdict"], out["a"])


if __name__ == "__main__":
    main(sys.argv[1], dry="--dry" in sys.argv[2:])
