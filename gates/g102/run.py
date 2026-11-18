"""G102 gated run: rebuild G84's case set, then score every profile x chip (registration.md).

Usage (repo root, host): python gates/g102/run.py <out dir>
"""
import json
import os
import subprocess
import sys

sys.path[:0] = [".", os.path.dirname(os.path.abspath(__file__))]
from opentsense import manifest  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.bench.score import score  # noqa: E402
import readings  # noqa: E402

EST = ["average", "field_model", "bayes_power", "inverted"]
CHIPS = tuple(range(6, 16))
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"


def inputs():
    """sha256 of this gate's files and every opentsense module loaded (the scorer imports its estimators)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mods = {os.path.relpath(m.__file__, root).replace(os.sep, "/") for m in list(sys.modules.values())
            if getattr(m, "__file__", None) and os.path.abspath(m.__file__).startswith(os.path.join(root, "opentsense"))}
    files = sorted(mods | {"gates/g102/run.py", "gates/g102/readings.py", "gates/g102/evaluate.py",
                           "gates/g102/registration.md", "gates/g84/make_cases.py"})
    return {p: manifest.file_sha256(os.path.join(root, p)) for p in files}


def main(out):
    os.makedirs(out, exist_ok=True)
    hashes = inputs()                                     # before any scoring: the code that produces the scores
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G102", "inputs_sha256": hashes})
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):
        subprocess.run([sys.executable, "gates/g84/make_cases.py", cases], check=True)
    cs = CaseSet.load(cases)
    if cs.sha256() != G84_SHA:
        raise SystemExit(f"case set {cs.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    res = {"case_set_sha256": cs.sha256(), "chips": list(CHIPS), "runs": {}}
    for prof in readings.sensor.PROFILES:
        for chip in CHIPS:
            r, _ = score(readings.with_sensor(cs, prof, chip), EST)
            res["runs"][f"{prof}/{chip}"] = r
        print(prof, "done", flush=True)
    if inputs() != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    json.dump(res, open(os.path.join(out, "scores.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
