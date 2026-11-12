"""G81e step 4: window features, the fitted linear model, and window/total consistency (no DRAMPower needed)."""
import numpy as np
import pytest

from opentsense.power import cache, dramctl, dramenergy

NB = 8
RFC = dramctl.LPDDR4_3200["t"]["RFCab"]


def mixed(seed=0, n=3000, cycles=300_000):
    rng = np.random.default_rng(seed)
    cyc = np.sort(rng.integers(0, cycles, n))
    port = np.where(rng.random(n) < 0.5, "D", "I")
    addr = np.where(port == "I", rng.integers(0, 1 << 15, n), rng.integers(1 << 20, (1 << 20) + (1 << 17), n)) & ~3
    we = (port == "D") & (rng.random(n) < 0.3)
    return dramctl.schedule(cache.h1(cyc, port, we, addr).txn, end_cycle=cycles)


def test_refresh_counts_as_active_background():
    idle = dramctl.schedule(cache.Txn(*(np.zeros(0, t) for t in (np.int64, np.int64, bool, np.int64))), end_cycle=100_000)
    f = dramenergy.features(idle, NB)
    nref = int((idle.cmd == "REFA").sum())
    assert f["any_open"][0] == nref * RFC
    assert f["closed"][0] == f["length"][0] - nref * RFC


def test_open_time_and_counts_of_one_access():
    tr = dramctl.schedule(cache.Txn(np.array([0]), np.array([0]), np.array([False]), np.array([64])),
                          ref_phase=10 ** 9, end_cycle=1000)
    f = dramenergy.features(tr, NB)
    end = int(tr.time[-1])
    assert f["act"][0, 0] == 1 and f["rd"][0, 0] == 2 and f["pre"].sum() == 0
    assert f["open"][0, 0] == end and f["any_open"][0] == end      # opened at 0, never closed


def test_windows_add_up_to_the_whole_trace():
    tr = mixed()
    m = dramenergy.Model(act=1.0, pre=2.0, rd=3.0, wr=4.0, refa=5.0, closed=1e-3, any_open=2e-3, io_cycle=1e-4,
                         io_cmd=0.5, io_rd=0.1, io_wr=0.2)
    end = int(tr.time[-1])
    edges = np.arange(0, end + 1600, 1600)                      # 1,000 CPU cycles at 1 GHz = 1,600 DRAM clocks
    edges[-1] = end
    w = dramenergy.windows(tr, NB, m, edges)
    p = dramenergy.predict_totals(tr, NB, m)
    assert w["total"].sum() == pytest.approx(p["total"], rel=1e-12)
    assert w["bank"].shape == (len(edges) - 1, NB) and (w["bank"] >= 0).all()


def test_fit_recovers_known_coefficients():
    """Synthetic 'DRAMPower' outputs made from known coefficients are fitted back exactly."""
    true = dramenergy.Model(act=2e-9, pre=1e-9, rd=1.7e-10, wr=1.2e-10, refa=2.8e-9, closed=2.2e-12, any_open=2.3e-11,
                            io_cycle=2e-12, io_cmd=1e-12, io_rd=3e-11, io_wr=4e-11)
    runs = []
    for seed in range(4):
        tr = mixed(seed)
        f = dramenergy.features(tr, NB)
        banks = [{"ACT": true.act * f["act"][0, k], "PRE": true.pre * f["pre"][0, k], "RD": true.rd * f["rd"][0, k],
                  "WR": true.wr * f["wr"][0, k], "REF_AB": true.refa * f["refa"][0],
                  "BG_PRE": true.closed * f["closed"][0]} for k in range(NB)]
        io = (true.io_cycle * f["length"][0] + true.io_cmd * f["ncmd"][0] + true.io_rd * f["rd"].sum()
              + true.io_wr * f["wr"].sum())
        runs.append((tr, {"CoreEnergy": {"BankEnergy": banks, "E_bg_act_shared": true.any_open * f["any_open"][0]},
                          "InterfaceEnergy": {"controller": {"dynamicEnergy": io}, "dram": {"dynamicEnergy": 0.0}}}))
    m, resid = dramenergy.fit(runs, NB)
    for k, v in true.as_dict().items():
        assert getattr(m, k) == pytest.approx(v, rel=1e-6), k
    assert max(resid.values()) < 1e-9


def test_prea_counts_once_per_open_bank():
    # two banks open (rows 0 of banks 0 and 1), then the refresh's PREA closes both
    tr = dramctl.schedule(cache.Txn(np.array([0, 1]), np.array([0, 2048]), np.zeros(2, bool), np.full(2, 64)),
                          ref_phase=2000, end_cycle=3000)
    assert (tr.cmd == "PREA").sum() == 1 and (tr.cmd == "PRE").sum() == 0
    f = dramenergy.features(tr, NB)
    assert f["pre"][0].tolist() == [1, 1, 0, 0, 0, 0, 0, 0]
