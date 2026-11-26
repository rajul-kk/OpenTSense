"""G79 step 1 controls for opentsense.estimate.dynamic on an independently solved linear thermal case: a three-node
RC chain discretised exactly, with a first-order sensor lag."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.linalg import expm

from opentsense.estimate.dynamic import (
    KalmanEstimator,
    Plant,
    PowerPrior,
    QuasiStaticEstimator,
    era,
    markov_from_steps,
)

DT = 5e-4


def rc_continuous(lag_s=None):
    """Three nodes, conductances to ambient and between neighbours, heat into nodes 0 and 2; sensors on nodes 1 and
    2: (Ac, Bc, Cc) of dT/dt = Ac T + Bc u. With lag_s, each sensor reads a first-order lag of its node."""
    Cth = np.array([2e-3, 1e-3, 1.5e-3])                       # J/K
    g_amb, g_link = np.array([0.5, 0.1, 0.3]), 0.8             # W/K
    L = np.diag(g_amb + g_link * np.array([1, 2, 1])) - g_link * (np.eye(3, k=1) + np.eye(3, k=-1))
    Ac = -L / Cth[:, None]
    Bc = np.zeros((3, 2))
    Bc[0, 0], Bc[2, 1] = 1 / Cth[0], 1 / Cth[2]
    Cc = np.eye(3)[[1, 2]]
    if lag_s is not None:                                      # states [T, s]: ds/dt = (T_sensed - s) / lag
        Ac = np.block([[Ac, np.zeros((3, 2))], [Cc / lag_s, -np.eye(2) / lag_s]])
        Bc, Cc = np.r_[Bc, np.zeros((2, 2))], np.c_[np.zeros((2, 3)), np.eye(2)]
    return Ac, Bc, Cc


def rc_chain(lag_s=None):
    """rc_continuous, discretised exactly with the input held over each slot of DT."""
    Ac, Bc, Cc = rc_continuous(lag_s)
    n = len(Ac)
    M = expm(np.block([[Ac, Bc], [np.zeros((2, n + 2))]]) * DT)
    return Plant(A=M[:n, :n], B=M[:n, n:], C=Cc)


def test_the_time_convention_matches_an_independent_ode_solution():
    """A pulse on [0, DT) then zero: Y[k] must equal the continuous solution at (k + 1) DT, not at k DT."""
    Ac, Bc, Cc = rc_continuous(1e-3)
    u0 = np.array([1.0, 0.0])
    ode = solve_ivp(lambda t, x: Ac @ x + (Bc @ u0 if t < DT else 0), (0, 4 * DT), np.zeros(len(Ac)),
                    t_eval=DT * np.arange(1, 5), rtol=1e-10, atol=1e-14, max_step=DT / 50)
    U = np.zeros((4, 2))
    U[0] = u0
    Y = rc_chain(1e-3).simulate(U)
    reference = (Cc @ ode.y).T
    assert np.allclose(Y, reference, rtol=1e-5, atol=1e-12)
    assert not np.allclose(Y[1:], reference[:-1], rtol=1e-3)   # a one-slot shift would not match


def test_the_kalman_estimate_for_slot_k_is_aligned_with_slot_k():
    """On a changing trace with near-exact readings, slot k's estimate tracks c[k], and is far from c[k-1]."""
    rng = np.random.default_rng(5)
    plant = rc_chain()
    prior, c = prior_and_trace(rng, 600, tau=1e-3)
    est = KalmanEstimator(plant, prior, 1e-7).run(plant.simulate(c))
    assert rmse(est[50:], c[50:]) < 0.02 * rmse(c[50:], c[49:-1])


@pytest.mark.parametrize("lag_s", [None, 1e-3])
def test_era_on_step_responses_recovers_the_plant(lag_s):
    true = rc_chain(lag_s)
    steps = np.stack([true.simulate(np.tile(np.eye(2)[j], (400, 1))) for j in range(2)], axis=-1)
    plant = era(markov_from_steps(steps), order=len(true.A), rows=60)
    assert np.allclose(plant.markov(300), true.markov(300), atol=1e-9 * np.abs(true.markov(1)).max())
    assert np.allclose(plant.steady_gain(), true.steady_gain(), rtol=1e-6)


def test_era_refuses_an_unstable_realisation():
    h = np.array([[[1.01 ** i]] for i in range(40)])
    with pytest.raises(ValueError, match="unstable"):
        era(h, order=1)


def test_era_refuses_an_order_above_the_numerical_rank():
    true = rc_chain()
    with pytest.raises(ValueError, match="numerical rank"):
        era(true.markov(200), order=len(true.A) + 2, rows=60)


def test_step_responses_starting_at_t0_are_refused():
    true = rc_chain()
    steps = np.stack([true.simulate(np.tile(np.eye(2)[j], (50, 1))) for j in range(2)], axis=-1)
    with pytest.raises(ValueError, match="t = 0"):
        markov_from_steps(np.concatenate([np.zeros_like(steps[:1]), steps[:-1]]))


def prior_and_trace(rng, K, tau):
    """A prior on two bins (identity basis) and a coefficient trace drawn from its own mean-reverting process."""
    D, mu, S = np.eye(2), np.array([0.4, 0.2]), np.array([[0.04, 0.01], [0.01, 0.02]])
    prior = PowerPrior(D=D, mu=mu, S=S, phi=float(np.exp(-DT / tau)))
    c, Lc = np.empty((K, 2)), np.linalg.cholesky((1 - prior.phi ** 2) * S)
    c[0] = mu
    for k in range(1, K):
        c[k] = mu + prior.phi * (c[k - 1] - mu) + Lc @ rng.standard_normal(2)
    return prior, c


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def test_the_kalman_filter_beats_the_quasi_static_inverse_on_transients():
    rng = np.random.default_rng(79)
    plant = rc_chain(1e-3)
    sigma = 0.01

    def draw():          # power changes faster than the stack settles
        prior, c = prior_and_trace(rng, 4000, tau=2e-3)
        return prior, c, plant.simulate(c) + sigma * rng.standard_normal((len(c), 2))

    _, c_cal, Y_cal = draw()                                   # the quasi-static arm's inflation, as G44 tuned it
    sigma_qs = float(np.std(Y_cal - c_cal @ plant.steady_gain().T))
    prior, c, Y = draw()
    kf = KalmanEstimator(plant, prior, sigma).run(Y)
    qs = QuasiStaticEstimator(plant, prior, sigma_qs).run(Y)
    prior_only = rmse(np.tile(prior.mu, (len(c), 1)), c)
    # a control, not the gate's evidence: the filter is clearly ahead, and both arms beat the prior mean alone
    assert rmse(kf, c) < 0.9 * rmse(qs, c)
    assert rmse(kf, c) < rmse(qs, c) < prior_only


def test_both_estimators_recover_a_settled_constant_power():
    plant, rng = rc_chain(), np.random.default_rng(1)
    prior, _ = prior_and_trace(rng, 2, tau=2e-3)
    c = np.tile([0.7, 0.1], (6000, 1))
    Y = plant.simulate(c)
    for est in (KalmanEstimator(plant, prior, 1e-6), QuasiStaticEstimator(plant, prior, 1e-6)):
        assert np.allclose(est.run(Y)[-1], c[-1], atol=1e-3)


def test_a_two_percent_rail_total_helps_both_estimators():
    rng = np.random.default_rng(7)
    plant = rc_chain(1e-3)
    sigma, rails = 0.02, np.ones((1, 2))                       # one rail summing both bins

    def draw():
        prior, c = prior_and_trace(rng, 3000, tau=2e-3)
        total = c @ rails.T
        measured = total + 0.02 * np.abs(total) * rng.standard_normal(total.shape)      # the meter: 2% of reading
        stated = np.full_like(total, 0.02 * float(np.abs(prior.mu @ rails.T).max()))   # what the filters are told
        return prior, c, plant.simulate(c) + sigma * rng.standard_normal((len(c), 2)), measured, stated

    # The quasi-static inverse treats moving temperatures as settled, so its temperature error is calibrated on a
    # separate trace (G44's inflation): without it, it trusts the biased readings over the rail.
    _, c_cal, Y_cal, _, _ = draw()
    sigma_qs = float(np.std(Y_cal - c_cal @ plant.steady_gain().T))
    prior, c, Y, total, std = draw()
    for est, s in ((KalmanEstimator, sigma), (QuasiStaticEstimator, sigma_qs)):
        without = est(plant, prior, s).run(Y)
        with_rail = est(plant, prior, s, rail_rows=rails).run(Y, total, std)
        assert rmse(with_rail, c) < rmse(without, c)
    with pytest.raises(ValueError, match="rail_rows"):
        KalmanEstimator(plant, prior, sigma).run(Y, total, std)
    bad = total.copy()
    bad[10] = np.nan
    bad_std = std.copy()
    bad_std[10] = np.inf
    for est in (KalmanEstimator, QuasiStaticEstimator):
        built = est(plant, prior, sigma, rail_rows=rails)
        for args in ((Y, bad, std), (Y, total, bad_std), (np.where(np.arange(len(Y))[:, None] == 10, np.nan, Y),
                                                          total, std), (Y[:, :1], total, std)):
            with pytest.raises(ValueError, match="finite"):
                built.run(*args)
        with pytest.raises(ValueError, match="sigma_T"):
            est(plant, prior, np.nan, rail_rows=rails).run(Y, total, std)


def test_the_prior_fit_keeps_every_rail_total_exact():
    rng = np.random.default_rng(4)
    P = np.abs(rng.normal(1.0, 0.3, size=(400, 8)) * np.linspace(0.2, 3, 8))
    rails = np.r_[[np.r_[np.ones(4), np.zeros(4)]], [np.r_[np.zeros(4), np.ones(4)]]]   # two dies of four bins
    prior = PowerPrior.fit(P, rank=4, dt=DT, tau=1e-2, keep=rails)
    projected = prior.powers(prior.coefficients(P))
    assert np.allclose(projected @ rails.T, P @ rails.T)
    assert np.allclose(prior.D.T @ prior.D, np.eye(4))
    flat = np.repeat(rng.normal(1.0, 0.1, size=(400, 2)), 4, axis=1)   # uniform within each die: the mean is a sum of rail rows
    prior = PowerPrior.fit(flat, rank=2, dt=DT, tau=1e-2, keep=rails)
    assert np.allclose(prior.powers(prior.coefficients(flat)) @ rails.T, flat @ rails.T)


def test_the_prior_fit_refuses_a_rank_the_train_variation_lacks():
    with pytest.raises(ValueError, match="rank below"):
        PowerPrior.fit(np.ones((100, 20)), rank=2, dt=DT, tau=1e-2)


def test_era_refuses_a_hankel_matrix_too_large_to_allocate():
    with pytest.raises(ValueError, match="max_bytes"):
        era(rc_chain().markov(400), order=3, max_bytes=2 ** 16)


def test_the_prior_fit_keeps_the_mean_in_a_truncated_basis():
    rng = np.random.default_rng(3)
    P = np.abs(rng.normal([1.0, 2.0, 0.5, 3.0, 1.5, 0.2], 0.2, size=(500, 6)))   # unequal bin scales
    prior = PowerPrior.fit(P, rank=2, dt=DT, tau=1e-2)
    assert np.allclose(prior.powers(prior.mu), P.mean(0))
    assert np.allclose(prior.D.T @ prior.D, np.eye(2))
