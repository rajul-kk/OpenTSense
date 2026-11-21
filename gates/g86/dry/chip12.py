"""G86 post-run diagnosis (exploratory, after the verdict): which sensor chip 12's check dropped, and that sensor's
drawn offset and gain, by redrawing the chip exactly as gates/g102/readings.py does.

Usage (repo root): python gates/g86/dry/chip12.py gates/g86/runs/main/cases.npz
"""
import os
import sys
import zlib

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "gates", "g102")]
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate import fault, sensor  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402
import readings  # noqa: E402


def main(cases, chip=12):
    cs0 = CaseSet.load(cases)
    tr, te = cs0.idx("train"), cs0.idx("test")
    gf = GaussianField(energy=0.9999).fit(cs0.T[tr].reshape(len(tr), -1))
    cs = readings.with_sensor(cs0, "ring_osc", chip)
    S, y, noise = cs0.flat_sensors, cs.readings[te].astype(np.float64), float(cs.noise_K)
    _, dropped = fault.repair(gf, S, y, noise, fault.threshold(0.01, len(S)))
    ids, counts = np.unique(dropped[dropped >= 0], return_counts=True)
    rng = np.random.default_rng([102, zlib.crc32(b"ring_osc"), chip])
    chip_draw = sensor.Chip.draw(sensor.PROFILES["ring_osc"], len(S), rng)
    print("dropped sensors and counts:", dict(zip(ids.tolist(), counts.tolist())))
    print("offsets (K):", np.round(chip_draw.offset, 2).tolist())
    print("largest |offset| sensor:", int(np.abs(chip_draw.offset).argmax()), "noise_K told:", round(noise, 3))


if __name__ == "__main__":
    main(sys.argv[1])
