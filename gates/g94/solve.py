"""G94's one refinement rule, used by the dry convergence run and the gated run alike.

Refinement level L: every slot is split into r = 2^L identical power rows of length slot / r, and every solver
advances one row per output (3D-ICE: step = slot = slot / r; PACT: one backward-Euler step per row; HotSpot: one
trace row each; on the small test stack its row-end values equal 3D-ICE's to 1e-4 K at the same rows, 16 Nov). So
the time step and the output resolution refine together for all three solvers, and a floor taken between levels
includes the error of sampling the trajectory at row ends.
"""
import tempfile

import numpy as np

from opentsense.stack import to_3dice
from opentsense.thermal.run import run_3dice, run_hotspot, run_pact

SOLVERS = {"ice": run_3dice, "pact": run_pact, "hs": run_hotspot}


def check_level(slot, level):
    """Refuse a level 3D-ICE's parser cannot represent (to_3dice.steps_per_slot), before any solve starts."""
    to_3dice.steps_per_slot(slot / 2 ** level, slot / 2 ** level)


def rise(solver, stack, P, slot, level):
    """{die: (n_slots * 2^level, ny, nx)} temperature rise at the end of every row."""
    r = 2 ** level
    check_level(slot, level)
    with tempfile.TemporaryDirectory() as wd:
        T = SOLVERS[solver](stack, {d: np.repeat(v, r, 0) for d, v in P.items()}, wd, transient=(slot / r, slot / r))
    return {d: v - stack.ambient_K for d, v in T.items()}


def on_grid(s, level, grid_level):
    """A row-resolution series at `level` sampled at the row ends of a coarser `grid_level` (slot ends: 0)."""
    r = 2 ** (level - grid_level)
    return np.asarray(s)[r - 1::r]


def t63(peak, dt):
    """Time where the peak rise first reaches 63.2% of its last value, rows ending at dt, 2 dt, ...; linear between
    row ends (from zero at t = 0 inside the first row)."""
    p = np.asarray(peak)
    target = (1 - np.exp(-1)) * p[-1]
    k = int(np.argmax(p >= target))
    t = dt * (np.arange(len(p)) + 1)
    if k == 0:
        return float(t[0] * target / p[0])
    return float(t[k - 1] + (t[k] - t[k - 1]) * (target - p[k - 1]) / (p[k] - p[k - 1]))


def series(T):
    """Per die: peak and mean rise at every row end."""
    return {d: {"peak": v.reshape(len(v), -1).max(1).tolist(), "mean": v.reshape(len(v), -1).mean(1).tolist()}
            for d, v in T.items()}
