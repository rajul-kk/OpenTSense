"""G104 dry run: sensors only outside the dense logic (goal 16), on G84's case set (G71 stack, 3 x 3 mm dies, the
1 mm active block of each die at cells 20-39; `gates/g71/inputs/maps.npz` act3).

Site sets, M_PER_DIE sensors on each die, chosen from the train split only:
  all/uniform       G84's sites (uniform grid on every cell), the reference
  outside/uniform   the first M_PER_DIE points outside the block and a KEEP-cell ring around it of
                    placement.uniform_grid(k) for the smallest k that has that many (row order, so a grid that does
                    not fill its last row loses points at the bottom right; here k = 9, the 3 x 3 grid minus its centre)
  all/greedy_a      A-optimal greedy on the field model of the train fields, die by die (each die's sites placed
                    given the dies before it)
  outside/greedy_a  the same, restricted to cells outside the block and the ring
Placement noise: the sensor profile's datasheet total over the train temperatures of the cells a set may use.
Readings: profile PROFILE, chips CHIPS (bench.readings with salt SALT), with independent offsets and with the
correlated offsets of G105's strongest setting (CORR), to see whether a placement chosen for independent noise holds up
when offsets are shared. Scored: average and field_model on the test split (bench.score; the field model is fitted
once on the train fields and reused, since its fit does not read the sensors). Per offset model, site set and chip:
field_model and average RMSE per die (whole die), the field model's peak error, its bootstrap difference from the
average, and its paired difference from all/uniform. The output records the sha256 of every input file; it is
rewritten after each chip (setup_s: load, fit and placement of the last run; wall_s: scoring time summed over runs),
and a rerun with the same inputs (and the same placed sites) skips the chips already done.

Usage (repo root): python gates/g104/dry/sites.py <G84 cases.npz> <out.json>
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.bench import metrics, readings  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.bench.estimators import FieldModel  # noqa: E402
from opentsense.bench.score import score  # noqa: E402
from opentsense.estimate import placement, sensor  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402

PROFILE, CHIPS, SALT, KEEP, M_PER_DIE = "ring_osc", (1, 2, 3, 4, 5), 104, 2, 8
CORR = {"indep": None, "corr0.8_3mm": (0.8, 3.0)}
MAPS = os.path.join(ROOT, "gates", "g71", "inputs", "maps.npz")
INPUTS = ["gates/g104/dry/sites.py", "opentsense/estimate/placement.py", "opentsense/estimate/sensor.py",
          "opentsense/estimate/field_model.py", "opentsense/bench/readings.py", "opentsense/bench/score.py",
          "opentsense/bench/estimators.py", "opentsense/bench/metrics.py", "opentsense/bench/cases.py",
          "opentsense/stack/model.py", "gates/g71/inputs/maps.npz"]          # + the case set's stack config (ambient)


def allowed_outside(shape, keep=KEEP):
    """(ny, nx) mask: cells outside G71's active block grown by `keep` cells."""
    act = np.load(MAPS)["act3"].astype(bool)
    if act.shape != tuple(shape):
        raise ValueError(f"act3 is {act.shape}, the case set's dies are {shape}")
    (r0, c0), (r1, c1) = np.argwhere(act).min(0), np.argwhere(act).max(0) + 1
    out = np.ones(shape, bool)
    out[max(r0 - keep, 0):r1 + keep, max(c0 - keep, 0):c1 + keep] = False
    return out


def grid_in(shape, m, mask):
    """The first m points inside mask of placement.uniform_grid(k), for the smallest k that has m there."""
    for k in range(m, 4 * m):
        pts = placement.uniform_grid(shape, k)
        pts = pts[mask.ravel()[pts]]
        if len(pts) >= m:
            return pts[:m]
    raise ValueError(f"no regular grid of up to {4 * m} points has {m} inside the mask")


def site_sets(cs):
    D, ny, nx = cs.T.shape[1:]
    masks = {"all": np.ones((ny, nx), bool), "outside": allowed_outside((ny, nx))}
    sets = {f"{n}/uniform": np.array([(d, *divmod(int(s), nx)) for d in range(D) for s in grid_in((ny, nx), M_PER_DIE, m)])
            for n, m in masks.items()}
    if not np.array_equal(sets["all/uniform"], cs.sensors):            # cheap check before the model fit
        raise ValueError("all/uniform does not reproduce G84's sites")
    tr = cs.idx("train")
    T_abs = cs.T[tr].astype(np.float64) + readings.ambient_K(cs)
    gf = GaussianField(energy=FieldModel().energy).fit(cs.T[tr].reshape(len(tr), -1))
    noise = {}
    for name, mask in masks.items():
        noise[name] = sensor.PROFILES[PROFILE].total_sigma(T_abs[:, :, mask])
        chosen = []
        for d in range(D):
            die_mask = np.zeros((D, ny, nx), bool)
            die_mask[d] = mask
            chosen = placement.greedy_a(gf, (d + 1) * M_PER_DIE, noise[name], die_mask.ravel(), start=chosen)
        sets[f"{name}/greedy_a"] = np.array([np.unravel_index(int(s), (D, ny, nx)) for s in chosen])
    return sets, noise, gf


def _write(res, out):
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(out + ".tmp", out)


def main(cases, out):
    t0 = time.time()
    cs = CaseSet.load(cases)
    inputs = INPUTS + [os.path.relpath(os.path.join(readings.STACKS, f"{cs.stack_id}.yaml"), ROOT).replace(os.sep, "/")]
    key = {"case_set_sha256": cs.sha256(), "profile": PROFILE, "chips": list(CHIPS), "salt": SALT, "keep_cells": KEEP,
           "offsets": {k: v for k, v in CORR.items()},
           "inputs_sha256": {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in inputs}}
    old = json.load(open(out)) if os.path.exists(out) else {}
    if old and {k: old.get(k) for k in key} != json.loads(json.dumps(key)):
        raise SystemExit(f"{out} was made from other inputs; move it aside to start again")
    sets, noise, gf = site_sets(cs)
    placed = {"placement_noise_K": noise, "sites": {k: v.tolist() for k, v in sets.items()}}
    if old and {k: old[k] for k in placed} != json.loads(json.dumps(placed)):
        raise SystemExit(f"{out}: this machine places different sites from the same inputs; move it aside")
    res = {**key, **placed,
           "per_die_count": {k: np.bincount(v[:, 0], minlength=len(cs.dies)).tolist() for k, v in sets.items()},
           "setup_s": round(time.time() - t0, 1), "runs": old.get("runs", {}), "wall_s": old.get("wall_s", 0.0)}
    groups = cs.group[cs.idx("test")]
    for oname, corr in CORR.items():
        for chip in CHIPS:
            if all(f"{oname}/{name}/{chip}" in res["runs"] for name in sets):
                continue
            t1 = time.time()
            per = {}
            for name, S in sets.items():
                r, p = score(readings.with_sensor(readings.with_sites(cs, S), PROFILE, chip, SALT, corr),
                             ["average", "field_model"], estimators={"field_model": FieldModel(gf=gf)})
                per[name] = p["field_model"]["rmse_K"]
                summ = r["estimators"]["field_model"]["summary"]
                avg = r["estimators"]["average"]["summary"]
                res["runs"][f"{oname}/{name}/{chip}"] = {
                    "rmse_K": {str(d): summ[str(d)]["all"]["rmse_K"]["mean_group_median"] for d in cs.dies},
                    "average_rmse_K": {str(d): avg[str(d)]["all"]["rmse_K"]["mean_group_median"] for d in cs.dies},
                    "peak_err_K": {str(d): summ[str(d)]["all"]["peak_err_K"]["mean_group_median"] for d in cs.dies},
                    "vs_average": {str(d): r["comparisons"]["field_model - average"][str(d)]["rmse_K"] for d in cs.dies}}
            for name in sets:
                if name != "all/uniform":
                    res["runs"][f"{oname}/{name}/{chip}"]["vs_all_uniform"] = {
                        str(d): metrics.bootstrap_diff(per[name][:, i], per["all/uniform"][:, i], groups)
                        for i, d in enumerate(cs.dies)}
            res["wall_s"] = round(res["wall_s"] + time.time() - t1, 1)
            _write(res, out)
            print(oname, "chip", chip, {k: res["runs"][f"{oname}/{k}/{chip}"]["rmse_K"] for k in sets}, flush=True)
    print("done in", round(time.time() - t0, 1), "s this run", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
