"""DRAM controller for the memory die (G81e step 3): DRAM transactions -> a timed command trace for DRAMPower.

A small in-order, open-page controller. Each transaction (`power.cache.Txn`) becomes one or more bursts; a burst to a
closed bank gets ACT first, a burst to another row in an open bank gets PRE then ACT. All-bank refresh (PREA, then
REFA) is issued every tREFI, also through idle stretches. Times are DRAM clock cycles; the CPU clock converts with
`cpu_ghz`.

Address map (row:bank:column, as in the G81e draft): a row holds nbrOfColumns x width bits; consecutive rows of the
address space rotate over the banks. `bank_salt` XORs a hash of the row into the bank index (the draft's bank-hash
seed for the noise floor); `ref_phase` offsets the first refresh.

`check` re-derives every timing rule from the trace alone, independently of the scheduler (G81e bar (v2)).

Read-to-write turnaround is approximated as RL + BL/2 + DQSCK + WPRE + 1 - WL clocks (the JEDEC LPDDR4 form, with
tDQSCK taken from the memspec). Refresh may be postponed by up to 8 x tREFI under JEDEC; the checker allows that and
the scheduler never needs it.
"""
from dataclasses import dataclass

import numpy as np

# JEDEC 8Gb LPDDR4-3200 x16, copied from DRAMSys configs/memspec/JEDEC_8Gb_LPDDR4-3200_16bit.json (the memspec G50a
# ran DRAMPower 6.3.1 with). Timings in clock cycles; tCK in seconds.
LPDDR4_3200 = {
    "arch": {"burstLength": 16, "nbrOfBanks": 8, "nbrOfColumns": 1024, "nbrOfRows": 65536, "width": 16},
    "t": {"CCD": 8, "FAW": 64, "RCD": 29, "REFI": 6246, "RFCab": 448, "RL": 28, "RAS": 68, "RPab": 34, "RPpb": 29,
          "RRD": 16, "RTP": 12, "WL": 14, "WPRE": 2, "WR": 29, "WTR": 16, "DQSCK": 6, "tCK": 6.25e-10},
}
COMMANDS = ("ACT", "PRE", "PREA", "RD", "WR", "REFA", "END")


@dataclass
class Trace:
    time: np.ndarray   # int64 DRAM cycles, non-decreasing
    cmd: np.ndarray    # str, one of COMMANDS
    bank: np.ndarray   # int64 (0 for all-bank commands)
    row: np.ndarray    # int64
    col: np.ndarray    # int64 column address of the burst

    def csv(self, spec=None):
        """DRAMPower command trace in G50a's format: time,cmd,0,0,bank,row,col[,data]. Toggle-rate modelling is off
        in G50a's config, so RD/WR carry an all-zero data word of one burst."""
        a = (spec or LPDDR4_3200)["arch"]
        zero = "0" * (a["burstLength"] * a["width"] // 4)
        lines = []
        for t, c, b, r, k in zip(self.time.tolist(), self.cmd.tolist(), self.bank.tolist(), self.row.tolist(), self.col.tolist()):
            row = f"{t},{c},0,0,{b},{r},{k}"
            lines.append(row + f",{zero}" if c in ("RD", "WR") else row)
        return "\n".join(lines) + "\n"


def geometry(spec):
    a = spec["arch"]
    burst_bytes = a["burstLength"] * a["width"] // 8
    row_bytes = a["nbrOfColumns"] * a["width"] // 8
    return burst_bytes, row_bytes, a["nbrOfBanks"]


def map_address(addr, spec, bank_salt=None):
    """Byte address -> (bank, row, column address). Row-interleaved over banks; optional XOR bank hash."""
    _, row_bytes, nb = geometry(spec)
    a = spec["arch"]
    page = addr // row_bytes
    bank, row = page % nb, (page // nb) % a["nbrOfRows"]
    if bank_salt is not None:
        bank = bank ^ ((row * 2654435761 + bank_salt) >> 7) % nb
    col = (addr % row_bytes) // (a["width"] // 8)
    return bank, row, col - col % a["burstLength"]


class _Sched:
    def __init__(self, spec, ref_phase):
        self.t, a = spec["t"], spec["arch"]
        self.BL, nb = a["burstLength"], a["nbrOfBanks"]
        self.open = [-1] * nb
        self.t_act = [-10 ** 9] * nb
        self.t_rd = [-10 ** 9] * nb
        self.t_wr = [-10 ** 9] * nb
        self.t_pre_done = [0] * nb
        self.acts = []                      # all ACT times, for tRRD and tFAW
        self.last_cmd = -1
        self.last_col = -10 ** 9
        self.last_rd_any = -10 ** 9
        self.last_wr_any = -10 ** 9
        self.t_free = 0                      # end of the last refresh
        self.next_ref = int(ref_phase)
        self.out = []

    def issue(self, t, cmd, bank=0, row=0, col=0):
        t = max(int(t), self.last_cmd + 1, self.t_free)
        self.out.append((t, cmd, bank, row, col))
        self.last_cmd = t
        return t

    def pre_ready(self, b):
        T = self.t
        return max(self.t_act[b] + T["RAS"], self.t_rd[b] + T["RTP"], self.t_wr[b] + T["WL"] + self.BL // 2 + T["WR"])

    def refresh(self, due):
        T = self.t
        t = due
        opened = [b for b, r in enumerate(self.open) if r >= 0]
        if opened:
            t = self.issue(max([t] + [self.pre_ready(b) for b in opened]), "PREA")
            for b in opened:
                self.open[b] = -1
                self.t_pre_done[b] = t + T["RPab"]
        t = self.issue(max([t] + self.t_pre_done), "REFA")
        self.t_free = t + T["RFCab"]

    def catch_up(self, now):
        while self.next_ref <= now:
            self.refresh(self.next_ref)
            self.next_ref += self.t["REFI"]

    def burst(self, arrive, b, row, col, write):
        T, BL = self.t, self.BL
        self.catch_up(max(arrive, self.last_cmd))
        if self.open[b] != row:
            if self.open[b] >= 0:
                tp = self.issue(max(arrive, self.pre_ready(b)), "PRE", b)
                self.t_pre_done[b] = tp + T["RPpb"]
                self.open[b] = -1
            ta = max(arrive, self.t_pre_done[b])
            if self.acts:
                ta = max(ta, self.acts[-1] + T["RRD"])
            if len(self.acts) >= 4:
                ta = max(ta, self.acts[-4] + T["FAW"])
            ta = self.issue(ta, "ACT", b, row)
            self.acts.append(ta)
            self.t_act[b], self.open[b] = ta, row
        tc = max(arrive, self.t_act[b] + T["RCD"], self.last_col + T["CCD"])
        if write:
            tc = max(tc, self.last_rd_any + T["RL"] + BL // 2 + T["DQSCK"] + T["WPRE"] + 1 - T["WL"])
        else:
            tc = max(tc, self.last_wr_any + T["WL"] + BL // 2 + T["WTR"])
        tc = self.issue(tc, "WR" if write else "RD", b, row, col)
        self.last_col = tc
        if write:
            self.t_wr[b] = self.last_wr_any = tc
        else:
            self.t_rd[b] = self.last_rd_any = tc


def schedule(txn, spec=LPDDR4_3200, cpu_ghz=1.0, ref_phase=0, bank_salt=None, end_cycle=None):
    """Command trace for transactions `txn` (power.cache.Txn), served in order. `end_cycle` (CPU cycles) extends the
    trace, with its refreshes, to the end of the program so that idle time is counted."""
    burst_bytes, _, _ = geometry(spec)
    cpu_to_dram = 1.0 / (cpu_ghz * 1e9) / spec["t"]["tCK"]
    s = _Sched(spec, ref_phase)
    for cyc, addr, write, nbytes in zip(txn.cycle.tolist(), txn.addr.tolist(), txn.write.tolist(), txn.nbytes.tolist()):
        arrive = int(np.ceil(cyc * cpu_to_dram))
        first = addr - addr % burst_bytes
        for a in range(first, addr + max(1, nbytes), burst_bytes):
            b, r, c = map_address(a, spec, bank_salt)
            s.burst(arrive, b, r, c, bool(write))
    end = max(s.last_cmd, int(np.ceil((end_cycle or 0) * cpu_to_dram)))
    s.catch_up(end)
    s.issue(max(end, s.last_cmd) + 10, "END")
    t, c, b, r, k = zip(*s.out)
    return Trace(np.array(t, np.int64), np.array(c), np.array(b, np.int64), np.array(r, np.int64), np.array(k, np.int64))


def check(tr, spec=LPDDR4_3200):
    """Every timing or state violation in a command trace, as readable strings; empty means the trace is legal."""
    T, a = spec["t"], spec["arch"]
    BL, nb = a["burstLength"], a["nbrOfBanks"]
    bad = []
    NEG = -10 ** 12
    open_row = [-1] * nb
    t_act, t_rd, t_wr, t_pre = [NEG] * nb, [NEG] * nb, [NEG] * nb, [NEG] * nb
    t_prea, t_ref, last_col, last_rd, last_wr, prev = NEG, NEG, NEG, NEG, NEG, NEG
    acts, refs = [], []

    def need(ok, t, what):
        if not ok:
            bad.append(f"cycle {t}: {what}")

    for t, c, b, r in zip(tr.time.tolist(), tr.cmd.tolist(), tr.bank.tolist(), tr.row.tolist()):
        need(c in COMMANDS, t, f"unknown command {c}")
        need(t > prev, t, "two commands in one cycle or out of order")
        prev = t
        need(t >= t_ref + T["RFCab"], t, f"{c} within tRFCab of REFA")
        if c == "ACT":
            need(open_row[b] < 0, t, f"ACT to open bank {b}")
            need(t >= t_pre[b] + T["RPpb"] and t >= t_prea + T["RPab"], t, f"ACT bank {b} before tRP")
            need(not acts or t >= acts[-1] + T["RRD"], t, "tRRD")
            need(len(acts) < 4 or t >= acts[-4] + T["FAW"], t, "tFAW")
            acts.append(t)
            t_act[b], open_row[b] = t, r
        elif c in ("RD", "WR"):
            need(open_row[b] >= 0, t, f"{c} to closed bank {b}")
            need(open_row[b] < 0 or open_row[b] == r, t, f"{c} to row {r} of bank {b}, but row {open_row[b]} is open")
            need(t >= t_act[b] + T["RCD"], t, f"{c} bank {b} before tRCD")
            need(t >= last_col + T["CCD"], t, "tCCD")
            if c == "RD":
                need(t >= last_wr + T["WL"] + BL // 2 + T["WTR"], t, "write-to-read (tWTR)")
                t_rd[b] = last_rd = t
            else:
                need(t >= last_rd + T["RL"] + BL // 2 + T["DQSCK"] + T["WPRE"] + 1 - T["WL"], t, "read-to-write")
                t_wr[b] = last_wr = t
            last_col = t
        elif c in ("PRE", "PREA"):
            banks = range(nb) if c == "PREA" else [b]
            for k in banks:
                if open_row[k] < 0:
                    need(c == "PREA", t, f"PRE to closed bank {k}")
                    continue
                need(t >= t_act[k] + T["RAS"], t, f"{c} bank {k} before tRAS")
                need(t >= t_rd[k] + T["RTP"], t, f"{c} bank {k} before tRTP")
                need(t >= t_wr[k] + T["WL"] + BL // 2 + T["WR"], t, f"{c} bank {k} before write recovery")
                open_row[k] = -1
                t_pre[k] = t
            if c == "PREA":
                t_prea = t
        elif c == "REFA":
            need(all(r < 0 for r in open_row), t, "REFA with a bank open")
            need(t >= t_prea + T["RPab"] and all(t >= p + T["RPpb"] for p in t_pre), t, "REFA before tRP")
            need(not refs or t - refs[-1] <= 9 * T["REFI"], t, "refresh postponed beyond 8 x tREFI")
            refs.append(t)
            t_ref = t
    return bad
