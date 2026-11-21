"""G86 gated run: one failed sensor per chip, each sensor in turn, every fault (registration.md).

Usage (repo root, host): python gates/g86/run.py <out dir>
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g102")]
from opentsense import manifest  # noqa: E402
from opentsense.bench import metrics  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate import fault  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402
import readings  # noqa: E402

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
PROFILE, CHIPS, ALPHA, N_BOOT = "ring_osc", tuple(range(6, 16)), 0.01, 10000
UNKNOWN = {
    "ambient": lambda y, y_train: np.zeros_like(y),
    "frozen": lambda y, y_train: np.full_like(y, y_train.mean()),
    "drift2": lambda y, y_train: y + 2.0,
    "drift1": lambda y, y_train: y + 1.0,
}
CODE = ["gates/g86/run.py", "gates/g86/registration.md", "gates/g102/readings.py", "gates/g84/make_cases.py",
        "opentsense/estimate/fault.py", "opentsense/estimate/field_model.py", "opentsense/estimate/sensor.py",
        "opentsense/bench/metrics.py", "opentsense/bench/cases.py"]


def inputs():
    return {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in CODE}


def rmse(cs, te, mean):
    return metrics.per_case(cs.T[te], mean.reshape((len(te),) + cs.T.shape[1:]), float(cs.cell_um))["rmse_K"]


def compare(r, r_avg, groups, dies):
    return {str(d): {"mean_group_median_K": metrics.summary(r[:, i], groups)["mean_group_median"],
                     "vs_average": metrics.bootstrap_diff(r[:, i], r_avg[:, i], groups, N_BOOT)}
            for i, d in enumerate(dies)}


def main(out):
    os.makedirs(out, exist_ok=True)
    hashes = inputs()
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G86", "inputs_sha256": hashes})
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), cases], check=True)
    cs0 = CaseSet.load(cases)
    if cs0.sha256() != G84_SHA:
        raise SystemExit(f"case set {cs0.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    tr, te = cs0.idx("train"), cs0.idx("test")
    groups, dies = cs0.group[te], cs0.dies
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S = cs0.flat_sensors
    m = len(S)
    z_max = fault.threshold(ALPHA, m)
    r_avg = rmse(cs0, te, np.broadcast_to(cs0.T[tr].mean(0).ravel(), (len(te), gf.n)))
    res = {"case_set_sha256": cs0.sha256(), "profile": PROFILE, "chips": list(CHIPS), "z_max": z_max,
           "n_test_cases": int(len(te)), "runs": {}}
    for chip in CHIPS:
        cs = readings.with_sensor(cs0, PROFILE, chip)
        y, y_tr, noise = cs.readings[te].astype(np.float64), cs.readings[tr].astype(np.float64), float(cs.noise_K)
        chk, dropped = fault.repair(gf, S, y, noise, z_max)
        row = {"noise_K": noise,
               "healthy": {"unchecked": compare(rmse(cs, te, gf.posterior(S, y, noise).mean), r_avg, groups, dies),
                           "checked": compare(rmse(cs, te, chk), r_avg, groups, dies),
                           "dropped_cases": int((dropped >= 0).sum())},
               "sensors": {}}
        for i in range(m):
            keep = np.arange(m) != i
            s = {"die": str(dies[cs.sensors[i, 0]]),
                 "dead": compare(rmse(cs, te, gf.posterior(S[keep], y[:, keep], noise).mean), r_avg, groups, dies)}
            for name, f in UNKNOWN.items():
                bad = y.copy()
                bad[:, i] = f(y[:, i], y_tr[:, i])
                chk, dropped = fault.repair(gf, S, bad, noise, z_max)
                s[name] = {"unchecked": compare(rmse(cs, te, gf.posterior(S, bad, noise).mean), r_avg, groups, dies),
                           "checked": compare(rmse(cs, te, chk), r_avg, groups, dies),
                           "detected_cases": int((dropped == i).sum())}
            row["sensors"][str(i)] = s
        res["runs"][str(chip)] = row
        print("chip", chip, "done", flush=True)
    if inputs() != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    with open(os.path.join(out, "scores.json.tmp"), "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(os.path.join(out, "scores.json.tmp"), os.path.join(out, "scores.json"))


if __name__ == "__main__":
    main(sys.argv[1])
