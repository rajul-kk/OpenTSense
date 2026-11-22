"""G105 gated run: spatially correlated sensor offsets on G84's case set (registration.md).

Rebuilds G84's case set, checks its sha256, then for every setting and gated chip computes what `dry/corr.py`
computed (field model and average RMSE per die, uncalibrated and calibrated, their bootstrap difference, the offset
left after calibration, false alarms of the leave-one-out check), with N_BOOT resamples. It repeats the per-chip
computation of `dry/corr.py` (frozen as run, so not refactored) and takes its constants and helpers from there; only
the chips and the resample count differ.

Usage (repo root, host): python gates/g105/run.py <out dir>
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(HERE, "dry")]
from opentsense import manifest  # noqa: E402
from opentsense.bench import metrics, readings  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate import fault, sensor  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402
import corr  # noqa: E402

CHIPS, N_BOOT = tuple(range(21, 31)), 10000
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"


def inputs(cs):
    """sha256 of this gate's files, every opentsense module loaded and the stack config (the ambient)."""
    mods = {os.path.relpath(m.__file__, ROOT).replace(os.sep, "/") for m in list(sys.modules.values())
            if getattr(m, "__file__", None) and os.path.abspath(m.__file__).startswith(os.path.join(ROOT, "opentsense"))}
    files = sorted(mods | {"gates/g105/run.py", "gates/g105/evaluate.py", "gates/g105/registration.md",
                           "gates/g105/dry/corr.py", "gates/g84/make_cases.py",
                           os.path.relpath(os.path.join(readings.STACKS, f"{cs.stack_id}.yaml"), ROOT).replace(os.sep, "/")})
    return {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in files}


def write_json(obj, path):
    """Whole or not at all: a gated record is never re-run, so a cut-off write must not leave a partial file."""
    with open(path + ".tmp", "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(path + ".tmp", path)


def summarise(r, r_avg, groups, dies):
    """corr.summarise with the gate's N_BOOT (corr's is a constant of the frozen dry script)."""
    return {str(d): {"rmse_K": metrics.summary(r[:, i], groups)["mean_group_median"],
                     "vs_average_ci95": metrics.bootstrap_diff(r[:, i], r_avg[:, i], groups, N_BOOT)["ci95"]}
            for i, d in enumerate(dies)}


def main(out):
    os.makedirs(out, exist_ok=True)
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):                 # built under another name and renamed: never a cut-off file
        tmp = os.path.abspath(os.path.join(out, "cases.tmp.npz"))
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), tmp], check=True, cwd=ROOT)
        os.replace(tmp, cases)
        os.replace(tmp[:-4] + ".json", os.path.join(out, "cases.json"))     # make_cases' summary
    cs0 = CaseSet.load(cases)
    if cs0.sha256() != G84_SHA:                  # recorded, so evaluate.py writes the INCONCLUSIVE verdict
        write_json({"case_set_sha256": cs0.sha256(), "runs": {}}, os.path.join(out, "scores.json"))
        raise SystemExit(f"case set {cs0.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    hashes = inputs(cs0)
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G105", "inputs_sha256": hashes})
    tr, ca, te = cs0.idx("train"), cs0.idx("cal"), cs0.idx("test")
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    S, groups, s = cs0.flat_sensors, cs0.group[te], cs0.sensors
    z_max = fault.threshold(corr.ALPHA, len(S))
    avg = np.broadcast_to(cs0.T[tr].mean(0), (len(te),) + cs0.T.shape[1:])
    r_avg = corr.die_rmse(cs0, te, np.asarray(avg).reshape(len(te), -1))
    T_cal = cs0.T[ca][:, s[:, 0], s[:, 1], s[:, 2]].astype(np.float64).mean(0) + readings.ambient_K(cs0)
    res = {"case_set_sha256": cs0.sha256(), "profile": corr.PROFILE, "chips": list(CHIPS), "salt": corr.SALT,
           "z_max": z_max, "n_boot": N_BOOT, "settings": dict(corr.SETTINGS), "runs": {}}
    for name, setting in corr.SETTINGS.items():
        for chip in CHIPS:
            cs, drawn = readings.read_chip(cs0, corr.PROFILE, chip, corr.SALT, setting)
            noise = float(cs.noise_K)
            y_ca, y_te = cs.readings[ca].astype(np.float64), cs.readings[te].astype(np.float64)
            off = fault.offsets(gf, S, y_ca, noise)
            fixed = drawn.offset + drawn.gain * (T_cal - sensor.T_TRIM)
            row = {"offset_err_rms_K": float(np.sqrt(np.mean((off - fixed) ** 2))),
                   "offset_rms_K": float(np.sqrt(np.mean(fixed ** 2)))}
            for mode, y in (("uncal", y_te), ("cal", y_te - off)):
                r = corr.die_rmse(cs0, te, gf.posterior(S, y, noise).mean)
                row[mode] = {"dies": summarise(r, r_avg, groups, cs0.dies),
                             "false_alarm": float((fault.repair(gf, S, y, noise, z_max)[1] >= 0).mean())}
            res["runs"][f"{name}/{chip}"] = row
        print(name, "done", flush=True)
    if inputs(cs0) != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    write_json(res, os.path.join(out, "scores.json"))


if __name__ == "__main__":
    main(sys.argv[1])
