"""G93 bars from the noise-floor rule (draft, "Bars by the noise-floor rule"), computed from each solver's own floor.

bar(stack, die, metric, a, b) = max(2 (f_a + f_b), 1%) of the pair's mean, with f from `floor_kaggle/floor_summary.json`
(each solver against itself, cells split in four). S3 takes, per solver and metric, the largest f over every die of
S1, S2 and S4. Usage: python gates/g93/dry/bars.py [summary] [out]
"""
import itertools
import json
import os
import sys

SOLVERS = ("ice", "hs", "pact")
METRICS = ("peak_rise_K", "spread_K")
MIN_BAR = 0.01


def bars(floor):
    """{stack: {die: {metric: {"a-b": bar_rel}}}} for S1, S2, S4 per die, and S3 as one entry for every region."""
    out = {}
    for stack, dies in floor.items():
        out[stack] = {die: {m: {f"{a}-{b}": max(2 * (fs[a][m] + fs[b][m]), MIN_BAR)
                                for a, b in itertools.combinations(SOLVERS, 2)} for m in METRICS}
                      for die, fs in dies.items()}
    worst = {s: {m: max(fs[s][m] for dies in floor.values() for fs in dies.values()) for m in METRICS} for s in SOLVERS}
    out["s3"] = {"*": {m: {f"{a}-{b}": max(2 * (worst[a][m] + worst[b][m]), MIN_BAR)
                           for a, b in itertools.combinations(SOLVERS, 2)} for m in METRICS}}
    return out, worst


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    src = argv[1] if len(argv) > 1 else os.path.join(here, "floor_kaggle", "floor_summary.json")
    dst = argv[2] if len(argv) > 2 else os.path.join(here, "bars.json")
    summary = json.load(open(src, encoding="utf-8"))
    if summary["missing"]:
        sys.exit(f"missing floor units: {summary['missing']}")
    b, worst = bars(summary["floor_rel"])
    from opentsense.manifest import write_json
    write_json({"source": os.path.relpath(src, here).replace(os.sep, "/"), "min_bar_rel": MIN_BAR,
                "s3_floor_rel": worst, "bars_rel": b}, dst)
    for stack, dies in b.items():
        for die, ms in dies.items():
            print(stack, die, {m: {p: f"{v:.2%}" for p, v in ps.items()} for m, ps in ms.items()})


if __name__ == "__main__":
    main(sys.argv)
