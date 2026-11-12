"""Benchmark scorer (G84) on a small synthetic case set with a known linear operator."""
import json

import numpy as np
import pytest

from opentsense.bench import metrics, score
from opentsense.bench.cases import CaseSet


def synthetic(N=120, D=2, ny=8, nx=8, nb=4, m=6, seed=0, noise=0.01):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:ny, 0:nx]
    R = np.zeros((D * nb, D, ny, nx))
    for k in range(D * nb):                                     # smooth bumps, more spread on the other die
        d, b = divmod(k, nb)
        cy, cx = (b // 2 + 0.5) * ny / 2, (b % 2 + 0.5) * nx / 2
        for e in range(D):
            w = 1.5 if e == d else 3.0
            R[k, e] = (1.0 if e == d else 0.4) * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * w * w))
    groups = np.repeat(np.arange(N // 10), 10)
    base = rng.uniform(0.5, 2.0, (N // 10, D * nb))[groups]
    P = (base * rng.uniform(0.8, 1.2, (N, D * nb))).reshape(N, D, nb)
    T = np.tensordot(P.reshape(N, -1), R, axes=1)
    sensors = np.array([[i % D, (3 * i) % ny, (5 * i + 1) % nx] for i in range(m)])
    readings = T[:, sensors[:, 0], sensors[:, 1], sensors[:, 2]] + rng.normal(0, noise, (N, m))
    split = np.where(groups < 6, "train", np.where(groups < 8, "cal", "test"))
    return CaseSet(dict(T=T, P=P, R=R, readings=readings, sensors=sensors, noise_K=noise, split=split,
                        group=np.array([f"g{g}" for g in groups]), tag=np.where(split == "test", "unseen-workload", "seen-group"),
                        dies=np.array(["top", "bot"]), buried=np.array([False, True]), cell_um=50.0, stack_id="synthetic"))


def test_round_trip(tmp_path):
    cs = synthetic()
    cs.save(tmp_path / "c.npz")
    cs2 = CaseSet.load(tmp_path / "c.npz")
    assert cs2.sha256() == cs.sha256() and cs2.N == cs.N


def test_group_cannot_span_splits():
    cs = synthetic()
    a = dict(cs.a); a["split"] = a["split"].copy(); a["split"][0] = "test"
    with pytest.raises(ValueError, match="spans splits"):
        CaseSet(a)


def test_metrics_exact():
    T = np.zeros((1, 1, 4, 4)); T[0, 0, 1, 1] = 2.0
    H = np.zeros((1, 1, 4, 4)); H[0, 0, 3, 1] = 1.5
    m = metrics.per_case(T, H, cell_um=10.0)
    assert m["peak_err_K"][0, 0] == pytest.approx(0.5)
    assert m["hotspot_um"][0, 0] == pytest.approx(20.0)
    assert np.isnan(m["pow_rel"]).all()


def test_scorer_orders_estimators(tmp_path):
    cs = synthetic()
    cs.save(tmp_path / "c.npz")
    res = score.main([str(tmp_path / "c.npz"), "--estimators", "average,field_model,bayes_power,inverted", "--out", str(tmp_path / "o"), "--n-boot", "500"])
    s = lambda e, k: res["estimators"][e]["summary"]["bot"]["all"][k]["mean_group_median"]
    assert s("bayes_power", "peak_err_K") < s("average", "peak_err_K")
    assert s("field_model", "peak_err_K") < s("average", "peak_err_K")
    # the deliberately wrong estimator loses on field error; peak error alone is not monotone in field error
    assert s("bayes_power", "rmse_K") < s("average", "rmse_K") < s("inverted", "rmse_K")
    assert res["comparisons"]["inverted - average"]["bot"]["rmse_K"]["ci95"][0] > 0
    assert res["estimators"]["bayes_power"]["summary"]["bot"]["all"]["pow_rel"]["mean_group_median"] < 0.3
    on_disk = json.load(open(tmp_path / "o" / "result.json"))
    assert on_disk["case_set"]["sha256"] == cs.sha256()
    assert (tmp_path / "o" / "manifest.json").exists()


def test_scorer_is_deterministic(tmp_path):
    cs = synthetic()
    r1, _ = score.score(cs, ["average", "bayes_power"], n_boot=200)
    r2, _ = score.score(cs, ["average", "bayes_power"], n_boot=200)
    for r in (r1, r2):
        for e in r["estimators"].values():
            e.pop("fit_s"); e.pop("predict_s")
    assert r1 == r2


def test_tikhonov_rules_beat_the_average():
    cs = synthetic()
    names = ["average", "ridge_gcv", "ridge_upre", "ridge_dp", "ridge_lc"]
    res, _ = score.score(cs, names, n_boot=200)
    s = lambda e, k: res["estimators"][e]["summary"]["bot"]["all"][k]["mean_group_median"]
    for n in names[1:]:
        assert s(n, "rmse_K") < s("average", "rmse_K"), n


def test_bayes_refactor_keeps_numbers():
    """LinearPower split out of BayesPower: same numbers as the direct formula."""
    from opentsense.bench.estimators import BayesPower
    cs = synthetic()
    tr, te = cs.idx("train"), cs.idx("test")
    est = BayesPower().fit(cs, tr)
    P = cs.P[tr].reshape(len(tr), -1)
    mu = P.mean(0); C = np.cov(P, rowvar=False); C = C + 1e-3 * np.trace(C) / len(C) * np.eye(len(C))
    s = cs.sensors; R = cs.R.reshape(cs.R.shape[0], -1)
    H = cs.R[:, s[:, 0], s[:, 1], s[:, 2]].T
    y = cs.readings[te]
    p = mu + (y - H @ mu) @ (C @ H.T @ np.linalg.inv(H @ C @ H.T + float(cs.noise_K) ** 2 * np.eye(len(H)))).T
    out = est.predict(cs.public(te))
    assert np.allclose(out["P"].reshape(len(te), -1), p)
    assert np.allclose(out["T"].reshape(len(te), -1), p @ R)


def test_wrong_sigma_entries():
    """The wrong-sigma entries tell the rule a scaled noise level; at scale 1 they equal the plain entry."""
    from opentsense.bench.estimators import REGISTRY, Tikhonov
    assert {"ridge_upre_s0.5", "ridge_upre_s2", "ridge_dp_s0.5", "ridge_dp_s2"} <= set(REGISTRY)
    assert REGISTRY["ridge_dp_s2"]().name == "ridge_dp_s2"
    cs = synthetic()
    tr, te = cs.idx("train"), cs.idx("test")
    pub = cs.public(te)
    p1, l1 = Tikhonov("upre").fit(cs, tr).solve(pub)
    p2, l2 = Tikhonov("upre", 1.0).fit(cs, tr).solve(pub)
    assert np.array_equal(p1, p2) and np.array_equal(l1, l2)
    lam = {k: Tikhonov("discrepancy", k).fit(cs, tr).solve(pub)[1] for k in (0.5, 1.0, 2.0)}
    assert np.all(lam[0.5] <= lam[1.0]) and np.all(lam[1.0] <= lam[2.0])   # a larger sigma allows a larger lambda
    with pytest.raises(ValueError):
        Tikhonov("upre", 0.0)
