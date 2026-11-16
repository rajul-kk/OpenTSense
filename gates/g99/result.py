"""G99 verdict files from the recorded reports: record/<design>-<ps>/{result,manifest}.json.
Usage: python gates/g99/result.py   (reads only record/; the run's bulk output is not needed)"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from opentsense import manifest  # noqa: E402

TPU_ROWS = 616   # G72 bar (a): W1 and W2 each give 616 result rows, idle W3 none


def window_ok(name, v):
    """Bar 4 per window, as G72 bar (a) scores it; every window must have exited 0."""
    if v.get("rc") != 0:
        return False
    if name.startswith("ibex_"):
        return v.get("checksum") == v.get("expected") is not None and v.get("done") == 1
    want = 0 if name == "tpu_W3" else TPU_ROWS
    return v.get("rows") == v.get("rows_match") == want


WINDOWS = {"ibex": [f"ibex_k{k}" for k in range(4)], "tpu": ["tpu_W1", "tpu_W2", "tpu_W3"]}


def first_slack(text, header):
    """Worst slack of the first path group after `header` (OpenSTA -format end, sorted worst first)."""
    m = re.search(re.escape(header) + r".*?^\S.*?\s(-?\d+\.\d+) \((MET|VIOLATED)\)", text, re.S | re.M)
    if not m:
        raise ValueError(f"no slack after {header!r}")
    return float(m[1])


def part(d):
    rec = os.path.join(HERE, "record", d)
    sta = open(os.path.join(rec, "reg2reg_TT.txt")).read()
    finish = open(os.path.join(rec, "6_finish.rpt")).read()
    drc = open(os.path.join(rec, "5_route_drc.rpt")).read()
    sim = json.load(open(os.path.join(rec, "sim.json")))
    lec_path = os.path.join(rec, "6_final_lec_check.log")
    lec = ("identical" if "Circuits are IDENTICAL" in open(lec_path).read() else "not identical") \
        if os.path.exists(lec_path) else "not run"
    windows = {k: sim.get(k, {}) for k in WINDOWS[d.split("-")[0]]}   # a missing window fails, never passes
    checks = {k: window_ok(k, v) for k, v in windows.items()}
    r = {"design": d, "setup_reg2reg_ps": first_slack(sta, "REG2REG max:"),
         "hold_reg2reg_ps": first_slack(sta, "REG2REG min:"),
         "wns_tns_zero": all("tns max 0.00" in t and "wns max 0.00" in t for t in (sta, finish)),
         "hold_violations_all_paths": int(re.search(r"^hold violation count (\d+)", finish, re.M)[1]),
         "drc_violations": len([l for l in drc.splitlines() if l.strip()]), "lec": lec,
         "windows": windows, "windows_match": checks}
    r["pass"] = (r["setup_reg2reg_ps"] >= 0 and r["hold_reg2reg_ps"] >= 0 and r["wns_tns_zero"]
                 and r["hold_violations_all_paths"] == 0
                 and r["drc_violations"] == 0 and lec != "not identical" and all(checks.values()))
    json.dump(r, open(os.path.join(rec, "result.json"), "w"), indent=1)
    manifest.write(os.path.join(rec, "manifest.json"),
                   extra={"layout_sha256": open(os.path.join(rec, "sha256.txt")).read().split("\n"),
                          "from": "recorded reports in this folder; run by launch.sh and bar4.sh"})
    return r


if __name__ == "__main__":
    for d in sorted(os.listdir(os.path.join(HERE, "record"))):
        r = part(d)
        print(d, {k: r[k] for k in ("setup_reg2reg_ps", "hold_reg2reg_ps", "drc_violations", "lec", "pass")})
