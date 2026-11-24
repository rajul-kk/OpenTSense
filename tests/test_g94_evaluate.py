"""G94 scorer validity: a unit missing a die, holding the wrong row count or a non-finite value is refused, not scored."""
import importlib.util
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def ev():
    cwd = os.getcwd()
    os.chdir(ROOT)                                   # evaluate.py puts "." and gates/g94 on sys.path
    try:
        spec = importlib.util.spec_from_file_location("g94_evaluate", os.path.join(ROOT, "gates", "g94", "evaluate.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod
    finally:
        os.chdir(cwd)
        sys.path[:] = [p for p in sys.path if p not in (".", os.path.join("gates", "g94"))]


def unit(dies=("top", "bot"), n_slots=3, level=1, case="step"):
    q = lambda n: {"peak": [1.0] * n, "mean": [0.5] * n}
    u = {"level": level, "wall_s": 2.0,
         "series": {d: q(n_slots * 2 ** level) for d in dies},
         "series_finer": {d: q(n_slots * 2 ** (level + 1)) for d in dies}}
    if case == "step":
        u["steady_end_diff_K"] = 0.001
    return u


def test_complete_unit_passes(ev):
    assert ev.problem(unit(), {"top", "bot"}, 3, "step") is None


def test_die_missing_from_the_unit_is_refused(ev):
    assert "dies" in ev.problem(unit(dies=("top",)), {"top", "bot"}, 3, "step")


def test_short_series_is_refused(ev):
    assert "rows" in ev.problem(unit(n_slots=2), {"top", "bot"}, 3, "pulse")


def test_non_finite_wall_time_is_refused(ev):
    u = unit()
    u["wall_s"] = float("nan")
    assert "non-finite" in ev.problem(u, {"top", "bot"}, 3, "step")


def test_null_values_are_refused_not_crashed_on(ev):
    u = unit()
    u["wall_s"] = None
    assert "non-finite" in ev.problem(u, {"top", "bot"}, 3, "step")
    u = unit()
    u["series"]["top"]["peak"][0] = None
    assert "non-finite" in ev.problem(u, {"top", "bot"}, 3, "step")


@pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, "gates", "g81b", "runs", "main")),
                    reason="G81b timelines (gitignored) not present")
def test_slot_counts_match_the_built_sequences(ev):
    S = ev.run_settings()
    for name, case in ev.units():
        built = len(next(iter(ev.cases.builders(name, ev.SEED, S)[case]().values())))
        assert ev.cases.n_slots(case, S, ev.SEED) == built, (name, case)


def test_step_without_its_steady_check_is_refused(ev):
    u = unit()
    del u["steady_end_diff_K"]
    assert ev.problem(u, {"top", "bot"}, 3, "step") is not None
    assert ev.problem(unit(case="pulse"), {"top", "bot"}, 3, "pulse") is None



S_BARS = {"slot_s": 0.005, "tol_c_K": 0.5, "tol_b_rel": 0.05}


def level1(rise):
    """(level 1, the series, the same values at level 2): a zero floor."""
    return 1, list(rise), list(np.repeat(rise, 2))


def test_trajectory_bar_gates_only_after_5_ms(ev):
    """Rows at level 1 end every 2.5 ms: rows 0-1 are the first 5 ms. A 0.6 K gap there is reported, not gated; the
    same gap later fails."""
    rise = np.linspace(0.1, 10.0, 16)
    early, late = rise.copy(), rise.copy()
    early[:2] += 0.6
    late[5] += 0.6
    c, first, rms, fa, fb = ev.trajectories(S_BARS, level1(rise), level1(early))
    assert c["ok"] and c["max_diff_K"] < 1e-12 and abs(first - 0.6) < 1e-12 and rms < 1e-12 and fa == fb == 0.0
    c, first, rms, _, _ = ev.trajectories(S_BARS, level1(rise), level1(late))
    assert not c["ok"] and c["bar_K"] == 0.5 and abs(c["max_diff_K"] - 0.6) < 1e-12 and first < 1e-12


def test_trajectory_bar_widens_with_the_floor(ev):
    """A 0.6 K gap passes when a solver's level-to-level change after 5 ms is 0.3 K (bar 3 x 0.3 = 0.9 K)."""
    rise = np.linspace(0.1, 10.0, 16)
    coarse = 1, list(rise), list(np.repeat(rise + 0.3, 2))
    c, *_ = ev.trajectories(S_BARS, coarse, level1(rise + 0.6))
    assert c["ok"] and abs(c["bar_K"] - 0.9) < 1e-12


def test_time_constant_bar_is_five_percent_of_the_mean(ev):
    t = 0.0025 * (np.arange(64) + 1)

    def step(tau):
        return 1, list(1 - np.exp(-t / tau)), list(1 - np.exp(-0.00125 * (np.arange(128) + 1) / tau))
    near = ev.time_constants(S_BARS, step(0.020), step(0.0204))      # t63 2% apart: passes
    far = ev.time_constants(S_BARS, step(0.020), step(0.030))        # 40% apart: fails
    assert near["ok"] and not far["ok"]
    ta, tb = near["t63_s"]
    assert near["bar_s"] >= 0.05 * (ta + tb) / 2 > abs(ta - tb)


def test_string_or_nested_series_are_refused(ev):
    u = unit()
    u["series"]["top"]["peak"] = [str(v) for v in u["series"]["top"]["peak"]]
    assert "non-numeric" in ev.problem(u, {"top", "bot"}, 3, "step")
    u = unit()
    u["series"]["top"]["peak"] = [[v] for v in u["series"]["top"]["peak"]]
    assert "non-numeric" in ev.problem(u, {"top", "bot"}, 3, "step")
