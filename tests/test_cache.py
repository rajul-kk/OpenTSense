"""G81e memory hierarchy: hits, misses, LRU, write-back, and the H0/H1 transaction streams."""
import numpy as np
import pytest

from opentsense.power import cache


def test_sequential_stream_misses_once_per_line():
    c = cache.Cache(size=4096, ways=2, line=64)
    for a in range(0, 8192, 4):                              # 8 KB of word reads through a 4 KB cache
        c.access(a, False)
    s = c.finish()
    assert s.accesses == 2048 and s.misses == 128            # one compulsory miss per 64 B line
    assert s.writebacks == 0


def test_lru_keeps_the_recent_line():
    c = cache.Cache(size=256, ways=2, line=64)               # 2 sets; addresses 0, 128, 256 share set 0
    for a in (0, 128, 0, 256, 0):
        c.access(a, False)
    # 0 miss, 128 miss, 0 hit, 256 miss evicts 128 (LRU), 0 hit
    assert c.stats.misses == 3


def test_dirty_eviction_writes_back_before_the_fill():
    c = cache.Cache(size=128, ways=1, line=64)               # 2 sets, direct mapped
    assert c.access(0, True) == [(0, False)]                 # write miss: allocate (fill), mark dirty
    ops = c.access(128, False)                               # same set: evict dirty line 0
    assert ops == [(0, True), (128, False)]
    assert c.access(128, False) == []                        # hit
    assert c.finish().dirty_at_end == 0


def test_dirty_lines_left_at_the_end_are_counted():
    c = cache.Cache(size=128, ways=1, line=64)
    c.access(0, True); c.access(64, True)
    assert c.finish().dirty_at_end == 2


def test_h1_splits_ports_and_keeps_cycles():
    cyc = np.array([0, 1, 2, 3])
    port = np.array(["I", "D", "I", "D"])
    we = np.array([False, True, False, False])
    addr = np.array([0, 0, 4, 4])                            # same line, but in separate caches
    r = cache.h1(cyc, port, we, addr)
    assert list(r.txn.cycle) == [0, 1] and list(r.txn.addr) == [0, 0] and not r.txn.write.any()
    assert (r.txn.nbytes == 64).all()
    assert r.stats["I"].misses == 1 and r.stats["D"].misses == 1 and r.stats["D"].accesses == 2


def test_h0_passes_every_request_through():
    cyc, port, we, addr = np.arange(3), np.array(["I", "D", "D"]), np.array([0, 1, 0], bool), np.array([0, 64, 128])
    r = cache.h0(cyc, port, we, addr)
    assert list(r.txn.addr) == [0, 64, 128] and list(r.txn.write) == [False, True, False] and (r.txn.nbytes == 4).all()


def test_h1_traffic_never_exceeds_h0_lines_for_a_looping_program():
    rng = np.random.default_rng(0)
    body = np.arange(0, 1024, 4)                             # a 1 KB loop body fetched 50 times
    iaddr = np.tile(body, 50)
    daddr = rng.integers(0, 2048, iaddr.size) & ~3           # data within 2 KB
    cyc = np.arange(2 * iaddr.size)
    port = np.tile(np.array(["I", "D"]), iaddr.size)
    addr = np.empty(2 * iaddr.size, np.int64); addr[0::2], addr[1::2] = iaddr, daddr
    we = np.zeros(2 * iaddr.size, bool); we[1::2] = rng.random(iaddr.size) < 0.3
    r = cache.h1(cyc, port, we, addr)
    assert r.stats["I"].misses == 16                         # the loop fits: compulsory misses only
    assert r.stats["D"].misses == 32 and r.stats["D"].writebacks == 0
    assert r.txn.nbytes.sum() < cache.h0(cyc, port, we, addr).txn.nbytes.sum()


@pytest.mark.parametrize("bad", [
    dict(port=np.array(["X"])),
    dict(cycle=np.array([1, 0]), port=np.array(["I", "I"]), we=np.zeros(2, bool), addr=np.zeros(2, np.int64)),
])
def test_rejects_bad_traces(bad):
    a = dict(cycle=np.array([0]), port=np.array(["I"]), we=np.array([False]), addr=np.array([0]))
    a.update(bad)
    with pytest.raises(ValueError):
        cache.h1(a["cycle"], a["port"], a["we"], a["addr"])


def test_instruction_writes_are_rejected():
    with pytest.raises(ValueError, match="instruction port write"):
        cache.h1(np.array([0]), np.array(["I"]), np.array([True]), np.array([0]))
