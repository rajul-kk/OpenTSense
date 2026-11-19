"""G81f: G81e's step 2 unchanged except the energy model, refitted in `dry/fit_energy2.json` (registration.md).

G81e's runner, scorer and G50a check run as recorded; only their FIT path (and the code list hashed with it) points
here, and the manifest is relabelled G81f. Usage (repo root, host, holding a heavy slot of 2 GB, as G81e):
python gates/g81f/run.py gates/g81f/runs/main
"""
import importlib.util
import json
import os
import sys

STEP2 = os.path.join("gates", "g81e", "step2")
FIT = "gates/g81f/dry/fit_energy2.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(out):
    if os.path.abspath(out).startswith(os.path.abspath(os.path.join("gates", "g81e"))):
        raise SystemExit("G81f writes under gates/g81f, not into G81e's runs")
    run = load("g81e_run", os.path.join(STEP2, "run.py"))
    old = run.FIT.replace(os.sep, "/")
    if old not in run.CODE:
        raise SystemExit(f"G81e's code list no longer names its fit {old}")
    run.FIT = FIT
    run.CODE = [FIT if p == old else p for p in run.CODE] + ["gates/g81f/run.py", "gates/g81f/dry/fit_energy2.py"]
    run.main(os.path.join("gates", "g81e", "runs", "step1-main"), out)       # input guard and resume inside
    load("g81e_g50a", os.path.join(STEP2, "g50a_check.py")).main(out)
    m = os.path.join(out, "manifest.json")
    json.dump({**json.load(open(m)), "gate": "G81f (G81e step 2 with the refitted energy model)"}, open(m, "w"), indent=2)
    load("g81e_evaluate", os.path.join(STEP2, "evaluate.py")).main(out)


if __name__ == "__main__":
    main(sys.argv[1])
