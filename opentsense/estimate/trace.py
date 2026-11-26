"""G79 trace plumbing. Time is in seconds, temperature rise in K, and power in W."""

from dataclasses import dataclass, field
from math import exp, isclose, isfinite

import numpy as np

from ..stack.to_3dice import steps_per_slot

# Allow binary floating-point roundoff, but no rounding to a different solver cadence.
_TIME_RTOL = 4 * np.finfo(float).eps


@dataclass(frozen=True)
class SlotGrid:
    """A filter slot of length dt and m equal solver rows of length step.

    Row zero ends at step. Slot k ends at (k+1)*dt, on row m*(k+1)-1, as in
    `gates/g94/solve.py::on_grid`. For one map per row, run the solver with
    transient=(step, step) and one power map per row.
    """

    dt: float
    step: float
    m: int = field(init=False)

    def __post_init__(self):
        if not all(isfinite(t) and t > 0 for t in (self.dt, self.step)):
            raise ValueError("slot and row lengths must be finite and positive")
        ratio = self.dt / self.step
        if not isfinite(ratio) or ratio < 1:
            raise ValueError("a slot must contain a positive whole number of solver rows")
        m = round(ratio)
        if not isclose(ratio, m, rel_tol=_TIME_RTOL):
            raise ValueError("a slot must contain a positive whole number of solver rows")
        if any(not isclose(t, float(f"{t:.6e}"), rel_tol=_TIME_RTOL) for t in (self.dt, self.step)):
            raise ValueError("slot or row length changes at 3D-ICE's write precision")
        if steps_per_slot(self.step, self.step) != 1:          # the runner writes (step, step): one map per row
            raise ValueError("3D-ICE does not represent the requested rows per slot")
        object.__setattr__(self, "m", m)

    def sample_rows(self, n_slots):
        return np.arange(1, n_slots + 1, dtype=np.intp) * self.m - 1

    def sample_times(self, n_slots):
        return np.arange(1, n_slots + 1) * self.dt

    def row_times(self, n_slots):
        return np.arange(1, n_slots * self.m + 1) * self.step


def gather_sites(fields, dies, sites):
    """Extract (n_rows, n_sites) in site ID order from runner fields {die: (n_rows, ny, nx)}.

    As in G84, each ID is a row in sites, with (die index into dies, y row from
    the lower edge, x column). Temperatures keep their input units. For runner
    maps in absolute K, subtract the stack ambient from the gathered values
    before applying the lag.
    """
    sites = np.asarray(sites)
    if (sites.ndim != 2 or sites.shape[1] != 3 or not len(sites)
            or sites.dtype.kind not in "iu" or np.any(sites < 0) or np.any(sites[:, 0] >= len(dies))):
        raise ValueError("sites must be nonempty integer (die, row, col) triples within the die list")
    if len(set(dies)) != len(dies):
        raise ValueError("die names must be unique")
    for die in dies:
        if die not in fields:
            raise ValueError(f"missing transient field for die {die!r}")
    out = None
    for die_index in np.unique(sites[:, 0]):
        die = dies[die_index]
        maps = np.asarray(fields[die])
        if maps.ndim != 3 or len(maps) == 0 or (out is not None and len(maps) != len(out)):
            raise ValueError(f"{die!r} must have (n_rows, ny, nx) maps with the common row count")
        cols = np.flatnonzero(sites[:, 0] == die_index)
        local = sites[cols]
        if np.any(local[:, 1:] >= maps.shape[1:]):
            raise ValueError(f"site outside the field of die {die!r}")
        values = maps[:, local[:, 1], local[:, 2]].astype(float)   # as bench.readings._site_T, one die at a time
        if out is None:
            out = np.empty((len(maps), len(sites)), dtype=values.dtype)
        out[:, cols] = values
    return out


def _trace(values, name):
    a = np.asarray(values, dtype=float)
    if a.ndim != 2 or not all(a.shape) or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be a nonempty, finite two-dimensional trace")
    return a


def sensor_lag(site_rise, grid, tau, initial_rise):
    """Lag (n_rows, n_sites) temperatures by holding each solver row-end rise over its row.

    initial_rise is the sensor state at t=0, scalar or one value per site.
    Ambient is 0 K rise. tau=0 is the instantaneous sensor limit.
    """
    rise = _trace(site_rise, "site temperature rise")
    initial = np.asarray(initial_rise, dtype=float)
    if initial.shape not in ((), (rise.shape[1],)) or not np.all(np.isfinite(initial)):
        raise ValueError("initial sensor rise must be finite and scalar or one value per site")
    if not isfinite(tau) or tau < 0:
        raise ValueError("sensor lag must be finite and nonnegative")
    if tau == 0:
        return rise.copy()
    decay = exp(-grid.step / tau)
    lagged = np.empty_like(rise)
    state = np.broadcast_to(initial, (rise.shape[1],)).copy()
    for i, value in enumerate(rise):
        state = value + decay * (state - value)
        lagged[i] = state
    return lagged


def sample_temperature(lagged_rise, grid, n_slots, sigma_T, rng):
    """Return one noisy temperature-rise reading per completed slot and site.

    rng is the caller's temperature-noise child Generator. Both arms should
    use the same returned readings.
    """
    rise = _trace(lagged_rise, "lagged temperature rise")
    if len(rise) != n_slots * grid.m:           # a trace at another resolution must not be sampled silently
        raise ValueError(f"temperature trace has {len(rise)} rows, not {n_slots} slots of {grid.m}")
    if not isfinite(sigma_T) or sigma_T < 0:
        raise ValueError("temperature noise standard deviation must be finite and nonnegative")
    sampled = rise[grid.sample_rows(n_slots)]
    if sigma_T:
        sampled += rng.normal(0, sigma_T, size=sampled.shape)
    return sampled


def rail_observation(totals_W, stated_std_W, rng):
    """Return rail and rail_std, both (n_slots, n_dies), in W.

    The synthetic meter uses 2% of the true total for its draw. The filter gets
    the same caller-supplied stated error in every slot, one value per die.
    Use a separate rail-noise child Generator and share both outputs across arms.
    """
    totals = _trace(totals_W, "true rail totals")
    stated = np.asarray(stated_std_W, dtype=float)
    if np.any(totals < 0):
        raise ValueError("true rail totals must be nonnegative")
    if stated.shape != (totals.shape[1],) or not np.all(np.isfinite(stated) & (stated > 0)):
        raise ValueError("stated rail error must give one finite, positive standard deviation per die")
    measured = totals + 0.02 * totals * rng.standard_normal(totals.shape)
    return measured, np.broadcast_to(stated, totals.shape).copy()


def slot_power(window_edges, window_power, grid):
    """Return slot-average W from contiguous piecewise-constant windows.

    window_edges gives seconds from zero and covers whole slots to roundoff: form it as integer cycle
    indices times the cycle period, not a cumulative sum of durations (that drifts past the check).
    Each row of window_power applies from its left edge to its right edge.
    Trailing dimensions (such as die and bin) are preserved.
    """
    edges = np.asarray(window_edges, dtype=float)
    power = np.asarray(window_power, dtype=float)
    if (power.ndim == 0 or not all(power.shape) or not np.all(np.isfinite(power))
            or edges.shape != (len(power) + 1,) or not np.all(np.isfinite(edges))
            or edges[0] != 0 or np.any(np.diff(edges) <= 0)):
        raise ValueError("power windows need finite values and strictly increasing edges starting at zero")
    duration_slots = edges[-1] / grid.dt
    if not isfinite(duration_slots) or duration_slots < 0.5:
        raise ValueError("power windows must cover a positive whole number of slots")
    n_slots = round(duration_slots)
    if not isclose(duration_slots, n_slots, rel_tol=_TIME_RTOL):
        raise ValueError("power windows must cover a positive whole number of slots")
    out = np.zeros((n_slots, *power.shape[1:]))
    window = 0
    left = 0.0
    for slot in range(n_slots):
        right = edges[-1] if slot == n_slots - 1 else grid.dt * (slot + 1)
        while left < right:
            end = min(right, edges[window + 1])
            out[slot] += (end - left) * power[window]
            left = end
            if end == edges[window + 1]:
                window += 1
    out /= grid.dt
    return out
