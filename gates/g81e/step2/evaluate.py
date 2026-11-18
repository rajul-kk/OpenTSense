"""Score G81e from step 2's output against registration.md.

Usage (repo root): python gates/g81e/step2/evaluate.py <run dir>    (reads <run dir>/<program>.json, *_H1.npz,
g50a.json; writes result.json)
"""
import json
import os
import sys

import numpy as np

NEED = 15
IDLE = "idle"
# A floor of exactly 0 would let any rounding difference pass a "> 3 x floor" bar; differences must also exceed these.
MIN_SHARE, MIN_REL_W = 1e-6, 1e-6


def pearson(x, y):
    """Pearson r, or None when either series is constant."""
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def per_program(summary, arrays):
    """Gated values and floors of one program under H1."""
    seeds = [v for s, v in summary["seeds"].items() if s != "0"]
    dyn = np.array([s["mean_dyn_W"] for s in seeds])
    shares = np.sort(np.array([s["bank_dyn_share"] for s in seeds]), axis=1)[:, ::-1]
    miss = arrays["miss_per_window"]
    r = [pearson(np.pad(arrays[f"s{s}_dyn_J"], (0, len(miss) - len(arrays[f"s{s}_dyn_J"]))), miss)
         for s in summary["seeds"] if s != "0"]
    S, floor_k = shares.mean(0), np.ptp(shares, 0)
    return {"dyn_W": float(dyn.mean()), "dyn_floor_W": float(np.ptp(dyn)),
            "dyn_W_nominal": summary["seeds"]["0"]["mean_dyn_W"],
            "dyn_share_of_total": float(dyn.mean() / np.mean([s["mean_total_W"] for s in seeds])),
            "pearson": r, "a2": all(x is not None and x >= 0.9 for x in r),
            "sorted_share": S.tolist(), "sorted_share_floor": floor_k.tolist(),
            "b": bool(np.any(np.abs(S - 1 / len(S)) > np.maximum(3 * floor_k, MIN_SHARE)))}


def main(run):
    names = sorted(f[:-5] for f in os.listdir(run) if f.endswith(".json") and f[:-5] not in ("result", "g50a", "manifest"))
    raw = {n: json.load(open(os.path.join(run, f"{n}.json"))) for n in names}
    progs = {n: per_program(raw[n]["H1"], np.load(os.path.join(run, f"{n}_H1.npz"))) for n in names}
    gated = [n for n in names if n != IDLE]
    med = sorted(gated, key=lambda n: progs[n]["dyn_W"])[len(gated) // 2]
    for n in gated:
        p = progs[n]
        bar = max(3 * max(p["dyn_floor_W"], progs[med]["dyn_floor_W"]), MIN_REL_W * progs[med]["dyn_W"])
        p["a1"] = abs(p["dyn_W"] - progs[med]["dyn_W"]) > bar
    g50a = json.load(open(os.path.join(run, "g50a.json")))
    violations = sum(s["violations"] for n in names for h in ("H1", "H0") for s in raw[n][h]["seeds"].values())
    v3 = {n: raw[n]["H1"]["v3"]["rel_err"] for n in names}
    valid = {"v2_no_violations": violations == 0, "v2_g50a": g50a["rel_diff"] <= 0.01,
             "v3_energy_model": all(e <= 1e-3 for e in v3.values()), "programs": len(gated) == 19}
    count = {b: sum(bool(progs[n][b]) for n in gated) for b in ("a1", "a2", "b")}
    passed = {b: c >= NEED for b, c in count.items()}
    verdict = "INCONCLUSIVE" if not all(valid.values()) else "PASS" if all(passed.values()) else "FAIL"
    h0 = {n: {"txn": raw[n]["H0"]["txn"], "dyn_W": raw[n]["H0"]["seeds"]["0"]["mean_dyn_W"],
              "total_W": raw[n]["H0"]["seeds"]["0"]["mean_total_W"]} for n in names}
    out = {"verdict": verdict, "valid": valid, "count": count, "passed": passed, "median_program": med,
           "violations": violations, "g50a": g50a, "v3_worst": max(v3.values()), "v3": v3,
           "programs": progs, "h1_stats": {n: raw[n]["H1"]["stats"] for n in names}, "h0": h0}
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    print(verdict, count, valid)


if __name__ == "__main__":
    main(sys.argv[1])
