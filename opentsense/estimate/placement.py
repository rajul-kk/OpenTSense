"""Sensor placement on a fitted GaussianField. Every function returns flat pixel indices, best first, drawn from
`allowed` (a boolean mask over pixels, default every pixel), with no repeats.

- qdeim:    QR with column pivoting on the leading modes (Drmac and Gugercin, SIAM J. Sci. Comput. 2016); beyond the
            number of modes it continues with greedy_a.
- greedy_a: A-optimal greedy: each step adds the sensor that most reduces the summed posterior variance of the field.
- greedy_d: D-optimal greedy: each step adds the sensor with the largest predictive variance over its noise, which
            maximises the log-determinant of the coefficient information (and the mutual information of a Gaussian).
- uniform_grid, random_sites: baselines.
`place` runs any of them by name."""
from __future__ import annotations

import numpy as np
from scipy.linalg import qr

from .field_model import GaussianField


def _mask(model: GaussianField, allowed):
    a = np.ones(model.n, bool) if allowed is None else np.asarray(allowed, bool).ravel()
    if a.shape != (model.n,):
        raise ValueError(f"allowed mask has {a.size} pixels, the field has {model.n}")
    return a


def _greedy(model: GaussianField, m: int, noise: float, allowed, kind: str, start=()):
    ok = _mask(model, allowed).copy()
    chosen = [int(s) for s in start]
    ok[chosen] = False
    if m - len(chosen) > ok.sum():
        raise ValueError(f"asked for {m} sensors, only {ok.sum() + len(chosen)} allowed pixels")
    Phi = model.Phi
    Sa = model.coef_cov(np.array(chosen, int), noise) if chosen else np.diag(model.lam)
    rho = noise ** 2 + model.resid
    while len(chosen) < m:
        B = Phi @ Sa                                   # row s: (Sa phi_s)^T
        pv = np.einsum("ij,ij->i", B, Phi)             # phi_s^T Sa phi_s, coefficient part of the predictive variance
        if kind == "a":
            # drop in sum_i Var(T_i) = ||Phi Sa phi_s||^2 / (pv + rho) = ||Sa phi_s||^2 / (pv + rho)  (Phi orthonormal)
            score = np.einsum("ij,ij->i", B, B) / (pv + rho)
        else:
            score = np.log1p(pv / rho)
        score[~ok] = -np.inf
        s = int(np.argmax(score))
        b = B[s]
        Sa = Sa - np.outer(b, b) / (pv[s] + rho[s])
        chosen.append(s)
        ok[s] = False
    return np.array(chosen, int)


def greedy_a(model, m, noise, allowed=None):
    return _greedy(model, m, noise, allowed, "a")


def greedy_d(model, m, noise, allowed=None):
    return _greedy(model, m, noise, allowed, "d")


def qdeim(model, m, noise, allowed=None):
    ok = _mask(model, allowed)
    k = min(m, model.r)
    idx = np.flatnonzero(ok)
    _, _, piv = qr(model.Phi[idx, :k].T, pivoting=True, mode="economic")
    first = idx[piv[:k]]
    return _greedy(model, m, noise, allowed, "a", start=first) if m > k else first


def uniform_grid(shape, m, allowed=None, offset=0.5):
    """About m sites on a regular grid over an (ny, nx) field, nearest allowed pixel to each grid point."""
    ny, nx = shape
    a = np.ones(ny * nx, bool) if allowed is None else np.asarray(allowed, bool).ravel()
    k = int(np.ceil(np.sqrt(m * nx / ny)))
    j = int(np.ceil(m / k))
    ys, xs = (np.arange(j) + offset) * ny / j, (np.arange(k) + offset) * nx / k
    yy, xx = np.divmod(np.flatnonzero(a), nx)
    out = []
    for y in ys:
        for x in xs:
            d = (yy - y) ** 2 + (xx - x) ** 2
            d[np.isin(yy * nx + xx, out)] = np.inf
            out.append(int(yy[np.argmin(d)] * nx + xx[np.argmin(d)]))
    return np.array(out[:m], int)


def random_sites(n, m, seed=0, allowed=None):
    a = np.ones(n, bool) if allowed is None else np.asarray(allowed, bool).ravel()
    return np.random.default_rng(seed).choice(np.flatnonzero(a), m, replace=False)


METHODS = {"qdeim": qdeim, "greedy_a": greedy_a, "greedy_d": greedy_d}


def place(method, model, m, noise, shape, seed=0, allowed=None):
    """m sensor pixels by `method` (a key of METHODS, "uniform" or "random") on a model of an (ny, nx) field."""
    if method == "uniform":
        return uniform_grid(shape, m, allowed)
    if method == "random":
        return random_sites(model.n, m, seed, allowed)
    if method not in METHODS:
        raise ValueError(f"unknown placement {method!r}; expected uniform, random or one of {sorted(METHODS)}")
    return METHODS[method](model, m, noise, allowed)
