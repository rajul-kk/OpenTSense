"""Score estimators on a case set with one command.

    python -m opentsense.bench.score CASES.npz --estimators average,field_model,bayes_power --out DIR [--split test]

Fits each estimator on the train split, predicts the scored split, and writes DIR/result.json (summaries per die and
test tag, comparisons against the average baseline), DIR/per_case.npz and DIR/manifest.json.
"""
import argparse
import json
import os
import time

import numpy as np

from .. import manifest
from . import metrics
from .cases import CaseSet
from .estimators import REGISTRY


def _summarise(m, dies, groups, tags):
    """Group summaries of per-case metrics, per die and per test tag (plus "all")."""
    out = {}
    for di, die in enumerate(dies):
        out[str(die)] = {}
        for tag in ["all"] + sorted(set(tags.tolist())):
            sel = np.ones(len(tags), bool) if tag == "all" else tags == tag
            out[str(die)][tag] = {k: metrics.summary(m[k][sel, di], groups[sel]) for k in metrics.METRICS}
    return out


def _compare(per, baseline, dies, groups, n_boot):
    """Group-bootstrap differences of every estimator against the baseline, per die, on peak error and RMSE."""
    if baseline not in per:
        return {}
    return {f"{name} - {baseline}": {
                str(die): {k: metrics.bootstrap_diff(per[name][k][:, di], per[baseline][k][:, di], groups, n_boot)
                           for k in ("peak_err_K", "rmse_K")}
                for di, die in enumerate(dies)}
            for name in per if name != baseline}


def score(cs, names, split="test", baseline="average", n_boot=10000):
    tr, te = cs.idx("train"), cs.idx(split)
    if not len(tr) or not len(te):
        raise ValueError("need train cases and cases in the scored split")
    groups, tags = cs.group[te], cs.tag[te]
    res = {"case_set": {"sha256": cs.sha256(), "stack_id": str(cs.stack_id), "n_train": int(len(tr)),
                        "n_scored": int(len(te)), "split": split, "dies": [str(d) for d in cs.dies],
                        "buried": [bool(b) for b in cs.buried], "sensors": int(len(cs.sensors)), "noise_K": float(cs.noise_K)},
           "estimators": {}}
    per = {}
    for name in names:
        est = REGISTRY[name]()
        t0 = time.perf_counter(); est.fit(cs, tr); t1 = time.perf_counter()
        out = est.predict(cs.public(te)); t2 = time.perf_counter()
        per[name] = metrics.per_case(cs.T[te], out["T"], float(cs.cell_um), cs.P[te] if cs.has_power else None, out.get("P"))
        res["estimators"][name] = {"fit_s": round(t1 - t0, 3), "predict_s": round(t2 - t1, 3),
                                   "summary": _summarise(per[name], cs.dies, groups, tags)}
    res["comparisons"] = _compare(per, baseline, cs.dies, groups, n_boot)
    return res, per


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cases")
    ap.add_argument("--estimators", default="average,field_model,bayes_power")
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    cs = CaseSet.load(a.cases)
    res, per = score(cs, [n for n in a.estimators.split(",") if n], a.split, n_boot=a.n_boot)
    with open(os.path.join(a.out, "result.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    np.savez_compressed(os.path.join(a.out, "per_case.npz"), **{f"{e}/{k}": v for e, m in per.items() for k, v in m.items()})
    manifest.write(os.path.join(a.out, "manifest.json"), {"case_set_sha256": res["case_set"]["sha256"], "cases": os.path.abspath(a.cases)})
    for name, e in res["estimators"].items():
        line = "  ".join(f"{d}: peak {v['all']['peak_err_K']['mean_group_median']:.3f} K" for d, v in e["summary"].items())
        print(f"{name:12s} {line}")
    return res


if __name__ == "__main__":
    main()
