"""Estimator interface and the first entries.

An estimator has `name`, `fit(cs, idx)` (it may read everything about the training cases idx) and
`predict(pub)` -> {"T": (n, D, ny, nx), "P": (n, D, nb) or None}, where `pub` is `cases.Public` for the cases to score.
"""
import numpy as np

from ..estimate import regularise
from ..estimate.field_model import GaussianField


class Estimator:
    name = "base"

    def fit(self, cs, idx):
        return self

    def predict(self, pub):
        raise NotImplementedError


class Average(Estimator):
    """Training-mean field and power; ignores the readings. The floor every estimator must beat."""
    name = "average"

    def fit(self, cs, idx):
        self.T = cs.T[idx].mean(0)
        self.P = cs.P[idx].mean(0) if cs.has_power else None
        return self

    def predict(self, pub):
        n = len(pub.readings)
        return {"T": np.broadcast_to(self.T, (n,) + self.T.shape).copy(),
                "P": None if self.P is None else np.broadcast_to(self.P, (n,) + self.P.shape).copy()}


class FieldModel(Estimator):
    """`estimate.field_model.GaussianField` on the stacked die fields: Gaussian prior from training fields, conditioned
    on the readings. Temperature only."""
    name = "field_model"

    def __init__(self, energy=0.9999):
        self.energy = energy

    def fit(self, cs, idx):
        self.shape = cs.T.shape[1:]
        self.gf = GaussianField(energy=self.energy).fit(cs.T[idx].reshape(len(idx), -1))
        D, ny, nx = self.shape
        s = cs.sensors
        self.S = s[:, 0] * ny * nx + s[:, 1] * nx + s[:, 2]
        return self

    def predict(self, pub):
        post = self.gf.posterior(self.S, pub.readings, pub.noise_K)
        return {"T": post.mean.reshape((-1,) + self.shape), "P": None}


class LinearPower(Estimator):
    """Shared set-up for estimators that recover binned power through the linear forward model and map it back to
    temperature with R: training-mean power mu, R flattened to (D*nb, D*ny*nx), and H = R at the sensor cells."""

    def fit(self, cs, idx):
        if not cs.has_power or "R" not in cs.a:
            raise ValueError(f"{self.name} needs P and R in the case set")
        self.Ptrain = cs.P[idx].reshape(len(idx), -1).astype(np.float64)
        self.mu = self.Ptrain.mean(0)
        R = cs.R.astype(np.float64)
        self.R = R.reshape(R.shape[0], -1)                     # (D*nb, D*ny*nx)
        s = cs.sensors
        self.H = R[:, s[:, 0], s[:, 1], s[:, 2]].T              # (m, D*nb)
        self.shape, self.nb = cs.T.shape[1:], cs.P.shape[2]
        return self

    def output(self, p):
        """Power vectors (n, D*nb) -> the estimator's prediction dict."""
        D = self.shape[0]
        return {"T": (p @ self.R).reshape((-1,) + tuple(self.shape)), "P": p.reshape(-1, D, self.nb)}


class BayesPower(LinearPower):
    """Cross-die Bayesian power recovery (as G42/G73): Gaussian prior on the binned power from the training cases,
    linear forward model H = R at the sensor cells, posterior mean of the power, temperature = R applied to it.
    Needs P and R in the case set."""
    name = "bayes_power"

    def __init__(self, shrink=1e-3):
        self.shrink = shrink

    def fit(self, cs, idx):
        super().fit(cs, idx)
        C = np.cov(self.Ptrain, rowvar=False)
        self.C = C + self.shrink * np.trace(C) / len(C) * np.eye(len(C))
        return self

    def posterior_power(self, pub):
        H, C = self.H, self.C
        K = H @ C @ H.T + pub.noise_K ** 2 * np.eye(len(H))
        G = C @ H.T @ np.linalg.inv(K)                          # (D*nb, m)
        return self.mu + (pub.readings - H @ self.mu) @ G.T

    def predict(self, pub):
        return self.output(self.posterior_power(pub))


class Tikhonov(LinearPower):
    """Regularised inversion about the training-mean power (G77): p = mu + argmin ||H z - (y - H mu)||^2 + lam ||z||^2,
    with lam chosen per case by `rule` (gcv, upre, discrepancy, lcurve; see estimate.regularise). Unlike bayes_power it
    uses no training covariance, only the mean. Needs P and R in the case set."""
    SHORT = {"gcv": "gcv", "upre": "upre", "discrepancy": "dp", "lcurve": "lc"}

    def __init__(self, rule="gcv", sigma_scale=1.0):
        """sigma_scale: the noise level the rule is told, as a multiple of the true one (G77's wrong-sigma runs);
        GCV and the L-curve do not use it."""
        if rule not in self.SHORT:
            raise ValueError(f"unknown rule {rule!r}")
        if not sigma_scale > 0:
            raise ValueError("sigma_scale must be positive")
        self.rule, self.sigma_scale = rule, float(sigma_scale)
        self.name = f"ridge_{self.SHORT[rule]}" + ("" if sigma_scale == 1 else f"_s{sigma_scale:g}")

    def fit(self, cs, idx):
        super().fit(cs, idx)
        self.svd = regularise.Svd.of(self.H)
        return self

    def solve(self, pub):
        """(power vectors (n, D*nb), the per-case lambda the rule picked); G77 reports the lambdas."""
        b = pub.readings - self.H @ self.mu
        lam = regularise.choose(self.rule, self.svd, b, sigma=pub.noise_K * self.sigma_scale)[0]
        return self.mu + regularise.solve(self.svd, b, lam), lam

    def predict(self, pub):
        return self.output(self.solve(pub)[0])


class Inverted(BayesPower):
    """Deliberately wrong (G84 bar (b)): bayes_power with the sign of its update flipped, p = mu - G (y - H mu).
    Its error is about twice the prior's wherever the right update helps, so it must score worse than `average`.
    (Feeding another case's readings was tried first in the unit test and is not reliably worse than the average:
    a donor case can sit closer to the truth than the training mean does.)"""
    name = "inverted"

    def predict(self, pub):
        return self.output(2 * self.mu - self.posterior_power(pub))


REGISTRY = {c.name: c for c in (Average, FieldModel, BayesPower, Inverted)}
REGISTRY.update({f"ridge_{short}": (lambda r=rule: Tikhonov(r)) for rule, short in Tikhonov.SHORT.items()})
# G77 wrong-sigma runs: the two rules that need sigma, told half and twice the true noise level
REGISTRY.update({f"ridge_{Tikhonov.SHORT[r]}_s{k:g}": (lambda r=r, k=k: Tikhonov(r, k))
                 for r in ("upre", "discrepancy") for k in (0.5, 2.0)})
