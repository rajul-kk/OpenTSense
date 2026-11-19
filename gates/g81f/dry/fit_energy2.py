"""G81f dry check 2 (not scored; after review of dry check 1, which stays as run in fit_energy.json).

Check 1's held-out traces were time-mixes of its calibration regimes at one length (2M cycles) and modest density,
scored on the whole-trace path. Here:
- calibration: 16 traces over regime (random, sequential, strided lines; refresh only), read/write mix, load and
  length (0.4M to 5M CPU cycles), with bursts arriving uniformly or packed into short dense phases;
- held out: 6 traces outside the calibration's range on purpose: denser packed sequential phases than any
  calibration trace (up to ~150k bursts per 1M cycles, nsichneu's density), lengths 0.3M and 6M cycles, and two
  regimes interleaved request by request (not in time blocks);
- scoring: the sum of G81e step 2's per-window energies (`window_energy`, the path v3 scores) against DRAMPower, with
  the interface error reported separately from the total.

Usage (repo root): python gates/g81f/dry/fit_energy2.py <out.json>
"""
import importlib.util
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g81e", "dry")]
import fit_energy as g81e  # noqa: E402
from opentsense.power import cache, dramctl, dramenergy  # noqa: E402

spec = importlib.util.spec_from_file_location("g81e_run", os.path.join("gates", "g81e", "step2", "run.py"))
step2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step2)


def addresses(kind, n, rng, base):
    return {"random": base + rng.integers(0, 1 << 18, n), "seq": base + 4 * np.arange(n),
            "stride": base + 256 * np.arange(n)}[kind] & ~3


def trace(seed, cycles, parts, packed=0.0):
    """parts = [(kind, n, wfrac)], interleaved request by request; packed = share of the run the requests are squeezed
    into (dense phases of 20k cycles), 0 = uniform."""
    rng = np.random.default_rng(seed)
    c, a, w = [], [], []
    for i, (kind, n, wfrac) in enumerate(parts):
        if packed:
            phases = rng.choice(cycles // 20000, max(1, int(packed * cycles / 20000)), replace=False)
            cyc = np.sort(rng.choice(phases, n) * 20000 + rng.integers(0, 20000, n))
        else:
            cyc = np.sort(rng.integers(0, cycles, n))
        c.append(cyc); a.append(addresses(kind, n, rng, (1 << 20) + i * (1 << 25))); w.append(rng.random(n) < wfrac)
    order = np.argsort(np.concatenate(c), kind="stable")
    C, A, W = (np.concatenate(x)[order] for x in (c, a, w))
    tr = dramctl.schedule(cache.h1(C, np.full(len(C), "D"), W, A).txn, end_cycle=cycles)
    bad = dramctl.check(tr)
    if bad:
        raise RuntimeError(f"illegal trace (seed {seed}): {bad[:3]}")
    return tr, cycles


def compare(tr, cycles, model):
    o = g81e.drampower(tr)
    e, _ = step2.window_energy(tr, model, cycles)
    io_model = float(e["io"].sum())
    io = o["InterfaceEnergy"]["controller"]["dynamicEnergy"] + o["InterfaceEnergy"]["dram"]["dynamicEnergy"]
    bursts = int(np.isin(tr.cmd, ("RD", "WR")).sum())
    return {"total_rel_err": abs(float(e["total"].sum()) - o["TotalEnergy"]) / o["TotalEnergy"],
            "io_rel_err": abs(io_model - io) / io, "io_share": io / o["TotalEnergy"], "cycles": cycles,
            "bursts": bursts, "bursts_per_Mcycle": bursts / cycles * 1e6, "acts": int((tr.cmd == "ACT").sum())}


def main(out):
    g81e.check_memspec()
    empty = cache.Txn(*(np.zeros(0, t) for t in (np.int64, np.int64, bool, np.int64)))
    specs = [(400_000, [("random", 4000, 0.0)], 0), (400_000, [("seq", 60000, 0.3)], 0.3),
             (1_000_000, [("random", 15000, 1.0)], 0), (1_000_000, [("seq", 150000, 0.0)], 0.4),
             (1_000_000, [("stride", 12000, 0.5)], 0.2), (2_000_000, [("seq", 200000, 1.0)], 0),
             (2_000_000, [("random", 20000, 0.3)], 0.5), (2_000_000, [("stride", 30000, 0.0)], 0),
             (2_000_000, [("seq", 300000, 0.1)], 0.3), (5_000_000, [("random", 40000, 0.6)], 0),
             (5_000_000, [("seq", 600000, 0.2)], 0.2), (5_000_000, [("stride", 50000, 0.9)], 0.4),
             (1_000_000, [("seq", 100000, 0.5)], 0), (3_000_000, [("random", 8000, 0.0)], 0.1),
             (3_000_000, [("stride", 20000, 0.2)], 0)]
    cal = [(dramctl.schedule(empty, end_cycle=1_500_000), 1_500_000)]
    cal += [trace(400 + i, cyc, parts, packed) for i, (cyc, parts, packed) in enumerate(specs)]
    model, resid = dramenergy.fit([(t, g81e.drampower(t)) for t, _ in cal])
    X = np.array([dramenergy._io_columns(dramenergy.features(t))[0] for t, _ in cal])
    held = {"dense_seq_1M": trace(501, 1_000_000, [("seq", 300000, 0.0)], 0.15),
            "dense_seq_rw_1M": trace(502, 1_000_000, [("seq", 250000, 0.4)], 0.2),
            "short_mixed_0p3M": trace(503, 300_000, [("seq", 30000, 0.0), ("random", 3000, 0.5)], 0.3),
            "long_mixed_6M": trace(504, 6_000_000, [("seq", 500000, 0.1), ("stride", 30000, 0.3)], 0.1),
            "interleaved_2M": trace(505, 2_000_000, [("seq", 200000, 0.2), ("random", 20000, 0.2), ("stride", 10000, 0.0)], 0),
            "dense_stride_1M": trace(506, 1_000_000, [("stride", 60000, 0.1)], 0.1)}
    res = {"model": model.as_dict(), "fit_max_rel_residual": resid, "calibration_traces": len(cal),
           "calibration_max_bursts_per_Mcycle": max(int(np.isin(t.cmd, ("RD", "WR")).sum()) / c * 1e6 for t, c in cal),
           "io_condition_number": float(np.linalg.cond(X / np.linalg.norm(X, axis=0))),
           "held_out": {k: compare(t, c, model) for k, (t, c) in held.items()}}
    res["held_out_worst_total_rel_err"] = max(h["total_rel_err"] for h in res["held_out"].values())
    res["held_out_worst_io_rel_err"] = max(h["io_rel_err"] for h in res["held_out"].values())
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("model", "held_out")}, indent=1))
    for k, h in res["held_out"].items():
        print(f"{k:18s} total {h['total_rel_err']:.2e} io {h['io_rel_err']:.2e} io share {h['io_share']:.2f} "
              f"bursts/Mcyc {h['bursts_per_Mcycle']:.0f}")


if __name__ == "__main__":
    main(sys.argv[1])
