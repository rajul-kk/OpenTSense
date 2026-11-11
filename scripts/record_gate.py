"""Copy a gate's verdict files from its (git-ignored) run folder into its tracked record folder.

    python scripts/record_gate.py g81b            # gates/g81b/runs/main/{result,manifest}.json -> gates/g81b/record/
    python scripts/record_gate.py g70 --run a b   # several runs -> gates/g70/record/a/, record/b/
    python scripts/record_gate.py g92d --parts    # one sub-folder per kit: runs/main/<kit>/ -> record/<kit>/

Bulk outputs stay in runs/ (ignored). record/ holds only the small files a reader or the test in
tests/test_gate_records.py needs: result.json and manifest.json. Missing files are reported, never invented.
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("result.json", "manifest.json")


def copy(src, dst):
    missing = []
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        s = os.path.join(src, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
        else:
            missing.append(os.path.relpath(s, ROOT))
    return missing


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gate", help="gate folder name, e.g. g81b")
    ap.add_argument("--run", nargs="+", default=["main"], help="run folder(s) under runs/ (default: main)")
    ap.add_argument("--parts", action="store_true", help="the run holds one sub-folder per part (kit, stack)")
    a = ap.parse_args(argv)
    gate = os.path.join(ROOT, "gates", a.gate)
    rec = os.path.join(gate, "record")
    missing = []
    for run in a.run:
        src = os.path.join(gate, "runs", run)
        if not os.path.isdir(src):
            sys.exit(f"no run folder {os.path.relpath(src, ROOT)}")
        dst = rec if len(a.run) == 1 else os.path.join(rec, run)
        if a.parts:
            parts = sorted(p for p in os.listdir(src) if os.path.isfile(os.path.join(src, p, "result.json")))
            for p in parts:
                missing += copy(os.path.join(src, p), os.path.join(dst, p))
        else:
            missing += copy(src, dst)
    for m in missing:
        print(f"missing: {m}")
    print(f"recorded {a.gate} -> {os.path.relpath(rec, ROOT)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
