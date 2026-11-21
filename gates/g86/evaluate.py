"""G86 verdict from run.py's scores.json against registration.md's bars; writes record/result.json.

Usage (repo root): python gates/g86/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
CHIPS = [str(c) for c in range(6, 16)]
FAULTS = ("dead", "ambient", "frozen", "drift2", "drift1")


def share_below(pairs, die):
    return float(np.mean([p["vs_average"]["ci95"][1] < 0 for p in pairs[die]]))


def main(run):
    s = json.load(open(os.path.join(run, "scores.json")))
    valid = (s["case_set_sha256"] == G84_SHA and sorted(s["runs"]) == sorted(CHIPS)
             and all(set(FAULTS) <= set(r["sensors"][i]) for r in s["runs"].values() for i in r["sensors"]))
    sensors = [x for r in s["runs"].values() for x in r["sensors"].values()]
    dies = list(sensors[0]["dead"])
    n_te = s["n_test_cases"]

    def pairs(fault, mode=None):
        return {d: [(x[fault] if mode is None else x[fault][mode])[d] for x in sensors] for d in dies}

    bars = {}
    dead, amb, frz = pairs("dead"), pairs("ambient", "checked"), pairs("frozen", "checked")
    detected = sum(x["ambient"]["detected_cases"] for x in sensors) / (len(sensors) * n_te)
    false = sum(r["healthy"]["dropped_cases"] for r in s["runs"].values()) / (len(s["runs"]) * n_te)
    bars["a_dead_below_avg"] = {d: share_below(dead, d) for d in dies}
    bars["b_ambient_detected_share"] = detected
    bars["b_ambient_checked_below_avg"] = {d: share_below(amb, d) for d in dies}
    bars["c_false_alarm_share"] = false
    bars["d_frozen_checked_below_avg"] = {d: share_below(frz, d) for d in dies}
    ok = {"a": all(v >= 0.95 for v in bars["a_dead_below_avg"].values()),
          "b": detected >= 0.99 and all(v >= 0.95 for v in bars["b_ambient_checked_below_avg"].values()),
          "c": false <= 0.01,
          "d": all(v >= 0.95 for v in bars["d_frozen_checked_below_avg"].values())}
    reported = {}
    for f in FAULTS:
        for mode in ([None] if f == "dead" else ["unchecked", "checked"]):
            p = pairs(f, mode)
            reported[f if mode is None else f"{f}/{mode}"] = {
                d: {"mean_K": float(np.mean([x["mean_group_median_K"] for x in p[d]])),
                    "worst_K": float(np.max([x["mean_group_median_K"] for x in p[d]])),
                    "below_avg_share": share_below(p, d)} for d in dies}
        if f != "dead":
            reported[f"{f}/detected_share"] = sum(x[f]["detected_cases"] for x in sensors) / (len(sensors) * n_te)
    healthy = {d: float(np.mean([r["healthy"]["unchecked"][d]["mean_group_median_K"] for r in s["runs"].values()]))
               for d in dies}
    reported["healthy_mean_K"] = healthy
    verdict = "INCONCLUSIVE" if not valid else ("PASS" if all(ok.values()) else "FAIL")
    out = {"gate": "G86", "verdict": verdict, "valid": valid, "bars_pass": ok, "bars": bars, "reported": reported}
    os.makedirs(os.path.join(HERE, "record"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "record", "result.json"), "w"), indent=1)
    print(json.dumps({"verdict": verdict, "bars_pass": ok, "bars": bars}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
