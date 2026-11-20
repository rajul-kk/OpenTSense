"""Goal 11 (ungated sensitivity, 3D-ICE only): what G93's gate leaves out, BEOL anisotropy and a board-side path.

Each die gets a BEOL layer on its source face (thickness BEOL_UM, over the die's footprint only), and the stack
optionally a coefficient on the face opposite the sink. Variants (all steady, nominal power, silicon k(T) by
thermal.run.solve_kT, as the gate):
  base          the stack as G93 built it before 17 Nov: stacks.build(..., beol_um=0) (no BEOL, adiabatic bottom)
  beol_iso      BEOL at its vertical k in every direction (what PACT and HotSpot could represent)
  beol_aniso    BEOL vertical k_v, lateral k_l (3D-ICE's three-conductivity material)
  beol_lo/_hi   beol_aniso with the vertical k at the ends of the published range
  board_lo/_hi  base plus a bottom coefficient h = 1 / (R_jb x the bottom layer's silicon area), R_jb at the ends of an
                ASSUMED range
Sources (17 Nov 2026 search), all graded secondary, so the values are a range, not a figure:
  vertical 2 to 6 W/(m K) across N90 to N5 (multiscale BEOL modelling, Int. J. Therm. Sci. 2026, S1290072926004916);
  0.65 measured (arXiv 2508.07740); 15 lateral / 1.0 vertical in a 5 um layer model (UCSD, schen.ucsd.edu paper73).
  BEOL_UM = 10 and cv: ASSUMED. R_jb: ASSUMED 2 to 8 K/W (a large flip-chip BGA on a board); the substrate itself is
  not modelled, so the coefficient sits on the stack's bottom face.
Per stack and variant: peak rise and largest gradient (K/mm) inside each powered silicon rectangle of each die, written
to <out>/<stack>_<cell>um_<variant>.json
(skipped when that file exists with the same "key": a hash of every input file, the image tag and the cell size).

Usage (in the image, repo root): python gates/g93/sens/beol_board.py <out_dir> <cell_um> <stack>[,<stack>...] [variant,...]
"""
import dataclasses
import hashlib
import json
import os
import sys
import tempfile
import time

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g93")]
import stacks  # noqa: E402
from opentsense.thermal import run  # noqa: E402

# Frozen as the recorded run (`runs/`) used them; the gated stacks' own values are stacks.BEOL and stacks.BEOL_CV.
BEOL_UM = 10.0
BEOL_CV = 2.0e6
K_V, K_L = 2.0, 15.0
K_V_RANGE = (1.0, 6.0)
R_JB = (2.0, 8.0)
VARIANTS = ("base", "beol_iso", "beol_aniso", "beol_lo", "beol_hi", "board_lo", "board_hi")


# The BEOL layer and the silicon lookups moved to stacks.py on 17 Nov 2026, when the gated stacks took an isotropic
# BEOL layer; this sensitivity builds its base without it (beol_um=0), so its stacks are the ones its recorded run
# (`runs/`) used.
silicon, powered = stacks.silicon, stacks.powered


def with_beol(st, P, k_v, k_l):
    return stacks.with_beol(st, P, BEOL_UM, k_v, k_l, BEOL_CV)


def variant(st, P, name):
    if name == "base":
        return st
    if name.startswith("board"):
        # R_jb is a resistance from the die to the board, so the coefficient spreads 1 / R_jb over the bottom
        # layer's silicon (the dies' footprint), not over the lid outline, most of which is air in a lidded stack.
        # 3D-ICE applies the coefficient over the whole bottom face, so the air beside the dies adds a weak parallel
        # path (S1: about 819 mm2 of air, roughly +10% on 1 / R_jb), a stated limit of this variant
        r = R_JB[0] if name.endswith("lo") else R_JB[1]
        area = sum(w * h for _, _, w, h in silicon(st, st.layers[-1])) * 1e-12
        return dataclasses.replace(st, opposite_htc=1.0 / (r * area))
    k_v = {"beol_lo": K_V_RANGE[0], "beol_hi": K_V_RANGE[1]}.get(name, K_V)
    return with_beol(st, P, k_v, None if name == "beol_iso" else K_L)


def summary(st, T, P):
    """Per die and powered silicon rectangle (S3: the logic die and each HBM column apart): peak rise and largest
    cell-to-cell gradient inside the rectangle (air beside a die is not counted)."""
    cx, cy = st.size_um[0] / st.grid[0] / 1000, st.size_um[1] / st.grid[1] / 1000
    out = {}
    for l in st.dies:
        rects = powered(st, l, P)
        for rect in rects:
            j0, j1, i0, i1 = st.cells(rect)
            rise = np.asarray(T[l.name])[i0:i1, j0:j1] - st.ambient_K
            g = max(np.abs(np.diff(rise, axis=1)).max(initial=0) / cx, np.abs(np.diff(rise, axis=0)).max(initial=0) / cy)
            label = l.name if len(rects) == 1 else f"{l.name}@{rect[0]:.0f},{rect[1]:.0f}"
            out[label] = {"peak_rise_K": float(rise.max()), "max_gradient_K_per_mm": float(g)}
    return out


INPUTS = ["gates/g93/stacks.py", "opentsense/stack/model.py", "opentsense/stack/floorplan.py",
          "opentsense/stack/to_3dice.py", "opentsense/thermal/run.py", "opentsense/power/dram.py"]


def key(cell_um):
    """Hash of everything that sets a result: this file, the stack builder, model, floorplans, the 3D-ICE path,
    the image tag and the cell size."""
    h = hashlib.sha256(f"{float(cell_um)}|{os.environ.get('OTS_IMAGE', 'unknown')}".encode())
    flp = os.path.join(ROOT, "configs", "floorplans")
    for p in [__file__] + [os.path.join(ROOT, f) for f in INPUTS] + sorted(os.path.join(flp, f) for f in os.listdir(flp)):
        h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


def main(out_dir, cell_um, names, variants=",".join(VARIANTS)):
    os.makedirs(out_dir, exist_ok=True)
    k = key(cell_um)
    for name in names.split(","):
        st0, P = stacks.build(name, float(cell_um), beol_um=0)
        for v in variants.split(","):
            path = os.path.join(out_dir, f"{name}_{float(cell_um):.0f}um_{v}.json")
            if os.path.exists(path) and json.load(open(path)).get("key") == k:
                print("skip", path)
                continue
            st = variant(st0, P, v)
            t0 = time.time()
            with tempfile.TemporaryDirectory() as wd:
                T, it = run.solve_kT(run.run_3dice, st, P, wd)
            rec = {"key": k, "stack": name, "variant": v, "cell_um": float(cell_um), "grid": list(st.grid),
                   "wall_s": round(time.time() - t0, 1), "kT_iterations": it, "dies": summary(st, T, P)}
            with open(path + ".tmp", "w") as f:
                json.dump(rec, f, indent=1)
            os.replace(path + ".tmp", path)
            print(json.dumps(rec))


if __name__ == "__main__":
    main(*sys.argv[1:])
