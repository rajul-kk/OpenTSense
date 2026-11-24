"""G86b gated run: G86's failed-sensor check after a per-chip offset calibration (registration.md).

Per chip (seeds 16 to 25): offsets from the cal split by `fault.offsets` (no true temperature), subtracted from every
test reading; then G86's check (`fault.repair` at `fault.threshold(0.01, 16)`) on the healthy chip, on the chip with
each sensor in turn shifted +2.7 K in cal and test, and with each sensor in turn failing on the test split only
(stuck at ambient, frozen, drift +1 / +2 K). Field model, average, cases and statistic as G86 (imported from its
run.py, which stays as run).

Usage (repo root, host): python gates/g86b/run.py <out dir>
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g86")]
import run as g86  # noqa: E402
from run import G84_SHA, PROFILE, UNKNOWN, CaseSet, GaussianField, compare, fault, manifest, readings, rmse  # noqa: E402

CHIPS, ALPHA, OUTLIER_K = tuple(range(16, 26)), 0.01, 2.7
CODE = g86.CODE + ["gates/g86b/run.py", "gates/g86b/evaluate.py", "gates/g86b/registration.md"]


def inputs():
    return {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in CODE}


def chip(cs, gf, S, ix, r_avg, groups, dies, z_max):
    tr, ca, te = ix
    y_tr, y_ca, y_te = (cs.readings[i].astype(np.float64) for i in (tr, ca, te))
    noise, m = float(cs.noise_K), len(S)
    off = fault.offsets(gf, S, y_ca, noise)

    def checked(y):
        chk, dropped = fault.repair(gf, S, y, noise, z_max)
        return compare(rmse(cs, te, chk), r_avg, groups, dies), dropped

    healthy, dropped = checked(y_te - off)
    row = {"noise_K": noise, "offsets_K": off.round(4).tolist(), "healthy": {
        "uncalibrated_unchecked": compare(rmse(cs, te, gf.posterior(S, y_te, noise).mean), r_avg, groups, dies),
        "checked": healthy, "dropped_cases": int((dropped >= 0).sum()),
        "dropped_cases_uncalibrated": int((fault.repair(gf, S, y_te, noise, z_max)[1] >= 0).sum())}, "sensors": {}}
    for i in range(m):
        shift = np.zeros(m)
        shift[i] = OUTLIER_K
        o = fault.offsets(gf, S, y_ca + shift, noise)
        s = {"die": str(dies[cs.sensors[i, 0]]),
             "offset27_dropped_cases": int((fault.repair(gf, S, y_te + shift - o, noise, z_max)[1] >= 0).sum())}
        for name, f in UNKNOWN.items():
            bad = y_te.copy()
            bad[:, i] = f(y_te[:, i], y_tr[:, i])
            res, dropped = checked(bad - off)
            s[name] = {"checked": res, "detected_cases": int((dropped == i).sum())}
        row["sensors"][str(i)] = s
    return row


def main(out):
    os.makedirs(out, exist_ok=True)
    hashes = inputs()
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G86b", "inputs_sha256": hashes})
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), cases], check=True)
    cs0 = CaseSet.load(cases)
    if cs0.sha256() != G84_SHA:
        raise SystemExit(f"case set {cs0.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    ix = tuple(cs0.idx(k) for k in ("train", "cal", "test"))
    tr, te = ix[0], ix[2]
    groups, dies = cs0.group[te], cs0.dies
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S = cs0.flat_sensors
    z_max = fault.threshold(ALPHA, len(S))
    r_avg = rmse(cs0, te, np.broadcast_to(cs0.T[tr].mean(0).ravel(), (len(te), gf.n)))
    res = {"case_set_sha256": cs0.sha256(), "profile": PROFILE, "chips": list(CHIPS), "z_max": z_max,
           "outlier_K": OUTLIER_K, "n_test_cases": int(len(te)), "runs": {}}
    for c in CHIPS:
        res["runs"][str(c)] = chip(readings.with_sensor(cs0, PROFILE, c), gf, S, ix, r_avg, groups, dies, z_max)
        print("chip", c, "done", flush=True)
    if inputs() != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    with open(os.path.join(out, "scores.json.tmp"), "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(os.path.join(out, "scores.json.tmp"), os.path.join(out, "scores.json"))


if __name__ == "__main__":
    main(sys.argv[1])
