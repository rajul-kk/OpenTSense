"""Score G104 from runs/<name>/scores.json against registration.md.

Usage (repo root): python gates/g104/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
DIES = ("top", "bot")
CHIPS = list(range(21, 31))
OFFSETS = {"indep": None, "corr0.8_3mm": [0.8, 3.0]}
SETS = ("all/uniform", "outside/uniform", "all/greedy_a", "outside/greedy_a")
NEED_A, SLACK_B_K = 8, 0.25


def eight_per_die(sites):
    s = np.array(sites).reshape(-1, 3)
    return len(s) == 16 and np.bincount(s[:, 0], minlength=2).tolist() == [8, 8]


def write_json(obj, path):
    with open(path + ".tmp", "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(path + ".tmp", path)


def main(run):
    d = json.load(open(os.path.join(run, "scores.json")))
    runs, chips = d.get("runs", {}), d.get("chips")
    valid = (d.get("case_set_sha256") == G84_SHA and chips == CHIPS and d.get("offsets") == OFFSETS
             and d.get("profile") == "ring_osc" and d.get("salt") == 104
             and all(f"{o}/{s}/{c}" in runs for o in OFFSETS for s in SETS for c in chips)
             and all(s in d.get("sites", {}) and eight_per_die(d["sites"][s]) for s in SETS))
    if not valid:
        out = {"verdict": "INCONCLUSIVE", "valid": False}
        write_json(out, os.path.join(run, "result.json"))
        print(out["verdict"])
        return

    def rmse(o, s, die):
        return [runs[f"{o}/{s}/{c}"]["field_model"][die]["all"]["rmse_K"]["mean_group_median"] for c in chips]

    def below(o, s, die):
        return sum(runs[f"{o}/{s}/{c}"]["vs_average"][die]["rmse_K"]["ci95"][1] < 0 for c in chips)

    a_counts = {f"{o}/{die}": below(o, "outside/uniform", die) for o in OFFSETS for die in DIES}
    a = all(n >= NEED_A for n in a_counts.values())
    gap = {die: float(np.mean(rmse("indep", "outside/uniform", die)) - np.mean(rmse("indep", "all/uniform", die)))
           for die in DIES}
    b = all(g <= SLACK_B_K for g in gap.values())

    def paired(o, s, die, ref="all/uniform"):
        x = np.array(rmse(o, s, die)) - np.array(rmse(o, ref, die))
        return {"mean": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(len(x)))}

    rep = {o: {s: {die: {"rmse_K": float(np.mean(rmse(o, s, die))),
                         "peak_err_K": float(np.mean([runs[f"{o}/{s}/{c}"]["field_model"][die]["all"]["peak_err_K"]
                                                      ["mean_group_median"] for c in chips])),
                         "average_rmse_K": float(np.mean([runs[f"{o}/{s}/{c}"]["average"][die]["all"]["rmse_K"]
                                                          ["mean_group_median"] for c in chips])),
                         "chips_below_average": below(o, s, die),
                         "vs_all_uniform": None if s == "all/uniform" else paired(o, s, die)}
                   for die in DIES} for s in SETS} for o in OFFSETS}
    rep["outside_greedy_minus_outside_uniform"] = {o: {die: paired(o, "outside/greedy_a", die, "outside/uniform")
                                                       for die in DIES} for o in OFFSETS}
    out = {"verdict": "PASS" if a and b else "FAIL", "valid": True,
           "a": {"ok": a, "need": NEED_A, "chips_outside_uniform_below_average": a_counts},
           "b": {"ok": b, "slack_K": SLACK_B_K, "outside_minus_all_uniform_mean_rmse_K": gap},
           "reported": rep}
    write_json(out, os.path.join(run, "result.json"))
    print(out["verdict"], out["a"], out["b"])


if __name__ == "__main__":
    main(sys.argv[1])
