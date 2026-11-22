"""What the G93 3D-ICE sensitivities (cooler.py, leak.py) share: the per-die summary and the cache key of a unit.
beol_board.py keeps its own copies, as its recorded run (`runs/`) used them."""
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g93")]
import stacks  # noqa: E402

INPUTS = ["gates/g93/stacks.py", "gates/g93/sens/common.py", "opentsense/stack/model.py", "opentsense/stack/floorplan.py",
          "opentsense/stack/to_3dice.py", "opentsense/thermal/run.py", "opentsense/thermal/electrothermal.py",
          "opentsense/power/dram.py"]


def summary(st, T, P):
    """Per die and powered silicon rectangle (S3: the logic die and each HBM column apart): peak rise, spread (peak
    minus coolest cell) and largest cell-to-cell gradient inside the rectangle (air beside a die is not counted)."""
    cx, cy = st.size_um[0] / st.grid[0] / 1000, st.size_um[1] / st.grid[1] / 1000
    out = {}
    for l in st.dies:
        rects = stacks.powered(st, l, P)
        for rect in rects:
            j0, j1, i0, i1 = st.cells(rect)
            rise = np.asarray(T[l.name])[i0:i1, j0:j1] - st.ambient_K
            g = max(np.abs(np.diff(rise, axis=1)).max(initial=0) / cx, np.abs(np.diff(rise, axis=0)).max(initial=0) / cy)
            label = l.name if len(rects) == 1 else f"{l.name}@{rect[0]:.0f},{rect[1]:.0f}"
            out[label] = {"peak_rise_K": float(rise.max()), "spread_K": float(rise.max() - rise.min()),
                          "max_gradient_K_per_mm": float(g)}
    return out


def key(script, cell_um):
    """Hash of everything that sets a unit's result: the script, INPUTS, the floorplans, the image tag, the cell."""
    h = hashlib.sha256(f"{float(cell_um)}|{os.environ.get('OTS_IMAGE', 'unknown')}".encode())
    flp = os.path.join(ROOT, "configs", "floorplans")
    for p in [script] + [os.path.join(ROOT, f) for f in INPUTS] + sorted(os.path.join(flp, f) for f in os.listdir(flp)):
        h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


def done(path, k):
    """True if the unit's output exists with this key (A17: skip only outputs of the same inputs)."""
    return os.path.exists(path) and json.load(open(path)).get("key") == k


def write(path, rec):
    with open(path + ".tmp", "w") as fh:
        json.dump(rec, fh, indent=1)
    os.replace(path + ".tmp", path)
    print(json.dumps(rec))
