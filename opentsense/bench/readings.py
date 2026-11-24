"""A case set read by other sensors: new sites, a sensor profile, one chip.

    with_sites(cs, sensors)                         -> the case set with sensors (m, 3) = (die, row, col), no readings
                                                       and no noise (NaN), for with_sensor to fill
    ambient_K(cs)                                   -> the ambient of the case set's stack config (K)
    with_sensor(cs, profile, chip_seed, salt=102, corr=None)
                                                    -> its readings replaced by one chip of a sensor profile
    read_chip(cs, profile, chip_seed, salt=102, corr=None)
                                                    -> (that case set, the sensor.Chip that read it)
    read_circuit(cs, name, profile, chip_seed, salt, squeeze_mV=None)
                                                    -> (the case set read by a circuit sensor, the chip's corner)
    subset(cs, cols, profile)                       -> a read case set keeping only sensors `cols`, same draws
corr: None (independent offsets, G102's model) or (share, length_mm), sensor.Correlation at the sensors' positions.

with_sensor is G102's `gates/g102/readings.py` (which stays as run) moved here so later gates share it; with the
default salt it reproduces G102's readings exactly. Every case (train, cal and test: one chip) is read by the same
sensors at ambient + rise (ambient from the case set's stack config), and the readings are returned as rises.
noise_K, what the estimators are told, is the profile's datasheet total (`sensor.Profile.total_sigma`) over the train
split's sensor temperatures only, so nothing from the scored cases reaches the estimators. Each (salt, profile, chip)
has its own generator, so readings do not depend on which other profiles or chips exist.
"""
import os

import numpy as np

from ..estimate import sensor, sensor_circuit
from ..stack import model
from .cases import CaseSet

STACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "configs", "stacks")


def with_sites(cs, sensors):
    s = np.asarray(sensors, int)
    return CaseSet({**cs.a, "sensors": s, "readings": np.full((cs.N, len(s)), np.nan), "noise_K": np.nan})


def ambient_K(cs):
    return model.load(os.path.join(STACKS, f"{cs.stack_id}.yaml")).ambient_K


def _site_T(cs, s, ambient):
    """(N, m) absolute temperature (K) at sites s (m, 3) = (die, row, col) in every case."""
    return cs.T[:, s[:, 0], s[:, 1], s[:, 2]].astype(np.float64) + ambient


def read_chip(cs, profile, chip_seed, salt=102, corr=None):
    p = sensor.PROFILES[profile]
    rng = sensor.chip_rng(profile, chip_seed, salt)
    s = cs.sensors
    c = None if corr is None else sensor.Correlation((s[:, [2, 1]] + 0.5) * float(cs.cell_um) / 1000, s[:, 0], *corr)
    chip = sensor.Chip.draw(p, len(s), rng, c)
    ambient = ambient_K(cs)
    T = _site_T(cs, s, ambient)
    out = CaseSet({**cs.a, "readings": chip.read(T, rng) - ambient, "noise_K": p.total_sigma(T[cs.idx("train")])})
    return out, chip


def read_circuit(cs, name, profile, chip_seed, salt, squeeze_mV=None):
    """A sensor_circuit.CircuitProfile `profile` (called `name`, which keys its generator), one chip at a corner drawn
    from that generator. squeeze_mV: None (a regulated sensor) or (N, m), the supply squeeze at each sensor in each
    case. noise_K is the profile's total over the train split only, squeeze included."""
    rng = sensor.chip_rng(name, chip_seed, salt)
    corner = sensor_circuit.draw_corner(rng)
    s, ambient, tr = cs.sensors, ambient_K(cs), cs.idx("train")
    T = _site_T(cs, s, ambient)
    sq = None if squeeze_mV is None else np.asarray(squeeze_mV, float)
    if sq is not None and sq.shape != T.shape:
        raise ValueError(f"squeeze_mV is {sq.shape}, need one value per case and sensor {T.shape}")
    y = sensor_circuit.read(profile, corner, T, rng, sq) - ambient
    noise = profile.total_sigma(T[tr], None if sq is None else sq[tr])
    return CaseSet({**cs.a, "readings": y, "noise_K": noise}), corner


def with_sensor(cs, profile, chip_seed, salt=102, corr=None):
    return read_chip(cs, profile, chip_seed, salt, corr)[0]


def subset(cs, cols, profile):
    """The case set read by only the sensors `cols` of an already read chip: the same per-sensor errors and draws,
    so site sets compared on one chip differ only in which sensors are read. noise_K is recomputed as read_chip
    does, over the train split's temperatures at the kept sensors."""
    cols = np.asarray(cols, int)
    s = cs.sensors[cols]
    T = _site_T(cs, s, ambient_K(cs))
    return CaseSet({**cs.a, "sensors": s, "readings": cs.readings[:, cols],
                    "noise_K": sensor.PROFILES[profile].total_sigma(T[cs.idx("train")])})
