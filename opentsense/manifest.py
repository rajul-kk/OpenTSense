"""Version manifest written by every run: tool versions, Python packages, repo commit and image digests."""
import datetime
import json
import os
import platform
import subprocess
from importlib import metadata

TOOLS = {
    "iverilog": ["iverilog", "-V"],
    "verilator": ["verilator", "--version"],
    "ngspice": ["ngspice", "--version"],
    "3dice_commit": ["cat", "/opt/3d-ice/COMMIT"],
    "superlu_mt_commit": ["git", "-C", "/opt/3d-ice/superlu_mt-4.0.0", "rev-parse", "HEAD"],
    "pact_commit": ["cat", "/opt/pact/COMMIT"],
    "ca_certificates": ["dpkg-query", "-W", "-f", "${Version}", "ca-certificates"],
}
PACKAGES = ["numpy", "scipy", "pandas", "PyYAML", "pytest"]


def _first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        txt = (r.stdout or r.stderr).strip().splitlines()
        # ngspice --version prints a banner; keep the line with the version number
        txt = [l for l in txt if any(c.isdigit() for c in l)] or txt
        return txt[0].strip("* ") if txt else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def repo_commit(repo=None):
    repo = repo or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True)
    c = r.stdout.strip() if r.returncode == 0 else None  # None: no commit yet
    dirty = _first_line(["git", "-C", repo, "status", "--porcelain"])
    return {"commit": c, "dirty": bool(dirty)}


def collect(extra=None):
    m = {
        "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "host": platform.node(),
        "python": platform.python_version(),
        "repo": repo_commit(),
        "image": os.environ.get("OPENTSENSE_IMAGE"),
        "orfs_image": os.environ.get("ORFS_IMAGE"),
        "tools": {k: _first_line(v) for k, v in TOOLS.items()},
        "packages": {},
    }
    for p in PACKAGES:
        try:
            m["packages"][p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            m["packages"][p] = None
    m.update(extra or {})
    return m


def write(path, extra=None):
    m = collect(extra)
    json.dump(m, open(path, "w"), indent=2)
    return m


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
