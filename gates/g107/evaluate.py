"""Score G107 from <run>/scores.json against registration.md; writes <run>/result.json.

Usage (repo root): python gates/g107/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
CHIPS = list(range(21, 31))
OFFSETS = {"indep": None, "corr0.8_3mm": [0.8, 3.0]}
COUNTS = {"bot8/uniform": [8, 8], "bot4/uniform": [8, 4], "bot2/uniform": [8, 2], "bot1/uniform": [8, 1],
          "bot0/uniform": [8, 0], "bot4/greedy_a": [8, 4], "bot2/greedy_a": [8, 2], "bot1/greedy_a": [8, 1]}
JOINT = {"joint12/greedy_a": 12, "joint16/greedy_a": 16}
REF, TOL_K = "bot8/uniform", 0.25
DRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dry", "budget.json")
OWN = ["gates/g107/run.py", "gates/g107/dry/budget.json", "gates/g84/make_cases.py"]     # run.py's own inputs
BARS = {"a": ("indep", "bot0/uniform"), "b": ("indep", "bot2/uniform"), "c": ("corr0.8_3mm", "bot2/uniform")}


def write_json(obj, path):
    with open(path + ".tmp", "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(path + ".tmp", path)


def checks(d, dry):
    """{check: bool}, every validity condition of the registration; dry: dry/budget.json."""
    runs, cnt = d.get("runs", {}), d.get("per_die_count", {})
    sets = list(COUNTS) + list(JOINT)
    vals = [v for r in runs.values() for x in ("rmse_K", "peak_err_K", "average_rmse_K", "average_peak_err_K")
            for v in r.get(x, {}).values()]
    return {"case_set": d.get("case_set_sha256") == G84_SHA, "chips": d.get("chips") == CHIPS,
            "offsets": d.get("offsets") == OFFSETS, "profile": d.get("profile") == "ring_osc", "salt": d.get("salt") == 107,
            "complete": d.get("complete") is True, "inputs_unchanged": d.get("inputs_unchanged") is True,
            "buried_die_is_bot": d.get("buried_die") == 1,
            "sites_as_dry": all(d.get(k) == dry[k] for k in ("sites", "buried_die", "placement_noise_K")),
            "run_files_hashed": set(OWN) <= set(d.get("inputs_sha256", {})),
            "counts": (all(cnt.get(s) == c for s, c in COUNTS.items())
                       and all(sum(cnt.get(s, [])) == n for s, n in JOINT.items())),
            "all_runs": all(f"{o}/{s}/{c}" in runs for o in OFFSETS for s in sets for c in CHIPS),
            "finite": bool(vals) and bool(np.all(np.isfinite(vals)))}


def main(run):
    d = json.load(open(os.path.join(run, "scores.json")))
    ok = checks(d, json.load(open(DRY)))
    if not all(ok.values()):
        out = {"verdict": "INCONCLUSIVE", "valid": False, "checks": ok}
        write_json(out, os.path.join(run, "result.json"))
        print(out["verdict"], {k: v for k, v in ok.items() if not v})
        return
    runs = d["runs"]

    def series(o, s, die, what="rmse_K"):
        return np.array([runs[f"{o}/{s}/{c}"][what][die] for c in CHIPS])

    def paired(o, s, die):
        x = series(o, s, die) - series(o, REF, die)
        return {"mean": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(len(x)))}

    bars = {}
    for k, (o, s) in BARS.items():
        gap = float(series(o, s, "bot").mean() - series(o, REF, "bot").mean())
        bars[k] = {"ok": gap <= TOL_K, "offsets": o, "set": s, "buried_minus_bot8_mean_rmse_K": gap, "tol_K": TOL_K}
    rep = {o: {s: {die: {"rmse_K": float(series(o, s, die).mean()),
                         "peak_err_K": float(series(o, s, die, "peak_err_K").mean()),
                         "average_rmse_K": float(series(o, s, die, "average_rmse_K").mean()),
                         "chips_below_average": int(sum(runs[f"{o}/{s}/{c}"]["vs_average"][die]["ci95"][1] < 0
                                                        for c in CHIPS)),
                         "vs_bot8": None if s == REF else paired(o, s, die)}
                   for die in ("top", "bot")} for s in list(COUNTS) + list(JOINT)} for o in OFFSETS}
    out = {"verdict": "PASS" if all(b["ok"] for b in bars.values()) else "FAIL", "valid": True, "checks": ok,
           **bars, "joint_per_die_count": {s: d["per_die_count"][s] for s in JOINT}, "reported": rep}
    write_json(out, os.path.join(run, "result.json"))
    print(out["verdict"], {k: (round(b["buried_minus_bot8_mean_rmse_K"], 3), b["ok"]) for k, b in bars.items()})


if __name__ == "__main__":
    main(sys.argv[1])
