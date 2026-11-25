"""gates/runaway_audit/audit.py: the monotone envelopes bracket a non-monotone leakage model on [T_amb, T_cap]."""
import importlib.util
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("runaway_audit", os.path.join(ROOT, "gates", "runaway_audit", "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_envelopes_are_monotone_and_bracket_the_model_between_grid_points():
    rng = np.random.default_rng(0)
    L = np.exp(rng.normal(-28, 0.3, (300, 5))).cumsum(axis=1)
    L[:120] = np.exp(rng.normal(-28, 0.5, (120, 5)))           # many non-monotone rows, some falling at the end
    L[0] = [1e-12, 2e-12, 1.5e-12, 3e-12, 2.5e-12]
    lo, hi = audit.envelopes(L)
    assert np.all(np.diff(lo, axis=1) >= 0) and np.all(np.diff(hi, axis=1) >= 0)
    tile = np.zeros(len(L), int)
    m = audit.et.LeakModel(audit.sweep.TEMPS, L, tile, 1)
    ml, mh = (audit.et.LeakModel(audit.GRID_C, E, tile, 1) for E in (lo, hi))
    for t in rng.uniform(85.0, 726.85, 300):                    # hot ambient to T_cap, deg C
        x = np.full(len(L), t)
        a, b, c = ml.inst(x), m.inst(x), mh.inst(x)
        assert np.all(a <= b * (1 + 1e-12)) and np.all(b <= c * (1 + 1e-12))


def test_a_monotone_table_is_not_enveloped():
    assert audit.monotone(np.array([[1.0, 1.0, 2.0, 3.0, 4.0]]))
    assert not audit.monotone(np.array([[1.0, 2.0, 1.9, 3.0, 4.0]]))
