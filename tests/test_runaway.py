"""U4: monotone Newton classifier of the leakage loop against the analytic one-tile boundary and the Picard solve."""
import numpy as np
import pytest

from opentsense.thermal import electrothermal as et
from opentsense.thermal import runaway

A = 0.03
TEMPS = np.array([25.0, 75.0, 125.0, 175.0])


def leak(c, n_tiles=1, tile=None):
    tile = np.zeros(1, int) if tile is None else np.asarray(tile)
    L = c * np.exp(A * TEMPS)                                    # exponential: the log-linear table is exact
    return et.LeakModel(TEMPS, np.tile(L, (len(tile), 1)), tile, n_tiles)


@pytest.mark.parametrize("frac, status", [(0.99, "converged"), (1.01, "runaway"), (0.5, "converged"), (3.0, "runaway")])
def test_one_tile_matches_the_analytic_boundary(frac, status):
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c = frac * runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    out = runaway.classify(np.array([[r]]), np.array([dyn]), leak(c), Tamb, max_it=200)
    assert out.status == status and out.monotone
    if status == "converged":
        assert out.rho < 1


def test_converged_point_equals_the_picard_solution():
    R = np.array([[2.0, 0.5], [0.5, 2.0]])
    dyn = np.array([1.0, 0.8])
    lk = et.LeakModel(TEMPS, np.tile(1e-6 * np.exp(A * TEMPS), (4, 1)) * 3e5, np.array([0, 0, 1, 1]), 2)
    out = runaway.classify(R, dyn, lk, 318.15)
    T, _, ok, _ = et.solve(R, dyn, lk, 318.15, max_it=5000)
    assert out.status == "converged" and ok and np.allclose(out.T, T, atol=1e-7)
    assert out.iterations < 15 and out.monotone
    assert all(b >= a - 1e-9 for a, b in zip(out.rho_path, out.rho_path[1:]))    # rho rises (to round-off)


def test_near_the_boundary_newton_is_fast():
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c = 0.999 * runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    out = runaway.classify(np.array([[r]]), np.array([dyn]), leak(c), Tamb, max_it=200)
    assert out.status == "converged" and out.rho > 0.9 and out.iterations < 60


def test_iteration_cap_is_its_own_status():
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c = 0.5 * runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    out = runaway.classify(np.array([[r]]), np.array([dyn]), leak(c), Tamb, max_it=1)
    assert out.status == "not_converged"


@pytest.mark.parametrize("frac", [0.3, 0.8, 0.99, 0.999])
def test_rho_at_the_fixed_point_follows_the_saddle_node_law(frac):
    """One tile, leakage c exp(aT): with f = c / c_crit, rho at the fixed point solves rho - ln rho = 1 - ln f
    (from T - T_amb - r dyn = rho / a and rho = r c a exp(aT)). Near the boundary 1 - rho ~ sqrt(2 (1 - f)), so a
    rho that looks far from 1 can be close to runaway in leakage."""
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c = frac * runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    out = runaway.classify(np.array([[r]]), np.array([dyn]), leak(c), Tamb, max_it=200, h=1e-3)
    exact = r * c * A * np.exp(A * (out.T[0] - 273.15))
    assert out.rho == pytest.approx(exact, rel=1e-6)
    assert out.rho - np.log(out.rho) == pytest.approx(1 - np.log(frac), rel=1e-9)
