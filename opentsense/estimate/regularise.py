"""Tikhonov inversion of a linear forward model with the regularisation parameter chosen per case (G77).

The problem is b = H x + e, e ~ N(0, sigma^2 I), solved about a prior mean mu:

    x(lam) = mu + argmin_z ||H z - (b - H mu)||^2 + lam ||z||^2

With the SVD H = U S V^T the solution and every quantity a parameter rule needs are sums over the singular values
with filter factors f_i = s_i^2 / (s_i^2 + lam), so all rules are evaluated on a log-spaced lambda grid at once.

Rules (each returns one lambda per case):
- gcv: generalised cross-validation, ||r||^2 / (m - dof)^2; needs no noise level.
- upre: unbiased predictive risk estimator, ||r||^2 + 2 sigma^2 dof - m sigma^2.
- discrepancy: the largest lambda with ||r||^2 <= tau m sigma^2 (Morozov).
- lcurve: the corner of (log ||r||, log ||x - mu||), as the point of largest curvature (Hansen).
- oracle: the lambda with the smallest error against a known truth; for evaluation only, never inside an estimator.
"""
from dataclasses import dataclass

import numpy as np

RULES = ("gcv", "upre", "discrepancy", "lcurve")


@dataclass
class Svd:
    U: np.ndarray   # (m, m)
    s: np.ndarray   # (k,), k = min(m, n)
    Vt: np.ndarray  # (k, n)

    @classmethod
    def of(cls, H):
        U, s, Vt = np.linalg.svd(np.asarray(H, float), full_matrices=True)   # full U: the residual needs U's null part
        return cls(U, s, Vt[:len(s)])

    @property
    def m(self):
        return self.U.shape[0]


def default_grid(s, n=80, lo=1e-10, hi=1e2):
    """Log-spaced lambda grid scaled to the largest singular value squared."""
    top = float(s[0] ** 2) if len(s) and s[0] > 0 else 1.0
    return np.logspace(np.log10(lo * top), np.log10(hi * top), n)


def curves(svd, b, lams):
    """Per case and lambda: squared residual, squared solution norm (about mu), and degrees of freedom.

    b: (N, m) data with the prior mean's prediction already removed. Returns res2 (N, L), xn2 (N, L), dof (L,)."""
    beta = b @ svd.U                                        # (N, m)
    k = len(svd.s)
    bi, bo = beta[:, :k], beta[:, k:]
    s2 = svd.s ** 2
    f = s2[None, :] / (s2[None, :] + lams[:, None])         # (L, k)
    res2 = (((1 - f)[None] * bi[:, None, :]) ** 2).sum(-1) + (bo ** 2).sum(-1, keepdims=True)
    inv_s = np.divide(1.0, svd.s, out=np.zeros_like(svd.s), where=svd.s > 0)
    xn2 = ((f * inv_s[None, :])[None] * bi[:, None, :]) ** 2
    return res2, xn2.sum(-1), f.sum(-1)


def solve(svd, b, lam):
    """Solutions about mu for one lambda per case: b (N, m), lam (N,) -> (N, n)."""
    beta = (b @ svd.U)[:, :len(svd.s)]
    s = svd.s[None, :]
    g = np.divide(s, s ** 2 + np.asarray(lam, float)[:, None], out=np.zeros((len(b), len(svd.s))), where=s > 0)
    return (g * beta) @ svd.Vt


def _lcurve_index(res2, xn2, lams):
    """Index of largest curvature of (log ||r||, log ||x||) against log lambda, per case."""
    t = np.log(lams)
    rho, eta = 0.5 * np.log(np.maximum(res2, 1e-300)), 0.5 * np.log(np.maximum(xn2, 1e-300))
    d1r, d1e = np.gradient(rho, t, axis=1), np.gradient(eta, t, axis=1)
    d2r, d2e = np.gradient(d1r, t, axis=1), np.gradient(d1e, t, axis=1)
    kappa = (d1r * d2e - d2r * d1e) / np.maximum(d1r ** 2 + d1e ** 2, 1e-300) ** 1.5
    kappa[:, [0, -1]] = -np.inf                              # one-sided differences at the ends are not trusted
    return np.argmax(kappa, axis=1)


def choose(rule, svd, b, sigma=None, lams=None, tau=1.0):
    """One lambda per case for `rule`. Returns (lam (N,), index into the grid (N,), the grid)."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}; expected one of {RULES}")
    lams = default_grid(svd.s) if lams is None else np.asarray(lams, float)
    res2, xn2, dof = curves(svd, b, lams)
    m = svd.m
    if rule in ("upre", "discrepancy") and sigma is None:
        raise ValueError(f"{rule} needs the noise level sigma")
    if rule == "gcv":
        i = np.argmin(res2 / np.maximum(m - dof, 1e-12)[None, :] ** 2, axis=1)
    elif rule == "upre":
        i = np.argmin(res2 + 2 * sigma ** 2 * dof[None, :] - m * sigma ** 2, axis=1)
    elif rule == "discrepancy":
        ok = res2 <= tau * m * sigma ** 2                    # res2 grows with lambda: take the largest feasible one
        i = np.where(ok.any(1), len(lams) - 1 - np.argmax(ok[:, ::-1], axis=1), 0)
    else:
        i = _lcurve_index(res2, xn2, lams)
    return lams[i], i, lams


def oracle(svd, b, x_true_minus_mu, lams=None, weight=None):
    """The grid lambda with the smallest (weighted) squared error against the truth, per case. Evaluation only."""
    lams = default_grid(svd.s) if lams is None else np.asarray(lams, float)
    err = np.stack([((solve(svd, b, np.full(len(b), l)) - x_true_minus_mu) ** 2 * (1 if weight is None else weight)).sum(1)
                    for l in lams], axis=1)
    i = np.argmin(err, axis=1)
    return lams[i], i, lams
