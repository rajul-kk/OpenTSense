"""G86 dry run, part 2 (not a gated result): harder single-sensor faults than floor.py's stuck-at-ambient.

Same cases, profile, dry chips, field model, threshold and bootstrap as floor.py. Each sensor in turn takes each
fault, in every test case of the chip:
  ambient  reads zero rise (floor.py's `stuck`; repeated as the easy reference)
  frozen   reads the chip's own mean reading of that sensor over the train split (a plausible, stuck value)
  drift2   reads 2 K high (an offset drift outside the profile's 1 K sigma)
  drift1   reads 1 K high
each scored unchecked (the estimator is not told) and checked (fault.repair). Per fault: RMSE per die, the interval
against the average, and the share of test cases in which the faulty sensor was the one dropped.

Usage (repo root): python gates/g86/dry/faults.py <G84 cases.npz> <out.json>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import floor  # noqa: E402  (its constants, rmse and compare; floor.py stays as run)
from floor import fault, readings, CaseSet, GaussianField  # noqa: E402

FAULTS = {
    "ambient": lambda y, y_train: np.zeros_like(y),
    "frozen": lambda y, y_train: np.full_like(y, y_train.mean()),
    "drift2": lambda y, y_train: y + 2.0,
    "drift1": lambda y, y_train: y + 1.0,
}


def main(cases, out):
    cs0 = CaseSet.load(cases)
    if cs0.sha256() != floor.G84_SHA:
        raise SystemExit(f"case set {cs0.sha256()} is not G84's")
    tr, te = cs0.idx("train"), cs0.idx("test")
    groups, dies = cs0.group[te], cs0.dies
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S = cs0.flat_sensors
    m = len(S)
    z_max = fault.threshold(floor.ALPHA, m)
    r_avg = floor.rmse(cs0, te, np.broadcast_to(cs0.T[tr].mean(0).ravel(), (len(te), gf.n)))
    res = {"case_set_sha256": cs0.sha256(), "profile": floor.PROFILE, "z_max": z_max, "chips": {}}
    for chip in floor.CHIPS:
        cs = readings.with_sensor(cs0, floor.PROFILE, chip)
        y, y_tr, noise = cs.readings[te].astype(np.float64), cs.readings[tr].astype(np.float64), float(cs.noise_K)
        row = {}
        for name, f in FAULTS.items():
            row[name] = {}
            for i in range(m):
                bad = y.copy()
                bad[:, i] = f(y[:, i], y_tr[:, i])
                chk_mean, dropped = fault.repair(gf, S, bad, noise, z_max)
                row[name][str(i)] = {
                    "unchecked": floor.compare(floor.rmse(cs, te, gf.posterior(S, bad, noise).mean), r_avg, groups, dies),
                    "checked": floor.compare(floor.rmse(cs, te, chk_mean), r_avg, groups, dies),
                    "detected_share": float((dropped == i).mean())}
        res["chips"][str(chip)] = row
        print("chip", chip, {n: round(float(np.mean([s["detected_share"] for s in row[n].values()])), 3) for n in FAULTS},
              flush=True)
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(out + ".tmp", out)
    for name in FAULTS:
        for d in ("top", "bot"):
            for mode in ("unchecked", "checked"):
                v = [s[mode][d]["mean_group_median_K"] for c in res["chips"].values() for s in c[name].values()]
                ok = sum(s[mode][d]["vs_average_ci95"][1] < 0 for c in res["chips"].values() for s in c[name].values())
                print(f"{name:8s} {mode:9s} {d}: mean {np.mean(v):.3f} K worst {max(v):.3f} K CI<0 {ok}/{len(v)}")
        det = [s["detected_share"] for c in res["chips"].values() for s in c[name].values()]
        print(f"{name:8s} detected: mean {np.mean(det):.3f} min {min(det):.3f}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
