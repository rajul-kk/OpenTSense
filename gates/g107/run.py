"""G107 gated run: the buried die's sensor budget on G84's case set (registration.md).

Rebuilds G84's case set and checks its sha256, then runs `dry/budget.py`'s `main` on the gated chips: the same site
sets, one chip read per chip number, the same scoring. The placed sites and placement noise must equal the dry run's
(`dry/budget.json`) before anything is scored. scores.json is rewritten after each chip and ends with `complete` and
`inputs_unchanged`, which evaluate.py requires.

Usage (repo root, host): python gates/g107/run.py <out dir>
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(HERE, "dry")]
import budget  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402

CHIPS = tuple(range(21, 31))
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
OWN = ["gates/g107/run.py", "gates/g107/dry/budget.json", "gates/g84/make_cases.py"]     # what makes the scores


def main(out):
    os.makedirs(out, exist_ok=True)
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):                 # built under another name and renamed: never a cut-off file
        tmp = os.path.abspath(os.path.join(out, "cases.tmp.npz"))
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), tmp], check=True, cwd=ROOT)
        os.replace(tmp, cases)
        os.replace(tmp[:-4] + ".json", os.path.join(out, "cases.json"))
    if CaseSet.load(cases).sha256() != G84_SHA:
        raise SystemExit("the case set is not G84's: nothing scored (INCONCLUSIVE)")
    dry = json.load(open(os.path.join(HERE, "dry", "budget.json")))
    budget.main(cases, os.path.join(out, "scores.json"), CHIPS, OWN, dry)


if __name__ == "__main__":
    main(sys.argv[1])
