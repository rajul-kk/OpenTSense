"""G77 noise floor for bar (a) (plan.md 2.1), and the factor it implies. Written 12 Nov 2026 before any floor data.

Repeat runs that should agree: G77's construction with seeds 78, 79 and 80 (never 77, the gated seed). For every stack,
noise level, die and rule with sigma known, the spread of the ratio (rule's power error / oracle's) over the seeds is
its sample standard deviation; the floor is the largest of these.

Factor (fixed by this formula before the floor was seen): K = max(1.5, 1 + 3 x floor). 1.5 is the factor in the
G77 draft of 11 Nov (from the unit test); the second term keeps the bar's distance from 1 at least 3 times the floor.

Usage (from the repo root): python gates/g77/dry/floor.py OUT.json DIR_SEED78 DIR_SEED79 DIR_SEED80
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import evaluate  # noqa: E402

BASE_FACTOR = 1.5


SEEDS = {78, 79, 80}


def main(out, dirs):
    seeds = [{v["seed"] for v in json.load(open(os.path.join(d, "cases.json"))).values()} for d in dirs]
    if sorted(s for ss in seeds for s in ss) != sorted(SEEDS) or any(len(ss) != 1 for ss in seeds):
        raise SystemExit(f"need one directory per seed {sorted(SEEDS)}; got seeds {seeds}")
    runs = [evaluate.main([d, os.path.join(d, "eval.json")]) for d in dirs]
    if len({tuple(sorted(r["case_sets"])) for r in runs}) != 1:
        raise SystemExit("the seed directories hold different case sets")
    known = evaluate.KNOWN
    spread = {}
    for f in runs[0]["case_sets"]:
        for n in known:
            for d in runs[0]["case_sets"][f]["dies"]:
                r = [run["case_sets"][f]["entries"][n]["dies"][d]["ratio_to_oracle"] for run in runs]
                spread[f"{f}/{n}/{d}"] = {"ratios": r, "sd": float(np.std(r, ddof=1))}
    floor = float(np.max([v["sd"] for v in spread.values()]))   # np.max keeps a NaN; max() may not
    if not np.isfinite(floor):
        raise SystemExit("a ratio is not finite; no floor")
    res = {"seeds_dirs": dirs, "floor": floor, "factor": max(BASE_FACTOR, 1 + 3 * floor), "spread": spread}
    json.dump(res, open(out, "w"), indent=1)
    print(f"floor {floor:.4f} -> factor {res['factor']:.4f}")
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
