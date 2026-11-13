"""G95 scorer: bars (a), (b), (c) of `registration.md` on the sweeps in a run folder.

Usage (from the repo root): python gates/g95/evaluate.py RUN_DIR CASE
RUN_DIR holds <kit>/sweep_<kit>.json for each kit (written by `sweep.py`, which stops before writing if a window's
real-leakage fixed point does not reproduce G92e's recorded peak: validity). CASE (nominal or hot) must match the
sweeps' case (files written before sweeps recorded their case are nominal). Writes RUN_DIR/result.json.
"""
import json
import os
import sys

KITS = ("ihp", "asap7", "asap7_lvt")
DELTA = 0.001              # (a): f <= 1 - DELTA converges, f >= 1 + DELTA runs away
PICARD_K = 1e-6            # (a): long Picard agrees with Newton on every converged point
RHO_B = 0.97               # (b): rho at the last converged bisection point (student, 12 Nov; the saddle-node law at
                           # the sweep's bisection tolerance 1e-4 gives 1 - sqrt(4e-4) = 0.98, so 0.97 is looser)
F_C, TOL_C = 0.8, 0.25     # (c): for converged f <= F_C, |A - 1/(1 - rho_hot)| / A <= TOL_C


def score_window(w):
    grid = w["grid"]
    wrong = [g["f"] for g in grid if (g["f"] <= 1 - DELTA and g["status"] != "converged")
             or (g["f"] >= 1 + DELTA and g["status"] != "runaway")]
    conv = [g for g in grid if g["status"] == "converged"]
    picard_bad = [g["f"] for g in conv if not g["picard_converged"] or g["picard_diff_K"] > PICARD_K]
    c_err = {g["f"]: abs(g["A"] - g["pred_hot"]) / g["A"] for g in conv if g["f"] <= F_C}
    c_worst = max(c_err.values()) if c_err else None
    return {"a": {"misclassified_f": wrong, "picard_disagrees_f": picard_bad, "pass": not wrong and not picard_bad},
            "b": {"rho_at_s_lo": w["rho_at_s_lo"], "bound": RHO_B, "pass": w["rho_at_s_lo"] >= RHO_B},
            "c": {"rel_err_by_f": c_err, "worst": c_worst, "pass": len(c_err) >= 2 and c_worst <= TOL_C},
            "f_nominal": w["f_nominal"]}


def main(run, case):
    res = {"case": case, "kits": {}, "missing": []}
    for kit in KITS:
        p = os.path.join(run, kit, f"sweep_{kit}.json")
        if not os.path.exists(p):
            res["missing"].append(kit)
            continue
        sw = json.load(open(p))
        if sw.get("case", "nominal") != case:
            raise SystemExit(f"{p} is case {sw.get('case')!r}, not {case!r}")
        res["kits"][kit] = {w: score_window(v) for w, v in sw["windows"].items()}
    wins = [v for k in res["kits"].values() for v in k.values()]
    if res["missing"]:
        res["verdict"] = "INCONCLUSIVE"
    else:
        res["bars"] = {b: all(v[b]["pass"] for v in wins) for b in ("a", "b", "c")}
        res["verdict"] = "PASS" if all(res["bars"].values()) else "FAIL"
    json.dump(res, open(os.path.join(run, "result.json"), "w"), indent=1)
    for kit, ws in res["kits"].items():
        for w, v in ws.items():
            print(kit, w, {b: v[b]["pass"] for b in "abc"}, "rho@s_lo", round(v["b"]["rho_at_s_lo"], 4),
                  "c worst", v["c"]["worst"] and round(v["c"]["worst"], 3), "1/f", round(1 / v["f_nominal"], 1))
    print("missing", res["missing"], "verdict", res["verdict"], res.get("bars"))
    return res


if __name__ == "__main__":
    main(*sys.argv[1:3])
