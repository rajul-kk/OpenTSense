"""G107 dry run: how few sensors the buried die needs (goal 21, item 3), on G84's case set (G71 stack: TPU die on
top, CPU die buried under it).

The top die keeps G84's 8 uniform sites in every set; only the buried die's budget changes. Site sets, chosen from
the train split only:
  bot<m>/uniform   m in 8, 4, 2, 1, 0 sites on the buried die: 8 is G84's own set (the reference); 4, 2 and 1 are
                   placement.uniform_grid(shape, m); 0 has no sensor on the buried die (protocol section 1.1's
                   case set), so that die is estimated from the top die's sensors alone
  bot<m>/greedy_a  m in 4, 2, 1: A-optimal greedy on the field model, the buried die's sites placed given the top
                   die's 8
  joint<n>/greedy_a  n in 12, 16 sites anywhere on either die, A-optimal greedy, no per-die budget: reported, to see
                   how many the field model itself would put on the buried die
Placement noise: the sensor profile's datasheet total over the train temperatures of every cell (as G104's "all").
Readings: profile PROFILE, chips CHIPS (bench.readings with salt SALT), independent offsets and G105's strongest
correlated setting (CORR). Scored: average and field_model on the test split (bench.score; the field model is fitted
once on the train fields). Per offset model, set and chip: RMSE and peak error per die, the field model's bootstrap
difference from the average, and its paired difference from bot8/uniform. The average ignores the readings, so it is
the same for every set; with no buried sensor it is the floor the field model must still beat on that die.
Each chip is read once at the union of every set's sites, and each set takes its sensors from that read
(bench.readings.subset): one chip, some sensors not read out, so two sets differ only in which sites they read (a
read per set, as the first dry run `dry/budget_v1.json` did, redraws every sensor's error).
The output records the sha256 of every input, is rewritten after each chip, and a rerun with the same inputs and the
same placed sites skips the chips already done.

Usage (repo root): python gates/g107/dry/budget.py <G84 cases.npz> <out.json>
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

PROFILE, CHIPS, SALT = "ring_osc", (1, 2, 3, 4, 5), 107
BUDGETS, GREEDY, JOINT = (8, 4, 2, 1, 0), (4, 2, 1), (12, 16)
REF = "bot8/uniform"
CORR = {"indep": None, "corr0.8_3mm": (0.8, 3.0)}
INPUTS = ["gates/g107/dry/budget.py", "opentsense/estimate/placement.py", "opentsense/estimate/sensor.py",
          "opentsense/estimate/field_model.py", "opentsense/bench/readings.py", "opentsense/bench/score.py",
          "opentsense/bench/estimators.py", "opentsense/bench/metrics.py", "opentsense/bench/cases.py",
          "opentsense/stack/model.py"]          # + the case set's stack config (ambient)


def site_sets(cs):
    """{name: (m, 3) sites (die, row, col)}, the field model fitted on the train fields, and the placement noise."""
    D, ny, nx = cs.T.shape[1:]
    bur = [i for i, b in enumerate(cs.a["buried"]) if b]
    if len(bur) != 1 or D != 2:
        raise ValueError(f"expected two dies, one buried; got {D} dies, buried {bur}")
    b = bur[0]
    S = np.asarray(cs.sensors)
    top, bot = S[S[:, 0] != b], S[S[:, 0] == b]
    if len(top) != 8 or len(bot) != 8:
        raise ValueError(f"G84's sites should be 8 per die, got {len(top)} and {len(bot)}")
    sets = {REF: np.concatenate([top, bot]), "bot0/uniform": top}
    for m in BUDGETS[1:-1]:
        pts = placement.uniform_grid((ny, nx), m)
        if len(pts) != m:
            raise ValueError(f"uniform_grid gave {len(pts)} sites for {m}")
        sets[f"bot{m}/uniform"] = np.concatenate([top, [(b, *divmod(int(p), nx)) for p in pts]])
    tr = cs.idx("train")
    gf = GaussianField(energy=FieldModel().energy).fit(cs.T[tr].reshape(len(tr), -1))
    noise = sensor.PROFILES[PROFILE].total_sigma(cs.T[tr].astype(np.float64) + readings.ambient_K(cs))
    flat_top = list(np.ravel_multi_index(tuple(top.T), (D, ny, nx)))
    on_bot = np.zeros((D, ny, nx), bool)
    on_bot[b] = True
    for m in GREEDY:
        chosen = placement.greedy_a(gf, len(top) + m, noise, on_bot.ravel(), start=flat_top)
        sets[f"bot{m}/greedy_a"] = np.array([np.unravel_index(int(s), (D, ny, nx)) for s in chosen])
    for n in JOINT:
        chosen = placement.greedy_a(gf, n, noise)
        sets[f"joint{n}/greedy_a"] = np.array([np.unravel_index(int(s), (D, ny, nx)) for s in chosen])
    return sets, noise, gf, b


def _write(res, out):
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(out + ".tmp", out)


def main(cases, out, chips=CHIPS, extra_inputs=(), expect=None):
    """Score `chips` into `out`. extra_inputs: more repo files to hash (the gated run's own); expect: a placed record
    (placement_noise_K, buried_die, sites) the placed sites must equal before anything is scored (the dry run's)."""
    t0 = time.time()
    cs = CaseSet.load(cases)
    inputs = INPUTS + list(extra_inputs) + [
        os.path.relpath(os.path.join(readings.STACKS, f"{cs.stack_id}.yaml"), ROOT).replace(os.sep, "/")]
    key = {"case_set_sha256": cs.sha256(), "profile": PROFILE, "chips": list(chips), "salt": SALT,
           "offsets": dict(CORR), "inputs_sha256": {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in inputs}}
    old = json.load(open(out)) if os.path.exists(out) else {}
    if old and {k: old.get(k) for k in key} != json.loads(json.dumps(key)):
        raise SystemExit(f"{out} was made from other inputs; move it aside to start again")
    sets, noise, gf, b = site_sets(cs)
    union = list(dict.fromkeys(tuple(int(x) for x in s) for S in sets.values() for s in S))
    cols = {k: [union.index(tuple(int(x) for x in s)) for s in S] for k, S in sets.items()}
    placed = json.loads(json.dumps(
        {"placement_noise_K": noise, "buried_die": int(b), "sites": {k: v.tolist() for k, v in sets.items()}}))
    for ref, what in ((old, "this run's earlier chips"), (expect, "the dry run")):
        if ref and ({k: ref[k] for k in placed} != placed):
            raise SystemExit(f"{out}: the placed sites differ from {what}; nothing scored")
    res = {**key, **placed,
           "per_die_count": {k: np.bincount(v[:, 0], minlength=len(cs.dies)).tolist() for k, v in sets.items()},
           "setup_s": round(time.time() - t0, 1), "runs": old.get("runs", {}), "wall_s": old.get("wall_s", 0.0)}
    groups = cs.group[cs.idx("test")]
    for oname, corr in CORR.items():
        for chip in chips:
            if all(f"{oname}/{name}/{chip}" in res["runs"] for name in sets):
                continue
            t1 = time.time()
            per = {}
            full = readings.with_sensor(readings.with_sites(cs, union), PROFILE, chip, SALT, corr)
            for name in sets:
                r, p = score(readings.subset(full, cols[name], PROFILE),
                             ["average", "field_model"], estimators={"field_model": FieldModel(gf=gf)})
                per[name] = p["field_model"]["rmse_K"]
                summ = r["estimators"]["field_model"]["summary"]
                avg = r["estimators"]["average"]["summary"]
                res["runs"][f"{oname}/{name}/{chip}"] = {
                    "rmse_K": {str(d): summ[str(d)]["all"]["rmse_K"]["mean_group_median"] for d in cs.dies},
                    "average_rmse_K": {str(d): avg[str(d)]["all"]["rmse_K"]["mean_group_median"] for d in cs.dies},
                    "peak_err_K": {str(d): summ[str(d)]["all"]["peak_err_K"]["mean_group_median"] for d in cs.dies},
                    "average_peak_err_K": {str(d): avg[str(d)]["all"]["peak_err_K"]["mean_group_median"]
                                           for d in cs.dies},
                    "vs_average": {str(d): r["comparisons"]["field_model - average"][str(d)]["rmse_K"] for d in cs.dies}}
            for name in sets:
                if name != REF:
                    res["runs"][f"{oname}/{name}/{chip}"]["vs_ref"] = {
                        str(d): metrics.bootstrap_diff(per[name][:, i], per[REF][:, i], groups)
                        for i, d in enumerate(cs.dies)}
            res["wall_s"] = round(res["wall_s"] + time.time() - t1, 1)
            _write(res, out)
            print(oname, "chip", chip, {k: res["runs"][f"{oname}/{k}/{chip}"]["rmse_K"] for k in sets}, flush=True)
    res["inputs_unchanged"] = all(manifest.file_sha256(os.path.join(ROOT, k)) == v
                                  for k, v in key["inputs_sha256"].items())
    res["complete"] = True                       # the end marker a reader requires: every chip scored, inputs checked
    _write(res, out)
    print("done in", round(time.time() - t0, 1), "s this run; inputs unchanged:", res["inputs_unchanged"], flush=True)
    return res


if __name__ == "__main__":
    main(*sys.argv[1:3])
