"""Sensor fault check: a stuck sensor is found and dropped; healthy readings are left alone at the stated rate."""
import numpy as np

from opentsense.estimate import fault
from opentsense.estimate.field_model import GaussianField


def fields(n_cases=400, seed=0):
    """Smooth random fields on a 12 x 12 grid: three Gaussian bumps of random height, plus a little white noise."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:12, 0:12]
    bumps = [np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / 18.0).ravel() for cx, cy in ((3, 3), (8, 4), (5, 9))]
    a = rng.uniform(0, 5, (n_cases, 3))
    return a @ np.array(bumps) + rng.normal(0, 0.01, (n_cases, 144))


S = np.array([0, 5, 11, 40, 66, 77, 100, 132, 143])
NOISE = 0.05


def setup():
    X = fields()
    gf = GaussianField(energy=0.9999).fit(X[:300])
    test = X[300:]
    y = test[:, S] + np.random.default_rng(1).normal(0, NOISE, (len(test), len(S)))
    return gf, test, y


def test_threshold_is_bonferroni():
    assert abs(fault.threshold(0.05, 1) - 1.959964) < 1e-5
    assert fault.threshold(0.01, 16) > fault.threshold(0.01, 1)


def test_healthy_readings_rarely_flagged():
    gf, _, y = setup()
    _, dropped = fault.repair(gf, S, y, NOISE, fault.threshold(0.01, len(S)))
    assert (dropped >= 0).mean() <= 0.05


def test_stuck_sensor_is_found_and_dropped():
    gf, test, y = setup()
    bad = y.copy()
    bad[:, 3] = 0.0                                   # sensor 3 reads ambient (zero rise) in every case
    mean, dropped = fault.repair(gf, S, bad, NOISE, fault.threshold(0.01, len(S)))
    hit = dropped == 3
    assert hit.mean() > 0.9
    plain = gf.posterior(S, bad, NOISE).mean
    err = lambda m: np.sqrt(((m - test) ** 2).mean(1))   # noqa: E731
    assert err(mean)[hit].mean() < 0.5 * err(plain)[hit].mean()


def test_loo_z_matches_a_direct_refit():
    gf, _, y = setup()
    z = fault.loo_z(gf, S, y[:3], NOISE)
    keep = np.arange(len(S)) != 0
    post = gf.posterior(S[keep], y[:3][:, keep], NOISE)
    direct = (y[:3, 0] - post.mean[:, S[0]]) / np.sqrt(post.std[S[0]] ** 2 + NOISE ** 2)
    assert np.allclose(z[:, 0], direct)
