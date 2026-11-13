"""Calibrated uncertainty for a field estimate, and an out-of-distribution score from the sensor readings alone.

Two bands, both of the form mean +- q * std (std from the Gaussian posterior):
- marginal:     each pixel is inside with probability >= 1 - alpha; q is the conformal quantile of the pooled per-pixel
                scores |T - mean| / std over the calibration fields.
- simultaneous: the whole field is inside with probability >= 1 - alpha; q is the conformal quantile of the per-field
                score max_i |T_i - mean_i| / std_i.
Split conformal (Vovk et al. 2005; Lei et al. 2018): the guarantee needs the calibration and test fields to be
exchangeable. Across packages it is not guaranteed, which is what `ood_report` measures.
For the marginal band the pooled pixels of one field are not independent, so its guarantee is over a random pixel of a
random field, and the finite-sample correction uses the number of fields."""
from __future__ import annotations

import numpy as np
from scipy.stats import chi2, norm


def conformal_q(scores: np.ndarray, alpha: float, n_exch: int | None = None) -> float:
    """The ceil((n + 1)(1 - alpha))-th smallest score, n = n_exch or len(scores); inf if that exceeds the count."""
    s = np.sort(np.asarray(scores, dtype=np.float64).ravel())
    n = len(s) if n_exch is None else n_exch
    level = np.ceil((n + 1) * (1 - alpha)) / n
    if level > 1:
        return float("inf")
    return float(np.quantile(s, level, method="higher"))


def scores(truth: np.ndarray, mean: np.ndarray, std: np.ndarray):
    """Per-pixel normalised errors (B, n) and the per-field maximum (B,)."""
    z = np.abs(truth - mean) / np.maximum(std, 1e-12)        # a noiseless sensor pixel has std 0
    return z, z.max(axis=1)


class Calibrator:
    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha

    def fit(self, truth, mean, std):
        z, zmax = scores(truth, mean, std)
        self.q_marg = conformal_q(z, self.alpha, n_exch=len(z))
        self.q_sim = conformal_q(zmax, self.alpha)
        self.q_gauss = float(norm.ppf(1 - self.alpha / 2))
        return self

    def evaluate(self, truth, mean, std) -> dict:
        z, zmax = scores(truth, mean, std)
        err = truth - mean
        return dict(n=int(len(z)),
                    rmse_K=float(np.sqrt(np.mean(err ** 2))), mae_K=float(np.mean(np.abs(err))),
                    max_abs_K=float(np.abs(err).max()), p99_field_max_K=float(np.quantile(np.abs(err).max(1), 0.99)),
                    peak_err_K=float(np.mean(np.abs(truth.max(1) - mean.max(1)))),
                    cover_gauss=float(np.mean(z <= self.q_gauss)), cover_marg=float(np.mean(z <= self.q_marg)),
                    cover_sim=float(np.mean(zmax <= self.q_sim)),
                    width_marg_K=float(2 * self.q_marg * np.mean(std)), width_sim_K=float(2 * self.q_sim * np.mean(std)),
                    q_marg=self.q_marg, q_sim=self.q_sim)


def auroc(neg: np.ndarray, pos: np.ndarray) -> float:
    """P(score of a positive > score of a negative), ties counted half (Mann-Whitney)."""
    neg, pos = np.asarray(neg, float), np.asarray(pos, float)
    allv = np.concatenate([neg, pos])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / cnt)[inv]
    rp = ranks[len(neg):].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def ood_report(mahal2_cal, mahal2_id, mahal2_ood, m: int, alpha: float = 0.05) -> dict:
    """OOD flag from the readings' Mahalanobis distance. Threshold: the conformal (1 - alpha) quantile of the calibration
    scores (so the in-distribution false-alarm rate is about alpha), and the chi-squared(m) quantile for reference."""
    thr = conformal_q(mahal2_cal, alpha)
    return dict(threshold=thr, chi2_threshold=float(chi2.ppf(1 - alpha, m)),
                false_alarm_id=float(np.mean(np.asarray(mahal2_id) > thr)),
                detect_ood=float(np.mean(np.asarray(mahal2_ood) > thr)),
                auroc=auroc(mahal2_id, mahal2_ood),
                median_id=float(np.median(mahal2_id)), median_ood=float(np.median(mahal2_ood)))
