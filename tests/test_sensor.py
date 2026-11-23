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


def test_correlated_offsets_keep_the_profile_sigma_and_correlate_neighbours():
    xy = np.array([[0.0, 0.0], [0.1, 0.0], [3.0, 0.0], [0.0, 0.0]])
    corr = sensor.Correlation(xy, np.array([0, 0, 0, 1]), 0.8, 1.0)
    rng = np.random.default_rng(0)
    off = np.array([sensor.Chip.draw("ring_osc", 4, rng, corr).offset for _ in range(20000)])
    assert np.allclose(off.std(0), 1.0, atol=0.03)
    c = np.corrcoef(off.T)
    assert c[0, 1] > 0.75 and abs(c[0, 2]) < 0.05 and abs(c[0, 3]) < 0.05   # near, far, other die


def test_bench_readings_reproduce_g102_and_correlation_keeps_the_noise_stream():
    """bench.readings is G102's readings.py moved: with the default salt it must give G102's case sets exactly; with
    a correlation of share 0 the offsets and the per-reading noise must be unchanged too."""
    import os
    import sys
    from opentsense.bench import readings as new
    from opentsense.bench.cases import CaseSet
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gates", "g102"))
    import readings as old
    rng = np.random.default_rng(0)
    T = rng.uniform(0, 20, (12, 2, 6, 6)).astype(np.float32)
    cs = CaseSet(dict(T=T, readings=np.zeros((12, 4)), sensors=np.array([[0, 1, 1], [0, 4, 4], [1, 2, 3], [1, 5, 0]]),
                      noise_K=0.1, split=np.array(["train"] * 8 + ["test"] * 4), group=np.array(list("aaaabbbbcccc")),
                      tag=np.array(["seen-group"] * 12), dies=np.array(["top", "bot"]), buried=np.array([False, True]),
                      cell_um=50.0, stack_id="g71_3d"))
    for prof, chip in (("ring_osc", 7), ("dts_1c", 9), ("bjt_trimmed", 1)):
        assert new.with_sensor(cs, prof, chip).sha256() == old.with_sensor(cs, prof, chip).sha256()
    a, b = new.with_sensor(cs, "ring_osc", 3, 105), new.with_sensor(cs, "ring_osc", 3, 105, (0.0, 1.0))
    assert np.array_equal(a.readings, b.readings)


def _derive():
    temps = ("0", "25", "50", "75", "85", "100", "125")
    err = {"tt": [0.0] * 7, "ss": [-3.0, -2.0, -1.0, -0.2, 0.0, 0.2, -0.2], "ff": [2.0, 1.0, 0.2, 0.0, 0.0, 0.2, 1.2]}
    ring = {"corner_error_K": {c: dict(zip(temps, v)) for c, v in err.items()},
            "droop_K_per_mV": {"tt": 4.0, "ss": 4.1, "ff": 3.8}}
    one = dict(zip(temps, [-3.6, -2.8, -1.8, -0.6, 0.0, 0.9, 2.6]))
    return {"ring": {"asap7": ring}, "dvbe": {c: {"error_one_point_K": one, "error_two_point_K": one} for c in err}}


def test_circuit_profile_reads_the_corner_error_and_the_squeeze():
    from opentsense.estimate import sensor_circuit as sc
    p = sc.CircuitProfile.ring(_derive(), "asap7", step_K=0.0, noise_K=0.0)
    rng = np.random.default_rng(0)
    T = np.array([273.15, 310.65, 358.15])                              # 0, 37.5 (between 25 and 50) and 85 C
    assert np.allclose(sc.read(p, "ss", T, rng) - T, [-3.0, -1.5, 0.0])
    assert np.allclose(sc.read(p, "tt", T, rng, squeeze_mV=2.0) - T, 8.0)    # lower supply reads hotter
    assert np.allclose(p.error("ff", [200.0, 450.0]), [2.0, 1.2])            # held at the swept ends
    assert sc.CircuitProfile.dvbe(_derive(), "one_point").droop_K_per_mV["tt"] == 0.0


def test_read_circuit_is_one_corner_per_chip_and_tells_a_train_only_total():
    from opentsense.bench import readings
    from opentsense.bench.cases import CaseSet
    from opentsense.estimate import sensor_circuit as sc
    rng = np.random.default_rng(0)
    N = 12
    T = rng.uniform(10, 60, (N, 2, 4, 4)).astype(np.float32)
    split = np.array(["train"] * 8 + ["test"] * 4)
    cs = CaseSet(dict(T=T, readings=np.zeros((N, 2)), sensors=np.array([[0, 1, 1], [1, 2, 3]]), noise_K=0.1,
                      split=split, group=np.array(list("aabbccddeeff")), tag=np.array(["x"] * N),
                      dies=np.array(["top", "bot"]), buried=np.array([False, True]), cell_um=100.0, stack_id="g71_3d"))
    p = sc.CircuitProfile.ring(_derive(), "asap7")
    a, ca = readings.read_circuit(cs, "asap7_ring", p, 3, 106)
    b, cb = readings.read_circuit(cs, "asap7_ring", p, 3, 106)
    assert ca == cb and np.array_equal(a.readings, b.readings)
    corners = {readings.read_circuit(cs, "asap7_ring", p, c, 106)[1] for c in range(30)}
    assert corners == set(sc.CORNERS)
    sq = np.zeros((N, 2)); sq[8:] = 50.0                                   # squeeze only on the test cases
    c, _ = readings.read_circuit(cs, "asap7_ring", p, 3, 106, sq)
    assert float(c.noise_K) == float(a.noise_K) and (c.readings[8:] > a.readings[8:] + 100).all()
    with pytest.raises(ValueError):
        readings.read_circuit(cs, "asap7_ring", p, 3, 106, np.zeros((N, 3)))
