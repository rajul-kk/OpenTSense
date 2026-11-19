"""Sensor model: offsets fixed per chip, quantised codes, zero-order-hold sampling, the ideal profile is G84's."""
import numpy as np
import pytest

from opentsense.estimate import sensor


def test_offsets_are_fixed_per_chip_and_differ_between_chips():
    rng = np.random.default_rng(0)
    chip = sensor.Chip.draw("ring_osc", 8, rng)
    T = np.full((1000, 8), sensor.T_TRIM)
    err = chip.read(T, rng) - T
    assert np.allclose(err.mean(0), chip.offset, atol=0.15)   # 0.25 K steps, 0.1 K noise, 1000 readings
    other = sensor.Chip.draw("ring_osc", 8, rng)
    assert not np.allclose(chip.offset, other.offset)


@pytest.mark.parametrize("name", ["bjt_trimmed", "ring_osc", "dts_1c"])
def test_readings_are_on_the_code_grid(name):
    rng = np.random.default_rng(1)
    step = sensor.PROFILES[name].step_K
    y = sensor.Chip.draw(name, 4, rng).read(rng.uniform(320, 380, (50, 4)), rng)
    assert np.allclose(y / step, np.round(y / step))


def test_gain_error_grows_away_from_the_trim_point():
    p = sensor.Profile(0.0, 0.0, 0.0, 0.0)
    chip = sensor.Chip(p, np.zeros(1), np.array([0.02]))
    rng = np.random.default_rng(2)
    assert chip.read([[sensor.T_TRIM]], rng)[0, 0] == pytest.approx(sensor.T_TRIM)
    assert chip.read([[sensor.T_TRIM - 50]], rng)[0, 0] == pytest.approx(sensor.T_TRIM - 51)


def test_ideal_profile_is_exact_plus_gaussian():
    rng = np.random.default_rng(3)
    chip = sensor.Chip.draw("ideal_gauss", 3, rng)
    e = chip.read(np.full((20000, 3), 330.0), rng) - 330.0
    assert np.all(chip.offset == 0) and abs(e.std() - 0.1) < 0.005


@pytest.mark.parametrize("dt,period", [(1e-3, 3e-3), (0.1, 0.3)])   # 0.1 x 9 > 0.3 x 3 in floating point
def test_sample_holds_the_last_sample(dt, period):
    t = np.arange(10) * dt
    assert sensor.sample(t, np.arange(10.0), period).tolist() == [0, 0, 0, 3, 3, 3, 6, 6, 6, 9]


def test_no_reading_before_the_first_sample():
    y = sensor.sample(np.arange(5) * 1e-3, np.arange(5.0), 1e-3, t0_s=2e-3)
    assert np.isnan(y[:2]).all() and y[2:].tolist() == [2, 3, 4]


def _gate_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_g102_readings_keep_the_case_set_and_tell_a_train_only_datasheet_total():
    import os
    from opentsense.bench.cases import CaseSet
    readings = _gate_module(os.path.join(os.path.dirname(__file__), "..", "gates", "g102", "readings.py"), "g102_readings")
    rng = np.random.default_rng(0)
    N, ny, nx = 12, 4, 4
    T = rng.uniform(10, 60, (N, 2, ny, nx)).astype(np.float32)
    sens = np.array([[0, 1, 1], [1, 2, 3]])
    split = np.array(["train"] * 8 + ["test"] * 4)
    cs = CaseSet(dict(T=T, readings=np.zeros((N, 2)), sensors=sens, noise_K=0.1, split=split,
                      group=np.array(list("aabbccddeeff")), tag=np.array(["x"] * N), dies=np.array(["top", "bot"]),
                      buried=np.array([False, True]), cell_um=100.0, stack_id="g71_3d"))
    a, b = readings.with_sensor(cs, "ring_osc", 1), readings.with_sensor(cs, "ring_osc", 1)
    assert np.array_equal(a.readings, b.readings) and np.array_equal(a.T, cs.T)
    truth = T[:, sens[:, 0], sens[:, 1], sens[:, 2]]
    assert np.abs(a.readings - truth).max() < 8                       # rises stay rises (ambient added and removed)
    p = sensor.PROFILES["ring_osc"]
    assert float(a.noise_K) > np.sqrt(p.offset_K ** 2 + p.step_K ** 2 / 12 + p.noise_K ** 2)   # gain term counted
    hot_test = CaseSet({**cs.a, "T": np.where((split == "test")[:, None, None, None], T + 40, T).astype(np.float32)})
    assert float(readings.with_sensor(hot_test, "ring_osc", 1).noise_K) == float(a.noise_K)  # test truth unused
    assert float(readings.with_sensor(cs, "ideal_gauss", 1).noise_K) == pytest.approx(0.1)


def test_sample_refuses_bad_input_and_has_no_value_before_data():
    t = np.arange(4) * 1.0
    with pytest.raises(ValueError):
        sensor.sample(t, np.arange(5.0), 1.0)
    with pytest.raises(ValueError):
        sensor.sample(t, np.arange(4.0), 0.0)
    y = sensor.sample(t + 1.0, np.arange(4.0), 2.0, t0_s=0.0)       # first instant (0 s) precedes the data (1 s)
    assert np.isnan(y[0]) and y[1:].tolist() == [1, 1, 3]


def test_sample_on_a_long_record():
    t = np.arange(0, 10_000_001) * 1e-6                               # 10 s at 1 us, sampled every 1 us
    y = sensor.sample(t[-20:], t[-20:], 1e-6, t0_s=t[-20])
    assert np.array_equal(y, t[-20:])
