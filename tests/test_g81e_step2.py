"""G81e step 2: per-window dynamic energy is a part of the total that sums to the whole-trace model, and the
scorer's statistics behave as registered (sorted shares ignore bank labels; constant series do not count)."""
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "gates", "g81e", "dry"))    # run.py imports fit_energy from there


def _gate_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STEP2 = os.path.join(HERE, "..", "gates", "g81e", "step2")
evaluate = _gate_module("g81e_evaluate", os.path.join(STEP2, "evaluate.py"))
run = _gate_module("g81e_run", os.path.join(STEP2, "run.py"))
from opentsense.power import cache, dramctl, dramenergy  # noqa: E402

MODEL = dramenergy.Model(**json.load(open(os.path.join(HERE, "..", run.FIT)))["model"])


def trace(seed, n=400, cycles=60_011):          # not a multiple of the window, as no real program is
    rng = np.random.default_rng(seed)
    c = np.sort(rng.integers(0, cycles, n))
    p = np.where(rng.random(n) < 0.6, "D", "I")
    a = np.where(p == "I", rng.integers(0, 1 << 15, n), rng.integers(1 << 20, (1 << 20) + (1 << 17), n)) & ~3
    return c, p, (p == "D") & (rng.random(n) < 0.3), a, cycles


def test_windows_sum_to_the_whole_trace_and_dynamic_is_part_of_the_total():
    c, p, w, a, cycles = trace(1)
    tr = dramctl.schedule(cache.h1(c, p, w, a).txn, end_cycle=cycles)
    e, dur = run.window_energy(tr, MODEL, cycles)
    dyn = e["dyn_bank"].sum(1) + e["dyn_io"]
    assert np.all(dyn <= e["total"]) and dyn.sum() > 0
    assert np.isclose(e["total"].sum(), dramenergy.predict_totals(tr, MODEL)["total"], rtol=1e-9)
    assert len(e["total"]) == int(np.ceil(cycles / run.WINDOW_CPU)) and dur >= cycles * 1e-9


def test_a_program_ending_on_a_window_edge_gets_no_sliver_window():
    c, p, w, a, _ = trace(5, cycles=60_000)
    tr = dramctl.schedule(cache.h1(c, p, w, a).txn, end_cycle=60_000)
    e, _ = run.window_energy(tr, MODEL, 60_000)
    assert len(e["total"]) == 60


def test_refresh_commands_are_not_dynamic():
    empty = cache.Txn(*(np.zeros(0, t) for t in (np.int64, np.int64, bool, np.int64)))
    tr = dramctl.schedule(empty, end_cycle=50_000)          # refresh only
    e, _ = run.window_energy(tr, MODEL, 50_000)
    assert np.allclose(e["dyn_bank"], 0) and np.allclose(e["dyn_io"], 0) and e["total"].sum() > 0


def test_a_controller_backlog_gets_its_own_windows_and_time():
    rng = np.random.default_rng(4)
    n, cycles = 3000, 4000                       # far more requests than the DRAM can serve in 4,000 cycles
    c = np.sort(rng.integers(0, cycles, n))
    out, arrays, _ = run.program((c, np.full(n, "D"), np.zeros(n, bool), rng.integers(0, 1 << 24, n) & ~3), cycles,
                                 MODEL, "H0")
    s = out["seeds"][0]
    assert s["trace_s"] > 2 * s["program_s"] and len(arrays["s0_dyn_J"]) == len(arrays["miss_per_window"]) > 4


def test_fills_exclude_write_backs():
    c, p, w, a, cycles = trace(2)
    out, arrays, _ = run.program((c, p, w, a), cycles, MODEL, "H1")
    st = out["stats"]["I"]["misses"] + out["stats"]["D"]["misses"]
    assert arrays["miss_per_window"].sum() == st < arrays["txn_per_window"].sum()


def summary(shares_by_seed, dyn=1e-4):
    return {"seeds": {str(s): {"mean_dyn_W": dyn, "mean_total_W": 1e-2, "bank_dyn_share": sh}
                      for s, sh in enumerate(shares_by_seed)}}


def test_sorted_shares_ignore_which_bank_the_hash_picks():
    hot = [0.9] + [0.1 / 7] * 7
    relabelled = [list(np.roll(hot, s)) for s in range(6)]        # nominal + 5 seeds, hot bank moves each time
    arrays = {f"s{s}_dyn_J": np.arange(10.0) for s in range(6)} | {"miss_per_window": np.arange(10)}
    p = evaluate.per_program(summary(relabelled), arrays)
    assert p["b"] and np.allclose(p["sorted_share_floor"], 0) and p["a2"]


def test_a_zero_floor_does_not_pass_a_rounding_difference():
    flat = [[1 / 8 + 1e-9] + [1 / 8 - 1e-9 / 7] * 7] * 6     # above float rounding, below the guard
    arrays = {f"s{s}_dyn_J": np.arange(10.0) for s in range(6)} | {"miss_per_window": np.arange(10)}
    assert not evaluate.per_program(summary(flat), arrays)["b"]


def test_constant_series_does_not_count_for_a2():
    arrays = {f"s{s}_dyn_J": np.ones(10) for s in range(6)} | {"miss_per_window": np.arange(10)}
    p = evaluate.per_program(summary([[1 / 8] * 8] * 6), arrays)
    assert not p["a2"] and not p["b"] and p["pearson"][0] is None
