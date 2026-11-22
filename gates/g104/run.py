"""G104 gated run: sensors only outside the dense logic block, on G84's case set (registration.md).

Rebuilds G84's case set and checks its sha256, places the four site sets with `dry/sites.py`'s `site_sets` (same
masks, ring, sensor count and greedy search; the sets depend only on the train split) and refuses to score unless
they and their placement noise equal the dry run's (`dry/sites.json`), then scores every offset model, set and gated
chip as the dry run did.

Usage (repo root, host): python gates/g104/run.py <out dir>
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(HERE, "dry")]
from opentsense import manifest  # noqa: E402
from opentsense.bench import metrics, readings  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.bench.estimators import FieldModel  # noqa: E402
from opentsense.bench.score import score  # noqa: E402
import sites  # noqa: E402

CHIPS = tuple(range(21, 31))
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"


def inputs(cs):
    """sha256 of this gate's files, every opentsense module loaded, G71's block map and the stack config."""
    mods = {os.path.relpath(m.__file__, ROOT).replace(os.sep, "/") for m in list(sys.modules.values())
            if getattr(m, "__file__", None) and os.path.abspath(m.__file__).startswith(os.path.join(ROOT, "opentsense"))}
    stack = os.path.relpath(os.path.join(readings.STACKS, f"{cs.stack_id}.yaml"), ROOT).replace(os.sep, "/")
    files = sorted(mods | {"gates/g104/run.py", "gates/g104/evaluate.py", "gates/g104/registration.md",
                           "gates/g104/dry/sites.py", "gates/g104/dry/sites.json",
                           "gates/g84/make_cases.py", "gates/g71/inputs/maps.npz", stack})
    return {p: manifest.file_sha256(os.path.join(ROOT, p)) for p in files}


def write_json(obj, path):
    """Whole or not at all: a gated record is never re-run, so a cut-off write must not leave a partial file."""
    with open(path + ".tmp", "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(path + ".tmp", path)


def main(out):
    os.makedirs(out, exist_ok=True)
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):                 # built under another name and renamed: never a cut-off file
        tmp = os.path.abspath(os.path.join(out, "cases.tmp.npz"))
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), tmp], check=True, cwd=ROOT)
        os.replace(tmp, cases)
        os.replace(tmp[:-4] + ".json", os.path.join(out, "cases.json"))     # make_cases' summary
    cs = CaseSet.load(cases)
    if cs.sha256() != G84_SHA:                   # recorded, so evaluate.py writes the INCONCLUSIVE verdict
        write_json({"case_set_sha256": cs.sha256(), "runs": {}}, os.path.join(out, "scores.json"))
        raise SystemExit(f"case set {cs.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    hashes = inputs(cs)
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G104", "inputs_sha256": hashes})
    sets, noise, gf = sites.site_sets(cs)
    dry = json.load(open(os.path.join(HERE, "dry", "sites.json")))
    same_noise = all(abs(noise[k] - dry["placement_noise_K"][k]) <= 1e-9 * dry["placement_noise_K"][k] for k in noise)
    if {k: v.tolist() for k, v in sets.items()} != dry["sites"] or not same_noise:
        raise SystemExit("the placed sites differ from the dry run's (dry/sites.json); nothing scored or recorded")
    res = {"case_set_sha256": cs.sha256(), "profile": sites.PROFILE, "chips": list(CHIPS), "salt": sites.SALT,
           "keep_cells": sites.KEEP, "offsets": dict(sites.CORR), "placement_noise_K": noise,
           "sites": {k: v.tolist() for k, v in sets.items()}, "runs": {}}
    groups = cs.group[cs.idx("test")]
    for oname, corr in sites.CORR.items():
        for chip in CHIPS:
            per = {}
            for name, S in sets.items():
                r, p = score(readings.with_sensor(readings.with_sites(cs, S), sites.PROFILE, chip, sites.SALT, corr),
                             ["average", "field_model"], estimators={"field_model": FieldModel(gf=gf)})
                per[name] = p["field_model"]["rmse_K"]
                res["runs"][f"{oname}/{name}/{chip}"] = {"field_model": r["estimators"]["field_model"]["summary"],
                                                         "average": r["estimators"]["average"]["summary"],
                                                         "vs_average": r["comparisons"]["field_model - average"]}
            for name in sets:
                if name != "all/uniform":
                    res["runs"][f"{oname}/{name}/{chip}"]["vs_all_uniform"] = {
                        str(d): metrics.bootstrap_diff(per[name][:, i], per["all/uniform"][:, i], groups)
                        for i, d in enumerate(cs.dies)}
        print(oname, "done", flush=True)
    if inputs(cs) != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    write_json(res, os.path.join(out, "scores.json"))


if __name__ == "__main__":
    main(sys.argv[1])
