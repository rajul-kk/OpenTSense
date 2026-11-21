"""G86 dry run (not a gated result): one failed sensor on G84's cases, ring-oscillator sensors (G102's profile).

For each dry chip (1-5) and each of the 16 sensors in turn, three failure modes against the healthy chip:
  dead    the sensor is known dead and left out (15 sensors)
  stuck   it reads ambient (zero rise) in every case, and the estimator is not told
  checked as stuck, with opentsense.estimate.fault.repair at the Bonferroni z for alpha = 0.01 over 16 sensors
Field model (G84's `field_model`: GaussianField, energy 0.9999, fitted once on the train split; the fit does not read
the readings). Test split. Per mode: mean group-median RMSE per die, and the group-bootstrap 95% interval of
(mode - average) RMSE (2,000 resamples, seed 0) as G102's bar (a); for `checked`, the share of test cases whose
stuck sensor was the one dropped; for the healthy chip, the share of cases with any sensor dropped (false alarms).

Usage (repo root): python gates/g86/dry/floor.py <G84 cases.npz> <out.json>
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g102")]
from opentsense.bench import metrics  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate import fault  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402
import readings  # noqa: E402

G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
PROFILE, CHIPS, ALPHA, N_BOOT = "ring_osc", (1, 2, 3, 4, 5), 0.01, 2000


def rmse(cs, te, mean):
    return metrics.per_case(cs.T[te], mean.reshape((len(te),) + cs.T.shape[1:]), float(cs.cell_um))["rmse_K"]


def compare(r, r_avg, groups, dies):
    return {str(d): {"mean_group_median_K": metrics.summary(r[:, i], groups)["mean_group_median"],
                     "vs_average_ci95": metrics.bootstrap_diff(r[:, i], r_avg[:, i], groups, N_BOOT)["ci95"]}
            for i, d in enumerate(dies)}


def main(cases, out):
    cs0 = CaseSet.load(cases)
    if cs0.sha256() != G84_SHA:
        raise SystemExit(f"case set {cs0.sha256()} is not G84's")
    tr, te = cs0.idx("train"), cs0.idx("test")
    groups, dies = cs0.group[te], cs0.dies
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S = cs0.flat_sensors
    m = len(S)
    z_max = fault.threshold(ALPHA, m)
    avg = np.broadcast_to(cs0.T[tr].mean(0).ravel(), (len(te), gf.n))
    r_avg = rmse(cs0, te, avg)
    res = {"case_set_sha256": cs0.sha256(), "profile": PROFILE, "z_max": z_max, "chips": {}}
    for chip in CHIPS:
        cs = readings.with_sensor(cs0, PROFILE, chip)
        y, noise = cs.readings[te].astype(np.float64), float(cs.noise_K)
        healthy_mean, healthy_drop = fault.repair(gf, S, y, noise, z_max)
        row = {"noise_K": noise,
               "healthy": compare(rmse(cs, te, gf.posterior(S, y, noise).mean), r_avg, groups, dies),
               "healthy_checked": compare(rmse(cs, te, healthy_mean), r_avg, groups, dies),
               "false_alarm_share": float((healthy_drop >= 0).mean()), "sensors": {}}
        for i in range(m):
            keep = np.arange(m) != i
            stuck = y.copy()
            stuck[:, i] = 0.0
            chk_mean, dropped = fault.repair(gf, S, stuck, noise, z_max)
            row["sensors"][str(i)] = {
                "die": str(dies[cs.sensors[i, 0]]),
                "dead": compare(rmse(cs, te, gf.posterior(S[keep], y[:, keep], noise).mean), r_avg, groups, dies),
                "stuck": compare(rmse(cs, te, gf.posterior(S, stuck, noise).mean), r_avg, groups, dies),
                "checked": compare(rmse(cs, te, chk_mean), r_avg, groups, dies),
                "detected_share": float((dropped == i).mean())}
        res["chips"][str(chip)] = row
        print("chip", chip, "false alarms", row["false_alarm_share"],
              "min detection", min(s["detected_share"] for s in row["sensors"].values()), flush=True)
    with open(out + ".tmp", "w") as f:
        json.dump(res, f, indent=1)
    os.replace(out + ".tmp", out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
