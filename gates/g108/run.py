"""Run the registered G108 chips into an output directory after launcher approval."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from gates.g108.dry import keepout

CHIPS = tuple(range(31, 41))
DRY = "gates/g108/dry/keepout.json"
DRY_SHA = "33e9c84efa9ecea22697afc81ce3841ba4bf4236120620c0bc1911cf098d02b5"
# The scorer was updated after the dry run; dry/a15/keepout.json reran chips 1-5 with this version and reproduced
# the dry placement, units and summary exactly.
SCORER = "gates/g108/dry/keepout.py"
SCORER_SHA = "f7bbe5ed6555e297e629628cda990edbe9dfc593f305b20a3fb35dc9265ee7aa"
RUN_INPUTS = (DRY, "gates/g108/run.py", "gates/g108/dry/launch.ps1")


def dry_reference():
    data = (ROOT / DRY).read_bytes()
    if hashlib.sha256(data).hexdigest() != DRY_SHA:
        raise ValueError("G108 dry reference differs from the registration")
    return json.loads(data)


def dry_input_pins(dry):
    return {**dry["key"]["inputs_sha256"], SCORER: SCORER_SHA, DRY: DRY_SHA}


def runtime():
    """The key.runtime that keepout.run records (dry/keepout.py, key construction); the evaluator requires the dry
    record's, so check it before any held-out unit is scored."""
    return {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "openblas_threads": os.environ.get("OPENBLAS_NUM_THREADS")}


def main(out):
    dry = dry_reference()
    if runtime() != dry["key"]["runtime"]:
        raise ValueError(f"runtime {runtime()} differs from the dry record's {dry['key']['runtime']}")
    out.mkdir(parents=True, exist_ok=True)
    keepout.run_locked(CHIPS, out / "scores.json", reference=dry["placement"],
                       extra_inputs=RUN_INPUTS, pinned_inputs=dry_input_pins(dry))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
