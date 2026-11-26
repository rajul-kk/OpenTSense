"""Independent row-end, site-index and energy controls for G79 trace plumbing."""

from math import exp

import numpy as np
import pytest

from opentsense.estimate.dynamic import _slots
from opentsense.estimate.trace import (
    SlotGrid,
    gather_sites,
    rail_observation,
    sample_temperature,
    sensor_lag,
    slot_power,
)

DT = 0.5e-3
STEP = 0.125e-3
TAU = 1e-3


@pytest.mark.parametrize(("step", "m"), [(STEP, 4), (STEP / 2, 8)])
def test_slot_timestamps_are_row_ends(step, m):
    grid = SlotGrid(DT, step)
    assert grid.m == m
    np.testing.assert_array_equal(grid.sample_rows(3), [m - 1, 2 * m - 1, 3 * m - 1])
    np.testing.assert_allclose(grid.sample_times(3), [DT, 2 * DT, 3 * DT], rtol=1e-15, atol=0)
    np.testing.assert_allclose(grid.row_times(3)[grid.sample_rows(3)], grid.sample_times(3), rtol=1e-15, atol=0)
    assert grid.row_times(3)[0] == step


@pytest.mark.parametrize(("dt", "step"), [(DT, 0.2e-3), (DT, DT / 3), (DT, 0)])
def test_grid_rejects_rows_the_solver_cannot_represent(dt, step):
    with pytest.raises(ValueError):
        SlotGrid(dt, step)


@pytest.fixture
def rc_pulse():
    """Closed-form RC response and independent convolution for a row-held sensor."""
    tau_rc = 0.8e-3
    steady_rise = 2.0
    n_slots, j, rows_per_slot = 6, 2, 4
    n_rows = n_slots * rows_per_slot
    t = np.arange(1, n_rows + 1) * STEP
    on, off = j * DT, (j + 1) * DT

    def step_response(age):
        return steady_rise * (1 - np.exp(-np.maximum(0, age) / tau_rc))

    rise = step_response(t - on) - step_response(t - off)
    # The input is constant within each row. The lag's impulse weights are a
    # geometric series, so convolution is an independent check of the recurrence.
    q = exp(-STEP / TAU)
    expected_rows = np.convolve(rise, (1 - q) * q ** np.arange(n_rows))[:n_rows]
    return SlotGrid(DT, STEP), j, rise[:, None], expected_rows.reshape(n_slots, rows_per_slot)[:, -1:]


def test_tagged_rc_pulse_first_responds_in_its_own_slot(rc_pulse):
    grid, j, rise, expected = rc_pulse
    lagged = sensor_lag(rise, grid, TAU, initial_rise=0)
    sampled = sample_temperature(lagged, grid, len(expected), 0, np.random.default_rng(5))
    np.testing.assert_allclose(sampled, expected, rtol=1e-13, atol=1e-14)
    assert np.flatnonzero(sampled[:, 0] > 0)[0] == j
    assert sampled[j, 0] < sampled[j + 1, 0]  # lagged peak follows the falling edge
    assert sampled[-1, 0] < sampled[j + 1, 0]


@pytest.mark.parametrize("mistake", ["wrong-thermal-start", "one-row-late", "beginning-of-slot"])
def test_pulse_comparison_detects_incorrect_readings(rc_pulse, mistake):
    grid, _, rise, expected = rc_pulse
    if mistake == "wrong-thermal-start":
        t = np.arange(1, len(rise) + 1)[:, None] * STEP
        rise = rise + 0.7 * np.exp(-t / 0.8e-3)
    lagged = sensor_lag(rise, grid, TAU, initial_rise=0)
    n_slots = len(expected)
    if mistake == "one-row-late":
        lagged = np.vstack([np.zeros((1, 1)), lagged[:-1]])
    if mistake == "beginning-of-slot":
        at_boundaries = np.vstack([np.zeros((1, 1)), lagged])
        wrong = at_boundaries[np.arange(n_slots) * grid.m]
    else:
        wrong = sample_temperature(lagged, grid, len(expected), 0, np.random.default_rng(5))
    assert wrong.shape == expected.shape
    assert np.max(np.abs(wrong - expected)) > 0.05


def test_gather_preserves_die_and_asymmetric_cell_order():
    row, y, x = np.indices((3, 4, 5))
    base = 100 * row + 10 * y + x
    fields = {"top": base, "bot": base + 1000}
    sites = np.array([[1, 1, 3], [0, 2, 1], [1, 0, 2]])
    np.testing.assert_array_equal(
        gather_sites(fields, ["top", "bot"], sites),
        [[1013, 21, 1002], [1113, 121, 1102], [1213, 221, 1202]],
    )


def test_gather_refuses_missing_dies():
    with pytest.raises(ValueError, match="missing transient field"):
        gather_sites({"top": np.zeros((4, 2, 3))}, ["top", "bot"], [[1, 0, 0]])


@pytest.mark.parametrize(("site", "error"), [
    ([0, 2, 0], "outside the field"),
    ([0, 0, 3], "outside the field"),
    ([0, -1, 1], "within the die list"),
])
def test_gather_refuses_out_of_range_cells(site, error):
    with pytest.raises(ValueError, match=error):
        gather_sites({"top": np.zeros((4, 2, 3))}, ["top"], [site])


def test_lag_step_matches_closed_form_at_every_row():
    grid = SlotGrid(DT, STEP)
    t = np.arange(1, 13) * STEP
    observed = sensor_lag(np.ones((len(t), 2)), grid, TAU, initial_rise=0)
    expected = np.column_stack([1 - np.exp(-t / TAU)] * 2)
    np.testing.assert_allclose(observed, expected, rtol=1e-14, atol=1e-15)


def test_lag_has_its_own_initial_state():
    grid = SlotGrid(DT, STEP)
    initial = np.array([0.8, 0.3])
    observed = sensor_lag(np.zeros((4, 2)), grid, TAU, initial_rise=initial)
    np.testing.assert_allclose(observed, np.exp(-np.outer(np.arange(1, 5) * STEP, [1 / TAU])) * initial,
                               rtol=1e-14, atol=1e-15)


@pytest.mark.parametrize("tau", [0, 1e-15])
def test_instantaneous_lag_recovers_the_input(tau):
    grid = SlotGrid(DT, STEP)
    rise = np.array([[0.0, 1.0], [1.0, 1e-18], [0.5, 0.0], [0.0, 0.5]])
    np.testing.assert_array_equal(sensor_lag(rise, grid, tau, initial_rise=0), rise)


def test_temperature_noise_is_drawn_at_slot_ends():
    grid = SlotGrid(DT, STEP)
    rise = np.arange(24, dtype=float).reshape(12, 2)
    expected = rise[[3, 7, 11]] + np.random.default_rng(1).normal(0, 0.1, size=(3, 2))
    np.testing.assert_array_equal(sample_temperature(rise, grid, 3, 0.1, np.random.default_rng(1)), expected)


def test_sampling_rejects_partial_slots():
    with pytest.raises(ValueError, match="rows, not"):
        sample_temperature(np.ones((5, 1)), SlotGrid(DT, STEP), 1, 0, np.random.default_rng(0))


def test_sampling_rejects_a_trace_at_another_resolution():
    fine = np.ones((8, 1))                      # one slot at 0.0625 ms read with the 0.125 ms grid
    with pytest.raises(ValueError, match="rows, not"):
        sample_temperature(fine, SlotGrid(DT, STEP), 1, 0, np.random.default_rng(0))


def test_grid_accepts_rows_that_tile_a_slot_the_runner_can_write():
    assert SlotGrid(3e-4, 1e-4).m == 3


def test_rail_noise_tracks_truth_but_stated_scale_stays_fixed():
    totals = np.array([[0.0, 3.0], [2.0, 5.0], [6.0, 4.0]])
    stated = [0.04, 0.08]
    rail, rail_std = rail_observation(totals, stated, np.random.default_rng(2))
    shifted_rail, shifted_std = rail_observation(totals + 1, stated, np.random.default_rng(2))
    noise = np.random.default_rng(2).standard_normal(totals.shape)
    np.testing.assert_array_equal(rail, totals + 0.02 * totals * noise)
    np.testing.assert_array_equal(shifted_rail, totals + 1 + 0.02 * (totals + 1) * noise)
    np.testing.assert_array_equal(rail_std, np.tile(stated, (len(totals), 1)))
    np.testing.assert_array_equal(rail_std, shifted_std)


def test_rail_outputs_match_the_estimator_slot_shapes():
    rail, rail_std = rail_observation(np.ones((3, 2)), [0.04, 0.08], np.random.default_rng(2))
    temperatures = np.ones((3, 4))
    rows = list(_slots(temperatures, 4, 0.1, rail, 2, rail_std))
    assert len(rows) == len(temperatures)
    for k, (obs, variance) in enumerate(rows):
        np.testing.assert_array_equal(obs, np.r_[temperatures[k], rail[k]])
        np.testing.assert_array_equal(variance, np.r_[np.full(4, 0.1 ** 2), rail_std[k] ** 2])


def test_crossing_window_splits_energy_between_slots():
    grid = SlotGrid(DT, STEP)
    edges = DT * np.array([0, 0.5, 1.5, 2])
    watts = np.array([[2.0, 0.0], [6.0, 4.0], [0.0, 8.0]])
    out = slot_power(edges, watts, grid)
    np.testing.assert_allclose(out, [[4, 2], [3, 6]], rtol=1e-15, atol=0)
    np.testing.assert_allclose(out.sum(axis=0) * DT, np.diff(edges) @ watts, rtol=1e-15, atol=0)


def test_window_power_refuses_uncovered_partial_slot():
    grid = SlotGrid(DT, STEP)
    with pytest.raises(ValueError, match="whole number of slots"):
        slot_power([0, 1.5 * DT], np.array([2.0]), grid)
