"""G102: G84's case set with its readings replaced by a sensor profile's readings for one chip.

    with_sensor(cs, profile, chip_seed) -> CaseSet

Every case (train, cal and test: one chip) is read by the same sensors at ambient + rise (ambient from the case set's
stack config), and the readings are returned as rises like G84's. noise_K, what the estimators are told, is the
profile's datasheet total (`sensor.Profile.total_sigma`) over the train split's sensor temperatures only, so nothing
from the scored cases reaches the estimators. Each (profile, chip) has its own generator, keyed by the profile's
name, so readings do not depend on which other profiles exist.
"""
import os
import zlib

import numpy as np

from opentsense.bench.cases import CaseSet
from opentsense.estimate import sensor
from opentsense.stack import model

STACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "configs", "stacks")


def with_sensor(cs, profile, chip_seed):
    p = sensor.PROFILES[profile]
    ambient = model.load(os.path.join(STACKS, f"{cs.stack_id}.yaml")).ambient_K
    rng = np.random.default_rng([102, zlib.crc32(profile.encode()), chip_seed])
    s = cs.sensors
    T = cs.T[:, s[:, 0], s[:, 1], s[:, 2]].astype(np.float64) + ambient
    chip = sensor.Chip.draw(p, len(s), rng)
    return CaseSet({**cs.a, "readings": chip.read(T, rng) - ambient, "noise_K": p.total_sigma(T[cs.idx("train")])})
