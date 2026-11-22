"""G106 dry run: temperature sensors as circuits (goal 18), swept in ngspice inside the image.

Ring oscillators (estimate.sensor_spice.ring) in ASAP7 and IHP at TEMPS, the three corners (power.leak.CORNERS,
G103's models), and supplies nominal x SUPPLY; the IHP npn13G2 dVBE pair (estimate.sensor_spice.dvbe) at TEMPS and
the three HBT corners. Each unit (kit, corner, supply) is one deck and is written as it finishes, so a rerun skips
finished units (A17). The key hashes this file, sensor_spice.py, power/leak.py, the image's model versions
(/opt/spice/VERSIONS) and its tag (OTS_IMAGE). A failed deck is printed with ngspice's last lines and not stored, so
a rerun retries it (code lint L54); derive.py refuses a sweep with a missing unit.

Usage (in the image, repo root): python gates/g106/dry/sweep.py <out.json>
"""
import hashlib
import json
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from opentsense.estimate import sensor_spice  # noqa: E402
from opentsense.power.leak import CORNERS, SPICE  # noqa: E402

TEMPS = (0, 25, 50, 75, 85, 100, 125)
SUPPLY = (0.95, 0.98, 0.99, 1.0, 1.01, 1.02, 1.05)


def key():
    h = hashlib.sha256(os.environ.get("OTS_IMAGE", "unknown").encode())
    for p in (__file__, os.path.join(ROOT, "opentsense", "estimate", "sensor_spice.py"),
              os.path.join(ROOT, "opentsense", "power", "leak.py"), os.path.join(SPICE, "VERSIONS")):
        h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


def units():
    out = [(f"ring/{kit}/{c}/{s:g}", lambda kit=kit, c=c, s=s: sensor_spice.ring(
        kit, c, round(sensor_spice.NOMINAL_V[kit] * s, 6), TEMPS)) for kit in sensor_spice.NOMINAL_V for c in CORNERS
        for s in SUPPLY]
    return out + [(f"dvbe/ihp/{c}", lambda c=c: sensor_spice.dvbe(c, TEMPS)) for c in CORNERS]


def main(out):
    k = key()
    res = json.load(open(out)) if os.path.exists(out) else {}
    if res.get("key") != k:
        res = {"key": k, "image": os.environ.get("OTS_IMAGE", "unknown"), "temps_C": list(TEMPS),
               "supply": list(SUPPLY), "units": {}}
    failed = []
    for name, fn in units():
        if name in res["units"]:
            continue
        t0 = time.time()
        r = fn()
        if "failed" in r:
            failed.append(name)
            print(name, "FAILED, not stored:", r["failed"][-400:], flush=True)
            continue
        res["units"][name] = {"result": r, "wall_s": round(time.time() - t0, 1)}
        print(name, res["units"][name], flush=True)
        with open(out + ".tmp", "w") as fh:
            json.dump(res, fh, indent=1)
        os.replace(out + ".tmp", out)
    if failed:
        raise SystemExit(f"{len(failed)} units failed: {failed}")


if __name__ == "__main__":
    main(sys.argv[1])
