"""On-die temperature sensor model: what a real sensor reports for a true temperature (goal 12).

    reading = quantise(T + offset + gain * (T - T_TRIM) + noise, step)

`offset` (K) and `gain` (relative slope error) are drawn once per sensor of one chip, so they are fixed across every
reading of that chip; `noise` is drawn per reading. Temperatures are absolute (K); a rise-only caller adds its
ambient first. Sampling: `sample` reads a transient field at every `period_s` (zero-order hold, the last sample
until the next), which a steady case does not need.

Correlated offsets (goal 17): process variation is smooth across a die, so neighbouring sensors share part of their
offset. `Chip.draw(..., corr=Correlation(...))` splits each sensor's offset variance into an independent part and a
share drawn from a zero-mean Gaussian field on the die with squared-exponential covariance of length `length_mm`;
dies are independent (each comes from its own wafer). The total 1-sigma offset stays the profile's. The smooth
field is drawn from a child generator (rng.spawn), so the chip's later per-reading noise is the same stream with or
without `corr`; without it the draws are exactly those of the independent model.

Profiles (offset and gain as 1-sigma; values graded B, from published sensors, not one product). offset_K is the
cited whole-range figure and the gain term comes on top of it, so a profile is somewhat worse than its cited class
(a conservative choice):
- bjt_trimmed: BJT sensor after a one-point trim, +-0.4 K (3 sigma) over -40..125 C in 22 nm (TU Delft, JSSC 2025);
  sigma 0.13 K, gain error 0.1%, 0.0625 K steps (a 12-bit-class code), noise 0.02 K.
- ring_osc: ring-oscillator sensor after a one-point trim, about +-1.5 to 3 K (survey in Sensors 24(11), 2024,
  PMC11154328); sigma 1.0 K, gain error 1%, 0.25 K steps, noise 0.1 K.
- dts_1c: a production digital thermal sensor read through its 1 K register (Linux coretemp: 1 C resolution); its
  accuracy is several K and generation-dependent (Intel 45 nm: -5/+10 C near 90 C, as quoted by Tom's Hardware,
  graded C), so sigma 2.0 K, gain error 2%, 1 K steps, noise 0.1 K.
- ideal_gauss: G84's model (exact temperature plus N(0, 0.1 K)), for comparison.
"""
from dataclasses import dataclass

import numpy as np

T_TRIM = 358.15     # trim (and reference) temperature, K: the junction limit the margins use


@dataclass(frozen=True)
class Profile:
    offset_K: float     # 1-sigma per-sensor offset
    gain: float         # 1-sigma per-sensor slope error (relative)
    step_K: float       # quantisation step; 0 = none
    noise_K: float      # 1-sigma per-reading noise

    def total_sigma(self, T_abs):
        """The datasheet total a user would enter for readings around temperatures T_abs (K): offset, gain at the rms
        distance from the trim point, quantisation and noise, in quadrature."""
        gain_K = self.gain * float(np.sqrt(np.mean((np.asarray(T_abs, float) - T_TRIM) ** 2)))
        return float(np.sqrt(self.offset_K ** 2 + gain_K ** 2 + self.step_K ** 2 / 12 + self.noise_K ** 2))


PROFILES = {
    "ideal_gauss": Profile(0.0, 0.0, 0.0, 0.1),
    "bjt_trimmed": Profile(0.13, 0.001, 0.0625, 0.02),
    "ring_osc": Profile(1.0, 0.01, 0.25, 0.1),
    "dts_1c": Profile(2.0, 0.02, 1.0, 0.1),
}


@dataclass(frozen=True)
class Correlation:
    xy_mm: np.ndarray       # (n, 2) sensor positions on their die
    die: np.ndarray         # (n,) die index; offsets on different dies are independent
    share: float            # share of the offset variance that is the smooth field, 0..1
    length_mm: float        # correlation length of the smooth field

    def cov(self):
        xy, die = np.asarray(self.xy_mm, float), np.asarray(self.die)
        d2 = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
        return np.exp(-d2 / (2 * self.length_mm ** 2)) * (die[:, None] == die[None, :])


@dataclass(frozen=True)
class Chip:
    """One chip's sensors: their fixed offsets and gain errors."""
    profile: Profile
    offset: np.ndarray
    gain: np.ndarray

    @classmethod
    def draw(cls, profile, n_sensors, rng, corr=None):
        p = PROFILES[profile] if isinstance(profile, str) else profile
        off, gain = rng.normal(0.0, p.offset_K, n_sensors), rng.normal(0.0, p.gain, n_sensors)
        if corr is not None:
            if not (0 <= corr.share <= 1 and corr.length_mm > 0 and np.shape(corr.xy_mm) == (n_sensors, 2)
                    and len(corr.die) == n_sensors):
                raise ValueError("need 0 <= share <= 1, length_mm > 0 and one (x, y) and die per sensor")
            L = np.linalg.cholesky(corr.cov() + 1e-10 * np.eye(n_sensors))
            smooth = L @ rng.spawn(1)[0].normal(0.0, p.offset_K, n_sensors)
            off = np.sqrt(1 - corr.share) * off + np.sqrt(corr.share) * smooth
        return cls(p, off, gain)

    def read(self, T, rng):
        """Readings (K) for true temperatures T (..., n_sensors), absolute."""
        T = np.asarray(T, float)
        y = T + self.offset + self.gain * (T - T_TRIM) + rng.normal(0.0, self.profile.noise_K, T.shape)
        step = self.profile.step_K
        return np.round(y / step) * step if step > 0 else y


def sample(t_s, T, period_s, t0_s=0.0):
    """Zero-order hold on sorted times t_s (n,) of a field T (n, ...): the sensor samples at t0 + k period (the first
    time step at or after each instant, to rounding) and holds it. Where no sample has been taken yet (before t0, or a
    sample instant before t_s[0]) the reading is NaN."""
    t_s, T = np.asarray(t_s, float), np.asarray(T, float)
    if period_s <= 0 or len(T) != len(t_s) or np.any(np.diff(t_s) < 0):
        raise ValueError("need period_s > 0, one row of T per time, and sorted times")
    tol = max(1e-9 * period_s, 64 * np.finfo(float).eps * max(np.abs(t_s).max(initial=0.0), abs(t0_s)))
    k = np.floor((t_s - t0_s + tol) / period_s)                      # the last sample instant at or before t
    instant = t0_s + k * period_s
    first = np.searchsorted(t_s, instant - tol)                      # the step that took that sample
    out = T[np.clip(first, 0, len(t_s) - 1)].copy()
    out[(k < 0) | (instant < t_s[0] - tol)] = np.nan
    return out
