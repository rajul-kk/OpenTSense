"""G77b evaluation: the parameter rules with the readings reference, against their oracle and against G77's reference.

As G77's `evaluate.py` (whose helpers it imports; G77's folder is a frozen record), with each case set solved twice:
about H mu (reference "model", G77) and about the training cases' mean readings (reference "readings",
`bench.estimators.Tikhonov`). Each reference has its own oracle (the grid lambda with the smallest power error for
that reference's data), and each rule's ratio is taken against its own reference's oracle.

Usage (from the repo root): python gates/g77b/evaluate.py CASES_DIR OUT.json [--factor K]
"""
import argparse
import glob
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
# G77's helpers (holm, constants), loaded by path: both gates' scripts are called evaluate.py
_spec = importlib.util.spec_from_file_location("g77_evaluate", os.path.join(HERE, "..", "g77", "evaluate.py"))
g77 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g77)
from opentsense import manifest                         # noqa: E402
from opentsense.bench import metrics                     # noqa: E402
from opentsense.bench.cases import CaseSet               # noqa: E402
from opentsense.bench.estimators import Tikhonov         # noqa: E402
from opentsense.estimate import regularise               # noqa: E402

REFS = ("model", "readings")
GATED = [Tikhonov(r, reference="readings").name for r in regularise.NEEDS_SIGMA]      # bar (a)


def entries():
    """(rule, sigma scale, reference): every rule with sigma known for both references; the wrong-sigma entries with
    the readings reference."""
    return ([(r, 1.0, ref) for ref in REFS for r in regularise.RULES]
            + [(r, k, "readings") for r in regularise.NEEDS_SIGMA for k in g77.WRONG])


def oracle_name(ref):
    return "oracle" if ref == "model" else "oracle_ref"


def evaluate(path):
    cs = CaseSet.load(path)
    ix = np.concatenate([cs.idx(s) for s in g77.SCORED])
    groups = cs.group[ix]
    pub = cs.public(ix)
    P = cs.P[ix].reshape(len(ix), -1)
    fitted = {ref: Tikhonov(reference=ref).fit(cs, cs.idx("train")) for ref in REFS}
    grid = regularise.default_grid(fitted["model"].svd.s)          # H, and so the grid, is the same for both

    def measure(est, b, lam, i):
        pred = est.output(est.mu + regularise.solve(est.svd, b, lam))
        return metrics.per_case(cs.T[ix], pred["T"], float(cs.cell_um), cs.P[ix], pred["P"]), lam, i

    res, ref_of = {}, {}
    for ref, est in fitted.items():
        b = pub.readings - est.y0
        res[oracle_name(ref)] = measure(est, b, *regularise.oracle(est.svd, b, P - est.mu, grid)[:2])
        ref_of[oracle_name(ref)] = ref
        for rule, k, r in entries():
            if r == ref:
                name = Tikhonov(rule, k, ref).name
                res[name] = measure(est, b, *regularise.choose(rule, est.svd, b, sigma=pub.noise_K * k, lams=grid)[:2])
                ref_of[name] = ref
    dies = [str(d) for d in cs.dies]
    s = fitted["model"].svd.s
    out = {"file": os.path.basename(path), "sha256": cs.sha256(), "noise_K": float(cs.noise_K), "dies": dies,
           "cases": int(len(ix)), "groups": int(len(np.unique(groups))),
           "grid_lo_over_smin2": float(grid[0] / s[-1] ** 2), "grid_hi_over_smax2": float(grid[-1] / s[0] ** 2),
           "entries": {}}
    for name, (m, lam, i) in res.items():
        lam_o = res[oracle_name(ref_of[name])][1]
        out["entries"][name] = {
            "reference": ref_of[name],
            "grid_end_fraction": {"low": float(np.mean(i == 0)), "high": float(np.mean(i == len(grid) - 1))},
            "median_log10_lam_over_oracle": float(np.median(np.log10(lam / lam_o))),
            "dies": {d: {k: metrics.summary(m[k][:, di], groups)["mean_group_median"] for k in ("pow_rel", "peak_err_K")}
                     for di, d in enumerate(dies)}}
    for name, e in out["entries"].items():
        o = out["entries"][oracle_name(e["reference"])]
        for d in dies:
            e["dies"][d]["ratio_to_oracle"] = e["dies"][d]["pow_rel"] / o["dies"][d]["pow_rel"]
    return out, {name: r[0]["pow_rel"] for name, r in res.items()}, groups


def compare(out, per, groups):
    """Bar (b): the readings reference against the model reference for UPRE and the discrepancy rule (sigma known),
    per die, Holm over the two rules. Reported: the same for GCV and the L-curve."""
    cmp = {}
    for d_i, d in enumerate(out["dies"]):
        for tag, rules in (("gated", regularise.NEEDS_SIGMA), ("reported", ("gcv", "lcurve"))):
            tests = {r: metrics.bootstrap_diff(per[Tikhonov(r, reference="readings").name][:, d_i],
                                               per[Tikhonov(r).name][:, d_i], groups, g77.N_BOOT, g77.BOOT_SEED)
                     for r in rules}
            for t, a in zip(tests.values(), g77.holm([t["p"] for t in tests.values()])):
                t["p_holm"] = a
                t["readings_better"] = bool(t["diff"] < 0 and a < g77.ALPHA)
            cmp.setdefault(d, {})[tag] = tests
    return cmp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cases_dir")
    ap.add_argument("out")
    ap.add_argument("--factor", type=float, help="bar (a): largest allowed ratio to the oracle (readings reference)")
    a = ap.parse_args(argv)
    files = sorted(glob.glob(os.path.join(a.cases_dir, "cases_*_noise*.npz")))
    if not files:
        raise SystemExit(f"no case sets in {a.cases_dir}")
    built = json.load(open(os.path.join(a.cases_dir, "cases.json")))
    want = {f["path"]: f["sha256"] for st in built.values() for f in st["files"].values()}
    result = {"case_sets": {}, "factor": a.factor,
              "build": {st: {k: v[k] for k in ("seed", "noise_K", "plumbing_max_dT_K")} for st, v in built.items()}}
    for f in files:
        out, per, groups = evaluate(f)
        if want.get(out["file"]) != out["sha256"]:
            raise SystemExit(f"{out['file']} differs from the build record cases.json")
        out["comparisons"] = compare(out, per, groups)
        result["case_sets"][out["file"]] = out
        print(out["file"])
        for name, e in out["entries"].items():
            line = "  ".join(f"{d}: pow {v['pow_rel']:.4f} x{v['ratio_to_oracle']:.2f}" for d, v in e["dies"].items())
            print(f"  {name:20s} {line}")
    if a.factor is not None:
        sets = list(result["case_sets"].values())
        plumb = max(v for st in built.values() for v in st["plumbing_max_dT_K"].values())
        worst = max(c["entries"][n]["dies"][d]["ratio_to_oracle"] for c in sets for n in GATED for d in c["dies"])
        b_all = all(t["readings_better"] for c in sets for d in c["comparisons"].values() for t in d["gated"].values())
        lo, hi = max(c["grid_lo_over_smin2"] for c in sets), min(c["grid_hi_over_smax2"] for c in sets)
        result["bars"] = {"v1": {"plumbing_max_dT_K": plumb, "pass": bool(plumb <= g77.PLUMBING_K)},
                          "v2": {"grid_lo_over_smin2_max": lo, "grid_hi_over_smax2_min": hi,
                                 "pass": bool(lo <= 1e-2 * (1 + 1e-9) and hi >= 1e2 * (1 - 1e-9))},
                          "a": {"worst_ratio": worst, "factor": a.factor, "pass": bool(worst <= a.factor)},
                          "b": {"pass": b_all}}
        for k, v in result["bars"].items():
            print(f"{k}: {v}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(result, fh, indent=1)
    manifest.write(os.path.join(os.path.dirname(os.path.abspath(a.out)), "manifest.json"),
                   {"cases_dir": os.path.abspath(a.cases_dir), "factor": a.factor,
                    "case_sets": {f: c["sha256"] for f, c in result["case_sets"].items()}})
    return result


if __name__ == "__main__":
    main()
