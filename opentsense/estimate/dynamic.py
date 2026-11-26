"""Causal per-slot power estimation from sparse temperature readings (G79): plant identification by ERA, and two
estimators that share one power prior and one observation model, an augmented-state Kalman filter and a
quasi-static Bayesian inverse.

Time convention (G79 draft, "Time conventions"): with slot length dt and zero-based k, the input u[k] acts on
[k dt, (k+1) dt) and the reading y[k] is taken at (k+1) dt, so

    x[k+1] = A x[k] + B u[k],    y[k] = C x[k+1] + v[k].

States and readings are deviations from ambient. Inputs are power-basis coefficients c (P_bins = D c), so the plant
is identified, and estimates are made, in coefficient space; scoring maps back with the basis. A first-order sensor
lag is part of the identified plant when the identification responses were taken at the lagged sensors.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Plant:
    A: np.ndarray   # (n, n)
    B: np.ndarray   # (n, m)
    C: np.ndarray   # (p, n)

    def simulate(self, U, x0=None):
        """Readings (K, p) for inputs U (K, m): y[k] = C x[k+1]."""
        x = np.zeros(len(self.A)) if x0 is None else np.asarray(x0, float)
        Y = np.empty((len(U), len(self.C)))
        for k, u in enumerate(U):
            x = self.A @ x + self.B @ u
            Y[k] = self.C @ x
        return Y

    def markov(self, K):
        """(K, p, m): h[i] = C A^i B, the reading at slot i of a unit input at slot 0 only."""
        out, AiB = [], self.B
        for _ in range(K):
            out.append(self.C @ AiB)
            AiB = self.A @ AiB
        return np.array(out)

    def steady_gain(self):
        """(p, m): readings per unit constant input once settled, C (I - A)^-1 B."""
        return self.C @ np.linalg.solve(np.eye(len(self.A)) - self.A, self.B)


def markov_from_steps(S):
    """Markov parameters (K, p, m) from step responses S (K, p, m), S[k] = reading at slot k for a unit input held
    from slot 0 on, so S[k] = h[0] + ... + h[k]. A first row of exact zeros is the t = 0 sample, one slot early:
    refused, since ERA would absorb the shift into a plausible stable plant."""
    S = np.asarray(S, float)
    if not np.any(S[0]):
        raise ValueError("S[0] is all zero: the step responses start at t = 0, not at the end of slot 0")
    return np.concatenate([S[:1], np.diff(S, axis=0)])


def era(h, order, rows=None, rank_tol=1e-10, max_bytes=2 ** 30):
    """Eigensystem realisation of order `order` from Markov parameters h (K, p, m), with `rows` block rows and the
    rest of h as columns. Raises ValueError if `order` exceeds the Hankel matrix's numerical rank (a kept singular
    value below rank_tol times the largest), the realisation is not stable (spectral radius >= 1), or one Hankel
    matrix would exceed max_bytes (the SVD needs about four such arrays): truncate h to the identification horizon
    and check the tail and steady gain on held-out responses instead."""
    h = np.asarray(h, float)
    K, p, m = h.shape
    r = rows or (K - 1) // 2
    c = K - 1 - r
    if r < 1 or c < 1 or order > min(r * p, c * m):
        raise ValueError(f"{K} Markov parameters cannot support order {order} with {r} block rows")
    if 8 * r * p * c * m > max_bytes:
        raise ValueError(f"a {r * p} x {c * m} Hankel matrix exceeds max_bytes={max_bytes}: shorten h or rows")
    H0 = np.block([[h[i + j] for j in range(c)] for i in range(r)])
    H1 = np.block([[h[i + j + 1] for j in range(c)] for i in range(r)])
    U, s, Vt = np.linalg.svd(H0, full_matrices=False)
    if s[order - 1] <= rank_tol * s[0]:
        raise ValueError(f"ERA order {order} exceeds the numerical rank (singular value {order} is "
                         f"{s[order - 1] / s[0]:.2e} of the largest)")
    U, s, Vt = U[:, :order], s[:order], Vt[:order]
    root = np.sqrt(s)
    A = (U.T @ H1 @ Vt.T) / np.outer(root, root)
    plant = Plant(A=A, B=(root[:, None] * Vt)[:, :m], C=(U * root)[:p])
    radius = float(np.max(np.abs(np.linalg.eigvals(A))))
    if radius >= 1:
        raise ValueError(f"ERA order {order} realisation is unstable (spectral radius {radius:.6f})")
    return plant


@dataclass(frozen=True)
class PowerPrior:
    """Train-fitted power basis D (bins, r) with orthonormal columns, coefficient mean mu (r) and covariance S
    (r, r), and a mean-reverting process c[k] = mu + phi (c[k-1] - mu) + w with phi = exp(-dt / tau), which keeps
    the stationary covariance S."""
    D: np.ndarray
    mu: np.ndarray
    S: np.ndarray
    phi: float

    @classmethod
    def fit(cls, P_train, rank, dt, tau, keep=None, floor=1e-9, rank_tol=1e-10):
        """From train bin powers (N, bins): an orthonormal basis of the train mean and the rows of `keep` (q, bins),
        e.g. the rail rows, so the mean and every rail total of a projected power are exact; then the leading
        principal directions of the train variation in the complement of that span, up to `rank` columns in all;
        and the coefficients' mean and covariance. Raises ValueError if the fixed directions are dependent or
        number more than rank, or if the complement has fewer than the remaining columns above rank_tol."""
        P = np.asarray(P_train, float)
        fixed = np.vstack([P.mean(0)] + ([] if keep is None else [np.asarray(keep, float)])).T
        Q, R = np.linalg.qr(fixed)
        if len(Q.T) > rank or np.min(np.abs(np.diag(R))) <= rank_tol * np.max(np.abs(np.diag(R))):
            raise ValueError(f"the mean and keep rows give {len(Q.T)} directions, dependent or more than rank {rank}")
        rest = (P - P.mean(0)) - ((P - P.mean(0)) @ Q) @ Q.T
        _, sv, Vt = np.linalg.svd(rest, full_matrices=False)
        need = rank - len(Q.T)
        if need and (len(sv) < need or sv[need - 1] <= rank_tol * max(sv[0], np.abs(P).max())):
            raise ValueError(f"the train variation outside the fixed directions has rank below {need}")
        V = Vt[:need].T
        D = np.c_[Q, V - Q @ (Q.T @ V)]        # re-orthogonalise against the fixed span (rounding)
        c = P @ D
        return cls(D=D, mu=c.mean(0), S=np.cov(c.T).reshape(rank, rank) + floor * np.eye(rank),
                   phi=float(np.exp(-dt / tau)))

    def coefficients(self, P):
        return np.asarray(P, float) @ self.D

    def powers(self, c):
        return np.asarray(c, float) @ self.D.T


def _gaussian_update(mean, cov, H, y, noise_var):
    """Posterior of a Gaussian (mean, cov) after y = H z + v, v ~ N(0, diag(noise_var)). Joseph form: it stays
    positive semi-definite when an observation is nearly exact (a rail total near zero has a tiny 2% error)."""
    Sy = H @ cov @ H.T + np.diag(noise_var)
    G = np.linalg.solve(Sy, H @ cov).T
    I_GH = np.eye(len(mean)) - G @ H
    cov = I_GH @ cov @ I_GH.T + (G * noise_var) @ G.T
    return mean + G @ (y - H @ mean), (cov + cov.T) / 2


def _slots(Y, p, sigma_T, rail, q, rail_std):
    """Per slot: the observation vector and its noise variances, the temperatures (K, p) then, when given, the rail
    totals (K, q) with standard deviations rail_std (K, q). rail_std is the meter's stated error, not a function
    of the true total. Every value must be finite: one NaN would poison the Kalman state for all later slots."""
    Y = np.asarray(Y, float)
    if Y.ndim != 2 or Y.shape[1] != p or not np.all(np.isfinite(Y)):
        raise ValueError(f"readings must be a finite (K, {p}) array")
    var_T = np.full(p, float(sigma_T) ** 2)
    if rail is not None:
        rail, rail_std = np.asarray(rail, float), np.asarray(rail_std, float)
        if rail.shape != (len(Y), q) or rail_std.shape != rail.shape or not (
                np.all(np.isfinite(rail)) and np.all(np.isfinite(rail_std)) and np.all(rail_std > 0)):
            raise ValueError(f"rail and rail_std must be finite ({len(Y)}, {q}) arrays, with rail_std > 0")
    for k, y in enumerate(Y):
        if rail is None:
            yield np.asarray(y, float), var_T
        else:
            yield np.r_[y, rail[k]], np.r_[var_T, np.asarray(rail_std[k], float) ** 2]


def _rows(H_temp, H_rail, rail):
    if rail is None:
        return H_temp
    if H_rail is None:
        raise ValueError("rail readings given, but the estimator was built without rail_rows")
    return np.vstack([H_temp, H_rail])


class KalmanEstimator:
    """Augmented state z = [x[k+1], c[k]]: the thermal state at the end of slot k and that slot's coefficients."""

    def __init__(self, plant, prior, sigma_T, rail_rows=None, thermal_floor=1e-10):
        """rail_rows (q, bins): which bins each rail total sums (e.g. one row per die)."""
        n, m = plant.B.shape
        if m != len(prior.mu):
            raise ValueError(f"plant inputs {m} != prior rank {len(prior.mu)}")
        self.prior, self.sigma_T, self.n = prior, float(sigma_T), n
        phi, A, B = prior.phi, plant.A, plant.B
        self.F = np.block([[A, phi * B], [np.zeros((m, n)), phi * np.eye(m)]])
        self.const = np.r_[(1 - phi) * B @ prior.mu, (1 - phi) * prior.mu]
        G = np.vstack([B, np.eye(m)])
        self.Q = G @ ((1 - phi ** 2) * prior.S) @ G.T + np.diag(np.r_[np.full(n, thermal_floor), np.zeros(m)])
        self.H_temp = np.c_[plant.C, np.zeros((len(plant.C), m))]
        self.H_rail = None if rail_rows is None else np.c_[np.zeros((len(rail_rows), n)),
                                                           np.asarray(rail_rows, float) @ prior.D]

    def run(self, Y, rail=None, rail_std=None, x0=None):
        """Coefficient estimates (K, m); slot k uses readings and rail up to slot k only. x0: the thermal state at
        t = 0 (default ambient), given to every arm alike."""
        n, H = self.n, _rows(self.H_temp, self.H_rail, rail)
        z = np.r_[np.zeros(n) if x0 is None else x0, self.prior.mu]
        P = np.zeros((len(z), len(z)))
        P[n:, n:] = self.prior.S
        out = np.empty((len(Y), len(self.prior.mu)))
        for k, (obs, var) in enumerate(_slots(Y, len(self.H_temp), self.sigma_T, rail, len(H) - len(self.H_temp),
                                              rail_std)):
            z, P = _gaussian_update(self.F @ z + self.const, self.F @ P @ self.F.T + self.Q, H, obs, var)
            out[k] = z[n:]
        return out


class QuasiStaticEstimator:
    """Each slot on its own: the prior N(mu, S) conditioned on the readings through the steady response
    C (I - A)^-1 B, as if the stack had settled at that slot's power (G44's steady Bayesian inverse)."""

    def __init__(self, plant, prior, sigma_T, rail_rows=None):
        self.prior, self.sigma_T = prior, float(sigma_T)
        self.H_temp = plant.steady_gain()
        self.H_rail = None if rail_rows is None else np.asarray(rail_rows, float) @ prior.D

    def run(self, Y, rail=None, rail_std=None, x0=None):
        """Coefficient estimates (K, m). x0 is accepted for a common call and unused: the inverse has no state."""
        H = _rows(self.H_temp, self.H_rail, rail)
        return np.array([_gaussian_update(self.prior.mu, self.prior.S, H, obs, var)[0]
                         for obs, var in _slots(Y, len(self.H_temp), self.sigma_T, rail,
                                                len(H) - len(self.H_temp), rail_std)])
