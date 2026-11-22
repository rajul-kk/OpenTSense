"""G105 dry run: spatially correlated sensor offsets (goal 17), on G84's case set and sites.

Per correlation setting (share of the offset variance in a smooth within-die field, its length; dies independent;
sensor.Correlation) and chip (PROFILE, CHIPS, bench.readings with salt SALT):
  rmse          field model (GaussianField(energy=0.9999) on the train fields, as bench's FieldModel) and average,
                test split, per die (mean over groups of the group median), uncalibrated and calibrated
  vs_average    bootstrap difference field model - average in RMSE, per die, uncalibrated and calibrated
  offset_err    RMS over sensors of (estimated - true) fixed error after the joint calibration on the cal split
                (estimate.fault.offsets), against the RMS of the true fixed error itself; the true fixed error of a
                sensor on the cal split is its drawn offset plus its gain error times (mean cal temperature - trim
                temperature), which calibration rightly absorbs too
  false_alarm   share of test cases in which the leave-one-out check (fault.repair, alpha ALPHA) drops a sensor,
                uncalibrated and calibrated
A smooth offset pattern the field model can explain as heat is expected to survive calibration (fault.offsets
drops it as unidentifiable); offset_err and the calibrated RMSE measure how much.

Usage (repo root): python gates/g105/dry/corr.py <G84 cases.npz> <out.json>
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from opentsense.bench import metrics, readings  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate import fault, sensor  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402

PROFILE, CHIPS, SALT, ALPHA, N_BOOT = "ring_osc", tuple(range(1, 21)), 105, 0.01, 2000
SETTINGS = {"indep": None, "s0.5_l0.5": (0.5, 0.5), "s0.5_l1.5": (0.5, 1.5), "s0.8_l3": (0.8, 3.0)}


def die_rmse(cs, te, mean):
    return metrics.per_case(cs.T[te], mean.reshape((len(te),) + cs.T.shape[1:]), float(cs.cell_um))["rmse_K"]


def summarise(r, r_avg, groups, dies):
    return {str(d): {"rmse_K": metrics.summary(r[:, i], groups)["mean_group_median"],
                     "vs_average_ci95": metrics.bootstrap_diff(r[:, i], r_avg[:, i], groups, N_BOOT)["ci95"]}
            for i, d in enumerate(dies)}


def main(cases, out):
    t0 = time.time()
    cs0 = CaseSet.load(cases)
    tr, ca, te = cs0.idx("train"), cs0.idx("cal"), cs0.idx("test")
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S = cs0.flat_sensors
    z_max = fault.threshold(ALPHA, len(S))
    groups = cs0.group[te]
    avg = np.broadcast_to(cs0.T[tr].mean(0), (len(te),) + cs0.T.shape[1:])
    r_avg = die_rmse(cs0, te, np.asarray(avg).reshape(len(te), -1))
    res = {"case_set_sha256": cs0.sha256(), "profile": PROFILE, "chips": list(CHIPS), "salt": SALT, "z_max": z_max,
           "settings": {k: v for k, v in SETTINGS.items()}, "runs": {}}
    for name, corr in SETTINGS.items():
        for chip in CHIPS:
            cs, drawn = readings.read_chip(cs0, PROFILE, chip, SALT, corr)
            noise = float(cs.noise_K)
            y_ca, y_te = cs.readings[ca].astype(np.float64), cs.readings[te].astype(np.float64)
            off = fault.offsets(gf, S, y_ca, noise)
            s = cs0.sensors
            T_cal = cs0.T[ca][:, s[:, 0], s[:, 1], s[:, 2]].astype(np.float64).mean(0) + readings.ambient_K(cs0)
            fixed = drawn.offset + drawn.gain * (T_cal - sensor.T_TRIM)
            row = {"offset_err_rms_K": float(np.sqrt(np.mean((off - fixed) ** 2))),
                   "offset_rms_K": float(np.sqrt(np.mean(fixed ** 2)))}
            for mode, y in (("uncal", y_te), ("cal", y_te - off)):
                r = die_rmse(cs0, te, gf.posterior(S, y, noise).mean)
                row[mode] = {"dies": summarise(r, r_avg, groups, cs0.dies),
                             "false_alarm": float((fault.repair(gf, S, y, noise, z_max)[1] >= 0).mean())}
            res["runs"][f"{name}/{chip}"] = row
            print(name, chip, round(row["offset_rms_K"], 3), round(row["offset_err_rms_K"], 3),
                  {m: ({d: round(v["rmse_K"], 3) for d, v in row[m]["dies"].items()}, row[m]["false_alarm"])
                   for m in ("uncal", "cal")}, flush=True)
    res["wall_s"] = round(time.time() - t0, 1)
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(out + ".tmp", out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
