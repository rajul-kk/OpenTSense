"""G77b noise floor for bar (a) (plan.md 2.1), and the factor it implies. Written 12 Nov 2026 before the floor was run.

Repeat runs that should agree: G77's case builds for seeds 78, 79 and 80 (G77's floor seeds, in gates/g77/runs/floor;
seed 81 is G77b's gated seed). For every stack, noise level, die and gated entry (UPRE and the discrepancy rule with
the readings reference), the spread of the ratio to the oracle over the seeds is its sample standard deviation; the
floor is the largest.

Factor (fixed by this formula before the floor was seen): K = max(1.2, 1 + 3 x floor), as in the G77b draft.

Usage (from the repo root): python gates/g77b/dry/floor.py OUT.json DIR_SEED78 DIR_SEED79 DIR_SEED80
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import evaluate  # noqa: E402

BASE_FACTOR = 1.2
SEEDS = {78, 79, 80}


def main(out, dirs):
    seeds = [{v["seed"] for v in json.load(open(os.path.join(d, "cases.json"))).values()} for d in dirs]
    if sorted(s for ss in seeds for s in ss) != sorted(SEEDS) or any(len(ss) != 1 for ss in seeds):
        raise SystemExit(f"need one directory per seed {sorted(SEEDS)}; got seeds {seeds}")
    scratch = os.path.join(os.path.dirname(os.path.abspath(out)), "floor_runs")
    runs = [evaluate.main([d, os.path.join(scratch, f"seed{min(s)}", "eval.json")]) for d, s in zip(dirs, seeds)]
    if len({tuple(sorted(r["case_sets"])) for r in runs}) != 1:
        raise SystemExit("the seed directories hold different case sets")
    spread = {}
    for f in runs[0]["case_sets"]:
        for n in evaluate.GATED:
            for d in runs[0]["case_sets"][f]["dies"]:
                r = [run["case_sets"][f]["entries"][n]["dies"][d]["ratio_to_oracle"] for run in runs]
                spread[f"{f}/{n}/{d}"] = {"ratios": r, "sd": float(np.std(r, ddof=1))}
    floor = float(np.max([v["sd"] for v in spread.values()]))
    if not np.isfinite(floor):
        raise SystemExit("a ratio is not finite; no floor")
    res = {"seeds_dirs": dirs, "floor": floor, "factor": max(BASE_FACTOR, 1 + 3 * floor), "spread": spread}
    json.dump(res, open(out, "w"), indent=1)
    print(f"floor {floor:.4f} -> factor {res['factor']:.4f}")
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
