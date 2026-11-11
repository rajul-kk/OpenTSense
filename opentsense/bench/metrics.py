"""Per-case metrics and their aggregation (protocol.md sections 4 and 5)."""
import numpy as np

METRICS = ("peak_err_K", "rmse_K", "hotspot_um", "pow_rel", "total_rel")


def per_case(T_true, T_hat, cell_um, P_true=None, P_hat=None):
    """Arrays (n, D) per metric. T: (n, D, ny, nx); P: (n, D, nb). Power metrics are NaN without both P."""
    n, D, ny, nx = T_true.shape
    t, h = T_true.reshape(n, D, -1), T_hat.reshape(n, D, -1)
    out = {
        "peak_err_K": np.abs(h.max(-1) - t.max(-1)),
        "rmse_K": np.sqrt(((h - t) ** 2).mean(-1)),
    }
    it, ih = t.argmax(-1), h.argmax(-1)
    out["hotspot_um"] = np.hypot(it // nx - ih // nx, it % nx - ih % nx) * cell_um
    if P_true is not None and P_hat is not None:
        out["pow_rel"] = np.linalg.norm(P_hat - P_true, axis=-1) / np.maximum(np.linalg.norm(P_true, axis=-1), 1e-30)
        out["total_rel"] = np.abs(P_hat.sum(-1) - P_true.sum(-1)) / np.maximum(np.abs(P_true.sum(-1)), 1e-30)
    else:
        out["pow_rel"] = out["total_rel"] = np.full((n, D), np.nan)
    return out


def group_stats(values, groups):
    """values (n,), groups (n,) -> per-group median and p90, as dicts."""
    med, p90 = {}, {}
    for g in np.unique(groups):
        v = values[groups == g]
        v = v[np.isfinite(v)]
        if len(v):
            med[str(g)], p90[str(g)] = float(np.median(v)), float(np.percentile(v, 90))
    return med, p90


def summary(values, groups):
    """Mean over groups of the group median and of the group p90 (each group counts once)."""
    med, p90 = group_stats(values, groups)
    if not med:
        return None
    return {"mean_group_median": float(np.mean(list(med.values()))), "mean_group_p90": float(np.mean(list(p90.values()))),
            "groups": len(med)}


def bootstrap_diff(a, b, groups, n_boot=10000, seed=0):
    """Group bootstrap of mean-over-groups(median a) - mean-over-groups(median b), paired by case.
    Returns point estimate and 95% interval."""
    ga, _ = group_stats(a, groups)
    gb, _ = group_stats(b, groups)
    keys = sorted(set(ga) & set(gb))
    d = np.array([ga[k] - gb[k] for k in keys])
    rng = np.random.default_rng(seed)
    boots = d[rng.integers(0, len(d), (n_boot, len(d)))].mean(1)
    return {"diff": float(d.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "groups": len(d), "n_boot": n_boot, "seed": seed}
