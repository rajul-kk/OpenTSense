"""Tikhonov parameter rules (G77) against brute-force matrix formulas on small random problems."""
import numpy as np
import pytest

from opentsense.estimate import regularise as rg


def problem(m=12, n=30, N=40, sigma=0.05, decay=0.7, seed=0):
    rng = np.random.default_rng(seed)
    Q1, _ = np.linalg.qr(rng.normal(size=(m, m)))
    Q2, _ = np.linalg.qr(rng.normal(size=(n, m)))
    H = Q1 @ np.diag(decay ** np.arange(m)) @ Q2.T          # graded singular values: an ill-posed but solvable case
    x = rng.normal(size=(N, n))
    b = x @ H.T + rng.normal(0, sigma, (N, m))
    return H, x, b, sigma


@pytest.mark.parametrize("shape", [(12, 30), (30, 12)])
def test_curves_match_dense_formulas(shape):
    m, n = shape
    rng = np.random.default_rng(1)
    H = rng.normal(size=(m, n)); b = rng.normal(size=(3, m))
    svd = rg.Svd.of(H)
    lams = np.array([1e-3, 0.1, 10.0])
    res2, xn2, dof = rg.curves(svd, b, lams)
    for j, lam in enumerate(lams):
        X = np.linalg.solve(H.T @ H + lam * np.eye(n), H.T @ b.T).T
        A = H @ np.linalg.solve(H.T @ H + lam * np.eye(n), H.T)
        assert np.allclose(res2[:, j], ((X @ H.T - b) ** 2).sum(1))
        assert np.allclose(xn2[:, j], (X ** 2).sum(1))
        assert dof[j] == pytest.approx(np.trace(A))
        assert np.allclose(rg.solve(svd, b, np.full(3, lam)), X)


def test_discrepancy_hits_its_target():
    H, x, b, sigma = problem()
    svd = rg.Svd.of(H)
    lam, i, lams = rg.choose("discrepancy", svd, b, sigma=sigma)
    res2, _, _ = rg.curves(svd, b, lams)
    target = H.shape[0] * sigma ** 2
    rows = np.arange(len(b))
    assert (res2[rows, i] <= target + 1e-12).all()
    nxt = np.minimum(i + 1, len(lams) - 1)
    assert ((res2[rows, nxt] > target) | (i == len(lams) - 1)).all()


@pytest.mark.parametrize("rule", ["gcv", "upre", "discrepancy", "lcurve"])
def test_rules_are_near_the_oracle(rule):
    H, x, b, sigma = problem()
    svd = rg.Svd.of(H)
    lam, _, lams = rg.choose(rule, svd, b, sigma=sigma)
    lam_o, _, _ = rg.oracle(svd, b, x, lams)
    err = ((rg.solve(svd, b, lam) - x) ** 2).sum(1)
    err_o = ((rg.solve(svd, b, lam_o) - x) ** 2).sum(1)
    err_0 = ((rg.solve(svd, b, np.full(len(b), lams[0])) - x) ** 2).sum(1)
    assert np.median(err) <= 1.5 * np.median(err_o)        # close to the best grid choice
    assert np.median(err) < np.median(err_0)               # and better than (almost) no regularisation


def test_noise_level_required():
    H, _, b, _ = problem()
    with pytest.raises(ValueError, match="sigma"):
        rg.choose("upre", rg.Svd.of(H), b)
    with pytest.raises(ValueError, match="unknown rule"):
        rg.choose("bogus", rg.Svd.of(H), b, sigma=0.1)
