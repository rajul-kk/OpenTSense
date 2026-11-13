"""G77 evaluation: each regularisation-parameter rule against the oracle, on every case set a run directory holds.

For each case set (`make_cases.py` output, one per stack and noise level) Tikhonov about the training-mean power is
fitted on the train split, and every case of the cal and test splits is solved with the lambda each rule picks
(gcv, upre, discrepancy, lcurve with sigma known; upre and discrepancy also told 0.5 and 2 times sigma) and with the
oracle lambda (the grid value with the smallest power error against the truth; evaluation only). Tikhonov uses
nothing from the cal split, so cal and test are both scored: 8 program groups instead of 4.

Per case: power error `pow_rel` per die (the gated quantity) and peak temperature error. Aggregation as the scorer:
the mean over groups of the group median (`bench.metrics.summary`). Paired comparisons use the scorer's group
bootstrap (`metrics.bootstrap_diff`: 10,000 resamples, seed 0, two-sided p).

Usage (from the repo root): python gates/g77/evaluate.py CASES_DIR OUT.json [--factor K]
`--factor` is bar (a)'s registered factor; without it the ratios are reported and nothing is judged.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from opentsense.bench import metrics                     # noqa: E402
from opentsense.bench.cases import CaseSet               # noqa: E402
from opentsense.bench.estimators import Tikhonov         # noqa: E402
from opentsense.estimate import regularise               # noqa: E402

SCORED = ("cal", "test")
WRONG = (0.5, 2.0)
N_BOOT, BOOT_SEED, ALPHA = 10000, 0, 0.05


PLUMBING_K = 0.005        # v1: PACT writes temperatures to 0.01 K


def entries():
    """(rule, sigma scale): every rule with sigma known, then the sigma rules told the wrong sigma."""
    return [(r, 1.0) for r in regularise.RULES] + [(r, k) for r in regularise.NEEDS_SIGMA for k in WRONG]


KNOWN = [Tikhonov(r).name for r, k in entries() if k == 1.0]     # the entries bar (a) gates


def holm(ps):
    """Holm-adjusted p-values, same order as given."""
    order = np.argsort(ps)
    adj, run = np.empty(len(ps)), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj.tolist()


def evaluate(path):
    """Per-entry summaries for one case set, and the per-case power errors the comparisons need."""
    cs = CaseSet.load(path)
    ix = np.concatenate([cs.idx(s) for s in SCORED])
    groups = cs.group[ix]
    est = Tikhonov().fit(cs, cs.idx("train"))
    pub = cs.public(ix)
    b = pub.readings - est.H @ est.mu
    grid = regularise.default_grid(est.svd.s)

    def measure(lam, i):
        pred = est.output(est.mu + regularise.solve(est.svd, b, lam))
        m = metrics.per_case(cs.T[ix], pred["T"], float(cs.cell_um), cs.P[ix], pred["P"])
        return m, lam, i

    res = {"oracle": measure(*regularise.oracle(est.svd, b, cs.P[ix].reshape(len(ix), -1) - est.mu, grid)[:2])}
    for rule, k in entries():
        res[Tikhonov(rule, k).name] = measure(*regularise.choose(rule, est.svd, b, sigma=pub.noise_K * k, lams=grid)[:2])

    dies = [str(d) for d in cs.dies]
    lam_o = res["oracle"][1]
    out = {"file": os.path.basename(path), "sha256": cs.sha256(), "noise_K": float(cs.noise_K), "dies": dies,
           "buried": [bool(x) for x in cs.buried], "cases": int(len(ix)), "groups": int(len(np.unique(groups))),
           # v2: the grid must reach well past both ends of the spectrum, so an end pick is a converged preference
           "grid_lo_over_smin2": float(grid[0] / est.svd.s[-1] ** 2), "grid_hi_over_smax2": float(grid[-1] / est.svd.s[0] ** 2),
           "entries": {}}
    for name, (m, lam, i) in res.items():
        e = {"grid_end_fraction": {"low": float(np.mean(i == 0)), "high": float(np.mean(i == len(grid) - 1))},
             "median_log10_lam_over_oracle": float(np.median(np.log10(lam / lam_o))), "dies": {}}
        for di, d in enumerate(dies):
            e["dies"][d] = {k: metrics.summary(m[k][:, di], groups)["mean_group_median"] for k in ("pow_rel", "peak_err_K")}
        out["entries"][name] = e
    for e in out["entries"].values():
        for d in dies:
            e["dies"][d]["ratio_to_oracle"] = e["dies"][d]["pow_rel"] / out["entries"]["oracle"]["dies"][d]["pow_rel"]
    per = {name: r[0]["pow_rel"] for name, r in res.items()}
    return out, per, groups


def compare(out, per, groups):
    """Bar (b): upre and discrepancy against gcv on power error, per die, Holm over the two rules; then the same at
    each wrong sigma (reported)."""
    cmp = {}
    for d_i, d in enumerate(out["dies"]):
        for tag, k in [("sigma_known", 1.0)] + [(f"sigma_x{k:g}", k) for k in WRONG]:
            names = [Tikhonov(r, k).name for r in regularise.NEEDS_SIGMA]
            tests = [metrics.bootstrap_diff(per[n][:, d_i], per["ridge_gcv"][:, d_i], groups, N_BOOT, BOOT_SEED)
                     for n in names]
            for t, a in zip(tests, holm([t["p"] for t in tests])):
                t["p_holm"] = a
                t["beats_gcv"] = bool(t["diff"] < 0 and a < ALPHA)
            cmp.setdefault(d, {})[tag] = dict(zip(names, tests))
    return cmp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cases_dir")
    ap.add_argument("out")
    ap.add_argument("--factor", type=float, help="bar (a): largest allowed ratio of a rule's power error to the oracle's")
    a = ap.parse_args(argv)
    files = sorted(glob.glob(os.path.join(a.cases_dir, "cases_*_noise*.npz")))
    if not files:
        raise SystemExit(f"no case sets in {a.cases_dir}")
    result = {"case_sets": {}, "factor": a.factor}
    for f in files:
        out, per, groups = evaluate(f)
        out["comparisons"] = compare(out, per, groups)
        result["case_sets"][out["file"]] = out
        print(out["file"])
        for name, e in out["entries"].items():
            line = "  ".join(f"{d}: pow {v['pow_rel']:.4f} x{v['ratio_to_oracle']:.2f}" for d, v in e["dies"].items())
            ends = e["grid_end_fraction"]
            print(f"  {name:16s} {line}  ends low {ends['low']:.2f} high {ends['high']:.2f}")
    built = json.load(open(os.path.join(a.cases_dir, "cases.json")))
    want = {f["path"]: f["sha256"] for st in built.values() for f in st["files"].values()}
    changed = [f for f, cs in result["case_sets"].items() if want.get(f) != cs["sha256"]]
    if changed:
        raise SystemExit(f"case sets differ from the build record cases.json: {changed}")
    plumb = max(v for st in built.values() for v in st["plumbing_max_dT_K"].values())
    result["build"] = {st: {k: v[k] for k in ("seed", "noise_K", "plumbing_max_dT_K")} for st, v in built.items()}
    if a.factor is not None:
        worst = max(cs["entries"][n]["dies"][d]["ratio_to_oracle"]
                    for cs in result["case_sets"].values() for n in KNOWN for d in cs["dies"])
        b_all = all(t["beats_gcv"] for cs in result["case_sets"].values() for d in cs["comparisons"].values()
                    for t in d["sigma_known"].values())
        sets = result["case_sets"].values()
        lo, hi = max(c["grid_lo_over_smin2"] for c in sets), min(c["grid_hi_over_smax2"] for c in sets)
        result["bars"] = {"v1": {"plumbing_max_dT_K": plumb, "pass": bool(plumb <= PLUMBING_K)},
                          "a": {"worst_ratio": worst, "factor": a.factor, "pass": bool(worst <= a.factor)},
                          "b": {"pass": b_all},
                          "v2": {"grid_lo_over_smin2_max": lo, "grid_hi_over_smax2_min": hi,
                                 "pass": bool(lo <= 1e-2 * (1 + 1e-9) and hi >= 1e2 * (1 - 1e-9))}}
        for k, v in result["bars"].items():
            print(f"{k}: {v}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(result, fh, indent=1)
    return result


if __name__ == "__main__":
    main()
