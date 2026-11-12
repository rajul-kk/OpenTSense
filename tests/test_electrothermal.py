"""Leakage-temperature loop (G92): log-linear leakage tables, the fixed point, the loop gain rho and amplification."""
import numpy as np
import pytest

from opentsense.thermal import electrothermal as et

A_EXP = 0.03                                   # 1/K: leakage grows as exp(A_EXP * T)
TEMPS = np.array([25.0, 75.0, 125.0])
R = np.array([[2.0, 0.5], [0.5, 2.0]])         # K/W, two tiles
DYN = np.array([1.0, 0.8])
TILE = np.array([0, 0, 1, 1])


def model(scale=1.0):
    L = 1e-6 * np.exp(A_EXP * TEMPS)
    return et.LeakModel(TEMPS, np.tile(L, (4, 1)), TILE, 2, scale=scale)


def test_log_linear_table_is_exact_for_exponential_leakage():
    lm = model()
    T = np.array([25.0, 50.0, 100.0, 150.0])                       # on a point, inside, inside, beyond the table
    assert np.allclose(lm.inst(T), 1e-6 * np.exp(A_EXP * T), rtol=1e-12)


def test_zero_leakage_instances_stay_zero():
    L = np.vstack([1e-6 * np.exp(A_EXP * TEMPS), np.zeros(3)])
    lm = et.LeakModel(TEMPS, L, np.array([0, 1]), 2)
    assert lm.inst(np.array([60.0, 60.0]))[1] == 0.0


def test_fixed_point_satisfies_the_loop_equation():
    lm = model(2e5)
    T, it, ok, _ = et.solve(R, DYN, lm, 318.15)
    assert ok and np.allclose(T, 318.15 + R @ (DYN + lm.tiles(T)), atol=1e-9)


def test_rho_matches_the_analytic_slope():
    lm = model(2e5)
    T = et.solve(R, DYN, lm, 318.15)[0]
    r, D = et.rho(R, lm, T)
    exact = A_EXP * lm.tiles(T)                                     # d/dT of c exp(aT) is a times itself
    assert np.allclose(D, exact, rtol=1e-4)
    assert r == pytest.approx(np.abs(np.linalg.eigvals(R * exact[None, :])).max(), rel=1e-4)


def test_one_over_one_minus_rho_only_holds_for_small_rho():
    """Measured amplification against 1/(1 - rho): close at small rho, an overestimate as rho grows (rho is taken at
    the hottest point, where leakage rises fastest). U4 must report the measured A."""
    gaps = []
    for scale in (1e5, 5e5):
        lm = model(scale)
        T, _, ok, _ = et.solve(R, DYN, lm, 318.15, max_it=5000)
        assert ok
        r = et.rho(R, lm, T)[0]
        A = et.amplification(R, DYN, lm, 318.15, T)[0]
        gaps.append((r, 1 / (1 - r) / A - 1))
    (r1, g1), (r2, g2) = gaps
    assert r1 < 0.1 and g1 < 0.002
    assert r2 > 0.5 and g2 > 0.1
