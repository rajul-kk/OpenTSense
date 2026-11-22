"""Collect the ungated sensitivity runs (cooler, leakage, cold plate) into one small record for git; the run folders
themselves stay out of git (.gitignore). Each entry keeps its file name, key and every field but the wall time.

Usage (repo root): python gates/g93/sens/record.py <out.json>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDERS = ("cooler_runs", "cooler_runs_v2", "leak_runs_v0", "leak_runs", "coldplate_runs_v1", "coldplate_runs")


def main(out):
    rec = {}
    for f in FOLDERS:
        d = os.path.join(HERE, f)
        rec[f] = {n: {k: v for k, v in json.load(open(os.path.join(d, n))).items() if k != "wall_s"}
                  for n in sorted(os.listdir(d)) if n.endswith(".json")}
    with open(out, "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    print({f: len(v) for f, v in rec.items()})


if __name__ == "__main__":
    main(sys.argv[1])
