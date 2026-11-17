"""Gaussian model of a temperature field and its posterior given a few point sensors.

The prior is fitted to training fields: mean mu and covariance C = Phi diag(lam) Phi^T + diag(resid), where Phi holds the
leading r eigenvectors of the empirical covariance and resid is the per-pixel variance the r modes leave out. With r equal
to the covariance's rank this is plain Gaussian conditioning (kriging) on the empirical covariance; with smaller r it is
Bayesian gappy POD.

A reading at sensor pixels S is y = T[S] + e, e ~ N(0, noise^2 I). The truncation residual at the sensors is treated as
independent noise (variance resid[S]); that is exact for r = rank and an approximation otherwise, which the conformal step
in `calibrate` then corrects for."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.linalg import cho_factor, cho_solve

GRAM_MAX = 8192   # pixels: an 8192^2 float64 Gram matrix is 0.5 GB


@dataclass
class Posterior:
    mean: np.ndarray          # (B, n) field estimate
    std: np.ndarray           # (n,) predictive standard deviation; the same for every reading with the same sensors
    coef: np.ndarray          # (B, r) posterior mean of the mode coefficients
    mahal2: np.ndarray        # (B,) squared Mahalanobis distance of the readings under the prior predictive (OOD score)
    m: int                    # number of sensors (the chi-squared degrees of freedom of mahal2 under the model)


class GaussianField:
    def __init__(self, rank: int | None = None, energy: float | None = None):
        """rank: number of modes kept; or energy: smallest rank whose eigenvalues hold this share of the variance."""
        if (rank is None) == (energy is None):
            raise ValueError("give exactly one of rank or energy")
        self.rank, self.energy = rank, energy

    def fit(self, fields: np.ndarray | Iterable[np.ndarray]) -> "GaussianField":
        """fields: (N, n) array, or an iterable of (b, n) chunks. Up to GRAM_MAX pixels the chunks stream into the
        n x n Gram matrix (any N); above it they are stacked and the modes come from a thin SVD of the centred
        fields, O(N^2 n) time and O(N n) memory, since an n x n covariance of a large stack does not fit in RAM."""
        chunks = [fields] if isinstance(fields, np.ndarray) else fields
        N, s, G, rows = 0, None, None, []
        for x in chunks:
            x = np.asarray(x, dtype=np.float64).reshape(len(x), -1)
            if s is None:
                s = np.zeros(x.shape[1])
                G = np.zeros((x.shape[1], x.shape[1])) if x.shape[1] <= GRAM_MAX else None
            N += len(x)
            s += x.sum(0)
            if G is None:
                rows.append(x)
            else:
                G += x.T @ x
        if N < 2:
            raise ValueError("need at least two training fields")
        self.n_train = N
        self.mu = s / N
        if G is not None:
            C = (G - N * np.outer(self.mu, self.mu)) / (N - 1)
            del G
            lam, V = np.linalg.eigh(C)
            lam, V = np.clip(lam[::-1], 0, None), V[:, ::-1]
            var = np.diag(C).copy()
        else:
            Xc = np.concatenate(rows)
            del rows
            Xc -= self.mu
            var = np.einsum("ij,ij->j", Xc, Xc) / (N - 1)
            _, sv, Vt = np.linalg.svd(Xc, full_matrices=False)
            lam, V = sv ** 2 / (N - 1), Vt.T
        if self.energy is not None:
            share = np.cumsum(lam) / lam.sum()
            r = int(np.searchsorted(share, self.energy) + 1)
        else:
            r = int(self.rank)
        r = max(1, min(r, int((lam > lam[0] * 1e-12).sum())))
        self.r = r
        self.lam = lam[:r]
        self.Phi = np.ascontiguousarray(V[:, :r])
        self.var = np.clip(var, 0, None)
        self.resid = np.clip(self.var - (self.Phi ** 2) @ self.lam, 0, None)
        self.energy_kept = float(self.lam.sum() / lam.sum()) if lam.sum() > 0 else 1.0
        return self

    @property
    def n(self) -> int:
        return len(self.mu)

    def _noise(self, S: np.ndarray, noise: float) -> np.ndarray:
        return noise ** 2 + self.resid[S]

    def coef_cov(self, S: np.ndarray, noise: float) -> np.ndarray:
        """Posterior covariance of the mode coefficients given sensors S."""
        S = np.asarray(S)
        Ps = self.Phi[S]
        A = Ps.T @ (Ps / self._noise(S, noise)[:, None]) + np.diag(1.0 / self.lam)
        return cho_solve(cho_factor(A), np.eye(len(A)))   # the covariance itself is needed (std, placement)

    def posterior(self, S: np.ndarray, readings: np.ndarray, noise: float) -> Posterior:
        """S: (m,) flat pixel indices; readings: (B, m) or (m,). noise: sensor noise standard deviation (same units)."""
        S = np.asarray(S)
        y = np.atleast_2d(np.asarray(readings, dtype=np.float64))
        if y.shape[1] != len(S):
            raise ValueError(f"readings have {y.shape[1]} columns for {len(S)} sensors")
        Rinv = 1.0 / self._noise(S, noise)
        Ps = self.Phi[S]
        Sa = self.coef_cov(S, noise)
        d = y - self.mu[S]
        a = (d * Rinv) @ Ps @ Sa                                   # Sa Ps^T R^-1 d, for each row
        mean = self.mu + a @ self.Phi.T
        std = np.sqrt(np.einsum("ij,jk,ik->i", self.Phi, Sa, self.Phi) + self.resid)
        # prior predictive of the readings: K = Ps diag(lam) Ps^T + R; Woodbury for K^-1
        Kinv_d = d * Rinv - ((d * Rinv) @ Ps @ Sa @ Ps.T) * Rinv
        mahal2 = np.einsum("ij,ij->i", d, Kinv_d)
        return Posterior(mean=mean, std=std, coef=a, mahal2=mahal2, m=len(S))
