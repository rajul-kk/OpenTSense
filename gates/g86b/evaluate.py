"""G86b verdict from run.py's scores.json against registration.md's bars; writes <run dir>/result.json
(scripts/record_gate.py copies runs/main's into record/).

Usage (repo root): python gates/g86b/evaluate.py <run dir>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
CHIPS = [str(c) for c in range(16, 26)]
FAULTS = ("ambient", "frozen", "drift2", "drift1")
Z_MAX = 3.4205     # fault.threshold(0.01, 16) = 3.42053, to 4 decimals


def share_below(pairs):
    return float(np.mean([p["vs_average"]["ci95"][1] < 0 for p in pairs]))


def main(run):
    s = json.load(open(os.path.join(run, "scores.json")))
    sensors = [x for r in s["runs"].values() for x in r.get("sensors", {}).values()]
    valid = (s["case_set_sha256"] == G84_SHA and sorted(s["runs"]) == sorted(CHIPS) and abs(s["z_max"] - Z_MAX) < 1e-4
             and s.get("outlier_K") == 2.7 and s.get("profile") == "ring_osc" and s.get("n_test_cases") == 80
             and all("healthy" in r and len(r.get("sensors", {})) == 16 for r in s["runs"].values())
             and all(set(FAULTS) | {"offset27_dropped_cases"} <= set(x) for x in sensors))
    if not valid:
        out = {"gate": "G86b", "verdict": "INCONCLUSIVE", "valid": False}
        json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
        print(json.dumps(out))
        return
    dies = list(sensors[0]["ambient"]["checked"]) if sensors else []
    n_te = s["n_test_cases"]

    def checked(fault):
        return {d: [x[fault]["checked"][d] for x in sensors] for d in dies}

    amb, frz = checked("ambient"), checked("frozen")
    bars = {
        "a_healthy_false_alarm_share": sum(r["healthy"]["dropped_cases"] for r in s["runs"].values())
        / (len(s["runs"]) * n_te),
        "b_offset27_false_alarm_share": sum(x["offset27_dropped_cases"] for x in sensors) / (len(sensors) * n_te),
        "c_ambient_detected_share": sum(x["ambient"]["detected_cases"] for x in sensors) / (len(sensors) * n_te),
        "c_ambient_checked_below_avg": {d: share_below(amb[d]) for d in dies},
        "d_frozen_checked_below_avg": {d: share_below(frz[d]) for d in dies},
    }
    ok = {"a": bars["a_healthy_false_alarm_share"] <= 0.01,
          "b": bars["b_offset27_false_alarm_share"] <= 0.01,
          "c": (bars["c_ambient_detected_share"] >= 0.99
                and all(v >= 0.95 for v in bars["c_ambient_checked_below_avg"].values())),
          "d": all(v >= 0.95 for v in bars["d_frozen_checked_below_avg"].values())}
    reported = {f"{f}/detected_share": sum(x[f]["detected_cases"] for x in sensors) / (len(sensors) * n_te)
                for f in FAULTS}
    for f in FAULTS:
        p = checked(f)
        reported[f"{f}/checked"] = {d: {"mean_K": float(np.mean([x["mean_group_median_K"] for x in p[d]])),
                                        "worst_K": float(np.max([x["mean_group_median_K"] for x in p[d]])),
                                        "below_avg_share": share_below(p[d])} for d in dies}
    reported["healthy_false_alarm_share_uncalibrated"] = sum(
        r["healthy"]["dropped_cases_uncalibrated"] for r in s["runs"].values()) / (len(s["runs"]) * n_te)
    reported["healthy_checked_mean_K"] = {d: float(np.mean([r["healthy"]["checked"][d]["mean_group_median_K"]
                                                            for r in s["runs"].values()])) for d in dies}
    reported["healthy_uncalibrated_unchecked_mean_K"] = {
        d: float(np.mean([r["healthy"]["uncalibrated_unchecked"][d]["mean_group_median_K"] for r in s["runs"].values()]))
        for d in dies}
    reported["max_abs_offset_K"] = {c: float(np.max(np.abs(r["offsets_K"]))) for c, r in s["runs"].items()}
    verdict = "PASS" if all(ok.values()) else "FAIL"
    out = {"gate": "G86b", "verdict": verdict, "valid": valid, "bars_pass": ok, "bars": bars, "reported": reported}
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    print(json.dumps({"verdict": verdict, "bars_pass": ok, "bars": bars}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
