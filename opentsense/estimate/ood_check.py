"""Cross-package out-of-distribution check for sparse-sensor reconstruction on IC-ThermBench.

For one level: fit the Gaussian field on the benchmark's train split, place m sensors, calibrate the bands on the first
half of val, then score
  ID:   the second half of val (packages seen in training: Case8 on level2-4, Case19 on level5), and
  OOD:  each test case (Case9 and Case10; Case20), with duplicates of earlier fields dropped by default.
The readings are the true temperature at the sensor pixels plus Gaussian noise of `noise` K.
Usage: python -m opentsense.estimate.ood_check <level> <out.json> [--m 16,32] [--rank 64] [--noise 0.1] [--alpha 0.1]
       [--methods qdeim,greedy_a,greedy_d,uniform,random] [--keep-duplicates]"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from . import calibrate, icthermbench, placement
from .field_model import GaussianField


def run(level, ms=(16, 32), rank=64, noise=0.1, alpha=0.1, methods=("qdeim", "greedy_a", "greedy_d", "uniform", "random"),
        dedupe=True, root=icthermbench.DEFAULT_ROOT, seed=0):
    t0 = time.time()
    lv = icthermbench.load(level, root)
    N, ny, nx = lv.T.shape
    X = lv.T.reshape(N, -1)
    dup = icthermbench.duplicate_mask(lv) if dedupe else np.zeros(N, bool)
    tr, va, te = (np.arange(N)[lv.split[k]] for k in ("train", "val", "test"))
    cal, idt = va[: len(va) // 2], va[len(va) // 2:]
    keep = lambda ix: ix[~dup[ix]]
    model = GaussianField(rank=rank).fit(X[tr])
    rng = np.random.default_rng(seed)
    sets = {"ID " + "/".join(sorted(set(lv.case[idt]))): keep(idt)}
    for c in sorted(set(lv.case[te]), key=lambda s: int(s[4:])):
        sets["OOD " + c] = keep(te[lv.case[te] == c])
    out = dict(level=level, case_source=lv.case_source, grid=[ny, nx], n=dict(train=len(tr), cal=len(cal), **{k: len(v) for k, v in sets.items()}),
               duplicates_dropped=int(dup[np.concatenate([cal, idt, te])].sum()) if dedupe else 0,
               rank=model.r, energy_kept=model.energy_kept, noise_K=noise, alpha=alpha, results={})
    for m in ms:
        for meth in methods:
            if meth == "uniform":
                S = placement.uniform_grid((ny, nx), m)
            elif meth == "random":
                S = placement.random_sites(model.n, m, seed=seed)
            else:
                S = placement.METHODS[meth](model, m, noise)
            def post(ix):
                y = X[ix][:, S] + rng.normal(0, noise, (len(ix), len(S)))
                return model.posterior(S, y, noise)
            pc = post(cal)
            cb = calibrate.Calibrator(alpha).fit(X[cal], pc.mean, pc.std)
            res = {}
            id_key = next(iter(sets))
            posts = {k: post(ix) for k, ix in sets.items() if len(ix)}
            for k, p in posts.items():
                res[k] = cb.evaluate(X[sets[k]], p.mean, p.std)
                if k != id_key:
                    res[k]["ood_flag"] = calibrate.ood_report(pc.mahal2, posts[id_key].mahal2, p.mahal2, len(S))
            out["results"][f"m{m} {meth}"] = dict(sensors=[int(s) for s in S], **res)
            r_id, r_ood = res[id_key], [v for k, v in res.items() if k != id_key]
            print(f"{level} m={m:3d} {meth:9s} ID rmse {r_id['rmse_K']:.3f} cov {r_id['cover_marg']:.3f}/{r_id['cover_sim']:.3f} | "
                  + " | ".join(f"{k.split()[1]} rmse {v['rmse_K']:.3f} cov {v['cover_marg']:.3f}/{v['cover_sim']:.3f} auroc {v['ood_flag']['auroc']:.3f}"
                               for k, v in zip([k for k in res if k != id_key], r_ood)), flush=True)
    out["wall_s"] = time.time() - t0
    return out


def run_loco(level, m=32, rank=64, noise=0.1, alpha=0.1, methods=("qdeim", "greedy_a", "uniform"), root=icthermbench.DEFAULT_ROOT, seed=0):
    """Leave one case (package) out: for each case, fit on every other case, calibrate on a random 10% of those, and test
    on the held-out case (fields byte-identical to any training or calibration field dropped). The ID row tests on a
    further random 10% of the other cases, disjoint from fit and calibration."""
    t0 = time.time()
    lv = icthermbench.load(level, root)
    N, ny, nx = lv.T.shape
    X = lv.T.reshape(N, -1)
    h = icthermbench.field_hashes(lv.T)
    rng = np.random.default_rng(seed)
    out = dict(level=level, case_source=lv.case_source, m=m, rank=rank, noise_K=noise, alpha=alpha, folds={})
    for c in sorted(set(lv.case), key=lambda s: int(s[4:])):
        rest = rng.permutation(np.flatnonzero(lv.case != c))
        k = len(rest) // 10
        cal, idt, fit = rest[:k], rest[k:2 * k], rest[2 * k:]
        seen = set(h[fit]) | set(h[cal])
        te = np.array([i for i in np.flatnonzero(lv.case == c) if h[i] not in seen], int)
        idt = np.array([i for i in idt if h[i] not in set(h[fit])], int)
        model = GaussianField(rank=rank).fit(X[fit])
        fold = dict(n=dict(fit=len(fit), cal=len(cal), id=len(idt), held_out=len(te)), energy_kept=model.energy_kept)
        for meth in methods:
            S = placement.uniform_grid((ny, nx), m) if meth == "uniform" else placement.METHODS[meth](model, m, noise)
            post = lambda ix: model.posterior(S, X[ix][:, S] + rng.normal(0, noise, (len(ix), len(S))), noise)
            pc, pi, po = post(cal), post(idt), post(te)
            cb = calibrate.Calibrator(alpha).fit(X[cal], pc.mean, pc.std)
            fold[meth] = dict(id=cb.evaluate(X[idt], pi.mean, pi.std), held_out=cb.evaluate(X[te], po.mean, po.std),
                              ood_flag=calibrate.ood_report(pc.mahal2, pi.mahal2, po.mahal2, len(S)))
            r1, r2 = fold[meth]["id"], fold[meth]["held_out"]
            print(f"{level} out={c:6s} m={m} {meth:9s} ID rmse {r1['rmse_K']:.3f} cov {r1['cover_marg']:.3f}/{r1['cover_sim']:.3f} | "
                  f"held-out rmse {r2['rmse_K']:.3f} max {r2['max_abs_K']:.2f} cov {r2['cover_marg']:.3f}/{r2['cover_sim']:.3f} "
                  f"| flag {fold[meth]['ood_flag']['detect_ood']:.3f} auroc {fold[meth]['ood_flag']['auroc']:.3f}", flush=True)
        out["folds"][c] = fold
    out["wall_s"] = time.time() - t0
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("level"); ap.add_argument("out")
    ap.add_argument("--loco", action="store_true", help="leave-one-case-out sweep (uses the first --m value)")
    ap.add_argument("--m", default="16,32"); ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--noise", type=float, default=0.1); ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--methods", default="qdeim,greedy_a,greedy_d,uniform,random")
    ap.add_argument("--keep-duplicates", action="store_true"); ap.add_argument("--root", default=icthermbench.DEFAULT_ROOT)
    a = ap.parse_args()
    if a.loco:
        json.dump(run_loco(a.level, int(a.m.split(",")[0]), a.rank, a.noise, a.alpha, root=a.root), open(a.out, "w"), indent=1)
        raise SystemExit
    r = run(a.level, tuple(int(x) for x in a.m.split(",")), a.rank, a.noise, a.alpha, tuple(a.methods.split(",")),
            not a.keep_duplicates, a.root)
    json.dump(r, open(a.out, "w"), indent=1)
