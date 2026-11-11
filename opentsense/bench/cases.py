"""Case-set format for the benchmark (protocol.md section 2).

One .npz file holds a whole case set:

| key | shape | meaning |
|---|---|---|
| T | (N, D, ny, nx) | true temperature rise above ambient per die (K), on the stack grid |
| P | (N, D, nb) | true power per die and bin (W); optional |
| readings | (N, m) | sensor readings (K), noise already added |
| sensors | (m, 3) int | (die, row, col) of each sensor; row = y index from the die's lower edge |
| noise_K | () | sensor noise standard deviation |
| split | (N,) str | train, cal or test |
| group | (N,) str | grouping unit (workload family x design); a group never spans splits |
| tag | (N,) str | seen-group, unseen-workload, unseen-design or unseen-stack |
| dies | (D,) str | die names, stack order |
| buried | (D,) bool | die is buried (reported separately) |
| cell_um | () | grid pitch (um), for hotspot distance |
| R | (D * nb, D, ny, nx) | response of each power bin, K per W; optional (the stack knowledge an estimator may use) |
| stack_id | () str | |

An estimator sees the train split in full, and only `Public` (readings, sensors, noise, R, shapes) for the cases it
predicts.
"""
import hashlib
from dataclasses import dataclass

import numpy as np

REQUIRED = ("T", "readings", "sensors", "noise_K", "split", "group", "tag", "dies", "buried", "cell_um", "stack_id")
SPLITS = ("train", "cal", "test")


@dataclass
class Public:
    readings: np.ndarray
    sensors: np.ndarray
    noise_K: float
    R: np.ndarray | None
    shape: tuple          # (D, ny, nx)
    nb: int | None        # power bins per die, if the case set has power


def _check(ok, msg):
    if not ok:
        raise ValueError(msg)


class CaseSet:
    def __init__(self, arrays: dict):
        missing = [k for k in REQUIRED if k not in arrays]
        if missing:
            raise ValueError(f"case set lacks {missing}")
        self.a = {k: np.asarray(v) for k, v in arrays.items()}
        self.validate()

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as z:
            return cls({k: z[k] for k in z.files})

    def save(self, path):
        np.savez_compressed(path, **self.a)

    def __getattr__(self, k):
        try:
            return self.__dict__["a"][k]
        except KeyError:
            raise AttributeError(k) from None

    @property
    def N(self):
        return len(self.a["T"])

    @property
    def has_power(self):
        return "P" in self.a

    def validate(self):
        """Raises ValueError on a malformed case set (explicit checks, so they also run under python -O)."""
        a = self.a
        N, D, ny, nx = a["T"].shape
        m = a["readings"].shape[1]
        _check(a["readings"].shape == (N, m), "readings must be (N, m)")
        _check(a["sensors"].shape == (m, 3), "sensors must be (m, 3)")
        s = a["sensors"]
        _check((s[:, 0] < D).all() and (s[:, 1] < ny).all() and (s[:, 2] < nx).all() and (s >= 0).all(), "sensor out of range")
        for k in ("split", "group", "tag"):
            _check(a[k].shape == (N,), f"{k} must be (N,)")
        _check(set(np.unique(a["split"])) <= set(SPLITS), "unknown split")
        for g in np.unique(a["group"]):
            sp = np.unique(a["split"][a["group"] == g])
            _check(len(sp) == 1, f"group {g} spans splits {list(sp)}")
        _check(a["dies"].shape == (D,) and a["buried"].shape == (D,), "dies and buried must be (D,)")
        if "P" in a:
            _check(a["P"].shape[:2] == (N, D), "P must be (N, D, nb)")
            if "R" in a:
                _check(a["R"].shape == (D * a["P"].shape[2], D, ny, nx), "R must be (D * nb, D, ny, nx)")

    def idx(self, split):
        return np.flatnonzero(self.a["split"] == split)

    def public(self, idx):
        a = self.a
        return Public(readings=a["readings"][idx], sensors=a["sensors"], noise_K=float(a["noise_K"]),
                      R=a.get("R"), shape=a["T"].shape[1:], nb=a["P"].shape[2] if "P" in a else None)

    def sensor_values(self, T):
        """Field values at the sensor cells: T (n, D, ny, nx) -> (n, m)."""
        s = self.a["sensors"]
        return T[:, s[:, 0], s[:, 1], s[:, 2]]

    def sha256(self):
        h = hashlib.sha256()
        for k in sorted(self.a):
            v = np.ascontiguousarray(self.a[k])
            h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(v.shape).encode()); h.update(v.tobytes())
        return h.hexdigest()
