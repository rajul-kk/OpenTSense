"""U4: the leakage-loop classifier (Newton, runaway confirmed by fixed-point iteration) against the analytic one-tile
boundary, the Picard solve, and a solver-free boundary on a non-convex table."""
import warnings

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
    r_end, _ = et.rho(np.array([[r]]), leak(c), out.T, 0.5)
    assert out.rho == r_end and out.rho_path[-1] == r_end           # rho belongs to the returned T


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


def test_critical_scale_finds_the_analytic_boundary():
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c_crit = runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    # not lo=0.1, hi=10: its first probe would be the fold itself (s = 1), where the fixed-point check that confirms a
    # runaway slows to a crawl and reports not_converged
    lo, hi, n = runaway.critical_scale(np.array([[r]]), np.array([dyn]), lambda s: leak(s * c_crit), Tamb,
                                       lo=0.1, hi=12.0, rtol=1e-4, max_it=400)
    assert lo <= 1.0 <= hi * (1 + 1e-9) and hi / lo - 1 <= 1e-4 and n < 40


def test_critical_scale_refuses_a_bad_bracket():
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c_crit = runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    with pytest.raises(RuntimeError, match="bracket"):
        runaway.critical_scale(np.array([[r]]), np.array([dyn]), lambda s: leak(s * c_crit), Tamb, lo=2.0, hi=10.0)


def test_critical_scale_refuses_reversed_bounds():
    with pytest.raises(ValueError, match="lo < hi"):
        runaway.critical_scale(np.eye(1), np.ones(1), None, 300.0, lo=10.0, hi=0.1)


def test_a_finite_step_into_overflow_is_runaway():
    # rho at ambient just under 1, far past the boundary: the first Newton step is finite but ~1e5 K, the leakage
    # table's last segment then overflows, and the next rho sees inf/NaN (c6 v2, bs_kbeol1.2_tc200, scale 1000)
    r, dyn, Tamb = 20.0, 1.0, 318.15
    c = 0.9998 / (r * A * np.exp(A * (Tamb - 273.15)))
    with warnings.catch_warnings():
        warnings.simplefilter("error")                          # the overflow is handled, not warned about
        out = runaway.classify(np.array([[r]]), np.array([dyn]), leak(c), Tamb)
        lo, hi, _ = runaway.critical_scale(np.array([[r]]), np.array([dyn]), lambda s: leak(s * c), Tamb,
                                           lo=1e-3, hi=1.0, rtol=1e-3)
    assert out.status == "runaway" and out.iterations == 2 and out.rho == np.inf
    assert out.rho_path[0] < 1 and out.T[0] > 1e4             # step 1 was finite and landed past the table
    c_crit = runaway.critical_scale_1tile(r, dyn, 1.0, A, Tamb)
    assert lo * c <= c_crit <= hi * c * (1 + 1e-9)


# c6's SVT table (dry/c6 v2 leak.json, W/mm^2 at 25..125 C): its log slope falls at 45 and 65 C (not convex)
SVT_C = np.array([25.0, 45.0, 65.0, 85.0, 105.0, 125.0])
SVT_W = np.array([0.0004702254761116959, 0.0014544919477811817, 0.003960914755529798, 0.010494060485181488,
                  0.029060322268241123, 0.08084974496801293])


def svt(s):
    return et.LeakModel(SVT_C, [SVT_W], [0], 1, scale=s)


def svt_boundary(r, dyn, Tamb):
    """Largest scale with a fixed point, without a solver: s* = max over T of (T - T_amb - r dyn) / (r P_1(T)); the
    ratio is maximised on a fine grid, refined around the best point."""
    def ratio(T):
        k, w = et.segment(SVT_C, T - 273.15)
        ln = np.log(SVT_W)
        return (T - Tamb - r * dyn) / (r * np.exp(ln[k] + w * (ln[k + 1] - ln[k])))
    T = np.linspace(Tamb + r * dyn, Tamb + 150.0, 300001)
    best = T[np.argmax(ratio(T))]
    return float(ratio(np.linspace(best - 1e-3, best + 1e-3, 20001)).max())


def test_a_newton_overshoot_past_a_stable_root_is_not_runaway():
    """Sol's C6-3 control: Newton steps over the stable root (319.80 K, rho 0.952) to 320.91 K where rho > 1."""
    R, dyn = np.array([[30.0]]), np.array([0.0266667])
    out = runaway.classify(R, dyn, svt(400.89027), 300.0)
    assert out.status == "converged" and out.picard_it > 0
    assert out.T[0] == pytest.approx(319.799056, abs=1e-5) and out.rho == pytest.approx(0.9518, abs=1e-3)


def test_critical_scale_on_a_non_convex_table_matches_the_solver_free_boundary():
    r, dyn, Tamb = 30.0, 0.0266667, 300.0
    s_star = svt_boundary(r, dyn, Tamb)
    lo, hi, _ = runaway.critical_scale(np.array([[r]]), np.array([dyn]), svt, Tamb, lo=1.0, hi=1e4, rtol=1e-5)
    assert lo <= s_star * (1 + 1e-6) and hi >= s_star * (1 - 1e-6)
    assert runaway.classify(np.array([[r]]), np.array([dyn]), svt(1.001 * s_star), Tamb).status == "runaway"


def test_an_exhausted_confirmation_is_not_converged():
    out = runaway.classify(np.array([[30.0]]), np.array([0.0266667]), svt(400.89027), 300.0, picard_it=3)
    assert out.status == "not_converged" and out.picard_it == 3


def test_the_fixed_point_check_refuses_a_negative_operator():
    with pytest.raises(ValueError, match="R >= 0"):
        runaway.lowest_fixed_point(np.array([[-1.0]]), np.array([1.0]), svt(1.0), 300.0)


def exp_leak(c, a, t0=0.0, t1=200.0):
    """One tile, leakage c exp(a T_C) as a two-knot table (exact)."""
    t = np.array([t0, t1])
    return et.LeakModel(t, [c * np.exp(a * t)], [0], 1)


def test_a_point_just_below_the_fold_is_converged_not_a_stencil_runaway():
    """Sol RF-1: R = 1, no dynamic power, slope 0.2/K, true slope 0.999 at the root; rho with h = 0.5 reads > 1."""
    a, Tr = 0.2, 304.995
    c = 4.995 * np.exp(-a * (Tr - 273.15))
    out = runaway.classify(np.array([[1.0]]), np.array([0.0]), exp_leak(c, a), 300.0)
    assert out.status == "converged" and out.T[0] == pytest.approx(Tr, abs=1e-3)


def test_runaway_is_relative_to_T_cap():
    """Sol RF-2: constant leakage, stable root at 1001 K: runaway at the default cap, converged with a higher one."""
    lk = exp_leak(1.0, 0.0)
    R, dyn = np.array([[1.0]]), np.array([700.0])
    assert runaway.classify(R, dyn, lk, 300.0).status == "runaway"
    out = runaway.classify(R, dyn, lk, 300.0, T_cap=1100.0)
    assert out.status == "converged" and out.T[0] == pytest.approx(1001.0)


def test_an_overflow_below_the_cap_proves_nothing():
    """Sol RF-3: leakage that overflows at a temperature with a real fixed point is inconclusive, not runaway."""
    lk = et.LeakModel(np.array([0.0, 20.0]), [[1e307, 1e308]], [0], 1)
    st, _, _ = runaway.lowest_fixed_point(np.array([[1e-310]]), np.array([0.0]), lk, 300.0)
    assert st == "not_converged"


def fold_leak(s):
    """One tile, P = s exp(T - 301 K): with R = 1, no dynamic power and 300 K ambient the fold is at s = 1."""
    t = np.array([0.0, 200.0])
    return et.LeakModel(t, [s * np.exp(t + 273.15 - 301.0)], [0], 1)


def test_a_small_step_just_past_the_fold_is_not_an_operating_point():
    """Sol RF-1 (round 2): at s = 1 + 1e-10 no fixed point exists (the residual stays >= log s), yet Picard's steps
    fall under tol; without an upper solution it is not converged, and the bracket is refused."""
    R, dyn = np.array([[1.0]]), np.array([0.0])
    assert runaway.classify(R, dyn, fold_leak(1 + 1e-10), 300.0).status != "converged"
    with pytest.raises(RuntimeError):
        runaway.critical_scale(R, dyn, fold_leak, 300.0, lo=1 + 1e-10, hi=1.0001)
    lo, hi, _ = runaway.critical_scale(R, dyn, fold_leak, 300.0, lo=0.5, hi=2.2, rtol=1e-4)   # hi=2 would probe s = 1, the fold
    assert lo <= 1.0 <= hi


def test_round_off_negatives_in_R_are_projected_and_larger_ones_refused():
    """Sol RF-3 (round 2): verdicts refer to R with round-off negatives set to 0; a real negative entry is refused."""
    # Sol's control: with the signed R, tile 1's huge leakage (rise 0.5 K at 1e-13 K/W) cools tile 0 to an in-cap root
    # at (995.025, 304.995) K; clipping the -5e-13 removes that and tile 0 sits at 300 + 720 = 1020 K, above the cap
    t = np.array([0.0, 200.0])
    lk = et.LeakModel(t, [[0.0, 0.0], 4.995e13 * np.exp(0.2 * (t + 273.15 - 304.995))], [0, 1], 2)
    signed = np.array([[1.0, -5e-13], [0.0, 1e-13]])
    assert runaway.operator(signed)[0, 1] == 0.0
    a = runaway.classify(signed, np.array([720.0, 0.0]), lk, 300.0)
    b = runaway.classify(np.maximum(signed, 0), np.array([720.0, 0.0]), lk, 300.0)
    assert a.status == b.status == "runaway"
    with pytest.raises(ValueError, match="R >= 0"):
        runaway.classify(np.array([[1.0, -0.1], [0.0, 1.0]]), np.array([1.0, 0.0]), lk, 300.0)
