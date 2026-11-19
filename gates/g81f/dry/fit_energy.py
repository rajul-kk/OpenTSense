"""G81f dry check (not scored): refit the per-window energy model on calibration traffic whose features vary
independently, and test it on held-out traces from regimes the calibration does not contain.

G81e's fit had 4 calibration traces for the 4 interface coefficients (exactly determined, so its 2e-15 residual
showed nothing) and all random-address traffic (commands a fixed multiple of bursts). Here the calibration has 12
traces over four regimes: random lines, sequential streams (row hits), strided lines, and a refresh-only trace, at
several read/write mixes and loads. Held out: 6 traces mixing the regimes in proportions the calibration lacks, plus a
long sequential read stream. Runs DRAMPower 6.3.1 in WSL through G81e's dry helper (unchanged).

Usage (repo root): python gates/g81f/dry/fit_energy.py <out.json>
"""
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g81e", "dry")]
import fit_energy as g81e  # noqa: E402
from opentsense.power import cache, dramctl, dramenergy  # noqa: E402

CYCLES = 2_000_000


def traffic(seed, n, wfrac, kind, salt=None, phase=0):
    """H1 traffic of one regime: 'random' lines, 'seq' streams (consecutive words), 'stride' (every 4th line)."""
    rng = np.random.default_rng(seed)
    cyc = np.sort(rng.integers(0, CYCLES, n))
    base = 1 << 20
    if kind == "random":
        addr = rng.integers(base, base + (1 << 18), n)
    elif kind == "seq":
        addr = base + 4 * np.arange(n) % (1 << 22)
    else:
        addr = base + 256 * np.arange(n) % (1 << 22)
    addr = addr & ~3
    we = rng.random(n) < wfrac
    tr = dramctl.schedule(cache.h1(cyc, np.full(n, "D"), we, addr).txn, bank_salt=salt, ref_phase=phase,
                          end_cycle=CYCLES)
    bad = dramctl.check(tr)
    if bad:
        raise RuntimeError(f"illegal trace (seed {seed}): {bad[:3]}")
    return tr


def mixed(seed, parts):
    """One trace that concatenates regimes in time: parts = [(kind, n, wfrac)], each in its own share of the run."""
    rng = np.random.default_rng(seed)
    cyc, addr, we, t0 = [], [], [], 0
    span = CYCLES // len(parts)
    for i, (kind, n, wfrac) in enumerate(parts):
        c = np.sort(rng.integers(t0, t0 + span, n)); t0 += span
        base = (1 << 20) + i * (1 << 22)
        a = {"random": base + rng.integers(0, 1 << 18, n), "seq": base + 4 * np.arange(n),
             "stride": base + 256 * np.arange(n)}[kind] & ~3
        cyc.append(c); addr.append(a); we.append(rng.random(n) < wfrac)
    c, a, w = (np.concatenate(x) for x in (cyc, addr, we))
    tr = dramctl.schedule(cache.h1(c, np.full(len(c), "D"), w, a).txn, end_cycle=CYCLES)
    assert not dramctl.check(tr)
    return tr


def compare(tr, model):
    o = g81e.drampower(tr)
    p = dramenergy.predict_totals(tr, model)
    io = o["InterfaceEnergy"]["controller"]["dynamicEnergy"] + o["InterfaceEnergy"]["dram"]["dynamicEnergy"]
    return {"total_rel_err": abs(p["total"] - o["TotalEnergy"]) / o["TotalEnergy"],
            "io_rel_err": abs(p["io"] - io) / io, "commands": int(len(tr.time)),
            "bursts": int(np.isin(tr.cmd, ("RD", "WR")).sum()), "acts": int((tr.cmd == "ACT").sum())}


def main(out):
    g81e.check_memspec()
    empty = cache.Txn(*(np.zeros(0, t) for t in (np.int64, np.int64, bool, np.int64)))
    cal = [dramctl.schedule(empty, end_cycle=CYCLES)]
    for i, (kind, n, w) in enumerate([("random", 20000, 0.0), ("random", 20000, 1.0), ("random", 8000, 0.3),
                                      ("seq", 200000, 0.0), ("seq", 200000, 1.0), ("seq", 80000, 0.3),
                                      ("stride", 20000, 0.0), ("stride", 20000, 1.0), ("stride", 8000, 0.5),
                                      ("seq", 400000, 0.1), ("random", 30000, 0.6)]):
        cal.append(traffic(100 + i, n, w, kind))
    runs = [(t, g81e.drampower(t)) for t in cal]
    model, resid = dramenergy.fit(runs)
    X = np.array([dramenergy._io_columns(dramenergy.features(t))[0] for t in cal])
    held = {f"mixed_{s}": mixed(s, parts) for s, parts in [
        (201, [("seq", 150000, 0.0), ("random", 10000, 0.3)]), (202, [("stride", 15000, 0.2), ("seq", 50000, 0.5)]),
        (203, [("random", 5000, 0.0), ("seq", 300000, 0.0), ("stride", 5000, 1.0)]),
        (204, [("seq", 20000, 0.9), ("random", 25000, 0.1)]), (205, [("stride", 30000, 0.0)] * 2),
        (206, [("seq", 100000, 0.2), ("stride", 10000, 0.2), ("random", 10000, 0.2)])]}
    held["seq_long"] = traffic(300, 600000, 0.0, "seq", salt=7, phase=1234)
    res = {"model": model.as_dict(), "fit_max_rel_residual": resid, "calibration_traces": len(cal),
           "io_condition_number": float(np.linalg.cond(X / np.linalg.norm(X, axis=0))),
           "held_out": {k: compare(t, model) for k, t in held.items()}}
    res["held_out_worst_total_rel_err"] = max(h["total_rel_err"] for h in res["held_out"].values())
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("fit_max_rel_residual", "io_condition_number", "held_out_worst_total_rel_err")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
