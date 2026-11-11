import os

import numpy as np
import pytest

from opentsense.estimate import GaussianField, calibrate, icthermbench, placement

NY = NX = 12


def smooth_fields(N, seed=0, shift=0.0, scale=1.0):
    """Fields drawn from a known Gaussian: a smooth squared-exponential covariance on a 12 x 12 grid, mean 300 K."""
    yy, xx = np.divmod(np.arange(NY * NX), NX)
    d2 = (yy[:, None] - yy[None]) ** 2 + (xx[:, None] - xx[None]) ** 2
    C = 4.0 * np.exp(-d2 / (2 * 3.0 ** 2)) + 1e-6 * np.eye(NY * NX)
    L = np.linalg.cholesky(C)
    z = np.random.default_rng(seed).standard_normal((N, NY * NX))
    return 300.0 + shift + scale * z @ L.T


def test_fit_recovers_mean_and_variance():
    X = smooth_fields(4000)
    g = GaussianField(rank=NY * NX).fit(X)
    assert abs(g.mu.mean() - 300) < 0.1
    assert np.allclose(g.var, 4.0, rtol=0.1)
    assert g.resid.max() < 1e-6 * 4                      # full rank: nothing left out


def test_streamed_fit_matches_batch():
    X = smooth_fields(600)
    a = GaussianField(rank=10).fit(X)
    b = GaussianField(rank=10).fit(X[i:i + 100] for i in range(0, 600, 100))
    assert np.allclose(a.mu, b.mu) and np.allclose(a.lam, b.lam)
    assert np.allclose(np.abs(a.Phi.T @ b.Phi), np.eye(10), atol=1e-6)


def test_energy_rank():
    g = GaussianField(energy=0.99).fit(smooth_fields(2000))
    assert 0.99 <= g.energy_kept and g.r < NY * NX


def test_exact_in_span_noiseless():
    """A field in the span of the r modes is recovered exactly from r well-placed noiseless sensors."""
    g = GaussianField(rank=6).fit(smooth_fields(2000))
    T = g.mu + g.Phi @ np.array([3.0, -2.0, 1.0, 0.5, -0.5, 0.2])
    g.resid[:] = 0.0                                      # make the model exactly rank 6
    S = placement.qdeim(g, 6, noise=0.0)
    p = g.posterior(S, T[S], noise=1e-9)
    assert np.abs(p.mean[0] - T).max() < 1e-4


def test_placements_distinct_and_allowed():
    g = GaussianField(rank=20).fit(smooth_fields(1500))
    allowed = np.zeros(NY * NX, bool); allowed[: NY * NX // 2] = True
    for f in (placement.qdeim, placement.greedy_a, placement.greedy_d):
        S = f(g, 30, 0.1, allowed)
        assert len(set(S)) == 30 and allowed[S].all()
    assert len(set(placement.uniform_grid((NY, NX), 16))) == 16


def test_greedy_beats_random():
    g = GaussianField(rank=NY * NX).fit(smooth_fields(3000))
    tot = lambda S: (g.posterior(S, g.mu[S], 0.1).std ** 2).sum()
    Sa = placement.greedy_a(g, 8, 0.1)
    rnd = [tot(placement.random_sites(g.n, 8, seed=s)) for s in range(20)]
    assert tot(Sa) <= min(rnd)


def test_greedy_a_variance_update_matches_direct():
    """The rank-one update inside the greedy search equals a fresh posterior with the chosen sensors."""
    g = GaussianField(rank=15).fit(smooth_fields(1500))
    S = placement.greedy_a(g, 5, 0.2)
    p = g.posterior(S, g.mu[S], 0.2)
    Sa = g.coef_cov(S, 0.2)
    assert np.allclose(p.std ** 2, np.einsum("ij,jk,ik->i", g.Phi, Sa, g.Phi) + g.resid)


def test_gaussian_and_conformal_coverage_in_distribution():
    rng = np.random.default_rng(1)
    g = GaussianField(rank=NY * NX).fit(smooth_fields(4000, seed=2))
    S = placement.greedy_a(g, 6, 0.1)
    def post(X):
        return g.posterior(S, X[:, S] + rng.normal(0, 0.1, (len(X), len(S))), 0.1)
    Xc, Xt = smooth_fields(1500, seed=3), smooth_fields(1500, seed=4)
    pc, pt = post(Xc), post(Xt)
    cb = calibrate.Calibrator(0.1).fit(Xc, pc.mean, pc.std)
    r = cb.evaluate(Xt, pt.mean, pt.std)
    assert abs(r["cover_gauss"] - 0.9) < 0.02           # the model is right, so the Gaussian band is calibrated
    assert r["cover_marg"] >= 0.88 and r["cover_sim"] >= 0.87
    # the readings' Mahalanobis distance is chi-squared with m degrees of freedom under the model
    assert abs(np.mean(pt.mahal2) - len(S)) < 0.3


def test_ood_shift_is_flagged_and_undercovers():
    rng = np.random.default_rng(5)
    g = GaussianField(rank=NY * NX).fit(smooth_fields(4000, seed=6))
    S = placement.greedy_a(g, 6, 0.1)
    post = lambda X: g.posterior(S, X[:, S] + rng.normal(0, 0.1, (len(X), len(S))), 0.1)
    Xc, Xi, Xo = smooth_fields(1000, seed=7), smooth_fields(1000, seed=8), smooth_fields(1000, seed=9, shift=3.0, scale=2.0)
    pc, pi, po = post(Xc), post(Xi), post(Xo)
    cb = calibrate.Calibrator(0.1).fit(Xc, pc.mean, pc.std)
    assert cb.evaluate(Xo, po.mean, po.std)["cover_sim"] < cb.evaluate(Xi, pi.mean, pi.std)["cover_sim"] - 0.2
    rep = calibrate.ood_report(pc.mahal2, pi.mahal2, po.mahal2, len(S))
    assert rep["auroc"] > 0.9 and rep["false_alarm_id"] < 0.1


def test_conformal_q_finite_sample():
    s = np.arange(1, 10)                                  # n = 9, alpha 0.1 -> ceil(10 * 0.9) = 9th smallest
    assert calibrate.conformal_q(s, 0.1) == 9
    assert calibrate.conformal_q(s, 0.05) == float("inf")


def test_auroc():
    assert calibrate.auroc([0, 1, 2], [3, 4]) == 1.0
    assert calibrate.auroc([1, 1], [1, 1]) == 0.5


def test_split_matches_benchmark():
    sp = icthermbench.split_indices(15000)
    assert (sp["train"].stop, sp["val"].stop) == (10800, 12000)
    sp = icthermbench.split_indices(5000)
    assert (sp["train"].stop, sp["val"].stop) == (3600, 4000)


def test_duplicate_mask_orders_splits():
    T = np.zeros((10, 2, 2), np.float32)
    T[:, 0, 0] = np.arange(10)
    T[9] = T[0]; T[8] = T[8 - 1]                          # test copies of a train field and of another test field
    lv = icthermbench.Level("x", T, np.array(["c"] * 10), {"train": slice(0, 6), "val": slice(6, 7), "test": slice(7, 10)}, "")
    assert list(np.flatnonzero(icthermbench.duplicate_mask(lv))) == [8, 9]


@pytest.mark.skipif(not os.path.isdir(os.path.join(icthermbench.DEFAULT_ROOT, "level5_steady")), reason="IC-ThermBench not present")
def test_level5_cases_from_manifest():
    pytest.importorskip("h5py")
    lv = icthermbench.load("level5", limit=10)
    assert lv.case_source == "manifest" and lv.T.shape == (10, 64, 64)
    c, _ = icthermbench._cases(os.path.join(icthermbench.DEFAULT_ROOT, "level5_steady"), "level5", 5000)
    assert set(c[lv.split["test"]]) == {"Case20"} and set(c[lv.split["val"]]) == {"Case19"}
