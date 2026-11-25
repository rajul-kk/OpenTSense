"""Shared G108 scorer. The dry CLI accepts only chip 1 or chips 1-5."""
import argparse
import json
import os
import sys
import time
from math import isfinite
from pathlib import Path

import numpy as np
import psutil
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "gates/g107/dry"), str(ROOT / "gates/g104/dry")]
import budget as g107
import sites as g104

from opentsense import manifest
from opentsense.bench import readings
from opentsense.bench.cases import CaseSet
from opentsense.bench.estimators import FieldModel
from opentsense.bench.score import score
from opentsense.estimate import placement

CASES = "gates/g84/dry/cases.npz"
CONTROL = "gates/g107/dry/budget.json"
STACK = "g71_3d"
ARMS = {f"bot{count}/{label}": count for count in (2, 8)
        for label in ("uniform", "outside_uniform", "greedy_a", "outside_greedy_a")}
METRICS = ("average/rmse_K", "average/peak_err_K", "field_model/rmse_K", "field_model/peak_err_K")
BOOTSTRAP = "field_minus_average_rmse_K"
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
CONTRASTS = {
    "outside_uniform_2_vs_8": ("bot2/outside_uniform", "bot8/outside_uniform"),
    "outside_greedy_2_vs_8": ("bot2/outside_greedy_a", "bot8/outside_greedy_a"),
    "original_uniform_2_vs_8": ("bot2/uniform", g107.REF),
    "outside_2_vs_original_8_uniform": ("bot2/outside_uniform", g107.REF),
    "uniform_keepout_2": ("bot2/outside_uniform", "bot2/uniform"),
    "uniform_keepout_8": ("bot8/outside_uniform", g107.REF),
    "greedy_keepout_2": ("bot2/outside_greedy_a", "bot2/greedy_a"),
    "greedy_keepout_8": ("bot8/outside_greedy_a", "bot8/greedy_a"),
}


def layouts(cases):
    original, noise, field, buried = g107.site_sets(cases)
    dim = cases.T.shape[1:]
    outside = g104.allowed_outside(dim[1:])
    top = original[g107.REF][original[g107.REF][:, 0] != buried]
    start = np.ravel_multi_index(top.T, dim)
    buried_only = np.zeros(dim, dtype=bool)
    buried_only[buried] = True
    greedy = {}
    for label, mask in (("greedy_a", buried_only), ("outside_greedy_a", buried_only & outside)):
        flat = placement.greedy_a(field, len(top) + 8, noise, mask.ravel(), start=start)
        greedy[label] = np.column_stack(np.unravel_index(flat, dim))

    arms = {}
    for count in (2, 8):
        prefix = f"bot{count}"
        grid = g104.grid_in(dim[1:], count, outside)
        outside_sites = np.column_stack((np.full(count, buried), *np.unravel_index(grid, dim[1:])))
        arms[f"{prefix}/uniform"] = original[f"{prefix}/uniform"]
        arms[f"{prefix}/outside_uniform"] = np.concatenate((top, outside_sites))
        for label, sites in greedy.items():
            arms[f"{prefix}/{label}"] = sites[:len(top) + count]
        for label in ("uniform", "outside_uniform", *greedy):
            arm = arms[f"{prefix}/{label}"]
            buried_sites = arm[arm[:, 0] == buried]
            if (len(buried_sites) != count or len(np.unique(arm, axis=0)) != len(top) + count
                    or not np.array_equal(arm[arm[:, 0] != buried], top)):
                raise ValueError(f"wrong sites or counts in {prefix}/{label}")
            if label.startswith("outside_") and not outside[tuple(buried_sites[:, 1:].T)].all():
                raise ValueError(f"keep-out intrusion in {prefix}/{label}")

    control = json.loads((ROOT / CONTROL).read_text(encoding="utf-8"))
    if (buried != control["buried_die"] or abs(noise - control["placement_noise_K"]) > 1e-9
            or {name: sites.tolist() for name, sites in original.items()} != control["sites"]
            or not np.array_equal(arms["bot2/greedy_a"], original["bot2/greedy_a"])):
        raise ValueError("could not reproduce G107's placement control")

    union = list(dict.fromkeys(tuple(site) for sites in (*original.values(), *arms.values()) for site in sites))
    excluded = np.argwhere(~outside)
    return {
        "buried_die": int(buried), "top_sites": top.tolist(), "placement_noise_K": noise,
        "keep_cells": g104.KEEP, "eligible_buried_cells": int(outside.sum()),
        "excluded_buried_bounds_inclusive": [excluded.min(axis=0).tolist(), excluded.max(axis=0).tolist()],
        "sites": {name: sites.tolist() for name, sites in arms.items()}, "union": np.asarray(union).tolist(),
        "buried_sites_in_keepout": {
            name: int((~outside[tuple(sites[sites[:, 0] == buried, 1:].T)]).sum())
            for name, sites in arms.items()
        },
    }, field


def score_chip(template, cols, field, chip, corr):
    full = readings.with_sensor(template, g107.PROFILE, chip, g107.SALT, corr)
    scores = {}
    for name, indices in cols.items():
        subset = readings.subset(full, indices, g107.PROFILE)
        result, _ = score(subset, ["average", "field_model"], estimators={"field_model": FieldModel(gf=field)})
        fits = result["estimators"]
        scores[name] = {
            f"{estimator}/{metric}": {
                str(die): fits[estimator]["summary"][str(die)]["all"][metric]["mean_group_median"]
                for die in template.dies
            }
            for estimator in ("average", "field_model") for metric in ("rmse_K", "peak_err_K")
        }
        scores[name]["field_minus_average_rmse_K"] = {
            str(die): result["comparisons"]["field_model - average"][str(die)]["rmse_K"] for die in template.dies
        }
    return scores


def summarise(units, chips, dies):
    summary = {}
    for offset in g107.CORR:
        scores = [units[f"{offset}/{chip}"] for chip in chips]
        summary[offset] = {}
        for die in dies:
            by_arm = {
                arm: np.array([item[arm]["field_model/rmse_K"][die] for item in scores]) for arm in scores[0]
            }
            deltas = {name: by_arm[left] - by_arm[right] for name, (left, right) in CONTRASTS.items()}
            summary[offset][die] = {
                "mean_rmse_K": {arm: float(values.mean()) for arm, values in by_arm.items()},
                "paired_rmse_K": {
                    name: {"chip_deltas": values.tolist(), "mean": float(values.mean()),
                           "se": float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else None}
                    for name, values in deltas.items()
                },
            }
    return summary


def write_record(out, record, hashes):
    """Atomic write, only while every input still hashes as at the start (boundary rehashing: a change made and
    undone between two writes is not seen; the run does not snapshot its inputs)."""
    if any(manifest.file_sha256(ROOT / path) != sha for path, sha in hashes.items()):
        raise ValueError("G108 inputs changed during scoring")
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(out)


def input_hashes(extra_inputs=()):
    files = set(g107.INPUTS + g104.INPUTS) | {
        CASES, CONTROL, "gates/g84/make_cases.py", Path(__file__).resolve().relative_to(ROOT).as_posix(),
        "opentsense/manifest.py", "opentsense/estimate/sensor_circuit.py", "opentsense/estimate/regularise.py",
        f"configs/stacks/{STACK}.yaml",
    }
    return {path: manifest.file_sha256(ROOT / path) for path in sorted(files | set(extra_inputs))}


def registered_key(chips):
    return {"case_set_sha256": G84_SHA, "profile": g107.PROFILE, "salt": g107.SALT, "chips": list(chips),
            "offsets": {name: list(corr) if corr else None for name, corr in g107.CORR.items()}}


def unit_names(chips):
    return {f"{offset}/{chip}" for offset in g107.CORR for chip in chips}


def finite(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def valid_bootstrap(item):
    if not isinstance(item, dict) or not all(finite(item.get(k)) for k in ("diff", "p")):
        return False
    ci = item.get("ci95")
    return (isinstance(ci, list) and len(ci) == 2 and all(map(finite, ci)) and ci[0] <= ci[1]
            and 0 <= item["p"] <= 1
            and all(type(item.get(k)) is int for k in ("groups", "n_boot", "seed"))
            and item["groups"] > 0 and item["n_boot"] > 0)


def valid_unit(unit, dies):
    if not isinstance(unit, dict) or set(unit) != set(ARMS):
        return False
    for arm in unit.values():
        if not isinstance(arm, dict) or set(arm) != {*METRICS, BOOTSTRAP}:
            return False
        if any(not isinstance(values, dict) or set(values) != set(dies) for values in arm.values()):
            return False
        if any(not finite(v) or v < 0 for metric in METRICS for v in arm[metric].values()):
            return False
        if not all(map(valid_bootstrap, arm[BOOTSTRAP].values())):
            return False
    return True


def run(chips, out, *, reference=None, extra_inputs=(), pinned_inputs=None):
    start = time.perf_counter()
    hashes = input_hashes(extra_inputs)
    if pinned_inputs is not None and any(hashes.get(path) != sha for path, sha in pinned_inputs.items()):
        raise ValueError("G108 inputs differ from the registered dry inputs")
    cases = CaseSet.load(ROOT / CASES)
    if cases.sha256() != G84_SHA:
        raise ValueError("G84 case-set fingerprint mismatch")
    key = {
        **registered_key(chips), "inputs_sha256": hashes,
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                    "openblas_threads": os.environ.get("OPENBLAS_NUM_THREADS")},
    }
    old = {}
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        if not isinstance(old, dict) or old.get("complete") is not False or old.get("key") != key:
            raise ValueError(f"will not overwrite completed or mismatched record {out}")
    placed, field = layouts(cases)
    if old and old.get("placement") != placed:
        raise ValueError("resumed placement differs from the existing record")
    if reference is not None and placed != reference:
        raise ValueError("placement differs from the dry reference")
    indices = {tuple(site): index for index, site in enumerate(placed["union"])}
    cols = {name: [indices[tuple(site)] for site in sites] for name, sites in placed["sites"].items()}
    template = readings.with_sites(cases, placed["union"])
    units = old.get("units", {})
    seconds = old.get("unit_wall_s", {})
    dies = cases.dies.tolist()
    if (not isinstance(units, dict) or not isinstance(seconds, dict) or set(units) != set(seconds)
            or not set(units) <= unit_names(chips) or any(not valid_unit(unit, dies) for unit in units.values())
            or any(not finite(t) or t < 0 for t in seconds.values())):
        raise ValueError("checkpoint has an unexpected or invalid unit")
    record = {"key": key, "placement": placed, "dies": dies, "stack": str(cases.stack_id),
              "cell_um": float(cases.cell_um), "shape": list(cases.T.shape),
              "split_counts": {split: len(cases.idx(split)) for split in ("train", "cal", "test")},
              "setup_s": time.perf_counter() - start, "units": units, "unit_wall_s": seconds, "complete": False}
    if reference is not None:
        write_record(out.parent / "manifest.json", {"gate": "G108", "key": key}, hashes)
    write_record(out, record, hashes)
    for offset, corr in g107.CORR.items():
        for chip in chips:
            unit = f"{offset}/{chip}"
            if unit in units:
                continue
            print(f"Scoring {unit}", flush=True)
            unit_start = time.perf_counter()
            units[unit] = score_chip(template, cols, field, chip, corr)
            seconds[unit] = time.perf_counter() - unit_start
            if not valid_unit(units[unit], dies):
                raise ValueError(f"{unit} has invalid scores")
            write_record(out, record, hashes)
    record.update(summary=summarise(units, chips, record["dies"]), wall_s=time.perf_counter() - start,
                  peak_working_set_bytes=psutil.Process().memory_info().peak_wset,
                  inputs_unchanged=True, complete=True)
    write_record(out, record, hashes)
    print(f"Completed {len(units)} paired units: {out.name}", flush=True)
    # the launcher's budget check reads this line: sampled after the last write, unlike the record's own peak
    print(f"final_peak_working_set_bytes={psutil.Process().memory_info().peak_wset}", flush=True)


def run_locked(chips, out, **kwargs):
    lock = out.with_suffix(".lock")
    try:
        lock.mkdir()                             # atomic: one process per record, checkpoints included
    except FileExistsError:
        sys.exit(f"{lock.name} exists: another run is writing {out.name} (or one died: check, then remove it)")
    try:
        run(chips, out, **kwargs)
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=["slice", "full"])
    parser.add_argument("--out", type=Path, help="separate dry record for a verification run")
    args = parser.parse_args()
    chips, default = (g107.CHIPS[:1], "slice.json") if args.scope == "slice" else (g107.CHIPS, "keepout.json")
    run_locked(chips, args.out or HERE / default)


if __name__ == "__main__":
    main()
