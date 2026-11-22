"""Score G105 from runs/<name>/scores.json against registration.md.

Usage (repo root): python gates/g105/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
DIES = ("top", "bot")
GATED = "s0.8_l3"
CHIPS = list(range(21, 31))
NEED_A, CAL_SLACK_K = 8, 0.1
SETTINGS = {"indep": None, "s0.5_l0.5": [0.5, 0.5], "s0.5_l1.5": [0.5, 1.5], "s0.8_l3": [0.8, 3.0]}


def write_json(obj, path):
    with open(path + ".tmp", "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(path + ".tmp", path)


def main(run):
    d = json.load(open(os.path.join(run, "scores.json")))
    runs, chips = d.get("runs", {}), d.get("chips")
    valid = (d.get("case_set_sha256") == G84_SHA and chips == CHIPS and d.get("settings") == SETTINGS
             and d.get("profile") == "ring_osc" and d.get("salt") == 105
             and d.get("n_boot") == 10000 and all(f"{s}/{c}" in runs for s in SETTINGS for c in chips))
    if not valid:
        out = {"verdict": "INCONCLUSIVE", "valid": False}
        write_json(out, os.path.join(run, "result.json"))
        print(out["verdict"])
        return

    def per(setting, mode, die, key):
        return [runs[f"{setting}/{c}"][mode]["dies"][die][key] for c in chips]

    below = {die: sum(ci[1] < 0 for ci in per(GATED, "uncal", die, "vs_average_ci95")) for die in DIES}
    a = all(n >= NEED_A for n in below.values())
    gap = {die: float(np.mean(per(GATED, "cal", die, "rmse_K")) - np.mean(per(GATED, "uncal", die, "rmse_K")))
           for die in DIES}
    b = all(g <= CAL_SLACK_K for g in gap.values())

    def paired(setting, die, mode="uncal"):
        x = np.array(per(setting, mode, die, "rmse_K")) - np.array(per("indep", mode, die, "rmse_K"))
        return {"mean": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(len(x)))}

    rep = {s: {"rmse_K": {m: {die: float(np.mean(per(s, m, die, "rmse_K"))) for die in DIES} for m in ("uncal", "cal")},
               "chips_field_below_average": {m: {die: sum(ci[1] < 0 for ci in per(s, m, die, "vs_average_ci95"))
                                                 for die in DIES} for m in ("uncal", "cal")},
               "vs_indep_paired": {m: {die: paired(s, die, m) for die in DIES} for m in ("uncal", "cal")},
               "offset_rms_K": float(np.mean([runs[f"{s}/{c}"]["offset_rms_K"] for c in chips])),
               "offset_err_rms_K": float(np.mean([runs[f"{s}/{c}"]["offset_err_rms_K"] for c in chips])),
               "false_alarm": {m: float(np.mean([runs[f"{s}/{c}"][m]["false_alarm"] for c in chips]))
                               for m in ("uncal", "cal")}}
           for s in sorted(SETTINGS)}
    out = {"verdict": "PASS" if a and b else "FAIL", "valid": True,
           "a": {"ok": a, "need": NEED_A, "chips_field_below_average": below},
           "b": {"ok": b, "slack_K": CAL_SLACK_K, "cal_minus_uncal_mean_rmse_K": gap},
           "reported": rep}
    write_json(out, os.path.join(run, "result.json"))
    print(out["verdict"], out["a"], out["b"])


if __name__ == "__main__":
    main(sys.argv[1])
