"""Memory-die energy per time window and bank from a DRAM command trace (G81e step 4).

DRAMPower reports energy for a whole trace. Its core model is linear: each command type costs a fixed energy, and
background energy accrues per cycle, split by whether the device is active (any bank open, or an all-bank refresh in
its tRFCab; shared by the device) or precharged (booked per bank). The interface draws energy every cycle (clock and
command bus) plus per command and per data burst. Both facts were found by fitting DRAMPower 6.3.1 runs (11 Nov):
an idle trace with refreshes only has active background equal to (refreshes x tRFCab) x the per-cycle rate.
This module fits those coefficients once from DRAMPower runs
(`fit`) and then splits any trace into windows from its counts and durations (`windows`), which DRAMPower cannot do
without one run per window. `features` and `predict_totals` let a caller check the fitted model against DRAMPower on
traces it was not fitted on. Precharges are counted per bank actually closed (a PREA counts once per open bank).

The trace is `power.dramctl.Trace`; times are DRAM clock cycles.
"""
from dataclasses import asdict, dataclass

import numpy as np

# DRAMPower output fields modelled, and the trace feature each one is linear in
PER_BANK = {"ACT": "act", "PRE": "pre", "RD": "rd", "WR": "wr", "REF_AB": "refa", "BG_PRE": "closed"}


@dataclass
class Model:
    act: float = 0.0       # J per ACT
    pre: float = 0.0       # J per bank precharged (PRE, or PREA closing an open bank)
    rd: float = 0.0        # J per read burst (core)
    wr: float = 0.0        # J per write burst (core)
    refa: float = 0.0      # J per REFA, per bank
    closed: float = 0.0    # J per cycle with no bank open, per bank
    any_open: float = 0.0  # J per cycle with at least one bank open, for the device
    io_cycle: float = 0.0  # J per cycle, interface (controller + DRAM)
    io_cmd: float = 0.0    # J per command of any kind, interface
    io_rd: float = 0.0     # J per read burst, interface
    io_wr: float = 0.0     # J per write burst, interface

    def as_dict(self):
        return asdict(self)


def _open_intervals(tr, nb):
    """Per bank, the (start, end) cycles it is open, and every precharge of an open bank as (time, bank). PRE and
    PREA both count once per bank they close; the trace's END closes anything still open without a precharge."""
    end = int(tr.time[tr.cmd == "END"][0]) if (tr.cmd == "END").any() else int(tr.time[-1])
    start = [None] * nb
    iv = [[] for _ in range(nb)]
    closes = []
    for t, c, b in zip(tr.time.tolist(), tr.cmd.tolist(), tr.bank.tolist()):
        if c == "ACT":
            start[b] = t
        elif c in ("PRE", "PREA"):
            for k in (range(nb) if c == "PREA" else [b]):
                if start[k] is not None:
                    iv[k].append((start[k], t))
                    closes.append((t, k))
                    start[k] = None
    for k in range(nb):
        if start[k] is not None:
            iv[k].append((start[k], end))
    return iv, closes, end


def _overlap(intervals, edges):
    """Cycles each [edges[i], edges[i+1]) window overlaps a list of disjoint intervals: the difference of the
    covered length up to each edge (prefix sums, O(intervals + windows) memory)."""
    edges = np.asarray(edges, float)
    if not intervals:
        return np.zeros(len(edges) - 1)
    s, e = np.array(sorted(intervals), float).T
    done = np.concatenate([[0.0], np.cumsum(e - s)])            # covered length of the first i intervals
    k = np.searchsorted(s, edges, side="right")                 # intervals starting at or before each edge
    j = np.maximum(k - 1, 0)
    cover = np.where(k > 0, done[j] + np.clip(np.minimum(edges, e[j]) - s[j], 0, None), 0.0)
    return np.diff(cover)


def _union(iv_lists):
    pts = sorted([(a, 1) for iv in iv_lists for a, _ in iv] + [(b, -1) for iv in iv_lists for _, b in iv])
    out, depth, start = [], 0, None
    for t, d in pts:
        if depth == 0 and d == 1:
            start = t
        depth += d
        if depth == 0 and start is not None:
            if t > start:
                out.append((start, t))
            start = None
    return out


def features(tr, nb, edges=None, rfc=None):
    """Counts and durations per window (rows) and bank. With edges=None, one window covering the whole trace.
    `rfc` (cycles, default the LPDDR4-3200 tRFCab) is how long each REFA keeps the device in active background."""
    from .dramctl import LPDDR4_3200
    rfc = LPDDR4_3200["t"]["RFCab"] if rfc is None else rfc
    iv, closes, end = _open_intervals(tr, nb)
    refresh = [(int(t), int(t) + rfc) for t in tr.time[tr.cmd == "REFA"].tolist()]
    edges = np.array([0, end], float) if edges is None else np.asarray(edges, float)
    if len(tr.time) and (tr.time.min() < edges[0] or tr.time.max() > edges[-1]):
        raise ValueError(f"windows [{edges[0]:g}, {edges[-1]:g}] do not cover the trace [{tr.time.min()}, {tr.time.max()}]")
    nw = len(edges) - 1

    def window_of(t):
        return np.clip(np.searchsorted(edges, t, side="right") - 1, 0, nw - 1)

    win = window_of(tr.time)
    f = {k: np.zeros((nw, nb)) for k in ("act", "pre", "rd", "wr", "open")}
    for name, key in (("ACT", "act"), ("RD", "rd"), ("WR", "wr")):
        sel = tr.cmd == name
        np.add.at(f[key], (win[sel], tr.bank[sel]), 1)
    if closes:
        ct, cb = np.array(closes, np.int64).T
        np.add.at(f["pre"], (window_of(ct), cb), 1)
    refa = np.zeros(nw)
    np.add.at(refa, win[tr.cmd == "REFA"], 1)
    for k in range(nb):
        f["open"][:, k] = _overlap(iv[k], edges)
    open_union = _overlap(_union(iv), edges)
    any_open = _overlap(_union(iv + [refresh]), edges)
    length = np.diff(edges)
    ncmd = np.zeros(nw)
    np.add.at(ncmd, win[tr.cmd != "END"], 1)
    return {**f, "refa": refa, "any_open": any_open, "open_union": open_union, "closed": length - any_open, "length": length, "ncmd": ncmd}


def fit(runs, nb):
    """Least-squares coefficients from DRAMPower runs: [(trace, DRAMPower JSON dict)]. Returns (Model, residuals),
    where residuals gives each output field's largest relative error over the runs."""
    rows = {k: ([], []) for k in ("ACT", "PRE", "RD", "WR", "REF_AB", "BG_PRE", "bg_act", "io")}
    for tr, out in runs:
        f = features(tr, nb)
        banks = out["CoreEnergy"]["BankEnergy"]
        for field, key in PER_BANK.items():
            for k in range(nb):
                x = f[key][0] if f[key].ndim == 1 else f[key][0, k]     # refa and closed are per device
                rows[field][0].append([x]); rows[field][1].append(banks[k][field])
        rows["bg_act"][0].append([f["any_open"][0]]); rows["bg_act"][1].append(out["CoreEnergy"]["E_bg_act_shared"])
        io = out["InterfaceEnergy"]
        rows["io"][0].append([f["length"][0], f["ncmd"][0], f["rd"].sum(), f["wr"].sum()])
        rows["io"][1].append(io["controller"]["dynamicEnergy"] + io["dram"]["dynamicEnergy"])
    coef, resid = {}, {}
    for field, (X, y) in rows.items():
        X, y = np.asarray(X, float), np.asarray(y, float)
        c = np.linalg.lstsq(X, y, rcond=None)[0] if np.any(X) else np.zeros(X.shape[1])
        coef[field] = c
        rel = np.abs(X @ c - y) / np.maximum(np.abs(y), 1e-30)
        resid[field] = float(rel[np.abs(y) > 0].max()) if np.any(np.abs(y) > 0) else 0.0
    m = Model(act=coef["ACT"][0], pre=coef["PRE"][0], rd=coef["RD"][0], wr=coef["WR"][0], refa=coef["REF_AB"][0],
              closed=coef["BG_PRE"][0], any_open=coef["bg_act"][0], io_cycle=coef["io"][0], io_cmd=coef["io"][1],
              io_rd=coef["io"][2], io_wr=coef["io"][3])
    return m, resid


def windows(tr, nb, model, edges):
    """Energy (J) per window: 'bank' (nw, nb) core energy booked to each bank, 'io' (nw,) interface energy, 'total'
    (nw,). Shared active background: the time some bank is open is split by each bank's open time; the time only a
    refresh holds the device active is split evenly over all banks (an all-bank refresh works every bank)."""
    f = features(tr, nb, edges)
    m = model
    core = (m.act * f["act"] + m.pre * f["pre"] + m.rd * f["rd"] + m.wr * f["wr"]
            + m.refa * f["refa"][:, None] + m.closed * f["closed"][:, None])
    by_open = m.any_open * f["open_union"]
    refresh_only = m.any_open * (f["any_open"] - f["open_union"])
    share = np.divide(f["open"], f["open"].sum(1, keepdims=True), out=np.full_like(f["open"], 1.0 / nb),
                      where=f["open"].sum(1, keepdims=True) > 0)
    bank = core + by_open[:, None] * share + refresh_only[:, None] / nb
    io = m.io_cycle * f["length"] + m.io_cmd * f["ncmd"] + m.io_rd * f["rd"].sum(1) + m.io_wr * f["wr"].sum(1)
    return {"bank": bank, "io": io, "total": bank.sum(1) + io}


def predict_totals(tr, nb, model):
    """Whole-trace prediction in DRAMPower's terms, for checking a fitted model: per-bank core (without the shared
    active background), the shared active background, interface dynamic energy and the total."""
    f = features(tr, nb)
    m = model
    core = (m.act * f["act"] + m.pre * f["pre"] + m.rd * f["rd"] + m.wr * f["wr"]
            + m.refa * f["refa"][:, None] + m.closed * f["closed"][:, None])[0]
    bg = m.any_open * f["any_open"][0]
    io = m.io_cycle * f["length"][0] + m.io_cmd * f["ncmd"][0] + m.io_rd * f["rd"].sum() + m.io_wr * f["wr"].sum()
    return {"bank_core": core, "bg_act": bg, "io": io, "total": core.sum() + bg + io}
