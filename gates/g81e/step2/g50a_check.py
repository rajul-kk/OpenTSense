"""G81e bar (v2), second half: G50a's streaming trace through today's DRAMPower set-up must give G50a's recorded
pJ/bit within 1%. Runs a copy of G50a's script in a scratch directory, so its record stays as run.

Usage (repo root, on the host): python gates/g81e/step2/g50a_check.py <out dir>
"""
import json
import os
import shutil
import subprocess
import sys

SENS = os.path.join("..", "..", "experiments", "code", "sens")
SCRIPT, RECORD = os.path.join(SENS, "g50a.py"), os.path.join(SENS, "g50", "g50a_res.json")


def main(out_dir):
    d = os.path.join(out_dir, "g50a")
    os.makedirs(d, exist_ok=True)
    shutil.copy(SCRIPT, d)
    # g50a.py checks neither its trace write nor DRAMPower's exit, and reads ~/g50/out.json: clear both files first
    subprocess.run(["wsl", "-e", "bash", "-c", "rm -f ~/g50/out.json ~/g50/trace.csv"], check=True)
    r = subprocess.run([sys.executable, os.path.join(d, "g50a.py")], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"G50a's script failed: {r.stdout[-1500:]} {r.stderr[-1500:]}")
    now = json.load(open(os.path.join(d, "g50", "g50a_res.json")))["pJ_per_bit_total"]
    rec = json.load(open(RECORD))["pJ_per_bit_total"]
    res = {"pJ_per_bit_now": now, "pJ_per_bit_recorded": rec, "rel_diff": abs(now - rec) / rec}
    json.dump(res, open(os.path.join(out_dir, "g50a.json"), "w"), indent=1)
    print(res)


if __name__ == "__main__":
    main(sys.argv[1])
