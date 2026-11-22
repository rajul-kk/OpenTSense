"""A case set read by other sensors: new sites, a sensor profile, one chip.

    with_sites(cs, sensors)                         -> the case set with sensors (m, 3) = (die, row, col), no readings
                                                       and no noise (NaN), for with_sensor to fill
    ambient_K(cs)                                   -> the ambient of the case set's stack config (K)
    with_sensor(cs, profile, chip_seed, salt=102, corr=None)
                                                    -> its readings replaced by one chip of a sensor profile
    read_chip(cs, profile, chip_seed, salt=102, corr=None)
                                                    -> (that case set, the sensor.Chip that read it)
corr: None (independent offsets, G102's model) or (share, length_mm), sensor.Correlation at the sensors' positions.

with_sensor is G102's `gates/g102/readings.py` (which stays as run) moved here so later gates share it; with the
default salt it reproduces G102's readings exactly. Every case (train, cal and test: one chip) is read by the same
sensors at ambient + rise (ambient from the case set's stack config), and the readings are returned as rises.
noise_K, what the estimators are told, is the profile's datasheet total (`sensor.Profile.total_sigma`) over the train
split's sensor temperatures only, so nothing from the scored cases reaches the estimators. Each (salt, profile, chip)
has its own generator, so readings do not depend on which other profiles or chips exist.
"""
import os
import zlib

import numpy as np

from ..estimate import sensor
from ..stack import model
from .cases import CaseSet

STACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "configs", "stacks")


def with_sites(cs, sensors):
    s = np.asarray(sensors, int)
    return CaseSet({**cs.a, "sensors": s, "readings": np.full((cs.N, len(s)), np.nan), "noise_K": np.nan})


def ambient_K(cs):
    return model.load(os.path.join(STACKS, f"{cs.stack_id}.yaml")).ambient_K


def read_chip(cs, profile, chip_seed, salt=102, corr=None):
    p = sensor.PROFILES[profile]
    rng = np.random.default_rng([salt, zlib.crc32(profile.encode()), chip_seed])
    s = cs.sensors
    c = None if corr is None else sensor.Correlation((s[:, [2, 1]] + 0.5) * float(cs.cell_um) / 1000, s[:, 0], *corr)
    chip = sensor.Chip.draw(p, len(s), rng, c)
    ambient = ambient_K(cs)
    T = cs.T[:, s[:, 0], s[:, 1], s[:, 2]].astype(np.float64) + ambient
    out = CaseSet({**cs.a, "readings": chip.read(T, rng) - ambient, "noise_K": p.total_sigma(T[cs.idx("train")])})
    return out, chip


def with_sensor(cs, profile, chip_seed, salt=102, corr=None):
    return read_chip(cs, profile, chip_seed, salt, corr)[0]
