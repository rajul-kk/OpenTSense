"""Memory hierarchy in front of the DRAM die (G81e step 2): CPU requests -> DRAM transactions.

A request trace is four equal-length arrays: cycle, port ("I" instruction fetch or "D" data), we (write enable) and
addr (byte address). Two hierarchies (G81e draft):

- H1: separate I- and D-caches, set-associative with LRU replacement, write-back and write-allocate. A miss fetches
  its whole line; evicting a dirty line first writes it back. Both become line-sized DRAM transactions.
- H0: no cache. Every request is one DRAM transaction of the request's own size; an upper bound on traffic.

Transactions keep the cycle of the request that caused them, in trace order (a write-back before the fill that evicted
it). Lines still dirty at the end of the trace are not written back; `Stats.dirty_at_end` counts them.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Txn:
    cycle: np.ndarray   # int64, cycle of the causing request
    addr: np.ndarray    # int64, byte address (line-aligned under H1)
    write: np.ndarray   # bool
    nbytes: np.ndarray  # int64


@dataclass
class Stats:
    accesses: int = 0
    misses: int = 0
    writebacks: int = 0
    dirty_at_end: int = 0


class Cache:
    """One set-associative, write-back, write-allocate cache with true LRU."""

    def __init__(self, size=4096, ways=2, line=64):
        if size % (ways * line) or line & (line - 1):
            raise ValueError("size must be a multiple of ways * line, and line a power of two")
        self.ways, self.line = ways, line
        self.sets = size // (ways * line)
        self.tag = np.full((self.sets, ways), -1, np.int64)
        self.dirty = np.zeros((self.sets, ways), bool)
        self.age = np.zeros((self.sets, ways), np.int64)   # last-use stamp; smallest is least recently used
        self.clock = 0
        self.stats = Stats()

    def access(self, addr, write):
        """One request. Returns DRAM operations it causes, as [(line address, is_write)] in issue order."""
        self.clock += 1
        self.stats.accesses += 1
        block = addr // self.line
        s, t = block % self.sets, block // self.sets
        hit = np.flatnonzero(self.tag[s] == t)
        ops = []
        if hit.size:
            w = int(hit[0])
        else:
            self.stats.misses += 1
            empty = np.flatnonzero(self.tag[s] < 0)
            w = int(empty[0]) if empty.size else int(np.argmin(self.age[s]))
            if self.tag[s, w] >= 0 and self.dirty[s, w]:
                self.stats.writebacks += 1
                ops.append(((int(self.tag[s, w]) * self.sets + s) * self.line, True))
            ops.append((block * self.line, False))
            self.tag[s, w], self.dirty[s, w] = t, False
        self.age[s, w] = self.clock
        if write:
            self.dirty[s, w] = True
        return ops

    def finish(self):
        self.stats.dirty_at_end = int((self.dirty & (self.tag >= 0)).sum())
        return self.stats


@dataclass
class Result:
    txn: Txn
    stats: dict = field(default_factory=dict)


def _check(cycle, port, we, addr):
    n = len(cycle)
    if not (len(port) == len(we) == len(addr) == n):
        raise ValueError("cycle, port, we and addr must have the same length")
    if n and np.any(np.diff(np.asarray(cycle)) < 0):
        raise ValueError("the trace must be in cycle order")
    bad = set(np.unique(port).tolist()) - {"I", "D"}
    if bad:
        raise ValueError(f"unknown ports {sorted(bad)}; expected I or D")


def h1(cycle, port, we, addr, size=4096, ways=2, line=64):
    """Split I/D caches in front of DRAM. Returns Result with line-sized transactions and per-cache stats."""
    _check(cycle, port, we, addr)
    caches = {"I": Cache(size, ways, line), "D": Cache(size, ways, line)}
    out_c, out_a, out_w = [], [], []
    for c, p, w, a in zip(np.asarray(cycle).tolist(), np.asarray(port).tolist(), np.asarray(we).tolist(),
                          np.asarray(addr).tolist()):
        if p == "I" and w:
            raise ValueError(f"instruction port write at cycle {c}")
        for la, lw in caches[p].access(int(a), bool(w)):
            out_c.append(c); out_a.append(la); out_w.append(lw)
    n = len(out_c)
    txn = Txn(np.asarray(out_c, np.int64), np.asarray(out_a, np.int64), np.asarray(out_w, bool), np.full(n, line, np.int64))
    return Result(txn, {p: c.finish() for p, c in caches.items()})


def h0(cycle, port, we, addr, nbytes=4):
    """No cache: one DRAM transaction per request, of `nbytes` (a 32-bit core's word)."""
    _check(cycle, port, we, addr)
    n = len(cycle)
    return Result(Txn(np.asarray(cycle, np.int64), np.asarray(addr, np.int64), np.asarray(we, bool),
                      np.full(n, nbytes, np.int64)))
