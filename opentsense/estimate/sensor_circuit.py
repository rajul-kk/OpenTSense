"""A temperature sensor whose error comes from its simulated circuit (goal 18, G106), not a datasheet class.

    reading = quantise(T + error_corner(T) + droop_corner x squeeze_mV + noise, step)

Each chip comes from one process corner (TT, SS or FF, drawn per chip with equal odds: ASSUMED, no foundry
distribution is public), and every sensor of the chip shares it. `error_corner(T)` is the trimmed sensor's error at
that corner (`gates/g106/dry/derive.py`: a one-point trim at 85 C against the TT curve), interpolated linearly in
temperature over the swept 0-125 C and held at the ends. `squeeze_mV` is the supply squeeze (VDD drop plus VSS rise)
at the sensor; `droop_corner` is the reading's rise per mV of squeeze, the slope linearised at the trim point (right
for squeezes of a few mV; the 1% read-back grows faster). A regulated sensor has no squeeze term. Step and noise are
the readout's (ASSUMED, G102's ring_osc values). Temperatures are absolute (K).
"""
from dataclasses import dataclass

import numpy as np

K0 = 273.15
CORNERS = ("tt", "ss", "ff")


@dataclass(frozen=True)
class CircuitProfile:
    temps_C: tuple             # swept temperatures, increasing
    error_K: dict              # corner -> error at each swept temperature (K)
    droop_K_per_mV: dict       # corner -> reading rise per mV of squeeze
    step_K: float
    noise_K: float

    @classmethod
    def ring(cls, derive, kit, step_K=0.25, noise_K=0.1):
        """From derive.json's ring/<kit> entry."""
        r = derive["ring"][kit]
        temps = tuple(sorted(int(t) for t in r["corner_error_K"]["tt"]))
        return cls(temps, {c: tuple(r["corner_error_K"][c][str(t)] for t in temps) for c in CORNERS},
                   {c: float(r["droop_K_per_mV"][c]) for c in CORNERS}, step_K, noise_K)

    @classmethod
    def dvbe(cls, derive, trim, step_K=0.25, noise_K=0.1):
        """From derive.json's dvbe entry; trim 'one_point' or 'two_point'. No supply term (bias not modelled)."""
        d = derive["dvbe"]
        key = f"error_{trim}_K"
        temps = tuple(sorted(int(t) for t in d["tt"][key]))
        return cls(temps, {c: tuple(d[c][key][str(t)] for t in temps) for c in CORNERS}, {c: 0.0 for c in CORNERS},
                   step_K, noise_K)

    def error(self, corner, T_abs):
        return np.interp(np.asarray(T_abs, float) - K0, self.temps_C, self.error_K[corner])

    def total_sigma(self, T_abs, squeeze_mV=None):
        """What an estimator is told: the rms over corners (equal odds) of the systematic error at temperatures
        T_abs (plus the squeeze term, if any), quantisation and noise, in quadrature."""
        sq = 0.0 if squeeze_mV is None else np.asarray(squeeze_mV, float)
        sys2 = np.mean([np.mean((self.error(c, T_abs) + self.droop_K_per_mV[c] * sq) ** 2) for c in CORNERS])
        return float(np.sqrt(sys2 + self.step_K ** 2 / 12 + self.noise_K ** 2))


def draw_corner(rng):
    return CORNERS[int(rng.integers(len(CORNERS)))]


def read(profile, corner, T_abs, rng, squeeze_mV=None):
    """Readings (K) for true temperatures T_abs (..., n_sensors) of a chip at `corner`; squeeze_mV broadcasts."""
    T = np.asarray(T_abs, float)
    y = T + profile.error(corner, T) + rng.normal(0.0, profile.noise_K, T.shape)
    if squeeze_mV is not None:
        y = y + profile.droop_K_per_mV[corner] * np.asarray(squeeze_mV, float)
    return np.round(y / profile.step_K) * profile.step_K if profile.step_K > 0 else y
