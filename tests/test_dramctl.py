"""G81e DRAM controller: command timing, address map, refresh, the independent checker, and DRAMPower's CSV format."""
import numpy as np
import pytest

from opentsense.power import cache, dramctl

S = dramctl.LPDDR4_3200
T = S["t"]


def txn(cycles, addrs, writes=None, nbytes=64):
    n = len(cycles)
    return cache.Txn(np.asarray(cycles, np.int64), np.asarray(addrs, np.int64),
                     np.zeros(n, bool) if writes is None else np.asarray(writes, bool), np.full(n, nbytes, np.int64))


def cmds(tr):
    return [(int(t), str(c), int(b)) for t, c, b in zip(tr.time, tr.cmd, tr.bank) if c != "END"]


def test_address_map_rotates_rows_over_banks():
    _, row_bytes, nb = dramctl.geometry(S)
    assert row_bytes == 2048 and nb == 8
    assert dramctl.map_address(0, S) == (0, 0, 0)
    assert dramctl.map_address(2048, S) == (1, 0, 0)
    assert dramctl.map_address(2048 * 8, S) == (0, 1, 0)
    assert dramctl.map_address(64, S) == (0, 0, 32)              # 64 B = 32 x16 columns = 2 bursts of 16


def test_one_line_read_is_act_then_two_bursts():
    tr = dramctl.schedule(txn([0], [0]), ref_phase=10 ** 9)       # refresh out of the way
    c = cmds(tr)
    assert [x[1] for x in c] == ["ACT", "RD", "RD"]
    assert c[1][0] - c[0][0] == T["RCD"] and c[2][0] - c[1][0] == T["CCD"]
    assert dramctl.check(tr) == []


def test_row_hit_needs_no_second_act_and_conflict_needs_pre():
    tr = dramctl.schedule(txn([0, 100, 200], [0, 64, 2048 * 8]), ref_phase=10 ** 9)   # last one: bank 0, row 1
    names = [x[1] for x in cmds(tr)]
    assert names.count("ACT") == 2 and names.count("PRE") == 1
    c = cmds(tr)
    pre = next(x for x in c if x[1] == "PRE")
    act2 = [x for x in c if x[1] == "ACT"][1]
    first_act = c[0][0]
    assert pre[0] >= first_act + T["RAS"] and act2[0] - pre[0] >= T["RPpb"]
    assert dramctl.check(tr) == []


def test_refresh_runs_through_idle_time():
    end_cpu = 200_000                                              # 200 us at 1 GHz
    tr = dramctl.schedule(txn([0], [0]), end_cycle=end_cpu)
    refs = tr.time[tr.cmd == "REFA"]
    expect = int(end_cpu * 1e-9 / T["tCK"] // T["REFI"]) + 1
    assert abs(len(refs) - expect) <= 1
    assert np.all(np.diff(refs) <= T["REFI"] + T["RFCab"] + T["RPab"] + 200)
    assert dramctl.check(tr) == []


@pytest.mark.parametrize("seed", range(5))
def test_random_program_traffic_is_legal(seed):
    rng = np.random.default_rng(seed)
    n = 4000
    cyc = np.sort(rng.integers(0, 400_000, n))
    port = np.where(rng.random(n) < 0.5, "I", "D")
    addr = np.where(port == "I", rng.integers(0, 1 << 15, n), rng.integers(1 << 20, (1 << 20) + (1 << 17), n)) & ~3
    we = (port == "D") & (rng.random(n) < 0.3)
    for h in (cache.h1(cyc, port, we, addr), cache.h0(cyc, port, we, addr)):
        tr = dramctl.schedule(h.txn, ref_phase=int(rng.integers(0, T["REFI"])), bank_salt=seed, end_cycle=400_000)
        assert dramctl.check(tr) == []
        assert np.all(np.diff(tr.time) > 0)


def test_checker_catches_each_kind_of_violation():
    tr = dramctl.schedule(txn([0, 50], [0, 2048 * 8]), ref_phase=10 ** 9)   # ACT RD RD PRE ACT RD RD
    assert dramctl.check(tr) == []
    early = dramctl.Trace(tr.time.copy(), tr.cmd.copy(), tr.bank.copy(), tr.row.copy(), tr.col.copy())
    i = int(np.flatnonzero(early.cmd == "RD")[0])
    early.time[i] = early.time[i - 1] + 1                         # RD right after ACT
    assert any("tRCD" in v for v in dramctl.check(early))
    j = int(np.flatnonzero(tr.cmd == "PRE")[0])
    noprecharge = dramctl.Trace(np.delete(tr.time, j), np.delete(tr.cmd, j), np.delete(tr.bank, j),
                                np.delete(tr.row, j), np.delete(tr.col, j))
    assert any("ACT to open bank" in v for v in dramctl.check(noprecharge))
    wrongrow = dramctl.Trace(tr.time.copy(), tr.cmd.copy(), tr.bank.copy(), tr.row.copy(), tr.col.copy())
    wrongrow.row[i] = 7                                            # a burst to a row that is not open
    assert any("but row 0 is open" in v for v in dramctl.check(wrongrow))


def test_write_then_read_respects_turnaround():
    tr = dramctl.schedule(txn([0, 1], [0, 64], writes=[True, False]), ref_phase=10 ** 9)
    c = cmds(tr)
    last_wr = max(t for t, n, _ in c if n == "WR")
    first_rd = min(t for t, n, _ in c if n == "RD")
    assert first_rd - last_wr >= T["WL"] + S["arch"]["burstLength"] // 2 + T["WTR"]
    assert dramctl.check(tr) == []


def test_csv_matches_the_g50a_format():
    tr = dramctl.schedule(txn([0], [0]), ref_phase=10 ** 9)
    lines = tr.csv().splitlines()
    assert lines[0] == "0,ACT,0,0,0,0,0"
    t, cmd, *_rest, data = lines[1].split(",")
    assert cmd == "RD" and len(data) == 64 and set(data) == {"0"}
    assert lines[-1].split(",")[1] == "END"


def test_bank_hash_needs_a_power_of_two_bank_count():
    spec = {**dramctl.LPDDR4_3200, "arch": {**dramctl.LPDDR4_3200["arch"], "nbrOfBanks": 6}}
    with pytest.raises(ValueError, match="power-of-two"):
        dramctl.map_address(0, spec, bank_salt=1)


def test_write_recovery_includes_the_extra_clock():
    T, BL = dramctl.LPDDR4_3200["t"], dramctl.LPDDR4_3200["arch"]["burstLength"]
    tw = T["RCD"]
    ok_pre = tw + T["WL"] + BL // 2 + 1 + T["WR"]
    for t_pre, legal in ((ok_pre, True), (ok_pre - 1, False)):
        t_pre = max(t_pre, T["RAS"])
        tr = dramctl.Trace(np.array([0, tw, t_pre]), np.array(["ACT", "WR", "PRE"]), np.zeros(3, np.int64),
                           np.zeros(3, np.int64), np.zeros(3, np.int64))
        assert (not any("write recovery" in v for v in dramctl.check(tr))) == legal
