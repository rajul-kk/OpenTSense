"""Score G102 from runs/<name>/scores.json against registration.md.

Usage (repo root): python gates/g102/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
DIES = ("top", "bot")
EST = ("average", "field_model", "bayes_power", "inverted")
NEED_A = 8


def ci(r, name, die):
    return r["comparisons"][f"{name} - average"][die]["rmse_K"]["ci95"]


def summary(r, est, die, metric):
    return r["estimators"][est]["summary"][die]["all"][metric]["mean_group_median"]


def main(run):
    d = json.load(open(os.path.join(run, "scores.json")))
    runs, chips = d["runs"], d["chips"]
    profiles = list(dict.fromkeys(k.split("/")[0] for k in runs))

    def count(profs, name, ok):
        return {f"{p}/{die}": sum(ok(ci(runs[f"{p}/{c}"], name, die)) for c in chips) for p in profs for die in DIES}

    below = count(("bjt_trimmed", "ring_osc"), "field_model", lambda x: x[1] < 0)
    caught = count(("bjt_trimmed", "ring_osc", "dts_1c"), "inverted", lambda x: x[0] > 0)
    a, b = all(n >= NEED_A for n in below.values()), all(n == len(chips) for n in caught.values())
    valid = (d["case_set_sha256"] == G84_SHA and chips == list(range(6, 16))      # registered held-out chips
             and set(profiles) == {"ideal_gauss", "bjt_trimmed", "ring_osc", "dts_1c"})
    mean = {p: {e: {die: {m: float(np.mean([summary(runs[f"{p}/{c}"], e, die, m) for c in chips]))
                          for m in ("rmse_K", "peak_err_K")} for die in DIES} for e in EST} for p in profiles}
    vs_ideal = {p: {e: {die: {m: mean[p][e][die][m] / mean["ideal_gauss"][e][die][m] for m in ("rmse_K", "peak_err_K")}
                        for die in DIES} for e in EST} for p in profiles}
    out = {"verdict": "INCONCLUSIVE" if not valid else "PASS" if a and b else "FAIL", "valid": valid,
           "a": {"ok": a, "chips_field_below_average": below},
           "b": {"ok": b, "chips_inverted_above_average": caught},
           "reported": {"mean_over_chips": mean, "ratio_to_ideal_gauss": vs_ideal,
                        "dts_1c_chips_field_below_average": count(("dts_1c",), "field_model", lambda x: x[1] < 0),
                        "chips_bayes_power_below_average": count(profiles, "bayes_power", lambda x: x[1] < 0)}}
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    print(out["verdict"], out["a"], out["b"])


if __name__ == "__main__":
    main(sys.argv[1])
