"""Sensor fault check for the Gaussian field model: predict each sensor from the others and drop one that disagrees.

    loo_z(gf, S, y, noise)            -> (B, m) z of each reading against its prediction from the other m - 1 sensors
    threshold(alpha, m)               -> two-sided Bonferroni z for m sensors: under the model a healthy case exceeds
                                         it on any sensor with probability at most alpha
    repair(gf, S, y, noise, z_max)    -> (field means (B, n), dropped sensor per case or -1)

The z uses the leave-one-out posterior at the left-out sensor's pixel, std^2 + noise^2 (the posterior std already holds
the truncation residual). One sensor at most is dropped per case (a single fault); the case is then re-estimated
from the other m - 1 sensors.
"""
import numpy as np
from scipy.stats import norm


def loo_z(gf, S, y, noise):
    S = np.asarray(S)
    y = np.atleast_2d(np.asarray(y, dtype=np.float64))
    z = np.empty_like(y)
    for i in range(len(S)):
        keep = np.arange(len(S)) != i
        post = gf.posterior(S[keep], y[:, keep], noise)
        z[:, i] = (y[:, i] - post.mean[:, S[i]]) / np.sqrt(post.std[S[i]] ** 2 + noise ** 2)
    return z


def threshold(alpha, m):
    if not 0 < alpha < 1 or m < 1:
        raise ValueError("need 0 < alpha < 1 and m >= 1")
    return float(norm.ppf(1 - alpha / (2 * m)))


def repair(gf, S, y, noise, z_max):
    S = np.asarray(S)
    y = np.atleast_2d(np.asarray(y, dtype=np.float64))
    if len(S) < 2:
        raise ValueError("a fault check needs at least two sensors")
    z = np.abs(loo_z(gf, S, y, noise))
    worst = z.argmax(1)
    dropped = np.where(z[np.arange(len(y)), worst] > z_max, worst, -1)
    mean = gf.posterior(S, y, noise).mean
    for i in np.unique(dropped[dropped >= 0]):
        rows = dropped == i
        keep = np.arange(len(S)) != i
        mean[rows] = gf.posterior(S[keep], y[rows][:, keep], noise).mean
    return mean, dropped
