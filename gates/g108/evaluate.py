"""Evaluate one G108 run directory against registration.md and write result.json."""
import argparse
import hashlib
import json
import re
import sys
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gates.g108.dry import keepout
from gates.g108.run import (
    CHIPS,
    RUN_INPUTS,
    dry_input_pins,
    dry_reference,
)

TOL_K = 0.25
PRIMARY = ("bot2/outside_uniform", "bot8/outside_uniform")
BARS = {"a": "indep", "b": "corr0.8_3mm"}
EVALUATOR_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def read_object(data):
    try:
        item = json.loads(data)
    except ValueError:
        return None
    return item if isinstance(item, dict) else None


def read_bytes(path):
    try:
        return path.read_bytes()
    except OSError:
        return b""


def successful_log(run, digest):
    for path in sorted(run.glob("launch.*.log")):
        lines = read_bytes(path).decode("utf-8", errors="replace").splitlines()
        if (len(lines) >= 2 and lines[-2] == f"scores_sha256={digest}"
                and re.fullmatch(r"rc=0 slot=[0-9a-f]{8} release_rc=0", lines[-1])
                and not any(line.startswith("launcher error:") for line in lines)):
            return path.name
    return None


def site_checks(placed, dry):
    expected = dry["placement"]
    sites = placed.get("sites")
    shape = dry["shape"][1:]
    buried = expected["buried_die"]
    top, counts, eligible, grid = (False,) * 4
    if isinstance(sites, dict) and set(sites) == set(keepout.ARMS):
        grid = all(isinstance(arm, list) and all(
            isinstance(site, list) and len(site) == len(shape) and all(
                type(i) is int and 0 <= i < n for i, n in zip(site, shape, strict=True)
            ) for site in arm) for arm in sites.values())
        if grid:
            bottom = {arm: [tuple(site[1:]) for site in coords if site[0] == buried] for arm, coords in sites.items()}
            top = all([s for s in coords if s[0] != buried] == expected["top_sites"] for coords in sites.values())
            counts = all(len(bottom[arm]) == len(set(bottom[arm])) == n for arm, n in keepout.ARMS.items())
            try:
                outside = keepout.g104.allowed_outside(shape[1:])
            except (OSError, ValueError, KeyError, BadZipFile):
                pass
            else:
                eligible = all(all(outside[cell] for cell in cells) for arm, cells in bottom.items()
                               if arm.split("/", 1)[1].startswith("outside_"))
    return {"sites_as_dry": placed == expected, "site_grid": grid, "fixed_top_sites": top,
            "buried_counts": counts, "outside_eligible": eligible}


def input_check(key, dry):
    try:
        actual = keepout.input_hashes(RUN_INPUTS)
    except OSError:
        return False
    return key.get("inputs_sha256") == actual and all(
        actual.get(name) == sha for name, sha in dry_input_pins(dry).items())


def checks(scores, dry, manifest, log):
    key = scores.get("key")
    key = key if isinstance(key, dict) else {}
    flags = {name: key.get(name) == value for name, value in keepout.registered_key(CHIPS).items()}
    placed = scores.get("placement")
    metadata = ("dies", "stack", "shape", "cell_um", "split_counts")
    units = scores.get("units")
    all_units = isinstance(units, dict) and set(units) == keepout.unit_names(CHIPS)
    flags.update(complete=scores.get("complete") is True, inputs_unchanged=scores.get("inputs_unchanged") is True,
                 inputs_sha256=input_check(key, dry), runtime=key.get("runtime") == dry["key"]["runtime"],
                 manifest=manifest == {"gate": "G108", "key": key},
                 launcher=log is not None, case_metadata=all(scores.get(n) == dry[n] for n in metadata),
                 all_units=all_units, finite_metrics=all_units and all(
                     keepout.valid_unit(unit, dry["dies"]) for unit in units.values()))
    flags.update(site_checks(placed if isinstance(placed, dict) else {}, dry))
    return flags


def report(units, dies):
    results = {}
    for offset in BARS.values():
        results[offset] = {}
        for die in dies:
            arms = {}
            for arm in keepout.ARMS:
                scores = {str(chip): units[f"{offset}/{chip}"][arm] for chip in CHIPS}
                arms[arm] = {metric: mean(s[metric][die] for s in scores.values()) for metric in keepout.METRICS}
                arms[arm][keepout.BOOTSTRAP] = {chip: s[keepout.BOOTSTRAP][die] for chip, s in scores.items()}
            results[offset][die] = arms
    return results


def bar(units, offset, die):
    """Buried-die field-model RMSE, 2 minus 8 outside-uniform sites, paired per chip: mean and standard error."""
    left, right = PRIMARY
    deltas = [units[f"{offset}/{chip}"][left]["field_model/rmse_K"][die]
              - units[f"{offset}/{chip}"][right]["field_model/rmse_K"][die] for chip in CHIPS]
    m = mean(deltas)
    return {"offset": offset, "tol_K": TOL_K, "ok": m <= TOL_K, "chip_deltas": deltas, "mean": m,
            "se": stdev(deltas) / sqrt(len(deltas))}


def evaluate(run):
    data = read_bytes(run / "scores.json")
    scores = read_object(data)
    try:
        dry = dry_reference()
    except (OSError, ValueError):
        dry = None
    flags = {"scores_readable": scores is not None, "dry_reference": dry is not None}
    if not all(flags.values()):
        return {"verdict": "INCONCLUSIVE", "valid": False, "checks": flags, "evaluator_sha256": EVALUATOR_SHA}
    digest = hashlib.sha256(data).hexdigest()
    log = successful_log(run, digest)
    manifest = read_object(read_bytes(run / "manifest.json"))
    flags.update(checks(scores, dry, manifest, log))
    out = {"verdict": "INCONCLUSIVE", "valid": all(flags.values()), "checks": flags, "scores_sha256": digest,
           "launcher_log": log, "evaluator_sha256": EVALUATOR_SHA}
    if not out["valid"]:
        return out
    units = scores["units"]
    dies = dry["dies"]
    summaries = keepout.summarise(units, CHIPS, dies)
    buried = dies[dry["placement"]["buried_die"]]
    bars = {label: bar(units, offset, buried) for label, offset in BARS.items()}
    out.update(verdict="PASS" if all(bar["ok"] for bar in bars.values()) else "FAIL", bars=bars, chips=list(CHIPS),
               paired_rmse_K=summaries, arm_metrics=report(units, dies), placement=scores["placement"])
    return out


def main(run):
    out = evaluate(run)
    if not run.is_dir():
        print(out["verdict"], {name: ok for name, ok in out["checks"].items() if not ok})
        return
    data = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with NamedTemporaryFile(mode="w", dir=run, suffix=".tmp", encoding="utf-8", delete=False) as fh:
        tmp = Path(fh.name)
    try:
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(run / "result.json")
    finally:
        tmp.unlink(missing_ok=True)
    print(out["verdict"], {name: ok for name, ok in out["checks"].items() if not ok})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    main(parser.parse_args().run)
